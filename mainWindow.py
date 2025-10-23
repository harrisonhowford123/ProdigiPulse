from PyQt6.QtWidgets import QWidget, QLabel, QPushButton
from PyQt6.QtCore import Qt

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        # Frameless
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        # 16:9 window at 90% of screen
        screen = self.screen().geometry()
        w, h = screen.width(), screen.height()
        if w / h > 16 / 9:
            height = int(h * 0.9)
            width = int(height * 16 / 9)
        else:
            width = int(w * 0.9)
            height = int(width / (16 / 9))
        self.setGeometry((w - width)//2, (h - height)//2, width, height)
        self.window_width = width
        self.window_height = height

        # Background
        self.bg = QLabel(self)
        self.bg.setGeometry(0, 0, width, height)
        self.bg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Title bar
        self.title_bar_height = 30
        self.title_bar = QWidget(self)
        self.title_bar.setGeometry(0, 0, width, self.title_bar_height)
        self.title_bar.setStyleSheet("background-color: #414141;")

        # Close button
        self.close_btn = QPushButton("✕", self.title_bar)
        self.close_btn.setGeometry(width - 40, 0, 40, self.title_bar_height)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: white; font-size: 16px;
            }
            QPushButton:hover { background-color: #1AA0FF; }
        """)
        self.close_btn.clicked.connect(self.close)

        # Minimize button
        self.minimize_btn = QPushButton("—", self.title_bar)
        self.minimize_btn.setGeometry(width - 80, 0, 40, self.title_bar_height)
        self.minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: white; font-size: 16px;
            }
            QPushButton:hover { background-color: #1AA0FF; }
        """)
        self.minimize_btn.clicked.connect(self.showMinimized)

        # Dragging
        self.old_pos = None

        # Menu
        self.menu = None

    # ---------- Dragging ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= self.title_bar_height:
            self.old_pos = event.globalPosition()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition() - self.old_pos
            self.move(self.x() + int(delta.x()), self.y() + int(delta.y()))
            self.old_pos = event.globalPosition()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    # ---------- Menu ----------
    def set_menu(self, menu):
        self.menu = menu
        menu.setParent(self)
        menu.setGeometry(
            0, self.title_bar_height,
            self.window_width, self.window_height - self.title_bar_height
        )
        menu.show()

    # ---------- Background ----------
    def set_background(self, pixmap):
        scaled = pixmap.scaled(
            self.window_width, self.window_height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.bg.setPixmap(scaled)
