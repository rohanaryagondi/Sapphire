# -*- coding: utf-8 -*-
"""Convert the 59 persona DOCX files to clean markdown, foldered by archetype."""
import os, re, sys
import docx

SRC = r"C:\Users\rohan.gondi\Desktop\Sapphire\extracted\Sapphire Prompt Work_Feb 2026"
OUT = r"C:\Users\rohan.gondi\Desktop\Sapphire\sapphire-capability-map\personas"

# zip folder -> output subfolder + human label
ARCHETYPES = {
    "Biotech Personas":   ("biotech-cso", "Biotech CSO"),
    "Pharma Personas":    ("pharma-svp", "Pharma SVP (R&D)"),
    "Pharma BD Personas": ("pharma-bd", "Pharma BD SVP"),
    "EC Venture Personas":("venture-ec", "Venture GP (East Coast)"),
    "WC Venture Personas":("venture-wc", "Venture GP (West Coast)"),
}

# fix mojibake / non-ascii artifacts seen in the source docs
REPL = {
    "’":"'", "‘":"'", "“":'"', "”":'"',
    "–":"-", "—":"—", "…":"...", "→":"->",
    "�":"", " ":" ", "•":"-",
}
def clean(t, strip=True):
    for a,b in REPL.items():
        t = t.replace(a,b)
    return t.strip() if strip else t

def runs_md(p):
    out = []
    for r in p.runs:
        txt = clean(r.text, strip=False)
        if not txt:
            continue
        if r.bold and txt.strip():
            # keep surrounding whitespace outside the bold markers
            lead = txt[:len(txt)-len(txt.lstrip())]
            trail = txt[len(txt.rstrip()):]
            txt = f"{lead}**{txt.strip()}**{trail}"
        out.append(txt)
    s = "".join(out) if out else clean(p.text)
    return re.sub(r"\*\*\s*\*\*", "", s).strip()

def para_to_md(p):
    style = ((p.style.name if p.style else "") or "").lower()
    txt = runs_md(p)
    if not txt:
        return ""
    if style.startswith("heading 1") or style == "title":
        return f"# {txt}"
    if style.startswith("heading 2"):
        return f"## {txt}"
    if style.startswith("heading 3"):
        return f"### {txt}"
    if "list" in style or p._p.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr') is not None:
        return f"- {txt}"
    # numbered section headers like "1. Core Identity" -> keep as bold-ish heading
    if re.match(r"^\d+\.\s+[A-Z]", txt) and len(txt) < 80:
        return f"## {txt}"
    return txt

def convert(path):
    d = docx.Document(path)
    lines, prev_blank = [], True
    for p in d.paragraphs:
        md = para_to_md(p)
        if md == "":
            if not prev_blank:
                lines.append("")
                prev_blank = True
            continue
        lines.append(md)
        prev_blank = False
    return "\n".join(lines).strip() + "\n"

def slug(name):
    name = name.replace("_for Feb 2026 Sapphire Prompts", "")
    name = re.sub(r"\.docx$", "", name)
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

index = []
for folder,(sub,label) in ARCHETYPES.items():
    srcdir = os.path.join(SRC, folder)
    outdir = os.path.join(OUT, sub)
    os.makedirs(outdir, exist_ok=True)
    files = sorted(f for f in os.listdir(srcdir) if f.endswith(".docx") and not f.startswith("~"))
    for f in files:
        md = convert(os.path.join(srcdir, f))
        base = slug(f)
        with open(os.path.join(outdir, base+".md"), "w", encoding="utf-8") as fh:
            fh.write(md)
        # first non-empty line = persona name/title
        first = next((l for l in md.splitlines() if l.strip()), base)
        title = re.sub(r"^#+\s*", "", first)
        index.append((label, sub, base, title))
        print(f"{label:24s} {base}")

# INDEX.md
index.sort()
with open(os.path.join(OUT, "INDEX.md"), "w", encoding="utf-8") as fh:
    fh.write("# Persona Index\n\n")
    fh.write(f"{len(index)} personas, foldered by archetype. Each is a faithful markdown conversion of the Feb-2026 Sapphire persona DOCX, usable as an agent system-persona or as the source that justifies/regenerates capability-map prompts.\n\n")
    cur = None
    for label, sub, base, title in index:
        if label != cur:
            fh.write(f"\n## {label}\n\n"); cur = label
        fh.write(f"- [{title}]({sub}/{base}.md)\n")
print(f"\nTOTAL: {len(index)} personas")
