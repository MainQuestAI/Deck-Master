"""Current explicit replacement endpoints, independent of input order."""
from copy import deepcopy
import pytest
from deck_master.review import finding_closed
from test_review import make_review, finding, ref


def chain():
    old, new = ref('old-page'), ref('new-page')
    owner = make_review('content', seed='owner', status='fail', subjects=[old], findings=[finding('f')],
        dependencies=[{'kind':'content','identity':'page:p1','sha256':old['sha256']}])
    owner.update(ref=ref('owner'), review_stage='preproduction')
    fixed = deepcopy(owner)
    fixed.update(ref=ref('fixed'), replaces=owner['ref'], status='pass', subjects=[new], observations=['read current'])
    fixed['dependencies'][0]['sha256'] = new['sha256']
    fixed['findings'][0].update(resolution='fixed', evidence=[new])
    opened = deepcopy(fixed)
    opened.update(ref=ref('opened'), replaces=fixed['ref'], status='fail')
    opened['findings'][0]['resolution'] = 'open'
    return owner, fixed, opened, {'content:page:p1':new['sha256']}


@pytest.mark.parametrize('mode', ['reopen', 'refixed', 'fork', 'stale', 'unrelated', 'missing_evidence', 'cycle'])
@pytest.mark.parametrize('reverse', [False, True])
def test_effective_endpoints(mode, reverse):
    owner, fixed, opened, artifacts = chain()
    rows = [owner, fixed, opened]
    expected = False
    if mode == 'refixed':
        end = deepcopy(fixed)
        end.update(ref=ref('refixed'), replaces=opened['ref'])
        rows.append(end)
        expected = True
    elif mode == 'fork':
        opened['replaces'] = owner['ref']
    elif mode == 'stale':
        opened['dependencies'][0]['sha256'] = ref('stale')['sha256']
        expected = True
    elif mode == 'unrelated':
        opened['findings'][0]['finding_id'] = 'other'
        expected = True
    elif mode == 'missing_evidence':
        opened['findings'][0]['evidence'] = []
    elif mode == 'cycle':
        fixed['replaces'] = opened['ref']
    assert finding_closed(list(reversed(rows)) if reverse else rows, owner, owner['findings'][0], artifacts) is expected
