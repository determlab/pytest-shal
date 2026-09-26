# Decisions

Newest last. A row is added, never rewritten; a later row may replace an earlier one.

| # | Decision | Why | Issue |
|---|---|---|---|
| D1 | **One record per test, through `shal.record`.** A test that uses `rig` or `check` writes exactly one record at teardown with `shal.record.write`, into the setup file's directory (`sim`: the rootdir). Each `check()` is one step with one measurement; a bare `assert` or `pytest.fail` adds a `fail` step, any other exception an `error` step; a skip writes nothing. `sequence_version`/`setup_version` are the file's git blob id, computed without git. This plugin never defines the record shape. | record.md §3/§6 R1: the shape lives in one place, `shal/record.py`. A test with no `rig`/`check` writes nothing, so a plain session is unchanged (the fence's first invariant). | #1 |
| D2 | **`deny` is the default of `--shal-approve`, and the CI default.** `deny` seats `shal.DenyAll`, `gate` seats `shal.ConsoleApprover` (reading the real terminal; with none it denies), `auto` seats `shal.AutoApprove` and is refused unless `--shal-setup sim`. A mode named on the command line is seated for the whole session; with no option, `deny` is seated only while the `rig` fixture is up. The mode lives in `src/pytest_shal/approve.py`. | spec §4: a gated op fails with the op named instead of hanging in CI; the plugin chooses among SHAL's approvers and never weakens the gate. Seating nothing in a plain session keeps it unchanged. The issue's names `gate`/`auto` are the spec's `prompt`/`allow`. | #1 |
