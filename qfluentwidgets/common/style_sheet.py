# coding:utf-8
from enum import Enum
from string import Template
import sys
from typing import List, Union
import weakref

from PySide6.QtCore import QFile, QObject, QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QApplication, QPushButton
from shiboken6 import isValid

from .config import qconfig, Theme, isDarkTheme

MANAGED_BEGIN = "/* qfw:begin */"
MANAGED_END = "/* qfw:end */"


class QssTemplate(Template):
    """ style sheet template """

    delimiter = '--'


class StyleSheetBase:
    """ Style sheet base class """

    def path(self, theme=Theme.AUTO):
        """ get the path of style sheet """
        raise NotImplementedError

    def content(self, theme=Theme.AUTO):
        """ get the content of style sheet """
        return getStyleSheetFromFile(self.path(theme))

    def apply(self, widget: QWidget, theme=Theme.AUTO):
        """ apply style sheet to widget """
        setStyleSheet(widget, self, theme)


class FluentStyleSheet(StyleSheetBase, Enum):
    """ Fluent style sheet """

    MENU = "menu"
    LABEL = "label"
    PIVOT = "pivot"
    BUTTON = "button"
    DIALOG = "dialog"
    SLIDER = "slider"
    INFO_BAR = "info_bar"
    SPIN_BOX = "spin_box"
    TAB_VIEW = "tab_view"
    TOOL_TIP = "tool_tip"
    CHECK_BOX = "check_box"
    COMBO_BOX = "combo_box"
    FLIP_VIEW = "flip_view"
    LINE_EDIT = "line_edit"
    LIST_VIEW = "list_view"
    TREE_VIEW = "tree_view"
    INFO_BADGE = "info_badge"
    PIPS_PAGER = "pips_pager"
    TABLE_VIEW = "table_view"
    CARD_WIDGET = "card_widget"
    TIME_PICKER = "time_picker"
    COLOR_DIALOG = "color_dialog"
    MEDIA_PLAYER = "media_player"
    SETTING_CARD = "setting_card"
    TEACHING_TIP = "teaching_tip"
    FLUENT_WINDOW = "fluent_window"
    SWITCH_BUTTON = "switch_button"
    MESSAGE_DIALOG = "message_dialog"
    STATE_TOOL_TIP = "state_tool_tip"
    CALENDAR_PICKER = "calendar_picker"
    FOLDER_LIST_DIALOG = "folder_list_dialog"
    SETTING_CARD_GROUP = "setting_card_group"
    EXPAND_SETTING_CARD = "expand_setting_card"
    NAVIGATION_INTERFACE = "navigation_interface"

    def path(self, theme=Theme.AUTO):
        theme = qconfig.theme if theme == Theme.AUTO else theme
        return f":/qfluentwidgets/qss/{theme.value.lower()}/{self.value}.qss"


APP_SHEETS = frozenset({
    FluentStyleSheet.BUTTON,
    FluentStyleSheet.CALENDAR_PICKER,
    FluentStyleSheet.CARD_WIDGET,
    FluentStyleSheet.CHECK_BOX,
    FluentStyleSheet.COMBO_BOX,
    FluentStyleSheet.FLIP_VIEW,
    FluentStyleSheet.FLUENT_WINDOW,
    FluentStyleSheet.INFO_BADGE,
    FluentStyleSheet.LABEL,
    FluentStyleSheet.LINE_EDIT,
    FluentStyleSheet.LIST_VIEW,
    FluentStyleSheet.MENU,
    FluentStyleSheet.PIPS_PAGER,
    FluentStyleSheet.SETTING_CARD_GROUP,
    FluentStyleSheet.SPIN_BOX,
    FluentStyleSheet.TIME_PICKER,
})

_APP_SHEET_ORDER = tuple(s for s in FluentStyleSheet if s in APP_SHEETS)


