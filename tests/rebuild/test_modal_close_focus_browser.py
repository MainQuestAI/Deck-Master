"""Queued native close must preserve navigation after synchronous restoration."""
import pytest
from test_ux06_recovery_responsive_browser import ux06_browser  # noqa: F401

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('removed,target', [
    (False, 'trigger'), (False, 'other'), (False, 'body'),
    (True, 'other'), (True, 'body'),
])
def test_queued_close_preserves_new_focus_and_retains_missing_trigger_fallback(ux06_browser, removed, target):
    page, server, *_ = ux06_browser
    # Isolate the shared helper from unrelated project polling/redraws.
    page.goto(server.start() + 'v2/dom.js')
    page.set_content('<main><h1 id="view-title" tabindex="-1">Surface</h1></main><dialog id="modal"></dialog>')
    result = page.evaluate('''async ({removed,target}) => {
      const {modal} = await import('/v2/dom.js');
      const main = document.querySelector('main') || document.body;
      const trigger = document.createElement('button'); trigger.textContent='Probe trigger';
      const other = document.createElement('button'); other.textContent='Probe next';
      main.append(trigger,other); trigger.focus();
      const dialog=modal('Probe',document.createElement('p'));
      const done=new Promise(resolve=>dialog.addEventListener('close',resolve,{once:true}));
      dialog.close();
      if(removed) trigger.remove();
      if(target==='other') other.focus();
      if(target==='body') document.activeElement.blur();
      const before=document.activeElement===other?'other':document.activeElement===trigger?'trigger':document.activeElement.tagName;
      await done;
      const after=document.activeElement===other?'other':document.activeElement===trigger?'trigger':document.activeElement.id||document.activeElement.tagName;
      trigger.remove();other.remove();
      return {before,after};
    }''', {'removed': removed, 'target': target})
    expected = 'view-title' if removed and target == 'body' else ('BODY' if target == 'body' else target)
    assert result['after'] == expected, result


def test_escape_then_keyboard_navigation_is_not_reversed_by_queued_close(ux06_browser):
    from playwright.sync_api import expect
    page, server, *_ = ux06_browser
    # Isolate the shared helper from unrelated project polling/redraws.
    page.goto(server.start() + 'v2/dom.js')
    page.set_content('<main><h1 id="view-title" tabindex="-1">Surface</h1></main><dialog id="modal"></dialog>')
    page.evaluate('''async()=>{
      const {modal}=await import('/v2/dom.js');
      const main=document.querySelector('main')||document.body;
      const previous=document.createElement('button');previous.id='focus-previous';previous.textContent='Previous';
      const trigger=document.createElement('button');trigger.id='focus-trigger';trigger.textContent='Trigger';
      main.append(previous,trigger);trigger.focus();
      const dialog=modal('Keyboard probe',document.createElement('p'));
      window.focusProbeClosed=false;
      dialog.addEventListener('close',()=>{window.focusProbeClosed=true},{once:true});
      await new Promise(resolve=>requestAnimationFrame(resolve));
    }''')
    page.keyboard.press('Escape')
    page.keyboard.press('Shift+Tab')
    page.wait_for_function('()=>window.focusProbeClosed')
    expect(page.locator('#focus-previous')).to_be_focused()
