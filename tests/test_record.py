"""The rig, check() and one record per test, on the sim that ships with shal."""
from pathlib import Path

import pytest
import yaml
from shal import record

from pytest_shal.plugin import SIM_TOPOLOGY

SIM_TEST = """
def test_room(rig, check):
    check("room", rig.ambient_temp.read_celsius(), "celsius", min=-40, max=125)
"""


def records(path):
    return record.read(path)


def test_sim_needs_no_file(pytester):
    pytester.makepyfile(SIM_TEST)
    result = pytester.runpytest("--shal-setup", "sim")
    result.assert_outcomes(passed=1)
    (rec,) = records(pytester.path)
    assert rec.runner == "pytest"
    assert rec.verdict == "pass"
    assert rec.unit == "bench"
    assert rec.station == "sim" and rec.setup == "sim"
    assert rec.sequence == "test_sim_needs_no_file.py::test_room"
    assert len(rec.sequence_version) == 40 and len(rec.setup_version) == 40
    (step,) = rec.steps
    (m,) = step.measurements
    assert (m.name, m.unit, m.limits.min, m.limits.max, m.passed) == (
        "room", "celsius", -40, 125, True)
    # both stores: the YAML audit copy and the db index
    assert (pytester.path / "records" / f"{rec.record}.yaml").is_file()
    assert (pytester.path / "records.db").is_file()


def test_verdicts_one_record_per_test(pytester):
    pytester.makepyfile("""
        import pytest

        def test_check_fails(rig, check):
            check("ok", 1.0, "V", min=0.9, max=1.1)
            check("vout", 5.3, "V", min=4.9, max=5.1)

        def test_bare_assert(check):
            assert 1 == 2

        def test_raises(rig):
            raise RuntimeError("boom")

        def test_skipped(rig):
            pytest.skip("not today")

        def test_plain():
            pass
    """)
    result = pytester.runpytest("--shal-setup", "sim")
    result.assert_outcomes(failed=3, skipped=1, passed=1)
    result.stdout.fnmatch_lines(["*check 'vout': 5.3 V is outside [[]4.9, 5.1[]]*"])
    by_test = {r.sequence.split("::")[1]: r for r in records(pytester.path)}
    # a skip writes no record; a test with no rig/check writes none either
    assert set(by_test) == {"test_check_fails", "test_bare_assert", "test_raises"}

    fails = by_test["test_check_fails"]
    assert fails.verdict == "fail"
    assert [(s.name, s.verdict) for s in fails.steps] == [("ok", "pass"), ("vout", "fail")]
    m = fails.steps[1].measurements[0]
    assert (m.value, m.limits.min, m.limits.max, m.passed) == (5.3, 4.9, 5.1, False)

    bare = by_test["test_bare_assert"]
    assert bare.verdict == "fail"
    assert [(s.name, s.verdict, s.measurements) for s in bare.steps] == [
        ("test_bare_assert", "fail", ())]

    assert by_test["test_raises"].verdict == "error"


def test_one_sided_limits_and_bad_values(pytester):
    pytester.makepyfile("""
        import pytest

        def test_max_only(check):
            check("ripple", 12.0, "mV", max=50)

        def test_nan(check):
            check("x", float("nan"))
    """)
    result = pytester.runpytest("--shal-setup", "sim")
    result.assert_outcomes(passed=1, failed=1)
    by_test = {r.sequence.split("::")[1]: r for r in records(pytester.path)}
    m = by_test["test_max_only"].steps[0].measurements[0]
    assert (m.limits.min, m.limits.max) == (None, 50)
    assert by_test["test_nan"].verdict == "error"


def test_unit_option_and_marker(pytester):
    pytester.makepyfile("""
        import pytest

        def test_from_option(check):
            check("a", 1)

        @pytest.mark.shal_unit("SN-000417")
        def test_from_marker(check):
            check("a", 1)
    """)
    result = pytester.runpytest("--shal-setup", "sim", "--shal-unit", "SN-1", "--strict-markers")
    result.assert_outcomes(passed=2)
    units = {r.sequence.split("::")[1]: r.unit for r in records(pytester.path)}
    assert units == {"test_from_option": "SN-1", "test_from_marker": "SN-000417"}


