"""Derived audience-register instructions for the existing page_copy reviewer.

This is review input, not an automatic judgment or a second manuscript. Words
such as source, assumption and timecode never produce findings by themselves.
"""


def page_copy_checklist(document, pages):
    return {
        'method': 'audience_register.v1',
        'unit': 'page_copy',
        'task': document.get('task') or {},
        'visibility_contract': 'customer_visible_only.v1',
        'questions': [
            'Read every customer-visible title, block, label, citation and qualification in its audience context.',
            'Distinguish actual business explanation from author instructions, internal evidence IDs, planning labels and production notes accidentally shown to the audience.',
            'Keep a legitimate source, necessary assumption, applicability condition or timecode when it helps this audience use or verify the content.',
            'Judge actual disclosure, audience purpose and misleading effect; a keyword is only a question, never an automatic F0 or finding.',
            'Record a located content/privacy finding through page_copy with the exact original phrase, expected audience expression, page/atom and supporting evidence. Do not invent facts in the proposed correction.',
            'A manuscript judgment does not prove the generated image obeyed it. Inspect the actual image under its own task and preserve original observation.',
        ],
        'impact_guidance': {
            'must_fix': 'Observed prohibited disclosure or internal process language that changes/misleads the intended audience meaning or prevents the intended use.',
            'needs_judgment': 'Audience authorization, intended use or disclosure meaning cannot be established from the actual evidence; state the missing decision.',
            'advisory': 'Observed wording friction with no material disclosure or misunderstanding; explain the audience effect.',
        },
        'pages': [{'page_id': page['page_id'], 'page_ref': page['page_ref'],
                   'visible_field': 'customer_visible', 'context_fields': ['speaker_notes', 'content_mapping']} for page in pages],
        'result_contract': 'Use existing review.v2 findings; valid pass with findings=[] requires actual completed review, never an empty receipt or unexecuted task.',
    }
