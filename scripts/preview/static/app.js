const state = {
  projects: [],
  workspace: null,
  pageDetail: null,
  activity: null,
  deliveryPreview: null,
  currentProjectId: new URLSearchParams(window.location.search).get("run") || "",
  currentPageId: new URLSearchParams(window.location.search).get("page") || "",
  filter: "all",
  viewMode: "page",
  loading: false,
};

const els = {
  workspaceTitle: document.querySelector("#workspace-title"),
  workspaceSubtitle: document.querySelector("#workspace-subtitle"),
  stageChip: document.querySelector("#stage-chip"),
  stageTitle: document.querySelector("#stage-title"),
  stageDetail: document.querySelector("#stage-detail"),
  nextStepTitle: document.querySelector("#next-step-title"),
  nextStepDetail: document.querySelector("#next-step-detail"),
  riskSummaryTitle: document.querySelector("#risk-summary-title"),
  riskSummaryDetail: document.querySelector("#risk-summary-detail"),
  metricPages: document.querySelector("#metric-pages"),
  metricApproved: document.querySelector("#metric-approved"),
  metricApprovals: document.querySelector("#metric-approvals"),
  metricExport: document.querySelector("#metric-export"),
  projectSwitcher: document.querySelector("#project-switcher"),
  projectSwitcherMeta: document.querySelector("#project-switcher-meta"),
  filterList: document.querySelector("#filter-list"),
  queueSummary: document.querySelector("#queue-summary"),
  pageList: document.querySelector("#page-list"),
  previewPanelLabel: document.querySelector("#preview-panel-label"),
  focusPageTitle: document.querySelector("#focus-page-title"),
  focusPageMeta: document.querySelector("#focus-page-meta"),
  criticalAlerts: document.querySelector("#critical-alerts"),
  previewStage: document.querySelector("#preview-stage"),
  previewNav: document.querySelector("#preview-nav"),
  currentLabel: document.querySelector("#current-label"),
  runReadiness: document.querySelector("#run-readiness"),
  readinessPill: document.querySelector("#readiness-pill"),
  claimSummaryChip: document.querySelector("#claim-summary-chip"),
  claimCoverage: document.querySelector("#claim-coverage"),
  activityCount: document.querySelector("#activity-count"),
  activityList: document.querySelector("#activity-list"),
  decisionPanelLabel: document.querySelector("#decision-panel-label"),
  decisionTitle: document.querySelector("#decision-title"),
  decisionSummary: document.querySelector("#decision-summary"),
  pageRoleContent: document.querySelector("#page-role-content"),
  pageSourceContent: document.querySelector("#page-source-content"),
  pageEvidenceContent: document.querySelector("#page-evidence-content"),
  pageRiskContent: document.querySelector("#page-risk-content"),
  approvalContent: document.querySelector("#approval-content"),
  decisionNote: document.querySelector("#decision-note"),
  actionFeedback: document.querySelector("#action-feedback"),
  approvePage: document.querySelector("#approve-page"),
  rejectPage: document.querySelector("#reject-page"),
  requestEvidence: document.querySelector("#request-evidence"),
  submitPageApproval: document.querySelector("#submit-page-approval"),
  saveNote: document.querySelector("#save-note"),
  submitRunApproval: document.querySelector("#submit-run-approval"),
  markDelivered: document.querySelector("#mark-delivered"),
  pageMode: document.querySelector("#page-mode"),
  deliveryMode: document.querySelector("#delivery-mode"),
  firstPage: document.querySelector("#first-page"),
  prevPage: document.querySelector("#prev-page"),
  nextPage: document.querySelector("#next-page"),
  lastPage: document.querySelector("#last-page"),
  openCreateModal: document.querySelector("#open-create-modal"),
  closeCreateModal: document.querySelector("#close-create-modal"),
  createRunModal: document.querySelector("#create-run-modal"),
  createRunForm: document.querySelector("#create-run-form"),
  createRunSubmit: document.querySelector("#create-run-submit"),
  brief: document.querySelector("#brief"),
  industry: document.querySelector("#industry"),
  targetPages: document.querySelector("#target-pages"),
  libraryMode: document.querySelector("#library-mode"),
  createStatus: document.querySelector("#create-status"),
};

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "请求失败");
  }
  return data;
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

