# Project context (for agents)

## What this project is
`pytest-shal` is a pytest plugin for SHAL (`pyshal`, repo `determlab/shal`). A
test engineer adds one line to `conftest.py`; each test gets the rig from a
setup file (`rig` fixture), `check()` asserts and records a measurement, and each
test writes one record through `shal.record`. The spec of record is
`projects/shal/specs/pytest-shal.md` in `determlab/ops`. Decisions:
`docs/DECISIONS.md`.

## Architecture map
- `src/pytest_shal/plugin.py` — the module the `pytest11` entry point loads
  (entry name `shal`). All pytest hooks, options and fixtures live here.
- `src/pytest_shal/approve.py` — the `--shal-approve` mode -> which SHAL
  approver is seated. The one place the approval mode lives.
- `src/pytest_shal/__init__.py` — package version, and the guard that makes
  `pytest_plugins = ["pytest_shal"]` register the plugin once, never twice.
- `tests/` — pytest suite. Use `pytester` to test plugin behaviour in a
  sub-session, not the outer session.
- `pyproject.toml` — dependencies and the entry point. Fenced.

## Conventions
- Python >= 3.10, src layout, `ruff check .` clean.
- Import SHAL through its public API (`shal.load`, `shal.record`). Do not
  define the record shape here; it lives in `shal/record.py`.

## Safety invariants / "don't ever" list
- The entry point loads this plugin into EVERY pytest run where it is
  installed. A session that uses no `rig`/`check` and no `--shal-*` option must
  behave exactly as without the plugin.
- Never weaken SHAL's approval gate. `--shal-approve` defaults to `deny`; a
  denied op fails the test with the op named, never hangs.
- No new dependencies without a human (`pyproject.toml` is fenced).
- `pyshal` is pinned by commit until 0.3.0 is on PyPI; then `pyshal>=0.3.0`.

## How to build / test / lint
```
py -3.12 -m venv .venv && .venv/Scripts/activate   # Windows; bin/activate elsewhere
pip install -e ".[dev]"
python -m pytest
ruff check .
pip install mypy && mypy --strict src     # not in the dev extra: pyproject is fenced
```
`tests/test_first_run.py` builds the wheel and installs it in a fresh venv, so
the suite needs network access.
`pip install` needs `git` (pyshal comes from a git URL for now).

## Definition of done
Tests prove the acceptance criteria; `python -m pytest` and `ruff check .` pass;
CI green on Python 3.10–3.13 on ubuntu and windows.
