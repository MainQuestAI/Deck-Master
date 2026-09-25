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
        state.region=null;
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
      if(block.items){const items=(rows,parent)=>{const list=append('ul','',parent);for(const item of rows){const li=append('li',item.text,list);if(item.items)items(item.items,li);}};items(block.items,body);}
      if(block.type==='table'){
        const table=append('table','');const header=append('tr','',table);
        for(const col of block.columns)append('th',col.label,header);
        for(const row of block.rows){const tr=append('tr','',table);for(const col of block.columns)append('td',(row.cells.find(c=>c.column_id===col.id)||{}).display_text,tr);}
      }
    }
    for(const key of ['callouts','labels','footnotes'])for(const item of customer[key] || [])append('p',item.text);
    const reviews=document.getElementById('review-list');reviews.replaceChildren();
    for(const review of state.view.reviews.filter(r=>r.page_ids?.includes(page.page_id))){
      const box=document.createElement('div');box.className='review-record';
      const title=document.createElement('strong');title.textContent=`${review.current_output ? '当前产物' : '历史产物'} · ${review.kind} · ${review.status}`;box.appendChild(title);
      for(const text of [...(review.observations || []),...(review.findings || []).map(f=>JSON.stringify(f))]){const line=document.createElement('p');line.textContent=text;box.appendChild(line);}
      reviews.appendChild(box);
    }
    if(!state.dirty)renderEditor(page);
  }

  function renderEditor(page){
    const form=document.getElementById('editor-fields');form.replaceChildren();
    const draft=state.drafts.get(page.page_id);
    state.editBase=draft ? draft.base : {revision:state.view.revision_id,hash:page.slots.content.sha256,page:JSON.parse(JSON.stringify(page.page))};
    let fieldIndex=0;
    const field=(labelText,pointer,value,json=false)=>{
      const label=document.createElement('label');label.textContent=labelText;
      const input=document.createElement('textarea');input.value=draft ? draft.values[fieldIndex++] : (value === null ? '' : String(value));input.dataset.pointer=pointer;input.dataset.json=String(json);input.dataset.rawType=typeof value;input.rows=json ? 1 : 2;
      input.addEventListener('input',()=>{state.dirty=true;});label.appendChild(input);form.appendChild(label);
    };
    for(const atom of page.visible_atoms){
      if(typeof atom.text!=='string')continue;
      field(atom.kind,atom.pointer,atom.text);
      if(atom.kind==='table_cell'){
        const parent=atom.pointer.slice(0,atom.pointer.lastIndexOf('/'));
        const cell=parent.slice(1).split('/').reduce((obj,key)=>obj[key],state.editBase.page);
        if(Object.hasOwn(cell,'value'))field('表格原始值（与显示文字分别保存；留空表示空值）',parent+'/value',cell.value,true);
        if(Object.hasOwn(cell,'unit'))field('表格单位',parent+'/unit',cell.unit);
      }
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
      for(const input of document.querySelectorAll('#editor-fields textarea'))pointerSet(page,input.dataset.pointer,input.dataset.json==='true' ? (input.value==='' ? null : input.dataset.rawType!=='string' && Number.isFinite(Number(input.value)) ? Number(input.value) : input.value) : input.value);
      const result=await post('/api/edit',{page,base_revision:state.editBase.revision,page_hash:state.editBase.hash,operation_id:crypto.randomUUID()});
      state.dirty=false;state.drafts.delete(state.activePage);return result;
    });
    document.getElementById('send-feedback').onclick=()=>action(()=>{
      let instruction=document.getElementById('feedback').value.trim();if(!instruction)throw new Error('请输入具体修改意见');
      if(state.region){
        if(state.region.revision!==state.view.revision_id)throw new Error('页面版本已变化，请重新框选区域；修改意见已保留。');
        instruction+='\n选中区域（相对图像左上角，0–1归一化坐标）：'+JSON.stringify(state.region);
      }
      return post('/api/feedback',{page_id:state.activePage,instruction,base_revision:state.view.revision_id,page_hash:state.view.pages.find(p=>p.page_id===state.activePage).slots.content.sha256});
    });
    document.getElementById('clear-region').onclick=()=>{state.region=null;document.querySelectorAll('.region-box').forEach(e=>e.remove());document.getElementById('feedback-region').textContent='区域已清除';};
    document.getElementById('export-working').onclick=()=>action(()=>post('/api/export',{purpose:'working'}));
    document.getElementById('refresh').onclick=refresh;
    document.getElementById('show-history').onclick=async()=>{
      const data=await fetch('/api/history').then(r=>r.json());const list=document.getElementById('history-list');list.replaceChildren();
      for(const entry of data.revisions){const button=document.createElement('button');button.textContent=entry.revision_id.slice(0,12)+' · '+entry.change.description;button.onclick=()=>action(()=>post('/api/restore',{revision_id:entry.revision_id,base_revision:state.view.revision_id,operation_id:crypto.randomUUID()}));list.appendChild(button);}
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
      const existing = panel.querySelector(".image-wrap, img, object");
      if (existing) existing.remove();
      if (ref) {
        if (placeholder) placeholder.style.display = "none";
        const img = document.createElement("img");
        img.src = fileUrl(ref);
        img.alt = slot + " view";
        const wrap=document.createElement('div');wrap.className='image-wrap';wrap.appendChild(img);panel.appendChild(wrap);img.draggable=false;
        let start=null;
        const point=e=>{const r=img.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))];};
        img.onpointerdown=e=>{start=point(e);img.setPointerCapture(e.pointerId);e.preventDefault();};
        img.onpointerup=e=>{if(!start)return;const end=point(e);const rect={x:Math.min(start[0],end[0]),y:Math.min(start[1],end[1]),width:Math.abs(start[0]-end[0]),height:Math.abs(start[1]-end[1])};start=null;
          if(rect.width<.005 || rect.height<.005)return;
          document.querySelectorAll('.region-box').forEach(el=>el.remove());const box=document.createElement('div');box.className='region-box';Object.assign(box.style,{left:rect.x*100+'%',top:rect.y*100+'%',width:rect.width*100+'%',height:rect.height*100+'%'});wrap.appendChild(box);
          state.region={page_id:page.page_id,slot,revision:state.view.revision_id,artifact:ref,...rect};document.getElementById('feedback-region').textContent='已框选 '+slot+' 区域；填写意见后提交。';
        };
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

  function applyZoom() {
    document.querySelectorAll(".slot img").forEach((img) => {
      img.style.width = state.zoom === null ? "" : state.zoom * 100 + "%";
    });
    const label = document.getElementById("zoom-level");
    if (label) label.textContent = state.zoom === null ? "适配宽度" : Math.round(state.zoom * 100) + "%";
  }

  function bindZoom() {
    state.zoom = state.zoom ?? null;
    const out = document.getElementById("zoom-out");
    const inn = document.getElementById("zoom-in");
    const fit = document.getElementById("zoom-fit");
    if (!out || !inn || !fit) return;
    out.onclick = () => { state.zoom = Math.max(0.25, (state.zoom ?? 1) / 1.25); applyZoom(); };
    inn.onclick = () => { state.zoom = Math.min(4, (state.zoom ?? 1) * 1.25); applyZoom(); };
    fit.onclick = () => { state.zoom = null; applyZoom(); };
  }

  function bindKeys() {
    document.addEventListener("keydown", (event) => {
      if (event.target && /^(TEXTAREA|INPUT|SELECT)$/.test(event.target.tagName)) return;
      if (!state.view) return;
      const pages = state.view.pages || [];
      if (!pages.length) return;
      const index = pages.findIndex((page) => page.page_id === state.activePage);
      let target = null;
      if (event.key === "ArrowRight") target = pages[(index + 1) % pages.length];
      else if (event.key === "ArrowLeft") target = pages[(index - 1 + pages.length) % pages.length];
      if (target) {
        event.preventDefault();
        document.querySelector(`#page-list li[data-page-id="${target.page_id}"]`)?.click();
      }
    });
  }

  function renderReconciliation(view) {
    let banner = document.getElementById("reconciliation-banner");
    const needsUpdate = view.input_alignment === "needs_reconciliation";
    if (!needsUpdate) {
      if (banner) banner.remove();
      return;
    }
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "reconciliation-banner";
      banner.className = "reconciliation-banner";
      const main = document.querySelector("main") || document.body;
      main.prepend(banner);
    }
    banner.replaceChildren();
    const title = document.createElement("strong");
    title.textContent = (view.reconciliation && view.reconciliation.notice) || "待按新要求更新";
    banner.appendChild(title);
    const reason = document.createElement("span");
    reason.className = "mono";
    reason.textContent = (view.reconciliation && view.reconciliation.reason)
      ? " · " + view.reconciliation.reason : "";
    banner.appendChild(reason);
    banner.appendChild(Object.assign(document.createElement("span"), {
      className: "mono", textContent: " · 编辑与交付已暂停；请先完成 inputs update 派发的修订任务。",
    }));
    // Read-only while reconciliation is pending: no edit controls.
    const editor = document.getElementById("editor-fields");
    if (editor) editor.replaceChildren();
    const save = document.getElementById("save-content");
    if (save) save.disabled = true;
    const feedback = document.getElementById("send-feedback");
    if (feedback) feedback.disabled = true;
  }

  async function refresh() {
    try {
      const view = await fetchView();
      state.view = view;
      if (state.activePage && !view.pages.some((page) => page.page_id === state.activePage)) {
        state.activePage = null;
      }
      renderMeta(view);
      renderReconciliation(view);
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
  bindZoom();
  bindKeys();
  refresh();
})();
