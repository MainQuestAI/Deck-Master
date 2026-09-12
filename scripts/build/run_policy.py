"""Creation mode remains the delivery policy for the life of a run."""
from pathlib import Path


def enforce_origin_mode(root, request, requested=None):
    from build.build_route import load_persisted_route
    route = load_persisted_route(Path(root)) if root is not None else {}
    origin = str(route.get('origin_run_mode') or request.get('origin_run_mode') or request.get('run_mode') or requested or 'production').strip().lower()
    for label, value in (('request.origin_run_mode', request.get('origin_run_mode')), ('request.run_mode', request.get('run_mode')), ('requested mode', requested)):
        if value and str(value).strip().lower() != origin:
            raise ValueError(f'RUN_MODE_CONFLICT: {label} cannot change creation mode {origin!r}; an explicit supported migration is required')
    return origin
