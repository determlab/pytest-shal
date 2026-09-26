"""The gate stays on (spec §4): deny is the default, and nothing ever hangs.

These run pytest in a subprocess with stdin closed (not a terminal) and a
timeout, so a prompt that waited for a person would fail the test, not hang it.
"""
import pytest
from shal import record

CONFIG_OP = """
def test_set_target(rig):
    rig.ambient_temp.set_target(30.0)   # side_effect="config": gated
"""


def run(pytester, *args):
    return pytester.runpytest_subprocess(*args, timeout=120)


@pytest.mark.parametrize("args", [(), ("--shal-approve=deny",)], ids=["default", "deny"])
def test_config_op_under_deny_fails_with_the_op_named(pytester, args):
    pytester.makepyfile(CONFIG_OP)
    result = run(pytester, "--shal-setup", "sim", *args)
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "*ApprovalDenied*set_target denied by the approval policy*",
        "*denied under --shal-approve=deny*",
    ])
    (rec,) = record.read(pytester.path)
    assert rec.verdict == "error"  # an exception outside an assert (spec §3)


def test_prompt_with_no_terminal_denies(pytester):
    pytester.makepyfile(CONFIG_OP)
    result = run(pytester, "--shal-setup", "sim", "--shal-approve=prompt")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "*set_target denied*",
        "*denied under --shal-approve=prompt: no one approved it*",
    ])


@pytest.mark.parametrize("args", [("--shal-setup", "sim"), ()], ids=["sim", "no-setup"])
def test_allow_is_refused_without_hal_bind_approver(pytester, args):
    # allow is bound to the rig's Hal only; this SHAL cannot do that, so: refused
    import shal
    assert not hasattr(shal.Hal, "bind_approver")
    pytester.makepyfile(CONFIG_OP)
    result = run(pytester, "--shal-approve=allow", *args)
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines([
        f"*--shal-approve=allow needs SHAL's Hal.bind_approver*pyshal {shal.__version__}*",
    ])


def test_named_mode_covers_a_hal_the_test_loads_itself(pytester):
    # --shal-approve=deny must hold even for a test that skips the rig fixture
    pytester.makepyfile("""
        import shal

        def test_own_hal():
            assert type(shal.get_approver()).__name__ == "DenyAll"
    """)
    run(pytester, "--shal-approve=deny").assert_outcomes(passed=1)


def test_deny_does_not_depend_on_test_order(pytester):
    # a check-only test that runs BEFORE any rig test still gets deny, scoped to it
    pytester.makepyfile("""
        import shal

        def test_1_check_only(check):
            assert type(shal.get_approver()).__name__ == "DenyAll"

        def test_2_plain():
            assert type(shal.get_approver()).__name__ == "ConsoleApprover"

        def test_3_rig(rig):
            assert type(shal.get_approver()).__name__ == "DenyAll"

        def test_4_check_after_rig(check):
            assert type(shal.get_approver()).__name__ == "DenyAll"
    """)
    run(pytester, "--shal-setup", "sim", "-p", "no:randomly").assert_outcomes(passed=4)


def test_allow_binds_the_rig_hal_only(pytester, monkeypatch):
    # a stand-in for SHAL's future Hal.bind_approver: the plugin must call it on
    # the rig's Hal, and keep deny as the process-wide approver
    import shal
    bound = []

    def bind_approver(hal, a):
        bound.append(a)
        hal.bound_for_test = a

    monkeypatch.setattr(shal.Hal, "bind_approver", bind_approver, raising=False)
    pytester.makepyfile("""
        import shal

        def test_rig(rig):
            assert type(shal.get_approver()).__name__ == "DenyAll"
            # bound to THIS rig's Hal
            assert type(rig._hal.bound_for_test).__name__ == "AutoApprove"
    """)
    pytester.runpytest("--shal-setup", "sim", "--shal-approve=allow").assert_outcomes(passed=1)
    assert [type(a).__name__ for a in bound] == ["AutoApprove"]
