"""Bounded frontend reads and ownership; synthetic fixtures, no model calls."""
import json
from urllib.parse import urlencode

import pytest

from deck_master import icons
from test_icon_browser import icon_browser
from test_icon_quality import accept, confirm, dispatch, icon_store, input_for, start

pytestmark = pytest.mark.browser


def test_icon_parent_owns_status_poll_and_hidden_resume(icon_browser):
    from playwright.sync_api import expect
    page, store, _ = icon_browser
    recipe = confirm(store, input_for(store, method='standard'))
    task = dispatch(store, recipe)[0]
    start(store, task)
    draft = icons.draft(store.project_root, recipe_id=recipe['recipe_id'], page_id='p01')
    candidate_id = accept(store, task, draft['svg'].encode())['candidate_ids'][0]
    requests = []
    def status(route):
        requests.append(route.request.url)
        route.fulfill(json={'status': 'running', 'candidate_id': candidate_id})
    page.route('**/api/candidate-preview/status?*', status)
    query = dict(part.split('=', 1) for part in page.url.split('#')[1].split('&'))
    query.update(revision=store.current_revision_id(), candidate=candidate_id)
    page.goto(page.url.split('#')[0] + '#' + urlencode(query))
    expect(page.locator('.candidate-icon-review [role=status]')).to_contain_text('正在编译')
    page.wait_for_timeout(4200)
    assert len(requests) == 3  # One initial read and one parent timer.
    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))")
    hidden_count = len(requests)
    page.wait_for_timeout(4200)
    assert len(requests) == hidden_count
    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_timeout(300)
    assert len(requests) == hidden_count + 1


def test_current_work_lazy_evidence_and_stable_paired_refresh(icon_browser):
    page, _, _ = icon_browser
    page.goto('/'.join(page.url.split('/')[:3]) + '/v2/project.js')
    result = page.evaluate("""async () => {
      const {currentWork} = await import('/v2/current-work.js');
      const {Project} = await import('/v2/project.js');
      const work={identity:{project_id:'p',artifact_revision_id:'r',control_revision_id:'c'},
        next:{actions:[],primary_action:null,title:'当前工作',label:'阅读',surface:'content'},
        optional:[],scope:{known:true},review:{status:'missing'},blockers:[]};
      const app={summary:{project_id:'p',revision_id:'r',current_work:work,pages:[]},
        health:{ui_capabilities:['workbench_summary.v2']},route:{revision:'r'},generation:1};
      const node=currentWork(app);document.body.replaceChildren(node);
      const evidence=node.querySelector('details'), pre=evidence.querySelector('pre');
      const initial=pre.textContent; evidence.open=true;
      await new Promise(resolve=>setTimeout(resolve,0));
      const button=node.querySelector('button');button.focus();
      for(let i=0;i<10;i++)await Project.prototype.refreshCurrentWork.call(app,{project_id:'p',control_revision_id:'c'},()=>true,app.summary);
      return {initial,formatted:pre.textContent,connected:node.isConnected,open:evidence.open,focused:document.activeElement===button};
    }""")
    assert result['initial'] == ''
    assert json.loads(result['formatted'])['identity']['project_id'] == 'p'
    assert result['connected'] and result['open'] and result['focused']


def test_method_reader_keeps_dom_but_refreshes_current_availability(icon_browser):
    page, _, _ = icon_browser
    page.goto('/'.join(page.url.split('/')[:3]) + '/v2/project.js')
    result = page.evaluate("""async () => {
      const {taskMethods}=await import('/v2/insight-reading.js');
      const original=fetch;let available=true, reads=0;
      window.fetch=async()=>{reads++;return new Response(JSON.stringify({data:{frozen_status:'recorded',resources:[],availability:{available}}}),{status:200});};
      const app={disposables:[]};
      try {
        const node=taskMethods(app,'task','revision',{routeOwned:false});document.body.replaceChildren(node);
        await node.refresh();const body=node.firstChild;
        for(let i=0;i<10;i++)await node.refresh();
        const stable=node.firstChild===body;available=false;await node.refresh();
        const changed=node.firstChild!==body&&node.textContent.includes('false');
        node.dispose();await node.refresh();return {stable,changed,reads,disposables:app.disposables.length};
      } finally {window.fetch=original;}
    }""")
    assert result == {'stable': True, 'changed': True, 'reads': 12, 'disposables': 0}


def test_thumbnail_backoff_has_single_finite_wait_budget(icon_browser):
    page, _, _ = icon_browser
    page.goto('/'.join(page.url.split('/')[:3]) + '/v2/project.js')
    result = page.evaluate("""async () => {
      const {ImagePool}=await import('/v2/images.js');const pool=new ImagePool();
      const original=setTimeout,waits=[];let reads=0;
      window.setTimeout=(fn,delay)=>{waits.push(delay);queueMicrotask(fn);return 1;};
      pool.fetch=async()=>{reads++;return {status:'queued',retry_after_ms:75};};
      try {await pool.load({kind:'thumb',controller:new AbortController()}, {path:'.deckmaster/objects/'+ 'a'.repeat(64)+'.png',sha256:'a'.repeat(64)},false,0,false);}
      catch(error){return {reads,waits,message:error.message};}
      finally{window.setTimeout=original;}
    }""")
    assert sum(result['waits']) == 12000
    assert max(result['waits']) <= 1000
    assert result['reads'] < 25
    assert '仍在准备' in result['message']


