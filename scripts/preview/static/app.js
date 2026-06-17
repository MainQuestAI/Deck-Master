const state = {
  deck: null,
  runs: [],
  narrative: null,
  assetSignals: null,
  governance: null,
  reviewSummary: null,
  claimCoverage: null,
  nextActions: null,
  externalResults: null,
  exportQueue: null,
  metrics: null,
  currentRunId: new URLSearchParams(window.location.search).get("run") || "",
  selectedIndex: 0,
  setupStatus: null,
  runState: null,
};

const els = {
  title: document.querySelector("#deck-title"),
  meta: document.querySelector("#deck-meta"),
  list: document.querySelector("#page-list"),
  label: document.querySelector("#current-label"),
  frame: document.querySelector("#preview-frame"),
  pageTitle: document.querySelector("#page-title"),
  details: document.querySelector("#page-details"),
  notes: document.querySelector("#notes"),
  save: document.querySelector("#save-decision"),
  saveStatus: document.querySelector("#save-status"),
  pageActionStatus: document.querySelector("#page-action-status"),
  approvePage: document.querySelector("#approve-page"),
  rejectPage: document.querySelector("#reject-page"),
  requestEvidence: document.querySelector("#request-evidence"),
  convertGenerate: document.querySelector("#convert-generate"),
  lockSource: document.querySelector("#lock-source"),
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
  overallReadiness: document.querySelector("#overall-readiness"),
  exportReadiness: document.querySelector("#export-readiness"),
  metricsLine: document.querySelector("#metrics-line"),
  readinessContent: document.querySelector("#readiness-content"),
  claimCoverageContent: document.querySelector("#claim-coverage-content"),
  nextActionsContent: document.querySelector("#next-actions-content"),
  externalResultsContent: document.querySelector("#external-results-content"),
  exportQueueContent: document.querySelector("#export-queue-content"),
  metricsContent: document.querySelector("#metrics-content"),
  setupBanner: document.querySelector("#setup-banner"),
  setupStatusLabel: document.querySelector("#setup-status-label"),
  setupNextCommand: document.querySelector("#setup-next-command"),
  runStatePanel: document.querySelector("#run-state-panel"),
  runStateLabel: document.querySelector("#run-state-label"),
  runStateDetail: document.querySelector("#run-state-detail"),
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
  if (!state.currentRunId) {
    renderRunWithoutPreview(null, "Create or select a run.");
    clearRunState();
    return;
  }
  await loadRunState();
  const currentRun = currentRunSummary();
  if (currentRun && Number(currentRun.pages || 0) === 0) {
    renderRunWithoutPreview(currentRun, state.runState && state.runState.next_command ? `Next: ${state.runState.next_command}` : "Preview is not ready yet.");
    return;
  }
  try {
    state.deck = await requestJson(`/api/deck${runQuery()}`);
    els.title.textContent = state.deck.title;
    els.meta.textContent = `${state.deck.run_id} · ${state.deck.status} · ${state.deck.pages.length} pages${qualitySummaryText(state.deck.quality)}`;
    renderList();
    selectPage(0);
    loadNarrative();
    loadAssetSignals();
    loadGovernance();
    loadCockpitData();
  } catch (error) {
    state.deck = null;
    state.narrative = null;
    state.assetSignals = null;
    state.governance = null;
    state.runState = null;
    clearCockpitData();
    clearRunState();
    els.title.textContent = "Studio";
    els.meta.textContent = "Create or select a run.";
    els.list.innerHTML = "";
    els.frame.innerHTML = `<div class="empty error">${escapeHtml(error.message)}</div>`;
    renderNarrative();
    renderAssetSignals();
    renderGovernance();
    renderCockpitData();
  }
}

function currentRunSummary() {
  return state.runs.find((run) => run.run_id === state.currentRunId) || null;
}

