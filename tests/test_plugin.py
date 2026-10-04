import pytest_shal.plugin


def test_entry_point_registers_the_plugin(pytestconfig):
    # pytest registers a pytest11 entry point under its name, `shal`.
    assert pytestconfig.pluginmanager.get_plugin("shal") is pytest_shal.plugin


# -- #27: a HopError in the test body is ERROR, not FAILED -----------------


def run(pytester, *args):
    return pytester.runpytest_subprocess(*args, timeout=120)


def test_a_hoperror_in_the_test_body_is_reported_as_error_not_failed(pytester):
    pytester.makepyfile("""
        import shal

        def test_dead_link(rig):
            raise shal.HopError("no route delivered", path="/bench/ambient_temp",
                                hop="bench", delivered="no")
    """)
    result = run(pytester, "--shal-setup", "sim")
    result.assert_outcomes(errors=1, failed=0)
    result.stdout.fnmatch_lines(["*ERROR*test_dead_link*"])


def test_a_failing_assert_in_the_test_body_stays_failed(pytester):
    pytester.makepyfile("""
        def test_bad_reading(rig):
            assert rig.ambient_temp.read_celsius() < 0  # never true on the sim
    """)
    result = run(pytester, "--shal-setup", "sim")
    result.assert_outcomes(failed=1, errors=0)
