"""PR123 review nit: four shared decision errors through real shipped UI.

The HTTP 409 envelopes are explicit transport/wording fixtures. No production
operation, Runtime guard, authorization or professional review is replaced.
"""
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from test_ui_design_browser import workbench_page  # noqa: F401

pytestmark = pytest.mark.browser


@pytest.mark.parametrize('context,missing,topics', [
    ('work_request', 'work_request', []),
    ('direction', 'decision', ['direction']),
    ('style', 'decision', ['style']),
    ('delivery_acceptance', 'decision', ['delivery_acceptance']),
])
def test_decision_error_is_work_neutral_and_preserves_specific_gap(workbench_page, context, missing, topics):
    page = workbench_page
    parsed = urlsplit(page.url)
    base = f'{parsed.scheme}://{parsed.netloc}'
    summary = page.request.get(base+'/api/view/summary').json()
    payload = {'error': {
        'code': 'decision_needed', 'message': 'A required business decision is missing: '+context,
        'action': context, 'reason_codes': ['decision_needed'],
        'reasons': [{'code': 'decision_needed', 'detail': 'Missing '+context,
                     'missing': missing, 'topics': topics}],
        'responsible_role': 'user', 'next_action': 'record an accepted decision',
        'decision_card': {'kind': 'request_card' if missing == 'work_request' else 'decision_card',
                          'topics': topics, 'projection': context},
    }}
    page.route('**/api/decision-wording-regression', lambda route: route.fulfill(status=409, json=payload))
    # Use the real post parser and admission renderer, rather than a copied
    # label table. Different facts must survive the shared neutral message.
    page.evaluate('''async ({summary,context}) => {
      const {post} = await import('/v2/api.js');
      const {admissionView} = await import('/v2/collaboration-desk.js');
      const {modal} = await import('/v2/dom.js');
      try { await post('/api/decision-wording-regression', {context}); }
      catch (error) { modal('决定缺项提示', admissionView({summary}, error)); }
    }''', {'summary': summary, 'context': context})
    dialog = page.get_by_role('dialog', name='决定缺项提示')
    expect(dialog.locator('.field-error')).to_have_text('还缺本次工作的明确决定。请核对具体缺项、相关范围和下一步操作。')
    expect(dialog.locator('.field-error')).not_to_contain_text('交付')
    expect(dialog).to_contain_text('当前稿件、可读报告和本次输入均保留')
    dialog.get_by_text('决定范围与影响', exact=True).click()
    expect(dialog).to_contain_text(context)
    dialog.get_by_text('错误依据与范围', exact=True).click()
    expect(dialog).to_contain_text('Missing '+context)
    expect(dialog).to_contain_text('"missing": "'+missing+'"')
    page.keyboard.press('Escape')
    if context == 'delivery_acceptance':
        # Delivery-specific copy belongs to the actual delivery surface.
        page.get_by_role('button', name='任务与交付', exact=True).click()
        page.get_by_role('button', name='文件', exact=True).click()
        judgement = page.get_by_label('所选实际文件的交付判断')
        expect(judgement).to_contain_text('所选文件仍有交付缺口')
        expect(judgement).to_contain_text('整稿 PPT')
        expect(page.get_by_role('button', name='生成正式交付包', exact=True)).to_be_disabled()
        expect(page.locator('.delivery-availability')).to_contain_text('交付缺口')
    assert page.request.get(base+'/api/view/summary').json()['revision_id'] == summary['revision_id']
