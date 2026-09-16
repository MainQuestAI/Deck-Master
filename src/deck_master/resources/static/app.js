/* Deck Master Review Workbench — rebuilt core (T05, read-only). */
"use strict";

(function () {
  const state = { view: null, activePage: null, activeSlot: "content", drafts: new Map() };

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
      item.tabIndex=0;item.setAttribute('role','button');item.onkeydown=e=>{if(e.key==='Enter' || e.key===' ')item.click();};
      if (page.broken) item.classList.add("broken");
      if (page.page_id === state.activePage) item.classList.add("is-active");
      item.addEventListener("click", () => {
        if(state.dirty && state.editBase)state.drafts.set(state.activePage,{base:state.editBase,values:Array.from(document.querySelectorAll('#editor-fields textarea')).map(input=>input.value)});
        state.activePage = page.page_id;
        renderPageList(view);
        state.dirty=false;
        renderPage(page);
        renderSlots(page);
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
    const customer = page.page.customer_visible;
    document.getElementById('page-subtitle').textContent=customer.subtitle || '';
    const append=(tag,text,parent=body)=>{const node=document.createElement(tag);node.textContent=text || '';parent.appendChild(node);return node;};
    for(const block of customer.body_blocks || []) {
      if(block.heading || block.title)append('h2',block.heading || block.title);
      if(block.text)append('p',block.text);
      if(block.items){const list=append('ul','');for(const item of block.items)append('li',item.text,list);}
      if(block.type==='table'){
        const table=append('table','');const header=append('tr','',table);
        for(const col of block.columns)append('th',col.label,header);
        for(const row of block.rows){const tr=append('tr','',table);for(const col of block.columns)append('td',(row.cells.find(c=>c.column_id===col.id)||{}).display_text,tr);}
      }
    }
    for(const key of ['callouts','labels','footnotes'])for(const item of customer[key] || [])append('p',item.text);
    if(!state.dirty)renderEditor(page);
  }

  function renderEditor(page){
    const form=document.getElementById('editor-fields');form.replaceChildren();
    const draft=state.drafts.get(page.page_id);
    state.editBase=draft ? draft.base : {revision:state.view.revision_id,hash:page.slots.content.sha256,page:JSON.parse(JSON.stringify(page.page))};
    let fieldIndex=0;
    for(const atom of page.visible_atoms){
      if(typeof atom.text!=='string')continue;
      const label=document.createElement('label');label.textContent=atom.kind;
      const input=document.createElement('textarea');input.value=draft ? draft.values[fieldIndex++] : atom.text;input.dataset.pointer=atom.pointer;input.rows=2;
      input.addEventListener('input',()=>{state.dirty=true;});label.appendChild(input);form.appendChild(label);
    }
    if(draft)state.dirty=true;
  }

  async function post(path,data){
    const session=await fetch('/api/session').then(r=>r.json());
    const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Deck-Token':session.token},body:JSON.stringify(data)});
    const result=await response.json();if(!response.ok)throw new Error(result.error || response.status);return result;
  }
  function notice(text){document.getElementById('action-status').textContent=text;}
  async function action(fn){try{const result=await fn();notice(result.output_dir ? '已导出：'+result.output_dir : result.status || '已完成');await refresh();}catch(error){notice(error.message);}}
  function pointerSet(root,pointer,value){const keys=pointer.slice(1).split('/').map(k=>k.replace(/~1/g,'/').replace(/~0/g,'~'));let obj=root;for(const k of keys.slice(0,-1))obj=obj[k];obj[keys.at(-1)]=value;}
  function bindActions(){
    document.getElementById('save-content').onclick=()=>action(async()=>{
      if(!state.editBase)throw new Error('先选择页面');
      const page=JSON.parse(JSON.stringify(state.editBase.page));
      for(const input of document.querySelectorAll('#editor-fields textarea'))pointerSet(page,input.dataset.pointer,input.value);
      const result=await post('/api/edit',{page,base_revision:state.editBase.revision,page_hash:state.editBase.hash,operation_id:crypto.randomUUID()});
      state.dirty=false;state.drafts.delete(state.activePage);return result;
    });
    document.getElementById('send-feedback').onclick=()=>action(()=>{
      const instruction=document.getElementById('feedback').value.trim();if(!instruction)throw new Error('请输入具体修改意见');
      return post('/api/feedback',{page_id:state.activePage,instruction,base_revision:state.view.revision_id,page_hash:state.view.pages.find(p=>p.page_id===state.activePage).slots.content.sha256});
    });
    document.getElementById('export-working').onclick=()=>action(()=>post('/api/export',{purpose:'working'}));
    document.getElementById('refresh').onclick=refresh;
    document.getElementById('show-history').onclick=async()=>{
      const data=await fetch('/api/history').then(r=>r.json());const list=document.getElementById('history-list');list.replaceChildren();
      for(const entry of data.revisions){const button=document.createElement('button');button.textContent=entry.created_at+' · '+entry.change.description;button.onclick=()=>action(()=>post('/api/restore',{revision_id:entry.revision_id,base_revision:state.view.revision_id,operation_id:crypto.randomUUID()}));list.appendChild(button);}
    };
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
      const cancel=document.createElement('button');cancel.textContent='取消';cancel.onclick=()=>action(()=>post('/api/cancel',{task_id:task.task_id,reason:'用户工作台取消'}));li.appendChild(cancel);
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
        document.querySelectorAll(".slot-tab").forEach((item) => {item.classList.remove("is-active");item.setAttribute("aria-selected","false");});
        document.querySelectorAll(".slot").forEach((item) => {item.classList.remove("is-active");item.setAttribute("aria-selected","false");});
        tab.classList.add("is-active");tab.setAttribute("aria-selected","true");
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
      const download=document.getElementById('download-ppt');
      download.hidden=!view.outputs.pptx;
      if(view.outputs.pptx)download.href=fileUrl(view.outputs.pptx);
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
  bindActions();
  refresh();
})();
