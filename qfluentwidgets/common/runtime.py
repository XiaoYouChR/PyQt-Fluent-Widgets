# coding:utf-8
from __future__ import annotations

import sys
import weakref

from PySide6.QtCore import QResource
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from .._rc import RCC_PATH

_appRef: weakref.ref[QApplication] | None = None


def load(app: QApplication) -> None:
    """Register QFluentWidgets binary resources and application-level stylesheet."""
    global _appRef

    if not isinstance(app, QApplication):
        raise TypeError(f"Expected QApplication instance, got {type(app).__name__}")
    if not isValid(app):
        raise RuntimeError("Cannot load qfluentwidgets onto a destroyed QApplication")

    currentApp = _appRef() if _appRef is not None else None
    if currentApp is app and isValid(currentApp):
        from . import style_sheet
        style_sheet.syncAppBundle(app)
        return
    if _appRef is not None:
        unload()

    if not RCC_PATH.is_file():
        raise FileNotFoundError(RCC_PATH)
    if not QResource.registerResource(str(RCC_PATH)):
        raise RuntimeError(f"Failed to register Qt resource: {RCC_PATH}")

    _appRef = weakref.ref(app)
    from . import style_sheet
    style_sheet.installAppBundle(app)
    app.aboutToQuit.connect(unload)


def unload() -> None:
    """Remove QFluentWidgets managed stylesheet, caches, global registries, and binary resources."""
    global _appRef

    ref = _appRef
    if ref is None:
        return
    _appRef = None

    app = ref()
    liveApp = app if app is not None and isValid(app) else None
    if liveApp is not None:
        try:
            liveApp.aboutToQuit.disconnect(unload)
        except (RuntimeError, TypeError):
            pass

    from . import style_sheet
    style_sheet.resetAppBundle(liveApp)

    if "qfluentwidgets.common.icon" in sys.modules:
        sys.modules["qfluentwidgets.common.icon"].clearCache()
    if "qfluentwidgets.common.router" in sys.modules:
        sys.modules["qfluentwidgets.common.router"].qrouter.clear()
    if "qfluentwidgets.components.widgets.info_bar" in sys.modules:
        sys.modules["qfluentwidgets.components.widgets.info_bar"].InfoBarManager.clearAll()

    QResource.unregisterResource(str(RCC_PATH))
