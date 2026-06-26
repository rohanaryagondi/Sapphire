/* orchestrator_ui/static/app.js
   Vanilla JS — consumes the SSE stream from POST /api/run and renders:
   - LEFT panel: live tool calls + reasoning (streaming)
   - CENTER: ranked genes table + synthesis (on result)
   - RIGHT panel: plan steps + gene summary (on result)
*/

(function () {
  'use strict';

  // ── DOM refs ───────────────────────────────────────────────────────────────
  const chatInput   = document.getElementById('chatInput');
  const sendBtn     = document.getElementById('sendBtn');
  const chatCol     = document.getElementById('chatCol');
  const emptyState  = document.getElementById('emptyState');
  const resultsArea = document.getElementById('resultsArea');
  const traceList   = document.getElementById('traceList');
  const traceStatus = document.getElementById('traceStatus');
  const liveLabel   = document.getElementById('liveLabel');
  const liveBadge   = document.getElementById('liveBadge');
  const planSteps   = document.getElementById('planSteps');
  const rankedGenes = document.getElementById('rankedGenes');
  const synthesis   = document.getElementById('synthesis');
  const rightStatus = document.getElementById('rightStatus');
  const rightHint   = document.getElementById('rightHint');
  const rightPlan   = document.getElementById('rightPlan');
  const rightGeneList = document.getElementById('rightGeneList');
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
    rightHint.style.display = 'block';
    rightPlan.innerHTML = '';
    rightGeneList.innerHTML = '';
    rankedGenes.innerHTML = '';
    synthesis.innerHTML = '';

    // Clear the input IMMEDIATELY (so it's obvious the query was sent) and show a WORKING state in
    // the center — the orchestrator is a real claude -p agent that takes a few minutes, so without
    // this the centre looks dead even though the live trace is streaming on the left.
    chatInput.value = '';
    chatInput.style.height = '';
    resultsArea.style.display = 'block';
    planSteps.innerHTML =
      '<div class="run-query">' + escHtml(query) + '</div>' +
      '<div class="run-working"><span class="rw-dots"><span></span><span></span><span></span></span>' +
      '<span class="rw-text">Orchestrator working — deciding tool calls, gathering Quiver moat + EMET evidence, ' +
      'then reasoning as the scientific team. This takes a few minutes; the live trace is streaming on the left →</span></div>';

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
    // Remove "Running orchestrator…" hint on first real event
    const hint = traceList.querySelector('.hint');
    if (hint) hint.remove();

    if (data.type === 'tool_call') {
      const el = document.createElement('div');
      el.className = 'trace-top';
      const label = data.label || ('→ ' + data.tool);
      let inputPreview = '';
      if (data.input && data.input.command) {
        inputPreview = data.input.command;
      }
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

    } else if (data.type === 'tool_result') {
      const el = document.createElement('div');
      el.className = 'trace-top';
      el.innerHTML =
        '<span class="tt-status" style="color:#2ea043">✓</span>' +
        '<div class="tt-body">' +
          (data.label ? '<div class="tt-name" style="color:var(--ink-3);font-size:10px">' + escHtml(data.label) + '</div>' : '') +
          '<div class="tt-detail" style="color:var(--ink-2);white-space:pre-wrap;margin-top:2px">' + escHtml((data.summary || '').slice(0, 400)) + '</div>' +
        '</div>';
      traceList.appendChild(el);
      traceList.scrollTop = traceList.scrollHeight;

    } else if (data.type === 'text') {
      const text = (data.text || '').trim();
      if (!text) return;
      const el = document.createElement('div');
      el.className = 'trace-top';
      el.innerHTML =
        '<span class="tt-status" style="color:var(--ink-3)">›</span>' +
        '<div class="tt-body">' +
          '<div class="tt-detail" style="color:var(--ink-2);white-space:pre-wrap">' + escHtml(text.slice(0, 800)) + '</div>' +
        '</div>';
      traceList.appendChild(el);
      traceList.scrollTop = traceList.scrollHeight;
    }
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

    // --- RIGHT PANEL: plan + gene summary ---
    rightHint.style.display = 'none';

    if (steps.length) {
      let html = '<div style="padding:12px 16px 0">';
      html += '<div class="src-section" style="padding:0 0 7px">Plan</div>';
      html += '<ol style="margin:0;padding-left:20px;font-size:12px;color:var(--ink-2);line-height:1.7">';
      steps.forEach(function (s) {
        html += '<li style="margin:3px 0">' + escHtml(String(s)) + '</li>';
      });
      html += '</ol></div>';
      rightPlan.innerHTML = html;
    }

    if (genes.length) {
      let html = '<div style="padding:12px 16px 0">';
      html += '<div class="src-section" style="padding:0 0 7px">Genes (' + genes.length + ')</div>';
      genes.forEach(function (g) {
        const confClass = g.confidence === 'high' ? 'conf-high'
          : g.confidence === 'medium' ? 'conf-medium' : 'conf-low';
        html += '<div class="src-row">';
        html += '<div class="src-meta" style="margin-bottom:4px">';
        html += '<span class="rg-rank" style="font-family:var(--mono);font-size:11px;color:var(--ink-3)">#' + escHtml(String(g.rank || '')) + '</span> ';
        html += '<span class="rg-gene" style="font-family:var(--mono);font-weight:600;color:var(--purple)">' + escHtml(String(g.gene || '')) + '</span>';
        html += ' <span class="conf ' + confClass + '">' + escHtml(String(g.confidence || '')) + '</span>';
        html += '</div>';
        if (g.mechanism) {
          html += '<div class="src-text" style="font-size:11px">' + escHtml(String(g.mechanism)) + '</div>';
        }
        html += '</div>';
      });
      html += '</div>';
      rightGeneList.innerHTML = html;
    }
  }

  // ── Status helpers ────────────────────────────────────────────────────────
  function setStatus(s) {
    if (s === 'running') {
      traceStatus.textContent = 'running';
      liveLabel.textContent = 'Running';
      liveBadge.className = 'live-badge';
      rightStatus.textContent = 'running';
    } else if (s === 'done') {
      traceStatus.textContent = 'done';
      liveLabel.textContent = 'Done';
      liveBadge.className = 'live-badge';
      rightStatus.textContent = 'done';
    } else if (s === 'error') {
      traceStatus.textContent = 'error';
      liveLabel.textContent = 'Error';
      liveBadge.className = 'live-badge';
      rightStatus.textContent = 'error';
    } else {
      traceStatus.textContent = 'idle';
      liveLabel.textContent = 'Ready';
      liveBadge.className = 'live-badge';
      rightStatus.textContent = 'idle';
    }
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
