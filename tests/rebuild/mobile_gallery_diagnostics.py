"""Opt-in evidence for one synthetic installed-navigation action; never retries it."""
from contextlib import contextmanager
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys

import deck_master
from time import time


@contextmanager
def gallery_click_evidence(page):
    root = os.environ.get('STUDIO_MOBILE_CLICK_DIAGNOSTICS')
    if not root:
        yield
        return
    out = Path(root)
    tracing = False

    def record(kind, action):
        # Evidence must not replace the original click exception, including when
        # the browser is unresponsive. Never print exception bodies or env dumps.
        try:
            value = action()
            data = {'kind': kind, 'utc_epoch_seconds': time(), 'value': value}
            print('MOBILE_GALLERY_DIAGNOSTIC ' + json.dumps(data), file=sys.__stdout__, flush=True)
            (out / f'{kind}.json').write_text(json.dumps(data, indent=2) + '\n')
        except Exception as error:
            print(f'MOBILE_GALLERY_DIAGNOSTIC {kind}: {type(error).__name__}', file=sys.__stdout__, flush=True)

    def geometry():
        return page.get_by_role('button', name='整稿画廊', exact=True).evaluate('''node => {
          const ancestors=[];
          for (let n=node;n;n=n.parentElement) {
            const s=getComputedStyle(n);
            ancestors.push({tag:n.tagName, class:n.className, rect:n.getBoundingClientRect().toJSON(),
              overflowX:s.overflowX, overflowY:s.overflowY, position:s.position,
              scrollBehavior:s.scrollBehavior, scrollTop:n.scrollTop, scrollLeft:n.scrollLeft,
              scrollHeight:n.scrollHeight, scrollWidth:n.scrollWidth,
              clientHeight:n.clientHeight, clientWidth:n.clientWidth});
          }
          return {route:location.hash, width:innerWidth, height:innerHeight,
            scrollX, scrollY, visibility:document.visibilityState, ancestors};
        }''', timeout=2000)

    try:
        out.mkdir(parents=True, exist_ok=True)
        page.context.tracing.start(screenshots=True, snapshots=True, sources=False)
        tracing = True
    except Exception as error:
        print(f'MOBILE_GALLERY_DIAGNOSTIC setup: {type(error).__name__}', file=sys.__stdout__, flush=True)
    record('identity', lambda: {
        'browser': page.context.browser.version, 'playwright': version('playwright'),
        'package': str(Path(deck_master.__file__).resolve()),
        'wheels': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in Path('/tmp/workbench-wheel').glob('deck_master-*.whl')},
    })
    record('before-click', geometry)
    try:
        yield
    except BaseException:
        record('failed-click', geometry)
        record('failure-screenshot', lambda: (
            page.screenshot(path=str(out / 'failure.png'), timeout=2000), 'failure.png')[1])
        raise
    else:
        record('click-returned', lambda: {'route': page.url.split('#', 1)[-1],
                                        'interpretation': 'timeout_not_reproduced'})
    finally:
        if tracing:
            record('trace', lambda: (page.context.tracing.stop(path=str(out / 'trace.zip')), 'trace.zip')[1])
