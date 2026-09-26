"""The approval mode: which of SHAL's own approvers is seated, and when (spec §4).

This file is the one place the mode, its default and its seating live, so the
fence can name it. The plugin never weakens SHAL's gate; it only chooses which
of SHAL's existing approvers is installed:

- ``deny`` (the default) -> ``shal.DenyAll``: a gated op fails the test at once,
  with the op named. Nothing waits on a prompt, so CI never hangs.
- ``prompt`` -> ``shal.ConsoleApprover``: a person at a bench is asked on the
  terminal. With no terminal (CI, a pipe) SHAL's own rule applies: it denies.
- ``allow`` -> ``shal.AutoApprove`` bound to the rig's Hal ONLY, through SHAL's
  ``Hal.bind_approver``, and only with ``--shal-setup sim``. It is never seated
  process-wide. A SHAL without ``Hal.bind_approver`` refuses ``allow`` with a
  usage error (checked by capability, not by version). While ``allow`` is in
  force, the process-wide approver is ``deny``.

When it is seated:

- A mode named with ``--shal-approve`` is seated for the whole session, from
  ``pytest_configure`` to the end, so it also covers a Hal a test loads itself
  (``allow`` seats ``deny`` there).
- With no option, ``deny`` is seated only while the plugin's own fixtures are
  up: the session ``rig`` fixture, and each test that uses the plugin's
  ``check``. A session that uses neither keeps SHAL's own default approver.
"""
from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest
import shal

MODES = ("deny", "prompt", "allow")
DEFAULT = "deny"
SIM = "sim"  # the --shal-setup value for the bundled sim

_SESSION = pytest.StashKey[contextlib.ExitStack]()


def can_allow() -> bool:
    """True when SHAL can bind an approver to one Hal (``Hal.bind_approver``)."""
    return hasattr(shal.Hal, "bind_approver")


def check_mode(config: pytest.Config) -> None:
    """Refuse a named mode the plugin cannot honour, before any test runs."""
    if config.getoption("--shal-approve") != "allow":
        return
    if not can_allow():
        raise pytest.UsageError(
            f"--shal-approve=allow needs SHAL's Hal.bind_approver, so the approval "
            f"is bound to the rig's Hal only; pyshal {shal.__version__} does not "
            f"have it. Use --shal-approve=deny or --shal-approve=prompt."
        )
    if config.getoption("--shal-setup") != SIM:
        raise pytest.UsageError("--shal-approve=allow is allowed only with --shal-setup sim")


def _terminal_prompt(config: pytest.Config) -> Callable[[str], str]:
    capman = config.pluginmanager.getplugin("capturemanager")

    def prompt(banner: str) -> str:
        # Ask on the real terminal, with pytest's capture out of the way.
        ctx = capman.global_and_fixture_disabled() if capman else contextlib.nullcontext()
        with ctx:
            sys.stdout.write(banner)
            sys.stdout.flush()
            line = sys.__stdin__.readline() if sys.__stdin__ else ""
        if not line:
            raise EOFError
        return line

    return prompt


def _process_approver(config: pytest.Config, mode: str) -> shal.Approver:
    """The process-wide approver for ``mode``. Never AutoApprove."""
    if mode == "prompt":
        # SHAL's ConsoleApprover checks `stream.isatty()`. pytest replaces
        # sys.stdin while it captures output, so hand it the real stdin.
        return shal.ConsoleApprover(stream=sys.__stdin__, prompt=_terminal_prompt(config))
    return shal.DenyAll()  # deny, and allow (whose AutoApprove is per-Hal only)


def mode(config: pytest.Config) -> str:
    """The mode in force: the one named on the command line, else the default."""
    named: str | None = config.getoption("--shal-approve")
    return named or DEFAULT


def seat_session(config: pytest.Config) -> None:
    """``pytest_configure``: seat a mode named on the command line, session-wide."""
    check_mode(config)
    named = config.getoption("--shal-approve")
    if named is None:
        return
    stack = contextlib.ExitStack()
    stack.enter_context(shal.approver(_process_approver(config, named)))
    config.stash[_SESSION] = stack
    config.add_cleanup(stack.close)


def seat_default(config: pytest.Config) -> AbstractContextManager[object]:
    """For the plugin's own fixtures: seat ``deny`` for as long as the fixture is
    up, unless a named mode already holds the whole session."""
    if _SESSION in config.stash:
        return contextlib.nullcontext()
    return shal.approver(shal.DenyAll())


def bind_rig(config: pytest.Config, hal: shal.Hal) -> None:
    """``allow`` only: bind AutoApprove to the rig's Hal, and to nothing else."""
    if mode(config) != "allow":
        return
    check_mode(config)  # already checked at configure; never bind without it
    getattr(hal, "bind_approver")(shal.AutoApprove())  # noqa: B009 — not in this pyshal's types
