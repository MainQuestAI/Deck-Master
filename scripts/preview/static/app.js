const state = {
  deck: null,
  runs: [],
  narrative: null,
  assetSignals: null,
  governance: null,
  currentRunId: new URLSearchParams(window.location.search).get("run") || "",
  selectedIndex: 0,
};

const els = {
  title: document.querySelector("#deck-title"),
  meta: document.querySelector("#deck-meta"),
  list: document.querySelector("#page-list"),
  label: document.querySelector("#current-label"),
  frame: document.querySelector("#preview-frame"),
  pageTitle: document.querySelector("#page-title"),
  details: document.querySelector("#page-details"),
  decision: document.querySelector("#decision"),
  notes: document.querySelector("#notes"),
  save: document.querySelector("#save-decision"),
  saveStatus: document.querySelector("#save-status"),
  form: document.querySelector("#create-run-form"),
  brief: document.querySelector("#brief"),
  industry: document.querySelector("#industry"),
  targetPages: document.querySelector("#target-pages"),
  libraryMode: document.querySelector("#library-mode"),
  create: document.querySelector("#create-run"),
  createStatus: document.querySelector("#create-status"),
  runList: document.querySelector("#run-list"),
  first: document.querySelector("#first-page"),
  prev: document.querySelector("#prev-page"),
  next: document.querySelector("#next-page"),
  last: document.querySelector("#last-page"),
  narrativeTitle: document.querySelector("#narrative-title"),
  narrativeContent: document.querySelector("#narrative-content"),
  pageNarrativeDetail: document.querySelector("#page-narrative-detail"),
  assetSignalsTitle: document.querySelector("#asset-signals-title"),
  assetSignalsContent: document.querySelector("#asset-signals-content"),
  pageAssetSignalsDetail: document.querySelector("#page-asset-signals-detail"),
  governanceTitle: document.querySelector("#governance-title"),
  governanceContent: document.querySelector("#governance-content"),
};

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  return data;
}

