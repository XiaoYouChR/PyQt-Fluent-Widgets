"""
PySide6-Fluent-Widgets
======================
A fluent design widgets library based on PySide6.

:copyright: (c) 2021 by zhiyiYo.
:license: GPLv3 for non-commercial project, see README for more details.
"""

__version__ = "1.11.3"
__author__ = "zhiyiYo"

from ._symbols import listDir, listExports, loadExport

__all__ = listExports(__name__)


def __getattr__(name: str):
    return loadExport(__name__, globals(), name)


def __dir__() -> list[str]:
    return listDir(__name__)
