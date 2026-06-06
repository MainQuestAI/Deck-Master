const state = {
  deck: null,
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
  first: document.querySelector("#first-page"),
  prev: document.querySelector("#prev-page"),
  next: document.querySelector("#next-page"),
  last: document.querySelector("#last-page"),
};

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  return data;
}

async function loadDeck() {
  try {
    state.deck = await requestJson("/api/deck");
    els.title.textContent = state.deck.title;
    els.meta.textContent = `${state.deck.run_id} · ${state.deck.status} · ${state.deck.pages.length} pages`;
    renderList();
    selectPage(0);
  } catch (error) {
    els.frame.innerHTML = `<div class="empty error">${escapeHtml(error.message)}</div>`;
  }
}

function renderList() {
  els.list.innerHTML = "";
  state.deck.pages.forEach((page, index) => {
    const item = document.createElement("button");
    item.className = `page-card decision-${page.decision}`;
    item.dataset.active = index === state.selectedIndex ? "true" : "false";
    item.innerHTML = `
      <span class="page-no">${String(page.order).padStart(2, "0")}</span>
      <span>
        <strong>${escapeHtml(page.title || page.page_id)}</strong>
        <small>${escapeHtml(page.source_type)} · ${escapeHtml(page.decision)}</small>
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
    "Alternatives": summarizeAlternatives(page.alternatives),
    "Generation task": page.generation_task ? page.generation_task.task_id : "",
    "Original PPT": page.source_pptx || "",
    "Slide index": page.source_slide_index ?? "",
    "Preview path": page.preview_path,
    "Asset": page.asset_exists ? "Available" : page.asset_error,
  });

  if (page.asset_exists) {
    els.frame.innerHTML = `<img src="${page.preview_url}?t=${Date.now()}" alt="${escapeHtml(page.title || page.page_id)}">`;
  } else {
    els.frame.innerHTML = `<div class="empty error"><strong>Preview unavailable</strong><p>${escapeHtml(page.asset_error)}</p></div>`;
  }
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
    const updated = await requestJson(`/api/page/${page.page_id}/decision`, {
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

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

els.save.addEventListener("click", saveDecision);
els.first.addEventListener("click", () => selectPage(0));
els.prev.addEventListener("click", () => selectPage(state.selectedIndex - 1));
els.next.addEventListener("click", () => selectPage(state.selectedIndex + 1));
els.last.addEventListener("click", () => selectPage(state.deck.pages.length - 1));
document.addEventListener("keydown", (event) => {
  if (event.key === "ArrowLeft") selectPage(state.selectedIndex - 1);
  if (event.key === "ArrowRight") selectPage(state.selectedIndex + 1);
});

loadDeck();