class StyleSheetFile(StyleSheetBase):
    """ Style sheet file """

    def __init__(self, path: str):
        super().__init__()
        self.filePath = path

    def path(self, theme=Theme.AUTO):
        return self.filePath


class CustomStyleSheet(StyleSheetBase):
    """ Custom style sheet """

    DARK_QSS_KEY = 'darkCustomQss'
    LIGHT_QSS_KEY = 'lightCustomQss'

    def __init__(self, widget: QWidget) -> None:
        super().__init__()
        self._widget = weakref.ref(widget)

    def path(self, theme=Theme.AUTO):
        return ''

    @property
    def widget(self):
        return self._widget()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CustomStyleSheet):
            return False

        return other.widget is self.widget

    def setCustomStyleSheet(self, lightQss: str, darkQss: str):
        """ set custom style sheet in light and dark theme mode """
        widget = self.widget
        if widget is not None and isValid(widget):
            widget.setProperty(self.LIGHT_QSS_KEY, lightQss)
            widget.setProperty(self.DARK_QSS_KEY, darkQss)
            addStyleSheet(widget, self)
        return self

    def setLightStyleSheet(self, qss: str):
        """ set the style sheet in light mode """
        widget = self.widget
        if widget is not None and isValid(widget):
            widget.setProperty(self.LIGHT_QSS_KEY, qss)
            addStyleSheet(widget, self)
        return self

    def setDarkStyleSheet(self, qss: str):
        """ set the style sheet in dark mode """
        widget = self.widget
        if widget is not None and isValid(widget):
            widget.setProperty(self.DARK_QSS_KEY, qss)
            addStyleSheet(widget, self)
        return self

    def lightStyleSheet(self) -> str:
        widget = self.widget
        if widget is None or not isValid(widget):
            return ''

        return widget.property(self.LIGHT_QSS_KEY) or ''

    def darkStyleSheet(self) -> str:
        widget = self.widget
        if widget is None or not isValid(widget):
            return ''

        return widget.property(self.DARK_QSS_KEY) or ''

    def content(self, theme=Theme.AUTO) -> str:
        theme = qconfig.theme if theme == Theme.AUTO else theme

        if theme == Theme.LIGHT:
            return self.lightStyleSheet()

        return self.darkStyleSheet()


class StyleSheetCompose(StyleSheetBase):
    """ Style sheet compose """

    def __init__(self, sources: List[StyleSheetBase]):
        super().__init__()
        self.sources = sources

    def content(self, theme=Theme.AUTO):
        return '\n'.join([i.content(theme) for i in self.sources])

    def add(self, source: StyleSheetBase):
        """ add style sheet source """
        if source is self or source in self.sources:
            return

        self.sources.append(source)

    def remove(self, source: StyleSheetBase):
        """ remove style sheet source """
        if source not in self.sources:
            return

        self.sources.remove(source)


_rawQssByPath: dict[str, str] = {}
_appQssCache: dict[tuple, str] = {}
_installedKey: tuple | None = None
_isLazySync = False


def _renderKey() -> tuple[Theme, int, tuple[str, ...]]:
    color = qconfig.get(qconfig._cfg.themeColor)
    fonts = tuple(qconfig.get(qconfig.fontFamilies))
    return (qconfig.theme, color.rgba(), fonts)


def _templateVars(fonts: tuple[str, ...] | None = None) -> dict[str, str]:
    mappings = {c.value: c.name() for c in ThemeColor._member_map_.values()}
    fontList = fonts if fonts is not None else tuple(qconfig.get(qconfig.fontFamilies))
    mappings["FontFamilies"] = ",".join(f"'{i}'" for i in fontList)
    return mappings


def _readFileText(file: Union[str, QFile]) -> str:
    f = QFile(file)
    f.open(QFile.ReadOnly)
    qss = str(f.readAll(), encoding='utf-8')
    f.close()
    return qss


def _loadRawQss(path: str) -> str:
    if path.startswith(":/qfluentwidgets/"):
        cached = _rawQssByPath.get(path)
        if cached is not None:
            return cached
        text = _readFileText(path)
        _rawQssByPath[path] = text
        return text
    return _readFileText(path)