function formatTime(value) {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatEvidencePolicy(policy) {
  const mapping = {
    at_least_one: "每个主论点至少补齐 1 条依据",
    required: "当前页必须补齐依据后才能推进",
    optional: "当前页建议补充依据",
  };
  return mapping[String(policy || "").trim()] || "当前未配置依据要求";
}

function formatClaimStatus(status) {
  const mapping = {
    covered: "已覆盖",
    blocked: "存在阻断",
    evidence_gap: "待补依据",
    review_required: "待复核",
    uncovered: "未覆盖",
  };
  return mapping[String(status || "").trim()] || "待确认";
}

function formatApprovalStatus(status) {
  const mapping = {
    pending: "待审批",
    approved: "已批准",
    rejected: "已驳回",
  };
  return mapping[String(status || "").trim()] || "待处理";
}

function formatActor(actor) {
  const mapping = {
    owner: "负责人",
    user: "当前处理人",
    system: "系统",
    alice: "主审人",
    bob: "审批人",
  };
  return mapping[String(actor || "").trim()] || String(actor || "未记录");
}

function formatActionType(actionType) {
  const mapping = {
    fix_quality_finding: "处理质量问题",
    fix_evidence_gap: "补齐关键依据",
    resolve_placeholder: "补齐负责人判断",
    rerun_generation: "重新生成内容",
    generate_preview: "补齐页面预览",
    fix_claim_coverage: "补强论点支撑",
    next_action: "下一步",
  };
  return mapping[String(actionType || "").trim()] || "下一步";
}

function currentWorkspace() {
  return state.workspace || {};
}

function currentStage() {
  return currentWorkspace().project_stage || currentWorkspace().stage || {};
}

function currentStageLabel() {
  return String(currentStage().label || "");
}

function isStageWorkspace() {
  return ["待准备", "生成中"].includes(currentStageLabel());
}

function isDeliveryStage() {
  return ["可交付", "已交付"].includes(currentStageLabel());
}

function currentPages() {
  return currentWorkspace().queue?.pages || [];
}

function filteredPages() {
  const pages = currentPages();
  switch (state.filter) {
    case "blocked":
      return pages.filter((page) => page.blocking_count > 0);
    case "needs_review":
      return pages.filter((page) => page.review_status === "needs_review");
    case "needs_evidence":
      return pages.filter((page) => page.review_status === "needs_evidence");
    case "approved":
      return pages.filter((page) => page.review_status === "approved");
    case "rejected":
      return pages.filter((page) => page.review_status === "rejected");
    default:
      return pages;
  }
}

function currentPageCard() {
  return currentPages().find((page) => page.page_id === state.currentPageId) || null;
}

function previewUrlWithProject(url) {
  if (!url) return "";
  const target = new URL(url, window.location.origin);
  if (state.currentProjectId) {
    target.searchParams.set("run", state.currentProjectId);
  }
  target.searchParams.set("t", String(Date.now()));
  return `${target.pathname}${target.search}`;
}

function updateLocation() {
  const url = new URL(window.location.href);
  if (state.currentProjectId) {
    url.searchParams.set("run", state.currentProjectId);
  } else {
    url.searchParams.delete("run");
  }
  if (state.currentPageId) {
    url.searchParams.set("page", state.currentPageId);
  } else {
    url.searchParams.delete("page");
  }
  window.history.replaceState({}, "", url);
}

function setButtonState(button, enabled, label) {
  if (!button) return;
  button.disabled = !enabled;
  button.setAttribute("aria-disabled", enabled ? "false" : "true");
  if (label) {
    button.title = label;
  } else {
    button.removeAttribute("title");
  }
}

function setFeedback(message, tone = "") {
  els.actionFeedback.textContent = message || "";
  els.actionFeedback.dataset.tone = tone;
}

function setCreateModal(open) {
  els.createRunModal.classList.toggle("hidden", !open);
  document.body.classList.toggle("modal-open", open);
}

function setPreviewNavVisible(visible) {
  els.previewNav.hidden = !visible;
}

function renderProjectSwitcher() {
  if (!els.projectSwitcher) return;
  els.projectSwitcher.innerHTML = "";
  els.projectSwitcherMeta.textContent = `${state.projects.length} 个方案项目`;
  if (!state.projects.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "暂无方案项目";
    els.projectSwitcher.appendChild(option);
    els.projectSwitcher.disabled = true;
    return;
  }

  els.projectSwitcher.disabled = false;
  state.projects.forEach((project) => {
    const option = document.createElement("option");
    option.value = project.run_id;
    const stageLabel = project.stage_label ? ` · ${project.stage_label}` : "";
    option.textContent = `${project.title || "未命名方案项目"}${stageLabel}`;
    option.selected = project.run_id === state.currentProjectId;
    els.projectSwitcher.appendChild(option);
  });
}

function renderFilters() {
  els.filterList.innerHTML = "";
  const filters = currentWorkspace().queue?.filters || [];
  filters.forEach((filter) => {
    const button = document.createElement("button");
    button.className = "filter-chip";
    button.dataset.active = filter.id === state.filter ? "true" : "false";
    button.textContent = `${filter.label} ${filter.count}`;
    button.addEventListener("click", () => {
      state.filter = filter.id;
      renderFilters();
      renderPageList();
    });
    els.filterList.appendChild(button);
  });
}

function renderPageList() {
  els.pageList.innerHTML = "";
  const pages = filteredPages();
  const metrics = currentWorkspace().header_metrics;
  if (metrics) {
    els.queueSummary.textContent = `${metrics.pages_total} 页 / ${metrics.pages_approved} 已批准 / ${metrics.pages_waiting} 待处理 / ${metrics.p0 + metrics.p1} 项高优先级风险`;
  } else {
    els.queueSummary.textContent = "当前还没有页面队列。";
  }

  if (!pages.length) {
    els.pageList.innerHTML = '<div class="empty-inline">当前筛选条件下没有页面。</div>';
    return;
  }

  pages.forEach((page) => {
    const item = document.createElement("button");
    item.className = "page-card";
    item.dataset.active = page.page_id === state.currentPageId ? "true" : "false";
    item.innerHTML = `
      <div class="page-card-top">
        <span class="page-order mono">${String(page.order).padStart(2, "0")}</span>
        <span class="status-pill ${page.status_tone}">${escapeHtml(page.status_label)}</span>
      </div>
      <strong>${escapeHtml(page.title)}</strong>
      <small>${escapeHtml(page.narrative_role || "未标注页面职责")}</small>
      <div class="page-card-meta">
        <span>${escapeHtml(page.source_label)}</span>
        <span class="mono">R${page.risk_count}</span>
        <span>${page.approval_state === "pending" ? "待审批" : "无审批"}</span>
      </div>
    `;
    item.addEventListener("click", async () => {
      state.viewMode = "page";
      await selectPage(page.page_id);
    });
    els.pageList.appendChild(item);
  });
}

function renderHeader() {
  const workspace = currentWorkspace();
  if (!workspace.project_id) {
    els.workspaceTitle.textContent = "请选择或创建一个方案项目";
    els.workspaceSubtitle.textContent = "顶部可切换已有方案项目，或新建一个项目进入工作台。";
    els.stageChip.textContent = "待准备";
    els.stageChip.className = "stage-chip muted";
    els.stageTitle.textContent = "-";
    els.stageDetail.textContent = "-";
    els.nextStepTitle.textContent = "-";
    els.nextStepDetail.textContent = "-";
    els.riskSummaryTitle.textContent = "-";
    els.riskSummaryDetail.textContent = "-";
    els.metricPages.textContent = "-";
    els.metricApproved.textContent = "-";
    els.metricApprovals.textContent = "-";
    els.metricExport.textContent = "-";
    return;
  }

  const stage = currentStage();
  const health = workspace.health || {};
  const metrics = workspace.header_metrics || {};
  els.workspaceTitle.textContent = workspace.project_title || workspace.title || "未命名方案项目";
  els.workspaceSubtitle.textContent = `当前阶段：${stage.label} · 更新于 ${formatTime(workspace.updated_at)}`;
  els.stageChip.textContent = stage.label || "待准备";
  els.stageChip.className = `stage-chip ${stage.tone || "muted"}`;
  els.stageTitle.textContent = stage.definition || "-";
  els.stageDetail.textContent = stage.blocking_reason || "-";
  els.nextStepTitle.textContent = stage.next_step || "-";
  els.nextStepDetail.textContent = `${stage.owner || "未指定"} · 目标结果：${stage.expected_result || "未定义"}`;
  els.riskSummaryTitle.textContent = (health.blocking_reasons || []).length ? `${health.blocking_reasons.length} 项主风险` : "当前无主阻断";
  els.riskSummaryDetail.textContent = (health.blocking_reasons || [])[0] || "当前已具备继续推进条件。";
  els.metricPages.textContent = String(metrics.pages_total ?? "-");
  els.metricApproved.textContent = String(metrics.pages_approved ?? "-");
  els.metricApprovals.textContent = String(metrics.pending_approvals ?? "-");
  els.metricExport.textContent = `${metrics.export_ready ?? 0} / ${metrics.export_blocked ?? 0}`;
}

function renderCriticalAlerts() {
  const alerts = [];
  const workspace = currentWorkspace();
  if (state.viewMode === "page" && state.pageDetail?.summary?.critical_alerts?.length) {
    alerts.push(...state.pageDetail.summary.critical_alerts);
  } else if (state.viewMode === "delivery" && state.deliveryPreview) {
    alerts.push({
      tone: state.deliveryPreview.artifact_ready ? "success" : "warning",
      label: "交付预览",
      detail: state.deliveryPreview.summary,
    });
  } else if (workspace.run_summary?.main_risks?.length) {
    workspace.run_summary.main_risks.slice(0, 3).forEach((risk) => {
      alerts.push({
        tone: risk.severity === "P0" ? "danger" : "warning",
        label: risk.severity,
        detail: `${risk.page_title} · ${risk.summary}`,
      });
    });
  } else if (workspace.run_summary?.next_actions?.length) {
    workspace.run_summary.next_actions.slice(0, 3).forEach((item) => {
      alerts.push({
        tone: item.severity === "P0" ? "danger" : "warning",
        label: formatActionType(item.action_type),
        detail: item.message || "",
      });
    });
  }

  if (!alerts.length) {
    els.criticalAlerts.innerHTML = '<div class="alert-card success">当前没有新的首屏阻断项。</div>';
    return;
  }

  els.criticalAlerts.innerHTML = alerts.map((alert) => `
    <div class="alert-card ${escapeHtml(alert.tone || "muted")}">
      <strong>${escapeHtml(alert.label || "提示")}</strong>
      <span>${escapeHtml(alert.detail || "")}</span>
    </div>
  `).join("");
}

function renderStageWorkspace() {
  const workspace = currentWorkspace();
  const stage = currentStage();
  const delivery = workspace.run_summary?.delivery_preview || {};
  const actions = workspace.run_summary?.next_actions || [];
  const blockers = workspace.health?.blocking_reasons || [];

  els.previewPanelLabel.textContent = "阶段工作区";
  els.focusPageTitle.textContent = `${stage.label || "待准备"} · ${stage.definition || "当前仍在准备阶段"}`;
  els.focusPageMeta.textContent = stage.blocking_reason || "系统正在整理进入可处理状态所需的前置内容。";
  els.currentLabel.textContent = "阶段工作区";
  setPreviewNavVisible(false);

  const blockerCards = (blockers.length ? blockers : [stage.blocking_reason || "当前还没有明确阻塞项。"]).slice(0, 3).map((item) => `
    <div class="stage-card ${escapeHtml(stage.tone || "muted")}">
      <span class="panel-title">当前阻塞</span>
      <strong>${escapeHtml(item)}</strong>
      <p>${escapeHtml(stage.next_step || "继续推进当前阶段。")}</p>
    </div>
  `).join("");
  const actionCards = actions.slice(0, 3).map((item) => `
    <div class="stage-check-item">
      <strong>${escapeHtml(formatActionType(item.action_type))}</strong>
      <p>${escapeHtml(item.message || "继续推进当前阶段。")}</p>
    </div>
  `).join("");

  els.previewStage.innerHTML = `
    <div class="stage-workspace">
      <div class="stage-workspace-top">
        ${blockerCards}
        <div class="stage-card ${escapeHtml(delivery.artifact_ready ? "success" : "warning")}">
          <span class="panel-title">交付预览</span>
          <strong>${escapeHtml(delivery.summary || "当前还没有交付级预览。")}</strong>
          <p>${escapeHtml(delivery.detail || "进入可交付阶段后可查看最终交付预览。")}</p>
        </div>
        <div class="stage-card">
          <span class="panel-title">责任对象</span>
          <strong>${escapeHtml(stage.owner || "未指定")}</strong>
          <p>${escapeHtml(`目标结果：${stage.expected_result || "形成可处理页面与交付判断"}`)}</p>
        </div>
      </div>
      <div class="stage-workspace-body">
        <section class="stage-checklist">
          <span class="panel-title">当前要推进的事情</span>
          <h3>${escapeHtml(stage.next_step || "继续推进当前阶段")}</h3>
          <div class="stage-check-grid">
            ${actionCards || '<div class="stage-check-item"><strong>等待下一步</strong><p>当前没有额外动作建议。</p></div>'}
          </div>
        </section>
      </div>
    </div>
  `;
}

function renderPagePreview() {
  const page = currentPageCard();
  if (!currentWorkspace().project_id) {
    els.previewPanelLabel.textContent = "方案项目工作台";
    els.focusPageTitle.textContent = "尚未加载方案项目";
    els.focusPageMeta.textContent = "顶部切换方案项目，或新建项目进入处理。";
    els.currentLabel.textContent = "-";
    setPreviewNavVisible(false);
    els.previewStage.innerHTML = `
      <div class="empty-state">
        <h3>等待选择方案项目</h3>
        <p>先从顶部切换项目，或点击右上角新建项目。</p>
      </div>
    `;
    return;
  }

  const focusPage = page || currentPages()[0];
  if (!focusPage) {
    els.previewPanelLabel.textContent = "页面预览";
    els.focusPageTitle.textContent = "当前还没有页面";
    els.focusPageMeta.textContent = "这个方案项目还没有进入可逐页处理状态。";
    els.currentLabel.textContent = "-";
    setPreviewNavVisible(false);
    els.previewStage.innerHTML = `
      <div class="empty-state">
        <h3>当前没有页面</h3>
        <p>先补齐页面生成、预览构建或前置资料，再回到工作台处理。</p>
      </div>
    `;
    return;
  }

  els.previewPanelLabel.textContent = "页面预览";
  els.focusPageTitle.textContent = focusPage.title;
  els.focusPageMeta.textContent = `${focusPage.order} / ${currentPages().length} · ${focusPage.narrative_role || "未标注页面职责"} · ${focusPage.source_decision_label}`;
  els.currentLabel.textContent = `第 ${String(focusPage.order).padStart(2, "0")} 页`;
  setPreviewNavVisible(true);

  if (focusPage.has_preview) {
    els.previewStage.innerHTML = `<img src="${previewUrlWithProject(focusPage.preview_url)}" alt="${escapeHtml(focusPage.title)}">`;
    return;
  }

  els.previewStage.innerHTML = `
    <div class="empty-state">
      <h3>预览暂不可用</h3>
      <p>当前页缺少可展示的预览文件，建议先补齐预览再继续审阅。</p>
    </div>
  `;
}

function renderDeliveryPreview() {
  const delivery = state.deliveryPreview || currentWorkspace().run_summary?.delivery_preview || {};
  els.previewPanelLabel.textContent = "交付预览";
  els.focusPageTitle.textContent = "交付级预览";
  els.focusPageMeta.textContent = delivery.summary || "当前正在检查交付级预览产物。";
  els.currentLabel.textContent = "交付预览";
  setPreviewNavVisible(false);

  if (!delivery.artifact_ready) {
    els.previewStage.innerHTML = `
      <div class="empty-state">
        <h3>${escapeHtml(delivery.summary || "当前还没有交付级预览")}</h3>
        <p>${escapeHtml(delivery.detail || "完成交付渲染后，这里会展示最终交付预览。")}</p>
      </div>
    `;
    return;
  }

  els.previewStage.innerHTML = `
    <div class="delivery-preview-layout">
      <div class="delivery-preview-meta">
        <div class="stage-card success">
          <span class="panel-title">预览状态</span>
          <strong>${escapeHtml(delivery.summary || "交付级预览已就绪")}</strong>
          <p>${escapeHtml(delivery.detail || "")}</p>
        </div>
        <div class="stage-card">
          <span class="panel-title">渲染时间</span>
          <strong>${escapeHtml(formatTime(delivery.created_at))}</strong>
          <p>${escapeHtml(`渲染状态：${delivery.render_status || "未记录"}`)}</p>
        </div>
        <div class="stage-card">
          <span class="panel-title">交付记录</span>
          <strong>${delivery.delivered ? "已记录交付" : "尚未记录交付"}</strong>
          <p>${escapeHtml(delivery.delivered ? formatTime(delivery.delivered_at) : "可在右上角完成交付确认。")}</p>
        </div>
      </div>
      <div class="delivery-preview-frame-wrap">
        <iframe class="delivery-preview-frame" src="${escapeHtml(delivery.artifact_url)}" title="交付级预览"></iframe>
      </div>
    </div>
  `;
}

function renderPreview() {
  const workspace = currentWorkspace();
  const showDeliveryMode = isDeliveryStage();
  if (els.deliveryMode) {
    els.deliveryMode.hidden = !showDeliveryMode;
  }
  if (!showDeliveryMode && state.viewMode === "delivery") {
    state.viewMode = "page";
  }

  if (isStageWorkspace()) {
    state.viewMode = "page";
    renderStageWorkspace();
    return;
  }

  if (state.viewMode === "delivery" && showDeliveryMode) {
    renderDeliveryPreview();
    return;
  }

  renderPagePreview();
}

function renderReadiness() {
  const workspace = currentWorkspace();
  if (!workspace.project_id) {
    els.readinessPill.textContent = "-";
    els.readinessPill.className = "pill muted";
    els.runReadiness.innerHTML = '<div class="empty-inline">当前还没有方案项目数据。</div>';
    return;
  }

  const stage = currentStage();
  const health = workspace.health || {};
  const summary = workspace.run_summary || {};
  const deliveryPreview = summary.delivery_preview || {};
  els.readinessPill.textContent = stage.label || "-";
  els.readinessPill.className = `pill ${stage.tone || "muted"}`;

  const deliveryCard = deliveryPreview.artifact_ready
    ? `<div class="stack-card success"><strong>交付预览已就绪</strong><p>${escapeHtml(deliveryPreview.summary || "")}</p><small>${escapeHtml(formatTime(deliveryPreview.created_at))}</small></div>`
    : `<div class="stack-card warning"><strong>交付预览未就绪</strong><p>${escapeHtml(deliveryPreview.detail || "当前还没有交付级预览产物。")}</p></div>`;
  const blocks = (health.blocking_reasons || []).length
    ? health.blocking_reasons.map((item) => `<div class="stack-card warning">${escapeHtml(item)}</div>`).join("")
    : '<div class="stack-card success">当前没有明确阻断，已具备继续推进条件。</div>';
  const nextActions = (summary.next_actions || []).slice(0, 3).map((item) => `
    <div class="stack-card">
      <strong>${escapeHtml(formatActionType(item.action_type))}</strong>
      <p>${escapeHtml(item.message || "")}</p>
    </div>
  `).join("");
  const delivery = summary.delivery?.delivered
    ? `<div class="stack-card success">已记录交付 · ${escapeHtml(formatTime(summary.delivery.delivered_at))}</div>`
    : `<div class="stack-card">尚未记录交付 · 当前可交付 ${summary.export_queue?.ready ?? 0} 页，阻断 ${summary.export_queue?.blocked ?? 0} 页</div>`;
  els.runReadiness.innerHTML = `${deliveryCard}${delivery}${blocks}${nextActions}`;
}

function renderClaimCoverage() {
  const workspace = currentWorkspace();
  if (!workspace.project_id) {
    els.claimSummaryChip.textContent = "-";
    els.claimSummaryChip.className = "pill muted";
    els.claimCoverage.innerHTML = '<div class="empty-inline">当前还没有论点覆盖数据。</div>';
    return;
  }

  const coverage = workspace.run_summary?.claim_coverage || {};
  els.claimSummaryChip.textContent = `${coverage.covered || 0}/${coverage.total || 0} 已覆盖`;
  els.claimSummaryChip.className = `pill ${(coverage.evidence_gap || coverage.blocked) ? "warning" : "success"}`;
  const cards = (coverage.claims || []).slice(0, 6).map((claim) => `
    <div class="stack-card ${escapeHtml(claim.status === "covered" ? "success" : claim.status === "blocked" ? "danger" : "warning")}">
      <strong>${escapeHtml(claim.statement || "论点")}</strong>
      <p>${escapeHtml(claim.statement || "")}</p>
      <small>${escapeHtml((claim.pages || []).join(", ") || "未绑定页面")} · ${escapeHtml(formatClaimStatus(claim.status))}</small>
    </div>
  `).join("");
  els.claimCoverage.innerHTML = cards || '<div class="empty-inline">当前还没有论点数据。</div>';
}

function renderActivity() {
  const items = state.activity?.items || [];
  els.activityCount.textContent = String(items.length);
  if (!items.length) {
    els.activityList.innerHTML = '<div class="empty-inline">当前还没有处理记录。</div>';
    return;
  }

  els.activityList.innerHTML = items.slice(0, 12).map((item) => `
    <article class="activity-item ${escapeHtml(item.severity || "info")}">
      <div class="activity-top">
        <strong>${escapeHtml(item.title)}</strong>
        <span class="mono">${escapeHtml(formatTime(item.timestamp))}</span>
      </div>
      <p>${escapeHtml(item.detail || "无补充说明")}</p>
    </article>
  `).join("");
}

function renderRunLevelDecisionRail() {
  const workspace = currentWorkspace();
  const stage = currentStage();
  const deliveryPreview = workspace.run_summary?.delivery_preview || {};
  const approvals = workspace.run_summary?.approvals || [];

  els.decisionPanelLabel.textContent = "当前推进";
  els.decisionTitle.textContent = workspace.project_title || workspace.title || "等待选择方案项目";
  els.decisionSummary.textContent = stage.blocking_reason || "当前还没有页面进入可逐页处理状态。";
  els.pageRoleContent.innerHTML = `
    <div class="stack-card">
      <strong>${escapeHtml(stage.label || "待准备")}</strong>
      <p>${escapeHtml(stage.definition || "当前仍在准备阶段。")}</p>
      <small>${escapeHtml(stage.owner || "未指定责任对象")}</small>
    </div>
  `;
  els.pageSourceContent.innerHTML = `
    <div class="stack-card">
      <strong>交付链路</strong>
      <p>${escapeHtml(deliveryPreview.summary || "当前还没有交付级预览产物。")}</p>
      <small>${escapeHtml(deliveryPreview.detail || "进入可交付阶段后可查看交付预览。")}</small>
    </div>
  `;
  els.pageEvidenceContent.innerHTML = `
    <div class="stack-card">
      <strong>下一步</strong>
      <p>${escapeHtml(stage.next_step || "继续推进当前阶段。")}</p>
      <small>${escapeHtml(`目标结果：${stage.expected_result || "形成可处理页面与交付判断"}`)}</small>
    </div>
  `;
  els.pageRiskContent.innerHTML = (workspace.health?.blocking_reasons || []).length
    ? workspace.health.blocking_reasons.map((item) => `<div class="stack-card warning"><strong>阻断</strong><p>${escapeHtml(item)}</p></div>`).join("")
    : '<div class="stack-card success">当前没有显式阻断项。</div>';
  els.approvalContent.innerHTML = approvals.length
    ? approvals.slice(0, 4).map((task) => `
      <div class="stack-card ${escapeHtml(task.status === "approved" ? "success" : task.status === "rejected" ? "danger" : "warning")}">
        <strong>${escapeHtml(task.subject || "审批任务")}</strong>
        <p>${escapeHtml(task.reason || "无审批原因")}</p>
        <small>${escapeHtml(formatApprovalStatus(task.status))} · ${escapeHtml(formatActor(task.submitted_by))}</small>
      </div>
    `).join("")
    : '<div class="empty-inline">当前方案项目还没有审批任务。</div>';
}

function renderPageDecisionRail() {
  const { hero, summary, evidence, quality, approvals } = state.pageDetail;
  els.decisionPanelLabel.textContent = "当前页面处理";
  els.decisionTitle.textContent = hero.title;
  els.decisionSummary.textContent = `${hero.review_label} · ${hero.source_label} · ${hero.source_decision_label}`;
  els.decisionNote.value = state.pageDetail.notes || "";

  els.pageRoleContent.innerHTML = `
    <div class="stack-card">
      <strong>${escapeHtml(hero.role || "未标注页面职责")}</strong>
      <p>${escapeHtml(summary.core_claim || "当前页还没有明确主论点。")}</p>
      <small>${escapeHtml(formatEvidencePolicy(summary.evidence_policy))}</small>
    </div>
  `;

  els.pageSourceContent.innerHTML = `
    <div class="stack-card">
      <strong>${escapeHtml(hero.source_label)}</strong>
      <p>${escapeHtml(summary.source_reason || "当前没有来源决策说明。")}</p>
      <small>${hero.confidence != null ? `置信度 ${hero.confidence}` : "当前没有置信度分数"}</small>
    </div>
  `;

  const evidenceCards = (evidence.claims || []).length
    ? evidence.claims.map((claim) => `
      <div class="stack-card ${claim.evidence_count ? "success" : "warning"}">
        <strong>${escapeHtml(claim.statement || claim.claim_id)}</strong>
        <p>${claim.evidence_count ? `${claim.evidence_count} 条证据已关联` : "当前没有关联证据"}</p>
        <small>${escapeHtml((claim.evidence || []).map((item) => item.title).join(" · ") || "待补证据")}</small>
      </div>
    `).join("")
    : '<div class="empty-inline">当前页还没有论点与证据数据。</div>';
  els.pageEvidenceContent.innerHTML = evidenceCards;

  const riskCards = (quality.risks || []).length
    ? quality.risks.map((risk) => `
      <div class="stack-card ${risk.severity === "P0" ? "danger" : risk.severity === "P1" ? "warning" : ""}">
        <strong>${escapeHtml(risk.severity)}</strong>
        <p>${escapeHtml(risk.summary || "")}</p>
        <small>${escapeHtml(risk.repair_instruction || "当前没有修复说明")}</small>
      </div>
    `).join("")
    : '<div class="stack-card success">当前页没有显式质量阻断。</div>';
  els.pageRiskContent.innerHTML = riskCards;

  const approvalCards = (approvals.tasks || []).length
    ? approvals.tasks.map((task) => `
      <div class="stack-card ${escapeHtml(task.status === "approved" ? "success" : task.status === "rejected" ? "danger" : "warning")}">
        <strong>${escapeHtml(task.subject || "审批任务")}</strong>
        <p>${escapeHtml(task.reason || "无审批原因")}</p>
        <small>${escapeHtml(formatApprovalStatus(task.status))} · ${escapeHtml(formatActor(task.submitted_by))} · ${escapeHtml(formatTime(task.submitted_at))}</small>
        ${task.status === "pending" ? `
          <div class="inline-actions">
            <button class="btn btn-small" data-approval-action="approve" data-scope="${escapeHtml(task.scope_type || "run")}" data-approval-id="${escapeHtml(task.approval_id)}">批准</button>
            <button class="btn btn-small" data-approval-action="reject" data-scope="${escapeHtml(task.scope_type || "run")}" data-approval-id="${escapeHtml(task.approval_id)}">驳回</button>
          </div>
        ` : ""}
      </div>
    `).join("")
    : '<div class="empty-inline">当前页和当前方案项目还没有审批任务。</div>';
  els.approvalContent.innerHTML = approvalCards;

  els.approvalContent.querySelectorAll("[data-approval-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.approvalAction === "approve" ? "approve_approval" : "reject_approval";
      const scope = button.dataset.scope || "run";
      const approvalId = button.dataset.approvalId || "";
      if (!approvalId) return;
      if (scope === "page") {
        await runPageAction(action, { approval_id: approvalId });
      } else {
        await runRunAction(action, { approval_id: approvalId });
      }
    });
  });
}

