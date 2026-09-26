# Changelog

## Unreleased (v0.1)

- `--shal-setup PATH|sim`: the rig from a SHAL setup file, or a built-in sim
  topology, with no file (spec R4, D3).
- `rig` fixture: `rig.<id>` and `rig["path/to/node"]`, one `shal.load` per session.
- `check(name, value, unit, min=, max=)`: asserts and records a measurement.
- `--shal-unit ID` and `@pytest.mark.shal_unit("ID")`; default `bench`.
- `--shal-approve deny|prompt|allow`, default `deny`; `allow` is refused until
  SHAL has `Hal.bind_approver`, and is never process-wide.
- One record per test that uses `rig` or `check`, through `shal.record` (D1).
- A session with no `rig`/`check` and no `--shal-*` option is unchanged.
