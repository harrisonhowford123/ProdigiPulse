from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import QRect, QPropertyAnimation, QSequentialAnimationGroup, QEasingCurve, Qt
from PyQt6.QtGui import QPixmap, QRegion
import os, sys

# ---------------- Resource Path ----------------
def resource_path(relative_path):
    try:
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def playBlueRectangleAnimation(window, after_forward_finished=None):
    w, h = window.window_width, window.window_height
    title_bar_height = window.title_bar_height

    start_width = int(w * 0.10)  # changed from 0.33 to 0.10
    start_height = 5

    # Image QLabel, scaled to window, centered, always on top
    img_label = QLabel(window)
    pixmap = QPixmap(resource_path("images/pulseLoading.png"))
    pixmap = pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    img_label.setPixmap(pixmap)
    img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    img_label.setGeometry(0, 0, w, h)
    img_label.show()
    img_label.raise_()  # Ensure it’s above all UI elements

    # Initially fully masked (invisible)
    initial_mask = QRegion((w - start_width)//2, h - start_height, start_width, start_height)
    img_label.setMask(initial_mask)

    # Overlay rect for animation geometry calculations
    rect = QWidget(window)
    rect.setGeometry((w - start_width)//2, h - start_height, start_width, start_height)
    rect.show()
    rect.raise_()

    def update_mask():
        img_label.setMask(QRegion(rect.geometry()))
        img_label.raise_()  # Keep image on top during animation

    # Forward Animation
    horiz_expand = QPropertyAnimation(rect, b"geometry", window)
    horiz_expand.setDuration(500)
    horiz_expand.setStartValue(QRect((w - start_width)//2, h - start_height, start_width, start_height))
    horiz_expand.setEndValue(QRect(0, h - start_height, w, start_height))
    horiz_expand.setEasingCurve(QEasingCurve.Type.OutCubic)
    horiz_expand.valueChanged.connect(lambda _: update_mask())

    vert_expand = QPropertyAnimation(rect, b"geometry", window)
    vert_expand.setDuration(400)
    vert_expand.setStartValue(QRect(0, h - start_height, w, start_height))
    vert_expand.setEndValue(QRect(0, title_bar_height, w, h - title_bar_height))
    vert_expand.setEasingCurve(QEasingCurve.Type.OutCubic)
    vert_expand.valueChanged.connect(lambda _: update_mask())

    forward_seq = QSequentialAnimationGroup(window)
    forward_seq.addAnimation(horiz_expand)
    forward_seq.addAnimation(vert_expand)

    window._current_animation = forward_seq
    window._blue_rect = rect
    window._image_label = img_label

    # Reverse Animation
    def playReverseAnimation():
        vert_shrink = QPropertyAnimation(rect, b"geometry", window)
        vert_shrink.setDuration(500)
        vert_shrink.setStartValue(QRect(0, title_bar_height, w, h - title_bar_height))
        vert_shrink.setEndValue(QRect(0, title_bar_height, w, start_height))
        vert_shrink.setEasingCurve(QEasingCurve.Type.InCubic)
        vert_shrink.valueChanged.connect(lambda _: update_mask())

        horiz_shrink = QPropertyAnimation(rect, b"geometry", window)
        horiz_shrink.setDuration(400)
        horiz_shrink.setStartValue(QRect(0, title_bar_height, w, start_height))
        horiz_shrink.setEndValue(QRect((w - start_width)//2, title_bar_height, start_width, start_height))
        horiz_shrink.setEasingCurve(QEasingCurve.Type.InCubic)
        horiz_shrink.valueChanged.connect(lambda _: update_mask())

        reverse_seq = QSequentialAnimationGroup(window)
        reverse_seq.addAnimation(vert_shrink)
        reverse_seq.addAnimation(horiz_shrink)

        def onReverseFinished():
            rect.setParent(None)
            rect.deleteLater()
            img_label.setParent(None)
            img_label.deleteLater()
            window._blue_rect = None
            window._image_label = None
            window._current_animation = None

        reverse_seq.finished.connect(onReverseFinished)
        reverse_seq.start()
        window._current_animation = reverse_seq

    # Forward finished callback
    def onForwardFinishedInternal():
        if callable(after_forward_finished):
            after_forward_finished()
        rect.raise_()
        img_label.raise_()  # Ensure image remains on top
        playReverseAnimation()

    forward_seq.finished.connect(onForwardFinishedInternal)
    forward_seq.start()


def playBlueRectangleAnimationTopDown(window, after_forward_finished=None):
    w, h = window.window_width, window.window_height
    title_bar_height = window.title_bar_height

    start_width = int(w * 0.10)  # changed from 0.33 to 0.10
    start_height = 5

    # Image QLabel, scaled to window, centered, always on top
    img_label = QLabel(window)
    pixmap = QPixmap(resource_path("images/pulseLoading.png"))
    pixmap = pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    img_label.setPixmap(pixmap)
    img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    img_label.setGeometry(0, 0, w, h)
    img_label.show()
    img_label.raise_()

    # Initially fully masked (invisible)
    initial_mask = QRegion((w - start_width)//2, title_bar_height, start_width, start_height)
    img_label.setMask(initial_mask)

    # Overlay rect for animation geometry calculations
    rect = QWidget(window)
    rect.setGeometry((w - start_width)//2, title_bar_height, start_width, start_height)
    rect.show()
    rect.raise_()

    def update_mask():
        img_label.setMask(QRegion(rect.geometry()))
        img_label.raise_()  # Keep image on top during animation

    # Forward Animation
    horiz_expand = QPropertyAnimation(rect, b"geometry", window)
    horiz_expand.setDuration(500)
    horiz_expand.setStartValue(QRect((w - start_width)//2, title_bar_height, start_width, start_height))
    horiz_expand.setEndValue(QRect(0, title_bar_height, w, start_height))
    horiz_expand.setEasingCurve(QEasingCurve.Type.OutCubic)
    horiz_expand.valueChanged.connect(lambda _: update_mask())

    vert_expand = QPropertyAnimation(rect, b"geometry", window)
    vert_expand.setDuration(400)
    vert_expand.setStartValue(QRect(0, title_bar_height, w, start_height))
    vert_expand.setEndValue(QRect(0, title_bar_height, w, h - title_bar_height))
    vert_expand.setEasingCurve(QEasingCurve.Type.OutCubic)
    vert_expand.valueChanged.connect(lambda _: update_mask())

    forward_seq = QSequentialAnimationGroup(window)
    forward_seq.addAnimation(horiz_expand)
    forward_seq.addAnimation(vert_expand)

    window._current_animation = forward_seq
    window._blue_rect = rect
    window._image_label = img_label

    # Reverse Animation
    def playReverseAnimation():
        vert_shrink = QPropertyAnimation(rect, b"geometry", window)
        vert_shrink.setDuration(500)
        vert_shrink.setStartValue(QRect(0, title_bar_height, w, h - title_bar_height))
        vert_shrink.setEndValue(QRect(0, h - start_height, w, start_height))
        vert_shrink.setEasingCurve(QEasingCurve.Type.InCubic)
        vert_shrink.valueChanged.connect(lambda _: update_mask())

        horiz_shrink = QPropertyAnimation(rect, b"geometry", window)
        horiz_shrink.setDuration(400)
        horiz_shrink.setStartValue(QRect(0, h - start_height, w, start_height))
        horiz_shrink.setEndValue(QRect((w - start_width)//2, h - start_height, start_width, start_height))
        horiz_shrink.setEasingCurve(QEasingCurve.Type.InCubic)
        horiz_shrink.valueChanged.connect(lambda _: update_mask())

        reverse_seq = QSequentialAnimationGroup(window)
        reverse_seq.addAnimation(vert_shrink)
        reverse_seq.addAnimation(horiz_shrink)

        def onReverseFinished():
            rect.setParent(None)
            rect.deleteLater()
            img_label.setParent(None)
            img_label.deleteLater()
            window._blue_rect = None
            window._image_label = None
            window._current_animation = None

        reverse_seq.finished.connect(onReverseFinished)
        reverse_seq.start()
        window._current_animation = reverse_seq

    # Forward finished callback
    def onForwardFinishedInternal():
        if callable(after_forward_finished):
            after_forward_finished()
        rect.raise_()
        img_label.raise_()  # Ensure image remains on top
        playReverseAnimation()

    forward_seq.finished.connect(onForwardFinishedInternal)
    forward_seq.start()