function renderDecisionRail() {
  const workspace = currentWorkspace();
  if (!workspace.project_id) {
    els.decisionPanelLabel.textContent = "当前推进";
    els.decisionTitle.textContent = "等待选择页面";
    els.decisionSummary.textContent = "先选择一个方案项目，再进入页面处理。";
    els.pageRoleContent.innerHTML = '<div class="empty-inline">暂无内容</div>';
    els.pageSourceContent.innerHTML = '<div class="empty-inline">暂无内容</div>';
    els.pageEvidenceContent.innerHTML = '<div class="empty-inline">暂无内容</div>';
    els.pageRiskContent.innerHTML = '<div class="empty-inline">暂无内容</div>';
    els.approvalContent.innerHTML = '<div class="empty-inline">暂无内容</div>';
    return;
  }

  if (!state.pageDetail || isStageWorkspace() || state.viewMode === "delivery") {
    renderRunLevelDecisionRail();
    return;
  }

  renderPageDecisionRail();
}

function syncModeButtons() {
  els.pageMode.classList.toggle("active", state.viewMode === "page");
  els.deliveryMode.classList.toggle("active", state.viewMode === "delivery");
}

function renderActionStates() {
  const stageLabel = currentStageLabel();
  const page = currentPageCard();
  const hasPage = Boolean(page && state.pageDetail && !isStageWorkspace() && state.viewMode !== "delivery");
  const pageReviewStatus = page?.review_status || "";
  const deliveryRecorded = Boolean(currentWorkspace().run_summary?.delivery?.delivered);

  const canSubmitRunApproval = ["可交付", "待审批"].includes(stageLabel) && Boolean(state.currentProjectId) && !deliveryRecorded;
  const canMarkDelivered = ["可交付", "已交付"].includes(stageLabel) && Boolean(state.currentProjectId);
  const canReviewPage = hasPage && ["待审阅", "待补证据", "待审批", "可交付", "已交付"].includes(stageLabel);
  const canRequestEvidence = hasPage && ["待审阅", "待补证据"].includes(stageLabel);
  const canEscalatePageApproval = hasPage && ["待审阅", "待补证据", "可交付", "待审批"].includes(stageLabel);
  const canSaveNote = Boolean(state.currentProjectId) && hasPage;

  els.submitRunApproval.hidden = !canSubmitRunApproval;
  els.markDelivered.hidden = !canMarkDelivered;

  setButtonState(
    els.submitRunApproval,
    canSubmitRunApproval,
    canSubmitRunApproval ? "" : "当前阶段还不适合发起方案项目审批。"
  );
  setButtonState(
    els.markDelivered,
    canMarkDelivered,
    canMarkDelivered ? "" : "当前还没有进入可交付阶段。"
  );
  els.markDelivered.textContent = deliveryRecorded ? "已记录交付" : "确认交付";

  setButtonState(
    els.approvePage,
    canReviewPage && pageReviewStatus !== "approved",
    hasPage ? "当前页还不能执行批准动作。" : "请先选择页面。"
  );
  setButtonState(
    els.rejectPage,
    canReviewPage && pageReviewStatus !== "rejected",
    hasPage ? "当前页还不能执行驳回动作。" : "请先选择页面。"
  );
  setButtonState(
    els.requestEvidence,
    canRequestEvidence,
    hasPage ? "当前页还不适合发起补证据动作。" : "请先选择页面。"
  );
  setButtonState(
    els.submitPageApproval,
    canEscalatePageApproval,
    hasPage ? "当前页还不适合升级审批。" : "请先选择页面。"
  );
  setButtonState(
    els.saveNote,
    canSaveNote,
    canSaveNote ? "" : "请先选择页面后再记录备注。"
  );
}

