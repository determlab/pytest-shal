"""A session with no rig/check and no --shal-* option is unchanged by the plugin."""
import re

import pytest

PLAIN = """
import pytest
import shal

def test_pass():
    # the plugin seated no approver: shal's own default is still in the seat
    assert type(shal.get_approver()).__name__ == "ConsoleApprover"

def test_fail():
    assert 1 == 2

@pytest.mark.skip(reason="skipped")
def test_skip():
    pass

@pytest.fixture
def boom():
    raise RuntimeError("setup")

def test_error(boom):
    pass
"""

_NOISE = re.compile(r"^(platform |plugins: |rootdir: |cachedir: )| in \d+\.\d+s")


def lines(result):
    return [ln for ln in result.outlines if not _NOISE.search(ln)]


def test_plain_session_is_unchanged(pytester):
    pytester.makepyfile(PLAIN)
    with_plugin = pytester.runpytest_subprocess("-p", "no:cacheprovider")
    without = pytester.runpytest_subprocess("-p", "no:cacheprovider", "-p", "no:shal")
    with_plugin.assert_outcomes(passed=1, failed=1, skipped=1, errors=1)
    assert with_plugin.ret == without.ret
    assert lines(with_plugin) == lines(without)
    assert not (pytester.path / "records.db").exists()
    assert not (pytester.path / "records").exists()


@pytest.mark.parametrize("autoload", ["1", None], ids=["autoload-off", "autoload-on"])
def test_conftest_line_registers_once(pytester, monkeypatch, autoload):
    # the spec's one line, with and without the entry point already loaded
    if autoload:
        monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", autoload)
    else:
        monkeypatch.delenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", raising=False)
    pytester.makeconftest('pytest_plugins = ["pytest_shal"]')
    pytester.makepyfile("""
        def test_a(check):
            check("a", 1)
    """)
    result = pytester.runpytest_subprocess("--shal-setup", "sim", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=1)
    from shal import record
    assert len(record.read(pytester.path)) == 1  # one record, not two
