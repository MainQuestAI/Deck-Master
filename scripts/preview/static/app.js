const state = {
  projects: [],
  setupStatus: null,
  runState: null,
  workspace: null,
  pageDetail: null,
  activity: null,
  deliveryPreview: null,
  shellError: null,
  shellState: null,
  selectedPageState: null,
  primaryActionState: null,
  drawerStateView: null,
  currentProjectId: new URLSearchParams(window.location.search).get("run") || "",
  currentPageId: new URLSearchParams(window.location.search).get("page") || "",
  drawerTab: new URLSearchParams(window.location.search).get("drawer-tab") || "readiness",
  drawerExpanded: new URLSearchParams(window.location.search).get("drawer") === "expanded",
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
  statusDrawer: document.querySelector("#status-drawer"),
  blockFlag: document.querySelector("#block-flag"),
  draftGateLabel: document.querySelector("#draft-gate-label"),
  exportLabel: document.querySelector("#export-label"),
  langToggle: document.querySelector("#lang-toggle"),
  bottomDrawer: document.querySelector("#bottom-drawer"),
  bottomDrawerTabs: document.querySelector(".bottom-drawer-tabs"),
  bottomDrawerPanels: document.querySelectorAll(".bottom-drawer-panel"),
  buildSkillPanel: document.querySelector("#build-skill-panel"),
  artifactPanel: document.querySelector("#artifact-panel"),
  exportPanel: document.querySelector("#export-panel"),
  actionBar: document.querySelector("#action-bar"),
  projectSwitcher: document.querySelector("#project-switcher"),
  projectSwitcherMeta: document.querySelector("#project-switcher-meta"),
  queuePanelLabel: document.querySelector("#queue-panel-label"),
  queuePanelTitle: document.querySelector("#queue-panel-title"),
  queuePanelDetail: document.querySelector("#queue-panel-detail"),
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
  readinessBadge: document.querySelector("#readiness-badge"),
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

function describeMutationAction(action) {
  const mapping = {
    approve: "批准页面",
    reject: "驳回页面",
    request_evidence: "请求补证据",
    submit_approval: "升级审批",
    add_note: "记录备注",
    approve_approval: "批准审批任务",
    reject_approval: "驳回审批任务",
    mark_delivered: "确认交付",
  };
  return mapping[String(action || "").trim()] || "执行操作";
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

function currentSetupStatus() {
  return state.setupStatus || {};
}

function currentRunState() {
  return state.runState || {};
}

function setupReady() {
  const setup = currentSetupStatus();
  return Boolean(setup.install_ready && setup.workspace_ready && setup.run_ready);
}

function uniqueList(items) {
  return [...new Set((items || []).map((item) => String(item || "").trim()).filter(Boolean))];
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
  url.searchParams.set("drawer-tab", state.drawerTab);
  url.searchParams.set("drawer", state.drawerExpanded ? "expanded" : "collapsed");
  window.history.replaceState({}, "", url);
}

function deriveShellState() {
  const setup = currentSetupStatus();
  const runState = currentRunState();
  const workspace = currentWorkspace();
  const stage = currentStage();
  const stageLabel = currentStageLabel();
  const selectedProject = state.projects.find((project) => project.run_id === state.currentProjectId) || null;
  const projectName = workspace.project_title || selectedProject?.title || state.currentProjectId || "方案项目";
  const setupBlocks = uniqueList([...(setup.missing_items || []), ...(setup.repair_items || [])]);
  const workspaceBlocks = uniqueList([
    ...(workspace.health?.blocking_reasons || []),
    ...(runState.next_step?.blocking_issues || []),
  ]);

  if (state.loading && !workspace.project_id) {
    return {
      id: "loading",
      tone: "muted",
      stageLabel: "载入中",
      headline: "正在读取当前工作台",
      subtitle: "系统正在同步当前 run、页面队列和动作状态。",
      stageTitle: state.currentProjectId ? "当前项目" : "系统状态",
      stageDetail: state.currentProjectId ? projectName : "准备进入工作台",
      nextTitle: "下一步",
      nextDetail: "载入完成后会自动切到当前状态对应的主舞台。",
      blockTitle: "请稍候",
      blockDetail: "当前仍在读取最新数据。",
      blockTone: "",
      blockers: [],
    };
  }

  if (state.shellError) {
    return {
      id: "error",
      tone: "danger",
      stageLabel: "状态异常",
      headline: state.shellError.title || "工作台状态异常",
      subtitle: state.shellError.detail || "当前无法稳定读取方案项目状态。",
      stageTitle: "问题位置",
      stageDetail: state.shellError.scope === "setup" ? "系统准备阶段" : projectName,
      nextTitle: "建议动作",
      nextDetail: state.shellError.recovery || "重新选择项目，或刷新页面后重试。",
      blockTitle: "当前阻断",
      blockDetail: state.shellError.detail || "当前请求失败。",
      blockTone: "danger",
      blockers: [state.shellError.detail || "当前请求失败。"],
    };
  }

  if (state.setupStatus && !setupReady()) {
    const missingCount = setupBlocks.length;
    return {
      id: "setup",
      tone: "warning",
      stageLabel: "Setup 未就绪",
      headline: "工作台还未准备完成",
      subtitle: setup.active_workspace
        ? `当前工作目录已识别：${setup.active_workspace}`
        : "系统还没有识别到可用工作目录。",
      stageTitle: "系统缺口",
      stageDetail: setupBlocks[0] || "仍有前置项待补齐。",
      nextTitle: "下一步",
      nextDetail: setup.next_command || "先补齐安装、工作目录或 run 绑定，再进入工作台。",
      blockTitle: missingCount ? `${missingCount} 项待补齐` : "仍有前置项待处理",
      blockDetail: setupBlocks[0] || "请先完成 setup。",
      blockTone: "danger",
      blockers: setupBlocks,
      warnings: setup.warnings || [],
    };
  }

  if (!state.currentProjectId) {
    return {
      id: "project-selection",
      tone: "muted",
      stageLabel: "待选择项目",
      headline: state.projects.length ? "先选择一个方案项目" : "当前还没有方案项目",
      subtitle: state.projects.length
        ? "项目切换放在右上角。选中后，左栏、中间舞台和右栏会同步进入当前 run。"
        : "点击右上角新建项目，完成后会自动回到工作台。",
      stageTitle: "项目状态",
      stageDetail: state.projects.length ? `${state.projects.length} 个可用项目` : "0 个可用项目",
      nextTitle: "下一步",
      nextDetail: state.projects.length ? "选择一个项目，马上进入当前阶段判断。" : "新建项目后进入工作台。",
      blockTitle: "当前入口",
      blockDetail: state.projects.length ? "工作台已就绪，等待选择项目。" : "当前还没有可进入的项目。",
      blockTone: "",
      blockers: [],
    };
  }

  if (runState.run_id && workspace.project_id && runState.run_id !== workspace.project_id) {
    return {
      id: "error",
      tone: "danger",
      stageLabel: "状态不一致",
      headline: "run 状态和工作台绑定不一致",
      subtitle: "当前页面读取到的 run 信息和工作台数据不在同一个项目上。",
      stageTitle: "当前项目",
      stageDetail: `${runState.run_id} / ${workspace.project_id}`,
      nextTitle: "建议动作",
      nextDetail: "重新选择项目，再刷新当前工作台。",
      blockTitle: "当前阻断",
      blockDetail: "run-state 与 workspace payload 不一致。",
      blockTone: "danger",
      blockers: ["run-state 与 workspace payload 不一致。"],
    };
  }

  if (!workspace.project_id) {
    return {
      id: "error",
      tone: "danger",
      stageLabel: "项目未载入",
      headline: "当前项目还没有稳定载入",
      subtitle: "工作台没有拿到完整的 run 数据。",
      stageTitle: "当前项目",
      stageDetail: projectName,
      nextTitle: "建议动作",
      nextDetail: "重新选择项目，或刷新页面后重试。",
      blockTitle: "当前阻断",
      blockDetail: "缺少 workspace payload。",
      blockTone: "danger",
      blockers: ["缺少 workspace payload。"],
    };
  }

  if (["待准备", "生成中"].includes(stageLabel)) {
    return {
      id: "generating",
      tone: stage.tone || "warning",
      stageLabel: stage.label || "生成中",
      headline: workspace.project_title || "当前方案项目",
      subtitle: stage.blocking_reason || "当前仍在补齐页面生成或预览构建。",
      stageTitle: "当前判断",
      stageDetail: stage.definition || "页面生成或预览构建还在推进。",
      nextTitle: "下一步",
      nextDetail: runState.next_command || stage.next_step || "等待生成完成，或补齐缺失预览。",
      blockTitle: workspaceBlocks.length ? `${workspaceBlocks.length} 项当前阻塞` : "当前无显式阻塞",
      blockDetail: workspaceBlocks[0] || "当前没有显式阻塞项。",
      blockTone: workspaceBlocks.length ? "danger" : "",
      blockers: workspaceBlocks,
      warnings: setup.warnings || [],
    };
  }

  if (["待审阅", "待补依据", "待审批"].includes(stageLabel)) {
    return {
      id: "review",
      tone: stage.tone || "success",
      stageLabel: stage.label || "待审阅",
      headline: workspace.project_title || "当前方案项目",
      subtitle: "当前已进入页级处理主路径。选中页面后，中间舞台和右栏动作会同步刷新。",
      stageTitle: "当前判断",
      stageDetail: stage.definition || "当前已进入可逐页处理阶段。",
      nextTitle: "下一步",
      nextDetail: stage.next_step || "先选中一个页面，完成当前页判断。",
      blockTitle: workspaceBlocks.length ? `${workspaceBlocks.length} 项需关注` : "当前无主阻断",
      blockDetail: workspaceBlocks[0] || "当前可以直接进入页面处理。",
      blockTone: workspaceBlocks.length ? "danger" : "",
      blockers: workspaceBlocks,
    };
  }

  return {
    id: "delivery",
    tone: stage.tone || "success",
    stageLabel: stage.label || "可交付",
    headline: workspace.project_title || "当前方案项目",
    subtitle: "当前已进入交付判断区。主舞台会聚焦交付预览、阻断原因和确认交付动作。",
    stageTitle: "当前判断",
    stageDetail: stage.definition || "当前已进入交付阶段。",
    nextTitle: currentWorkspace().run_summary?.delivery?.delivered ? "交付已记录" : "下一步",
    nextDetail:
      currentWorkspace().run_summary?.delivery?.delivered
        ? `交付时间：${formatTime(currentWorkspace().run_summary?.delivery?.delivered_at)}`
        : stage.next_step || "先确认交付预览，再记录最终交付。",
    blockTitle: workspaceBlocks.length ? `${workspaceBlocks.length} 项交付阻断` : "交付链路已清晰",
    blockDetail: workspaceBlocks[0] || "当前可以进入交付预览和交付确认。",
    blockTone: workspaceBlocks.length ? "danger" : "",
    blockers: workspaceBlocks,
  };
}

function deriveSelectedPageState(shellState) {
  const pages = currentPages();
  const page = currentPageCard() || pages[0] || null;
  const index = page ? pages.findIndex((item) => item.page_id === page.page_id) : -1;

  return {
    shellId: shellState.id,
    page,
    count: pages.length,
    index,
    orderLabel: page ? `第 ${String(page.order).padStart(2, "0")} 页` : "",
    roleLabel: page?.narrative_role || "未标注页面职责",
    sourceLabel: page?.source_decision_label || page?.source_label || "来源待确认",
    reviewLabel: state.pageDetail?.hero?.review_label || page?.status_label || shellState.stageLabel,
  };
}

function derivePrimaryActionState(shellState, selectedPageState) {
  const page = selectedPageState.page;
  const pageDetailReady = Boolean(page && state.pageDetail);
  const stageLabel = currentStageLabel();
  const highestRisk = currentPageHighestRisk();
  const reviewStatus = String(page?.review_status || "");

  if (shellState.id === "setup") {
    return {
      label: "先完成 setup",
      enabled: false,
      action: "",
      hint: shellState.nextDetail,
    };
  }

  if (shellState.id === "project-selection") {
    return {
      label: state.projects.length ? "先选择项目" : "先新建项目",
      enabled: false,
      action: "",
      hint: shellState.nextDetail,
    };
  }

  if (shellState.id === "loading") {
    return {
      label: "正在载入",
      enabled: false,
      action: "",
      hint: shellState.nextDetail,
    };
  }

  if (shellState.id === "error") {
    return {
      label: "状态异常",
      enabled: false,
      action: "",
      hint: shellState.nextDetail,
    };
  }

  if (state.viewMode === "delivery") {
    return {
      label: "交付预览模式",
      enabled: false,
      action: "",
      hint: "当前主舞台正在显示交付预览，页面级动作已收起。",
    };
  }

  if (!page) {
    return {
      label: "请先选页",
      enabled: false,
      action: "",
      hint: "先在左栏选择一页，工作台会同步显示当前页上下文和动作。",
    };
  }

  if (shellState.id === "generating") {
    return {
      label: stageLabel === "生成中" ? "等待生成完成" : "等待进入可审阶段",
      enabled: false,
      action: "",
      hint: `当前选中：${selectedPageState.orderLabel}《${page.title}》· 先补齐预览与生成结果，再开放页面级动作。`,
    };
  }

  if (!pageDetailReady) {
    return {
      label: "正在同步当前页",
      enabled: false,
      action: "",
      hint: "当前页已选中，系统正在补齐页面级详情。",
    };
  }

  const stageAllowsReview = ["待审阅", "待补依据", "待审批", "可交付", "已交付"].includes(stageLabel);
  const stageAllowsEvidence = ["待审阅", "待补依据"].includes(stageLabel);

  if (reviewStatus === "approved") {
    return {
      label: "下一页",
      enabled: true,
      action: "next-page",
      hint: "当前页已批准。跳到下一待审或阻断页继续处理。",
    };
  }

  if (reviewStatus === "rejected") {
    return {
      label: "重新审查",
      enabled: stageAllowsReview,
      action: "re-review",
      hint: stageAllowsReview ? "当前页已驳回，可重新进入审查。" : "当前阶段还不允许重新审查。",
    };
  }

  if (reviewStatus === "needs_evidence") {
    return {
      label: "请求补证据",
      enabled: stageAllowsEvidence,
      action: "request-evidence",
      hint: stageAllowsEvidence ? "当前页证据不足，先发起补证据再继续审查。" : "当前阶段还不允许请求补证据。",
    };
  }

  if (reviewStatus === "needs_review") {
    if (highestRisk === "P0") {
      return {
        label: "先处理阻断",
        enabled: false,
        action: "",
        hint: "当前页存在 P0 阻断。先处理风险与缺口，或请求补证据。",
      };
    }
    if (highestRisk === "P1") {
      return {
        label: "批准页面",
        enabled: stageAllowsReview,
        action: "approve",
        hint: stageAllowsReview ? "当前页带有 P1 风险，批准前请先完成判断。" : "当前阶段还不允许批准页面。",
      };
    }
    return {
      label: "批准页面",
      enabled: stageAllowsReview,
      action: "approve",
      hint: stageAllowsReview ? "当前页无显式阻断，可直接推进批准。" : "当前阶段还不允许批准页面。",
    };
  }

  return {
    label: "当前暂无动作",
    enabled: false,
    action: "",
    hint: "当前页状态还不支持直接操作。",
  };
}

function deriveDrawerState(shellState) {
  const setup = currentSetupStatus();
  const workspace = currentWorkspace();
  const badgeCount = shellState.id === "setup"
    ? uniqueList([...(setup.missing_items || []), ...(setup.repair_items || [])]).length
    : (workspace.health?.blocking_reasons || []).length;

  return {
    tab: state.drawerTab,
    expanded: state.drawerExpanded,
    badgeCount,
  };
}

function syncDerivedState() {
  state.shellState = deriveShellState();
  state.selectedPageState = deriveSelectedPageState(state.shellState);
  state.primaryActionState = derivePrimaryActionState(state.shellState, state.selectedPageState);
  state.drawerStateView = deriveDrawerState(state.shellState);
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
  const shellState = state.shellState || deriveShellState();
  els.projectSwitcher.innerHTML = "";
  els.projectSwitcherMeta.textContent = `${state.projects.length} 个方案项目`;
  if (!state.projects.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = shellState.id === "setup" ? "等待 setup 完成" : "暂无方案项目";
    els.projectSwitcher.appendChild(option);
    els.projectSwitcher.disabled = true;
    return;
  }

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "选择项目";
  placeholder.selected = !state.currentProjectId;
  els.projectSwitcher.appendChild(placeholder);
  els.projectSwitcher.disabled = shellState.id === "setup";
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
  if (!els.filterList) return;
  const shellState = state.shellState || deriveShellState();
  els.filterList.innerHTML = "";
  if (!["generating", "review", "delivery"].includes(shellState.id)) {
    return;
  }
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
  if (!els.pageList) return;
  const shellState = state.shellState || deriveShellState();
  els.pageList.innerHTML = "";
  const pages = filteredPages();
  const metrics = currentWorkspace().header_metrics;
  if (els.queuePanelLabel) {
    els.queuePanelLabel.textContent = shellState.id === "setup" ? "系统入口" : "任务目录";
  }
  if (els.queuePanelTitle) {
    const mapping = {
      setup: "先完成系统准备",
      "project-selection": state.projects.length ? "请选择一个方案项目" : "当前还没有方案项目",
      loading: "正在同步任务目录",
      error: "当前目录暂不可用",
      generating: "当前待处理页面",
      review: "当前待审页面",
      delivery: "当前交付页面",
    };
    els.queuePanelTitle.textContent = mapping[shellState.id] || "当前待处理页面";
  }
  if (els.queuePanelDetail) {
    const detail = {
      setup: "补齐 setup 后再进入 run 目录",
      "project-selection": state.projects.length ? "先选中项目，再进入页级处理" : "新建项目后自动回到这里",
      loading: "请稍候",
      error: "重新选择项目或刷新页面",
      generating: "列表保持可扫视，重点看页号、状态、角色和风险",
      review: "左栏只保留决策必需信息",
      delivery: "交付阶段优先看可交付页和阻断页",
    }[shellState.id] || "按顺序处理";
    els.queuePanelDetail.textContent = detail;
  }

  if (shellState.id === "setup") {
    els.queueSummary.textContent = shellState.blockDetail;
    els.pageList.innerHTML = '<div class="empty-inline">完成 setup 后，这里会出现当前项目的任务目录。</div>';
    return;
  }

  if (shellState.id === "project-selection") {
    els.queueSummary.textContent = shellState.blockDetail;
    els.pageList.innerHTML = '<div class="empty-inline">先从右上角选择项目，或直接新建项目。</div>';
    return;
  }

  if (shellState.id === "loading") {
    els.queueSummary.textContent = "正在读取页面队列...";
    els.pageList.innerHTML = '<div class="empty-inline">系统正在同步页面队列，请稍候。</div>';
    return;
  }

  if (shellState.id === "error") {
    els.queueSummary.textContent = shellState.blockDetail;
    els.pageList.innerHTML = `<div class="empty-inline">${escapeHtml(shellState.nextDetail)}</div>`;
    return;
  }

  if (metrics) {
    els.queueSummary.textContent = `共 ${metrics.pages_total} 页 · 待处理 ${metrics.pages_waiting} · 已批准 ${metrics.pages_approved} · 高优风险 ${metrics.p0 + metrics.p1}`;
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
    const approvalLabel = page.approval_state === "pending" ? "待审批" : "无审批";
    const riskTone = page.blocking_count > 0 ? "danger" : page.risk_count > 0 ? "warning" : "muted";
    item.innerHTML = `
      <div class="page-card-top">
        <span class="page-order mono">P${String(page.order).padStart(2, "0")}</span>
        <span class="status-pill ${page.status_tone}">${escapeHtml(page.status_label)}</span>
      </div>
      <strong>${escapeHtml(page.title)}</strong>
      <div class="page-card-tags">
        <span class="page-chip">${escapeHtml(page.narrative_role || "未标注页面职责")}</span>
        <span class="page-chip">${escapeHtml(page.source_label || "来源待确认")}</span>
      </div>
      <div class="page-card-meta">
        <span class="page-risk page-risk-${riskTone}">风险 ${page.risk_count}</span>
        <span>${escapeHtml(approvalLabel)}</span>
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
  if (!els.workspaceTitle) return;
  const shellState = state.shellState || deriveShellState();
  const workspace = currentWorkspace();
  const metrics = workspace.header_metrics || {};
  els.workspaceTitle.textContent = shellState.headline;
  els.workspaceSubtitle.textContent = shellState.subtitle;
  els.stageChip.textContent = shellState.stageLabel;
  els.stageChip.className = `stage-chip ${shellState.tone || "muted"}`;
  els.stageTitle.textContent = shellState.stageTitle || "-";
  els.stageDetail.textContent = shellState.stageDetail || "-";
  els.nextStepTitle.textContent = shellState.nextTitle || "-";
  els.nextStepDetail.textContent = shellState.nextDetail || "-";
  els.riskSummaryTitle.textContent = shellState.blockTitle || "-";
  els.riskSummaryDetail.textContent = shellState.blockDetail || "-";
  els.draftGateLabel.textContent = shellState.id === "review" || shellState.id === "delivery"
    ? "可判定"
    : shellState.id === "generating"
      ? "未开放"
      : shellState.id === "setup"
        ? "待准备"
        : "-";
  els.exportLabel.textContent = workspace.project_id
    ? `${metrics.export_ready ?? 0} ready / ${metrics.export_blocked ?? 0} blocked`
    : shellState.id === "setup"
      ? (currentSetupStatus().production_ready ? "ready" : "hold")
      : "-";

  if (shellState.id === "setup") {
    const missingCount = uniqueList([
      ...(currentSetupStatus().missing_items || []),
      ...(currentSetupStatus().repair_items || []),
    ]).length;
    els.metricPages.textContent = currentSetupStatus().active_workspace ? "1" : "0";
    els.metricApproved.textContent = String(missingCount);
    els.metricApprovals.textContent = String((currentSetupStatus().warnings || []).length);
    els.metricExport.textContent = currentSetupStatus().production_ready ? "ready" : "hold";
    return;
  }

  if (!workspace.project_id) {
    els.metricPages.textContent = state.projects.length ? String(state.projects.length) : "-";
    els.metricApproved.textContent = "-";
    els.metricApprovals.textContent = "-";
    els.metricExport.textContent = "-";
    return;
  }

  els.metricPages.textContent = String(metrics.pages_total ?? "-");
  els.metricApproved.textContent = String(metrics.pages_approved ?? "-");
  els.metricApprovals.textContent = String(metrics.pending_approvals ?? "-");
  els.metricExport.textContent = `${metrics.export_ready ?? 0} / ${metrics.export_blocked ?? 0}`;
}

function renderCriticalAlerts() {
  if (!els.criticalAlerts) return;
  const shellState = state.shellState || deriveShellState();
  if (["setup", "project-selection", "loading", "error"].includes(shellState.id)) {
    const shellAlerts = [];
    if (shellState.blockDetail) {
      shellAlerts.push({
        tone: shellState.blockTone || (shellState.id === "error" ? "danger" : shellState.id === "setup" ? "warning" : "muted"),
        label: shellState.stageLabel,
        detail: shellState.blockDetail,
      });
    }
    (shellState.warnings || []).slice(0, 2).forEach((item) => {
      shellAlerts.push({
        tone: "warning",
        label: "提示",
        detail: item,
      });
    });
    if (!shellAlerts.length) {
      shellAlerts.push({
        tone: shellState.tone || "muted",
        label: shellState.stageLabel,
        detail: shellState.subtitle,
      });
    }
    els.criticalAlerts.innerHTML = shellAlerts.map((alert) => `
      <div class="alert-card ${escapeHtml(alert.tone || "muted")}">
        <strong>${escapeHtml(alert.label || "提示")}</strong>
        <span>${escapeHtml(alert.detail || "")}</span>
      </div>
    `).join("");
    return;
  }

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

function renderShellWorkspace() {
  if (!els.previewStage) return;
  const shellState = state.shellState || deriveShellState();
  const cards = (shellState.blockers || []).slice(0, 3).map((item) => `
    <div class="stage-card ${escapeHtml(shellState.blockTone || "warning")}">
      <span class="panel-title">当前阻断</span>
      <strong>${escapeHtml(item)}</strong>
      <p>${escapeHtml(shellState.nextDetail || "请先完成当前前置项。")}</p>
    </div>
  `).join("");
  const warnings = (shellState.warnings || []).slice(0, 3).map((item) => `
    <div class="stage-check-item">
      <strong>提示</strong>
      <p>${escapeHtml(item)}</p>
    </div>
  `).join("");

  els.previewPanelLabel.textContent = shellState.id === "setup" ? "系统入口" : "工作台入口";
  els.focusPageTitle.textContent = shellState.headline;
  els.focusPageMeta.textContent = shellState.subtitle;
  els.currentLabel.textContent = shellState.stageLabel;
  setPreviewNavVisible(false);

  els.previewStage.innerHTML = `
    <div class="stage-workspace">
      <div class="stage-card stage-card-focus ${escapeHtml(shellState.tone || "muted")}">
        <div class="stage-card-topline">
          <span class="panel-title">${escapeHtml(shellState.stageLabel)}</span>
          <span class="status-pill ${escapeHtml(shellState.tone || "muted")}">${escapeHtml(shellState.stageLabel)}</span>
        </div>
        <strong>${escapeHtml(shellState.blockTitle || shellState.headline)}</strong>
        <p>${escapeHtml(shellState.nextDetail || shellState.subtitle)}</p>
        <div class="stage-card-tags">
          <span class="page-chip">${escapeHtml(shellState.stageTitle || "当前判断")}</span>
          <span class="page-chip">${escapeHtml(shellState.stageDetail || "待确认")}</span>
        </div>
      </div>
      <div class="stage-workspace-top">
        ${cards || `<div class="stage-card"><span class="panel-title">当前状态</span><strong>${escapeHtml(shellState.blockDetail || "当前入口已就绪")}</strong><p>${escapeHtml(shellState.subtitle)}</p></div>`}
      </div>
      <section class="stage-checklist">
        <span class="panel-title">现在该做什么</span>
        <h3>${escapeHtml(shellState.nextTitle || "下一步")}</h3>
        <div class="stage-check-grid">
          ${warnings || `<div class="stage-check-item"><strong>${escapeHtml(shellState.nextTitle || "下一步")}</strong><p>${escapeHtml(shellState.nextDetail || "当前没有额外说明。")}</p></div>`}
        </div>
      </section>
    </div>
  `;
}

function renderStageWorkspace() {
  if (!els.previewStage) return;
  const workspace = currentWorkspace();
  const stage = currentStage();
  const focusPage = currentPageCard() || currentPages()[0] || null;
  const delivery = workspace.run_summary?.delivery_preview || {};
  const actions = workspace.run_summary?.next_actions || [];
  const blockers = workspace.health?.blocking_reasons || [];

  if (focusPage) {
    const orderLabel = `第 ${String(focusPage.order).padStart(2, "0")} 页`;
    const sourceLabel = focusPage.source_decision_label || focusPage.source_label || "来源待确认";
    els.previewPanelLabel.textContent = "当前选中页面（待就绪）";
    els.focusPageTitle.textContent = `${orderLabel} · ${focusPage.title}`;
    els.focusPageMeta.textContent = `${focusPage.narrative_role || "未标注页面职责"} · ${sourceLabel} · 当前阶段仍在${stage.label || "待准备"}，预览与审批待开放`;
    els.currentLabel.textContent = `${orderLabel} · 阶段工作区`;
  } else {
    els.previewPanelLabel.textContent = "阶段工作区";
    els.focusPageTitle.textContent = `${stage.label || "待准备"} · ${stage.definition || "当前仍在准备阶段"}`;
    els.focusPageMeta.textContent = stage.blocking_reason || "系统正在整理进入可处理状态所需的前置内容。";
    els.currentLabel.textContent = "阶段工作区";
  }
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
  const focusPageCard = focusPage ? `
    <div class="stage-card stage-card-focus">
      <div class="stage-card-topline">
        <span class="panel-title">当前选中页面</span>
        <span class="status-pill ${escapeHtml(focusPage.status_tone || "muted")}">${escapeHtml(focusPage.status_label || "待处理")}</span>
      </div>
      <strong>${escapeHtml(`第 ${String(focusPage.order).padStart(2, "0")} 页 · ${focusPage.title}`)}</strong>
      <p>${escapeHtml(`这页承担“${focusPage.narrative_role || "未标注页面职责"}”的说明任务。当前仍处于${stage.label || "待准备"}阶段，先补齐预览与生成结果，再开放页面级操作。`)}</p>
      <div class="stage-card-tags">
        <span class="page-chip">${escapeHtml(focusPage.source_decision_label || focusPage.source_label || "来源待确认")}</span>
        <span class="page-chip">风险 ${escapeHtml(String(focusPage.risk_count || 0))}</span>
        <span class="page-chip">${escapeHtml(focusPage.approval_state === "pending" ? "待审批" : "无审批")}</span>
      </div>
    </div>
  ` : "";

  els.previewStage.innerHTML = `
    <div class="stage-workspace">
      <div class="stage-workspace-top">
        ${focusPageCard}
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
  if (!els.previewStage) return;
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
    els.previewStage.innerHTML = `
      <div class="page-preview-frame">
        <div class="page-preview-toolbar">
          <span class="panel-title">当前预览</span>
          <span class="page-chip">第 ${String(focusPage.order).padStart(2, "0")} 页</span>
          <span class="page-chip">${escapeHtml(focusPage.narrative_role || "未标注页面职责")}</span>
        </div>
        <img src="${previewUrlWithProject(focusPage.preview_url)}" alt="${escapeHtml(focusPage.title)}">
      </div>
    `;
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
  if (!els.previewStage) return;
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
  if (!els.previewStage) return;
  const shellState = state.shellState || deriveShellState();
  const showDeliveryMode = isDeliveryStage();
  if (els.deliveryMode) {
    els.deliveryMode.hidden = shellState.id !== "delivery";
  }
  if (!showDeliveryMode && state.viewMode === "delivery") {
    state.viewMode = "page";
  }

  if (["setup", "project-selection", "loading", "error"].includes(shellState.id)) {
    state.viewMode = "page";
    renderShellWorkspace();
    return;
  }

  if (shellState.id === "generating") {
    state.viewMode = "page";
    renderStageWorkspace();
    return;
  }

  if (state.viewMode === "delivery" && shellState.id === "delivery") {
    renderDeliveryPreview();
    return;
  }

  renderPagePreview();
}

function renderReadiness() {
  if (!els.runReadiness) return;
  const shellState = state.shellState || deriveShellState();
  const workspace = currentWorkspace();
  const drawerStateView = state.drawerStateView || deriveDrawerState(shellState);
  const blockCount = drawerStateView.badgeCount;
  if (els.readinessBadge) {
    els.readinessBadge.textContent = String(blockCount);
    els.readinessBadge.classList.toggle("is-visible", blockCount > 0);
  }

  if (shellState.id === "setup") {
    const setup = currentSetupStatus();
    const blocks = uniqueList([...(setup.missing_items || []), ...(setup.repair_items || [])]);
    els.readinessPill.textContent = shellState.stageLabel;
    els.readinessPill.className = "pill warning";
    els.runReadiness.innerHTML = `
      <div class="stack-card warning">
        <strong>系统仍未就绪</strong>
        <p>${escapeHtml(shellState.blockDetail)}</p>
        <small>${escapeHtml(setup.next_command || "完成 setup 后可进入 run 工作台。")}</small>
      </div>
      ${blocks.map((item) => `<div class="stack-card warning"><strong>待补齐</strong><p>${escapeHtml(item)}</p></div>`).join("")}
      ${(setup.warnings || []).map((item) => `<div class="stack-card"><strong>提示</strong><p>${escapeHtml(item)}</p></div>`).join("")}
    `;
    return;
  }

  if (!workspace.project_id) {
    els.readinessPill.textContent = shellState.stageLabel || "-";
    els.readinessPill.className = `pill ${shellState.tone || "muted"}`;
    els.runReadiness.innerHTML = `<div class="empty-inline">${escapeHtml(shellState.nextDetail || "当前还没有方案项目数据。")}</div>`;
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
  if (!els.claimCoverage) return;
  const shellState = state.shellState || deriveShellState();
  const workspace = currentWorkspace();
  if (!workspace.project_id) {
    els.claimSummaryChip.textContent = shellState.stageLabel || "-";
    els.claimSummaryChip.className = `pill ${shellState.tone || "muted"}`;
    els.claimCoverage.innerHTML = `<div class="empty-inline">${escapeHtml(shellState.id === "setup" ? "完成 setup 后，这里会显示 run 级论点覆盖。" : "选择项目后，这里会显示 run 级论点覆盖。")}</div>`;
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
  if (!els.activityList) return;
  const shellState = state.shellState || deriveShellState();
  if (!currentWorkspace().project_id) {
    els.activityCount.textContent = "0";
    els.activityList.innerHTML = `<div class="empty-inline">${escapeHtml(shellState.id === "setup" ? "完成 setup 后，这里会记录处理过程。" : "进入项目后，这里会记录当前 run 的处理过程。")}</div>`;
    return;
  }
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

function renderShellDecisionRail() {
  if (!els.decisionTitle) return;
  const shellState = state.shellState || deriveShellState();
  const blocks = shellState.blockers || [];

  els.decisionPanelLabel.textContent = "当前可执行动作";
  els.decisionTitle.textContent = shellState.headline;
  els.decisionSummary.textContent = shellState.nextDetail || shellState.subtitle;
  els.decisionNote.value = "";

  els.pageRoleContent.innerHTML = `
    <div class="stack-card">
      <strong>${escapeHtml(shellState.stageTitle || "当前判断")}</strong>
      <p>${escapeHtml(shellState.stageDetail || "待确认")}</p>
      <small>${escapeHtml(shellState.stageLabel)}</small>
    </div>
  `;
  els.pageSourceContent.innerHTML = `
    <div class="stack-card">
      <strong>当前入口</strong>
      <p>${escapeHtml(shellState.blockDetail || "当前没有额外说明。")}</p>
      <small>${escapeHtml(shellState.subtitle || "")}</small>
    </div>
  `;
  els.pageEvidenceContent.innerHTML = `
    <div class="stack-card">
      <strong>${escapeHtml(shellState.nextTitle || "下一步")}</strong>
      <p>${escapeHtml(shellState.nextDetail || "当前没有额外说明。")}</p>
      <small>${escapeHtml(currentSetupStatus().next_command || "")}</small>
    </div>
  `;
  els.pageRiskContent.innerHTML = blocks.length
    ? blocks.map((item) => `<div class="stack-card warning"><strong>待处理</strong><p>${escapeHtml(item)}</p></div>`).join("")
    : '<div class="stack-card success">当前没有显式阻断项。</div>';
  els.approvalContent.innerHTML = '<div class="empty-inline">当前阶段还没有页级审批记录。</div>';
}

function renderRunLevelDecisionRail() {
  if (!els.decisionTitle) return;
  const workspace = currentWorkspace();
  const stage = currentStage();
  const focusPage = currentPageCard() || currentPages()[0] || null;
  const deliveryPreview = workspace.run_summary?.delivery_preview || {};
  const approvals = workspace.run_summary?.approvals || [];

  if (focusPage && isStageWorkspace()) {
    els.decisionPanelLabel.textContent = "当前页（待就绪）";
    els.decisionTitle.textContent = focusPage.title;
    els.decisionSummary.textContent = `${focusPage.narrative_role || "未标注页面职责"} · 当前阶段仍在${stage.label || "待准备"}，页面级操作暂未开放。`;
  } else {
    els.decisionPanelLabel.textContent = "当前推进";
    els.decisionTitle.textContent = workspace.project_title || workspace.title || "等待选择方案项目";
    els.decisionSummary.textContent = stage.blocking_reason || "当前还没有页面进入可逐页处理状态。";
  }
  els.pageRoleContent.innerHTML = `
    <div class="stack-card">
      <strong>${escapeHtml(focusPage && isStageWorkspace() ? `${String(focusPage.order).padStart(2, "0")} · ${focusPage.narrative_role || "未标注页面职责"}` : stage.label || "待准备")}</strong>
      <p>${escapeHtml(focusPage && isStageWorkspace() ? focusPage.title : stage.definition || "当前仍在准备阶段。")}</p>
      <small>${escapeHtml(focusPage && isStageWorkspace() ? `${focusPage.source_decision_label || focusPage.source_label || "来源待确认"} · 当前阶段责任对象：${stage.owner || "未指定"}` : stage.owner || "未指定责任对象")}</small>
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
  if (!els.decisionTitle) return;
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
      <small>${escapeHtml((claim.evidence || []).map((item) => item.title).join(" · ") || "待补依据")}</small>
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
  if (!els.decisionTitle) return;
  const shellState = state.shellState || deriveShellState();
  if (["setup", "project-selection", "loading", "error"].includes(shellState.id)) {
    renderShellDecisionRail();
    return;
  }

  if (!state.pageDetail || shellState.id === "generating" || state.viewMode === "delivery") {
    renderRunLevelDecisionRail();
    return;
  }

  renderPageDecisionRail();
}

function syncModeButtons() {
  if (!els.pageMode || !els.deliveryMode) return;
  els.pageMode.classList.toggle("active", state.viewMode === "page");
  els.deliveryMode.classList.toggle("active", state.viewMode === "delivery");
}

// B3: P0/P1 三处联动 — 顶部阻断标记
function renderBlockFlag() {
  if (!els.blockFlag) return;
  const shellState = state.shellState || deriveShellState();
  if (shellState.id === "setup") {
    const missingCount = uniqueList([
      ...(currentSetupStatus().missing_items || []),
      ...(currentSetupStatus().repair_items || []),
    ]).length;
    els.blockFlag.textContent = missingCount ? `${missingCount} 项 setup 待处理` : "setup 仍有待确认项";
    els.blockFlag.dataset.tone = "danger";
    els.blockFlag.hidden = false;
    return;
  }
  if (["project-selection", "loading"].includes(shellState.id)) {
    els.blockFlag.textContent = shellState.blockDetail || "等待进入工作台";
    els.blockFlag.dataset.tone = "";
    els.blockFlag.hidden = false;
    return;
  }
  if (shellState.id === "error") {
    els.blockFlag.textContent = shellState.blockDetail || "当前工作台状态异常";
    els.blockFlag.dataset.tone = "danger";
    els.blockFlag.hidden = false;
    return;
  }
  const metrics = currentWorkspace().header_metrics || {};
  const blockedCount = (metrics.p0 || 0) + (metrics.p1 || 0);
  if (blockedCount > 0) {
    els.blockFlag.textContent = `${blockedCount} 项阻断待处理`;
    els.blockFlag.dataset.tone = "danger";
    els.blockFlag.hidden = false;
  } else {
    els.blockFlag.textContent = "-";
    els.blockFlag.dataset.tone = "";
    els.blockFlag.hidden = false;
  }
}

// B3: 计算当前页最高风险等级（P0 > P1 > P2 > P3）
function currentPageHighestRisk() {
  const risks = state.pageDetail?.quality?.risks || [];
  const order = ["P0", "P1", "P2", "P3"];
  let highest = null;
  for (const risk of risks) {
    const severity = String(risk.severity || "").toUpperCase();
    if (!order.includes(severity)) continue;
    if (!highest || order.indexOf(severity) < order.indexOf(highest)) {
      highest = severity;
    }
  }
  return highest;
}

// B3: 主动作条状态机（spec §10.7）
function renderActionBar() {
  if (!els.actionBar) return;
  const primaryActionState = state.primaryActionState || derivePrimaryActionState(
    state.shellState || deriveShellState(),
    state.selectedPageState || deriveSelectedPageState(state.shellState || deriveShellState())
  );
  const primaryClass = "btn btn-cta";
  const primaryDisabled = primaryActionState.enabled ? "" : "disabled aria-disabled=\"true\"";
  const hintTone = primaryActionState.enabled ? "" : "data-tone=\"warning\"";

  els.actionBar.innerHTML = `
    <button class="${primaryClass}" ${primaryDisabled} data-action-primary="${escapeHtml(primaryActionState.action)}">${escapeHtml(primaryActionState.label)}</button>
    <span class="action-bar-hint mono" ${hintTone}>${escapeHtml(primaryActionState.hint || "")}</span>
  `;

  const primaryBtn = els.actionBar.querySelector("[data-action-primary]");
  if (primaryBtn && primaryActionState.enabled) {
    primaryBtn.addEventListener("click", async () => {
      const action = primaryBtn.dataset.actionPrimary;
      if (action === "next-page") {
        const nextPage = findNextReviewOrBlockedPage();
        if (nextPage) {
          await selectPage(nextPage.page_id);
        } else {
          setFeedback("当前已是最后一页，或没有更多待审 / 阻断页。", "");
        }
      } else if (action === "approve") {
        await runPageAction("approve");
      } else if (action === "request-evidence") {
        await runPageAction("request_evidence");
      } else if (action === "re-review") {
        await runPageAction("approve");
      }
    });
  }
}

// B3: 查找下一个待审 / 阻断页（优先阻断 P0 > P1，其次 needs_review）
function findNextReviewOrBlockedPage() {
  const pages = currentPages();
  const currentIndex = pages.findIndex((page) => page.page_id === state.currentPageId);
  if (currentIndex < 0) return null;

  const after = pages.slice(currentIndex + 1);
  const before = pages.slice(0, currentIndex);

  const pick = (list) => {
    const blocked = list.find((page) => page.blocking_count > 0);
    if (blocked) return blocked;
    const needsReview = list.find((page) => page.review_status === "needs_review" || page.review_status === "needs_evidence");
    return needsReview || null;
  };

  return pick(after) || pick(before) || null;
}

function renderActionStates() {
  if (!els.approvePage) return;
  const shellState = state.shellState || deriveShellState();
  const stageLabel = currentStageLabel();
  const page = currentPageCard();
  const hasPage = Boolean(page && state.pageDetail && shellState.id !== "generating" && state.viewMode !== "delivery");
  const pageReviewStatus = page?.review_status || "";
  const deliveryRecorded = Boolean(currentWorkspace().run_summary?.delivery?.delivered);
  const pendingRunApproval = (currentWorkspace().run_summary?.approvals || []).some(
    (task) => task.scope_type === "run" && task.status === "pending"
  );

  const canSubmitRunApproval =
    ["可交付", "待审批"].includes(stageLabel) &&
    Boolean(state.currentProjectId) &&
    !deliveryRecorded &&
    !pendingRunApproval;
  const showMarkDelivered = ["可交付", "已交付"].includes(stageLabel) && Boolean(state.currentProjectId);
  const canMarkDelivered =
    ["可交付", "已交付"].includes(stageLabel) &&
    Boolean(state.currentProjectId) &&
    !deliveryRecorded;
  const canReviewPage = hasPage && ["待审阅", "待补依据", "待审批", "可交付", "已交付"].includes(stageLabel);
  const canRequestEvidence = hasPage && ["待审阅", "待补依据"].includes(stageLabel);
  const canEscalatePageApproval = hasPage && ["待审阅", "待补依据", "可交付", "待审批"].includes(stageLabel);
  const canSaveNote = Boolean(state.currentProjectId) && hasPage;
  const shellReason = {
    setup: "先完成 setup，页面级动作才会开放。",
    "project-selection": "先选择项目，页面级动作才会开放。",
    loading: "当前仍在读取工作台，请稍候。",
    error: "当前工作台状态异常，先恢复状态再操作。",
    generating: `当前阶段仍在${stageLabel || "生成中"}，页面级动作尚未开放。`,
  }[shellState.id] || "";

  els.submitRunApproval.hidden = !canSubmitRunApproval;
  els.markDelivered.hidden = !showMarkDelivered;

  setButtonState(
    els.submitRunApproval,
    canSubmitRunApproval,
    canSubmitRunApproval ? "" : pendingRunApproval ? "当前方案项目已经有待审批任务。" : "当前阶段还不适合发起方案项目审批。"
  );
  setButtonState(
    els.markDelivered,
    canMarkDelivered,
    canMarkDelivered ? "" : deliveryRecorded ? "当前方案项目已经记录过交付结果。" : "当前还没有进入可交付阶段。"
  );
  els.markDelivered.textContent = deliveryRecorded ? "已记录交付" : "确认交付";

  setButtonState(
    els.approvePage,
    canReviewPage && pageReviewStatus !== "approved",
    hasPage ? "当前页还不能执行批准动作。" : (shellReason || "请先选择页面。")
  );
  setButtonState(
    els.rejectPage,
    canReviewPage && pageReviewStatus !== "rejected",
    hasPage ? "当前页还不能执行驳回动作。" : (shellReason || "请先选择页面。")
  );
  setButtonState(
    els.requestEvidence,
    canRequestEvidence,
    hasPage ? "当前页还不适合发起补依据动作。" : (shellReason || "请先选择页面。")
  );
  setButtonState(
    els.submitPageApproval,
    canEscalatePageApproval,
    hasPage ? "当前页还不适合升级审批。" : (shellReason || "请先选择页面。")
  );
  setButtonState(
    els.saveNote,
    canSaveNote,
    canSaveNote ? "" : (shellReason || "请先选择页面后再记录备注。")
  );
}

function renderDrawerState() {
  if (!els.bottomDrawer) return;
  const drawerStateView = state.drawerStateView || deriveDrawerState(state.shellState || deriveShellState());
  els.bottomDrawer.classList.toggle("collapsed", !drawerStateView.expanded);
  if (els.bottomDrawerTabs) {
    els.bottomDrawerTabs.querySelectorAll("[data-tab]").forEach((btn) => {
      const active = btn.dataset.tab === drawerStateView.tab;
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });
  }
  els.bottomDrawerPanels.forEach((panel) => {
    panel.hidden = panel.id !== `bottom-panel-${drawerStateView.tab}`;
  });
}

function renderAll() {
  syncDerivedState();
  renderHeader();
  renderProjectSwitcher();
  renderFilters();
  renderPageList();
  renderCriticalAlerts();
  renderPreview();
  renderDrawerState();
  renderReadiness();
  renderClaimCoverage();
  renderActivity();
  renderDecisionRail();
  renderActionStates();
  renderBlockFlag();
  renderActionBar();
  syncModeButtons();
}

async function loadProjects() {
  const payload = await requestJson("/api/runs");
  state.projects = payload.runs || [];
}

async function loadSetupStatus({ silent = false } = {}) {
  try {
    state.setupStatus = await requestJson("/api/setup-status");
    if (state.shellError?.scope === "setup") {
      state.shellError = null;
    }
  } catch (error) {
    state.setupStatus = null;
    state.shellError = {
      scope: "setup",
      title: "setup 状态读取失败",
      detail: error.message,
      recovery: "刷新页面后重试，或先检查本地 preview 服务。",
    };
  }
  if (!silent) renderAll();
}

async function loadRunState() {
  if (!state.currentProjectId) {
    state.runState = null;
    return;
  }
  state.runState = await requestJson(`/api/run-state/${encodeURIComponent(state.currentProjectId)}`);
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
  if (!setupReady()) {
    state.runState = null;
    state.workspace = null;
    state.pageDetail = null;
    state.activity = null;
    state.deliveryPreview = null;
    renderAll();
    return;
  }

  if (!state.currentProjectId) {
    state.runState = null;
    state.workspace = null;
    state.pageDetail = null;
    state.activity = null;
    state.deliveryPreview = null;
    renderAll();
    return;
  }

  state.loading = true;
  state.shellError = null;
  renderAll();
  try {
    const [runState, workspace, activity] = await Promise.all([
      loadRunState().then(() => state.runState),
      requestJson(`/api/workspace/${encodeURIComponent(state.currentProjectId)}`),
      requestJson(`/api/workspace/${encodeURIComponent(state.currentProjectId)}/activity`),
    ]);
    state.runState = runState;
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
    state.runState = null;
    state.workspace = null;
    state.pageDetail = null;
    state.activity = null;
    state.deliveryPreview = null;
    state.shellError = {
      scope: "workspace",
      title: "当前方案项目无法载入",
      detail: error.message,
      recovery: "重新选择项目，或刷新页面后重试。",
    };
  } finally {
    state.loading = false;
    renderAll();
  }
}

async function refreshCurrentProject() {
  await loadSetupStatus({ silent: true });
  if (!setupReady()) {
    state.runState = null;
    state.workspace = null;
    state.pageDetail = null;
    state.activity = null;
    state.deliveryPreview = null;
    renderAll();
    return;
  }
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
  const page = currentPageCard();
  const actionLabel = describeMutationAction(action);
  const targetLabel = page ? `${String(page.order).padStart(2, "0")} 页《${page.title}》` : "当前页面";
  setFeedback(`正在处理：${targetLabel} · ${actionLabel}`, "");
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
    setFeedback(`${targetLabel}已完成“${actionLabel}”，工作台正在刷新。`, "success");
    await refreshCurrentProject();
  } catch (error) {
    setFeedback(`${targetLabel}执行“${actionLabel}”失败：${error.message}`, "danger");
  }
}

async function runRunAction(action, extra = {}) {
  if (!state.currentProjectId) return;
  const actionLabel = describeMutationAction(action);
  const targetLabel = currentWorkspace().project_title || state.currentProjectId || "当前项目";
  setFeedback(`正在处理：${targetLabel} · ${actionLabel}`, "");
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
    setFeedback(`${targetLabel}已完成“${actionLabel}”，工作台正在刷新。`, "success");
    await refreshCurrentProject();
  } catch (error) {
    setFeedback(`${targetLabel}执行“${actionLabel}”失败：${error.message}`, "danger");
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
  // B4: bottom-drawer tab switching + collapse toggle
  if (els.bottomDrawerTabs) {
    els.bottomDrawerTabs.addEventListener("click", (event) => {
      const tab = event.target.closest("[data-tab]");
      if (!tab) return;
      const tabName = tab.dataset.tab;
      const sameTab = tabName === state.drawerTab;
      state.drawerExpanded = sameTab ? !state.drawerExpanded : true;
      state.drawerTab = tabName;
      els.bottomDrawerTabs.querySelectorAll("[data-tab]").forEach((btn) => {
        btn.setAttribute("aria-selected", btn === tab ? "true" : "false");
      });
      els.bottomDrawerPanels.forEach((panel) => {
        panel.hidden = panel.id !== `bottom-panel-${tabName}`;
      });
      els.bottomDrawer.classList.toggle("collapsed", !state.drawerExpanded);
      updateLocation();
    });
  }
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
    state.shellError = null;
    updateLocation();
    if (!state.currentProjectId) {
      state.runState = null;
      state.workspace = null;
      state.pageDetail = null;
      state.activity = null;
      state.deliveryPreview = null;
      renderAll();
      return;
    }
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
    await loadSetupStatus({ silent: true });
    if (setupReady()) {
      await loadProjects();
    }
    renderProjectSwitcher();
    if (setupReady() && state.currentProjectId) {
      await loadWorkspace();
    } else {
      renderAll();
    }
  } catch (error) {
    state.shellError = {
      scope: "setup",
      title: "工作台加载失败",
      detail: error.message,
      recovery: "刷新页面后重试。",
    };
    renderAll();
  }
}

boot();
