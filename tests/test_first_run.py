"""The first ten minutes, as a test (spec §5, R4): a clean venv, the built wheel,
`pytest --shal-setup sim` on a tiny test, and one record written.

It builds the wheel with pip and installs it with its dependencies into a fresh
venv, so it needs network access (pyshal comes from PyPI).
"""
import subprocess
import sys
import venv
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

FIRST_TEST = """
def test_first(rig, check):
    check("room", rig.ambient_temp.read_celsius(), "celsius", min=-40, max=125)
"""

READ_BACK = """
from shal import record
recs = record.read(".")
print(len(recs), recs[0].verdict, recs[0].runner, recs[0].station)
"""


def sh(*args, cwd=None):
    out = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=900,
                         check=False)
    assert out.returncode == 0, f"{args}\n{out.stdout}\n{out.stderr}"
    return out.stdout


def test_clean_venv_first_run(tmp_path):
    dist = tmp_path / "dist"
    sh(sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", str(dist), str(REPO))
    (wheel,) = dist.glob("pytest_shal-*.whl")

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    py = env_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    sh(str(py), "-m", "pip", "install", "-q", str(wheel))

    work = tmp_path / "work"
    work.mkdir()
    (work / "test_first.py").write_text(FIRST_TEST)
    out = sh(str(py), "-m", "pytest", "--shal-setup", "sim", "-p", "no:cacheprovider",
             cwd=work)
    assert "1 passed" in out
    assert sh(str(py), "-c", READ_BACK, cwd=work).split() == ["1", "pass", "pytest", "sim"]
