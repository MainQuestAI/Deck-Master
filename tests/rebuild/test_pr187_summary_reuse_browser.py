"""#142: reuse only a fresh poll's matching artifact/control observation."""
import shutil

import pytest
from playwright.sync_api import sync_playwright, expect

from deck_master.samples import create_gallery_sample
from deck_master.web import WorkbenchServer

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('route', ['v2', 'studio'])
def test_thirty_page_idle_keeps_three_summary_reads(tmp_path, route):
    project = tmp_path / 'project'
    create_gallery_sample(project, page_count=30, readonly=False)
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            page = browser.new_page()
            counts = {'summary': 0, 'project': 0}
            def count(request):
                path = request.url.split('?')[0]
                if path.endswith('/api/view/summary'):
                    counts['summary'] += 1
                elif path.endswith('/api/project'):
                    counts['project'] += 1
            page.on('request', count)
            page.goto(server.start() + route + '/')
            expect(page.locator('#view-title')).to_be_visible()
            page.wait_for_timeout(16000)
            # Keep the original cadence/count boundary. The third summary can
            # still be in flight at 16s; its dependent control read follows the
            # response, so wait for that read rather than sample between them.
            assert counts['summary'] == 3, counts
            if counts['project'] == 2:
                with page.expect_response(lambda r: r.url.split('?')[0].endswith('/api/project'), timeout=5000):
                    pass
            assert counts == {'summary': 3, 'project': 3}, counts
            browser.close()
    finally:
        server.stop()


def test_matching_control_reuses_but_history_writes_and_races_do_not(tmp_path):
    project = tmp_path / 'project'
    create_gallery_sample(project, page_count=24, readonly=False)
    server = WorkbenchServer(project)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=shutil.which('chromium'), args=['--no-sandbox'])
            page = browser.new_page()
            # Same-origin empty document: exercise actual module, without a
            # background application poll or a second product state machine.
            page.goto(server.start() + 'v2/project.js')
            result = page.evaluate('''async () => {
              const {Project} = await import('/v2/project.js');
              const summary = (artifact, control) => ({project_id:'p', next_actions:[],
                current_work:{identity:{project_id:'p',artifact_revision_id:artifact,control_revision_id:control}}});
              const run = async (artifact, control, observed, race = false) => {
                let reads=0;
                const app={health:{ui_capabilities:['workbench_summary.v2']}, info:{project_id:'p'},
                  summary:{current_work:{sentinel:true}}, route:{revision:artifact}, generation:1,
                  summaryURL:() => '/synthetic-summary'};
                const original=window.fetch;
                window.fetch=async () => {reads++; if(race)app.generation++;
                  return new Response(JSON.stringify(summary(artifact,control)),{status:200,headers:{'Content-Type':'application/json'}});};
                try {await Project.prototype.refreshCurrentWork.call(app,{project_id:'p',control_revision_id:control},()=>true,observed);}
                finally {window.fetch=original;}
                return {reads,work:app.summary.current_work};
              };
              return {
                same:await run('r1','c1',summary('r1','c1')),
                historical:await run('r0','c1',summary('r1','c1')),
                mutation:await run('r1','c2',summary('r1','c1')),
                absent:await run('r1','c2',null),
                race:await run('r0','c2',summary('r1','c1'),true)
              };
            }''')
            assert result['same']['reads'] == 0
            for key in ('historical', 'mutation', 'absent', 'race'):
                assert result[key]['reads'] == 1
            assert result['historical']['work']['identity']['artifact_revision_id'] == 'r0'
            assert result['mutation']['work']['identity']['control_revision_id'] == 'c2'
            assert result['race']['work'] == {'sentinel': True}
            browser.close()
    finally:
        server.stop()
