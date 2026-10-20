"""Strict routing for optional read-only content insight endpoints."""
import re
from urllib.parse import parse_qs, unquote
from . import content_insight as insight


def route(project, path, query):
    from .method_library_view import resource
    if path.startswith('/api/method-library/resources/'):
        query_values = parse_qs(query, keep_blank_values=True)
        if set(query_values) != {'catalog_digest', 'sha256'} or any(len(v) != 1 or not re.fullmatch('[a-f0-9]{64}', v[0]) for v in query_values.values()):
            insight.fail('One catalog digest and resource hash required')
        return resource(unquote(path.removeprefix('/api/method-library/resources/')), **{k: v[0] for k, v in query_values.items()})
    routes = [
        (r'/api/tasks/([^/]+)/methods', insight.task_methods, {'revision', 'availability'}),
        (r'/api/content/arguments', insight.arguments, {'revision', 'limit', 'offset'}),
        (r'/api/content/arguments/([a-f0-9]{64})', insight.argument, {'revision'}),
        (r'/api/content/evidence/([^/]+)', insight.evidence, {'revision', 'element_ref'}),
        (r'/api/reviews/([^/]+)/reading', insight.review_reading, {'revision', 'review_sha256'}),
        (r'/api/content/requirements/([^/]+)', insight.requirements, {'revision'}),
    ]
    for pattern, function, allowed in routes:
        match = re.fullmatch(pattern, path)
        if not match:
            continue
        values = parse_qs(query, keep_blank_values=True)
        if set(values) - allowed or any(len(v) != 1 or not v[0] for v in values.values()):
            insight.fail('Use one nonempty value per supported parameter')
        kwargs = {k: v[0] for k, v in values.items()}
        for k in ('limit', 'offset'):
            if k in kwargs:
                if not kwargs[k].isascii() or not kwargs[k].isdigit():
                    insight.fail('Invalid pagination')
                kwargs[k] = int(kwargs[k])
        return function(project, *(unquote(x) for x in match.groups()), **kwargs)
    return None