function runQuery(extra = {}) {
  const params = new URLSearchParams(extra);
  if (state.currentRunId) {
    params.set("run_id", state.currentRunId);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function loadRuns() {
  try {
    const data = await requestJson("/api/runs");
    state.runs = data.runs || [];
    renderRuns();
    if (!state.currentRunId && state.runs.length) {
      state.currentRunId = state.runs[0].run_id;
      updateLocation();
    }
  } catch (error) {
    els.createStatus.textContent = error.message;
  }
}

async function loadDeck() {
  try {
    state.deck = await requestJson(`/api/deck${runQuery()}`);
    els.title.textContent = state.deck.title;
    els.meta.textContent = `${state.deck.run_id} · ${state.deck.status} · ${state.deck.pages.length} pages${qualitySummaryText(state.deck.quality)}`;
    renderList();
    selectPage(0);
    loadNarrative();
    loadAssetSignals();
    loadGovernance();
  } catch (error) {
    state.deck = null;
    state.narrative = null;
    state.assetSignals = null;
    state.governance = null;
    els.title.textContent = "Studio";
    els.meta.textContent = "Create or select a run.";
    els.list.innerHTML = "";
    els.frame.innerHTML = `<div class="empty error">${escapeHtml(error.message)}</div>`;
    renderNarrative();
    renderAssetSignals();
    renderGovernance();
  }
}

function renderRuns() {
  if (!els.runList) return;
  els.runList.innerHTML = "";
  if (!state.runs.length) {
    els.runList.innerHTML = '<p class="muted">No runs yet.</p>';
    return;
  }
  state.runs.forEach((run) => {
    const item = document.createElement("button");
    item.className = "run-card";
    item.dataset.active = run.run_id === state.currentRunId ? "true" : "false";
    item.innerHTML = `
      <strong>${escapeHtml(run.title || run.run_id)}</strong>
      <small>${escapeHtml(run.run_id)} · ${escapeHtml(run.status)} · ${run.pages || 0} pages</small>
    `;
    item.addEventListener("click", () => {
      state.currentRunId = run.run_id;
      updateLocation();
      loadDeck();
      renderRuns();
    });
    els.runList.appendChild(item);
  });
}

function renderList() {
  if (!state.deck) return;
  els.list.innerHTML = "";
  state.deck.pages.forEach((page, index) => {
    const item = document.createElement("button");
    item.className = `page-card decision-${page.decision}`;
    item.dataset.active = index === state.selectedIndex ? "true" : "false";
    item.innerHTML = `
      <span class="page-no">${String(page.order).padStart(2, "0")}</span>
      <span>
        <strong>${escapeHtml(page.title || page.page_id)}</strong>
        <small>${escapeHtml(page.source_type)} · ${escapeHtml(page.decision)}${page.quality && page.quality.length ? ` · ${page.quality.length} quality finding(s)` : ""}</small>
      </span>
      ${page.asset_exists ? "" : '<b class="warn">!</b>'}
    `;
    item.addEventListener("click", () => selectPage(index));
    els.list.appendChild(item);
  });
}

function selectPage(index) {
  if (!state.deck || !state.deck.pages.length) return;
  state.selectedIndex = Math.max(0, Math.min(index, state.deck.pages.length - 1));
  const page = state.deck.pages[state.selectedIndex];
  renderList();
  renderPage(page);
}

function renderPage(page) {
  els.label.textContent = `${page.order} / ${state.deck.pages.length} · ${page.page_id}`;
  els.pageTitle.textContent = page.title || page.page_id;
  els.decision.value = page.decision;
  els.notes.value = page.notes || "";
  els.saveStatus.textContent = "";

  els.details.innerHTML = detailRows({
    "Source": page.source_type,
    "Sourcing decision": page.source_decision || "",
    "Narrative role": page.narrative_role,
    "Reason": page.decision_reason || page.reuse_reason || page.generation_reason || "",
    "Confidence": page.confidence ?? "",
    "Risks": Array.isArray(page.risk_flags) ? page.risk_flags.join(", ") : "",
    "Quality findings": summarizeQuality(page.quality),
    "Alternatives": summarizeAlternatives(page.alternatives),
    "Generation task": page.generation_task ? page.generation_task.task_id : "",
    "Original PPT": page.source_pptx || "",
    "Slide index": page.source_slide_index ?? "",
    "Preview path": page.preview_path,
    "Asset": page.asset_exists ? "Available" : page.asset_error,
  });

  if (page.asset_exists) {
    els.frame.innerHTML = `<img src="${page.preview_url}${runQuery({ t: Date.now() })}" alt="${escapeHtml(page.title || page.page_id)}">`;
  } else {
    els.frame.innerHTML = `<div class="empty error"><strong>Preview unavailable</strong><p>${escapeHtml(page.asset_error)}</p></div>`;
  }

  renderPageNarrativeDetail(page);
  renderPageAssetSignalsDetail(page);
}

function qualitySummaryText(quality) {
  if (!quality || !Object.keys(quality).length) return "";
  return Object.entries(quality)
    .map(([gate, report]) => ` · ${gate}: ${report.status}${report.blocks_delivery ? " blocked" : ""}`)
    .join("");
}

function summarizeQuality(findings) {
  if (!Array.isArray(findings) || !findings.length) return "";
  return findings
    .map((item) => `${item.gate || "quality"} ${item.severity || ""}: ${item.message || item.finding_id || ""}${item.repair_instruction ? ` | Repair: ${item.repair_instruction}` : ""}`)
    .join(" · ");
}

function summarizeAlternatives(alternatives) {
  if (!Array.isArray(alternatives) || !alternatives.length) return "";
  return alternatives
    .slice(0, 3)
    .map((item) => `${item.title || item.candidate_id || "candidate"} (${item.confidence ?? ""})`)
    .join(" · ");
}

function detailRows(rows) {
  return Object.entries(rows)
    .filter(([, value]) => value !== "" && value !== null && value !== undefined)
    .map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(String(value))}</dd>`)
    .join("");
}

async function saveDecision() {
  const page = state.deck.pages[state.selectedIndex];
  els.save.disabled = true;
  els.saveStatus.textContent = "Saving...";
  try {
    const updated = await requestJson(`/api/page/${page.page_id}/decision${runQuery()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        decision: els.decision.value,
        notes: els.notes.value,
      }),
    });
    state.deck.pages[state.selectedIndex] = updated;
    renderList();
    renderPage(updated);
    els.saveStatus.textContent = "Saved to preview_manifest.json";
  } catch (error) {
    els.saveStatus.textContent = error.message;
  } finally {
    els.save.disabled = false;
  }
}