function renderAll() {
  renderHeader();
  renderProjectSwitcher();
  renderFilters();
  renderPageList();
  renderCriticalAlerts();
  renderPreview();
  renderReadiness();
  renderClaimCoverage();
  renderActivity();
  renderDecisionRail();
  renderActionStates();
  syncModeButtons();
}

async function loadProjects() {
  const payload = await requestJson("/api/runs");
  state.projects = payload.runs || [];
  if (!state.currentProjectId && state.projects.length) {
    state.currentProjectId = state.projects[0].run_id;
  }
}

async function loadDeliveryPreview({ silent = false } = {}) {
  if (!state.currentProjectId) {
    state.deliveryPreview = null;
    if (!silent) renderAll();
    return;
  }

  try {
    state.deliveryPreview = await requestJson(`/api/workspace/${encodeURIComponent(state.currentProjectId)}/delivery-preview`);
  } catch (error) {
    state.deliveryPreview = {
      artifact_ready: false,
      summary: "交付预览暂不可用。",
      detail: error.message,
      render_status: "failed",
    };
  }

  if (!silent) renderAll();
}

async function loadPageDetail() {
  if (!state.currentProjectId || !state.currentPageId) {
    state.pageDetail = null;
    renderAll();
    return;
  }

  try {
    state.pageDetail = await requestJson(
      `/api/workspace/${encodeURIComponent(state.currentProjectId)}/page/${encodeURIComponent(state.currentPageId)}`
    );
  } catch (error) {
    state.pageDetail = null;
    setFeedback(error.message, "danger");
  }
  renderAll();
}