def test_two_units_into_one_store(pytester):
    pytester.makepyfile(SIM_TEST)
    pytester.runpytest("--shal-setup", "sim", "--shal-unit", "SN-1").assert_outcomes(passed=1)
    (first,) = record.read(pytester.path, unit="SN-1")
    first_file = pytester.path / "records" / f"{first.record}.yaml"
    first_bytes = first_file.read_bytes()

    pytester.runpytest("--shal-setup", "sim", "--shal-unit", "SN-2").assert_outcomes(passed=1)
    assert len(record.read(pytester.path)) == 2
    (second,) = record.read(pytester.path, unit="SN-2")
    assert second.record != first.record
    assert first_file.read_bytes() == first_bytes
    assert len(record.read(pytester.path, unit="SN-1")) == 1


def test_blank_unit_is_refused(pytester):
    pytester.makepyfile("def test_a(): pass")
    result = pytester.runpytest("--shal-unit", " ")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*--shal-unit must not be blank*"])


def test_rig_by_id_and_by_path(pytester):
    pytester.makepyfile("""
        import pytest

        def test_lookup(rig):
            assert rig["ambient_temp"] is rig.ambient_temp
            assert rig["/bus/temp0"] is rig.ambient_temp
            assert rig["bus/temp0"] is rig.ambient_temp
            with pytest.raises(AttributeError, match="no device 'psu'"):
                rig.psu
            with pytest.raises(KeyError):
                rig["nope"]
    """)
    pytester.runpytest("--shal-setup", "sim").assert_outcomes(passed=1)


def sim_file(dest: Path) -> Path:
    dest.write_text(yaml.safe_dump(SIM_TOPOLOGY), encoding="utf-8")
    return dest


def test_setup_file_default_and_option(pytester):
    sim_file(pytester.path / "setup.yaml")
    pytester.makepyfile(SIM_TEST)
    pytester.runpytest().assert_outcomes(passed=1)
    (rec,) = records(pytester.path)
    assert (rec.setup, rec.station) == ("setup.yaml", "setup")

    bench = pytester.mkdir("bench")
    sim_file(bench / "bench.yaml")
    pytester.runpytest("--shal-setup", "bench/bench.yaml").assert_outcomes(passed=1)
    (rec,) = records(bench)  # the record goes beside the setup file
    assert (rec.setup, rec.station) == ("bench.yaml", "bench")


def test_setup_from_env(pytester, monkeypatch):
    path = sim_file(pytester.mkdir("elsewhere") / "line2.yaml")
    monkeypatch.setenv("SHAL_SETUP", str(path))
    pytester.makepyfile(SIM_TEST)
    pytester.runpytest().assert_outcomes(passed=1)
    (rec,) = records(path.parent)
    assert rec.station == "line2"


def test_no_setup_says_how(pytester, monkeypatch):
    monkeypatch.delenv("SHAL_SETUP", raising=False)
    pytester.makepyfile(SIM_TEST)
    result = pytester.runpytest()
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*no SHAL setup*--shal-setup sim*"])
    assert not (pytester.path / "records.db").exists()


def test_missing_setup_file(pytester):
    pytester.makepyfile(SIM_TEST)
    result = pytester.runpytest("--shal-setup", "nope.yaml")
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*--shal-setup: no setup file at*nope.yaml*"])


# -- #29: a transport failure's error step carries cause: transport --------


def test_dead_link_error_step_has_transport_cause(pytester):
    # `fail_next` is the sim i2c bus's own test hook (shal.buses.sim.SimI2cBus):
    # 2 drops exhausts the one idempotent retry, so the HopError (a dead link,
    # "simulated link drop before send") reaches the test body uncaught.
    pytester.makepyfile("""
        def test_dead_link(rig):
            rig["/bus"].fail_next = 2
            rig.ambient_temp.read_celsius()
    """)
    result = pytester.runpytest("--shal-setup", "sim")
    result.assert_outcomes(errors=1)
    (rec,) = records(pytester.path)
    assert rec.verdict == "error"
    (step,) = rec.steps
    assert step.verdict == "error"
    assert step.cause == "transport"