def _renderAppQss(key: tuple[Theme, int, tuple[str, ...]]) -> str:
    cached = _appQssCache.get(key)
    if cached is not None:
        return cached
    if len(_appQssCache) >= 4:
        _appQssCache.clear()

    theme, _, fonts = key
    raw = "\n".join(_loadRawQss(sheet.path(theme)) for sheet in _APP_SHEET_ORDER)
    rendered = QssTemplate(raw).safe_substitute(_templateVars(fonts))
    _appQssCache[key] = rendered
    return rendered


def _mergeManagedBlock(current: str, block: str) -> str:
    begin = current.find(MANAGED_BEGIN)
    if begin != -1:
        end = current.find(MANAGED_END, begin)
        if end != -1:
            return current[:begin] + block + current[end + len(MANAGED_END):]
    if current:
        return block + "\n" + current
    return block


def _stripManagedBlock(current: str) -> str:
    begin = current.find(MANAGED_BEGIN)
    if begin == -1:
        return current
    end = current.find(MANAGED_END, begin)
    if end == -1:
        return current
    before = current[:begin].rstrip("\n")
    after = current[end + len(MANAGED_END):].lstrip("\n")
    if before and after:
        return before + "\n" + after
    return before or after


class StyleSheetBinding(QObject):
    """Widget-owned child binding for widget-level and custom stylesheets.

    Destroyed automatically by Qt with its parent widget and synced natively on
    QEvent.StyleChange and QEvent.Show.
    """

    def __init__(self, widget: QWidget, compose: StyleSheetCompose) -> None:
        super().__init__(parent=widget)
        self.compose = compose
        self._appliedKey: tuple | None = None
        widget.installEventFilter(self)

    def applyNow(self, theme: Theme = Theme.AUTO) -> None:
        widget = self.parent()
        if widget is None or not isValid(widget):
            return
        qss = getStyleSheet(self.compose, theme)
        self._appliedKey = _renderKey()
        if qss != widget.styleSheet():
            widget.setStyleSheet(qss)

    def detach(self) -> None:
        widget = self.parent()
        if widget is not None and isValid(widget):
            widget.removeEventFilter(self)
        self.setParent(None)
        self.deleteLater()

    def eventFilter(self, obj: QObject, e: QEvent) -> bool:
        if obj is not self.parent() or _installedKey is None:
            return False

        eventType = e.type()
        if eventType == QEvent.Type.StyleChange:
            if self._appliedKey == _renderKey() or (_isLazySync and not obj.isVisible()):
                return False
            self.applyNow(Theme.AUTO)
        elif eventType == QEvent.Type.Show:
            if self._appliedKey != _renderKey():
                self.applyNow(Theme.AUTO)

        return False


def _bindingOf(widget: QWidget) -> StyleSheetBinding | None:
    if not isValid(widget):
        return None
    return widget.findChild(StyleSheetBinding, options=Qt.FindChildOption.FindDirectChildrenOnly)


def _registerBinding(source, widget: QWidget, reset: bool = True) -> StyleSheetBinding:
    if isinstance(source, str):
        source = StyleSheetFile(source)

    binding = _bindingOf(widget)
    if isinstance(source, StyleSheetCompose):
        if binding is None:
            return StyleSheetBinding(widget, source)
        if reset:
            binding.compose = source
        else:
            for item in source.sources:
                binding.compose.add(item)
        return binding

    if binding is None:
        sources = [source] if isinstance(source, CustomStyleSheet) else [source, CustomStyleSheet(widget)]
        return StyleSheetBinding(widget, StyleSheetCompose(sources))

    if reset:
        sources = [source] if isinstance(source, CustomStyleSheet) else [source, CustomStyleSheet(widget)]
        binding.compose = StyleSheetCompose(sources)
    else:
        binding.compose.add(source)
    return binding


