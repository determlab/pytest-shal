"""The gate stays on (spec §4): deny is the default, and nothing ever hangs.

These run pytest in a subprocess with stdin closed (not a terminal) and a
timeout, so a prompt that waited for a person would fail the test, not hang it.
"""
import pytest
import shal
from shal import record

from pytest_shal import approve

# allow needs shal.load(approver=) (shal #217). The pinned pyshal may be older, so
# the allow tests run on the SHAL that has it, and the refusal test on one that
# does not. Checked by capability, the same check the plugin makes.
HAS_LOAD_APPROVER = approve.can_allow()
needs_load_approver = pytest.mark.skipif(
    not HAS_LOAD_APPROVER,
    reason=f"installed pyshal {shal.__version__} has no shal.load(approver=) "
           f"(shal #217, PR #219); allow is refused here, see the refusal test",
)
old_shal_only = pytest.mark.skipif(
    HAS_LOAD_APPROVER,
    reason="installed pyshal has shal.load(approver=); allow is not refused",
)

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


@old_shal_only
@pytest.mark.parametrize("args", [("--shal-setup", "sim"), ()], ids=["sim", "no-setup"])
def test_allow_is_refused_without_load_approver(pytester, args):
    # allow holds for the rig's Hal only; this SHAL cannot do that, so: refused
    pytester.makepyfile(CONFIG_OP)
    result = run(pytester, "--shal-approve=allow", *args)
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines([
        f"*--shal-approve=allow needs {approve.NEEDS}*pyshal {shal.__version__}*",
    ])
    assert approve.NEEDS == ("pyshal with shal.load(approver=) — determlab/shal#217 / "
                             "PR #219 (commit ae0113a), not yet on PyPI")


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


@needs_load_approver
def test_allow_approves_on_the_rig_hal_only(pytester):
    # the rig's gated op is approved; the process keeps deny, and a Hal the test
    # loads itself is still denied
    pytester.makepyfile("""
        import copy

        import pytest
        import shal
        from pytest_shal.plugin import SIM_TOPOLOGY

        def test_rig(rig):
            rig.ambient_temp.set_target(30.0)   # gated: approved on the rig's Hal
            assert type(shal.get_approver()).__name__ == "DenyAll"

        def test_own_hal_is_denied(rig):
            with shal.load(copy.deepcopy(SIM_TOPOLOGY)) as hal:
                with pytest.raises(shal.ApprovalDenied):
                    hal.get_device("ambient_temp").set_target(30.0)
    """)
    result = run(pytester, "--shal-setup", "sim", "--shal-approve=allow")
    result.assert_outcomes(passed=2)
    assert {r.verdict for r in record.read(pytester.path)} == {"pass"}


@needs_load_approver
def test_allow_needs_the_sim(pytester):
    pytester.makepyfile(CONFIG_OP)
    result = run(pytester, "--shal-approve=allow")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*allow is allowed only with --shal-setup sim*"])


@pytest.mark.parametrize("args", [(), ("--shal-approve=deny",), ("--shal-approve=prompt",)],
                         ids=["default", "deny", "prompt"])
def test_only_allow_gives_the_rig_an_approver(pytester, args):
    # deny and prompt pass no approver= to the rig's load: the host's decides
    config = pytester.parseconfig("--shal-setup", "sim", *args)
    assert approve.rig_approver(config) == {}
