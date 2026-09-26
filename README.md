# pytest-shal

**A test sequencer an agent can drive, safely.**

It is a pytest plugin. You keep writing pytest. One line in `conftest.py`, and
every test gets the rig from a SHAL setup file, every `check()` is a measurement
with limits, and every test writes one record: unit, station, pass/fail per
step, every measurement. SHAL's approval gate stays on: an op that changes a
device fails the test by default instead of waiting for a person.

## First run (no hardware, no file)

```
pip install pytest-shal
```

```python
# test_first.py
def test_room(rig, check):
    check("room", rig.ambient_temp.read_celsius(), "celsius", min=-40, max=125)
```

```
pytest --shal-setup sim
```

`sim` is the simulated rig that ships with shal. The record lands in
`records.db` and `records/<id>.yaml` in the rootdir.

## At the bench

```python
# conftest.py — the one line (only needed when plugin autoload is off)
pytest_plugins = ["pytest_shal"]
```

```python
def test_vout(rig, check):
    rig.psu.set_voltage(channel=1, volts=5.0)      # any node id in the setup file
    check("vout", rig.dmm.measure_voltage(), "V", min=4.9, max=5.1)
```

```
pytest --shal-setup bench.yaml --unit SN-000417
```

| name | what |
|---|---|
| `--shal-setup PATH\|sim` | the setup file; default `setup.yaml` in the rootdir, then `$SHAL_SETUP` |
| `--unit ID`, `@pytest.mark.unit("ID")` | the DUT id in the record; default `bench` |
| `--shal-approve deny\|gate\|auto` | `deny` (default) fails a gated op; `gate` asks a person at the terminal (denies with no terminal); `auto` allows, only with `--shal-setup sim` |
| `rig` | session fixture: `rig.<id>`, or `rig["path/to/node"]` |
| `check(name, value, unit, min=, max=)` | asserts the limits and records the measurement |

Records go beside the setup file (for `sim`, the rootdir), through
`shal.record`. A test that uses neither `rig` nor `check` is left alone.

Contract: `projects/shal/specs/pytest-shal.md` in `determlab/ops`.
