"""Which setup wins: --shal-setup > setup.yaml in the rootdir > $SHAL_SETUP."""

import yaml
from shal import record

from pytest_shal.plugin import SIM_TOPOLOGY

SIM_TEST = """
def test_room(rig, check):
    check("room", rig.ambient_temp.read_celsius(), "celsius", min=-40, max=125)
"""


def sim_file(dest):
    dest.write_text(yaml.safe_dump(SIM_TOPOLOGY), encoding="utf-8")
    return dest


def test_setup_yaml_beats_env(pytester, monkeypatch):
    sim_file(pytester.path / "setup.yaml")
    env_file = sim_file(pytester.mkdir("elsewhere") / "envrig.yaml")
    monkeypatch.setenv("SHAL_SETUP", str(env_file))
    pytester.makepyfile(SIM_TEST)
    pytester.runpytest().assert_outcomes(passed=1)
    (rec,) = record.read(pytester.path)
    assert rec.station == "setup"
    assert not record.read(env_file.parent)


def test_option_beats_setup_yaml_and_env(pytester, monkeypatch):
    sim_file(pytester.path / "setup.yaml")
    env_file = sim_file(pytester.mkdir("elsewhere") / "envrig.yaml")
    monkeypatch.setenv("SHAL_SETUP", str(env_file))
    other = sim_file(pytester.mkdir("bench") / "other.yaml")
    pytester.makepyfile(SIM_TEST)
    pytester.runpytest("--shal-setup", "bench/other.yaml").assert_outcomes(passed=1)
    (rec,) = record.read(other.parent)
    assert rec.station == "other"
    assert not record.read(pytester.path)
    assert not record.read(env_file.parent)


def test_env_missing_file(pytester, monkeypatch):
    monkeypatch.setenv("SHAL_SETUP", str(pytester.path / "gone.yaml"))
    pytester.makepyfile(SIM_TEST)
    result = pytester.runpytest()
    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(["*$SHAL_SETUP: no setup file at*gone.yaml*"])
