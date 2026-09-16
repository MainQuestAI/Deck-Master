/* Deck Master Review Workbench — rebuilt core (T05, read-only). */
"use strict";

(function () {
  const state = { view: null, activePage: null, activeSlot: "content" };

  async function fetchView() {
    const response = await fetch("/api/view");
    if (!response.ok) throw new Error("view unavailable: " + response.status);
    return response.json();
  }

  function fileUrl(ref) {
    if (!ref) return null;
    const query = new URLSearchParams({ path: ref.path, sha256: ref.sha256 });
    return "/api/file?" + query.toString();
  }

  function renderMeta(view) {
    document.getElementById("meta-project").textContent = view.project_id || "—";
    document.getElementById("meta-revision").textContent = (view.revision_id || "—").slice(0, 12);
    document.getElementById("meta-pages").textContent = String(view.page_count);
    document.getElementById("meta-status").textContent = view.view_status || "—";
  }

  function renderPageList(view) {
    const list = document.getElementById("page-list");
    list.innerHTML = "";
    if (!view.pages.length) {
      const empty = document.createElement("li");
      empty.className = "mono";
      empty.textContent = "0 pages · awaiting_host";
      list.appendChild(empty);
      return;
    }
    view.pages.forEach((page, index) => {
      const item = document.createElement("li");
      item.textContent = `p${index + 1} · ${page.page_id}`;
      item.dataset.pageId = page.page_id;
      if (page.broken) item.classList.add("broken");
      if (page.page_id === state.activePage) item.classList.add("is-active");
      item.addEventListener("click", () => {
        state.activePage = page.page_id;
        renderPageList(view);
        renderPage(page);
      });
      list.appendChild(item);
    });
    if (!state.activePage && view.pages.length) {
      state.activePage = view.pages[0].page_id;
      renderPageList(view);
      renderPage(view.pages[0]);
    }
  }

  function renderPage(page) {
    document.getElementById("page-title").textContent = page.broken ? "页面损坏" : page.title || "(无标题)";
    document.getElementById("page-subtitle").textContent = "";
    const body = document.getElementById("page-body");
    body.innerHTML = "";
    if (page.broken) {
      const note = document.createElement("p");
      note.className = "mono";
      note.textContent = page.detail || "unreadable";
      body.appendChild(note);
      return;
    }
    const atoms = page.visible_atoms || [];
    // Group atoms: title/subtitle rendered separately; body blocks in order.
    const customer = pageData || {};
    (atoms.filter((atom) => atom.kind === "callout")).forEach((atom) => {
      const p = document.createElement("p");
      p.className = "block-heading";
      p.textContent = atom.text;
      body.appendChild(p);
    });
    (atoms.filter((atom) => atom.kind === "block_heading")).forEach((atom) => {
      const h = document.createElement("h2");
      h.className = "block-heading";
      h.textContent = atom.text;
      body.appendChild(h);
    });
    (atoms.filter((atom) => atom.kind === "item_text" || atom.kind === "paragraph")).forEach((atom) => {
      const li = document.createElement("li");
      li.textContent = atom.text;
      body.appendChild(li);
    });
    const tableCells = atoms.filter((atom) => atom.kind === "table_cell");
    if (tableCells.length) {
      const table = document.createElement("table");
      const row = document.createElement("tr");
      tableCells.forEach((cell) => {
        const td = document.createElement("td");
        td.textContent = cell.text;
        row.appendChild(td);
      });
      table.appendChild(row);
      body.appendChild(table);
    }
    (atoms.filter((atom) => atom.kind === "footnote" || atom.kind === "label")).forEach((atom) => {
      const p = document.createElement("p");
      p.className = "mono";
      p.textContent = atom.text;
      body.appendChild(p);
    });
  }

  function renderSlots(page) {
    const waiting = {
      blueprint: page.slots && page.slots.blueprint,
      svg: page.slots && (page.slots.svg || page.slots.svg_preview),
      ppt: page.slots && (page.slots.ppt_preview || page.slots.pptx),
    };
    Object.entries(waiting).forEach(([slot, ref]) => {
      const placeholder = document.querySelector(`.slot-waiting[data-slot="${slot}"]`);
      const panel = document.getElementById(`slot-${slot}`);
      const existing = panel.querySelector("img, object");
      if (existing) existing.remove();
      if (ref) {
        if (placeholder) placeholder.style.display = "none";
        const img = document.createElement("img");
        img.src = fileUrl(ref);
        img.alt = slot + " view";
        panel.appendChild(img);
      } else {
        if (placeholder) placeholder.style.display = "";
      }
    });
  }

  function renderTasks(view) {
    const list = document.getElementById("task-list");
    list.innerHTML = "";
    (view.pending_tasks || []).forEach((task) => {
      const li = document.createElement("li");
      const kind = document.createElement("span");
      kind.className = "kind";
      kind.textContent = task.kind || "task";
      const status = document.createElement("span");
      status.className = "status";
      status.textContent = task.status || "";
      li.appendChild(kind);
      li.appendChild(status);
      const instruction = document.createElement("div");
      instruction.textContent = (task.instruction || "").slice(0, 160);
      li.appendChild(instruction);
      list.appendChild(li);
    });
    if (!(view.pending_tasks || []).length) {
      const li = document.createElement("li");
      li.textContent = "No pending Host tasks.";
      list.appendChild(li);
    }
  }

  function bindTabs() {
    document.querySelectorAll(".slot-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".slot-tab").forEach((item) => item.classList.remove("is-active"));
        document.querySelectorAll(".slot").forEach((item) => item.classList.remove("is-active"));
        tab.classList.add("is-active");
        document.getElementById(`slot-${tab.dataset.slot}`).classList.add("is-active");
      });
    });
  }

  async function refresh() {
    try {
      const view = await fetchView();
      state.view = view;
      if (state.activePage && !view.pages.some((page) => page.page_id === state.activePage)) {
        state.activePage = null;
      }
      renderMeta(view);
      renderPageList(view);
      const active = view.pages.find((page) => page.page_id === state.activePage);
      if (active) {
        renderPage(active);
        renderSlots(active);
      }
      renderTasks(view);
    } catch (error) {
      document.getElementById("meta-status").textContent = "unavailable";
      const list = document.getElementById("page-list");
      list.innerHTML = "";
      const li = document.createElement("li");
      li.className = "mono";
      li.textContent = "服务不可达：" + error.message;
      list.appendChild(li);
    }
  }

  bindTabs();
  refresh();
})();
