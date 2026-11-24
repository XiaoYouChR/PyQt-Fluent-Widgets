# coding:utf-8
from PySide6.QtCore import QResource

from . import RCC_PATH


def qInitResources() -> bool:
    return QResource.registerResource(str(RCC_PATH))


def qCleanupResources() -> bool:
    return QResource.unregisterResource(str(RCC_PATH))
