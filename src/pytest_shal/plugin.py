"""The pytest11 entry point: the rig from a setup file, check(), one record per test.

The whole surface (spec §3): ``--shal-setup PATH|sim``, ``--shal-unit ID``,
``--shal-approve deny|prompt|allow``, the ``shal_unit`` marker, and the ``rig`` and
``check`` fixtures. Everything else is pytest's.

Safety invariant: the entry point loads this module into every pytest run where
the package is installed. A session that uses no ``rig``/``check`` fixture and
passes no ``--shal-*`` option must behave exactly as without it. Every option and
marker added here is ``shal``-prefixed, so it cannot clash with a project's own.
So nothing here
acts until a test asks for ``rig`` or ``check``, or an option is given: no
approver is seated, no setup is read and no record is written before that.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import math
import os
import secrets
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import shal
from shal import record as shal_record

from pytest_shal import approve

#: ``--shal-setup sim``: the simulated rig that ships with shal (spec R4).
SIM = approve.SIM
#: Only tests that ask for one of these get a record.
_FIXTURES = frozenset(("rig", "check"))
_DEFAULT_UNIT = "bench"  # record.md §2: never blank


#: The sim, as an in-memory topology of the plugin's own (D3): one simulated I2C
#: bus and one simulated temperature sensor on it, id ``ambient_temp``. Both
#: drivers ship with shal; its ``set_target`` is a gated ``config`` op.
SIM_TOPOLOGY: dict[str, Any] = {
    "shal_version": 1,
    "root": {
        "bus": {
            "driver": "shal,sim-i2c",
            "address": "sim0",
            "children": {
                "temp0": {"id": "ambient_temp", "driver": "shal,sim-sensor", "address": 0x48},
            },
        },
    },
}


# --------------------------------------------------------------------------- #
# options
# --------------------------------------------------------------------------- #

def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("shal", "SHAL: the rig from a setup file, one record per test")
    group.addoption(
        "--shal-setup", default=None, metavar="PATH|sim",
        help="the SHAL setup file, or `sim` for the simulated rig that ships with "
             "shal (default: setup.yaml in the rootdir, then $SHAL_SETUP)",
    )
    group.addoption(
        "--shal-unit", default=None, metavar="ID",
        help="the DUT id written to each record (default: bench); "
             "@pytest.mark.shal_unit(ID) overrides it per test",
    )
    group.addoption(
        "--shal-approve", default=None, choices=approve.MODES,
        help=f"who approves a gated SHAL op: deny fails the test (default: "
             f"{approve.DEFAULT}), prompt asks a person at the terminal, allow "
             f"approves on the sim rig only (needs SHAL's Hal.bind_approver)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "shal_unit(id): the DUT id written to this test's SHAL record"
    )
    unit = config.getoption("--shal-unit")
    if unit is not None and not unit.strip():
        raise pytest.UsageError("--shal-unit must not be blank (leave it out for 'bench')")
    approve.seat_session(config)  # only when --shal-approve is named


# --------------------------------------------------------------------------- #
# the setup file
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class _Setup:
    source: Path | None  # what shal.load reads; None = SIM_TOPOLOGY
    name: str      # record `setup`
    station: str   # record `station`
    version: str   # record `setup_version`
    store: Path    # where records.db and records/ go


_SETUP = pytest.StashKey["_Setup | str"]()


def _git_blob_id(path: Path) -> str:
    """The file's git blob id (`git hash-object --no-filters`), with no git needed.

    Committed and unchanged, it is the id git itself has for the file; edited, it
    changes with the bytes. That is "git sha if in a repo, else the file hash" as
    one rule (spec §3).
    """
    data = path.read_bytes()
    header = b"blob %d\0" % len(data)
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def _sim_version() -> str:
    """The sim's version: a hash of its topology, in canonical JSON."""
    text = json.dumps(SIM_TOPOLOGY, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(text.encode(), usedforsecurity=False).hexdigest()


def _resolve_setup(config: pytest.Config) -> _Setup | str:
    """The setup, or the reason there is none. Order: option, setup.yaml, env."""
    opt = config.getoption("--shal-setup")
    if opt == SIM:
        return _Setup(None, SIM, SIM, _sim_version(), Path(config.rootpath))
    if opt:
        path = Path(config.invocation_params.dir) / opt
        how = "--shal-setup"
    elif (Path(config.rootpath) / "setup.yaml").is_file():
        path = Path(config.rootpath) / "setup.yaml"
        how = "the default setup.yaml"
    elif os.environ.get("SHAL_SETUP"):
        path = Path(os.environ["SHAL_SETUP"])
        how = "$SHAL_SETUP"
    else:
        return ("no SHAL setup: pass --shal-setup PATH, put a setup.yaml in the "
                "rootdir, set SHAL_SETUP, or try the simulated rig: --shal-setup sim")
    if not path.is_file():
        return f"{how}: no setup file at {path}"
    path = path.resolve()
    return _Setup(path, path.name, path.stem, _git_blob_id(path), path.parent)


def _setup(config: pytest.Config) -> _Setup | str:
    if _SETUP not in config.stash:
        config.stash[_SETUP] = _resolve_setup(config)
    return config.stash[_SETUP]


def _setup_or_fail(config: pytest.Config) -> _Setup:
    setup = _setup(config)
    if isinstance(setup, str):
        pytest.fail(setup, pytrace=False)
    return setup


# --------------------------------------------------------------------------- #
# the rig fixture
# --------------------------------------------------------------------------- #

class Rig:
    """The bound devices of the setup: ``rig.<id>``, or ``rig["path/to/node"]``."""

    def __init__(self, hal: shal.Hal) -> None:
        self._hal = hal

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._hal.get_device(name)
        except shal.LoadError as e:
            raise AttributeError(f"rig has no device {name!r}: {e}") from None

    def __getitem__(self, key: str) -> Any:
        # an id, or a node path; the leading "/" is optional for a path
        if "/" in key and not key.startswith("/"):
            key = "/" + key
        try:
            return self._hal.get_device(key)
        except shal.LoadError as e:
            raise KeyError(f"rig has no device {key!r}: {e}") from None


@pytest.fixture(scope="session")
def rig(pytestconfig: pytest.Config) -> Generator[Rig]:
    """The rig from the setup file: one ``shal.load`` per session, closed at the end."""
    setup = _setup_or_fail(pytestconfig)
    with contextlib.ExitStack() as stack:
        stack.enter_context(approve.seat_default(pytestconfig))  # deny unless named
        source = copy.deepcopy(SIM_TOPOLOGY) if setup.source is None else str(setup.source)
        hal = stack.enter_context(shal.load(source))
        approve.bind_rig(pytestconfig, hal)  # allow: AutoApprove on this Hal only
        yield Rig(hal)


# --------------------------------------------------------------------------- #
# check() and the record
# --------------------------------------------------------------------------- #

class CheckFailed(AssertionError):
    """A ``check()`` outside its limits. Already a step in the record."""


@dataclass
class _Run:
    """What one test has produced so far, for its record."""

    started: str = ""
    steps: list[shal_record.Step] = field(default_factory=list)
    skipped: bool = False


_RUN = pytest.StashKey[_Run]()


def _run_of(item: pytest.Item) -> _Run:
    if _RUN not in item.stash:
        item.stash[_RUN] = _Run()
    return item.stash[_RUN]


def _finite(what: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"check(): {what} must be a number, got {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"check(): {what} must be finite")
    return value


class Check:
    """``check(name, value, unit=, min=, max=)``: a measurement row and an assert."""

    def __init__(self, run: _Run) -> None:
        self._run = run

    def __call__(
        self,
        name: str,
        value: float,
        unit: str = "",
        *,
        min: float | None = None,
        max: float | None = None,
    ) -> None:
        value = _finite("value", value)
        low = None if min is None else _finite("min", min)
        high = None if max is None else _finite("max", max)
        passed = (low is None or value >= low) and (high is None or value <= high)
        self._run.steps.append(shal_record.Step(
            name=name,
            verdict="pass" if passed else "fail",
            measurements=(shal_record.Measurement(
                name=name, value=value, unit=unit,
                limits=shal_record.Limits(min=low, max=high), passed=passed,
            ),),
        ))
        if not passed:
            shown = f"{value} {unit}".strip()
            raise CheckFailed(f"check {name!r}: {shown} is outside [{low}, {high}]")


@pytest.fixture
def check(request: pytest.FixtureRequest) -> Generator[Check]:
    """Assert a measured value against its limits, and record it."""
    _setup_or_fail(request.config)  # the record goes beside the setup
    # deny for this test too, so the approver does not depend on test order
    with approve.seat_default(request.config):
        yield Check(_run_of(request.node))


def _wants_record(item: pytest.Item) -> bool:
    """True only when the test's `rig` or `check` really runs THIS plugin's fixture.

    Walk the override chain the way pytest resolves it: start at the closest
    definition, and step to the one it overrides only while it requests its own
    name (``def rig(rig): ...``). A project's own, unrelated `check` or `rig`
    stops the walk, so it is not a SHAL test.
    """
    info = getattr(item, "_fixtureinfo", None)
    if info is None:
        return False
    for name in _FIXTURES:
        defs = info.name2fixturedefs.get(name, ())
        for fixturedef in reversed(defs):
            if getattr(fixturedef.func, "__module__", None) == __name__:
                return True
            if name not in fixturedef.argnames:
                break
    return False


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _unit(item: pytest.Item) -> str:
    marker = item.get_closest_marker("shal_unit")
    if marker is not None:
        value = marker.args[0] if marker.args else None
        if not isinstance(value, str) or not value.strip():
            raise ValueError("@pytest.mark.shal_unit needs a non-blank id")
        return value
    opt = item.config.getoption("--shal-unit")
    return str(opt) if opt else _DEFAULT_UNIT


def _note(item: pytest.Item, run: _Run, call: pytest.CallInfo[None]) -> None:
    """Turn one phase's outcome into steps (spec §3, verdict mapping)."""
    exc = call.excinfo
    if exc is None:
        return
    if exc.errisinstance(pytest.skip.Exception):
        run.skipped = True  # a skip writes no record
        return
    if call.when == "call":
        if exc.errisinstance(CheckFailed):
            return  # the check already recorded its step
        failed = exc.errisinstance((AssertionError, pytest.fail.Exception))
        run.steps.append(
            shal_record.Step(name=item.name, verdict="fail" if failed else "error")
        )
    else:
        run.steps.append(shal_record.Step(name=f"{item.name} [{call.when}]", verdict="error"))


def _denied_hint(mode: str) -> str:
    if mode == "prompt":
        return ("denied under --shal-approve=prompt: no one approved it (stdin is not "
                "a terminal, or the answer was not yes).")
    return (f"denied under --shal-approve={mode}. At a bench, run with "
            f"--shal-approve=prompt to be asked.")


def _write_record(item: pytest.Item, run: _Run, ended: str) -> str | None:
    """Write this test's one record. Returns an error message, or None."""
    setup = _setup(item.config)
    if isinstance(setup, str):
        return None  # no setup: the test already errored saying so; nowhere to write
    try:
        rec = shal_record.Record(
            record=f"rec-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{secrets.token_hex(3)}",
            unit=_unit(item),
            station=setup.station,
            sequence=item.nodeid,
            sequence_version=_git_blob_id(Path(item.path)),
            setup=setup.name,
            setup_version=setup.version,
            runner="pytest",
            started=run.started,
            ended=ended,
            steps=tuple(run.steps),
        )
        shal_record.write(rec, setup.store)
    except (OSError, ValueError, shal.Error) as e:
        return f"pytest-shal: no record written for {item.nodeid}: {e}"
    return None


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    report = yield
    if not _wants_record(item):
        return report  # not a SHAL test: untouched
    run = _run_of(item)
    if call.when == "setup":
        run.started = _iso(call.start)
    _note(item, run, call)
    if call.excinfo is not None and call.excinfo.errisinstance(shal.ApprovalDenied):
        report.sections.append(("shal approval", _denied_hint(approve.mode(item.config))))
    if call.when == "teardown" and not run.skipped:
        error = _write_record(item, run, _iso(call.stop))
        if error is not None:
            report.outcome = "failed"
            report.longrepr = error
    return report
