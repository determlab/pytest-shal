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


def test_gate_with_no_terminal_denies(pytester):
    pytester.makepyfile(CONFIG_OP)
    result = run(pytester, "--shal-setup", "sim", "--shal-approve=gate")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*set_target denied*"])


def test_auto_on_the_sim_allows(pytester):
    pytester.makepyfile(CONFIG_OP)
    run(pytester, "--shal-setup", "sim", "--shal-approve=auto").assert_outcomes(passed=1)


def test_auto_without_the_sim_is_refused(pytester):
    pytester.makepyfile("def test_a(): pass")
    (pytester.path / "setup.yaml").write_text("shal_version: 1\nroot: {}\n")
    for args in ((), ("--shal-setup", "setup.yaml")):
        result = run(pytester, "--shal-approve=auto", *args)
        assert result.ret == pytest.ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines(["*--shal-approve=auto is allowed only with --shal-setup sim*"])


def test_named_mode_covers_a_hal_the_test_loads_itself(pytester):
    # --shal-approve=deny must hold even for a test that skips the rig fixture
    pytester.makepyfile("""
        import shal

        def test_own_hal():
            assert type(shal.get_approver()).__name__ == "DenyAll"
    """)
    run(pytester, "--shal-approve=deny").assert_outcomes(passed=1)