def _applyAppSheet(widget: QWidget, source: FluentStyleSheet, theme: Theme, register: bool) -> bool:
    if not register or theme != Theme.AUTO or source not in APP_SHEETS:
        return False

    binding = _bindingOf(widget)
    if binding is not None:
        customs = [
            s for s in binding.compose.sources
            if isinstance(s, CustomStyleSheet) and (s.lightStyleSheet() or s.darkStyleSheet())
        ]
        if customs:
            binding.compose = StyleSheetCompose(customs)
            binding.applyNow(Theme.AUTO)
        else:
            binding.detach()
            if widget.styleSheet():
                widget.setStyleSheet("")
    # macOS QMacStyle caches Aqua button margins in QPushButton C++ init before app QSS matches the subclass
    if sys.platform == "darwin" and isinstance(widget, QPushButton):
        widget.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
    return True


def installAppBundle(app: QApplication) -> bool:
    return syncAppBundle(app, force=True)


def syncAppBundle(app: QApplication | None = None, force: bool = False) -> bool:
    global _installedKey
    if not force and _installedKey is None:
        return False
    if app is None:
        app = QApplication.instance()
    if app is None or not isValid(app):
        return False

    key = _renderKey()
    current = app.styleSheet()
    if not force and _installedKey == key and MANAGED_BEGIN in current:
        return False

    rendered = _renderAppQss(key)
    block = f"{MANAGED_BEGIN}\n{rendered}\n{MANAGED_END}"
    newQss = _mergeManagedBlock(current, block)
    _installedKey = key
    if newQss != current:
        app.setStyleSheet(newQss)
        return True
    return False


def resetAppBundle(app: QApplication | None = None) -> None:
    global _installedKey
    if app is None:
        app = QApplication.instance()
    if app is not None and isValid(app) and _installedKey is not None:
        stripped = _stripManagedBlock(app.styleSheet())
        if stripped != app.styleSheet():
            app.setStyleSheet(stripped)
    _installedKey = None
    _rawQssByPath.clear()
    _appQssCache.clear()


def _iterAllBindings(app: QApplication) -> list[StyleSheetBinding]:
    seen: set[int] = set()
    bindings: list[StyleSheetBinding] = []
    for top in app.topLevelWidgets():
        if not isValid(top):
            continue
        direct = _bindingOf(top)
        if direct is not None and id(direct) not in seen:
            seen.add(id(direct))
            bindings.append(direct)
        for child in top.findChildren(StyleSheetBinding):
            if isValid(child) and id(child) not in seen:
                seen.add(id(child))
                bindings.append(child)
    return bindings


def applyThemeColor(qss: str):
    """ apply theme color to style sheet """
    return QssTemplate(qss).safe_substitute(_templateVars())


def renderQss(qss: str):
    """ render font and theme color to style sheet """
    return QssTemplate(qss).safe_substitute(_templateVars())


def getStyleSheetFromFile(file: Union[str, QFile]):
    """ get style sheet from qss file """
    if isinstance(file, str):
        return _loadRawQss(file)
    return _readFileText(file)


def getStyleSheet(source: Union[str, StyleSheetBase], theme=Theme.AUTO):
    """ get style sheet """
    if isinstance(source, str):
        source = StyleSheetFile(source)

    return renderQss(source.content(theme))


def setStyleSheet(widget: QWidget, source: Union[str, StyleSheetBase], theme=Theme.AUTO, register=True):
    """ set the style sheet of widget """
    if isinstance(source, FluentStyleSheet) and _applyAppSheet(widget, source, theme, register):
        return

    if register:
        _registerBinding(source, widget, reset=True).applyNow(theme)
    else:
        qss = getStyleSheet(source, theme)
        if qss != widget.styleSheet():
            widget.setStyleSheet(qss)


def setCustomStyleSheet(widget: QWidget, lightQss: str, darkQss: str):
    """ set custom style sheet """
    CustomStyleSheet(widget).setCustomStyleSheet(lightQss, darkQss)


