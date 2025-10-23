import sys
import os

from PyQt6.QtWidgets import (
    QApplication, QLabel, QWidget, QComboBox, QPushButton,
    QLineEdit, QListWidget
)
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QTimer, QObject, QEvent, QPoint, QPropertyAnimation

from mainWindow import MainWindow
from mainMenu import Menu, resource_path
from dataAnalysis import DynamicScreen
from facilityManager import FacilityScreen
from manualTasks import manualTaskScreen
from animations import playBlueRectangleAnimation, playBlueRectangleAnimationTopDown
from prodigallyScreen import ProdigallyScreen
from clientCalls import fetch_pulse_employees

import warnings
warnings.filterwarnings("ignore", message="sipPyTypeDict.*", category=DeprecationWarning)


logged_in_employee = None

def createHomeScreen():
    app = QApplication(sys.argv)
    window = MainWindow()

    # ---------------- Background Paths ----------------
    bg_home = resource_path(os.path.join("images", "homeScreen.png"))
    bg_analysis = resource_path(os.path.join("images", "dataAnalysis.png"))
    bg_facility = resource_path(os.path.join("images", "dataAnalysis.png"))  # reuse or change

    window.set_background(QPixmap(bg_home))
    window.bg.lower()

    # ---------------- Shared State ----------------
    menu_state = 0  # used to prevent duplicate click handling

    # ---------------- Helpers: Cleanup ----------------
    def cleanup_menu():
        if window.menu:
            for btn in window.menu.buttons:
                btn.setParent(None)
                btn.deleteLater()
            if hasattr(window.menu, "shadow_buttons"):
                for shadow in window.menu.shadow_buttons:
                    shadow.setParent(None)
                    shadow.deleteLater()
            if hasattr(window.menu, "logout_button") and window.menu.logout_button:
                print("YES")
                window.menu.logout_button.setParent(None)
                window.menu.logout_button.deleteLater()
                window.menu.logout_button = None
            window.menu.setParent(None)
            window.menu.deleteLater()
            window.menu = None


    def cleanup_dynamic_screen():
        if hasattr(window, "dynamic_screen") and window.dynamic_screen:
            window.dynamic_screen.cleanup()
            window.dynamic_screen = None

    def cleanup_facility_screen():
        if hasattr(window, "facility_screen") and window.facility_screen:
            window.facility_screen.cleanup()
            window.facility_screen = None

    def cleanup_prodigally_screen():
        if hasattr(window, "prodigally_screen") and window.prodigally_screen:
            window.prodigally_screen.cleanup()
            window.prodigally_screen = None

    def cleanup_manual_task_screen():
        if hasattr(window, "manual_task_screen") and window.manual_task_screen:
            window.manual_task_screen.cleanup()
            window.manual_task_screen = None

    # ---------------- Screen Builders ----------------
    def show_dynamic_screen():
        cleanup_menu()
        window.set_background(QPixmap(bg_analysis))
        window.bg.lower()

        dynamic_screen = DynamicScreen(window, return_to_menu=return_to_main_menu)
        window.dynamic_screen = dynamic_screen

        for elem in dynamic_screen.elements:
            elem.raise_()
        if hasattr(window, "_blue_rect") and window._blue_rect:
            window._blue_rect.raise_()

    def show_facility_screen():
        cleanup_menu()
        window.set_background(QPixmap(bg_facility))
        window.bg.lower()

        print(logged_in_employee)
        facility_screen = FacilityScreen(window, logged_in_employee, return_to_main_menu)

        window.facility_screen = facility_screen

        for elem in facility_screen.elements:
            elem.raise_()
        if hasattr(window, "_blue_rect") and window._blue_rect:
            window._blue_rect.raise_()

    def show_prodigally_screen():
        cleanup_menu()
        window.set_background(QPixmap(bg_facility))
        window.bg.lower()

        prodigally_screen = ProdigallyScreen(window, return_to_menu=return_to_main_menu)
        window.prodigally_screen = prodigally_screen

        for elem in prodigally_screen.elements:
            elem.raise_()
        if hasattr(window, "_blue_rect") and window._blue_rect:
            window._blue_rect.raise_()

    def show_manual_task_screen():
        cleanup_menu()
        # You can reuse the home background or a different one
        window.set_background(QPixmap(resource_path(os.path.join("images", "dataAnalysis.png"))))
        window.bg.lower()

        treat = manualTaskScreen(window, return_to_menu=return_to_main_menu)
        window.manual_task_screen = treat

        # Raise all elements to be visible
        for elem in treat.elements:
            elem.raise_()
        if hasattr(window, "_blue_rect") and window._blue_rect:
            window._blue_rect.raise_()

    # ---------------- Return to Main Menu ----------------
    def return_to_main_menu():
        nonlocal menu_state

        def after_animation():
            cleanup_dynamic_screen()
            cleanup_facility_screen()
            cleanup_prodigally_screen()
            cleanup_manual_task_screen()  # <- added

            window.set_background(QPixmap(bg_home))
            window.bg.lower()
            
            main_menu_images = ["analysisMode.png", "facilityManager.png", "prodigally.png", "manualTask.png"]
            menu = Menu(window, main_menu_images, logout_callback=logout, logged_in_employee=logged_in_employee)
            window.set_menu(menu)

            menu_state = 0
            menu.clicked = None

            # Start polling for menu button clicks
            def check_click():
                nonlocal menu_state
                if menu.clicked is not None and menu_state == 0:
                    menu_state = menu.clicked
                    if menu_state == 1:
                        QTimer.singleShot(100, lambda: playBlueRectangleAnimation(window, show_dynamic_screen))
                    elif menu_state == 2:
                        QTimer.singleShot(100, lambda: playBlueRectangleAnimation(window, show_facility_screen))
                    elif menu_state == 3:
                        QTimer.singleShot(100, lambda: playBlueRectangleAnimation(window, show_prodigally_screen))
                    elif menu_state == 4:
                        QTimer.singleShot(100, lambda: playBlueRectangleAnimation(window, show_manual_task_screen))
                else:
                    QTimer.singleShot(50, check_click)

            QTimer.singleShot(50, check_click)

        playBlueRectangleAnimationTopDown(window, after_animation)

    # ---------------- Show Initial Menu ----------------
    def show_initial_menu():
        nonlocal menu_state

        cleanup_dynamic_screen()
        cleanup_facility_screen()
        cleanup_prodigally_screen()

        window.set_background(QPixmap(bg_home))
        window.bg.lower()

        main_menu_images = ["analysisMode.png", "facilityManager.png", "prodigally.png", "manualTask.png"]
        menu = Menu(window, main_menu_images, logout_callback=logout, logged_in_employee=logged_in_employee)
        window.set_menu(menu)


        menu_state = 0
        menu.clicked = None

        # Poll for click input
        def check_click():
            nonlocal menu_state
            if menu.clicked is not None and menu_state == 0:
                menu_state = menu.clicked
                if menu_state == 1:
                    QTimer.singleShot(100, lambda: playBlueRectangleAnimation(window, show_dynamic_screen))
                elif menu_state == 2:
                    QTimer.singleShot(100, lambda: playBlueRectangleAnimation(window, show_facility_screen))
                elif menu_state == 3:
                    QTimer.singleShot(100, lambda: playBlueRectangleAnimation(window, show_prodigally_screen))
                elif menu_state == 4:
                    QTimer.singleShot(100, lambda: playBlueRectangleAnimation(window, show_manual_task_screen))
            else:
                QTimer.singleShot(50, check_click)


        QTimer.singleShot(50, check_click)

    def logout():
        global logged_in_employee
        logged_in_employee = None  # reset

        def after_animation():
            # Remove the current menu if exists
            if hasattr(window, "menu") and window.menu:
                # Remove buttons
                for btn in getattr(window.menu, "buttons", []):
                    btn.setParent(None)
                    btn.deleteLater()
                # Remove shadow buttons
                for shadow in getattr(window.menu, "shadow_buttons", []):
                    shadow.setParent(None)
                    shadow.deleteLater()
                # Remove logout button explicitly
                if getattr(window.menu, "logout_button", None):
                    window.menu.logout_button.setParent(None)
                    window.menu.logout_button.deleteLater()
                    window.menu.logout_button = None
                # Delete the menu itself
                window.menu.setParent(None)
                window.menu.deleteLater()
                window.menu = None

            # Now draw sign-in overlay
            show_sign_in_overlay(window, show_initial_menu)

        playBlueRectangleAnimation(window, after_animation)

    # ---------------- Sign-In Overlay with Transition ----------------
    def show_sign_in_overlay(window, show_initial_menu):
        sign_in_path = resource_path(os.path.join("images", "signIn.png"))
        sign_in_label = QLabel(window)
        sign_in_label.setPixmap(QPixmap(sign_in_path))
        sign_in_label.setGeometry(0, 0, window.width(), window.height())
        sign_in_label.setScaledContents(True)
        sign_in_label.show()

        # Allow title bar interaction
        sign_in_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        window.title_bar.raise_()
        window.close_btn.raise_()
        window.minimize_btn.raise_()

        # ---------- Username LineEdit ----------
        line_edit = QLineEdit(window)
        line_edit.setPlaceholderText("Username")
        line_edit.setFixedSize(int(window.width()*0.128), int(window.width()*0.0225))
        line_edit_font_size = 16
        line_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #3B3B3B;
                color: white;
                border: 2px solid #3B3B3B;
                border-radius: 0px;
                font-size: {line_edit_font_size}px;
                padding-left: 8px;
            }}
            QLineEdit:focus {{
                border: 2px solid #1AA0FF;
            }}
        """)
        line_edit.move(int((window.width()) *0.425), int(window.height() * 0.513))
        line_edit.show()

        # ---------- Password LineEdit ----------
        password_edit = QLineEdit(window)
        password_edit.setPlaceholderText("Password")
        password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        password_edit.setFixedSize(line_edit.size())
        password_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #3B3B3B;
                color: white;
                border: 2px solid #3B3B3B;
                border-radius: 0px;
                font-size: {line_edit_font_size}px;
                padding-left: 8px;
            }}
            QLineEdit:focus {{
                border: 2px solid #1AA0FF;
            }}
        """)
        password_edit.move(int((window.width()) *0.425), int(window.height() * 0.625))
        password_edit.show()

        # ---------- Dropdown Arrow Button ----------
        arrow_btn = QPushButton("▼", window)
        arrow_btn.setFixedSize(30, line_edit.height())
        arrow_btn.setStyleSheet("""
            QPushButton {
                background-color: #1AA0FF;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #0090DD;
            }
        """)
        arrow_btn.move(line_edit.x() + line_edit.width() - arrow_btn.width(), line_edit.y())
        arrow_btn.show()

        # ---------- Popup List ----------
        popup_list = QListWidget(window)
        popup_list.setWindowFlags(Qt.WindowType.ToolTip)
        popup_list.setStyleSheet(f"""
            QListWidget {{
                background-color: #2B2B2B;
                color: white;
                border: 1px solid #1AA0FF;
                border-radius: 0px;
                font-size: {line_edit_font_size}px;
            }}
            QListWidget::item:selected {{
                background-color: #1AA0FF;
                color: white;
            }}
            QScrollBar:vertical {{ width: 0px; }}
        """)
        popup_list.hide()

        all_employees = []

        def populate_employees():
            nonlocal all_employees
            employees = fetch_pulse_employees()
            all_employees = employees
            line_edit.all_employee_names = [emp.employeeName for emp in employees]

        QTimer.singleShot(100, populate_employees)

        # ---------- Update Popup ----------
        def update_popup():
            text = line_edit.text().lower()
            popup_list.clear()
            matches = [name for name in getattr(line_edit, "all_employee_names", []) if text in name.lower()]
            if not matches:
                popup_list.hide()
                return
            popup_list.addItems(matches)
            row_height = popup_list.sizeHintForRow(0)
            popup_list.setFixedHeight(min(8, len(matches)) * row_height + 2)
            popup_list.setFixedWidth(line_edit.width())
            popup_list.move(line_edit.mapToGlobal(QPoint(0, line_edit.height())))
            popup_list.show()

        line_edit.textChanged.connect(update_popup)

        # ---------- Selection ----------
        def select_employee(item=None):
            if item:
                line_edit.setText(item.text())
            elif popup_list.currentItem():
                line_edit.setText(popup_list.currentItem().text())
            popup_list.hide()
            line_edit.clearFocus()

        popup_list.itemClicked.connect(select_employee)

        # ---------- Username key handling ----------
        def handle_username_keys(event):
            key = event.key()
            if key == Qt.Key.Key_Down:
                if popup_list.isVisible() and popup_list.count() > 0:
                    if not popup_list.hasFocus():
                        popup_list.setFocus()
                        if popup_list.currentRow() < 0:
                            popup_list.setCurrentRow(0)
            elif key == Qt.Key.Key_Return:
                if popup_list.isVisible() and popup_list.count() > 0:
                    item = popup_list.currentItem() or popup_list.item(0)
                    line_edit.setText(item.text())
                popup_list.hide()
                password_edit.setFocus()
            else:
                QLineEdit.keyPressEvent(line_edit, event)

        line_edit.keyPressEvent = handle_username_keys

        # ---------- Popup list key handling ----------
        def handle_popup_keys(event):
            key = event.key()
            if key == Qt.Key.Key_Return:
                if popup_list.currentItem():
                    line_edit.setText(popup_list.currentItem().text())
                popup_list.hide()
                password_edit.setFocus()
            elif key == Qt.Key.Key_Escape:
                popup_list.hide()
                line_edit.setFocus()
            else:
                QListWidget.keyPressEvent(popup_list, event)

        popup_list.keyPressEvent = handle_popup_keys

        # ---------- Password key handling ----------
        def handle_password_keys(event):
            key = event.key()
            if key == Qt.Key.Key_Return:
                trigger_login()
            else:
                QLineEdit.keyPressEvent(password_edit, event)

        password_edit.keyPressEvent = handle_password_keys

        # ---------- Toggle popup manually ----------
        def toggle_popup():
            if popup_list.isVisible():
                popup_list.hide()
                line_edit.clearFocus()
            else:
                popup_list.clear()
                popup_list.addItems(getattr(line_edit, "all_employee_names", []))
                row_height = popup_list.sizeHintForRow(0)
                popup_list.setFixedHeight(min(8, len(getattr(line_edit, "all_employee_names", []))) * row_height + 2)
                popup_list.setFixedWidth(line_edit.width())
                popup_list.move(line_edit.mapToGlobal(QPoint(0, line_edit.height())))
                popup_list.show()
                line_edit.setFocus()

        arrow_btn.clicked.connect(toggle_popup)

        # ---------- Click-away handling ----------
        class ClickAwayFilter(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.MouseButtonPress:
                    if popup_list.isVisible() and not (
                        popup_list.geometry().contains(event.globalPosition().toPoint()) or
                        line_edit.geometry().contains(line_edit.mapFromGlobal(event.globalPosition().toPoint())) or
                        arrow_btn.geometry().contains(arrow_btn.mapFromGlobal(event.globalPosition().toPoint()))
                    ):
                        popup_list.hide()
                        line_edit.clearFocus()
                return False

        click_filter = ClickAwayFilter(window)
        window.installEventFilter(click_filter)

        # ---------- Login Button ----------
        class LoginButton(QWidget):
            def __init__(self, callback=None, parent=None, text="Login"):
                super().__init__(parent)
                self.bg_color = "#3B3B3B"
                self.hover_color = "#1AA0FF"
                self.text = text
                self.callback = callback
                self.setFixedSize(int(line_edit.width()*0.6), line_edit.height())

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
                font.setBold(False)
                font.setPointSize(int(line_edit_font_size*0.7))
                painter.setFont(font)
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)

            def mousePressEvent(self, event):
                if callable(self.callback):
                    self.callback()

        login_button = LoginButton(parent=window, callback=lambda: trigger_login(), text="Login")
        login_button.move(int((window.width() * 0.476)), int(window.height() * 0.723))
        login_button.show()

        # ---------- Trigger Login ----------
        def trigger_login():
            selected_name = line_edit.text()
            entered_password = password_edit.text()
            selected_emp = next((emp for emp in all_employees if emp.employeeName == selected_name), None)

            if not selected_emp or entered_password != selected_emp.password:
                # Wrong password: red outline + shake + reset field
                red_color = "#FF5555"
                anim = QPropertyAnimation(password_edit, b"pos", window)
                original_pos = password_edit.pos()
                anim.setDuration(150)
                anim.setKeyValueAt(0, original_pos)
                anim.setKeyValueAt(0.25, original_pos + QPoint(-5, 0))
                anim.setKeyValueAt(0.5, original_pos + QPoint(5, 0))
                anim.setKeyValueAt(0.75, original_pos + QPoint(-5, 0))
                anim.setKeyValueAt(1, original_pos)
                anim.start()

                # Set red border
                password_edit.setStyleSheet(f"""
                    QLineEdit {{
                        background-color: #3B3B3B;
                        color: white;
                        border: 2px solid {red_color};
                        border-radius: 0px;
                        font-size: {line_edit_font_size}px;
                        padding-left: 8px;
                    }}
                """)

                password_edit.setText("")
                password_edit.setPlaceholderText("Password")

                # Wait 1 second after animation and reset border
                def reset_border():
                    password_edit.setStyleSheet(f"""
                        QLineEdit {{
                            background-color: #3B3B3B;
                            color: white;
                            border: 2px solid #3B3B3B;
                            border-radius: 0px;
                            font-size: {line_edit_font_size}px;
                            padding-left: 8px;
                        }}
                    """)
                
                QTimer.singleShot(500, reset_border)  # 1000 ms = 1 second
                return

            # Successful login
            global logged_in_employee
            logged_in_employee = selected_emp  # <-- make the employee global
            print(logged_in_employee.pulseAccess)

            def halfway_callback():
                sign_in_label.hide()
                popup_list.hide()
                line_edit.hide()
                password_edit.hide()
                arrow_btn.hide()
                login_button.hide()
                show_initial_menu()

            playBlueRectangleAnimationTopDown(window, halfway_callback)

        # ---------- Raise everything ----------
        line_edit.raise_()
        password_edit.raise_()
        popup_list.raise_()
        arrow_btn.raise_()
        login_button.raise_()
        window.title_bar.raise_()
        window.close_btn.raise_()
        window.minimize_btn.raise_()

    # ---------------- Initialize ----------------
    show_sign_in_overlay(window, show_initial_menu)
    window.show()
    app.exec()

    return getattr(window.menu, "clicked", None)

# ---------------- Main ----------------
if __name__ == "__main__":
    buttonNum = createHomeScreen()
    if buttonNum is None:
        print("Window closed via X")
    else:
        print(f"You clicked image {buttonNum}")
