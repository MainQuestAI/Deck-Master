"""Opt-in evidence for the original installed style-navigation browser test."""
from contextlib import contextmanager
import json
import pytest


@pytest.fixture(autouse=True)
def style_recipe_diagnostics(request, monkeypatch):
    if 'test_pending_current_version_sidebar_keeps_reviewed_candidate_revision' not in request.node.nodeid:
        return
    import test_pr103_complete_browser as original_module
    original = original_module.browser_for

    @contextmanager
    def observed(project):
        with original(project) as (page, server):
            events = []

            def response(value):
                if '/api/styles' not in value.url and '/api/drafts' not in value.url:
                    return
                event = {'kind': 'response', 'url': value.url, 'status': value.status}
                events.append(event)
                try:
                    event['body'] = value.json()
                except Exception as error:
                    event['body_error'] = str(error)

            page.on('response', response)
            page.on('pageerror', lambda error: events.append({'kind': 'pageerror', 'error': str(error)}))
            page.on('requestfailed', lambda req: events.append({'kind': 'requestfailed', 'url': req.url, 'failure': req.failure}))
            page.add_init_script('''(() => {
              window.styleLifecycleTrace=[];
              for (const name of ['draft-editor-replaced','draft-state-changed','summary-refreshed'])
                document.addEventListener(name, event => {
                  window.styleLifecycleTrace.push({event:name,time:performance.now(),url:location.href,
                    draft:document.querySelector('.draft-state')?.textContent,
                    recipes:document.querySelectorAll('.studio-recipe-card').length});
                },true);
            })();''')
            try:
                yield page, server
            finally:
                result = {'nodeid': request.node.nodeid, 'events': events}
                try:
                    result['dom'] = page.evaluate('''() => ({url:location.href,
                      trace:window.styleLifecycleTrace,
                      draft:[...document.querySelectorAll('.draft-state')].map(n=>n.textContent),
                      notices:[...document.querySelectorAll('.style-calibration > [role=status]')].map(n=>({text:n.textContent,hidden:n.hidden})),
                      styleCount:document.querySelectorAll('.style-calibration').length,
                      mainBusy:document.querySelector('#main')?.getAttribute('aria-busy'),
                      source:document.querySelector('[aria-label="风格参考来源"] select')?.value,
                      recipeOptions:[...document.querySelectorAll('[aria-label="已确认的风格版本"] option')].map(n=>({value:n.value,text:n.textContent})),
                      library:document.querySelector('.studio-recipe-library')?.outerHTML,
                      draftDetails:[...document.querySelectorAll('.draft-state')].map(n=>n.closest('.draft-editor')?.textContent)
                    })''')
                except Exception as error:
                    result['dom_error'] = str(error)
                target = project.parent / 'browser-evidence' / 'style-recipe-diagnostics.json'
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(result, ensure_ascii=False, indent=2))
                print('STYLE_RECIPE_DIAGNOSTICS=' + str(target))
    monkeypatch.setattr(original_module, 'browser_for', observed)