def addStyleSheet(widget: QWidget, source: Union[str, StyleSheetBase], theme=Theme.AUTO, register=True):
    """ add style sheet to widget """
    if isinstance(source, FluentStyleSheet) and _applyAppSheet(widget, source, theme, register):
        return

    if register:
        _registerBinding(source, widget, reset=False).applyNow(theme)
    else:
        qss = widget.styleSheet() + '\n' + getStyleSheet(source, theme)
        if qss.rstrip() != widget.styleSheet().rstrip():
            widget.setStyleSheet(qss)


def updateStyleSheet(lazy=False):
    """ update the style sheet of all fluent widgets """
    global _isLazySync
    if _installedKey is None:
        return
    app = QApplication.instance()
    if app is None or not isValid(app):
        return

    _isLazySync = lazy
    try:
        didAppChange = syncAppBundle(app)
        if not didAppChange or not lazy:
            key = _renderKey()
            for binding in _iterAllBindings(app):
                if isValid(binding) and (not didAppChange or binding._appliedKey != key):
                    widget = binding.parent()
                    if widget is not None and isValid(widget) and (not lazy or widget.isVisible()):
                        binding.applyNow(Theme.AUTO)
    finally:
        _isLazySync = False


def setTheme(theme: Theme, save=False, lazy=False):
    """ set the theme of application """
    qconfig.set(qconfig.themeMode, theme, save)
    updateStyleSheet(lazy)
    qconfig.themeChangedFinished.emit()


def toggleTheme(save=False, lazy=False):
    """ toggle the theme of application """
    theme = Theme.LIGHT if isDarkTheme() else Theme.DARK
    setTheme(theme, save, lazy)


class ThemeColor(Enum):
    """ Theme color type """

    PRIMARY = "ThemeColorPrimary"
    DARK_1 = "ThemeColorDark1"
    DARK_2 = "ThemeColorDark2"
    DARK_3 = "ThemeColorDark3"
    LIGHT_1 = "ThemeColorLight1"
    LIGHT_2 = "ThemeColorLight2"
    LIGHT_3 = "ThemeColorLight3"

    def name(self):
        return self.color().name()

    def color(self):
        color = qconfig.get(qconfig._cfg.themeColor)  # type:QColor

        # transform color into hsv space
        h, s, v, _ = color.getHsvF()

        if isDarkTheme():
            s *= 0.84
            v = 1
            if self == self.DARK_1:
                v *= 0.9
            elif self == self.DARK_2:
                s *= 0.977
                v *= 0.82
            elif self == self.DARK_3:
                s *= 0.95
                v *= 0.7
            elif self == self.LIGHT_1:
                s *= 0.92
            elif self == self.LIGHT_2:
                s *= 0.78
            elif self == self.LIGHT_3:
                s *= 0.65
        else:
            if self == self.DARK_1:
                v *= 0.75
            elif self == self.DARK_2:
                s *= 1.05
                v *= 0.5
            elif self == self.DARK_3:
                s *= 1.1
                v *= 0.4
            elif self == self.LIGHT_1:
                v *= 1.05
            elif self == self.LIGHT_2:
                s *= 0.75
                v *= 1.05
            elif self == self.LIGHT_3:
                s *= 0.65
                v *= 1.05

        return QColor.fromHsvF(h, min(s, 1), min(v, 1))


def themeColor():
    """ get theme color """
    return ThemeColor.PRIMARY.color()


def setThemeColor(color, save=False, lazy=False):
    """ set theme color """
    color = QColor(color)
    qconfig.set(qconfig.themeColor, color, save=save)
    updateStyleSheet(lazy)


def updateDynamicStyle(widget: QWidget):
    """Re-evaluate dynamic QSS properties without detaching QStyle."""
    if widget is None or not isValid(widget):
        return
    if not widget.testAttribute(Qt.WidgetAttribute.WA_WState_Polished):
        return
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()
