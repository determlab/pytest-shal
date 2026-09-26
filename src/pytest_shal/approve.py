"""The approval mode: which of SHAL's own approvers the plugin seats (spec §4).

This file is the one place the mode lives, so the fence can name it. The plugin
never weakens SHAL's gate; it only chooses which existing approver is installed:

- ``deny`` (the default) -> ``shal.DenyAll``: a gated op fails the test at once,
  with the op named. Nothing waits on a prompt, so CI never hangs.
- ``gate`` -> ``shal.ConsoleApprover``: a person at a bench is asked on the
  terminal. With no terminal (CI, a pipe) SHAL's own rule applies: it denies.
- ``auto`` -> ``shal.AutoApprove``: every gated op is allowed. Refused unless the
  setup is the bundled sim (``--shal-setup sim``), so it never reaches hardware.
"""
from __future__ import annotations

import sys
from collections.abc import Callable

import pytest
import shal

MODES = ("deny", "gate", "auto")
DEFAULT = "deny"


def approver_for(
    mode: str, *, setup_is_sim: bool, prompt: Callable[[str], str]
) -> shal.Approver:
    """The approver for ``mode``. Never weaker than the mode asked for.

    ``prompt`` asks a person (``gate`` only); the plugin passes one that reads the
    real terminal with pytest's output capture suspended.
    """
    if mode == "deny":
        return shal.DenyAll()
    if mode == "gate":
        # SHAL's ConsoleApprover checks `stream.isatty()`. pytest replaces
        # sys.stdin while it captures output, so hand it the real stdin.
        return shal.ConsoleApprover(stream=sys.__stdin__, prompt=prompt)
    if mode == "auto":
        if not setup_is_sim:
            raise pytest.UsageError(
                "--shal-approve=auto is allowed only with --shal-setup sim "
                "(it approves every gated op, so it must not reach hardware)"
            )
        return shal.AutoApprove()
    raise pytest.UsageError(
        f"--shal-approve must be one of {', '.join(MODES)}, got {mode!r}"
    )
