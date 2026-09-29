"""The error messages check() and the shal_unit marker give a test engineer."""
import pytest
from shal import record


def records(path):
    return record.read(path)


@pytest.mark.parametrize(
    "call, message",
    [
        ('check("x", "5")', "*must be a number, got str*"),
        ('check("x", True)', "*must be a number, got bool*"),
        ('check("x", 1, min=float("inf"))', "*min must be finite*"),
    ],
)
def test_bad_check_input_says_why(pytester, call, message):
    pytester.makeconftest('pytest_plugins = ["pytest_shal"]')
    pytester.makepyfile(f"""
        def test_bad(check):
            {call}
    """)
    result = pytester.runpytest("--shal-setup", "sim")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([message])
    (rec,) = records(pytester.path)
    assert rec.verdict == "error"


def test_blank_marker_says_why(pytester):
    pytester.makeconftest('pytest_plugins = ["pytest_shal"]')
    pytester.makepyfile("""
        import pytest

        @pytest.mark.shal_unit("  ")
        def test_bad(check):
            check("a", 1)
    """)
    result = pytester.runpytest("--shal-setup", "sim", "--strict-markers")
    result.stdout.fnmatch_lines(["*shal_unit needs a non-blank id*"])
    assert result.ret != 0
    assert all(r.verdict == "error" for r in records(pytester.path))
