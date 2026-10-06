"""shal#409/pytest-shal#39: this plugin writes and reads every record v3
key -- per step `ops`, per measurement `instrument_id`/`instrument_simulated`/
`limit_source`, per record `repeatability` -- empty or null when unknown
(the plugin computes none of them; filling them is out of scope for this
ticket, same as shal's own record.py).

Shape exactly as `shal.record` (record.md §2.1): nothing is re-defined
here, this file only proves the shape round-trips through this plugin's
own write path, and through a real test run.
"""
from __future__ import annotations

import os

import pytest
import shal
import yaml
from shal import record

SIM_TEST = """
def test_room(rig, check):
    check("room", rig.ambient_temp.read_celsius(), "celsius", min=-40, max=125)
"""

# record_version 3 (shal#409) postdates the released pyshal>=0.3.0,<0.5 (not
# yet on PyPI) -- checked by capability, the same pattern test_record.py's
# own HAS_STEP_CAUSE already uses, never by version string.
HAS_RECORD_V3 = hasattr(record, "LimitSource")

# CTO review on PR #41: a skip here is silent -- CI stays green with 4 skips
# if the pin step (ci.yml) is ever dropped or edited, or pip resolves
# differently, and "pytest -q passes in CI with the pinned shal" (#39's own
# Done-when) would then be proving nothing. ci.yml sets this on the pin
# step's job; when it is set, a missing `LimitSource` is a collection
# FAILURE, never a skip, so a broken pin cannot hide behind a green run.
if not HAS_RECORD_V3 and os.environ.get("PYTEST_SHAL_REQUIRE_RECORD_V3") == "1":
    pytest.fail(
        f"PYTEST_SHAL_REQUIRE_RECORD_V3=1 but installed pyshal {shal.__version__} has "
        f"no shal.record.LimitSource (shal#409, record_version 3) -- the pin step "
        f"that should install it is missing, was edited, or pip resolved differently",
        pytrace=False)

needs_record_v3 = pytest.mark.skipif(
    not HAS_RECORD_V3,
    reason=f"installed pyshal {shal.__version__} has no shal.record.LimitSource "
           f"(shal#409, record_version 3, not yet on PyPI)",
)


def _records(path):
    return record.read(path)


# --------------------------------------------------------------------------- #
# the real sample (rule 8): a record this plugin actually wrote, not a
# hand-written fixture
# --------------------------------------------------------------------------- #

@needs_record_v3
def test_a_real_test_run_writes_a_v3_record_with_all_five_keys_null(pytester):
    pytester.makepyfile(SIM_TEST)
    result = pytester.runpytest("--shal-setup", "sim")
    result.assert_outcomes(passed=1)
    (rec,) = _records(pytester.path)

    assert rec.record_version == 3
    assert rec.repeatability is None
    (step,) = rec.steps
    assert step.ops is None
    (m,) = step.measurements
    assert m.instrument_id is None
    assert m.instrument_simulated is None
    assert m.limit_source is None

    # the agent path (issue's own DoD line, which says "JSON" -- imprecise;
    # a record's audit copy is YAML, `record.md` §4): read the record file
    # and find all five keys, present and null -- a v3 record never omits
    # them, so an agent sees every key without reading docs.
    yaml_doc = yaml.safe_load(
        (pytester.path / "records" / f"{rec.record}.yaml").read_text(encoding="utf-8"))
    assert yaml_doc["repeatability"] is None
    step_doc = yaml_doc["steps"][0]
    assert step_doc["ops"] is None
    m_doc = step_doc["measurements"][0]
    assert m_doc["instrument_id"] is None
    assert m_doc["instrument_simulated"] is None
    assert m_doc["limit_source"] is None


# --------------------------------------------------------------------------- #
# round-trip: every v3 key empty, and every v3 key filled
# --------------------------------------------------------------------------- #

@needs_record_v3
def test_v3_keys_round_trip_when_empty(tmp_path):
    rec = record.Record(
        record="rec-20261007T000000-empty1",
        unit="bench", station="sim", sequence="t", sequence_version="0" * 40,
        setup="sim", setup_version="0" * 40, runner="pytest",
        started="2026-10-07T00:00:00Z", ended="2026-10-07T00:00:01Z",
        steps=[record.Step(name="s", verdict="pass", ops=None, measurements=[
            record.Measurement(name="v", value=1.0, unit="V",
                               limits=record.Limits(), passed=True,
                               instrument_id=None, instrument_simulated=None,
                               limit_source=None),
        ])],
        repeatability=None,
    )
    record.write(rec, tmp_path)
    [got] = record.read(tmp_path)
    assert got == rec
    assert got.repeatability is None
    assert got.steps[0].ops is None
    assert got.steps[0].measurements[0].instrument_id is None


@needs_record_v3
def test_v3_keys_round_trip_when_filled(tmp_path):
    rec = record.Record(
        record="rec-20261007T000000-filled1",
        unit="bench", station="sim", sequence="t", sequence_version="0" * 40,
        setup="sim", setup_version="0" * 40, runner="pytest",
        started="2026-10-07T00:00:00Z", ended="2026-10-07T00:00:01Z",
        steps=[record.Step(name="s", verdict="pass", ops=[
            record.Op(device="psu", op="set_voltage", args={"volts": 3.3},
                     side_effect="actuator", simulated=True, result="ok"),
        ], measurements=[
            record.Measurement(name="v", value=3.3, unit="V",
                               limits=record.Limits(min=3.2, max=3.4), passed=True,
                               instrument_id="dmm0", instrument_simulated=True,
                               limit_source=record.LimitSource(
                                   document="datasheet", revision="rev B")),
        ])],
        # repeatability stays None even in the "filled" variant -- nothing
        # in this plugin or in shal#409 computes it yet (out of scope for
        # both tickets); the other four keys are what "filled" exercises.
        repeatability=None,
    )
    record.write(rec, tmp_path)
    [got] = record.read(tmp_path)
    assert got == rec
    assert got.steps[0].ops[0].device == "psu"
    assert got.steps[0].measurements[0].instrument_id == "dmm0"
    assert got.steps[0].measurements[0].limit_source.document == "datasheet"


@needs_record_v3
def test_an_old_record_without_v3_fields_still_loads(tmp_path):
    """A record written before shal#409 (record_version 2, no ops/
    instrument_id/instrument_simulated/limit_source/repeatability keys at
    all) must still load, with all five reading back empty/null."""
    doc = {
        "record_version": 2,
        "record": "rec-20250101T000000-old0001",
        "unit": "bench", "station": "sim", "sequence": "t",
        "sequence_version": "0" * 40, "setup": "sim", "setup_version": "0" * 40,
        "runner": "pytest", "started": "2025-01-01T00:00:00Z",
        "ended": "2025-01-01T00:00:01Z", "verdict": "pass",
        "steps": [{"name": "s", "verdict": "pass", "measurements": [
            {"name": "v", "value": 1.0, "unit": "V", "limits": {}, "pass": True},
        ]}],
    }
    path = record.yaml_path(tmp_path, doc["record"])
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8", newline="\n")

    [got] = record.read(tmp_path)
    assert got.record_version == 2
    assert got.repeatability is None
    assert got.steps[0].ops is None
    assert got.steps[0].measurements[0].instrument_id is None
    assert got.steps[0].measurements[0].instrument_simulated is None
    assert got.steps[0].measurements[0].limit_source is None
