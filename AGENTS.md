# pytest-shal — v0.1

A test sequencer an agent can drive, safely. It is a pytest plugin for SHAL:
each test gets the rig from a setup file (`rig`), `check()` asserts and records a
measurement, and each test that uses them writes one record through
`shal.record`. A gated SHAL op fails the test by default (`--shal-approve=deny`);
nothing waits on a prompt.

**Install** (from a clone, until it is on PyPI): `pip install .`

**First success — no account, no key, no config file, no hardware:**

```
# test_first.py
def test_room(rig, check):
    check("room", rig.ambient_temp.read_celsius(), "celsius", min=-40, max=125)
```
```
python -m pytest --shal-setup sim test_first.py
python -c "from shal import record; r = record.read('.')[0]; print(r.verdict, r.unit, r.station)"
```
Expect `1 passed`, then `pass bench sim`. The record is `records.db` and
`records/<id>.yaml` in the rootdir; the `shal records` section in the pytest
output says where and, for anything not `pass`, the record id.

**Entry points an agent calls:**
- `--shal-setup PATH|sim`, `--shal-unit ID`, `--shal-approve deny|prompt|allow`
  (`allow` gives the sim rig's own `shal.load` `approver=shal.AutoApprove()`;
  it is refused on a pyshal whose `shal.load` has no `approver=` — shal #217 / PR #219).
- Fixtures `rig` (`rig.<id>`, `rig["path/to/node"]`) and
  `check(name, value, unit, min=, max=)`; marker `@pytest.mark.shal_unit("ID")`.
- conftest: `pytest_plugins = ["pytest_shal"]` (only this form).
- Records: `shal.record.read(store, unit=, station=, sequence=, verdict=)`.

**Develop:** `pip install -e ".[dev]"`, then `python -m pytest`, `ruff check .`,
and `pip install mypy` + `mypy --strict src` (CI runs all three).

**The contract:** the "Entry points an agent calls" list above and `docs/DECISIONS.md`.
Agent rules: `docs/agents/context.md`, `.agent-loop.yml`, `docs/DECISIONS.md`.