async function loadWorkspace() {
  if (!state.currentProjectId) {
    state.workspace = null;
    state.pageDetail = null;
    state.activity = null;
    state.deliveryPreview = null;
    renderAll();
    return;
  }

  state.loading = true;
  try {
    const [workspace, activity] = await Promise.all([
      requestJson(`/api/workspace/${encodeURIComponent(state.currentProjectId)}`),
      requestJson(`/api/workspace/${encodeURIComponent(state.currentProjectId)}/activity`),
    ]);
    state.workspace = workspace;
    state.activity = activity;
    state.deliveryPreview = workspace.run_summary?.delivery_preview || null;
    const pageIds = currentPages().map((page) => page.page_id);
    if (!state.currentPageId || !pageIds.includes(state.currentPageId)) {
      state.currentPageId = workspace.focus_page_id || pageIds[0] || "";
    }
    updateLocation();
    await loadPageDetail();
    if (isDeliveryStage()) {
      await loadDeliveryPreview({ silent: true });
    }
  } catch (error) {
    state.workspace = null;
    state.pageDetail = null;
    state.activity = null;
    state.deliveryPreview = null;
    els.workspaceTitle.textContent = "当前方案项目无法加载";
    els.workspaceSubtitle.textContent = error.message;
  } finally {
    state.loading = false;
    renderAll();
  }
}

