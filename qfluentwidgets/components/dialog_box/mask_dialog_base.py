# coding:utf-8
from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QPropertyAnimation, Qt, QEvent,
                            QPoint, QPointF, QRectF, QSize, QSizeF)
from PySide6.QtGui import QColor, QPainter, QPixmap, QResizeEvent
from PySide6.QtWidgets import (QDialog, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
                               QGraphicsPixmapItem, QGraphicsScene, QHBoxLayout, QStyle,
                               QStyleOption, QWidget, QFrame)

from ...common.config import isDarkTheme


def buildShadowPixmap(panel: QWidget, ratio: float, blurRadius: float, offset, color: QColor):
    size = panel.size()
    source = QPixmap(size * ratio)
    source.setDevicePixelRatio(ratio)
    source.fill(Qt.transparent)
    opt = QStyleOption()
    opt.initFrom(panel)
    painter = QPainter(source)
    panel.style().drawPrimitive(QStyle.PE_Widget, opt, painter, panel)
    painter.end()

    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(blurRadius)
    effect.setOffset(*offset)
    effect.setColor(color)
    bounds = effect.boundingRectFor(QRectF(QPointF(0, 0), QSizeF(size))).toAlignedRect()

    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(source)
    item.setGraphicsEffect(effect)
    scene.addItem(item)

    pixmap = QPixmap(bounds.size() * ratio)
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)
    out = QPainter(pixmap)
    scene.render(out, QRectF(QPointF(0, 0), QSizeF(bounds.size())), QRectF(bounds))
    out.setCompositionMode(QPainter.CompositionMode_DestinationOut)
    out.drawPixmap(-bounds.left(), -bounds.top(), source)
    out.end()
    return bounds, pixmap


class ShadowLayer(QWidget):
    """Cached sibling shadow so QGraphicsEffect does not block child scroll blitting."""

    def __init__(self, panel: QWidget, parent: QWidget):
        super().__init__(parent)
        self._panel = panel
        self._blurRadius = 0.0
        self._offset = (0.0, 0.0)
        self._color = QColor()
        self._origin = QPoint()
        self._panelSize = QSize()
        self._pixmap = QPixmap()
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set(self, blurRadius, offset, color):
        self._blurRadius = float(blurRadius)
        self._offset = (float(offset[0]), float(offset[1]))
        self._color = QColor(color)
        self.refresh(force=True)

    def refresh(self, force: bool = False):
        panel = self._panel
        if panel.parentWidget() is not self.parentWidget() or not panel.isVisible() or panel.size().isEmpty():
            self.hide()
            return

        ratio = self.devicePixelRatioF()
        if force or self._pixmap.isNull() or self._panelSize != panel.size() or self._pixmap.devicePixelRatio() != ratio:
            bounds, self._pixmap = buildShadowPixmap(panel, ratio, self._blurRadius, self._offset, self._color)
            self._origin = bounds.topLeft()
            self._panelSize = panel.size()
            self.resize(bounds.size())

        self.move(panel.pos() + self._origin)
        if not self.isVisible():
            self.stackUnder(panel)
            self.show()

    def paintEvent(self, e):
        if not self._pixmap.isNull():
            QPainter(self).drawPixmap(0, 0, self._pixmap)


