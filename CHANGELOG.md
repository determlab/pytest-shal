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