function renderRunWithoutPreview(run, message) {
  state.deck = null;
  state.narrative = null;
  state.assetSignals = null;
  state.governance = null;
  clearCockpitData();
  els.title.textContent = run ? (run.title || run.run_id) : "Studio";
  els.meta.textContent = run
    ? `${run.run_id} · ${run.status || "request_ready"} · ${run.pages || 0} pages`
    : "Create or select a run.";
  els.list.innerHTML = "";
  els.label.textContent = "No page selected";
  els.pageTitle.textContent = run ? "Preview not ready" : "No page selected";
  els.details.innerHTML = "";
  els.notes.value = "";
  els.saveStatus.textContent = "";
  if (els.pageActionStatus) {
    els.pageActionStatus.textContent = "";
  }
  els.frame.innerHTML = `<div class="empty">${escapeHtml(message || "Preview is not ready yet.")}</div>`;
  renderNarrative();
  renderAssetSignals();
  renderGovernance();
  renderCockpitData();
}

function clearRunState() {
  state.runState = null;
  renderRunState();
}

function renderRunState(errorMsg) {
  if (!els.runStatePanel) return;

  if (errorMsg) {
    els.runStateLabel.textContent = "Error";
    els.runStateDetail.textContent = errorMsg;
    return;
  }

  if (!state.currentRunId || !state.runState) {
    els.runStateLabel.textContent = "No run selected";
    els.runStateDetail.textContent = "Select a run to view status and next command.";
    return;
  }

  const status = state.runState.status || "unknown";
  const stage = state.runState.stage || "";
  const mode = state.runState.run_mode ? ` · ${state.runState.run_mode}` : "";
  const nextCommand = state.runState.next_command || "";
  els.runStateLabel.textContent = `${status}${stage ? ` · ${stage}` : ""}${mode}`;
  els.runStateDetail.textContent = nextCommand ? `Next: ${nextCommand}` : "No action required.";
}

async function loadRunState() {
  if (!state.currentRunId) {
    clearRunState();
    return;
  }
  try {
    state.runState = await requestJson(`/api/run-state/${encodeURIComponent(state.currentRunId)}`);
    renderRunState();
  } catch (error) {
    state.runState = null;
    renderRunState(error.message);
  }
}

function renderSetupStatus(errorMsg) {
  if (!els.setupBanner) return;

  if (errorMsg) {
    els.setupBanner.classList.remove("ready", "warning");
    els.setupStatusLabel.textContent = "Unavailable";
    els.setupNextCommand.textContent = errorMsg;
    return;
  }

  if (!state.setupStatus) {
    els.setupBanner.classList.remove("ready", "warning");
    els.setupStatusLabel.textContent = "Checking...";
    els.setupNextCommand.textContent = "Loading setup status.";
    return;
  }

  const status = String(state.setupStatus.status || "unknown");
  const nextCommand = state.setupStatus.next_command || "";
  els.setupBanner.classList.remove("ready", "warning");
  if (status === "ready" && state.setupStatus.production_ready) {
    els.setupBanner.classList.add("ready");
  } else {
    els.setupBanner.classList.add("warning");
  }
  els.setupStatusLabel.textContent = status;
  els.setupNextCommand.textContent = nextCommand || "Setup command available from setup status";
}

