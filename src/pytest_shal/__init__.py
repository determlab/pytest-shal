"""pytest-shal: a pytest plugin for SHAL.

The hooks, options and fixtures live in ``pytest_shal.plugin``, which the
``pytest11`` entry point (name ``shal``) loads. This package module holds none,
so ``pytest_plugins = ["pytest_shal"]`` in a conftest never registers them twice.

PYTEST_DONT_REWRITE: the entry point imports this package before a conftest
names it, so pytest could not rewrite it anyway; this marker stops the
"already imported" warning, which fails a session run with ``-W error``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

__version__ = "0.0.1"


def pytest_addhooks(pluginmanager: pytest.PytestPluginManager) -> None:
    """``pytest_plugins = ["pytest_shal"]``: load the plugin once, and only once.

    With entry points loaded (the usual case) the plugin is already registered
    and this does nothing. With autoload off (``PYTEST_DISABLE_PLUGIN_AUTOLOAD``)
    it registers the plugin under the entry point's name, ``shal``. ``-p no:shal``
    blocks that name, and is respected.
    """
    from pytest_shal import plugin

    if not pluginmanager.is_registered(plugin) and not pluginmanager.is_blocked("shal"):
        pluginmanager.register(plugin, "shal")
