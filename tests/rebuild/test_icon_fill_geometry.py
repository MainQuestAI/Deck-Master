"""Nonzero fill checks must keep exact cancellation without quadratic work."""
import math
import time
from fractions import Fraction

import pytest

from deck_master import icons


@pytest.mark.parametrize('subpaths, expected', [
    ([], False),
    ([[(0, 0)]], False),
    ([[(0, 0), (3, 4)]], False),
    ([[(0, 0), (1, 1), (2, 2)]], False),
    ([[(0, 0), (6, 0), (3, 6)]], True),  # implicit closing edge
    ([[(0, 0), (6, 0), (3, 6), (6, 0), (0, 0)]], False),
    ([[(0, 0), (6, 0), (3, 6)], [(0, 0), (3, 6), (6, 0)]], False),
    # This is nonzero winding, not parity: two forward copies still paint.
    ([[(0, 0), (6, 0), (3, 6)], [(0, 0), (6, 0), (3, 6)]], True),
    # A reversed edge can be split differently without changing cancellation.
    ([[(0, 0), (6, 0), (3, 6)],
      [(0, 0), (3, 6), (6, 0), (4, 0), (2, 0)]], False),
    ([[(0, 0), (0, 6), (6, 6), (6, 0)],
      [(0, 0), (6, 0), (6, 6), (0, 6), (0, 4), (0, 2)]], False),
    # Partial overlap is not complete cancellation.
    ([[(0, 0), (6, 0), (6, 6), (0, 6)],
      [(3, 0), (3, 6), (9, 6), (9, 0)]], True),
    # Opposite lobes have zero signed area but both paint under nonzero fill.
    ([[(0, 0), (6, 6), (0, 6), (6, 0)]], True),
    ([[(0, 0), (6, 0), (6, 6), (0, 6)],
      [(2, 2), (4, 2), (4, 4), (2, 4)]], True),
    ([[(0, 0), (6, 0), (6, 6), (0, 6)],
      [(2, 2), (2, 4), (4, 4), (4, 2)]], True),
    ([[(0, 0), (1, 1), (2, 2 + Fraction(1, 10**40))]], True),
    # Cancelling subpaths may follow an earlier apparently visible contour.
    ([[(0, 0), (6, 0), (3, 6)], [(10, 10), (20, 20), (30, 30)],
      [(0, 0), (3, 6), (6, 0)]], False),
])
def test_exact_nonzero_fill(subpaths, expected):
    assert icons._filled_area(subpaths) is expected


@pytest.mark.parametrize('path', [
    'M2 12 C2 2 22 2 22 12 C22 22 2 22 2 12Z',
    'M2 12 Q12 2 22 12 T2 12Z',
    'M2 12 A10 10 0 1 0 22 12 A10 10 0 1 0 2 12Z',
])
def test_curve_fill_uses_parsed_native_segments(path):
    parsed = icons.parse_svg(
        f'<svg viewBox="0 0 24 24"><path d="{path}" fill="black"/></svg>'.encode(),
        page_id='curve-fill',
    )
    assert len(parsed['shapes'][0]['commands']) > 4
    assert icons.visible_geometry(parsed)


@pytest.mark.parametrize('cancel', [False, True])
def test_complex_fill_and_reversed_copy_complete_promptly(cancel):
    points = [(12 + 10 * math.cos(i * math.tau / 2500),
               12 + 10 * math.sin(i * math.tau / 2500)) for i in range(2500)]
    subpaths = [points, list(reversed(points))] if cancel else [points]
    started = time.perf_counter()
    assert icons._filled_area(subpaths) is not cancel
    elapsed = time.perf_counter() - started
    # Generous wall-time guard: optimized paths take well below a second;
    # the previous all-pairs Fraction intersection takes tens of seconds.
    assert elapsed < 5, f'2500-point fill check took {elapsed:.3f}s'