class MaskDialogBase(QDialog):
    """ Dialog box base class with a mask """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._isClosableOnMaskClicked = False
        self._isDraggable = False
        self._dragPos = QPoint()
        self._hBoxLayout = QHBoxLayout(self)
        self.windowMask = QWidget(self)

        # dialog box in the center of mask, all widgets take it as parent
        self.widget = QFrame(self, objectName='centerWidget')
        self._shadowLayer = ShadowLayer(self.widget, self)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(0, 0, parent.width(), parent.height())

        c = 0 if isDarkTheme() else 255
        self.windowMask.resize(self.size())
        self.windowMask.setStyleSheet(f'background:rgba({c}, {c}, {c}, 0.6)')
        self._hBoxLayout.addWidget(self.widget)
        self.setShadowEffect()

        self._pendingDoneCode = None
        self.windowMask.installEventFilter(self)
        self.widget.installEventFilter(self)

    def _installHostWindowFilter(self):
        win = self.window()
        if win is not None and win is not self:
            win.installEventFilter(self)

    def _removeHostWindowFilter(self):
        win = self.window()
        if win is not None and win is not self:
            win.removeEventFilter(self)

    def setShadowEffect(self, blurRadius=60, offset=(0, 10), color=QColor(0, 0, 0, 100)):
        """ add shadow to dialog """
        self._shadowLayer.set(blurRadius, offset, color)

    def setMaskColor(self, color: QColor):
        """ set the color of mask """
        self.windowMask.setStyleSheet(f"""
            background: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})
        """)

    def showEvent(self, e):
        """ fade in """
        self._installHostWindowFilter()
        opacityEffect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(opacityEffect)
        opacityAni = QPropertyAnimation(opacityEffect, b'opacity', self)
        opacityAni.setStartValue(0)
        opacityAni.setEndValue(1)
        opacityAni.setDuration(200)
        opacityAni.setEasingCurve(QEasingCurve.InSine)
        opacityAni.finished.connect(self._onShowAniFinished)
        opacityAni.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        super().showEvent(e)

    def _onShowAniFinished(self):
        self.setGraphicsEffect(None)

    def hideEvent(self, e):
        self._removeHostWindowFilter()
        super().hideEvent(e)

    def done(self, code):
        """ fade out """
        self._pendingDoneCode = code
        opacityEffect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(opacityEffect)
        opacityAni = QPropertyAnimation(opacityEffect, b'opacity', self)
        opacityAni.setStartValue(1)
        opacityAni.setEndValue(0)
        opacityAni.setDuration(100)
        opacityAni.finished.connect(self._onDoneAniFinished)
        opacityAni.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def _onDoneAniFinished(self):
        code = self._pendingDoneCode
        self._pendingDoneCode = None
        if code is not None:
            self._onDone(code)

    def _onDone(self, code):
        self._removeHostWindowFilter()
        self.setGraphicsEffect(None)
        QDialog.done(self, code)

    def isClosableOnMaskClicked(self):
        return self._isClosableOnMaskClicked

    def setClosableOnMaskClicked(self, isClosable: bool):
        self._isClosableOnMaskClicked = isClosable

    def setDraggable(self, draggable: bool):
        self._isDraggable = draggable

    def isDraggable(self) -> bool:
        return self._isDraggable

    def resizeEvent(self, e):
        self.windowMask.resize(self.size())

    def eventFilter(self, obj, e: QEvent):
        if obj is self.window():
            if e.type() == QEvent.Resize:
                re = QResizeEvent(e)
                self.resize(re.size())
        elif obj is self.windowMask:
            if e.type() == QEvent.MouseButtonRelease and e.button() == Qt.LeftButton \
                    and self.isClosableOnMaskClicked():
                self.reject()
        elif obj is self.widget:
            eventType = e.type()
            if eventType == QEvent.StyleChange:
                self._shadowLayer.refresh(force=True)
            elif eventType in (QEvent.Move, QEvent.Resize, QEvent.Show, QEvent.Hide, QEvent.ParentChange):
                self._shadowLayer.refresh()

            if self.isDraggable():
                if eventType == QEvent.MouseButtonPress and e.button() == Qt.LeftButton:
                    if not self.widget.childrenRegion().contains(e.pos()):
                        self._dragPos = e.pos()
                        return True
                elif eventType == QEvent.MouseMove and not self._dragPos.isNull():
                    pos = self.widget.pos() + e.pos() - self._dragPos
                    pos.setX(max(0, min(pos.x(), self.width() - self.widget.width())))
                    pos.setY(max(0, min(pos.y(), self.height() - self.widget.height())))

                    self.widget.move(pos)
                    return True
                elif eventType == QEvent.MouseButtonRelease:
                    self._dragPos = QPoint()

        return super().eventFilter(obj, e)
