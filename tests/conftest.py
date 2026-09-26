import pytest

pytest_plugins = ["pytester"]


@pytest.fixture(autouse=True)
def _utf8_subprocess(monkeypatch):
    # pytester decodes a subprocess's output as UTF-8; on Windows the child would
    # write the console code page (shal's messages carry an em dash).
    monkeypatch.setenv("PYTHONUTF8", "1")
