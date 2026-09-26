# Changelog

## Unreleased (v0.1)

- `--shal-setup PATH|sim`: the rig from a SHAL setup file, or the sim that ships
  with shal, with no file (spec R4).
- `rig` fixture: `rig.<id>` and `rig["path/to/node"]`, one `shal.load` per session.
- `check(name, value, unit, min=, max=)`: asserts and records a measurement.
- `--unit ID` and `@pytest.mark.unit("ID")`; default `bench`.
- `--shal-approve deny|gate|auto`, default `deny`; `auto` only with the sim.
- One record per test that uses `rig` or `check`, through `shal.record` (D1).
- A session with no `rig`/`check` and no `--shal-*` option is unchanged.
