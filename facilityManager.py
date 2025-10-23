import sys
import os

from PyQt6.QtWidgets import (
    QWidget, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QDialog, QLineEdit, QApplication, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, QEasingCurve, QPoint, QTimer, pyqtProperty
from PyQt6.QtGui import QPixmap, QMouseEvent, QFont, QFontMetrics, QPainter, QColor, QBrush, QPen

from clientCalls import (
    fetch_all_employees,
    remove_employee,
    add_or_update_employee,
    get_facility_workstations,
    removeWorkstation,
    add_facility_workstation,
    loggedOut,
    fetch_pulse_employees
)


GLOBAL_WORKSTATIONS = []

# ---------------- Resource Path ----------------
def resource_path(relative_path):
    try:
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# ---------------- Animated Bar Button ----------------
class AnimatedBarButton(QWidget):
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
            self.label.setPixmap(self.pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
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
        self.anim.setEndValue(QRect((self.width() - target_width)//2, self.base_height, target_width, self.bar_height))
        self.anim.start()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and callable(self.callback):
            self.callback()

# ---------------- Arrow Button ----------------
class ArrowButton(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rotation = 0.0
        self._animating = False
        self.bg_color = "#3B3B3B"

    def getRotation(self):
        return self._rotation

    def setRotation(self, value):
        self._rotation = value
        self.update()

    rotation = pyqtProperty(float, fget=getRotation, fset=setRotation)

    def setAnimating(self, animating: bool):
        self._animating = animating
        self.bg_color = "#1AA0FF" if animating else "#3B3B3B"
        self.update()

    def enterEvent(self, event):
        if not self._animating:
            self.bg_color = "#1AA0FF"
            self.update()

    def leaveEvent(self, event):
        if not self._animating:
            self.bg_color = "#3B3B3B"
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(self.bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())
        w, h = self.width(), self.height()
        painter.translate(w/2, h/2)
        painter.rotate(self._rotation)
        painter.translate(-w/2, -h/2)
        points = [QPoint(int(w*0.3), int(h*0.25)), QPoint(int(w*0.3), int(h*0.75)), QPoint(int(w*0.7), int(h*0.5))]
        painter.setBrush(QColor("white"))
        painter.drawPolygon(*points)

# ---------------- Mode Dial ----------------
class ModeDial(QWidget):
    MODES = ["Staff Manager", "Facility Manager"]

    def __init__(self, parent=None, window_width=800, height=50):
        super().__init__(parent)
        self.height_val = height
        self.width_val = int(window_width * 0.25)
        self.label_width = self.width_val - 40
        self.setFixedSize(self.width_val, self.height_val)

        self.current_index = 0
        self.animating = False  # <-- Click guard
        self.font = QFont("Arial", 10, QFont.Weight.Bold)
        self.calculate_fixed_font()

        # Container for labels
        self.text_container = QWidget(self)
        self.text_container.setGeometry(0, 0, self.label_width, self.height_val)
        self.text_container.setStyleSheet("background-color: #3B3B3B;")

        # Initial label
        self.label = QLabel(self.MODES[self.current_index], self.text_container)
        self.label.setFont(self.font)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setGeometry(0, 0, self.label_width, self.height_val)
        self.label.setStyleSheet("color: white;")

        # Arrow button
        self.arrow_btn = ArrowButton(self)
        self.arrow_btn.setGeometry(self.label_width, 0, 40, self.height_val)
        # Safe click: avoids first-draw crashes
        from PyQt6.QtCore import QTimer
        self.arrow_btn.mousePressEvent = lambda e: QTimer.singleShot(0, self.next_mode)

    def calculate_fixed_font(self):
        max_width = int(self.label_width * 0.7)
        longest_text = max(self.MODES, key=lambda s: len(s))
        font_size = 10
        font = QFont("Arial", font_size, QFont.Weight.Bold)
        metrics = QFontMetrics(font)
        while metrics.horizontalAdvance(longest_text) < max_width:
            font_size += 1
            font.setPointSize(font_size)
            metrics = QFontMetrics(font)
        while metrics.horizontalAdvance(longest_text) > max_width:
            font_size -= 1
            font.setPointSize(font_size)
            metrics = QFontMetrics(font)
        self.font = font

    def next_mode(self):
        if getattr(self, 'animating', False):
            return  # Guard: ignore clicks during animation

        old_index = self.current_index
        new_index = (self.current_index + 1) % len(self.MODES)
        if new_index == old_index:
            return

        self.current_index = new_index
        self.animating = True  # start animation guard

        old_label = self.label
        new_label = QLabel(self.MODES[new_index], self.text_container)
        new_label.setFont(self.font)
        new_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        new_label.setStyleSheet("color: white;")
        new_label.setGeometry(self.label_width, 0, self.label_width, self.height_val)
        new_label.show()

        width = self.label_width

        # --- Correct directions ---
        if old_index == 0:  # Staff Manager -> Facility Manager
            x_end_old = width      # old slides off right
            x_start_new = -width   # new slides in from left
        else:                # Facility Manager -> Staff Manager
            x_end_old = -width     # old slides off left
            x_start_new = width    # new slides in from right

        # Animate old label out
        anim_out = QPropertyAnimation(old_label, b"pos", self)
        anim_out.setDuration(300)
        anim_out.setStartValue(QPoint(0, 0))
        anim_out.setEndValue(QPoint(x_end_old, 0))
        anim_out.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # Animate new label in
        new_label.move(x_start_new, 0)
        anim_in = QPropertyAnimation(new_label, b"pos", self)
        anim_in.setDuration(300)
        anim_in.setStartValue(QPoint(x_start_new, 0))
        anim_in.setEndValue(QPoint(0, 0))
        anim_in.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # Arrow rotation
        arrow_anim = QPropertyAnimation(self.arrow_btn, b"rotation", self)
        arrow_anim.setDuration(300)
        arrow_anim.setStartValue(self.arrow_btn._rotation)
        arrow_anim.setEndValue(self.arrow_btn._rotation + 180)
        arrow_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.arrow_btn.setAnimating(True)
        arrow_anim.finished.connect(lambda: self.arrow_btn.setAnimating(False))
        arrow_anim.start()

        # Cleanup and unlock animation
        def on_finished():
            old_label.setParent(None)
            old_label.deleteLater()
            self.label = new_label
            self.animating = False  # unlock click guard

        anim_in.finished.connect(on_finished)

        anim_out.start()
        anim_in.start()

# ---------------- Employee Table ----------------
class EmployeeTable(QTableWidget):
    def __init__(self, parent, x, y, width, height, header_font):
        super().__init__(parent)
        self.setGeometry(x, y, width, height)
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(["Employee Name"])
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setShowGrid(False)
        self.setFrameShape(QFrame.Shape.Box)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setLineWidth(1)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setStyleSheet("""
            QTableWidget { background-color: rgba(59,59,59,178); color:white; border:1px solid white;}
            QTableWidget::item:selected { background-color: #1AA0FF; color:white;}
            QHeaderView::section { background-color: rgba(59,59,59,255); color:white; border:1px solid white;}
        """)

        header_font = QFont(header_font)
        header_font.setPointSize(int(header_font.pointSize()*0.75))
        self.horizontalHeader().setFont(header_font)

        # --- Internal data store ---
        self.all_employees = []

        # Add search bar as first row
        self.insertRow(0)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search employee...")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #3B3B3B;
                color: white;
                border: 1px solid white;
                padding: 4px;
                selection-background-color: #1AA0FF;
            }
        """)
        self.setCellWidget(0, 0, self.search_bar)
        self.search_bar.textChanged.connect(self.filter_employees)

        self.populate_table()
        self.show()

    # ---------------- Populate Table ----------------
    def populate_table(self):
        global hiddenNames

        employees = fetch_all_employees()

        # Normalize hidden names once
        normalized_hidden = [n.strip().lower() for n in hiddenNames]

        # Filter out hidden names immediately
        self.all_employees = [
            e for e in employees
            if e.employeeName.strip().lower() not in normalized_hidden
        ] if employees else []

        if not self.all_employees:
            self.setRowCount(2)  # row 0 = search bar, row 1 = placeholder
            item = QTableWidgetItem("[SERVER RETURNED EMPTY]")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setForeground(QBrush(QColor("white")))
            self.setItem(1, 0, item)
            return

        # Display the already filtered employees
        self._display_employees(self.all_employees)

    # ---------------- Filter Employees ----------------
    def filter_employees(self, text):
        text_lower = text.strip().lower()
        filtered = [
            e for e in self.all_employees
            if text_lower in e.employeeName.strip().lower()
        ]
        self._display_employees(filtered)

    # ---------------- Display Helper ----------------
    def _display_employees(self, employees):
        # Clear existing rows except search bar
        self.setRowCount(1)  # keep row 0 for search bar
        for i, e in enumerate(employees, start=1):
            self.insertRow(i)
            item = QTableWidgetItem(e.employeeName)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.setItem(i, 0, item)


# ---------------- Trained Station Table ----------------
class TrainedTable(QTableWidget):
    def __init__(self, parent, x, y, width, height, header_font):
        super().__init__(parent)
        self.setGeometry(x, y, width, height)
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(["Trained Workstations"])
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setShowGrid(False)
        self.setFrameShape(QFrame.Shape.Box)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setLineWidth(1)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setStyleSheet("""
            QTableWidget { background-color: rgba(59,59,59,178); color:white; border:1px solid white;}
            QTableWidget::item:selected { background-color: #1AA0FF; color:white;}
            QHeaderView::section { background-color: rgba(59,59,59,255); color:white; border:1px solid white;}
        """)
        header_font = QFont(header_font)
        header_font.setPointSize(int(header_font.pointSize()*0.75))
        self.horizontalHeader().setFont(header_font)

        # start empty
        self.setRowCount(0)
        self.show()

    def populate_table(self, selected_employee: str | None):
        # no employee selected -> placeholder (not selectable)
        if not selected_employee:
            self.setRowCount(1)
            item = QTableWidgetItem("[Select an employee to see trained workstations]")
            flags = item.flags()
            flags &= ~Qt.ItemFlag.ItemIsSelectable
            flags &= ~Qt.ItemFlag.ItemIsEditable
            item.setFlags(flags)
            item.setForeground(QBrush(QColor("white")))
            self.setItem(0, 0, item)
            return

        # fetch facility data
        workstations, availableStations, eligibleList = get_facility_workstations()

        # robust filtering: handle either dict mapping ws -> list or parallel lists
        filtered_workstations = []
        if isinstance(eligibleList, dict):
            # eligibleList expected like { "SwissQP": ["Harrison Howford", ...], ... }
            for ws in workstations:
                if selected_employee in eligibleList.get(ws, []):
                    filtered_workstations.append(ws)
        else:
            # assume parallel lists: workstations, eligibleList (list-of-lists)
            for ws, eligible in zip(workstations, eligibleList):
                if isinstance(eligible, (list, tuple)) and selected_employee in eligible:
                    filtered_workstations.append(ws)

        # if nothing eligible, show message (kept selectable per your request)
        if not filtered_workstations:
            filtered_workstations = [f"[No eligible workstations for {selected_employee}]"]

        # populate rows (workstations selectable, not editable)
        self.setRowCount(len(filtered_workstations))
        for row, ws in enumerate(filtered_workstations):
            item = QTableWidgetItem(str(ws))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setForeground(QBrush(QColor("white")))
            self.setItem(row, 0, item)

# ---------------- Employee Popup & Tick/Cross Button ----------------
class TickCrossButton(QWidget):
    def __init__(self, is_tick=True, callback=None, parent=None):
        super().__init__(parent)
        self.is_tick = is_tick
        self.bg_color = "#3B3B3B"
        self.callback = callback

    def enterEvent(self, event):
        if self.isEnabled():
            self.bg_color = "#1AA0FF"
            self.update()

    def leaveEvent(self, event):
        if self.isEnabled():
            self.bg_color = "#3B3B3B"
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # grey out if disabled
        if not self.isEnabled():
            painter.setBrush(QColor("#7A7A7A"))  # disabled grey
        else:
            painter.setBrush(QColor(self.bg_color))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())
        painter.setPen(Qt.GlobalColor.white)
        w, h = self.width(), self.height()
        if self.is_tick:
            painter.drawLine(int(w*0.28), int(h*0.5), int(w*0.45), int(h*0.7))
            painter.drawLine(int(w*0.45), int(h*0.7), int(w*0.75), int(h*0.3))
        else:
            painter.drawLine(int(w*0.28), int(h*0.28), int(w*0.72), int(h*0.72))
            painter.drawLine(int(w*0.72), int(h*0.28), int(w*0.28), int(h*0.72))

    def mousePressEvent(self, event):
        if self.isEnabled() and callable(self.callback):
            self.callback()



class EmployeePopup(QDialog):
    def __init__(self, parent=None, textbox_width=200, textbox_height=40, margin=16, btn_size=40):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("background-color: #3B3B3B;")

        self.margin = margin
        self.textbox_width = textbox_width
        self.textbox_height = textbox_height
        self.btn_size = btn_size

        # --- Name ---
        self.title_name = QLabel("New Employee Name", self)
        self.title_name.setStyleSheet("color:white;")
        self.title_font = QFont("Arial", 10, QFont.Weight.Bold)
        self.title_name.setFont(self.title_font)
        self.title_name_h = 20

        # --- Pay Rate ---
        self.title_pay = QLabel("Pay Rate", self)
        self.title_pay.setStyleSheet("color:white;")
        self.title_pay.setFont(self.title_font)
        self.title_pay_h = 20

        total_height = margin + self.title_name_h + 5 + textbox_height + 5 + self.title_pay_h + 5 + textbox_height + margin
        total_width = margin + textbox_width + btn_size*2 + margin
        self.setFixedSize(total_width, total_height)

        # --- Textboxes ---
        y_offset = margin
        self.title_name.setGeometry(margin, y_offset, textbox_width, self.title_name_h)
        y_offset += self.title_name_h + 5
        self.textbox_name = QLineEdit(self)
        self.textbox_name.setGeometry(margin, y_offset, textbox_width, textbox_height)
        self.textbox_name.setStyleSheet("QLineEdit { background-color: #3B3B3B; color: white; border:1px solid white; padding:5px;}")

        y_offset += textbox_height + 5
        self.title_pay.setGeometry(margin, y_offset, textbox_width, self.title_pay_h)
        y_offset += self.title_pay_h + 5
        self.textbox_pay = QLineEdit(self)
        self.textbox_pay.setGeometry(margin, y_offset, textbox_width, textbox_height)
        self.textbox_pay.setStyleSheet("QLineEdit { background-color: #3B3B3B; color: white; border:1px solid white; padding:5px;}")
        self.textbox_pay.setText("£")
        self.textbox_pay.cursorPositionChanged.connect(self._fix_cursor)
        self.textbox_pay.textChanged.connect(self._fix_text)

        # --- Tick/Cross Buttons ---
        tick_x = margin + textbox_width + 5
        cross_x = tick_x + btn_size + 5
        tick_y = cross_y = self.textbox_pay.y()

        self.tick_btn = TickCrossButton(is_tick=True, parent=self)
        self.tick_btn.setGeometry(tick_x, tick_y, btn_size, self.textbox_height)

        self.cross_btn = TickCrossButton(is_tick=False, parent=self)
        self.cross_btn.setGeometry(cross_x, cross_y, btn_size, self.textbox_height)

    def _fix_text(self, text):
        if not text.startswith("£"):
            self.textbox_pay.blockSignals(True)
            self.textbox_pay.setText("£" + text.replace("£", ""))
            self.textbox_pay.setCursorPosition(len(self.textbox_pay.text()))
            self.textbox_pay.blockSignals(False)

    def _fix_cursor(self, old_pos, new_pos):
        if new_pos == 0:
            self.textbox_pay.setCursorPosition(1)

    def get_name_pay(self):
        name = self.textbox_name.text().strip() or None
        pay_text = self.textbox_pay.text().replace("£", "").strip()
        try:
            pay = float(pay_text)
        except ValueError:
            pay = None
        return name, pay


def createEmployee_nonblocking(parent, new_btn, result_callback, table_to_refresh=None):
    popup = EmployeePopup(parent, textbox_width=200, textbox_height=40)

    # Position popup
    if new_btn and new_btn.isVisible():
        btn_global = new_btn.mapToGlobal(QPoint(0,0))
        popup.move(btn_global.x(), btn_global.y() + new_btn.height())
    elif parent:
        geom = parent.geometry()
        popup.move(geom.x() + (geom.width() - popup.width())//2,
                   geom.y() + (geom.height() - popup.height())//2)
    else:
        screen = QApplication.primaryScreen()
        g = screen.availableGeometry()
        popup.move(g.x() + (g.width()-popup.width())//2,
                   g.y() + (g.height()-popup.height())//2)

    def on_tick():
        name, pay = popup.get_name_pay()
        if name:
            add_or_update_employee(employeeName=name, password="Password", hourlyRate=pay, workstation_list=[])
            popup.accept()
            if table_to_refresh:
                table_to_refresh.populate_table()
        else:
            popup.reject()

    def on_cross():
        popup.reject()

    popup.tick_btn.callback = on_tick
    popup.cross_btn.callback = on_cross
    popup.textbox_name.setFocus()

    def finished_handler(code):
        result = popup.get_name_pay() if code == QDialog.DialogCode.Accepted else (None, None)
        result_callback(result)
        popup.deleteLater()

    popup.finished.connect(finished_handler)
    popup.open()

# ---------------- Remove Employee ----------------
class ConfirmRemoveEmployeePopup(QDialog):
    def __init__(self, parent=None, employee_name="[Employee]"):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("background-color: #3B3B3B;")
        
        self.employee_name = employee_name
        self.width_val = 300
        self.height_val = 120
        self.btn_size = 40
        self.padding = 16
        self.setFixedSize(self.width_val, self.height_val)
        
        # --- Message Label ---
        self.message_label = QLabel(f"Are you sure you want to remove\n{self.employee_name}?", self)
        self.message_label.setStyleSheet("color:white;")
        self.message_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setGeometry(self.padding, 20, self.width_val - 2*self.padding, 40)
        
        # --- Tick / Cross Buttons centered at bottom ---
        btn_y = self.height_val - self.btn_size - self.padding
        spacing = 20
        total_width = 2*self.btn_size + spacing
        start_x = (self.width_val - total_width)//2
        
        self.tick_btn = TickCrossButton(is_tick=True, parent=self)
        self.tick_btn.setGeometry(start_x, btn_y, self.btn_size, self.btn_size)
        
        self.cross_btn = TickCrossButton(is_tick=False, parent=self)
        self.cross_btn.setGeometry(start_x + self.btn_size + spacing, btn_y, self.btn_size, self.btn_size)

# ---------------- Helper function ----------------
def confirm_remove_employee(parent, employee_name, table_to_refresh=None):
    popup = ConfirmRemoveEmployeePopup(parent, employee_name)

    # Center popup relative to parent
    if parent:
        geom = parent.geometry()
        popup.move(geom.x() + (geom.width() - popup.width()) // 2,
                   geom.y() + (geom.height() - popup.height()) // 2)
    else:
        screen = QApplication.primaryScreen()
        g = screen.availableGeometry()
        popup.move(g.x() + (g.width() - popup.width()) // 2,
                   g.y() + (g.height() - popup.height()) // 2)

    # Tick callback
    def on_tick():
        try:
            remove_employee(employee_name)
            if table_to_refresh:
                table_to_refresh.populate_table()
        except Exception as e:
            print(f"[ERROR] Failed to remove employee: {e}")
        popup.accept()

    # Cross callback
    def on_cross():
        popup.reject()

    popup.tick_btn.callback = on_tick
    popup.cross_btn.callback = on_cross

    # Cleanup after closing
    def finished_handler(code):
        popup.deleteLater()
        # Refocus main window so hover animations work
        if parent:
            parent.activateWindow()
            parent.raise_()
            parent.setFocus()

    popup.finished.connect(finished_handler)

    # Open as non-blocking modal
    popup.open()

def removeEmp(screen_instance):
    table = next((elem for elem in screen_instance.elements if isinstance(elem, EmployeeTable)), None)
    if not table:
        return
    selected_items = table.selectedItems()
    if not selected_items:
        return
    row = selected_items[0].row()
    employee_name_item = table.item(row, 0)
    if not employee_name_item:
        return
    employee_name = employee_name_item.text()
    if not employee_name:
        return
    try:
        remove_employee(employee_name)
    except Exception as e:
        print(f"[ERROR] Failed to remove employee: {e}")
    table.populate_table()

# ---------------- Remove Workstation Callback ----------------
def remove_workstation_callback(trained_table: QTableWidget, employee_table: QTableWidget):
    selected_items = trained_table.selectedItems()
    if not selected_items:
        print("[DEBUG] No workstation selected.")
        return

    row = selected_items[0].row()
    workstation_item = trained_table.item(row, 0)
    if not workstation_item:
        print("[DEBUG] Selected workstation item is None.")
        return

    workstation_name = workstation_item.text()
    print(f"[DEBUG] Selected workstation: {workstation_name}")

    # Get selected employee
    selected_employee_items = employee_table.selectedItems()
    employee_name = selected_employee_items[0].text() if selected_employee_items else None
    if not employee_name:
        print("[WARN] No employee selected, cannot remove from workstation")
        return

    print(f"[DEBUG] Selected employee: {employee_name}")

    try:
        removeWorkstation(employee_name, workstation_name)  # pass both names
        print(f"[INFO] Removed workstation '{workstation_name}' from employee '{employee_name}'.")
    except Exception as e:
        print(f"[ERROR] Failed to remove workstation: {e}")

    # Refresh the table
    trained_table.populate_table(employee_name)

class WorkstationPopup(QDialog):
    def __init__(self, parent=None, selected_employee_name="[Select employee]", width=400, height=500, btn_size=40, padding=10):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("background-color: #3B3B3B;")
        self.setFixedSize(width, height)

        self.padding = padding
        self.btn_size = btn_size
        self.employee_name = selected_employee_name

        # --- Title ---
        self.title_label = QLabel(f"Add Workstation To {self.employee_name}", self)
        self.title_label.setStyleSheet("color:white;")
        self.title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.title_label.setGeometry(padding, padding, width - 2*padding, 30)

        # --- Table of Workstations ---
        table_y = self.title_label.y() + self.title_label.height() + padding
        table_height = height - table_y - btn_size - 3*padding
        self.table = QTableWidget(self)
        self.table.setGeometry(padding, table_y, width - 2*padding, table_height)
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Workstation"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)  # <-- SHIFT/CTRL for multi-select

        # --- Style ---
        self.table.setStyleSheet("""
            QTableWidget { 
                background-color: rgba(59,59,59,178); 
                color:white; 
                border:1px solid white;
            }
            QTableWidget::item:selected { 
                background-color: #1AA0FF; 
                color:white;
            }
            QHeaderView::section { 
                background-color: rgba(59,59,59,255); 
                color:white; 
                border:1px solid white;
            }
            QScrollBar:vertical {
                background: rgba(59,59,59,178);
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: white;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: white;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        header_font = QFont("Arial", 14, QFont.Weight.Bold)
        self.table.horizontalHeader().setFont(header_font)

        # --- Search bar row (first row) ---
        self.table.setRowCount(1)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search workstation...")
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 25);
                color: white;
                border: 1px solid #1AA0FF;
                border-radius: 4px;
                padding: 4px;
            }
            QLineEdit:focus {
                border: 1px solid #1AA0FF;
                background-color: rgba(255, 255, 255, 40);
            }
        """)
        self.table.setCellWidget(0, 0, self.search_bar)

        # Prevent the search bar row from ever being selected
        self.table.setRowHeight(0, 30)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # --- Populate the rest of the table ---
        self.populate_table()

        # --- Live search filter ---
        self.search_bar.textChanged.connect(self.filter_table)

        # --- Tick/Cross Buttons at bottom right ---
        btn_y = height - btn_size - padding
        self.tick_btn = TickCrossButton(is_tick=True, parent=self)
        self.cross_btn = TickCrossButton(is_tick=False, parent=self)
        self.tick_btn.setGeometry(width - 2*btn_size - 2*padding, btn_y, btn_size, btn_size)
        self.cross_btn.setGeometry(width - btn_size - padding, btn_y, btn_size, btn_size)

    def populate_table(self):
        global GLOBAL_WORKSTATIONS
        workstations, availableStations, eligibleList = get_facility_workstations()
        GLOBAL_WORKSTATIONS = workstations
        self.all_workstations = GLOBAL_WORKSTATIONS

        self.table.setRowCount(len(GLOBAL_WORKSTATIONS) + 1)  # +1 for search bar
        for row, ws in enumerate(GLOBAL_WORKSTATIONS, start=1):
            item = QTableWidgetItem(ws)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setForeground(QBrush(QColor("white")))
            self.table.setItem(row, 0, item)

    def filter_table(self, text):
        text = text.strip().lower()
        for row in range(1, self.table.rowCount()):  # skip search bar row
            item = self.table.item(row, 0)
            if not item:
                continue
            match = text in item.text().lower()
            self.table.setRowHidden(row, not match)

    def get_selected_workstations(self):
        # Skip the search bar
        return [
            self.table.item(row, 0).text()
            for row in range(1, self.table.rowCount())
            if self.table.item(row, 0)
            and not self.table.isRowHidden(row)
            and self.table.item(row, 0).isSelected()
        ]

# ----------------- Button creator -----------------
def createAddStationButton(parent_window, employee_table, trained_table, x, y, scale_factor=0.25):
    btn = AnimatedBarButton(resource_path("images/addStation.png"), None, parent_window, scale_factor=scale_factor)
    btn.move(x, y)

    def on_click():
        selected_items = employee_table.selectedItems()
        employee_name = selected_items[0].text() if selected_items else "[Select employee]"

        popup = WorkstationPopup(parent_window, selected_employee_name=employee_name)

        # Center popup
        geom = parent_window.geometry()
        popup.move(geom.x() + (geom.width() - popup.width()) // 2,
                   geom.y() + (geom.height() - popup.height()) // 2)

        # Give focus to table so hover detection works immediately
        popup.table.setFocus()

        # Tick callback: return selected workstations
        def on_tick():
            selected_ws = popup.get_selected_workstations()
            if employee_name != "[Select employee]" and selected_ws:
                # Call the API to update the employee's workstations
                try:
                    add_or_update_employee(employeeName=employee_name,
                                           workstation_list=selected_ws)
                    trained_table.populate_table(employee_name)
                    print(f"[INFO] Updated {employee_name} with workstations: {selected_ws}")
                except Exception as e:
                    print(f"[ERROR] Failed to update employee workstations: {e}")
            else:
                print("[WARN] No employee selected or no workstations selected.")

            popup.accept()
            parent_window.activateWindow()
            parent_window.raise_()
            parent_window.setFocus()


        # Cross callback: just close
        def on_cross():
            popup.reject()
            parent_window.activateWindow()
            parent_window.raise_()
            parent_window.setFocus()

        popup.tick_btn.callback = on_tick
        popup.cross_btn.callback = on_cross

        # Cleanup after popup closes
        def finished_handler(code):
            popup.deleteLater()

        popup.finished.connect(finished_handler)
        popup.open()  # non-blocking modal

    btn.callback = on_click
    btn.show()
    return btn

class EmployeeRateEntry(QWidget):
    def __init__(self, parent=None, width=200, height=40, btn_size=40):
        super().__init__(parent)
        self.setFixedSize(width + btn_size + 5, height)

        # --- Entry field ---
        self.line_edit = QLineEdit(self)
        self.line_edit.setGeometry(0, 0, width, height)
        self.line_edit.setStyleSheet(
            "QLineEdit { background-color: #3B3B3B; color: white; border:1px solid white; padding:5px; }"
        )
        self.line_edit.setText("£XX.XX")
        self.line_edit.setReadOnly(True)

        # Prevent cursor before £
        self.line_edit.cursorPositionChanged.connect(self._fix_cursor)
        # Ensure £ prefix is never deleted
        self.line_edit.textEdited.connect(self._ensure_prefix)

        # --- Tick/Cross button ---
        self.button = TickCrossButton(is_tick=True, parent=self)
        self.button.setGeometry(width + 5, 0, btn_size, height)
        self.button.callback = self.on_button_clicked

        # --- State ---
        self.active_employee = None
        self.ticked = False     # True if showing cross
        self.editing = False    # True if editing mode
        self._original_rate = None  # Store the original rate for comparison

    # ---------------- Reset entry ----------------
    def reset_entry(self):
        self.line_edit.setText("£XX.XX")
        self.line_edit.setReadOnly(True)
        self.button.is_tick = True
        self.ticked = False
        self.editing = False
        self._original_rate = None
        self.update()

    # ---------------- Tick / Cross logic ----------------
    def on_button_clicked(self):
        if not self.ticked:
            # Tick pressed → fetch employee's current rate
            if self.active_employee:
                from clientCalls import fetch_all_employees
                employees = fetch_all_employees()

                emp_data = next(
                    (e for e in employees if (getattr(e, "employeeName", None) or e.get("employeeName")) == self.active_employee),
                    None
                )

                if emp_data:
                    rate = getattr(emp_data, "hourlyRate", None) or emp_data.get("hourlyRate", "0.00")
                    self.line_edit.setText(f"£{float(rate):.2f}")
                    self._original_rate = float(rate)  # store original
                else:
                    self.line_edit.setText("£0.00")
                    self._original_rate = 0.00

                self.line_edit.setReadOnly(False)   # enable editing
                self.button.is_tick = False         # switch to cross
                self.ticked = True
                self.editing = True

        else:
            # Cross pressed → commit new rate only if changed
            if self.editing and self.active_employee:
                raw_text = self.line_edit.text().replace("£", "").strip()
                try:
                    new_rate = float(raw_text)
                except ValueError:
                    new_rate = 0.00

                # enforce 2dp formatting
                new_rate = float(f"{new_rate:.2f}")

                # Only update if changed
                if self._original_rate is None or new_rate != self._original_rate:
                    add_or_update_employee(
                        employeeName=self.active_employee,
                        hourlyRate=new_rate,
                        workstation_list=[]  # always empty
                    )
                    print("SENT")

            # Reset UI
            self.reset_entry()

    # ---------------- Employee change ----------------
    def set_employee(self, employee_name):
        if self.active_employee != employee_name:
            self.active_employee = employee_name
            self.reset_entry()

    # ---------------- Cursor guard ----------------
    def _fix_cursor(self, old_pos, new_pos):
        # Block cursor from being before "£"
        if new_pos == 0:
            self.line_edit.setCursorPosition(1)

    # ---------------- Prefix guard ----------------
    def _ensure_prefix(self, text):
        if not text.startswith("£"):
            self.line_edit.blockSignals(True)
            self.line_edit.setText("£" + text.replace("£", ""))
            self.line_edit.setCursorPosition(max(1, len(self.line_edit.text())))
            self.line_edit.blockSignals(False)

class EmployeePasswordEntry(QWidget):
    def __init__(self, parent=None, width=200, height=40, btn_size=40):
        super().__init__(parent)
        self.setFixedSize(width + btn_size + 5, height)

        # --- Entry field ---
        self.line_edit = QLineEdit(self)
        self.line_edit.setGeometry(0, 0, width, height)
        self.line_edit.setStyleSheet(
            "QLineEdit { background-color: #3B3B3B; color: white; border:1px solid white; padding:5px; }"
        )
        self.line_edit.setReadOnly(True)
        self.line_edit.setText("••••")  # default placeholder

        # --- Tick/Cross button ---
        self.button = TickCrossButton(is_tick=True, parent=self)
        self.button.setGeometry(width + 5, 0, btn_size, height)
        self.button.callback = self.on_button_clicked

        # --- State ---
        self.active_employee = None
        self.ticked = False
        self.editing = False
        self._original_password = None

    # ---------------- Reset entry ----------------
    def reset_entry(self):
        # show placeholder or hide dots
        if self._original_password:
            self.line_edit.setText("•" * len(self._original_password))
        else:
            self.line_edit.setText("••••")
        self.line_edit.setReadOnly(True)
        self.button.is_tick = True
        self.ticked = False
        self.editing = False
        self._original_password = None
        self.update()

    # ---------------- Tick / Cross logic ----------------
    def on_button_clicked(self):
        from clientCalls import fetch_all_employees, add_or_update_employee

        if not self.ticked:
            # Tick pressed → fetch employee's password
            if self.active_employee:
                employees = fetch_all_employees()
                emp_data = next(
                    (e for e in employees if (getattr(e, "employeeName", None) or e.get("employeeName")) == self.active_employee),
                    None
                )
                password = ""
                if emp_data:
                    password = getattr(emp_data, "password", None) or emp_data.get("password", "")

                self._original_password = password
                self.line_edit.setText(password)   # reveal actual password
                self.line_edit.setReadOnly(False)
                self.button.is_tick = False
                self.ticked = True
                self.editing = True

        else:
            # Cross pressed → commit new password if changed
            if self.editing and self.active_employee:
                new_password = self.line_edit.text().strip()
                if self._original_password is None or new_password != self._original_password:
                    add_or_update_employee(
                        employeeName=self.active_employee,
                        password=new_password,
                        hourlyRate=None,
                        workstation_list=[]
                    )
                    print("Password updated!")

            # Reset UI → show dots matching password length
            if self._original_password:
                self.line_edit.setText("•" * len(self._original_password))
            else:
                self.line_edit.setText("••••")
            self.line_edit.setReadOnly(True)
            self.button.is_tick = True
            self.ticked = False
            self.editing = False

class LogoutButton(QWidget):
    def __init__(self, callback=None, parent=None, text="Logout"):
        super().__init__(parent)
        self.bg_color = "#3B3B3B"
        self.hover_color = "#FF5555"
        self.border_color = "#3B3B3B"
        self.text = text
        self.callback = callback
        self._animation_active = False  # <-- new flag

    def enterEvent(self, event):
        if not self._animation_active:   # only change hover color if no animation
            self.bg_color = self.hover_color
            self.update()

    def leaveEvent(self, event):
        if not self._animation_active:   # only reset if no animation
            self.bg_color = "#3B3B3B"
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(self.bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())

        pen = QPen(QColor(self.border_color))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect())

        painter.setPen(Qt.GlobalColor.white)
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text)

    def mousePressEvent(self, event):
        if callable(self.callback):
            self.callback()

    def _play_success_animation(self):
        self._animation_active = True   # lock colors

        original_pos = self.pos()
        anim = QPropertyAnimation(self, b"pos")
        anim.setDuration(300)
        anim.setKeyValueAt(0, original_pos)
        anim.setKeyValueAt(0.25, original_pos + QPoint(-5, 0))
        anim.setKeyValueAt(0.5, original_pos + QPoint(5, 0))
        anim.setKeyValueAt(0.75, original_pos + QPoint(-5, 0))
        anim.setKeyValueAt(1, original_pos)

        if not hasattr(self, "_animations"):
            self._animations = []
        self._animations.append(anim)
        anim.finished.connect(lambda: self._animations.remove(anim))
        anim.start()

        # Green fill + outline
        self.bg_color = "#55FF71"
        self.border_color = "#55FF71"
        self.update()

        # Reset after 1 second
        QTimer.singleShot(500, self._reset_after_success)

    def _reset_after_success(self):
        self.bg_color = "#3B3B3B"
        self.border_color = "#3B3B3B"
        self._animation_active = False  # unlock colors
        self.update()

# ---------------- Workstations Table ----------------
class FacilityTable(QTableWidget):
    def __init__(self, parent, x, y, width, height, header_font):
        super().__init__(parent)
        self.setGeometry(x, y, width, height)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Workstation", "Available"])
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
        self.setFrameShape(QFrame.Shape.Box)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setLineWidth(1)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # Style
        self.setStyleSheet("""
            QTableWidget { 
                background-color: rgba(59,59,59,178); 
                color:white; 
                border:1px solid white;
            }
            QTableWidget::item:selected { 
                background-color: #1AA0FF; 
                color:white;
            }
            QHeaderView::section { 
                background-color: rgba(59,59,59,255); 
                color:white; 
                border:1px solid white;
            }
        """)

        # Header font
        font = QFont(header_font)
        font.setPointSize(int(header_font.pointSize() * 0.75))
        self.horizontalHeader().setFont(font)

        # Fix column widths
        self.setColumnWidth(0, int(width * 0.5))
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Stretch last column

        # Disable horizontal scrolling
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Delay population until widget is fully initialized
        QTimer.singleShot(0, self.populate_table)

    def populate_table(self):
        workstations, availableStations, eligibleList = get_facility_workstations()
        row_count = max(len(workstations), 1)
        self.setRowCount(row_count)

        # Header alignment
        header_item = self.horizontalHeaderItem(1)
        if header_item:
            header_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if not workstations:
            # Empty placeholder
            item = QTableWidgetItem("[No facility workstations available]")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # enable but not selectable
            self.setItem(0, 0, item)
            self.setItem(0, 1, QTableWidgetItem(""))
            return

        for row, (ws, avail) in enumerate(zip(workstations, availableStations)):
            # Workstation name
            ws_item = QTableWidgetItem(str(ws))
            ws_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)  # selectable & enabled
            ws_item.setForeground(QBrush(QColor("white")))
            self.setItem(row, 0, ws_item)

            # Available number
            avail_item = QTableWidgetItem(str(avail))
            avail_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            avail_item.setForeground(QBrush(QColor("white")))
            avail_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 1, avail_item)

class ProductsTable(QTableWidget):
    def __init__(self, parent, x, y, width, height, header_font):
        super().__init__(parent)
        self.setGeometry(x, y, width, height)
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(["Products"])
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setShowGrid(False)
        self.setFrameShape(QFrame.Shape.Box)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setLineWidth(1)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setStyleSheet("""
            QTableWidget { background-color: rgba(59,59,59,178); color:white; border:1px solid white;}
            QTableWidget::item:selected { background-color: #1AA0FF; color:white;}
            QHeaderView::section { background-color: rgba(59,59,59,255); color:white; border:1px solid white;}
        """)
        # Header font
        header_font = QFont(header_font)
        header_font.setPointSize(int(header_font.pointSize() * 0.75))
        self.horizontalHeader().setFont(header_font)

        # Placeholder row
        self.setRowCount(1)
        item = QTableWidgetItem("[SERVER RETURNED EMPTY]")
        flags = item.flags()
        flags &= ~Qt.ItemFlag.ItemIsSelectable
        flags &= ~Qt.ItemFlag.ItemIsEditable
        item.setFlags(flags)
        item.setForeground(QBrush(QColor("white")))
        self.setItem(0, 0, item)

# ---------------- Global function for delete_ws / add_ws ----------------
def handle_delete_workstation(workstation_table):
    selected_items = workstation_table.selectedItems()
    if not selected_items:
        print("No workstation selected!")
        return

    # Take the first selected row's workstation name (column 0)
    selected_row = selected_items[0].row()
    ws_item = workstation_table.item(selected_row, 0)
    workstation_name = ws_item.text() if ws_item else None

    if not workstation_name:
        print("No workstation name found!")
        return

    print("Trying to send workstation ok!")
    # Call the API to add the workstation with addElse=True
    result = add_facility_workstation(workstation_name, addElse=False)
    
    if result.get("status") == "error":
        print(f"Error adding workstation: {result.get('message')}")
    else:
        print(f"Workstation '{workstation_name}' added successfully!")


def handle_add_workstation(workstation_table):
    selected_items = workstation_table.selectedItems()
    if not selected_items:
        print("No workstation selected!")
        return

    # Take the first selected row's workstation name (column 0)
    selected_row = selected_items[0].row()
    ws_item = workstation_table.item(selected_row, 0)
    workstation_name = ws_item.text() if ws_item else None

    if not workstation_name:
        print("No workstation name found!")
        return

    print("Trying to send workstation ok!")
    # Call the API to add the workstation with addElse=True
    result = add_facility_workstation(workstation_name, addElse=True)
    
    if result.get("status") == "error":
        print(f"Error adding workstation: {result.get('message')}")
    else:
        print(f"Workstation '{workstation_name}' added successfully!")

# ---------------- Facility Screen ----------------
class FacilityScreen:
    def __init__(self, window, loggedEmployee = None, return_to_menu=None):
        self.window = window
        self.elements = []
        self.staff_ui_elements = []
        self.facility_ui_elements = []
        self.orig_positions = {}
        self.return_to_menu = return_to_menu
        self.current_ui_mode = "Staff Manager"  # Tracks actual UI state
        self.loggedEmployee = loggedEmployee
        global hiddenNames
        pulse_access = [a.lower() for a in getattr(loggedEmployee, "pulseAccess", [])]
        if "all" in pulse_access:
            hiddenNames = []  
        else:
            hiddenNames = self.getHiddenNames()
        self.setup_ui()


    def getHiddenNames(self):
        pulse_employees = fetch_pulse_employees()
        pulseNames = [employee.employeeName for employee in pulse_employees]
        return pulseNames

    def setup_ui(self):
        w, h = self.window.window_width, self.window.window_height
        padding = 10

        # Home button
        home_btn = AnimatedBarButton(resource_path("images/homeIcon.png"), self.on_button_clicked, self.window, scale_factor=0.25)
        home_btn.move(w - home_btn.width() - padding, self.window.title_bar_height + padding)
        home_btn.show()
        self.elements.append(home_btn)

        # Inside FacilityScreen.setup_ui()
        self.mode_dial = ModeDial(self.window, window_width=w, height=home_btn.height())
        self.mode_dial.move(padding, self.window.title_bar_height + padding)
        self.mode_dial.show()
        self.elements.append(self.mode_dial)

        # Helper for setting opacity
        def set_opacity(widget, opacity_value):
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(opacity_value)
            widget.setGraphicsEffect(effect)

        # Store original next_mode function
        original_next_mode = self.mode_dial.next_mode

        def next_mode_with_slide():
            # Permission check
            pulse_access = [a.lower() for a in getattr(self.loggedEmployee, "pulseAccess", [])]
            has_facility_access = any(role in pulse_access for role in ["facilitymanager", "all"])

            if not self.loggedEmployee or not has_facility_access:
                print("Access denied: cannot switch to Facility Manager.")
                # Optionally: self.mode_dial.flash_warning("Access denied")
                return

            # Perform actual mode change
            old_mode = self.current_ui_mode
            original_next_mode()
            new_mode = self.mode_dial.MODES[self.mode_dial.current_index]
            self.current_ui_mode = new_mode
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.handle_mode_change(old_mode, new_mode))

        # Replace the dial's next_mode with our wrapped version
        self.mode_dial.next_mode = next_mode_with_slide

        # --- Apply access-based visual state ---
        pulse_access = [a.lower() for a in getattr(self.loggedEmployee, "pulseAccess", [])]
        has_facility_access = any(role in pulse_access for role in ["facilitymanager", "all"])

        if not has_facility_access:
            # Dim and disable the mode dial if user lacks access
            set_opacity(self.mode_dial, 0.4)
            self.mode_dial.setEnabled(False)
        else:
            # Full opacity and interactive
            set_opacity(self.mode_dial, 1.0)
            self.mode_dial.setEnabled(True)


        # ---------------- Employee Table ----------------
        table_x, table_y = self.mode_dial.x(), self.mode_dial.y() + self.mode_dial.height() + padding
        table_width, table_height = int(w * 0.25), h - table_y - padding
        self.employee_table = EmployeeTable(self.window, table_x, table_y, table_width, table_height, self.mode_dial.font)
        self.elements.append(self.employee_table)
        self.staff_ui_elements.append(self.employee_table)
        self.orig_positions[self.employee_table] = self.employee_table.pos()
        self.employee_table.itemSelectionChanged.connect(self.on_employee_selected)

        # ---------------- Facility Manager UI ----------------
        # Table positions
        table_x, table_y = self.mode_dial.x(), self.mode_dial.y() + self.mode_dial.height() + padding
        table_width, table_height = int(w * 0.25), h - table_y - padding

        # ---------------- Facility Table ----------------
        fac_table_width, fac_table_height = int(table_width), h - table_y - padding
        self.facility_table = FacilityTable(self.window, table_x, table_y, fac_table_width, fac_table_height, self.mode_dial.font)
        self.facility_table.show()
        self.orig_positions[self.facility_table] = self.facility_table.pos()
        # move offscreen left initially
        self.facility_table.move(-fac_table_width - 50, table_y)

        # ---------------- Products Table ----------------
        extra_gap = int(table_width * 0.25)
        products_table_width, products_table_height = int(table_width * 0.8), fac_table_height
        products_table_x = table_x + fac_table_width + extra_gap
        products_table_y = table_y
        self.products_table = ProductsTable(self.window, products_table_x, products_table_y, products_table_width, products_table_height, self.mode_dial.font)
        self.products_table.show()
        self.orig_positions[self.products_table] = self.products_table.pos()
        # move offscreen left initially
        self.products_table.move(-products_table_width - 50, products_table_y)

        # ---------------- Custom Buttons Between Tables (Top-Aligned) ----------------
        button_width, button_height = 50, 50
        button_x = table_x + fac_table_width + (products_table_x - (table_x + fac_table_width) - button_width) // 2

        # Create Workstation button (top-aligned with Facility Table)
        create_ws = AnimatedBarButton(resource_path("images/addStation.png"), None, self.window, scale_factor=0.25)  # use same add WS image as Staff Manager
        create_ws.move(button_x, table_y)  # align top with Facility Table
        create_ws.show()
        create_ws.callback = lambda: handle_add_workstation(self.facility_table)
        self.orig_positions[create_ws] = create_ws.pos()
        # move offscreen left initially
        create_ws.move(-button_width - 50, table_y)

        # Delete Workstation button (below create_ws, same padding)
        delete_ws = AnimatedBarButton(resource_path("images/binicon.png"), None, self.window, scale_factor=0.25)
        delete_ws.move(button_x, table_y + button_height + padding)
        delete_ws.show()
        delete_ws.callback = lambda: handle_delete_workstation(self.facility_table)
        self.orig_positions[delete_ws] = delete_ws.pos()
        # move offscreen left initially
        delete_ws.move(-button_width - 50, table_y + button_height + padding)
        # ---------------- Facility UI Elements ----------------
        self.facility_ui_elements = [
            self.facility_table,
            create_ws,
            delete_ws,
            self.products_table
        ]

        # Add all elements to the general elements list
        self.elements.extend(self.facility_ui_elements)

        # ---------------- Add/Remove Employee buttons ----------------
        shift_x = table_x + table_width + padding
        new_btn = AnimatedBarButton(resource_path("images/addEmp.png"), None, self.window, scale_factor=0.25)
        new_btn.move(shift_x, table_y)
        new_btn.show()
        self.elements.append(new_btn)
        self.staff_ui_elements.append(new_btn)
        self.orig_positions[new_btn] = new_btn.pos()

        remove_btn = AnimatedBarButton(resource_path("images/binicon.png"), None, self.window, scale_factor=0.25)
        remove_btn.move(shift_x, new_btn.y() + new_btn.height() + padding)
        remove_btn.show()
        remove_btn.callback = lambda: (
            confirm_remove_employee(self.window,
                                    employee_name=self.employee_table.selectedItems()[0].text(),
                                    table_to_refresh=self.employee_table)
            if self.employee_table.selectedItems() else None
        )
        self.elements.append(remove_btn)
        self.staff_ui_elements.append(remove_btn)
        self.orig_positions[remove_btn] = remove_btn.pos()

        # ---------------- Trained Table ----------------
        trained_table_x = remove_btn.x() + remove_btn.width() + padding
        trained_table_y = table_y
        self.trained_table = TrainedTable(self.window, trained_table_x, trained_table_y, table_width, h - trained_table_y - padding, self.mode_dial.font)
        self.elements.append(self.trained_table)
        self.staff_ui_elements.append(self.trained_table)
        self.orig_positions[self.trained_table] = self.trained_table.pos()

        # ---------------- Workstation buttons ----------------
        add_station_btn = createAddStationButton(
            parent_window=self.window,
            employee_table=self.employee_table,
            trained_table=self.trained_table,
            x=self.trained_table.x() + self.trained_table.width() + padding,
            y=self.trained_table.y(),
            scale_factor=0.25
        )
        self.elements.append(add_station_btn)
        self.staff_ui_elements.append(add_station_btn)
        self.orig_positions[add_station_btn] = add_station_btn.pos()

        remove_ws_btn = AnimatedBarButton(resource_path("images/binicon.png"), None, self.window, scale_factor=0.25)
        remove_ws_btn.move(add_station_btn.x(), add_station_btn.y() + add_station_btn.height() + padding)
        remove_ws_btn.show()
        remove_ws_btn.callback = lambda: remove_workstation_callback(self.trained_table, self.employee_table)
        self.elements.append(remove_ws_btn)
        self.staff_ui_elements.append(remove_ws_btn)
        self.orig_positions[remove_ws_btn] = remove_ws_btn.pos()

        # ---------------- Employee Rate Entry ----------------
        rate_entry_x = self.trained_table.x() + self.trained_table.width() + int(self.trained_table.width()*0.25) + padding
        rate_entry_y = table_y
        self.employee_rate_entry = EmployeeRateEntry(self.window, width=200, height=40, btn_size=40)
        self.employee_rate_entry.move(rate_entry_x, rate_entry_y)
        self.employee_rate_entry.show()
        self.elements.append(self.employee_rate_entry)
        self.staff_ui_elements.append(self.employee_rate_entry)
        self.orig_positions[self.employee_rate_entry] = self.employee_rate_entry.pos()

        # Keep employee rate entry synced
        def update_rate_entry():
            selected_items = self.employee_table.selectedItems()
            employee_name = selected_items[0].text() if selected_items else None
            self.employee_rate_entry.set_employee(employee_name)
        self.employee_table.itemSelectionChanged.connect(update_rate_entry)

        # --- Pay Rate Access Control ---
        pulse_access = [a.lower() for a in getattr(self.loggedEmployee, "pulseAccess", [])]
        has_payrate_access = any(role in pulse_access for role in ["all", "viewpayrate"])

        def set_opacity(widget, opacity_value):
            effect = QGraphicsOpacityEffect(widget)
            effect.setOpacity(opacity_value)
            widget.setGraphicsEffect(effect)

        if not has_payrate_access:
            # Lock down input
            self.employee_rate_entry.line_edit.setReadOnly(True)
            self.employee_rate_entry.button.setEnabled(False)
            
            # Apply 40% alpha
            set_opacity(self.employee_rate_entry.line_edit, 0.4)
            set_opacity(self.employee_rate_entry.button, 0.4)
        else:
            # Normal access
            self.employee_rate_entry.line_edit.setReadOnly(False)
            self.employee_rate_entry.button.setEnabled(True)
            
            # Ensure fully visible
            set_opacity(self.employee_rate_entry.line_edit, 1.0)
            set_opacity(self.employee_rate_entry.button, 1.0)


        # ---------------- Employee Password Entry (below rate entry) ----------------
        password_entry_x = rate_entry_x  # same x as rate entry
        password_entry_y = rate_entry_y + self.employee_rate_entry.height() + padding  # below rate entry
        self.employee_password_entry = EmployeePasswordEntry(self.window, width=200, height=40, btn_size=40)
        self.employee_password_entry.move(password_entry_x, password_entry_y)
        self.employee_password_entry.show()
        self.elements.append(self.employee_password_entry)
        self.staff_ui_elements.append(self.employee_password_entry)
        self.orig_positions[self.employee_password_entry] = self.employee_password_entry.pos()

        # Keep password entry synced with employee selection
        def update_password_entry():
            selected_items = self.employee_table.selectedItems()
            employee_name = selected_items[0].text() if selected_items else None
            self.employee_password_entry.active_employee = employee_name

            if employee_name:
                from clientCalls import fetch_all_employees
                employees = fetch_all_employees()
                emp_data = next(
                    (e for e in employees if (getattr(e, "employeeName", None) or e.get("employeeName")) == employee_name),
                    None
                )
                password = getattr(emp_data, "password", None) or emp_data.get("password", "")
                self.employee_password_entry._original_password = password
                self.employee_password_entry.line_edit.setText("•" * max(len(password), 4))  # at least 4 dots
            else:
                self.employee_password_entry._original_password = None
                self.employee_password_entry.line_edit.setText("••••")

            self.employee_password_entry.line_edit.setReadOnly(True)
            self.employee_password_entry.button.is_tick = True
            self.employee_password_entry.ticked = False
            self.employee_password_entry.editing = False

        self.employee_table.itemSelectionChanged.connect(update_password_entry)

        # ---------------- Logout Button (below password entry) ----------------
        logout_button_x = self.employee_password_entry.x()
        logout_button_y = self.employee_password_entry.y() + self.employee_password_entry.height() + padding

        # Create the button first (inherits TickCrossButton visual style)
        self.logout_button = LogoutButton(
            parent=self.window,
            text="Logout",
            callback=lambda: None  # placeholder, set real callback next
        )
        self.logout_button.setFixedSize(self.employee_password_entry.width(), self.employee_password_entry.height())
        self.logout_button.move(logout_button_x, logout_button_y)
        self.logout_button.show()
        self.elements.append(self.logout_button)
        self.staff_ui_elements.append(self.logout_button)
        self.orig_positions[self.logout_button] = self.logout_button.pos()

        # ---------------- Logout Button (below password entry) ----------------
        logout_button_x = self.employee_password_entry.x()
        logout_button_y = self.employee_password_entry.y() + self.employee_password_entry.height() + padding

        self.logout_button = LogoutButton(
            parent=self.window,
            text="Logout",
            callback=lambda: None  # placeholder
        )
        self.logout_button.setFixedSize(
            self.employee_password_entry.width(),
            self.employee_password_entry.height()
        )
        self.logout_button.move(logout_button_x, logout_button_y)
        self.logout_button.show()
        self.elements.append(self.logout_button)
        self.staff_ui_elements.append(self.logout_button)
        self.orig_positions[self.logout_button] = self.logout_button.pos()

        # ---------------- Update logout callback ----------------
        def safe_logout_callback():
            selected_items = self.employee_table.selectedItems()
            if not selected_items:
                print("No employee selected")
                return

            employee_name = selected_items[0].text()
            from clientCalls import loggedOut
            response = loggedOut(employee_name)
            print(f"Logout response: {response}")

            # Trigger green shake + outline
            self.logout_button._play_success_animation()

        self.logout_button.callback = safe_logout_callback

        # ---------------- Enable/disable logic ----------------
        def update_logout_button_state():
            has_employee = bool(self.employee_table.selectedItems())
            self.logout_button.setEnabled(has_employee)
            self.logout_button.update()  # force repaint

        self.employee_table.itemSelectionChanged.connect(update_logout_button_state)
        update_logout_button_state()  # set initial state

        # Disable buttons initially
        add_station_btn.setEnabled(False)
        remove_ws_btn.setEnabled(False)
        remove_btn.setEnabled(False)

        def update_button_states():
            has_employee = bool(self.employee_table.selectedItems())
            has_ws = bool(self.trained_table.selectedItems())
            add_station_btn.setEnabled(has_employee)
            remove_ws_btn.setEnabled(has_employee and has_ws)
            remove_btn.setEnabled(has_employee)
        self.employee_table.itemSelectionChanged.connect(update_button_states)
        self.trained_table.itemSelectionChanged.connect(update_button_states)

        # Add employee callback
        new_btn.callback = lambda btn=new_btn: createEmployee_nonblocking(
            self.window,
            btn,
            result_callback=lambda r: None,
            table_to_refresh=self.employee_table
        )

        # Populate trained table with no employee selected
        self.trained_table.populate_table(None)

    # ---------------- Mode change animations ----------------
    def handle_mode_change(self, old_mode, new_mode):
        slide_distance = self.window.window_width + 50
        animations = []

        if old_mode == new_mode:
            return

        # Staff → Facility
        if new_mode == "Facility Manager":
            for elem in self.staff_ui_elements:
                anim = QPropertyAnimation(elem, b"pos")
                anim.setDuration(300)
                anim.setStartValue(elem.pos())
                anim.setEndValue(QPoint(self.orig_positions[elem].x() + slide_distance, elem.y()))
                anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
                anim.start()
                animations.append(anim)

            for elem in self.facility_ui_elements:
                anim = QPropertyAnimation(elem, b"pos")
                anim.setDuration(300)
                anim.setStartValue(elem.pos())  # already offscreen
                anim.setEndValue(self.orig_positions[elem])
                anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
                anim.start()
                animations.append(anim)

        # Facility → Staff
        else:
            for elem in self.staff_ui_elements:
                anim = QPropertyAnimation(elem, b"pos")
                anim.setDuration(300)
                anim.setStartValue(elem.pos())
                anim.setEndValue(self.orig_positions[elem])
                anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
                anim.start()
                animations.append(anim)

            for elem in self.facility_ui_elements:
                anim = QPropertyAnimation(elem, b"pos")
                anim.setDuration(300)
                anim.setStartValue(elem.pos())
                anim.setEndValue(QPoint(-elem.width() - 50, elem.y()))
                anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
                anim.start()
                animations.append(anim)

        self._mode_animations = animations

    # ---------------- Employee selection ----------------
    def on_employee_selected(self):
        selected_items = self.employee_table.selectedItems()
        if not selected_items:
            self.trained_table.populate_table(None)
            return
        self.trained_table.populate_table(selected_items[0].text().strip())

    # ---------------- Home button ----------------
    def on_button_clicked(self):
        if callable(self.return_to_menu):
            self.return_to_menu()

    # ---------------- Cleanup ----------------
    def cleanup(self):
        for elem in self.elements:
            elem.setParent(None)
            elem.deleteLater()
        self.elements.clear()
        self.staff_ui_elements.clear()
        self.facility_ui_elements.clear()
        self.orig_positions.clear()


