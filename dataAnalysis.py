import sys
import os
from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QMouseEvent


# ---------------- Resource Path ----------------
def resource_path(relative_path):
    try:
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


# ---------------- Animated Bar Button ----------------
class AnimatedBarButton(QWidget):
    """
    A simple button with an animated blue bar under it on hover.
    """
    def __init__(self, img_path, callback, parent=None, scale_factor=0.25):
        super().__init__(parent)
        self.callback = callback
        self.pixmap = QPixmap(img_path)
        self.base_width = int(200 * scale_factor)
        self.base_height = int(200 * scale_factor)
        self.bar_height = max(1, int(6 * scale_factor * 2))

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.bar = QLabel(self)
        self.bar.setStyleSheet("background-color: #1AA0FF;")
        self.bar.setVisible(False)
        self.bar.setGeometry((self.base_width - 0)//2, self.base_height, 0, self.bar_height)

        self.anim = None
        self.resize(self.base_width, self.base_height + self.bar_height)
        self.orig_x = 0
        self.orig_y = 0
        self.update_contents()

    def update_contents(self):
        w = self.width()
        h = self.height() - self.bar_height
        if w > 0 and h > 0:
            self.label.setPixmap(
                self.pixmap.scaled(
                    w, h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
        self.label.setGeometry(0, 0, w, h)

    def resizeEvent(self, event):
        self.update_contents()
        super().resizeEvent(event)

    def enterEvent(self, event):
        self.bar.setVisible(True)
        self.animate_bar(self.width())

    def leaveEvent(self, event):
        self.animate_bar(0)

    def animate_bar(self, target_width):
        if self.anim and self.anim.state() == QPropertyAnimation.State.Running:
            self.anim.stop()
        self.anim = QPropertyAnimation(self.bar, b"geometry")
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.anim.setStartValue(self.bar.geometry())
        self.anim.setEndValue(
            QRect((self.width() - target_width)//2, self.base_height, target_width, self.bar_height)
        )
        self.anim.start()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and callable(self.callback):
            self.callback()


# ---------------- Prodigally Screen ----------------
class DynamicScreen:
    """
    A simple screen with one animated home button (top-right).
    """
    def __init__(self, window, return_to_menu=None):
        self.window = window
        self.elements = []
        self.return_to_menu = return_to_menu
        self.setup_ui()

    def setup_ui(self):
        w, h = self.window.window_width, self.window.window_height
        btn_path = resource_path("images/homeIcon.png")

        y_offset = self.window.title_bar_height + 10

        # Single home button (top-right)
        home_btn = AnimatedBarButton(btn_path, self.on_home_clicked, self.window, scale_factor=0.25)
        home_btn.move(w - home_btn.width() - 20, y_offset)
        home_btn.orig_x = home_btn.x()
        home_btn.orig_y = home_btn.y()
        home_btn.show()
        self.elements.append(home_btn)

    def on_home_clicked(self):
        print("Home button clicked! Returning to main menu...")
        if callable(self.return_to_menu):
            self.return_to_menu()

    def cleanup(self):
        for elem in self.elements:
            elem.setParent(None)
            elem.deleteLater()
        self.elements.clear()
