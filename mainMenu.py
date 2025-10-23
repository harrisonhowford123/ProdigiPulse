import sys
import os
from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtGui import QPixmap, QMouseEvent, QPainter, QColor
from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, QEasingCurve, QTimer

def resource_path(relative_path):
    try:
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


# ---------------- Image Button ----------------
class ImageButton(QWidget):
    def __init__(self, img_path, index, callback, parent=None, scale_factor=1.0):
        super().__init__(parent)
        self.index = index
        self.callback = callback
        self.pixmap = QPixmap(img_path)

        # 🔹 Wait until parent is shown to get valid size
        if parent and parent.width() > 0 and parent.height() > 0:
            pw, ph = parent.width(), parent.height()
        else:
            # fallback for init-time calls
            pw, ph = 1920, 1080

        # 🔹 Base size relative to parent
        self.base_width = int(pw * 0.12 * scale_factor*15)
        self.base_height = self.base_width
        self.bar_height = max(2, int(self.base_height * 0.03))

        # make sure nothing is 0
        self.base_width = max(self.base_width, 100)
        self.base_height = max(self.base_height, 100)

        # ---------- Visuals ----------
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.bar = QLabel(self)
        self.bar.setStyleSheet("background-color: #1AA0FF;")
        self.bar.setVisible(False)
        bar_width = self.base_width // 2
        self.bar.setGeometry(
            (self.base_width - bar_width)//2, self.base_height, bar_width, self.bar_height
        )

        # ---------- Animation ----------
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._target_scale = 1.0
        self.anim.finished.connect(self._on_anim_finished)

        # ---------- Initial placement ----------
        self.resize(self.base_width, self.base_height + self.bar_height)
        self.orig_x = 0
        self.orig_y = 0

        self.update_contents()


    # ---------- Maintain bar visibility ----------
    def _on_anim_finished(self):
        if self._target_scale == 1.0:
            self.bar.setVisible(False)

    # ---------- Update image when resized ----------
    def resizeEvent(self, event):
        self.update_contents()
        super().resizeEvent(event)

    # ---------- Apply scaled pixmap + bar ----------
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
        if self.bar.isVisible():
            scale = w / self.base_width
            progress = min(max((scale - 1.0) / 0.2, 0.0), 1.0)
            bar_width = int(w * (0.5 + 0.5 * progress))
            self.bar.setGeometry((w - bar_width)//2, h, bar_width, self.bar_height)

    # ---------- Hover events ----------
    def enterEvent(self, event):
        self.bar.setVisible(True)
        self.animate_scale(1.2)

    def leaveEvent(self, event):
        self.animate_scale(1.0)

    # ---------- Scale animation ----------
    def animate_scale(self, scale_factor):
        self._target_scale = scale_factor
        new_w = int(self.base_width * scale_factor)
        new_h = int(self.base_height * scale_factor) + self.bar_height

        new_geom = QRect(
            self.orig_x + (self.base_width - new_w)//2,
            self.orig_y + (self.base_height - new_h)//2,
            new_w,
            new_h
        )
        self.anim.stop()
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(new_geom)
        self.anim.start()

    # ---------- Click handling ----------
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.callback(self.index)


class LogoutButton(QWidget):
    def __init__(self, parent=None, callback=None, text="Logout"):
        super().__init__(parent)
        self.bg_color = "#3B3B3B"
        self.hover_color = "#1AA0FF"
        self.text = text
        self.callback = callback

        # Automatically calculate size relative to parent window
        if parent:
            parent_w, parent_h = parent.width(), parent.height()
            button_width = int(parent_w * 0.06)   # 6% of window width
            button_height = int(parent_h * 0.03)  # 3% of window height
            self.setFixedSize(button_width, button_height)
        else:
            self.setFixedSize(120, 40)  # fallback if no parent provided

        # Position top-right corner with 2% margin
        if parent:
            x_pos = int(parent.width()*0.93)
            y_pos = int(parent.height() * 0.06)
            self.move(x_pos, y_pos)

    def enterEvent(self, event):
        self.bg_color = self.hover_color
        self.update()

    def leaveEvent(self, event):
        self.bg_color = "#3B3B3B"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(self.bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())
        painter.setPen(Qt.GlobalColor.white)
        font = painter.font()
        font.setPointSize(max(10, int(self.height() * 0.3)))  # font scales with height
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)

    def mousePressEvent(self, event):
        if callable(self.callback):
            self.callback()

