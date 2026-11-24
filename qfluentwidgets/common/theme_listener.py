# coding:utf-8
from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QGuiApplication

from .config import Theme, qconfig


class SystemThemeListener(QThread):
    """ System theme listener backed by Qt 6 colorSchemeChanged """

    systemThemeChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._isConnected = False

    def start(self, priority=QThread.Priority.InheritPriority):
        app = QGuiApplication.instance()
        if app is not None:
            if not self._isConnected:
                app.styleHints().colorSchemeChanged.connect(self._onColorSchemeChanged)
                self._isConnected = True
            return
        super().start(priority)

    def terminate(self):
        self._disconnectSignal()
        super().terminate()

    def quit(self):
        self._disconnectSignal()
        super().quit()

    def _disconnectSignal(self):
        if not self._isConnected:
            return
        self._isConnected = False
        app = QGuiApplication.instance()
        if app is not None:
            try:
                app.styleHints().colorSchemeChanged.disconnect(self._onColorSchemeChanged)
            except (RuntimeError, TypeError):
                pass

    def _onColorSchemeChanged(self, scheme: Qt.ColorScheme):
        if scheme == Qt.ColorScheme.Dark:
            self._onThemeChanged("dark")
        elif scheme == Qt.ColorScheme.Light:
            self._onThemeChanged("light")

    def run(self):
        import sys
        import darkdetect

        if sys.platform == "win32":
            darkdetect.listener(self._onThemeChanged)
            return

        while not self.isInterruptionRequested():
            t = (darkdetect.theme() or "light").lower()
            theme = Theme.DARK if t == "dark" else Theme.LIGHT
            if theme != qconfig.theme:
                self._onThemeChanged(t)
                self.msleep(2000)
            else:
                self.msleep(1000)

    def _onThemeChanged(self, theme: str):
        theme = Theme.DARK if theme.lower() == "dark" else Theme.LIGHT

        if qconfig.themeMode.value != Theme.AUTO or theme == qconfig.theme:
            return

        qconfig.theme = Theme.AUTO
        qconfig._cfg.themeChanged.emit(Theme.AUTO)
        self.systemThemeChanged.emit()
