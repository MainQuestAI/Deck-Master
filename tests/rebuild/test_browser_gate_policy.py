"""A required browser gate must fail when its tests do not execute."""

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]
GATE = Path(__file__).with_name("conftest.py")


@pytest.fixture
def gate_suite(pytester):
    pytester.makeconftest(
        "import runpy\n"
        f"hooks = runpy.run_path({str(GATE)!r})\n"
        "globals().update({key: value for key, value in hooks.items() if key.startswith('pytest_')})\n"
    )
    pytester.makeini("[pytest]\nmarkers = browser: real browser tests\n")
    return pytester


@pytest.mark.parametrize("stage", ["setup", "call"])
def test_required_browser_skip_fails(gate_suite, stage):
    setup = 'pytest.skip("Chromium unavailable")' if stage == "setup" else 'return None'
    gate_suite.makepyfile(
        "import pytest\n"
        "@pytest.fixture\n"
        "def browser():\n"
        f"    {setup}\n"
        "@pytest.mark.browser\n"
        "def test_browser(browser):\n"
        "    pytest.skip('browser did not execute')\n"
    )
    result = gate_suite.runpytest_subprocess("--require-browser", "-q")
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.assert_outcomes(**({"errors": 1} if stage == "setup" else {"failed": 1}))
    result.stdout.fnmatch_lines(["*Required browser gate did not execute*"])


def test_optional_browser_skip_is_explicit(gate_suite):
    gate_suite.makepyfile(
        "import pytest\n@pytest.mark.browser\n"
        "def test_browser():\n    pytest.skip('Chromium unavailable')\n"
    )
    result = gate_suite.runpytest_subprocess("-q")
    result.assert_outcomes(skipped=1)
    assert result.ret == pytest.ExitCode.OK


def test_required_browser_cannot_select_only_unit_tests(gate_suite):
    gate_suite.makepyfile("def test_unit():\n    pass\n")
    result = gate_suite.runpytest_subprocess("--require-browser", "-q")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*--require-browser selected no browser tests*"])