def test_hidden_runs_and_unopened_handoffs_do_not_read_on_ticks(icon_browser):
    page, _, _ = icon_browser
    page.goto('/'.join(page.url.split('/')[:3]) + '/v2/project.js')
    page.add_script_tag(url='/v2/icons.js')
    result = page.evaluate("""async () => {
      const {runDesk}=await import('/v2/run-desk.js');
      const {changeHandoffs}=await import('/v2/change-handoff.js');
      document.documentElement.dataset.workbenchUi='studio';
      const task={task_id:'t',operation_id:'o',status:'completed',kind:'compose',scope_pages:[],instruction:'read',human_actions:[],created_at:'2026-01-01T00:00:00Z'};
      const value={tasks:[task],groups:[],revision_id:'r',pagination:{total:1,next_offset:null}};
      const app={root:document.createElement('div'),info:{project_identity:'synthetic-runs'},summary:{pages:[]},
        route:{revision:'r'},health:{ui_capabilities:['run_desk.v1']},disposables:[]};
      const original=fetch;let reads=0;
      window.fetch=async()=>{reads++;return new Response(JSON.stringify(value),{status:200});};
      const settle=()=>new Promise(resolve=>setTimeout(resolve,0));
      try {
        const handoffs=changeHandoffs(app,[]),node=runDesk(app,{runPage:value,runDetail:null});
        document.body.replaceChildren(node);await settle();const row=node.querySelector('.run-task');
        for(let i=0;i<10;i++){app.root.dispatchEvent(new CustomEvent('summary-refreshed'));await settle();}
        const stable=node.querySelector('.run-task')===row, registrations=app.disposables.length;
        node.setActive(false);const before=reads;
        for(let i=0;i<10;i++){app.root.dispatchEvent(new CustomEvent('summary-refreshed'));await settle();}
        const hiddenReads=reads-before;node.setActive(true);await settle();
        return {stable,registrations,hiddenReads,resumeReads:reads-before};
      }finally{app.disposables.forEach(fn=>fn());window.fetch=original;}
    }""")
    assert result == {'stable': True, 'registrations': 2, 'hiddenReads': 0, 'resumeReads': 1}


def test_candidate_a_b_a_delayed_request_and_hidden_inflight_resume(icon_browser):
    """Selection changes queue GET only; resumed slow GET does not inherit a timer."""
    from playwright.sync_api import expect
    from urllib.parse import parse_qs, urlsplit

    page, store, _ = icon_browser
    ids = []
    for index in range(2):
        value = input_for(store, method='standard')
        value['instruction'] += str(index)
        recipe = confirm(store, value)
        task = dispatch(store, recipe)[0]
        start(store, task)
        draft = icons.draft(store.project_root, recipe_id=recipe['recipe_id'], page_id='p01')
        ids.append(accept(store, task, draft['svg'].encode())['candidate_ids'][0])
    reads, posts = [], []

    def status(route):
        reads.append(route)
        if len(reads) == 1:
            route.fulfill(json={'status': 'not_requested', 'candidate_id': ids[0]})

    page.route('**/api/candidate-preview/status?*', status)
    page.route('**/api/candidate-preview/request', lambda route: posts.append(route))
    query = dict(part.split('=', 1) for part in page.url.split('#')[1].split('&'))
    query.update(revision=store.current_revision_id(), candidate=ids[0])
    page.goto(page.url.split('#')[0] + '#' + urlencode(query))
    expect(page.locator('.candidate-icon-review [role=status]')).to_contain_text('尚未')
    page.get_by_role('button', name='生成候选实际 PPT', exact=True).click()
    page.wait_for_timeout(100)
    assert len(posts) == 1
    for candidate in [ids[1], ids[0]]:
        page.get_by_label('选择本页候选', exact=True).select_option(candidate)
        expect(page.locator('.candidate-desk')).to_have_attribute('data-candidate-id', candidate)
    assert len(reads) == 1
    posts[0].fulfill(json={'status': 'running', 'candidate_id': ids[0]})
    page.wait_for_timeout(200)
    assert len(reads) == 2
    assert parse_qs(urlsplit(reads[1].request.url).query)['candidate_id'] == [ids[0]]
    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))")
    page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'))")
    reads[1].fulfill(json={'status': 'running', 'candidate_id': ids[0]})
    page.wait_for_timeout(200)
    assert len(reads) == 3
    # Keep the resumed request pending past the old response's timer deadline.
    page.wait_for_timeout(2200)
    assert len(reads) == 3
    reads[2].fulfill(json={'status': 'not_requested', 'candidate_id': ids[0]})
    page.wait_for_timeout(300)
    assert len(reads) == 3
    assert len(posts) == 1  # No selection/resume path retries the explicit POST.
