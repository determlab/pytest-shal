# pytest-shal — v0.1

A pytest plugin for SHAL. One line in `conftest.py`, and every test gets the rig
from a setup file, every failing check becomes a step fail, and every test
writes one record. Today this repo is a skeleton: the plugin registers with
pytest and does nothing yet. The package itself is #1.

**Install (dev):** `pip install -e ".[dev]"`

**The one command:** `python -m pytest` (CI also runs `ruff check .`)

**The contract:** `projects/shal/specs/pytest-shal.md` in `determlab/ops`.
Agent rules for this repo: `docs/agents/context.md` and `.agent-loop.yml`.
