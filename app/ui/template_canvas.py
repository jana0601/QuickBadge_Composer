from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView


class TemplateCanvas(QGraphicsView):
    clicked = Signal(float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._marker_items: list[QGraphicsEllipseItem] = []
        self.setRenderHints(self.renderHints())
        self.setMouseTracking(True)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._scene.clear()
        self._marker_items.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(self._pixmap_item.boundingRect())
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._pixmap_item is not None:
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        pos = self.mapToScene(event.pos())
        if self._pixmap_item is not None and self._scene.sceneRect().contains(pos):
            self.clicked.emit(pos.x(), pos.y())
        super().mousePressEvent(event)

    def set_markers(self, points: list[tuple[float, float]]) -> None:
        for marker in self._marker_items:
            self._scene.removeItem(marker)
        self._marker_items.clear()
        pen = QPen(QColor("red"))
        for x, y in points:
            marker = self._scene.addEllipse(x - 4, y - 4, 8, 8, pen)
            self._marker_items.append(marker)

