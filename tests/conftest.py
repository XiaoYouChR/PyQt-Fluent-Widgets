from __future__ import annotations

import gc
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QColor

import qfluentwidgets
from qfluentwidgets import Theme, qconfig

REPO_ROOT = Path(__file__).resolve().parent.parent


def runPython(code: str, *, extraEnv: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    if extraEnv:
        env.update(extraEnv)
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )


def waitReclaim(qtbot, rounds: int = 2, waitMs: int = 50) -> None:
    for _ in range(rounds):
        qtbot.wait(waitMs)
        gc.collect()


@pytest.fixture
def fluentApp(qapp):
    qfluentwidgets.unload()
    qapp.setStyleSheet("")
    qconfig.set(qconfig.themeMode, Theme.LIGHT, save=False)
    qconfig.theme = Theme.LIGHT
    qconfig.set(qconfig.themeColor, QColor("#009faa"), save=False)
    qfluentwidgets.load(qapp)
    yield qapp
    qfluentwidgets.unload()
    qapp.setStyleSheet("")
