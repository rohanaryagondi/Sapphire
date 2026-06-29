"""Deterministic EMET (BenchSci) browser capture — NO LLM in the loop.

Drives EMET in the authenticated Playwright browser, waits deterministically for the
answer to finish, then **scrapes the rendered DOM** (answer body + Sources panel) into
an EMET envelope (`emet_protocol.md §7`). The `claude -p` LLM-agent runner
(`handler._default_runner`) tool-fails / is too slow; this is the robust path while the
EMET-MCP is unavailable.

Design:
  * `parse_emet_html(...)` is a PURE, stdlib-only (`html.parser`) DOM->envelope function.
    It is what the offline test exercises (no browser needed) and what `capture_emet`
    calls on the live `page.content()`. NO reasoning — selectors + regex only.
  * `capture_emet(...)` is the live driver. **Playwright is imported lazily inside the
    function**, so importing this module (and never `live_engine`) does NOT pull in
    Playwright — the engine import path stays stdlib.

Honesty / boundary:
  * Login screen (`id.summit.benchsci.com`) / timeout / no answer -> honest abstain
    (`{"login_required": True}` or a raised/returned signal). NEVER fabricate PMIDs.
  * Only PUBLIC identifiers ever cross to EMET (the query carries gene/disease terms);
    the envelope carries public PMIDs/DOIs only.

This is NOT imported by the engine. It is a standalone tool (like `_build/emet_login.py`),
run via the CLI to produce `scenarios/emet_envelopes/<candidate>.json`, which the
session-bridge (`make_session_emet_handler`) then feeds into `run_live`.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]            # repo root
ENVELOPES_DIR = ROOT / "sapphire-orchestrator" / "scenarios" / "emet_envelopes"

EMET_URL = "https://emet.benchsci.com/"

# Default persistent Chromium profile for BenchSci (gitignored under RohanOnly/).
# Set via $SAPPHIRE_EMET_PROFILE or --profile; this is the fallback when neither is supplied.
BENCHSCI_PROFILE = ROOT / "RohanOnly" / "benchsci_profile"

_LOGIN_HOSTS = ("id.summit.benchsci.com", "accounts.google.com", "login.microsoftonline",
                "okta", "auth0", "/login", "duosecurity")

# Map a free-text candidate/question hint to one of the 5 schema-allowed workflows.
_WORKFLOWS = ("Drug Safety", "Target Validation", "Pathway Analysis",
              "Quantitative Evidence", "Database Q&A")

_PMID_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")
_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
_PMID_TEXT_RE = re.compile(r"\bPMID[:\s]*?(\d{4,9})\b", re.IGNORECASE)


# --------------------------------------------------------------------------------------
# Pure DOM -> envelope (stdlib only; this is what the offline test drives)
# --------------------------------------------------------------------------------------
class _TextHarvester(HTMLParser):
    """Walks the DOM collecting (a) the answer-article paragraphs, (b) every PubMed/DOI link
    with the visible text around it, and (c) raw text. Deterministic — no reasoning."""

    # Tags whose text we treat as block boundaries (so sentences don't run together).
    _BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "div", "section", "article", "br", "td", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._stack: list[str] = []
        self._article_depth = 0           # >0 while inside an <article>
        self._cur_href: str | None = None
        self._cur_link_text: list[str] = []
        # outputs
        self.blocks: list[str] = []                      # block-level text fragments (all)
        self.article_blocks: list[str] = []              # block text inside <article>
        self._buf: list[str] = []                        # current block buffer
        self.links: list[dict] = []                      # {href, text}
        self.full_text_parts: list[str] = []

    # -- helpers
    def _flush_block(self) -> None:
        txt = " ".join(" ".join(self._buf).split())
        if txt:
            self.blocks.append(txt)
            if self._article_depth > 0:
                self.article_blocks.append(txt)
        self._buf = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        self._stack.append(tag)
        if tag == "article":
            self._article_depth += 1
        if tag in self._BLOCK:
            self._flush_block()
        if tag == "a":
            href = dict(attrs).get("href") or ""
            self._cur_href = href
            self._cur_link_text = []

    def handle_startendtag(self, tag, attrs):
        if tag.lower() == "br":
            self._flush_block()

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "a" and self._cur_href is not None:
            text = " ".join(" ".join(self._cur_link_text).split())
            self.links.append({"href": self._cur_href, "text": text})
            self._cur_href = None
            self._cur_link_text = []
        if tag in self._BLOCK:
            self._flush_block()
        if tag == "article" and self._article_depth > 0:
            self._article_depth -= 1
        # pop matching tag
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i] == tag:
                del self._stack[i]
                break

    def handle_data(self, data):
        if not data:
            return
        self._buf.append(data)
        self.full_text_parts.append(data)
        if self._cur_href is not None:
            self._cur_link_text.append(data)

    def close(self):  # type: ignore[override]
        super().close()
        self._flush_block()


def _is_login_html(html: str) -> bool:
    """Deterministically decide if `html` is a BenchSci login/SSO screen.

    Conservative on purpose: the authenticated SPA bundle references auth providers
    (e.g. ``auth0``) in its JavaScript, so a bare substring match would false-positive on a
    real answer page. A login screen has (a) a password field with a sign-in affordance and
    NO answer article, OR (b) the canonical login redirect host AND no answer article.
    The live driver also checks the page URL via ``_on_login_page`` (the authoritative signal)."""
    low = html.lower()
    has_article = "<article" in low
    if has_article:
        return False
    has_pw = 'type="password"' in low
    if has_pw and ("sign in" in low or "log in" in low or "log in to" in low):
        return True
    # The canonical BenchSci login redirect host, only meaningful when no answer rendered.
    if "id.summit.benchsci.com" in low and ("sign in" in low or "log in" in low or has_pw):
        return True
    return False


def pick_workflow(candidate: str, query: str) -> str:
    """Deterministic workflow choice from the question text (no LLM). Defaults to Database Q&A."""
    q = f"{candidate} {query}".lower()
    if any(w in q for w in ("safety", "toxic", "adverse", "contraindicat", "side effect")):
        return "Drug Safety"
    if any(w in q for w in ("pathway", "network", "interactome", "signal")):
        return "Pathway Analysis"
    if any(w in q for w in ("effect size", "quantitat", "odds ratio", "hazard ratio", "how many")):
        return "Quantitative Evidence"
    if any(w in q for w in ("viable target", "validation", "validate", "druggab", "target for",
                            "genetic evidence", "association")) or (
            "viable" in q and "target" in q) or ("therapeutic target" in q):
        return "Target Validation"
    return "Database Q&A"


def _derive_verdict(answer_text: str, candidate: str) -> str:
    """Conservative, documented heuristic (NO LLM). Default 'pass' when cited evidence exists;
    downgrade only on explicit textual markers. The roundtable, not EMET, decides go/no-go;
    EMET corroborates/gates, so we keep this deliberately cautious."""
    low = answer_text.lower()
    no_go_markers = ("contraindicated", "not a viable", "is not viable", "strong safety concern",
                     "serious safety", "black box", "withdrawn from market")
    flag_markers = ("insufficient evidence", "no studies", "no direct evidence", "limited evidence",
                    "unclear", "conflicting", "remains uncertain", "thin evidence",
                    "no published", "further research is needed", "not well established")
    if any(m in low for m in no_go_markers):
        return "no_go"
    if any(m in low for m in flag_markers):
        return "flag"
    return "pass"


def _split_sentences(block: str) -> list[str]:
    # Lightweight sentence split; keeps citation brackets attached.
    parts = re.split(r"(?<=[.;])\s+(?=[A-Z0-9])", block)
    return [p.strip() for p in parts if p.strip()]


def parse_emet_html(html: str, *, candidate: str, query: str = "",
                    chat_url: str = "", workflow: str | None = None,
                    captured_at: str | None = None) -> dict:
    """PURE DOM -> EMET envelope. stdlib only. NO browser, NO LLM.

    Returns the `emet_protocol.md §7` envelope (8 keys, schema-valid) on success, or
    ``{"login_required": True}`` if `html` is a BenchSci login screen. Never fabricates:
    if the answer carries no citable PMIDs/DOIs the envelope's evidence is ``[]`` and the
    verdict is downgraded to ``flag``.
    """
    if _is_login_html(html):
        return {"login_required": True}

    h = _TextHarvester()
    h.feed(html)
    h.close()

    # Prefer the answer <article> text; fall back to all block text if no <article> rendered.
    article_blocks = h.article_blocks or h.blocks
    answer_text = "\n".join(article_blocks).strip()

    # --- inline PubMed citations (href -> PMID) ---
    inline_pmids: list[str] = []
    for link in h.links:
        m = _PMID_RE.search(link["href"] or "")
        if m:
            inline_pmids.append(m.group(1))

    # --- Sources panel: any link to pubmed/doi, plus printed PMID/DOI in source rows ---
    sources: list[dict] = []          # {id, kind, source}
    seen_ids: set[str] = set()

    def _add_source(_id: str, kind: str, label: str) -> None:
        if not _id or _id in seen_ids:
            return
        seen_ids.add(_id)
        sources.append({"id": _id, "kind": kind, "source": (label or "").strip()})

    for link in h.links:
        href = link["href"] or ""
        label = link["text"] or ""
        mp = _PMID_RE.search(href)
        if mp:
            _add_source(f"PMID:{mp.group(1)}", "pmid", label)
            continue
        md = _DOI_RE.search(href)
        if md and "doi.org" in href:
            _add_source(md.group(0).rstrip(".,);"), "doi", label)
    # Printed (non-linked) PMIDs / DOIs anywhere in the text (Sources panel often prints them).
    full_text = " ".join(h.full_text_parts)
    for m in _PMID_TEXT_RE.finditer(full_text):
        _add_source(f"PMID:{m.group(1)}", "pmid", "")
    for m in _DOI_RE.finditer(full_text):
        _add_source(m.group(0).rstrip(".,);"), "doi", "")

    # --- Build evidence: pair answer sentences with the citation id they mention ---
    evidence: list[dict] = []
    used_ids: set[str] = set()
    for block in article_blocks:
        for sent in _split_sentences(block):
            ids_here: list[str] = []
            for pm in _PMID_TEXT_RE.finditer(sent):
                ids_here.append(f"PMID:{pm.group(1)}")
            for dm in _DOI_RE.finditer(sent):
                ids_here.append(dm.group(0).rstrip(".,);"))
            for _id in ids_here:
                if _id in used_ids:
                    continue
                used_ids.add(_id)
                evidence.append({"claim": sent, "source": "EMET (BenchSci)", "id_or_url": _id})

    # If the answer cited PMIDs inline (links) but they weren't printed in the sentence text,
    # still surface them as evidence paired with the nearest answer block, de-duped.
    for pmid in inline_pmids:
        _id = f"PMID:{pmid}"
        if _id in used_ids:
            continue
        used_ids.add(_id)
        claim = article_blocks[0] if article_blocks else f"EMET evidence for {candidate}"
        evidence.append({"claim": claim, "source": "EMET (BenchSci)", "id_or_url": _id})

    # Fold any source ids not yet represented in evidence (Sources panel entries).
    for s in sources:
        if s["id"] in used_ids:
            continue
        used_ids.add(s["id"])
        evidence.append({"claim": (s["source"] or f"EMET source for {candidate}"),
                         "source": "EMET (BenchSci)", "id_or_url": s["id"]})

    wf = workflow or pick_workflow(candidate, query)
    if wf not in _WORKFLOWS:
        wf = "Database Q&A"

    verdict = _derive_verdict(answer_text, candidate)
    if not evidence:
        # No citable evidence scraped -> honest thin-evidence flag, NEVER a fabricated PMID.
        verdict = "flag"

    notes_bits = []
    if not evidence:
        notes_bits.append("no citable PMIDs/DOIs scraped from the rendered answer")
    notes = "; ".join(notes_bits)

    return {
        "candidate": candidate,
        "emet_workflow": wf,
        "verdict": verdict,
        "evidence": evidence,
        "notes": notes,
        "chat_url": chat_url or "",
        "captured_at": captured_at or _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "provenance": "emet-live",
    }


# --------------------------------------------------------------------------------------
# Live driver (Playwright imported lazily — keeps this module's import cheap)
# --------------------------------------------------------------------------------------
def _profile_has_session(profile_dir) -> bool:
    """True when profile_dir contains a Chromium Cookies file.

    Playwright (and Chromium) only write `Default/Cookies` after a real authenticated
    session, NOT on a bare `launch_persistent_context` launch that was interrupted before
    the user completed login.  A non-empty dir check would false-positive on a partial
    (interrupted) login attempt, causing a slow (~30-45s) headless launch that ends with
    honest abstain at the `_on_login_page` gate anyway.

    Returns False for:
    - None / missing directory
    - directory created by an interrupted `python -m emet.login` (no `Default/Cookies` yet)
    → honest abstain before launching a browser."""
    if not profile_dir:
        return False
    return (Path(profile_dir) / "Default" / "Cookies").is_file()


def _on_login_page(url: str) -> bool:
    return any(h in (url or "") for h in _LOGIN_HOSTS)


def _answer_ready(page) -> tuple[bool, int]:
    """Deterministic readiness probe. Returns (sources_present, answer_len)."""
    n_articles = page.eval_on_selector_all("article", "els => els.length")
    # A 'Sources (N)' button appears once references are attached.
    sources_btn = page.eval_on_selector_all(
        "button",
        "els => els.filter(b => /sources\\s*\\(\\d+\\)/i.test((b.textContent||''))).length",
    )
    answer_len = page.eval_on_selector_all(
        "article",
        "els => els.map(e => (e.innerText||'').length).reduce((a,b)=>a+b,0)",
    )
    return (n_articles > 0 and sources_btn > 0), int(answer_len or 0)


def capture_emet(query: str, candidate: str, *, cdp: str | None = None,
                 profile: str | None = None, headless: bool = True,
                 timeout_s: int = 300, save_html: str | None = None) -> dict:
    """Drive EMET deterministically and scrape the rendered answer into an EMET envelope.

    Connection: ``cdp`` (or ``$SAPPHIRE_EMET_CDP``) via ``connect_over_cdp`` is preferred;
    otherwise ``launch_persistent_context(profile or $SAPPHIRE_EMET_PROFILE)`` (the profile
    is auto-login-authenticated by ``_build/emet_login.py``).

    Returns the §7 envelope, or ``{"login_required": True}`` on a login screen / no usable
    answer within ``timeout_s`` (honest abstain — never fabricated).
    """
    # Resolve session source BEFORE importing Playwright — the profile check is pure stdlib
    # and must short-circuit (honest abstain) even when playwright is not installed.
    cdp = cdp or os.environ.get("SAPPHIRE_EMET_CDP") or None
    profile = profile or os.environ.get("SAPPHIRE_EMET_PROFILE") or str(BENCHSCI_PROFILE)
    if not cdp and not _profile_has_session(profile):
        return {
            "login_required": True,
            "reason": (
                "BenchSci session not found — run the one-time login: "
                "python -m emet.login"
            ),
        }

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:                              # pragma: no cover - env-specific
        raise RuntimeError(
            "playwright not installed — run via the .emet-venv "
            "(.emet-venv/bin/python -m emet.capture ...)") from exc

    with sync_playwright() as p:
        ctx = None
        browser = None
        owns_ctx = False
        if cdp:
            browser = p.chromium.connect_over_cdp(cdp)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        else:
            ctx = p.chromium.launch_persistent_context(profile, headless=headless)
            owns_ctx = True
        try:
            return _drive(ctx, query, candidate, timeout_s=timeout_s, save_html=save_html)
        finally:
            try:
                if owns_ctx:
                    ctx.close()
                elif browser is not None:
                    browser.close()
            except Exception:
                pass


def _click_send(page, arrow_locator) -> None:
    """Click the EMET send control. The arrow renders as a clickable <div> (not a <button>),
    so click the icon's nearest clickable ancestor; fall back to clicking the icon itself."""
    handle = arrow_locator.element_handle()
    if handle is not None:
        clickable = handle.evaluate_handle(
            "el => el.closest('button, [role=button], .cursor-pointer') || el.parentElement")
        as_el = clickable.as_element()
        if as_el is not None:
            as_el.click()
            return
    arrow_locator.click(force=True)


