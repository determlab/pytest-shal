"""``pytest_terminal_summary``: where the records went, and the failing record ids."""
import re

_RECORD_ID = re.compile(r"rec-\d{8}T\d{6}-[0-9a-f]{6}")


def test_summary_shows_counts_and_the_failing_record(pytester):
    pytester.makepyfile("""
        def test_ok(rig, check):
            check("room", rig.ambient_temp.read_celsius(), "celsius", min=-40, max=125)

        def test_ripple(rig, check):
            check("ripple", 999, "mV", min=0, max=10)
    """)
    result = pytester.runpytest_subprocess("--shal-setup", "sim", "-p", "no:cacheprovider")
    result.assert_outcomes(passed=1, failed=1)
    result.stdout.fnmatch_lines([
        "*shal records*",
        "2 records in*records.db (pass 1, fail 1, error 0), unit bench",
        "fail*test_summary_shows_counts_and_the_failing_record.py::test_ripple*",
    ])
    (fail_line,) = [
        line for line in result.outlines if line.startswith("fail") and "test_ripple" in line
    ]
    assert _RECORD_ID.search(fail_line)


def test_no_summary_when_the_session_writes_no_record(pytester):
    pytester.makepyfile("""
        def test_plain():
            assert 1 == 1
    """)
    result = pytester.runpytest_subprocess("-p", "no:cacheprovider")
    result.assert_outcomes(passed=1)
    assert "shal records" not in result.stdout.str()