async function loadSetupStatus() {
  try {
    state.setupStatus = await requestJson("/api/setup-status");
  } catch (error) {
    state.setupStatus = null;
    renderSetupStatus(error.message);
    return;
  }
  renderSetupStatus();
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

function sourceLabelFor(page) {
  const origin = String(page.candidate_origin || page.library_source || page.source_type || "").toLowerCase();
  if (origin === "ppt_library") return "真实库";
  if (origin === "fixture") return "Fixture";
  if (origin === "imported") return "Imported";
  if (page.source_type === "generated") return "Generated";
  return origin || "";
}

function sourceBadgeFor(page) {
  const label = sourceLabelFor(page);
  return label ? `<span class="source-badge source-${escapeHtml(String(page.candidate_origin || page.library_source || "unknown").toLowerCase())}">${escapeHtml(label)}</span>` : "";
}

function renderList() {
  if (!state.deck) return;
  els.list.innerHTML = "";
  state.deck.pages.forEach((page, index) => {
    const item = document.createElement("button");
    item.className = `page-card decision-${page.decision}`;
    item.dataset.active = index === state.selectedIndex ? "true" : "false";
    const sourceBadge = sourceBadgeFor(page);
    item.innerHTML = `
      <span class="page-no">${String(page.order).padStart(2, "0")}</span>
      <span>
        <strong>${escapeHtml(page.title || page.page_id)}</strong>
        <small>${sourceBadge}${escapeHtml(page.source_type)} · ${escapeHtml(page.decision)}${page.quality && page.quality.length ? ` · ${page.quality.length} quality finding(s)` : ""}</small>
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
  els.notes.value = page.notes || "";
  els.saveStatus.textContent = "";
  if (els.pageActionStatus) {
    els.pageActionStatus.textContent = `Current status: ${page.review_status || page.decision || "needs_review"}`;
  }

  els.details.innerHTML = detailRows({
    "Source": page.source_type,
    "Library source": sourceLabelFor(page),
    "Candidate origin": page.candidate_origin || "",
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
  renderPageFindingHints(page);
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

async function runPageAction(action, extra = {}) {
  const page = state.deck.pages[state.selectedIndex];
  if (!page) return;
  const buttons = [els.save, els.approvePage, els.rejectPage, els.requestEvidence, els.convertGenerate, els.lockSource].filter(Boolean);
  buttons.forEach((btn) => { btn.disabled = true; });
  els.saveStatus.textContent = "Applying...";
  if (els.pageActionStatus) els.pageActionStatus.textContent = "";
  try {
    const body = {
      action,
      actor: "user",
      note: els.notes.value,
      reason: els.notes.value,
      ...extra,
    };
    const result = await requestJson(`/api/page/${page.page_id}/review-action${runQuery()}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    await refreshAfterAction(page.page_id);
    els.saveStatus.textContent = result.message || `${action} applied`;
  } catch (error) {
    els.saveStatus.textContent = error.message;
    if (els.pageActionStatus) els.pageActionStatus.textContent = error.message;
  } finally {
    buttons.forEach((btn) => { btn.disabled = false; });
  }
}

async function refreshAfterAction(pageId) {
  const pagePayload = await requestJson(`/api/page/${encodeURIComponent(pageId)}${runQuery()}`);
  state.deck.pages[state.selectedIndex] = pagePayload;
  renderList();
  renderPage(pagePayload);
  await Promise.all([
    loadReviewSummary(),
    loadNextActions(),
    loadExportQueue(),
    loadMetrics(),
  ]);
}

async function saveDecision() {
  await runPageAction("add_note", { note: els.notes.value });
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
    els.createStatus.textContent = payload.pages != null
      ? `Draft ready: ${payload.pages} pages`
      : `Run created: ${payload.status || "request_ready"}`;
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

function clearCockpitData() {
  state.reviewSummary = null;
  state.claimCoverage = null;
  state.nextActions = null;
  state.externalResults = null;
  state.exportQueue = null;
  state.metrics = null;
}

async function loadCockpitData() {
  if (!state.currentRunId) {
    clearCockpitData();
    renderCockpitData();
    return;
  }
  await Promise.all([
    loadReviewSummary(),
    loadClaimCoverage(),
    loadNextActions(),
    loadExternalResults(),
    loadExportQueue(),
    loadMetrics(),
  ]);
}

function renderCockpitData() {
  renderReadiness();
  renderClaimCoverage();
  renderNextActions();
  renderExternalResults();
  renderExportQueue();
  renderMetrics();
}

async function loadReviewSummary() {
  try {
    state.reviewSummary = await requestJson(`/api/review-summary/${encodeURIComponent(state.currentRunId)}`);
    renderReadiness();
  } catch (error) {
    state.reviewSummary = null;
    renderReadiness(error.message);
  }
}

async function loadClaimCoverage() {
  try {
    state.claimCoverage = await requestJson(`/api/claim-coverage/${encodeURIComponent(state.currentRunId)}`);
    renderClaimCoverage();
  } catch (error) {
    state.claimCoverage = null;
    renderClaimCoverage(error.message);
  }
}

async function loadNextActions() {
  try {
    state.nextActions = await requestJson(`/api/next-actions/${encodeURIComponent(state.currentRunId)}`);
    renderNextActions();
  } catch (error) {
    state.nextActions = null;
    renderNextActions(error.message);
  }
}

async function loadExternalResults() {
  try {
    state.externalResults = await requestJson(`/api/external-results/${encodeURIComponent(state.currentRunId)}`);
    renderExternalResults();
  } catch (error) {
    state.externalResults = null;
    renderExternalResults(error.message);
  }
}

async function loadExportQueue() {
  try {
    state.exportQueue = await requestJson(`/api/export-queue/${encodeURIComponent(state.currentRunId)}?queue_type=client`);
    renderExportQueue();
  } catch (error) {
    state.exportQueue = null;
    renderExportQueue(error.message);
  }
}

async function loadMetrics() {
  try {
    state.metrics = await requestJson(`/api/run-metrics/${encodeURIComponent(state.currentRunId)}`);
    renderMetrics();
  } catch (error) {
    state.metrics = null;
    renderMetrics(error.message);
  }
}

function renderReadiness(errorMsg) {
  if (!els.readinessContent) return;
  if (errorMsg) {
    els.readinessContent.innerHTML = `<p class="muted">${escapeHtml(errorMsg)}</p>`;
    updateOverview();
    return;
  }
  if (!state.reviewSummary) {
    els.readinessContent.innerHTML = '<p class="muted">选择 run 后加载 readiness...</p>';
    updateOverview();
    return;
  }
  const readiness = state.reviewSummary.deck_readiness || {};
  const counts = state.reviewSummary.counts || {};
  const dimensions = ["narrative", "evidence", "generation", "quality", "export"]
    .map((key) => `<span class="status-pill ${statusClass(readiness[key])}">${escapeHtml(key)}: ${escapeHtml(readiness[key] || "-")}</span>`)
    .join("");
  els.readinessContent.innerHTML = `
    <div class="status-row">
      <span class="status-pill ${statusClass(readiness.overall)}">overall: ${escapeHtml(readiness.overall || "-")}</span>
      ${dimensions}
    </div>
    <dl class="compact-metrics">
      ${metricRow("Pages", counts.pages)}
      ${metricRow("Approved / Rejected / Review", `${valueOrDash(counts.approved)} / ${valueOrDash(counts.rejected)} / ${valueOrDash(counts.needs_review)}`)}
      ${metricRow("Reuse / Adapt / Generate / Placeholder", `${valueOrDash(counts.reuse)} / ${valueOrDash(counts.adapt)} / ${valueOrDash(counts.generate)} / ${valueOrDash(counts.manual_placeholder)}`)}
      ${metricRow("P0 / P1 / P2", `${valueOrDash(counts.p0)} / ${valueOrDash(counts.p1)} / ${valueOrDash(counts.p2)}`)}
    </dl>
  `;
  updateOverview();
}

function renderClaimCoverage(errorMsg) {
  if (!els.claimCoverageContent) return;
  if (errorMsg) {
    els.claimCoverageContent.innerHTML = `<p class="muted">${escapeHtml(errorMsg)}</p>`;
    return;
  }
  const claims = state.claimCoverage && Array.isArray(state.claimCoverage.claims) ? state.claimCoverage.claims : [];
  if (!claims.length) {
    els.claimCoverageContent.innerHTML = '<p class="muted">暂无 claim coverage 数据。</p>';
    return;
  }
  els.claimCoverageContent.innerHTML = claims.map((claim) => {
    const pages = Array.isArray(claim.page_refs) ? claim.page_refs : (claim.pages || claim.linked_pages || []);
    const evidence = Array.isArray(claim.evidence_refs) ? claim.evidence_refs : (claim.evidence || claim.supporting_evidence || []);
    const pageLinks = pages.length
      ? pages.map((pageId) => `<button class="inline-link claim-page-link" data-page-id="${escapeHtml(pageId)}">${escapeHtml(pageId)}</button>`).join(" ")
      : "-";
    return `<div class="claim-row ${statusClass(claim.status)}">
      <strong>${escapeHtml(claim.statement || claim.claim || claim.claim_id || "")}</strong>
      <small>${escapeHtml(claim.status || "-")} · pages: ${pageLinks} · evidence: ${escapeHtml(evidence.length ? evidence.join(", ") : "-")}</small>
      ${claim.status === "evidence_gap" ? '<small class="warn">建议 request evidence</small>' : ""}
    </div>`;
  }).join("");
  els.claimCoverageContent.querySelectorAll(".claim-page-link").forEach((btn) => {
    btn.addEventListener("click", () => jumpToPage(btn.dataset.pageId));
  });
}

function renderNextActions(errorMsg) {
  if (!els.nextActionsContent) return;
  if (errorMsg) {
    els.nextActionsContent.innerHTML = `<p class="muted">${escapeHtml(errorMsg)}</p>`;
    return;
  }
  const actions = state.nextActions && Array.isArray(state.nextActions.actions) ? state.nextActions.actions : [];
  if (!actions.length) {
    els.nextActionsContent.innerHTML = '<p class="muted">当前没有优先动作。</p>';
    return;
  }
  els.nextActionsContent.innerHTML = actions.map((action) => {
    const target = action.target || "";
    return `<div class="next-action ${severityClass(action.severity)}">
      <small>${escapeHtml(action.priority || "")} · ${escapeHtml(action.action_type || "")} · ${escapeHtml(action.severity || "")}</small>
      <strong>${escapeHtml(action.message || "")}</strong>
      ${target ? `<button class="inline-link action-target" data-target="${escapeHtml(target)}">${escapeHtml(target)}</button>` : ""}
    </div>`;
  }).join("");
  els.nextActionsContent.querySelectorAll(".action-target").forEach((btn) => {
    btn.addEventListener("click", () => jumpToPage(btn.dataset.target));
  });
}

function renderExternalResults(errorMsg) {
  if (!els.externalResultsContent) return;
  if (errorMsg) {
    els.externalResultsContent.innerHTML = `<p class="muted">${escapeHtml(errorMsg)}</p>`;
    return;
  }
  if (!state.externalResults) {
    els.externalResultsContent.innerHTML = '<p class="muted">选择 run 后加载 external results...</p>';
    return;
  }
  const advice = state.externalResults.narrative_advice;
  const reviews = Array.isArray(state.externalResults.external_reviews) ? state.externalResults.external_reviews : [];
  const generations = Array.isArray(state.externalResults.generation_results) ? state.externalResults.generation_results : [];
  const readiness = state.externalResults.runtime_readiness || {};
  const suite = readiness.suite_readiness || {};
  const importsSummary = readiness.imports_summary || {};
  const qualitySummary = readiness.quality_blocking_summary || {};
  const feedbackSummary = readiness.feedback_pending_summary || {};
  const reviewSummary = reviews.map((review) => {
    const findings = Array.isArray(review.findings) ? review.findings : [];
    const p0 = findings.filter((f) => f.severity === "P0").length;
    const p1 = findings.filter((f) => f.severity === "P1").length;
    const p2 = findings.filter((f) => f.severity === "P2").length;
    return `<div class="external-card">
      <strong>${escapeHtml(review.reviewer || review.gate || review._report_file || "external review")}</strong>
      <small>${escapeHtml(review.scope || "")} · P0/P1/P2: ${p0}/${p1}/${p2}</small>
    </div>`;
  }).join("");
  const generationSummary = generations.map((result) => `<div class="external-card ${result.status === "failed" ? "failed" : ""}">
    <strong>${escapeHtml(result.task_id || result.beat_id || result.tool || "generation result")}</strong>
    <small>${escapeHtml(result.tool || "")} · ${escapeHtml(result.status || "-")} · ${escapeHtml(result.preview_path || "")}</small>
  </div>`).join("");
  els.externalResultsContent.innerHTML = `
    <dl class="compact-metrics">
      ${metricRow("Suite readiness", suite.status || "-")}
      ${metricRow("Import log", importsSummary.total || 0)}
      ${metricRow("Blocking quality", qualitySummary.delivery_blocked ? `blocked · P0/P1 ${qualitySummary.p0 || 0}/${qualitySummary.p1 || 0}` : "clear")}
      ${metricRow("Pending feedback", feedbackSummary.pending || 0)}
      ${metricRow("Narrative advice", advice ? `${advice.advisor || "advisor"} · ${countItems(advice.page_recommendations)} page recs · ${countItems(advice.deck_level_risks)} risks` : "-")}
      ${metricRow("External reviews", reviews.length)}
      ${metricRow("Generation results", generations.length)}
    </dl>
    ${reviewSummary || ""}
    ${generationSummary || ""}
  `;
}

function renderExportQueue(errorMsg) {
  if (!els.exportQueueContent) return;
  if (errorMsg) {
    els.exportQueueContent.innerHTML = `<p class="muted">${escapeHtml(errorMsg)}</p>`;
    updateOverview();
    return;
  }
  if (!state.exportQueue) {
    els.exportQueueContent.innerHTML = '<p class="muted">选择 run 后加载 export queue...</p>';
    updateOverview();
    return;
  }
  const pages = Array.isArray(state.exportQueue.pages) ? state.exportQueue.pages : [];
  const blocked = Array.isArray(state.exportQueue.blocked_pages) ? state.exportQueue.blocked_pages : [];
  els.exportQueueContent.innerHTML = `
    <dl class="compact-metrics">
      ${metricRow("Ready pages", pages.length)}
      ${metricRow("Blocked pages", blocked.length)}
    </dl>
    ${pages.map((page) => exportQueueRow(page, false)).join("")}
    ${blocked.map((page) => exportQueueRow(page, true)).join("")}
  `;
  updateOverview();
}

function renderMetrics(errorMsg) {
  if (!els.metricsContent) return;
  if (errorMsg) {
    els.metricsContent.innerHTML = `<p class="muted">${escapeHtml(errorMsg)}</p>`;
    updateOverview();
    return;
  }
  if (!state.metrics) {
    els.metricsContent.innerHTML = '<p class="muted">选择 run 后加载 metrics...</p>';
    updateOverview();
    return;
  }
  const counts = state.metrics.counts || {};
  const durations = state.metrics.durations || {};
  els.metricsContent.innerHTML = `
    <dl class="compact-metrics">
      ${metricRow("Pages", counts.pages)}
      ${metricRow("Approved / Rejected / Review", `${valueOrDash(counts.approved)} / ${valueOrDash(counts.rejected)} / ${valueOrDash(counts.needs_review)}`)}
      ${metricRow("Reuse / Adapt / Generate / Placeholder", `${valueOrDash(counts.reuse)} / ${valueOrDash(counts.adapt)} / ${valueOrDash(counts.generate)} / ${valueOrDash(counts.manual_placeholder)}`)}
      ${metricRow("P0 / P1 / P2", `${valueOrDash(counts.p0)} / ${valueOrDash(counts.p1)} / ${valueOrDash(counts.p2)}`)}
      ${metricRow("Created to preview", `${valueOrDash(durations.created_to_preview_minutes)} min`)}
      ${metricRow("Preview to quality gate", `${valueOrDash(durations.preview_to_first_quality_gate_minutes)} min`)}
    </dl>
    <p class="muted">Lightweight metrics only; not a v1.0 benchmark conclusion.</p>
  `;
  updateOverview();
}

function renderPageFindingHints(page) {
  if (!els.pageActionStatus || !state.governance || !page) return;
  const findings = Array.isArray(state.governance.page_findings) ? state.governance.page_findings : [];
  const pageFindings = findings.filter((finding) => finding.page_id === page.page_id);
  const p01 = pageFindings.filter((finding) => finding.severity === "P0" || finding.severity === "P1");
  if (p01.length) {
    els.pageActionStatus.textContent = `${p01.length} P0/P1 finding(s) may block approval/export.`;
  }
}

function updateOverview() {
  const readiness = state.reviewSummary ? state.reviewSummary.deck_readiness || {} : {};
  const queue = state.exportQueue || {};
  const metrics = state.metrics || {};
  const counts = metrics.counts || {};
  if (els.overallReadiness) {
    els.overallReadiness.textContent = readiness.overall || "-";
    els.overallReadiness.className = statusClass(readiness.overall);
  }
  if (els.exportReadiness) {
    const blocked = Array.isArray(queue.blocked_pages) ? queue.blocked_pages.length : 0;
    const ready = Array.isArray(queue.pages) ? queue.pages.length : 0;
    els.exportReadiness.textContent = queue.run_id ? `${ready} ready / ${blocked} blocked` : "-";
  }
  if (els.metricsLine) {
    els.metricsLine.textContent = counts.pages != null
      ? `${counts.approved || 0} approved · ${counts.needs_review || 0} review · P1 ${counts.p1 || 0}`
      : "-";
  }
}

function jumpToPage(pageId) {
  if (!pageId || !state.deck) return;
  const index = state.deck.pages.findIndex((page) => page.page_id === pageId || page.beat_id === pageId);
  if (index >= 0) selectPage(index);
}

function metricRow(label, value) {
  return `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(valueOrDash(value))}</dd>`;
}

function valueOrDash(value) {
  return value === null || value === undefined || value === "" ? "-" : String(value);
}

function statusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized.includes("ready") || normalized === "pass" || normalized === "covered") return "status-ready";
  if (normalized.includes("block") || normalized === "fail" || normalized === "uncovered") return "status-blocked";
  if (normalized.includes("gap") || normalized.includes("review") || normalized === "warning") return "status-warning";
  return "status-muted";
}

function severityClass(severity) {
  const normalized = String(severity || "").toUpperCase();
  if (normalized === "P0") return "severity-p0";
  if (normalized === "P1") return "severity-p1";
  return "severity-p2";
}

function countItems(value) {
  return Array.isArray(value) ? value.length : 0;
}

function exportQueueRow(page, blocked) {
  return `<div class="queue-row ${blocked ? "blocked" : "ready"}">
    <strong>${escapeHtml(page.order || "")}. ${escapeHtml(page.title || page.page_id || "")}</strong>
    <small>${escapeHtml(page.source_type || "")} · ${escapeHtml(page.decision || "")}${page.quality_override_active ? " · override active" : ""}</small>
    ${blocked ? `<small class="warn">${escapeHtml(page.quality_block_reason || "")}</small>` : ""}
  </div>`;
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
els.approvePage.addEventListener("click", () => runPageAction("approve"));
els.rejectPage.addEventListener("click", () => runPageAction("reject"));
els.requestEvidence.addEventListener("click", () => runPageAction("request_evidence"));
els.convertGenerate.addEventListener("click", () => runPageAction("convert_to_generate"));
els.lockSource.addEventListener("click", () => runPageAction("lock_source"));
els.first.addEventListener("click", () => selectPage(0));
els.prev.addEventListener("click", () => selectPage(state.selectedIndex - 1));
els.next.addEventListener("click", () => selectPage(state.selectedIndex + 1));
els.last.addEventListener("click", () => selectPage(state.deck.pages.length - 1));
document.addEventListener("keydown", (event) => {
  if (event.key === "ArrowLeft") selectPage(state.selectedIndex - 1);
  if (event.key === "ArrowRight") selectPage(state.selectedIndex + 1);
});

(async function bootstrap() {
  await loadSetupStatus();
  await loadRuns();
  await loadDeck();
})();
