# Changelog

## Unreleased (v0.1)

- Depends on `pyshal>=0.3.0,<0.4` from PyPI; the git pin is gone, so installing
  needs no git (#7).
- Depends on `pyshal>=0.3.0,<0.5`: also accepts pyshal 0.4.x, verified against
  `determlab/shal` main ahead of its PyPI release (#30).
- `--shal-setup PATH|sim`: the rig from a SHAL setup file, or a built-in sim
  topology, with no file (spec R4, D3).
- `rig` fixture: `rig.<id>` and `rig["path/to/node"]`, one `shal.load` per session.
- `check(name, value, unit, min=, max=)`: asserts and records a measurement.
- `--shal-unit ID` and `@pytest.mark.shal_unit("ID")`; default `bench`.
- `--shal-approve deny|prompt|allow`, default `deny`; `allow` passes
  `approver=shal.AutoApprove()` to the sim rig's own `shal.load` (shal #217), is
  never process-wide, and is refused on a pyshal whose `shal.load` has no
  `approver=` (D5).
- One record per test that uses `rig` or `check`, through `shal.record` (D1).
- A session with no `rig`/`check` and no `--shal-*` option is unchanged.
- A `shal records` terminal summary: the store path, counts per verdict, and
  the node id and record id of anything not `pass` — written only when the
  session wrote at least one record (#8).
- `tests/test_readme_commands.py`: every fenced command on README's first
  screen and in AGENTS.md is extracted and run as written, in a fresh venv —
  docs are tests (D3, #34). With `RC_WHEELS=<dir>` set, `pip install` lines
  run against that dir instead of PyPI; a `doc-test: skip` marker is honoured
  only while `RC_WHEELS` is unset, and the test caps how many such skips the
  docs may carry at once.
- Writes and reads every `record_version` 3 key (shal#409): per step `ops`
  (pass-through, `None` when not collected), per measurement
  `instrument_id`/`instrument_simulated`/`limit_source`, per record
  `repeatability` — empty or `null`, since this plugin computes none of
  them (#39). Checked by capability (`hasattr(shal.record, "LimitSource")`),
  the same pattern already used for `Step.from_error`. CI pins `pyshal` to
  `shal@a799eaa` (record_version 3's merge commit) to test this ahead of
  its PyPI release, without touching the released `pyshal>=0.3.0,<0.5`
  range, and sets `PYTEST_SHAL_REQUIRE_RECORD_V3` on that job so a missing
  `LimitSource` is a collection failure there, never a silent skip. Tracking
  issue #42: remove the pin, the env var and the skip once a pyshal with
  `LimitSource` is on PyPI, and raise the floor instead.
