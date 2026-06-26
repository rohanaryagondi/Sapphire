/* orchestrator_ui/static/app.js
   Vanilla JS — consumes the SSE stream from POST /api/run and renders:
   - LEFT panel: agent/tool outputs — each tool_result (streaming)
   - CENTER: plan + ranked genes table + synthesis (on result)
   - RIGHT panel: live trace — tool calls + step-by-step reasoning (streaming)
*/

(function () {
  'use strict';

  // ── DOM refs ───────────────────────────────────────────────────────────────
  const chatInput   = document.getElementById('chatInput');
  const sendBtn     = document.getElementById('sendBtn');
  const chatCol     = document.getElementById('chatCol');
  const emptyState  = document.getElementById('emptyState');
  const resultsArea = document.getElementById('resultsArea');
  const traceList   = document.getElementById('traceList');     // RIGHT pane — the live trace
  const traceStatus = document.getElementById('traceStatus');
  const outputsList   = document.getElementById('outputsList'); // LEFT pane — agent/tool outputs
  const outputsStatus = document.getElementById('outputsStatus');
  const liveLabel   = document.getElementById('liveLabel');
  const liveBadge   = document.getElementById('liveBadge');
  const queryEcho   = document.getElementById('queryEcho');
  const planSteps   = document.getElementById('planSteps');
  const rankedGenes = document.getElementById('rankedGenes');
  const synthesis   = document.getElementById('synthesis');
  const suggestions = document.getElementById('suggestions');

  // ── Panel toggle buttons ───────────────────────────────────────────────────
  document.getElementById('leftToggle').addEventListener('click', function () {
    const panel = document.getElementById('leftPanel');
    panel.classList.toggle('open');
  });
  document.getElementById('rightToggle').addEventListener('click', function () {
    const panel = document.getElementById('rightPanel');
    panel.classList.toggle('open');
  });

  // ── Suggestion chips ───────────────────────────────────────────────────────
  suggestions.addEventListener('click', function (e) {
    const btn = e.target.closest('.sug');
    if (!btn) return;
    chatInput.value = btn.dataset.q || '';
    autoResize();
    sendBtn.click();
  });

  // ── Textarea auto-resize ───────────────────────────────────────────────────
  function autoResize() {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + 'px';
  }
  chatInput.addEventListener('input', autoResize);
  chatInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendBtn.click();
    }
  });

  // ── State ─────────────────────────────────────────────────────────────────
  let running = false;

  // ── Submit handler ────────────────────────────────────────────────────────
  sendBtn.addEventListener('click', function () {
    const query = chatInput.value.trim();
    if (!query || running) return;
    startRun(query);
  });

  // ── Start a run ───────────────────────────────────────────────────────────
  function startRun(query) {
    running = true;
    sendBtn.disabled = true;

    // Reset UI
    emptyState.style.display = 'none';
    resultsArea.style.display = 'none';
    chatCol.classList.add('active');
    traceList.innerHTML = '<div class="hint">Running orchestrator…</div>';
    outputsList.innerHTML = '<div class="hint">Agent &amp; tool outputs will appear here…</div>';
    rankedGenes.innerHTML = '';
    synthesis.innerHTML = '';

    // Clear the input IMMEDIATELY (so it's obvious the query was sent) and show a WORKING state in
    // the center — the orchestrator is a real claude -p agent that takes a few minutes, so without
    // this the centre looks dead even though the live trace is streaming on the left.
    chatInput.value = '';
    chatInput.style.height = '';
    resultsArea.style.display = 'block';
    // The question persists in its own element (renderResult never overwrites it).
    queryEcho.innerHTML = '<div class="run-query">' +
      '<span style="display:block;font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--purple);font-weight:600;margin-bottom:5px">Question</span>' +
      escHtml(query) + '</div>';
    // The working banner lives in planSteps — renderResult replaces it with the plan on completion.
    planSteps.innerHTML =
      '<div class="run-working"><span class="rw-dots"><span></span><span></span><span></span></span>' +
      '<span class="rw-text">Orchestrator working — deciding tool calls, gathering Quiver moat + EMET evidence, ' +
      'then reasoning as the scientific team. This takes a few minutes; the live trace is streaming on the right →</span></div>';

    // Status
    setStatus('running');

    // POST query
    fetch('/api/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    }).then(function (resp) {
      if (!resp.ok || !resp.body) {
        appendTrace({ type: 'text', text: 'HTTP error: ' + resp.status });
        setStatus('error');
        done();
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      function read() {
        reader.read().then(function ({ done: streamDone, value }) {
          if (streamDone) {
            done();
            return;
          }
          buf += decoder.decode(value, { stream: true });
          const parts = buf.split('\n\n');
          buf = parts.pop(); // last part may be incomplete
          parts.forEach(parseSSE);
          read();
        }).catch(function (err) {
          appendTrace({ type: 'text', text: 'Stream error: ' + err });
          done();
        });
      }
      read();
    }).catch(function (err) {
      appendTrace({ type: 'text', text: 'Fetch error: ' + err });
      setStatus('error');
      done();
    });
  }

  // ── Parse one SSE chunk ───────────────────────────────────────────────────
  function parseSSE(chunk) {
    const lines = chunk.split('\n');
    let event = '';
    let dataLines = [];
    lines.forEach(function (line) {
      if (line.startsWith('event: ')) event = line.slice(7).trim();
      else if (line.startsWith('data: ')) dataLines.push(line.slice(6));
    });
    if (!event || dataLines.length === 0) return;
    const raw = dataLines.join('\n');
    let data;
    try { data = JSON.parse(raw); } catch (e) { return; }

    if (event === 'trace') {
      appendTrace(data);
    } else if (event === 'result') {
      renderResult(data);
    } else if (event === 'error') {
      appendTrace({ type: 'text', text: '⚠ Error: ' + (data.error || JSON.stringify(data)) });
      setStatus('error');
    } else if (event === 'done') {
      setStatus('done');
      done();
    }
  }

  // ── Append a trace item to the LEFT panel ────────────────────────────────
  function appendTrace(data) {
    if (data.type === 'tool_call') {
      // RIGHT pane (trace) — what the orchestrator is about to do
      removeHint(traceList);
      const el = document.createElement('div');
      el.className = 'trace-top';
      const label = data.label || ('→ ' + data.tool);
      const inputPreview = (data.input && data.input.command) ? data.input.command : '';
      el.innerHTML =
        '<span class="tt-status">⚡</span>' +
        '<div class="tt-body">' +
          '<div class="tt-name" style="color:var(--purple)">' + escHtml(label) + '</div>' +
          (inputPreview
            ? '<div class="tt-detail" style="font-family:var(--mono);font-size:10px;word-break:break-all;margin-top:3px">' + escHtml(inputPreview.slice(0, 200)) + '</div>'
            : '') +
        '</div>';
      traceList.appendChild(el);
      traceList.scrollTop = traceList.scrollHeight;

    } else if (data.type === 'text') {
      // RIGHT pane (trace) — the orchestrator's reasoning / thinking
      const text = (data.text || '').trim();
      if (!text) return;
      removeHint(traceList);
      const el = document.createElement('div');
      el.className = 'trace-top';
      el.innerHTML =
        '<span class="tt-status" style="color:var(--ink-3)">›</span>' +
        '<div class="tt-body">' +
          '<div class="tt-detail" style="color:var(--ink-2);white-space:pre-wrap">' + escHtml(text.slice(0, 800)) + '</div>' +
        '</div>';
      traceList.appendChild(el);
      traceList.scrollTop = traceList.scrollHeight;

    } else if (data.type === 'tool_result') {
      // LEFT pane (outputs) — the specific output this agent/tool returned
      removeHint(outputsList);
      const el = document.createElement('div');
      el.className = 'trace-top';
      el.innerHTML =
        '<span class="tt-status" style="color:#2ea043">✓</span>' +
        '<div class="tt-body">' +
          (data.label ? '<div class="tt-name" style="color:var(--purple)">' + escHtml(data.label) + '</div>' : '') +
          '<div class="tt-detail" style="color:var(--ink-2);white-space:pre-wrap;margin-top:3px">' + escHtml((data.summary || '').slice(0, 600)) + '</div>' +
        '</div>';
      outputsList.appendChild(el);
      outputsList.scrollTop = outputsList.scrollHeight;
    }
  }

  function removeHint(panel) {
    const h = panel.querySelector('.hint');
    if (h) h.remove();
  }

  // ── Render the final result in CENTER and RIGHT ───────────────────────────
  function renderResult(data) {
    resultsArea.style.display = 'block';

    // --- PLAN STEPS (center) ---
    const steps = data.plan_steps || [];
    if (steps.length) {
      let html = '<div class="plan-steps"><div class="ps-lbl">To answer this, I will:</div><ol class="ps-list">';
      steps.forEach(function (s) {
        html += '<li>' + escHtml(String(s)) + '</li>';
      });
      html += '</ol></div>';
      planSteps.innerHTML = html;
    }

    // --- RANKED GENES TABLE (center) ---
    const genes = data.ranked_genes || [];
    if (genes.length) {
      let html = '<div class="ranked-genes">';
      html += '<div class="rg-lbl">Ranked Rescue Genes <span class="rg-sub">Quiver moat · EMET PMIDs · LLM reasoning</span></div>';
      html += '<table class="rg-table"><thead><tr>';
      html += '<th>#</th><th>Gene</th><th>Moat Rank</th><th>Mechanism</th><th>Citations</th><th>Conf</th>';
      html += '</tr></thead><tbody>';
      genes.forEach(function (g) {
        const confClass = g.confidence === 'high' ? 'conf-high'
          : g.confidence === 'medium' ? 'conf-medium' : 'conf-low';
        const cites = (g.citations || []).map(function (c) {
          return '<span class="rg-cite">' + escHtml(String(c)) + '</span>';
        }).join('');
        const moatRank = g.moat_rank != null ? String(g.moat_rank) : '–';
        html += '<tr class="rg-row">';
        html += '<td class="rg-rank">' + escHtml(String(g.rank || '')) + '</td>';
        html += '<td class="rg-gene">' + escHtml(String(g.gene || '')) + '</td>';
        html += '<td class="rg-moat">' + escHtml(moatRank) + '</td>';
        html += '<td class="rg-mech">' + escHtml(String(g.mechanism || ''))
          + (cites ? '<div class="rg-cites">' + cites + '</div>' : '') + '</td>';
        html += '<td></td>';
        html += '<td class="rg-conf"><span class="conf ' + confClass + '">' + escHtml(String(g.confidence || '')) + '</span></td>';
        html += '</tr>';
      });
      html += '</tbody></table></div>';
      rankedGenes.innerHTML = html;
    }

    // --- SYNTHESIS callout (center) ---
    if (data.synthesis) {
      const confClass = data.confidence === 'high' ? 'conf-high'
        : data.confidence === 'medium' ? 'conf-medium' : 'conf-low';
      synthesis.innerHTML =
        '<div class="synthesis">' +
          '<div class="synthesis-lbl">Synthesis</div>' +
          '<div class="synthesis-rec">' + escHtml(String(data.synthesis)) + '</div>' +
          (data.confidence
            ? '<div class="synthesis-conf">Confidence: <b>' + escHtml(String(data.confidence)) + '</b></div>'
            : '') +
        '</div>';
    }

    // (Plan + ranked genes render in the CENTER; the RIGHT pane is the live trace, the LEFT pane the
    //  per-agent/tool outputs — both stream during the run.)
  }

  // ── Status helpers ────────────────────────────────────────────────────────
  function setStatus(s) {
    const label = (s === 'running') ? 'running'
      : (s === 'done') ? 'done'
      : (s === 'error') ? 'error' : 'idle';
    traceStatus.textContent = label;
    if (outputsStatus) outputsStatus.textContent = label;
    liveLabel.textContent = (s === 'running') ? 'Running'
      : (s === 'done') ? 'Done'
      : (s === 'error') ? 'Error' : 'Ready';
    liveBadge.className = 'live-badge';
  }

  function done() {
    running = false;
    sendBtn.disabled = false;
    chatInput.value = '';
    chatInput.style.height = '';
  }

  // ── XSS helper ───────────────────────────────────────────────────────────
  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

})();
