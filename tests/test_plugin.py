import pytest_shal.plugin


def test_entry_point_registers_the_plugin(pytestconfig):
    # pytest registers a pytest11 entry point under its name, `shal`.
    assert pytestconfig.pluginmanager.get_plugin("shal") is pytest_shal.plugin
