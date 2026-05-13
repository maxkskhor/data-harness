"""Generate a self-contained HTML dashboard from smoke_results/latest.json.

Called automatically by conftest.pytest_sessionfinish after every live test
run. Can also be invoked directly:

    python tests/_smoke_dashboard.py smoke_results/latest.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def build_html(data: dict) -> str:
    data_json = json.dumps(data, separators=(",", ":"))
    return _TEMPLATE.replace("__SMOKE_DATA__", data_json)


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>dataact smoke dashboard</title>
<style>
:root{
  --ivory:#FAF9F5;--oat:#E3DACC;--slate:#141413;--clay:#D97757;
  --gray-5:#3D3D3A;--gray-3:#888885;--gray-1:#E8E5DF;
  --olive:#788C5D;--amber:#C78E3F;--danger:#B04A4A;--info:#5C7CA3;
  --sp-1:4px;--sp-2:8px;--sp-3:12px;--sp-4:16px;--sp-5:24px;--sp-6:32px;--sp-7:48px;
  --r-xs:4px;--r-sm:8px;--r-md:12px;--r-lg:20px;
  --shadow-sm:0 1px 2px rgba(20,20,19,.06);--shadow-md:0 4px 12px rgba(20,20,19,.08);
  --font:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
  --mono:"SF Mono","JetBrains Mono","Fira Code",ui-monospace,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--ivory);color:var(--slate);font-family:var(--font);font-size:16px;line-height:1.55}
.page{max-width:1060px;margin:0 auto;padding:var(--sp-7) var(--sp-6)}
.page-header{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:var(--sp-6);gap:var(--sp-5);flex-wrap:wrap}
.page-title{font-size:28px;font-weight:500;line-height:1.2}
.page-sub{font-size:13px;color:var(--gray-3);margin-top:4px;font-family:var(--mono)}
.export-row{display:flex;gap:var(--sp-2);align-items:center;flex-shrink:0;margin-top:4px}
.exp-btn{padding:6px 14px;border:1px solid var(--gray-1);background:white;color:var(--gray-5);border-radius:var(--r-sm);font-size:13px;font-family:var(--font);cursor:pointer;transition:border-color .15s,color .15s}
.exp-btn:hover{border-color:var(--clay);color:var(--clay)}
.exp-btn.copied{background:var(--clay);color:white;border-color:var(--clay)}
.tabs{display:flex;border-bottom:2px solid var(--gray-1);margin-bottom:var(--sp-6)}
.tab-btn{padding:var(--sp-3) var(--sp-5);font-size:14px;font-weight:500;border:none;background:none;color:var(--gray-3);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;transition:color .15s,border-color .15s;font-family:var(--font)}
.tab-btn.active{color:var(--clay);border-bottom-color:var(--clay)}
.tab-btn:hover:not(.active){color:var(--gray-5)}
.tab-panel{display:none}.tab-panel.active{display:block}
.summary-bar{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--sp-4);margin-bottom:var(--sp-6)}
.sum-tile{background:white;border:1px solid var(--gray-1);border-radius:var(--r-md);padding:var(--sp-4) var(--sp-5)}
.sum-tile .slabel{font-size:11px;font-weight:500;color:var(--gray-3);text-transform:uppercase;letter-spacing:.04em;font-family:var(--mono)}
.sum-tile .sval{font-size:26px;font-weight:500;margin-top:4px}
.sum-tile .ssub{font-size:12px;color:var(--gray-3);margin-top:2px}
.green .sval{color:var(--olive)}.clay .sval{color:var(--clay)}
.test-grid{display:flex;flex-direction:column;gap:var(--sp-3)}
.test-card{border:1px solid var(--gray-1);border-radius:var(--r-md);background:white;overflow:hidden}
.test-card.multi{border-left:3px solid var(--clay)}
.card-hdr{display:flex;align-items:center;gap:var(--sp-4);padding:var(--sp-4) var(--sp-5);cursor:pointer;user-select:none}
.card-hdr:hover{background:var(--ivory)}
.badge{display:inline-flex;align-items:center;font-size:11px;font-weight:500;padding:2px 8px;border-radius:var(--r-lg);font-family:var(--mono);white-space:nowrap;flex-shrink:0}
.pass{background:rgba(120,140,93,.12);color:var(--olive)}.fail{background:rgba(176,74,74,.12);color:var(--danger)}
.tname{font-size:14px;font-weight:500;flex:1;font-family:var(--mono)}
.chips{display:flex;gap:var(--sp-2);flex-wrap:wrap;margin-left:auto;align-items:center}
.chip{display:inline-flex;align-items:center;gap:4px;font-size:12px;color:var(--gray-5);background:var(--ivory);border:1px solid var(--gray-1);border-radius:var(--r-sm);padding:2px 8px;font-family:var(--mono);white-space:nowrap}
.chip.warn{border-color:rgba(199,142,63,.3);color:var(--amber);background:rgba(199,142,63,.06)}
.arrow{font-size:11px;color:var(--gray-3);flex-shrink:0;width:16px;text-align:center;transition:transform .2s}
.test-card.open .arrow{transform:rotate(90deg)}
.card-body{display:none;border-top:1px solid var(--gray-1);background:var(--ivory);padding:var(--sp-5)}
.test-card.open .card-body{display:block}
.dcols{display:grid;grid-template-columns:repeat(3,1fr);gap:var(--sp-4);margin-bottom:var(--sp-5)}
.dstat .dl{font-size:11px;color:var(--gray-3);font-family:var(--mono);text-transform:uppercase;letter-spacing:.04em}
.dstat .dv{font-size:22px;font-weight:500;margin-top:2px}
.dstat .ds{font-size:11px;color:var(--gray-3)}
.dv.clay{color:var(--clay)}
.sec{margin-top:var(--sp-5)}
.sec-label{font-size:11px;font-weight:500;color:var(--gray-3);text-transform:uppercase;letter-spacing:.04em;font-family:var(--mono);margin-bottom:var(--sp-2)}
.tool-tags{display:flex;flex-wrap:wrap;gap:var(--sp-1)}
.ttag{font-size:11px;font-family:var(--mono);padding:2px 7px;background:rgba(92,124,163,.08);color:var(--info);border-radius:var(--r-xs);border:1px solid rgba(92,124,163,.18)}
.sys-prompt{font-size:12px;font-family:var(--mono);background:rgba(20,20,19,.04);border-radius:var(--r-sm);padding:var(--sp-3);white-space:pre-wrap;word-break:break-word;color:var(--gray-5);max-height:120px;overflow-y:auto}
/* harness section */
.harness-section{margin-top:var(--sp-5)}
.harness-label{font-size:12px;font-weight:500;font-family:var(--mono);color:var(--clay);margin-bottom:var(--sp-3);display:flex;align-items:center;gap:var(--sp-2)}
.harness-stats{display:flex;gap:var(--sp-5);flex-wrap:wrap;margin-bottom:var(--sp-3)}
.hstat{font-size:12px;font-family:var(--mono);color:var(--gray-5)}
.hstat span{font-weight:500;color:var(--slate)}
/* conversation */
.conv-wrap{display:flex;flex-direction:column;gap:var(--sp-2);margin-top:var(--sp-2)}
.conv-msg{border-radius:var(--r-sm);overflow:hidden}
.user-msg{background:var(--oat);margin-right:15%}
.assistant-msg{background:white;border:1px solid var(--gray-1);margin-left:15%}
.tool-result-msg{margin-left:15%;border-radius:var(--r-sm);overflow:hidden}
.conv-role{padding:var(--sp-2) var(--sp-3);font-size:10px;font-family:var(--mono);font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--gray-3);display:flex;align-items:center;justify-content:space-between}
.role-user .conv-role{color:var(--gray-5)}
.role-assistant .conv-role{color:var(--info)}
.role-tool .conv-role{color:var(--olive)}
.role-tool-err .conv-role{color:var(--danger)}
.turn-meta{font-size:10px;font-family:var(--mono);font-weight:400;color:var(--gray-3)}
.conv-text{padding:var(--sp-2) var(--sp-3) var(--sp-3);font-size:13px;white-space:pre-wrap;word-break:break-word;line-height:1.5}
.tool-call{border-top:1px solid var(--gray-1);overflow:hidden}
.tool-call-hdr{padding:var(--sp-2) var(--sp-3);background:rgba(92,124,163,.05);display:flex;align-items:center;gap:var(--sp-2);border-bottom:1px solid rgba(92,124,163,.12)}
.tool-badge{font-size:11px;font-family:var(--mono);font-weight:600;color:var(--info)}
.code-block{margin:0;padding:var(--sp-3);background:#F4F3EF;font-family:var(--mono);font-size:11px;line-height:1.55;overflow-x:auto;white-space:pre}
.code-block code{font-family:inherit}
.tool-output{border-top:1px solid var(--gray-1)}
.err-out .code-block{background:rgba(176,74,74,.04)}
/* coverage tab */
.cov-intro{font-size:14px;color:var(--gray-5);margin-bottom:var(--sp-5);max-width:620px}
.cov-table{width:100%;border-collapse:collapse;font-size:14px}
.cov-table th{text-align:left;font-size:11px;font-weight:500;text-transform:uppercase;letter-spacing:.05em;font-family:var(--mono);color:var(--gray-3);padding:var(--sp-2) var(--sp-4) var(--sp-2) 0;border-bottom:1px solid var(--gray-1)}
.cov-table td{padding:var(--sp-3) var(--sp-4) var(--sp-3) 0;border-bottom:1px solid var(--gray-1);vertical-align:top}
.cov-table tr:last-child td{border-bottom:none}
.feat{font-family:var(--mono);font-size:13px}
.spill{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:500;padding:3px 10px;border-radius:var(--r-lg);font-family:var(--mono)}
.sc{background:rgba(120,140,93,.12);color:var(--olive)}
.sp{background:rgba(199,142,63,.12);color:var(--amber)}
.sm{background:rgba(176,74,74,.10);color:var(--danger)}
.cnote{font-size:13px;color:var(--gray-5)}
/* suggestion cards */
.sug-grid{display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-4);margin-top:var(--sp-5)}
.sug-card{background:white;border:1px solid var(--gray-1);border-radius:var(--r-md);padding:var(--sp-5)}
.sug-num{font-size:11px;font-family:var(--mono);color:var(--clay);font-weight:500;margin-bottom:var(--sp-2)}
.sug-title{font-size:14px;font-weight:500;font-family:var(--mono);margin-bottom:var(--sp-2)}
.sug-desc{font-size:13px;color:var(--gray-5);line-height:1.55}
.sug-assert{display:block;font-size:12px;font-family:var(--mono);color:var(--info);background:rgba(92,124,163,.06);border:1px solid rgba(92,124,163,.15);border-radius:var(--r-xs);padding:2px 8px;margin-top:4px}
.footnote{margin-top:var(--sp-6);font-size:12px;color:var(--gray-3);font-family:var(--mono)}
</style>
</head>
<body>
<div class="page">
  <div class="page-header">
    <div>
      <div class="page-title">dataact smoke dashboard</div>
      <div class="page-sub" id="page-sub"></div>
    </div>
    <div class="export-row">
      <button class="exp-btn" onclick="copyAs(this,'md')">Copy as markdown</button>
      <button class="exp-btn" onclick="copyAs(this,'json')">Copy as JSON</button>
    </div>
  </div>
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('results',this)">Results &amp; Cost</button>
    <button class="tab-btn" onclick="switchTab('coverage',this)">PLAN_v5 Coverage</button>
  </div>

  <!-- Results tab -->
  <div id="tab-results" class="tab-panel active">
    <div class="summary-bar" id="summary-bar"></div>
    <div class="test-grid" id="test-grid"></div>
    <div class="footnote" id="footnote"></div>
  </div>

  <!-- Coverage tab (static) -->
  <div id="tab-coverage" class="tab-panel">
    <p class="cov-intro">PLAN_v5 added typed run results, usage tracking, session inspection, tool annotations, and richer JSONL logging. The table below maps each feature to its current smoke-test coverage.</p>
    <table class="cov-table">
      <thead><tr><th style="width:36%">Feature</th><th style="width:18%">Status</th><th>Notes</th></tr></thead>
      <tbody>
        <tr><td class="feat">Harness.run() → str</td><td><span class="spill sc">✓ Covered</span></td><td class="cnote">Used in 5 of 7 tests; JSONL and tokens asserted.</td></tr>
        <tr><td class="feat">ConnectorRegistry progressive disclosure</td><td><span class="spill sc">✓ Covered</span></td><td class="cnote">connector_fred_data and disk_backed_cache both exercise load_connectors.</td></tr>
        <tr><td class="feat">SessionCache disk spill (hot_limit)</td><td><span class="spill sc">✓ Covered</span></td><td class="cnote">disk_backed_cache asserts location="disk" and raw data absent from messages.</td></tr>
        <tr><td class="feat">Planner tool (add / list / update)</td><td><span class="spill sc">✓ Covered</span></td><td class="cnote">explicit_harness asserts planner__add in tool_names and planner._items ≥ 2.</td></tr>
        <tr><td class="feat">Subagent spawning + handle transfer</td><td><span class="spill sc">✓ Covered</span></td><td class="cnote">explicit_harness asserts "subagent" in tool_names; subagents produce own JSONL.</td></tr>
        <tr><td class="feat">JSONL: system_hash stable across turns</td><td><span class="spill sc">✓ Covered</span></td><td class="cnote">Asserted: len({system_hash}) == 1 across all records.</td></tr>
        <tr><td class="feat">Tool errors in JSONL (is_error)</td><td><span class="spill sc">✓ Covered</span></td><td class="cnote">tool_error_reported_logged asserts any(block["is_error"]) in tool_results.</td></tr>
        <tr><td class="feat">Harness.run_result() → RunResult</td><td><span class="spill sm">✗ Missing</span></td><td class="cnote">All smoke tests call harness.run() (returns str). run_result() untested live. → test_run_result_typed_return</td></tr>
        <tr><td class="feat">Agent.run_result() → RunResult</td><td><span class="spill sm">✗ Missing</span></td><td class="cnote">Agent-level typed result never called in smoke tests. → test_run_result_typed_return</td></tr>
        <tr><td class="feat">AgentSession.ask_result() + multi-turn</td><td><span class="spill sm">✗ Missing</span></td><td class="cnote">No smoke test uses Agent.session(). → test_agent_session_multiturn</td></tr>
        <tr><td class="feat">RunResult.usage (token counts)</td><td><span class="spill sm">✗ Missing</span></td><td class="cnote">No assertion on result.usage.input_tokens > 0. → test_run_result_typed_return</td></tr>
        <tr><td class="feat">RunResult.stop_reason</td><td><span class="spill sm">✗ Missing</span></td><td class="cnote">Never asserted live. → test_run_result_typed_return</td></tr>
        <tr><td class="feat">RunResult.run_id / session_id</td><td><span class="spill sm">✗ Missing</span></td><td class="cnote">UUID fields never inspected. → test_run_result_typed_return / test_agent_session_multiturn</td></tr>
        <tr><td class="feat">RunResult.cache_storage (CacheStorageInfo)</td><td><span class="spill sm">✗ Missing</span></td><td class="cnote">result.cache_storage never accessed live. → test_cache_storage_info_live</td></tr>
        <tr><td class="feat">JSONL: visible_tools field</td><td><span class="spill sp">⚠ Partial</span></td><td class="cnote">Written to every record but never asserted. → test_jsonl_new_fields</td></tr>
        <tr><td class="feat">JSONL: tool_error_count field</td><td><span class="spill sp">⚠ Partial</span></td><td class="cnote">Written but only is_error on blocks is checked. → test_jsonl_new_fields</td></tr>
        <tr><td class="feat">JSONL: tool_annotations field</td><td><span class="spill sm">✗ Missing</span></td><td class="cnote">No smoke test uses annotated tools or checks tool_annotations. → test_jsonl_new_fields</td></tr>
        <tr><td class="feat">ToolAnnotations on connector tools</td><td><span class="spill sm">✗ Missing</span></td><td class="cnote">ConnectorBuilder.tool(annotations=…) not exercised live. → test_jsonl_new_fields</td></tr>
        <tr><td class="feat">MAX_TOKENS / STOP_SEQUENCE terminates</td><td><span class="spill sm">✗ Missing</span></td><td class="cnote">Cannot reliably force from real API; covered by unit tests only.</td></tr>
      </tbody>
    </table>
    <div style="display:flex;gap:24px;margin-top:20px;flex-wrap:wrap">
      <div style="display:flex;align-items:center;gap:8px;font-size:13px"><span class="spill sc" style="font-size:12px">✓ Covered</span><span style="color:var(--gray-5)">7 features</span></div>
      <div style="display:flex;align-items:center;gap:8px;font-size:13px"><span class="spill sp" style="font-size:12px">⚠ Partial</span><span style="color:var(--gray-5)">2 features</span></div>
      <div style="display:flex;align-items:center;gap:8px;font-size:13px"><span class="spill sm" style="font-size:12px">✗ Missing</span><span style="color:var(--gray-5)">10 features</span></div>
    </div>
    <div style="margin-top:40px"><h2 style="font-size:20px;font-weight:500;margin-bottom:20px">Suggested smoke tests</h2>
    <div class="sug-grid">
      <div class="sug-card"><div class="sug-num">NEW SMOKE TEST 1</div><div class="sug-title">test_run_result_typed_return</div><div class="sug-desc">Calls agent.run_result() against the real API. Verifies the typed result surface end-to-end.</div><span class="sug-assert">result.status == "success"</span><span class="sug-assert">result.usage.input_tokens > 0</span><span class="sug-assert">result.stop_reason == StopReason.END_TURN</span><span class="sug-assert">result.run_id is not None</span></div>
      <div class="sug-card"><div class="sug-num">NEW SMOKE TEST 2</div><div class="sug-title">test_agent_session_multiturn</div><div class="sug-desc">Uses Agent.session() for two sequential asks. Verifies session state, last_result, and cache persistence.</div><span class="sug-assert">session.turns == r1.turns + r2.turns</span><span class="sug-assert">isinstance(session.last_result, RunResult)</span><span class="sug-assert">cache handle from ask 1 accessible in ask 2</span></div>
      <div class="sug-card"><div class="sug-num">NEW SMOKE TEST 3</div><div class="sug-title">test_jsonl_new_fields</div><div class="sug-desc">Runs a harness with an annotated tool. Asserts visible_tools, tool_error_count, and tool_annotations all present.</div><span class="sug-assert">"visible_tools" in every JSONL record</span><span class="sug-assert">"tool_error_count" in every JSONL record</span><span class="sug-assert">tool_annotations["get_pi"]["read_only"] == True</span></div>
      <div class="sug-card"><div class="sug-num">NEW SMOKE TEST 4</div><div class="sug-title">test_cache_storage_info_live</div><div class="sug-desc">Calls agent.run_result() after saving a handle. Verifies result.cache_storage returns typed CacheStorageInfo.</div><span class="sug-assert">"answer" in result.cache_storage</span><span class="sug-assert">isinstance(info, CacheStorageInfo)</span><span class="sug-assert">info.location == "memory"</span></div>
    </div></div>
  </div>
</div>

<script>
const SMOKE_DATA = __SMOKE_DATA__;

// ── boot ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  renderMeta();
  renderSummary();
  renderTests();
});

function renderMeta() {
  const d = SMOKE_DATA;
  const t = d.totals;
  const date = new Date(d.run_date).toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short'});
  document.getElementById('page-sub').textContent =
    `${date} · ${d.model} · ${t.tests} tests · ${fmtDur(t.duration_ms)}`;
  document.getElementById('footnote').textContent =
    `Pricing: ${d.model} $${d.pricing.input_per_m}/1M input · $${d.pricing.output_per_m}/1M output. Costs estimated from JSONL token counts.`;
}

function renderSummary() {
  const t = SMOKE_DATA.totals;
  const allPass = t.failed === 0;
  document.getElementById('summary-bar').innerHTML = `
    <div class="sum-tile ${allPass ? 'green' : ''}">
      <div class="slabel">Tests</div>
      <div class="sval">${t.passed} / ${t.tests}</div>
      <div class="ssub">${allPass ? 'all passed' : t.failed + ' failed'}</div>
    </div>
    <div class="sum-tile">
      <div class="slabel">Total tokens</div>
      <div class="sval">${(t.input_tokens + t.output_tokens).toLocaleString()}</div>
      <div class="ssub">${t.input_tokens.toLocaleString()} in · ${t.output_tokens.toLocaleString()} out</div>
    </div>
    <div class="sum-tile clay">
      <div class="slabel">Est. cost</div>
      <div class="sval">${fmtCost(t.cost_usd)}</div>
      <div class="ssub">${SMOKE_DATA.model} pricing</div>
    </div>
    <div class="sum-tile">
      <div class="slabel">Total latency</div>
      <div class="sval">${fmtDur(t.duration_ms)}</div>
      <div class="ssub">wall clock</div>
    </div>`;
}

function renderTests() {
  document.getElementById('test-grid').innerHTML =
    SMOKE_DATA.tests.map(renderCard).join('');
}

function renderCard(test) {
  const t = test.totals;
  const multi = test.harnesses.length > 1;
  const badgeCls = test.status === 'passed' ? 'pass' : 'fail';
  const badgeTxt = test.status.toUpperCase();
  return `<div class="test-card${multi ? ' multi' : ''}" data-test="${esc(test.name)}">
    <div class="card-hdr" onclick="toggle(this)">
      <span class="badge ${badgeCls}">${badgeTxt}</span>
      <span class="tname">${esc(test.short_name)}</span>
      <div class="chips">
        <span class="chip">${t.turns} turn${t.turns !== 1 ? 's' : ''}</span>
        <span class="chip">${(t.input_tokens + t.output_tokens).toLocaleString()} tokens</span>
        <span class="chip">${fmtDur(test.duration_ms)}</span>
        <span class="chip">${fmtCost(t.cost_usd)}</span>
        ${t.tool_errors > 0 ? `<span class="chip warn">${t.tool_errors} error${t.tool_errors > 1 ? 's' : ''}</span>` : ''}
      </div>
      <span class="arrow">▶</span>
    </div>
    <div class="card-body">${renderBody(test)}</div>
  </div>`;
}

function renderBody(test) {
  const t = test.totals;
  let h = `<div class="dcols">
    <div class="dstat"><div class="dl">Input tokens</div><div class="dv">${t.input_tokens.toLocaleString()}</div></div>
    <div class="dstat"><div class="dl">Output tokens</div><div class="dv">${t.output_tokens.toLocaleString()}</div></div>
    <div class="dstat"><div class="dl">Cost (USD)</div><div class="dv clay">${fmtCost(t.cost_usd)}</div></div>
  </div>`;

  const main = test.harnesses[0];
  if (!main) return h;

  if (main.system) {
    h += `<div class="sec"><div class="sec-label">System prompt</div>
      <div class="sys-prompt">${esc(main.system)}</div></div>`;
  }

  if (main.visible_tools?.length) {
    h += `<div class="sec"><div class="sec-label">Visible tools</div>
      <div class="tool-tags">${main.visible_tools.map(t => `<span class="ttag">${esc(t)}</span>`).join('')}</div></div>`;
  }

  test.harnesses.forEach((harness, i) => {
    const label = harness.role === 'main'
      ? `Conversation trace — ${harness.turns} turn${harness.turns !== 1 ? 's' : ''}`
      : `${harness.role} — ${harness.turns} turns · ${harness.input_tokens.toLocaleString()} in · ${harness.output_tokens.toLocaleString()} out · ${fmtCost(harness.cost_usd)}`;
    h += `<div class="harness-section">
      <div class="harness-label">${i > 0 ? '↳ ' : ''}${esc(label)}</div>
      <div class="conv-wrap">${renderConv(harness.conversation)}</div>
    </div>`;
  });

  return h;
}

function renderConv(conversation) {
  if (!conversation?.length) return '<div style="color:var(--gray-3);font-size:13px;font-style:italic">no conversation data</div>';
  return conversation.map(msg => renderMsg(msg)).join('');
}

function renderMsg(msg) {
  if (msg.role === 'user') {
    const isToolResult = msg.content?.some(b => b.type === 'tool_result');
    if (isToolResult) {
      return msg.content.map(b => renderToolResultBlock(b)).join('');
    }
    const txt = msg.content?.filter(b => b.type === 'text').map(b => b.text).join('\n') || '';
    return `<div class="conv-msg user-msg role-user">
      <div class="conv-role">👤 user</div>
      <div class="conv-text">${esc(txt)}</div>
    </div>`;
  }
  if (msg.role === 'assistant') {
    const m = msg.turn_metrics;
    const metaTxt = m ? `${m.input_tokens}↑ ${m.output_tokens}↓ · ${Math.round(m.latency_ms)}ms` : '';
    const stop = msg.stop_reason ? ` · stop: ${msg.stop_reason}` : '';
    let inner = '';
    for (const b of (msg.content || [])) {
      if (b.type === 'text') {
        inner += `<div class="conv-text">${esc(b.text)}</div>`;
      } else if (b.type === 'tool_use') {
        inner += renderToolUseBlock(b);
      }
    }
    return `<div class="conv-msg assistant-msg role-assistant">
      <div class="conv-role">🤖 assistant<span class="turn-meta">&nbsp;${esc(metaTxt + stop)}</span></div>
      ${inner}
    </div>`;
  }
  return '';
}

function renderToolUseBlock(b) {
  const isPy = b.name === 'python_interpreter' && b.input?.code;
  const inputStr = isPy ? b.input.code : JSON.stringify(b.input, null, 2);
  return `<div class="tool-call">
    <div class="tool-call-hdr"><span class="tool-badge">⚙ ${esc(b.name)}</span></div>
    <pre class="code-block"><code>${esc(inputStr)}</code></pre>
  </div>`;
}

function renderToolResultBlock(b) {
  const isErr = b.is_error;
  const content = String(b.content || '');
  return `<div class="conv-msg tool-result-msg ${isErr ? 'role-tool-err' : 'role-tool'}">
    <div class="conv-role">${isErr ? '✗ tool error' : '✓ tool result'}</div>
    <div class="tool-output ${isErr ? 'err-out' : ''}">
      <pre class="code-block"><code>${esc(content)}</code></pre>
    </div>
  </div>`;
}

// ── helpers ──────────────────────────────────────────────────────────────────
function toggle(hdr) { hdr.closest('.test-card').classList.toggle('open'); }
function switchTab(id, btn) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  btn.classList.add('active');
}
function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fmtDur(ms) {
  if (ms >= 60000) return `${Math.floor(ms/60000)}m ${Math.round((ms%60000)/1000)}s`;
  if (ms >= 1000) return `${(ms/1000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
}
function fmtCost(usd) {
  if (usd < 0.0001) return `$${usd.toFixed(7)}`;
  if (usd < 0.01)   return `$${usd.toFixed(6)}`;
  return `$${usd.toFixed(4)}`;
}

// ── export ───────────────────────────────────────────────────────────────────
function copyAs(btn, fmt) {
  const text = fmt === 'json' ? JSON.stringify(SMOKE_DATA, null, 2) : buildMd();
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.textContent;
    btn.textContent = 'Copied!'; btn.classList.add('copied');
    setTimeout(() => { btn.textContent = orig; btn.classList.remove('copied'); }, 2000);
  });
}
function buildMd() {
  const d = SMOKE_DATA; const t = d.totals;
  const date = new Date(d.run_date).toLocaleString('en-GB',{dateStyle:'medium',timeStyle:'short'});
  let md = `# dataact smoke dashboard\n\n**${date}** · ${d.model} · ${t.tests} tests · ${fmtDur(t.duration_ms)}\n\n`;
  md += `## Summary\n| Metric | Value |\n|---|---|\n`;
  md += `| Tests | ${t.passed}/${t.tests} passed |\n| Tokens | ${(t.input_tokens+t.output_tokens).toLocaleString()} |\n`;
  md += `| Cost | ${fmtCost(t.cost_usd)} |\n\n`;
  md += `## Results\n| Test | Status | Turns | Tokens | Cost | Errors |\n|---|---|---|---|---|---|\n`;
  for (const test of d.tests) {
    const tt = test.totals;
    md += `| ${test.short_name} | ${test.status} | ${tt.turns} | ${(tt.input_tokens+tt.output_tokens).toLocaleString()} | ${fmtCost(tt.cost_usd)} | ${tt.tool_errors} |\n`;
  }
  return md;
}
</script>
</body>
</html>
""".replace("__SMOKE_DATA__", "__SMOKE_DATA__")  # sentinel kept for .replace() in build_html


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("smoke_results/latest.json")
    data = json.loads(path.read_text())
    out = path.with_suffix(".html")
    out.write_text(build_html(data))
    print(f"Written: {out}")