async function createRun(event) {
  event.preventDefault();
  const brief = els.brief.value.trim();
  if (!brief) {
    els.createStatus.textContent = "Brief is required.";
    return;
  }
  els.create.disabled = true;
  els.createStatus.textContent = "Generating draft...";
  try {
    const payload = await requestJson("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        brief,
        industry: els.industry.value.trim(),
        target_pages: els.targetPages.value,
        audience: "client",
        library_mode: els.libraryMode.value,
      }),
    });
    state.currentRunId = payload.run_id;
    updateLocation();
    els.createStatus.textContent = `Draft ready: ${payload.pages} pages`;
    await loadRuns();
    await loadDeck();
  } catch (error) {
    els.createStatus.textContent = error.message;
  } finally {
    els.create.disabled = false;
  }
}

function updateLocation() {
  if (!state.currentRunId) return;
  const url = new URL(window.location.href);
  url.searchParams.set("run", state.currentRunId);
  window.history.replaceState({}, "", url);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

async function loadNarrative() {
  if (!state.currentRunId) {
    state.narrative = null;
    renderNarrative();
    return;
  }
  try {
    state.narrative = await requestJson(`/api/narrative/${encodeURIComponent(state.currentRunId)}`);
    renderNarrative();
  } catch (error) {
    state.narrative = null;
    renderNarrative(error.message);
  }
}

function renderNarrative(errorMsg) {
  if (!els.narrativeContent) return;
  if (errorMsg) {
    els.narrativeContent.innerHTML = `<p class="muted">${escapeHtml(errorMsg)}</p>`;
    return;
  }
  if (!state.narrative) {
    els.narrativeContent.innerHTML = '<p class="muted">选择 run 后加载叙事数据...</p>';
    return;
  }
  const brief = state.narrative.deck_brief || {};
  const judgments = state.narrative.judgments || {};
  const claimGraph = state.narrative.claim_graph || {};
  const judgmentList = Array.isArray(judgments.judgments) ? judgments.judgments.slice(0, 5) : [];
  const claims = Array.isArray(claimGraph.claims) ? claimGraph.claims : [];
  const gaps = Array.isArray(claimGraph.gaps) ? claimGraph.gaps : [];
  const evidenceCount = claims.reduce((sum, c) => sum + (Array.isArray(c.evidence) ? c.evidence.length : 0), 0);

  const sections = [];

  // Deck objective
  if (brief.business_goal) {
    sections.push(`<div class="narrative-section"><dt>Deck Objective</dt><dd>${escapeHtml(brief.business_goal)}</dd></div>`);
  }

  // Core thesis
  const corePoints = Array.isArray(brief.core_points) ? brief.core_points : [];
  if (corePoints.length) {
    sections.push(`<div class="narrative-section"><dt>Core Thesis</dt><dd><ul>${corePoints.map((p) => `<li>${escapeHtml(p)}</li>`).join("")}</ul></dd></div>`);
  }

  // Audience strategy
  if (brief.audience) {
    const audienceText = typeof brief.audience === "string" ? brief.audience : JSON.stringify(brief.audience);
    sections.push(`<div class="narrative-section"><dt>Audience Strategy</dt><dd>${escapeHtml(audienceText)}</dd></div>`);
  }

  // Top judgments
  if (judgmentList.length) {
    sections.push(`<div class="narrative-section"><dt>Top Judgments (${judgmentList.length})</dt><dd><ol>${judgmentList.map((j) => `<li><strong>${escapeHtml(j.label || j.id || "")}</strong>: ${escapeHtml(j.summary || j.text || "")}${j.confidence != null ? ` <small>(${j.confidence})</small>` : ""}</li>`).join("")}</ol></dd></div>`);
  }

  // Claim evidence coverage
  sections.push(`<div class="narrative-section"><dt>Claim Evidence Coverage</dt><dd>${claims.length} claims · ${evidenceCount} evidence items${claims.length ? ` · ${(evidenceCount / claims.length).toFixed(1)} avg` : ""}</dd></div>`);

  // Gaps
  if (gaps.length) {
    sections.push(`<div class="narrative-section narrative-gaps"><dt>Gaps (${gaps.length})</dt><dd><ul>${gaps.map((g) => `<li>${escapeHtml(g.description || g.gap_id || JSON.stringify(g))}</li>`).join("")}</ul></dd></div>`);
  }

  if (!sections.length) {
    els.narrativeContent.innerHTML = '<p class="muted">该 run 暂无叙事审查数据（deck_brief / judgments / claim_graph）。</p>';
    return;
  }

  els.narrativeContent.innerHTML = `<dl class="narrative-dl">${sections.join("")}</dl>`;
}

function renderPageNarrativeDetail(page) {
  if (!els.pageNarrativeDetail) return;
  if (!state.narrative || !page) {
    els.pageNarrativeDetail.innerHTML = "";
    return;
  }
  const claimMap = state.narrative.claim_map || {};
  const claimGraph = state.narrative.claim_graph || {};
  const pageClaims = Array.isArray(claimMap.pages)
    ? claimMap.pages.find((p) => p.page_id === page.page_id)
    : null;
  const graphClaims = Array.isArray(claimGraph.claims)
    ? claimGraph.claims.filter((c) => c.page_id === page.page_id)
    : [];

  const parts = [];
  if (pageClaims && pageClaims.core_claim) {
    parts.push(`<dt>Page Core Claim</dt><dd>${escapeHtml(pageClaims.core_claim)}</dd>`);
  }
  if (pageClaims && pageClaims.evidence_policy) {
    parts.push(`<dt>Evidence Policy</dt><dd>${escapeHtml(typeof pageClaims.evidence_policy === "string" ? pageClaims.evidence_policy : JSON.stringify(pageClaims.evidence_policy))}</dd>`);
  }
  if (graphClaims.length) {
    const evidenceTotal = graphClaims.reduce((s, c) => s + (Array.isArray(c.evidence) ? c.evidence.length : 0), 0);
    parts.push(`<dt>Linked Claims</dt><dd>${graphClaims.length} claims · ${evidenceTotal} evidence</dd>`);
  }

  els.pageNarrativeDetail.innerHTML = parts.length ? `<dl>${parts.join("")}</dl>` : "";
}

async function loadAssetSignals() {
  if (!state.currentRunId) {
    state.assetSignals = null;
    renderAssetSignals();
    return;
  }
  try {
    state.assetSignals = await requestJson(`/api/asset-signals/${encodeURIComponent(state.currentRunId)}`);
    renderAssetSignals();
  } catch (error) {
    state.assetSignals = null;
    renderAssetSignals(error.message);
  }
}

function renderAssetSignals(errorMsg) {
  if (!els.assetSignalsContent) return;
  if (errorMsg) {
    els.assetSignalsContent.innerHTML = `<p class="muted">${escapeHtml(errorMsg)}</p>`;
    return;
  }
  if (!state.assetSignals) {
    els.assetSignalsContent.innerHTML = '<p class="muted">选择 run 后加载资产信号...</p>';
    return;
  }

  const pageSignals = Array.isArray(state.assetSignals.page_signals) ? state.assetSignals.page_signals : [];
  const hasAssetGraph = !!state.assetSignals.asset_graph;
  const hasFeedback = Array.isArray(state.assetSignals.feedback) && state.assetSignals.feedback.length > 0;

  if (!hasAssetGraph && !hasFeedback && !pageSignals.length) {
    els.assetSignalsContent.innerHTML = '<p class="muted asset-unavailable">资产数据不可用 — 该 run 暂无 asset graph 或 feedback 记录。</p>';
    return;
  }

  // Summary stats
  const totalDelivered = pageSignals.reduce((s, p) => s + (p.delivered_count || 0), 0);
  const totalFeedback = pageSignals.reduce((s, p) => s + (p.feedback_count || 0), 0);
  const avgApproval = pageSignals.filter((p) => p.approval_rate != null).reduce((acc, p, _, arr) => acc + p.approval_rate / arr.length, 0);
  const pagesWithFlags = pageSignals.filter((p) => p.health_flags && p.health_flags.length > 0).length;

  const sections = [];

  sections.push(`<div class="signal-section"><dt>总览</dt><dd>${pageSignals.length} 页 · ${totalDelivered} 已交付 · ${totalFeedback} 条反馈${avgApproval ? ` · ${(avgApproval * 100).toFixed(0)}% 平均通过率` : ""}${pagesWithFlags ? ` · <span class="warn">${pagesWithFlags} 页有健康标记</span>` : ""}</dd></div>`);

  // Per-page signal cards
  if (pageSignals.length) {
    const cards = pageSignals.map((ps) => {
      const rateText = ps.approval_rate != null ? `${(ps.approval_rate * 100).toFixed(0)}%` : "—";
      const flagsText = ps.health_flags && ps.health_flags.length ? ps.health_flags.join(", ") : "";
      const candidateScore = ps.selected_candidate ? (ps.selected_candidate.score ?? ps.selected_candidate.confidence ?? "") : "";
      return `<div class="signal-card" data-page-id="${escapeHtml(ps.page_id)}">
        <strong>${escapeHtml(ps.page_id)}</strong>
        <small>通过率 ${rateText} · 拒绝 ${ps.rejection_count} · 交付 ${ps.delivered_count}${ps.has_screenshot ? " · 📷" : ""}${candidateScore !== "" ? ` · 评分 ${candidateScore}` : ""}</small>
        ${flagsText ? `<small class="warn">⚠ ${escapeHtml(flagsText)}</small>` : ""}
      </div>`;
    });
    sections.push(`<div class="signal-section"><dt>页面信号</dt><dd class="signal-cards">${cards.join("")}</dd></div>`);
  }

  els.assetSignalsContent.innerHTML = `<dl class="signal-dl">${sections.join("")}</dl>`;
}

function renderPageAssetSignalsDetail(page) {
  if (!els.pageAssetSignalsDetail) return;
  if (!state.assetSignals || !page) {
    els.pageAssetSignalsDetail.innerHTML = "";
    return;
  }

  const pageSignals = Array.isArray(state.assetSignals.page_signals) ? state.assetSignals.page_signals : [];
  const ps = pageSignals.find((p) => p.page_id === page.page_id);
  if (!ps) {
    els.pageAssetSignalsDetail.innerHTML = "";
    return;
  }

  const parts = [];
  const rateText = ps.approval_rate != null ? `${(ps.approval_rate * 100).toFixed(0)}%` : "无数据";
  parts.push(`<dt>Asset Approval Rate</dt><dd>${escapeHtml(rateText)}</dd>`);
  parts.push(`<dt>Feedback Count</dt><dd>${ps.feedback_count} (${ps.rejection_count} rejected)</dd>`);
  parts.push(`<dt>Delivered Assets</dt><dd>${ps.delivered_count}${ps.has_screenshot ? " · screenshot available" : ""}</dd>`);

  if (ps.health_flags && ps.health_flags.length) {
    parts.push(`<dt>Health Flags</dt><dd class="warn">${escapeHtml(ps.health_flags.join(", "))}</dd>`);
  }

  if (ps.selected_candidate) {
    const sc = ps.selected_candidate;
    const scoreParts = [];
    if (sc.score != null) scoreParts.push(`score: ${sc.score}`);
    if (sc.confidence != null) scoreParts.push(`confidence: ${sc.confidence}`);
    if (sc.source_type) scoreParts.push(`source: ${sc.source_type}`);
    if (sc.candidate_id) scoreParts.push(`id: ${sc.candidate_id}`);
    if (scoreParts.length) {
      parts.push(`<dt>Selected Candidate</dt><dd>${escapeHtml(scoreParts.join(" · "))}</dd>`);
    }
  }

  els.pageAssetSignalsDetail.innerHTML = parts.length ? `<dl>${parts.join("")}</dl>` : "";
}

async function loadGovernance() {
  if (!state.currentRunId) {
    state.governance = null;
    renderGovernance();
    return;
  }
  try {
    state.governance = await requestJson(`/api/quality-governance/${encodeURIComponent(state.currentRunId)}`);
    renderGovernance();
  } catch (error) {
    state.governance = null;
    renderGovernance(error.message);
  }
}

function renderGovernance(errorMsg) {
  if (!els.governanceContent) return;
  if (errorMsg) {
    els.governanceContent.innerHTML = `<p class="muted">${escapeHtml(errorMsg)}</p>`;
    return;
  }
  if (!state.governance) {
    els.governanceContent.innerHTML = '<p class="muted">选择 run 后加载质量治理数据...</p>';
    return;
  }

  const g = state.governance;
  const sections = [];

  // Delivery readiness indicator
  const readiness = g.delivery_readiness || {};
  const readyClass = readiness.ready ? "governance-ready" : "governance-blocked";
  const readyLabel = readiness.ready ? "Ready for delivery" : "Blocked";
  sections.push(`<div class="governance-section governance-readiness ${readyClass}">
    <dt>Delivery Readiness</dt>
    <dd><strong>${readyLabel}</strong>${readiness.has_blocking_gates ? " · has blocking gates" : ""}${readiness.active_override_count ? ` · ${readiness.active_override_count} active override(s)` : ""}</dd>
  </div>`);

  // Gate summary cards
  const gates = Array.isArray(g.gate_summary) ? g.gate_summary : [];
  if (gates.length) {
    const gateCards = gates.map((gate) => {
      const statusClass = gate.blocks_delivery ? "gate-fail" : "gate-pass";
      return `<div class="gate-card ${statusClass}">
        <strong>${escapeHtml(gate.gate)}</strong>
        <small>${escapeHtml(gate.status)} · ${gate.findings_count} findings${gate.page_findings_count ? ` · ${gate.page_findings_count} page-level` : ""}</small>
      </div>`;
    });
    sections.push(`<div class="governance-section"><dt>Gate Summary</dt><dd class="gate-cards">${gateCards.join("")}</dd></div>`);
  }

  // Page-level findings
  const findings = Array.isArray(g.page_findings) ? g.page_findings : [];
  if (findings.length) {
    const findingItems = findings.slice(0, 20).map((f) => {
      const sevClass = f.severity === "P0" ? "severity-p0" : f.severity === "P1" ? "severity-p1" : "severity-p2";
      const pageTag = f.page_id ? ` [${escapeHtml(f.page_id)}]` : "";
      return `<div class="finding-item ${sevClass}">
        <small><strong>${escapeHtml(f.severity || "")}</strong> ${escapeHtml(f.gate || "")}${pageTag}</small>
        <span>${escapeHtml(f.message || f.finding_id || "")}</span>
        ${f.repair_instruction ? `<small class="repair">Repair: ${escapeHtml(f.repair_instruction)}</small>` : ""}
      </div>`;
    });
    sections.push(`<div class="governance-section"><dt>Findings (${findings.length})</dt><dd class="findings-list">${findingItems.join("")}</dd></div>`);
  }

  // Active overrides
  const overrides = Array.isArray(g.active_overrides) ? g.active_overrides : [];
  if (overrides.length) {
    const overrideItems = overrides.map((o) => {
      return `<div class="override-item">
        <small><strong>${escapeHtml(o.override_id || "")}</strong> · ${escapeHtml(o.severity || "")} · ${escapeHtml(o.target_id || "")}</small>
        <span>${escapeHtml(o.reason || "")}</span>
        <small>by ${escapeHtml(o.approver || o.actor || "")} · expires ${escapeHtml(o.expires_at ? o.expires_at.split("T")[0] : "")}</small>
        <button class="revoke-override-btn" data-override-id="${escapeHtml(o.override_id || "")}">Revoke</button>
      </div>`;
    });
    sections.push(`<div class="governance-section"><dt>Active Overrides (${overrides.length})</dt><dd class="overrides-list">${overrideItems.join("")}</dd></div>`);
  }

  // Validation status
  if (g.validation_status) {
    const lineage = g.lineage || {};
    sections.push(`<div class="governance-section">
      <dt>Final Artifact Validation</dt>
      <dd>${escapeHtml(g.validation_status)}${lineage.artifact_hash ? ` · hash: ${escapeHtml(lineage.artifact_hash.substring(0, 12))}...` : ""}${lineage.page_count != null ? ` · ${lineage.page_count} pages` : ""}</dd>
    </div>`);
  }

  // Delivery outcome form
  const outcome = g.outcome || {};
  const deliveredText = outcome.delivered ? `Delivered at ${escapeHtml(outcome.delivered_at ? outcome.delivered_at.split("T")[0] : "")}` : "Not delivered";
  const reactionText = outcome.customer_reaction ? ` · Reaction: ${escapeHtml(outcome.customer_reaction)}` : "";
  sections.push(`<div class="governance-section">
    <dt>Delivery Outcome</dt>
    <dd>${deliveredText}${reactionText}</dd>
    <div class="delivery-form">
      <button class="primary mark-delivered-btn"${outcome.delivered ? " disabled" : ""}>Mark as delivered</button>
      <div class="form-row-inline">
        <input id="customer-reaction" placeholder="Customer reaction..." value="${escapeHtml(outcome.customer_reaction || "")}">
        <button class="record-reaction-btn">Save reaction</button>
      </div>
    </div>
  </div>`);

  els.governanceContent.innerHTML = `<dl class="governance-dl">${sections.join("")}</dl>`;

  // Wire up buttons
  const revokeButtons = els.governanceContent.querySelectorAll(".revoke-override-btn");
  revokeButtons.forEach((btn) => {
    btn.addEventListener("click", () => handleRevokeOverride(btn.dataset.overrideId));
  });

  const markBtn = els.governanceContent.querySelector(".mark-delivered-btn");
  if (markBtn) {
    markBtn.addEventListener("click", handleMarkDelivered);
  }

  const reactionBtn = els.governanceContent.querySelector(".record-reaction-btn");
  if (reactionBtn) {
    reactionBtn.addEventListener("click", handleRecordReaction);
  }
}

async function handleRevokeOverride(overrideId) {
  if (!overrideId || !state.currentRunId) return;
  const reason = prompt("Reason for revoking this override:");
  if (reason === null) return;
  try {
    await requestJson(`/api/override/revoke${runQuery()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ override_id: overrideId, reason }),
    });
    await loadGovernance();
  } catch (error) {
    alert(error.message);
  }
}

async function handleMarkDelivered() {
  if (!state.currentRunId) return;
  try {
    await requestJson(`/api/delivery/mark-delivered${runQuery()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    await loadGovernance();
  } catch (error) {
    alert(error.message);
  }
}

async function handleRecordReaction() {
  if (!state.currentRunId) return;
  const reactionInput = document.querySelector("#customer-reaction");
  const reaction = reactionInput ? reactionInput.value.trim() : "";
  try {
    await requestJson(`/api/delivery/record-reaction${runQuery()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ customer_reaction: reaction, delivered: true }),
    });
    await loadGovernance();
  } catch (error) {
    alert(error.message);
  }
}

els.form.addEventListener("submit", createRun);
els.save.addEventListener("click", saveDecision);
els.first.addEventListener("click", () => selectPage(0));
els.prev.addEventListener("click", () => selectPage(state.selectedIndex - 1));
els.next.addEventListener("click", () => selectPage(state.selectedIndex + 1));
els.last.addEventListener("click", () => selectPage(state.deck.pages.length - 1));
document.addEventListener("keydown", (event) => {
  if (event.key === "ArrowLeft") selectPage(state.selectedIndex - 1);
  if (event.key === "ArrowRight") selectPage(state.selectedIndex + 1);
});

loadRuns().then(loadDeck);