# ---------------- Menu Widget ----------------
class Menu(QWidget):
    def __init__(self, parent, button_images, logout_callback=None, logged_in_employee=None):
        super().__init__(parent)
        self.buttons = []
        self.clicked = None
        self.logout_callback = logout_callback
        self.animations = []

        self.logged_in_employee = logged_in_employee  # <-- store logged in employee
        self.permissions_map = ["dataAnalysis", "staffManager", "trackingTool", "manualTasks"]

        self.grid_cols = 3
        self.row_spacing = 200  # vertical spacing between rows

        # ---------- Setup buttons ----------
        self.setup_buttons(button_images)

        # ---------- Setup logout button ----------
        self.setup_logout_button()


    # ---------- Setup main menu image buttons ----------
    def setup_buttons(self, button_images):
        num_buttons = len(button_images)
        w, h = self.parent().width(), self.parent().height()

        # Relative layout setup
        first_row_y = int(h * 0.45)
        buttons_per_row = 3
        spacing_x = int(w * 0.05)   # 5% of window width
        spacing_y = int(h * 0.15)   # 15% of window height

        for i, img_file in enumerate(button_images, start=1):
            row = (i - 1) // buttons_per_row
            col = (i - 1) % buttons_per_row

            btn = ImageButton(resource_path(os.path.join("images", img_file)), i, self.on_click, self)

            if row == 0:
                # First row: centered logic
                spacing = w // (min(buttons_per_row, num_buttons) + 1)
                x = spacing * (col + 1) - btn.width() // 2
                y = int((first_row_y - btn.height() // 2) * 0.9)
            else:
                # Second+ rows: align left under first row
                first_row_left_x = w // (buttons_per_row + 1) - btn.width() // 2
                x = first_row_left_x + col * (btn.width() + spacing_x)
                y = first_row_y + row * spacing_y

            btn.move(x, y)
            btn.orig_x = x
            btn.orig_y = y
            self.buttons.append(btn)

        # --- Apply pulseAccess permissions ---
        if self.logged_in_employee:
            access = self.logged_in_employee.pulseAccess
            for btn, perm in zip(self.buttons, self.permissions_map):
                if "ALL" in access or perm in access:
                    btn.setEnabled(True)
                    btn.setStyleSheet("opacity: 1.0;")  # fully visible
                else:
                    btn.setEnabled(False)
                    btn.setStyleSheet("opacity: 0.4;")  # semi-transparent greyed-out


    # ---------- Setup logout button ----------
    def setup_logout_button(self):
        if not self.logout_callback:
            return

        if hasattr(self, "logout_button") and self.logout_button:
            self.logout_button.setParent(None)
            self.logout_button.deleteLater()
            self.logout_button = None

        self.logout_button = LogoutButton(parent=self.parent(), callback=self.logout_callback, text="Logout")
        self.logout_button.show()
        self.logout_button.raise_()

    # ---------- Handle clicks ----------
    def on_click(self, index):
        if self.clicked is not None:
            return
        self.clicked = index
        for btn in self.buttons:
            btn.setEnabled(False)
        QTimer.singleShot(0, self.animate_buttons_fall)

    def animate_buttons_fall(self):
        self.shadow_buttons = []
        self.animations.clear()

        fall_speed = 1  # pixels per ms (controls fall rate)

        # Create shadow copies of each button
        for btn in self.buttons:
            pix = btn.label.pixmap()
            if pix is None:
                continue
            btn.setVisible(False)
            btn.setEnabled(False)

            shadow = QLabel(self)
            shadow.setPixmap(pix)
            shadow.setGeometry(btn.geometry())
            shadow.show()
            self.shadow_buttons.append(shadow)

        # Animate all buttons together
        for shadow in self.shadow_buttons:
            geom = shadow.geometry()
            distance = (self.height() + geom.height()) - geom.y()

            # constant speed — longer distance = longer duration
            duration = int(distance / fall_speed)

            anim = QPropertyAnimation(shadow, b"geometry")
            anim.setStartValue(geom)
            anim.setEndValue(QRect(geom.x(), self.height() + geom.height(), geom.width(), geom.height()))
            anim.setDuration(duration)
            anim.setEasingCurve(QEasingCurve.Type.InQuad)

            anim.start()
            self.animations.append(anim)










