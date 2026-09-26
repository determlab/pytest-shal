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


_ADDR = re.compile(r" at 0x[0-9A-Fa-f]+")


def lines(result):
    return [_ADDR.sub(" at 0x?", ln) for ln in result.outlines if not _NOISE.search(ln)]


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


def test_a_projects_own_check_fixture_is_left_alone(pytester, monkeypatch):
    # its own `check` and `rig`, and a setup the plugin could find: still not ours
    setup = pytester.path / "bench.yaml"
    setup.write_text("shal_version: 1\nroot: {}\n")
    monkeypatch.setenv("SHAL_SETUP", str(setup))
    pytester.makeconftest("""
        import pytest

        @pytest.fixture
        def check():
            return lambda value: value > 0

        @pytest.fixture
        def rig():
            return "the project's own rig"
    """)
    pytester.makepyfile("""
        def test_ok(check, rig):
            assert check(1) and rig == "the project's own rig"

        def test_red(check):
            assert check(-1)
    """)
    with_plugin = pytester.runpytest_subprocess("-p", "no:cacheprovider")
    without = pytester.runpytest_subprocess("-p", "no:cacheprovider", "-p", "no:shal")
    with_plugin.assert_outcomes(passed=1, failed=1)
    assert lines(with_plugin) == lines(without)
    assert not (pytester.path / "records.db").exists()
    assert not (pytester.path / "records").exists()


def test_a_projects_own_unit_option_and_marker_run_unchanged(pytester):
    pytester.makeconftest("""
        def pytest_addoption(parser):
            parser.addoption("--unit", default="none")

        def pytest_configure(config):
            config.addinivalue_line("markers", "unit(id): the project's own marker")
    """)
    pytester.makepyfile("""
        import pytest

        @pytest.mark.unit("mine")
        def test_a(pytestconfig):
            assert pytestconfig.getoption("--unit") == "X"
    """)
    args = ("-p", "no:cacheprovider", "--strict-markers", "--unit", "X")
    with_plugin = pytester.runpytest_subprocess(*args)
    without = pytester.runpytest_subprocess(*args, "-p", "no:shal")
    with_plugin.assert_outcomes(passed=1)
    assert lines(with_plugin) == lines(without)


def test_conftest_line_under_W_error(pytester, monkeypatch):
    # autoload on: the package is imported before the conftest names it
    monkeypatch.delenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", raising=False)
    pytester.makeconftest('pytest_plugins = ["pytest_shal"]')
    pytester.makepyfile("def test_a(): pass")
    result = pytester.runpytest_subprocess("-W", "error", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=1)


def test_extended_plugin_fixtures_still_record(pytester):
    # a conftest that builds on the plugin's fixtures: still a SHAL test
    pytester.makeconftest("""
        import pytest

        @pytest.fixture(scope="session")
        def rig(rig):
            return rig

        @pytest.fixture
        def check(check):
            return check

        @pytest.fixture
        def room(rig):
            return rig.ambient_temp
    """)
    pytester.makepyfile("""
        def test_rig(rig):
            rig.ambient_temp.read_celsius()

        def test_check(check):
            check("a", 1)

        def test_room(room):
            room.read_celsius()
    """)
    pytester.runpytest("--shal-setup", "sim").assert_outcomes(passed=3)
    from shal import record
    assert sorted(r.sequence.split("::")[1] for r in record.read(pytester.path)) == [
        "test_check", "test_rig", "test_room"]