async function refreshCurrentProject() {
  await loadProjects();
  await loadWorkspace();
}

async function selectPage(pageId) {
  state.currentPageId = pageId;
  updateLocation();
  await loadPageDetail();
}

async function runPageAction(action, extra = {}) {
  if (!state.currentProjectId || !state.currentPageId) return;
  setFeedback("正在处理...", "");
  try {
    await requestJson(
      `/api/workspace/${encodeURIComponent(state.currentProjectId)}/page/${encodeURIComponent(state.currentPageId)}/actions`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          actor: "user",
          note: els.decisionNote.value.trim(),
          ...extra,
        }),
      }
    );
    setFeedback("操作已完成。", "success");
    await refreshCurrentProject();
  } catch (error) {
    setFeedback(error.message, "danger");
  }
}

async function runRunAction(action, extra = {}) {
  if (!state.currentProjectId) return;
  setFeedback("正在处理...", "");
  try {
    await requestJson(`/api/workspace/${encodeURIComponent(state.currentProjectId)}/actions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        actor: "user",
        note: els.decisionNote.value.trim(),
        ...extra,
      }),
    });
    setFeedback("操作已完成。", "success");
    await refreshCurrentProject();
  } catch (error) {
    setFeedback(error.message, "danger");
  }
}

async function createRun(event) {
  event.preventDefault();
  const brief = els.brief.value.trim();
  if (!brief) {
    els.createStatus.textContent = "请先填写需求简述。";
    return;
  }

  els.createRunSubmit.disabled = true;
  els.createStatus.textContent = "正在创建方案项目...";
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
    state.currentProjectId = payload.run_id;
    state.currentPageId = "";
    els.createStatus.textContent = "方案项目已创建，正在载入工作台。";
    setCreateModal(false);
    await refreshCurrentProject();
  } catch (error) {
    els.createStatus.textContent = error.message;
  } finally {
    els.createRunSubmit.disabled = false;
  }
}

function bindEvents() {
  els.openCreateModal.addEventListener("click", () => setCreateModal(true));
  els.closeCreateModal.addEventListener("click", () => setCreateModal(false));
  els.createRunModal.addEventListener("click", (event) => {
    if (event.target === els.createRunModal) setCreateModal(false);
  });
  els.createRunForm.addEventListener("submit", createRun);

  els.projectSwitcher.addEventListener("change", async (event) => {
    state.currentProjectId = event.target.value;
    state.currentPageId = "";
    state.viewMode = "page";
    updateLocation();
    await loadWorkspace();
  });

  els.pageMode.addEventListener("click", () => {
    state.viewMode = "page";
    renderAll();
  });
  els.deliveryMode.addEventListener("click", async () => {
    state.viewMode = "delivery";
    if (!state.deliveryPreview || !state.deliveryPreview.artifact_ready) {
      await loadDeliveryPreview({ silent: true });
    }
    renderAll();
  });

  els.firstPage.addEventListener("click", async () => {
    const page = filteredPages()[0];
    if (page) await selectPage(page.page_id);
  });
  els.prevPage.addEventListener("click", async () => {
    const pages = filteredPages();
    const index = pages.findIndex((page) => page.page_id === state.currentPageId);
    if (index > 0) await selectPage(pages[index - 1].page_id);
  });
  els.nextPage.addEventListener("click", async () => {
    const pages = filteredPages();
    const index = pages.findIndex((page) => page.page_id === state.currentPageId);
    if (index >= 0 && index < pages.length - 1) await selectPage(pages[index + 1].page_id);
  });
  els.lastPage.addEventListener("click", async () => {
    const pages = filteredPages();
    const page = pages[pages.length - 1];
    if (page) await selectPage(page.page_id);
  });

  els.approvePage.addEventListener("click", async () => runPageAction("approve"));
  els.rejectPage.addEventListener("click", async () => runPageAction("reject"));
  els.requestEvidence.addEventListener("click", async () => runPageAction("request_evidence"));
  els.submitPageApproval.addEventListener("click", async () => runPageAction("submit_approval"));
  els.saveNote.addEventListener("click", async () => runPageAction("add_note"));
  els.submitRunApproval.addEventListener("click", async () => runRunAction("submit_approval"));
  els.markDelivered.addEventListener("click", async () => runRunAction("mark_delivered", { delivered: true }));
}

async function boot() {
  bindEvents();
  renderAll();
  try {
    await loadProjects();
    renderProjectSwitcher();
    if (state.currentProjectId) {
      await loadWorkspace();
    }
  } catch (error) {
    els.workspaceTitle.textContent = "工作台加载失败";
    els.workspaceSubtitle.textContent = error.message;
  }
}

boot();