def _drive(ctx, query: str, candidate: str, *, timeout_s: int, save_html: str | None) -> dict:
    page = ctx.new_page()
    try:
        page.goto(EMET_URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2500)
        if _on_login_page(page.url):
            return {"login_required": True}

        # Type into the TipTap editor and submit via the up-arrow (Enter does NOT submit).
        # Click the editable WRAPPER (`.tiptap`), not the inner `<p>` — clicking the inner
        # placeholder paragraph doesn't reliably focus the contenteditable, so the text never
        # commits and the (reactive) send button never renders. Verified live 2026-06-25.
        editor = page.locator(".tiptap").first
        editor.wait_for(state="visible", timeout=30000)
        editor.click()
        page.keyboard.type(query, delay=10)
        page.wait_for_timeout(600)
        # The up-arrow send control only appears once the editor holds content (reactive). NOTE:
        # it renders as a clickable <div> (rounded-full bg-primary), NOT a <button>, so target the
        # `.lucide-arrow-up` icon and click its clickable ancestor. Verified live 2026-06-25.
        arrow = page.locator(".lucide-arrow-up").first
        arrow.wait_for(state="visible", timeout=20000)
        _click_send(page, arrow)

        # Capture the /chat/<uuid> URL once it appears.
        chat_url = ""
        try:
            page.wait_for_url(re.compile(r"/chat/[0-9a-fA-F-]+"), timeout=30000)
            chat_url = page.url
        except Exception:
            chat_url = page.url

        # Deterministic wait: article present AND a 'Sources (N)' button AND text length
        # stable across ~3s. Bounded by timeout_s.
        import time
        deadline = time.time() + max(10, timeout_s)
        stable_since = None
        last_len = -1
        while time.time() < deadline:
            if _on_login_page(page.url):
                return {"login_required": True}
            ready, length = _answer_ready(page)
            if ready and length > 0:
                if length == last_len:
                    if stable_since is None:
                        stable_since = time.time()
                    elif time.time() - stable_since >= 3.0:
                        break        # stable for ~3s -> done
                else:
                    stable_since = None
                    last_len = length
            page.wait_for_timeout(1500)

        # Open the Sources panel if a 'Sources (N)' button is present (so the panel renders
        # into the DOM we scrape). Best-effort; the parser also reads inline citations.
        try:
            src_btn = page.locator("button", has_text=re.compile(r"sources\s*\(\d+\)", re.I)).first
            if src_btn.count() > 0:
                src_btn.click(timeout=4000)
                page.wait_for_timeout(1500)
        except Exception:
            pass

        html = page.content()
        if save_html:
            Path(save_html).parent.mkdir(parents=True, exist_ok=True)
            Path(save_html).write_text(html, encoding="utf-8")

        env = parse_emet_html(html, candidate=candidate, query=query, chat_url=chat_url)
        # If the page never produced an answer article, abstain rather than emit an empty shell.
        if env.get("login_required"):
            return env
        if not env.get("evidence") and "<article" not in html.lower():
            return {"login_required": True, "reason": "no answer rendered within timeout"}
        return env
    finally:
        try:
            page.close()
        except Exception:
            pass


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def _write_envelope(candidate: str, env: dict) -> Path:
    ENVELOPES_DIR.mkdir(parents=True, exist_ok=True)
    out = ENVELOPES_DIR / f"{candidate}.json"
    out.write_text(json.dumps(env, indent=2) + "\n", encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m emet.capture",
        description="Deterministic EMET DOM-scrape capture -> scenarios/emet_envelopes/<candidate>.json")
    ap.add_argument("--candidate", required=True, help="public identifier (gene/protein/SMILES)")
    ap.add_argument("--query", required=True, help="evidence question (public identifiers only)")
    ap.add_argument("--cdp", default=None, help="CDP endpoint (else $SAPPHIRE_EMET_CDP)")
    ap.add_argument("--profile", default=None, help="persistent profile dir (else $SAPPHIRE_EMET_PROFILE)")
    ap.add_argument("--headed", action="store_true", help="run headed (default headless)")
    ap.add_argument("--timeout", type=int, default=300, help="max seconds to wait for the answer")
    ap.add_argument("--save-html", default=None, help="also save the rendered answer HTML to this path")
    args = ap.parse_args(argv)

    env = capture_emet(args.query, args.candidate, cdp=args.cdp, profile=args.profile,
                       headless=not args.headed, timeout_s=args.timeout, save_html=args.save_html)

    if env.get("login_required"):
        reason = env.get("reason", "BenchSci login screen — run: python -m emet.login")
        print(f"ABSTAIN: {reason}. No envelope written (never fabricates).", file=sys.stderr)
        return 2

    n = len(env.get("evidence") or [])
    if n == 0:
        print("ABSTAIN: no citable PMIDs/DOIs scraped — writing flag envelope (no fabrication).",
              file=sys.stderr)
    out = _write_envelope(args.candidate, env)
    ids = [e["id_or_url"] for e in env.get("evidence", [])]
    print(f"Wrote {out}")
    print(f"  workflow={env['emet_workflow']} verdict={env['verdict']} evidence={n}")
    print(f"  chat_url={env['chat_url']}")
    if ids:
        print(f"  ids={', '.join(ids[:12])}{' …' if len(ids) > 12 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
