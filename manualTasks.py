import sys
import os
from io import BytesIO
import threading

from PyQt6.QtWidgets import (
    QWidget, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QStyledItemDelegate, QLineEdit, QFileDialog, QDialog, QGraphicsOpacityEffect
)
from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, QEasingCurve, QTimer, pyqtProperty, QPoint
from PyQt6.QtGui import (
    QPixmap, QMouseEvent, QFont, QBrush, QColor, QPainter, QPen,
    QKeyEvent, QPageSize, QPageLayout, QFontMetrics
)
from PyQt6.QtPrintSupport import QPrinter

from clientCalls import fetch_manual_tasks, edit_tasks, fetch_all_employees, fetch_employees_tasks, get_facility_workstations

# Optional barcode support
try:
    from barcode import Code128
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False
    print("[WARNING] python-barcode not installed. Install with: pip install python-barcode pillow")

# ---------------- Helper function for opacity ----------------
def set_screen_opacity(elements, opacity_value):
    """Set opacity for all elements in the list."""
    for elem in elements:
        effect = QGraphicsOpacityEffect(elem)
        effect.setOpacity(opacity_value)
        elem.setGraphicsEffect(effect)

# ---------------- Quantity Delegate ----------------
class QuantityDelegate(QStyledItemDelegate):
    """Custom delegate for quantity/barcode columns."""
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        palette = editor.palette()
        palette.setColor(palette.ColorRole.Base, QColor("#1AA0FF"))
        palette.setColor(palette.ColorRole.Text, QColor("white"))
        editor.setPalette(palette)
        editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        editor.clear()
        return editor

    def setEditorData(self, editor, index):
        editor.clear()

    def setModelData(self, editor, model, index):
        text = editor.text()
        try:
            value = round(float(text))
            if value < 0:
                value = 0
        except ValueError:
            value = 0
        model.setData(index, str(value))

# ---------------- Task Table ----------------
class TaskTable(QTableWidget):
    def __init__(self, parent, x, y, width, height, header_font: QFont):
        super().__init__(parent)
        self.setGeometry(x, y, width, height)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["Task Name", "Quantity", "Barcodes"])
        self.verticalHeader().setVisible(False)
        self.setFrameShape(QTableWidget.Shape.Box)
        self.setFrameShadow(QTableWidget.Shadow.Plain)
        self.setLineWidth(1)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        self.setEditTriggers(
            QTableWidget.EditTrigger.SelectedClicked |
            QTableWidget.EditTrigger.CurrentChanged |
            QTableWidget.EditTrigger.AnyKeyPressed
        )

        self.setShowGrid(True)
        self.setStyleSheet("""
            QTableWidget { 
                background-color: rgba(59,59,59,178); 
                color:white; 
                border:1px solid white; 
                gridline-color: white;
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

        self.horizontalHeader().setFont(header_font)
        self.setColumnWidth(0, int(width * 0.40))
        self.setColumnWidth(1, int(width * 0.30))
        self.setColumnWidth(2, int(width * 0.30))
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        # Create ONE shared delegate instance for both columns
        self.quantity_delegate = QuantityDelegate(self)
        self.setItemDelegateForColumn(1, self.quantity_delegate)
        self.setItemDelegateForColumn(2, self.quantity_delegate)

        # --- Internal data store ---
        self.all_tasks = []

        # Add search bar as first row
        self.insertRow(0)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search task...")
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
        self.setSpan(0, 0, 1, 3)  # Span search bar across all 3 columns
        self.search_bar.textChanged.connect(self.filter_tasks)

        QTimer.singleShot(0, self.populate_tasks)

    def mousePressEvent(self, event: QMouseEvent):
        item = self.itemAt(event.pos())
        if item is None:
            self.clearSelection()
            self.itemSelectionChanged.emit()
        else:
            super().mousePressEvent(event)

    def populate_tasks(self):
        try:
            task_names = fetch_manual_tasks()
        except Exception as e:
            task_names = []

        # Store all tasks
        self.all_tasks = task_names if task_names else []

        if not self.all_tasks:
            self.setRowCount(2)  # row 0 = search bar, row 1 = placeholder
            item = QTableWidgetItem("[SERVER RETURNED EMPTY]")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setForeground(QBrush(QColor("white")))
            self.setItem(1, 0, item)
            # Empty cells for other columns
            self.setItem(1, 1, QTableWidgetItem(""))
            self.setItem(1, 2, QTableWidgetItem(""))
            return

        # Display all tasks
        self._display_tasks(self.all_tasks)

    def filter_tasks(self, text):
        """Filter tasks based on search text - searches current table content."""
        text_lower = text.strip().lower()
        
        # Get all current rows (excluding search bar row 0)
        for row in range(1, self.rowCount()):
            task_item = self.item(row, 0)
            if task_item:
                task_name = task_item.text().lower()
                # Show row if search text matches, hide otherwise
                match = text_lower in task_name
                self.setRowHidden(row, not match)

    def _display_tasks(self, tasks):
        """Display the given list of tasks (helper method)."""
        # Clear existing rows except search bar
        self.setRowCount(1)  # keep row 0 for search bar
        
        for i, task_name in enumerate(tasks, start=1):
            self.insertRow(i)
            
            left_item = QTableWidgetItem(task_name)
            left_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            left_item.setForeground(QBrush(QColor("white")))
            left_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.setItem(i, 0, left_item)

            quantity_item = QTableWidgetItem("0")
            quantity_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
            quantity_item.setForeground(QBrush(QColor("white")))
            quantity_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(i, 1, quantity_item)

            barcode_item = QTableWidgetItem("0")
            barcode_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
            barcode_item.setForeground(QBrush(QColor("white")))
            barcode_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(i, 2, barcode_item)

    def get_selected_task(self) -> str | None:
        selected_items = self.selectedItems()
        if not selected_items:
            return None
        # First column of the selected row (skip row 0 which is search bar)
        row = selected_items[0].row()
        if row == 0:  # Don't select search bar row
            return None
        task_item = self.item(row, 0)
        if task_item is None:
            return None
        return task_item.text()

# ---------------- Resource Path ----------------
def resource_path(relative_path):
    try:
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_path, relative_path)
    return path

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
    MODES = ["Manual Task Generation", "Live Ally Tasks"]

    def __init__(self, parent=None, window_width=800, height=50, target_width=None):
        super().__init__(parent)
        self.height_val = height
        
        # If target_width is provided, use it; otherwise use default calculation
        if target_width:
            self.width_val = target_width
        else:
            self.width_val = int(window_width * 0.25)
        
        self.label_width = self.width_val - 40  # 40 is the arrow button width
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
        self.hover_enabled = True
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
        if self.hover_enabled:  # Check flag
            self.bar.setVisible(True)
            self.animate_bar(self.width())

    def leaveEvent(self, event):
        if self.hover_enabled:  # Check flag
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

    def reset_hover(self):
        """Force reset hover state"""
        self.hover_enabled = False  # Disable hover
        self.bar.setVisible(False)
        if self.anim and self.anim.state() == QPropertyAnimation.State.Running:
            self.anim.stop()
        self.bar.setGeometry((self.base_width - 0)//2, self.base_height, 0, self.bar_height)
        
        # Re-enable hover after a short delay
        QTimer.singleShot(50, lambda: setattr(self, 'hover_enabled', True))


class PDFPreview(QWidget):
    def __init__(self, parent=None, x=0, y=0, width=300, height=400):
        super().__init__(parent)
        self.setGeometry(x, y, width, height)
        self.setMinimumSize(width, height)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Enable keyboard focus

        tasks = fetch_employees_tasks()
        if tasks and tasks[-1]:
            availableNum = tasks[-1][-1]
            # ✅ Increment by 1 if it looks like an "m##########" string
            if isinstance(availableNum, str) and availableNum.startswith("m") and availableNum[1:].isdigit():
                num = int(availableNum[1:]) + 1
                availableNum = f"m{num:010d}"
            elif isinstance(availableNum, int):
                availableNum += 1
        else:
            availableNum = None
        tasks = []

        self.startCode = availableNum
        print(f"[DEBUG] startCode initialized to {self.startCode}")


        self.setStyleSheet("background-color: transparent;")
        self.logo = None
        self.labels = []  # store text labels for boxes
        self.current_page = 0  # track current page
        self.total_pages = 1   # track total pages
        self.page_changed = None  # callback for page changes

        logo_path = resource_path("images/logo.png")
        if os.path.exists(logo_path):
            self.logo = QPixmap(logo_path)

    def assign_employees_to_labels(self, employees, task_table):
        from collections import defaultdict

        if not hasattr(self, "labels") or not self.labels:
            print("⚠️ No labels to assign.")
            return

        if not employees:
            print("⚠️ No employees assigned; clearing preview names.")
            self.label_assignments = {}
            return

        # --- 1. Group barcodes by task label
        start_num = 0
        if hasattr(self.pdf_preview, "startCode") and str(self.pdf_preview.startCode).startswith("m"):
            start_num = int(self.pdf_preview.startCode[1:])

        for idx, label in enumerate(labels):
            bc_num = start_num + idx
            bc = f"m{bc_num:010d}"
            task_barcodes[label].append(bc)


        # --- 2. Gather all task rows from the table
        tasks = []
        for row in range(1, task_table.rowCount()):
            name_item = task_table.item(row, 0)
            qty_item = task_table.item(row, 1)
            bc_item = task_table.item(row, 2)
            if not name_item:
                continue
            try:
                task_name = name_item.text().strip()
                qty = int(qty_item.text()) if qty_item else 0
                count = int(bc_item.text()) if bc_item else 0
            except Exception:
                continue
            if count <= 0:
                continue
            label = f"{task_name} x {qty}"
            tasks.append((label, count))

        # --- 3. Divide each task's barcodes across employees
        self.label_assignments = {}
        n = len(employees)
        for label, _ in tasks:
            barcode_indices = task_barcodes.get(label, [])
            if not barcode_indices:
                continue

            per_emp = len(barcode_indices) // n
            remainder = len(barcode_indices) % n
            start = 0
            for i, emp in enumerate(employees):
                end = start + per_emp + (1 if i < remainder else 0)
                for idx in barcode_indices[start:end]:
                    self.label_assignments[idx] = emp
                start = end

        print("📋 PDF preview updated with employee name assignments.")


    def calculate_boxes(self):
        """Calculate coordinates for 6 rows (12 boxes total: left & right)."""
        boxes = []
        page_width = self.width()
        page_height = self.height()
        padding = 20

        # Header position based on logo
        logo_bottom = int(page_height * 0.1) + 10
        header_line_y = logo_bottom + 20
        remaining_height = page_height - header_line_y - padding
        section_height = remaining_height / 6
        
        half_width = (page_width - 2 * padding) / 2

        # Create 12 boxes: 6 rows × 2 columns
        for i in range(6):
            top_y = header_line_y + i * section_height
            # Left box
            boxes.append((padding, top_y, half_width, section_height))
            # Right box
            boxes.append((padding + half_width, top_y, half_width, section_height))
        return boxes

    def update_labels(self, labels):
        """Set labels and trigger repaint."""
        self.labels = labels
        # Calculate total pages needed (12 labels per page)
        self.total_pages = max(1, (len(labels) + 11) // 12)  # Round up
        self.current_page = 0  # Reset to first page
        self.update()  # triggers paintEvent()

    def keyPressEvent(self, event: QKeyEvent):
        """Handle arrow key navigation between pages."""
        if event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_Up:
            if self.current_page > 0:
                self.current_page -= 1
                self.update()
                if callable(self.page_changed):
                    self.page_changed()
        elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_Down:
            if self.current_page < self.total_pages - 1:
                self.current_page += 1
                self.update()
                if callable(self.page_changed):
                    self.page_changed()
        else:
            super().keyPressEvent(event)

    def get_current_page_labels(self):
        """Get the labels for the current page (12 per page)."""
        start_idx = self.current_page * 12
        end_idx = start_idx + 12
        return self.labels[start_idx:end_idx]

    def paintEvent(self, event):
        super().paintEvent(event)
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            page_width = self.width()
            page_height = self.height()

            # White background
            painter.fillRect(0, 0, page_width, page_height, Qt.GlobalColor.white)
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            painter.drawRect(0, 0, page_width, page_height)

            # Draw logo
            logo_bottom = 0
            if self.logo:
                logo_height = int(page_height * 0.1)
                logo_width = int(self.logo.width() * (logo_height / self.logo.height()))
                painter.drawPixmap(10, 10, logo_width, logo_height, self.logo)
                logo_bottom = 10 + logo_height

            # Solid header line
            padding = 20
            header_line_y = int(logo_bottom + 20)
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            painter.drawLine(int(padding), int(header_line_y),
                             int(page_width - padding), int(header_line_y))

            # Divide remaining area into 6 rows
            boxes = self.calculate_boxes()

            pen_dotted = QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DotLine)
            painter.setPen(pen_dotted)
            
            # Draw horizontal lines (between rows)
            for i in range(1, 6):
                y = int(boxes[i * 2][1])  # every 2nd box is a new row
                painter.drawLine(int(padding), y, int(page_width - padding), y)

            # Draw vertical middle line
            painter.drawLine(int(page_width // 2),
                             int(header_line_y),
                             int(page_width // 2),
                             int(page_height - padding))

            # Get labels for current page only
            current_labels = self.get_current_page_labels()

            # --- Draw box labels (top center), barcodes (bottom), and barcode images (center) ---
            painter.setPen(QPen(Qt.GlobalColor.black))
            painter.setFont(QFont("Arial", 8, QFont.Weight.Medium))

            # Iterate through boxes on this page
            for box_idx in range(len(boxes)):
                x, y, w, h = boxes[box_idx]
                
                # Generate unique barcode number for this box across all pages
                global_box_idx = self.current_page * 12 + box_idx
                if self.startCode and str(self.startCode).startswith("m"):
                    start_num = int(self.startCode[1:])  # strip 'm' and get numeric
                    barcode_number = f"m{str(start_num + global_box_idx).zfill(10)}"
                else:
                    barcode_number = f"m{str(global_box_idx).zfill(10)}"

                # Only draw label if we have one for this box on this page
                if box_idx < len(current_labels):
                    text = current_labels[box_idx]
                    
                    # Draw task label at TOP center
                    text_rect = QRect(
                        int(x + 5),
                        int(y + 5),
                        int(w - 10),
                        20
                    )
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, text)

                    # >>> NEW BLOCK: draw employee name if assigned <<<
                    if hasattr(self, "label_assignments"):
                        emp_name = self.label_assignments.get(global_box_idx)
                        if emp_name:
                            painter.setFont(QFont("Arial", 7, QFont.Weight.Normal))
                            emp_rect = QRect(
                                int(x + 5),
                                int(y + 22),  # just below the task label
                                int(w - 10),
                                15
                            )
                            painter.drawText(emp_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, emp_name)
                            painter.setFont(QFont("Arial", 8, QFont.Weight.Medium))  # restore font
                    # <<< END NEW BLOCK >>>

                    # Draw barcode number at BOTTOM center
                    barcode_text_rect = QRect(
                        int(x + 5),
                        int(y + h - 20),
                        int(w - 10),
                        15
                    )
                    painter.setFont(QFont("Arial", 7, QFont.Weight.Normal))
                    painter.drawText(barcode_text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, barcode_number)
                    painter.setFont(QFont("Arial", 8, QFont.Weight.Medium))  # restore font

                    # Draw barcode image in CENTER of box
                    self._draw_barcode(painter, barcode_number, x, y+5, w, h)

        except Exception as e:
            print(f"[ERROR] PDFPreview paintEvent exception: {e}")


    def render_page_to_painter(self, painter, page_num, page_width, page_height):
        """Render a specific page to a painter (for PDF export)."""
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Convert to integers
            page_width = int(page_width)
            page_height = int(page_height)

            # White background
            painter.fillRect(0, 0, page_width, page_height, Qt.GlobalColor.white)
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            painter.drawRect(0, 0, page_width, page_height)

            # Draw logo
            logo_bottom = 0
            if self.logo:
                logo_height = int(page_height * 0.1)
                logo_width = int(self.logo.width() * (logo_height / self.logo.height()))
                painter.drawPixmap(10, 10, logo_width, logo_height, self.logo)
                logo_bottom = 10 + logo_height

            # Solid header line
            padding = 20
            header_line_y = int(logo_bottom + 20)
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            painter.drawLine(int(padding), int(header_line_y),
                             int(page_width - padding), int(header_line_y))

            # Calculate boxes for this page size
            remaining_height = page_height - header_line_y - padding
            section_height = remaining_height / 6
            half_width = (page_width - 2 * padding) / 2
            
            boxes = []
            for i in range(6):
                top_y = header_line_y + i * section_height
                boxes.append((padding, top_y, half_width, section_height))
                boxes.append((padding + half_width, top_y, half_width, section_height))

            # Draw grid lines
            pen_dotted = QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DotLine)
            painter.setPen(pen_dotted)
            
            for i in range(1, 6):
                y = int(boxes[i * 2][1])
                painter.drawLine(int(padding), y, int(page_width - padding), y)

            painter.drawLine(int(page_width // 2),
                             int(header_line_y),
                             int(page_width // 2),
                             int(page_height - padding))

            # Get labels for this page
            start_idx = page_num * 12
            end_idx = start_idx + 12
            page_labels = self.labels[start_idx:end_idx]

            # Draw content
            painter.setPen(QPen(Qt.GlobalColor.black))

            for box_idx in range(len(boxes)):
                x, y, w, h = boxes[box_idx]
                
                global_box_idx = page_num * 12 + box_idx
                if self.startCode and str(self.startCode).startswith("m"):
                    start_num = int(self.startCode[1:])  # strip 'm' and get numeric
                    barcode_number = f"m{str(start_num + global_box_idx).zfill(10)}"
                else:
                    barcode_number = f"m{str(global_box_idx).zfill(10)}"

                if box_idx < len(page_labels):
                    text = page_labels[box_idx]
                    
                    # Draw task label at TOP - more padding from edges
                    painter.setFont(QFont("Arial", 12, QFont.Weight.Medium))
                    text_rect = QRect(int(x + 30), int(y + 30), int(w - 60), int(h * 0.25))
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, text)

                    # Draw barcode number at BOTTOM - more padding from edges
                    painter.setFont(QFont("Arial", 12, QFont.Weight.Normal))
                    barcode_text_rect = QRect(int(x + 30), int(y + h * 0.80), int(w - 60), int(h * 0.15))
                    painter.drawText(barcode_text_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, barcode_number)

                    # Draw barcode image in CENTER of box
                    self._draw_barcode(painter, barcode_number, x, y, w, h)

        except Exception as e:
            print(f"[ERROR] render_page_to_painter exception: {e}")
            import traceback
            traceback.print_exc()

    def _draw_barcode(self, painter, barcode_text, box_x, box_y, box_w, box_h):
        """Draw a scannable barcode in the center of the box."""
        try:
            # Save painter state
            painter.save()
            
            # Barcode area: centered, leaving space for text at top and bottom
            barcode_height = int(box_h * 0.4)  # 40% of box height
            barcode_width = int(box_w * 0.8)   # 80% of box width
            
            # Center the barcode
            barcode_x = int(box_x + (box_w - barcode_width) / 2)
            barcode_y = int(box_y + (box_h - barcode_height) / 2)
            
            if BARCODE_AVAILABLE:
                # Generate actual scannable barcode
                try:
                    buffer = BytesIO()
                    
                    # Code128 can encode alphanumeric data
                    code128 = Code128(barcode_text, writer=ImageWriter())
                    
                    # Use reasonable fixed dimensions that work well for Code128
                    # These will be scaled to fit, but generated at high resolution
                    code128.write(buffer, options={
                        'module_height': 15,  # Height of bars in mm
                        'module_width': 0.4,  # Width of narrowest bar in mm
                        'quiet_zone': 2.5,    # Margin around barcode
                        'font_size': 0,       # Hide text below barcode
                        'text_distance': 1,
                        'background': 'white',
                        'foreground': 'black',
                        'dpi': 300,           # High DPI
                    })
                    
                    buffer.seek(0)
                    barcode_pixmap = QPixmap()
                    barcode_pixmap.loadFromData(buffer.read())
                    
                    if not barcode_pixmap.isNull():
                        # Scale to fit the available space while maintaining aspect ratio
                        scaled_pixmap = barcode_pixmap.scaled(
                            barcode_width,
                            barcode_height,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        # Center in the allocated space
                        draw_x = barcode_x + (barcode_width - scaled_pixmap.width()) // 2
                        draw_y = barcode_y + (barcode_height - scaled_pixmap.height()) // 2
                        
                        painter.drawPixmap(draw_x, draw_y, scaled_pixmap)
                    else:
                        raise Exception("Failed to load barcode image")
                    
                except Exception as e:
                    print(f"[ERROR] Failed to generate barcode: {e}")
                    import traceback
                    traceback.print_exc()
                    # Fall back to simple visual barcode
                    self._draw_simple_barcode(painter, barcode_text, barcode_x, barcode_y, barcode_width, barcode_height)
            else:
                # Fall back to simple visual barcode if library not available
                self._draw_simple_barcode(painter, barcode_text, barcode_x, barcode_y, barcode_width, barcode_height)
            
            # Restore painter state
            painter.restore()
            
        except Exception as e:
            print(f"[ERROR] PDFPreview._draw_barcode exception: {e}")
            painter.restore()
    
    def _draw_simple_barcode(self, painter, barcode_text, barcode_x, barcode_y, barcode_width, barcode_height):
        """Fallback: Draw a simple visual barcode (not scannable)."""
        bar_count = len(barcode_text) + 2
        bar_width = barcode_width / bar_count
        
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Start bar (black)
        painter.setBrush(QBrush(Qt.GlobalColor.black))
        painter.drawRect(int(barcode_x), barcode_y, int(bar_width), barcode_height)
        
        # Data bars (alternate based on character value)
        for i, char in enumerate(barcode_text):
            is_black = (ord(char) % 2 == 0)
            x_pos = int(barcode_x + (i + 1) * bar_width)
            
            if is_black:
                painter.setBrush(QBrush(Qt.GlobalColor.black))
                painter.drawRect(x_pos, barcode_y, int(bar_width), barcode_height)
        
        # Stop bar (black)
        painter.setBrush(QBrush(Qt.GlobalColor.black))
        painter.drawRect(int(barcode_x + (bar_count - 1) * bar_width), barcode_y, int(bar_width), barcode_height)

class LiveSuccessPopup(QDialog):
    """Identical styling/flow to NewTaskPopup; text in top half, square tick centered below."""
    def __init__(self, parent=None, message="Your Tasks are now Live!", margin=16, btn_size=40):
        super().__init__(parent)
        self.parent_window = parent
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("background-color: #3B3B3B;")  # same as NewTaskPopup

        # ---- Title ----
        self.title_label = QLabel(message, self)
        self.title_label.setStyleSheet("color:white;")
        self.title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_h = 25

        # ---- Dimensions ----
        msg_block_h = 50
        total_height = margin + self.title_h + 5 + msg_block_h + margin
        total_width  = margin + 220 + btn_size * 2 + margin
        self.setFixedSize(total_width, total_height)

        # ---- Place title in top half ----
        title_y = total_height // 4 - self.title_h // 2
        self.title_label.setGeometry(
            margin,
            title_y,
            total_width - 2 * margin,
            self.title_h
        )

        # ---- Square tick button centered below title ----
        tick_x = (total_width - btn_size) // 2
        tick_y = total_height // 2  # vertically centered below text
        self.tick_btn = TickCrossButton(is_tick=True, parent=self, callback=self.accept)
        self.tick_btn.setGeometry(tick_x, tick_y, btn_size, btn_size)  # square dimensions

        # ---- No cross button ----

        # ---- Center on parent ----
        if parent:
            pg = parent.geometry()
            self.move(
                pg.x() + (pg.width() - self.width()) // 2,
                pg.y() + (pg.height() - self.height()) // 2
            )

def sendFormat(data, pdf_preview, employee_multiplier=1):
    labels = []
    employee_multiplier = max(1, int(employee_multiplier or 1))

    for row in data:
        if len(row) < 3:
            continue
        name, qty, barcodes = row
        try:
            count = int(barcodes)
            qty = int(qty)
        except ValueError:
            continue  # skip invalid rows
        
        if count <= 0:
            continue

        label = f"{name} x {qty}"
        # Add this label 'count * employee_multiplier' times
        for _ in range(count * employee_multiplier):
            labels.append(label)

    # Update PDF
    pdf_preview.update_labels(labels)

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

class NewTaskPopup(QDialog):
    def __init__(self, parent=None, textbox_width=220, textbox_height=40, margin=16, btn_size=40):
        super().__init__(parent)
        self.parent_window = parent  # store main window reference
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("background-color: #3B3B3B;")

        self.result_text = None

        # ---- Title ----
        self.title_label = QLabel("Name New Task", self)
        self.title_label.setStyleSheet("color:white;")
        self.title_font = QFont("Arial", 10, QFont.Weight.Bold)
        self.title_label.setFont(self.title_font)
        self.title_h = 20

        # ---- Layout ----
        total_height = margin + self.title_h + 5 + textbox_height + margin
        total_width = margin + textbox_width + btn_size * 2 + margin
        self.setFixedSize(total_width, total_height)

        # ---- Textbox ----
        y_offset = margin
        self.title_label.setGeometry(margin, y_offset, textbox_width, self.title_h)
        y_offset += self.title_h + 5

        self.textbox = QLineEdit(self)
        self.textbox.setGeometry(margin, y_offset, textbox_width, textbox_height)
        self.textbox.setStyleSheet(
            "QLineEdit { background-color: #3B3B3B; color: white; border:1px solid white; padding:5px; }"
        )
        self.textbox.setPlaceholderText("Enter task name...")

        # ---- Tick / Cross Buttons ----
        tick_x = margin + textbox_width + 5
        cross_x = tick_x + btn_size + 5
        btn_y = y_offset  # aligned with textbox

        self.tick_btn = TickCrossButton(is_tick=True, parent=self, callback=self._on_tick)
        self.tick_btn.setGeometry(tick_x, btn_y, btn_size, textbox_height)

        self.cross_btn = TickCrossButton(is_tick=False, parent=self, callback=self._on_cross)
        self.cross_btn.setGeometry(cross_x, btn_y, btn_size, textbox_height)

        # ---- Center the popup on parent window ----
        if parent:
            parent_geom = parent.geometry()
            self.move(
                parent_geom.x() + (parent_geom.width() - self.width()) // 2,
                parent_geom.y() + (parent_geom.height() - self.height()) // 2
            )

    def _on_tick(self):
        self.result_text = self.textbox.text().strip()
        self.accept()

    def _on_cross(self):
        self.result_text = None
        self.reject()

    def _refocus_parent(self):
        """Refocus the main window to re-enable hover effects."""
        if self.parent_window:
            self.parent_window.activateWindow()
            self.parent_window.raise_()

    def get_result(self):
        return self.result_text

def createNewTask(parent=None, button=None, task_table=None, screen_elements=None):
    # Dim the screen
    if screen_elements:
        set_screen_opacity(screen_elements, 0.3)
    
    # Disable hover BEFORE opening popup
    if button:
        button.hover_enabled = False
        button.bar.setVisible(False)
        if button.anim and button.anim.state() == QPropertyAnimation.State.Running:
            button.anim.stop()
        button.bar.setGeometry((button.base_width - 0)//2, button.base_height, 0, button.bar_height)
    
    popup = NewTaskPopup(parent)
    
    def on_tick():
        popup.result_text = popup.textbox.text().strip()
        popup.accept()

    def on_cross():
        popup.result_text = None
        popup.reject()

    popup.tick_btn.callback = on_tick
    popup.cross_btn.callback = on_cross
    
    # Set focus to textbox
    popup.textbox.setFocus()
    
    def finished_handler(code):
        task_name = popup.result_text if code == QDialog.DialogCode.Accepted else None
        
        # Restore full opacity
        if screen_elements:
            set_screen_opacity(screen_elements, 1.0)
        
        # Re-enable hover
        if button:
            QTimer.singleShot(100, lambda: setattr(button, 'hover_enabled', True))
        
        # Refocus parent
        if parent:
            parent.activateWindow()
            parent.raise_()
        
        if task_name:
            def run_create():
                response = edit_tasks(taskName=task_name, editFlag=True, debug=False)
                if response.get("status") == "success" and task_table:
                    # Add new row to table
                    row_count = task_table.rowCount()
                    task_table.insertRow(row_count)
                    
                    # Task name (non-editable)
                    left_item = QTableWidgetItem(task_name)
                    left_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    left_item.setForeground(QBrush(QColor("white")))
                    left_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                    task_table.setItem(row_count, 0, left_item)

                    # Quantity (editable)
                    quantity_item = QTableWidgetItem("0")
                    quantity_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
                    quantity_item.setForeground(QBrush(QColor("white")))
                    quantity_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    task_table.setItem(row_count, 1, quantity_item)

                    # Barcode (editable)
                    barcode_item = QTableWidgetItem("0")
                    barcode_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
                    barcode_item.setForeground(QBrush(QColor("white")))
                    barcode_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    task_table.setItem(row_count, 2, barcode_item)
                    
                else:
                    print(f"Failed to create task '{task_name}': {response.get('message')}")

            threading.Thread(target=run_create).start()
        else:
            print("Task creation canceled.")
        
        popup.deleteLater()
    
    popup.finished.connect(finished_handler)
    popup.open()  # Non-blocking - this enables the fade-in animation!


from PyQt6.QtWidgets import QDialog, QLabel, QTableWidget, QTableWidgetItem, QLineEdit, QAbstractItemView
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QBrush, QColor

class PostToAllyPopup(QDialog):
    """Original Ally popup, but with Shift/Ctrl multi-select enabled.
    Styling and layout are unchanged; only selection + result payload differ.
    - Call get_result() -> list[str] of selected employee names (may be empty).
    """
    def __init__(self, parent=None, textbox_width=220, textbox_height=40, margin=16, btn_size=40):
        super().__init__(parent)
        self.parent_window = parent
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("background-color: #3B3B3B;")

        self._selected_employees = []

        # ---- Title ----
        self.title_label = QLabel("Post Tasks To Ally", self)
        self.title_label.setStyleSheet("color:white;")
        self.title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.title_h = 25

        # ---- Dimensions ----
        table_height = 250
        total_height = margin + self.title_h + 5 + table_height + btn_size + 2 * margin
        total_width = textbox_width + 2 * margin + btn_size * 2
        self.setFixedSize(total_width, total_height)

        # ---- Title ----
        y_offset = margin
        self.title_label.setGeometry(margin, y_offset, total_width - 2 * margin, self.title_h)
        y_offset += self.title_h + 5

        # ---- Table ----
        self.table = QTableWidget(self)
        self.table.setGeometry(margin, y_offset, total_width - 2 * margin, table_height)
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Employee"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # *** Change: allow Shift/Ctrl multi-select ***
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        # ---- Style ----
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
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        # ---- Search bar row ----
        self.table.setRowCount(1)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search employee...")
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
        self.table.setRowHeight(0, 30)

        # ---- Populate table ----
        self.populate_table()

        # Double-click still accepts (collects multi-selection on accept)
        self.table.itemDoubleClicked.connect(lambda _: self._on_tick())

        # ---- Live filter ----
        self.search_bar.textChanged.connect(self.filter_table)

        # ---- Buttons ----
        btn_y = y_offset + table_height + margin
        tick_x = total_width - 2 * btn_size - margin
        cross_x = total_width - btn_size - margin

        self.tick_btn = TickCrossButton(is_tick=True, parent=self, callback=self._on_tick)
        self.tick_btn.setGeometry(tick_x, btn_y, btn_size, btn_size)

        self.cross_btn = TickCrossButton(is_tick=False, parent=self, callback=self._on_cross)
        self.cross_btn.setGeometry(cross_x, btn_y, btn_size, btn_size)

        # ---- Center on parent ----
        if parent:
            parent_geom = parent.geometry()
            self.move(
                parent_geom.x() + (parent_geom.width() - self.width()) // 2,
                parent_geom.y() + (parent_geom.height() - self.height()) // 2
            )

    def populate_table(self):
        employees = fetch_all_employees()
        self.all_employees = [e.employeeName for e in employees]

        # Optionally extend with facility workstations (first list only)
        try:
            ws_lists = get_facility_workstations()
            if isinstance(ws_lists, (list, tuple)) and len(ws_lists) >= 1:
                first_list = ws_lists[0] or []
                # Coerce to strings and de-dup against employees
                existing = set(n.lower() for n in self.all_employees)
                for x in first_list:
                    s = str(x).strip()
                    if s and s.lower() not in existing:
                        self.all_employees.append(s)
                        existing.add(s.lower())
        except Exception:
            # If get_facility_workstations isn't imported yet, just skip.
            pass

        self.table.setRowCount(len(self.all_employees) + 1)  # +1 for search bar
        for i, name in enumerate(self.all_employees, start=1):
            item = QTableWidgetItem(name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setForeground(QBrush(QColor("white")))
            self.table.setItem(i, 0, item)

    def filter_table(self, text):
        text = text.strip().lower()
        for row in range(1, self.table.rowCount()):
            item = self.table.item(row, 0)
            if not item:
                continue
            match = text in item.text().lower()
            self.table.setRowHidden(row, not match)

    # --- Multi-select helpers ---
    def _selected_names(self) -> list:
        rows = self.table.selectionModel().selectedRows()
        names = []
        for idx in rows:
            it = self.table.item(idx.row(), 0)
            if it:
                t = it.text().strip()
                if t:
                    names.append(t)
        return names

    def _on_tick(self):
        self._selected_employees = self._selected_names()
        self.accept()

    def _on_cross(self):
        self._selected_employees = []
        self.reject()

    def get_result(self):
        """Return list[str] of selected employees ([] if none)."""
        return list(self._selected_employees)

def exportToAlly(parent=None, button=None, task_table=None, pdf_preview=None,
                 screen_elements=None, employee_field=None, owner=None):
    """
    UI-only multi-select Ally flow (no server calls):
      1) Opens PostToAllyPopup with ExtendedSelection.
      2) On confirm, writes selected names into `employee_field`.
      3) NEW: auto-calls owner's send_and_update() to regenerate preview.
    """
    # Dim the screen
    if screen_elements:
        set_screen_opacity(screen_elements, 0.3)

    # Disable hover BEFORE opening popup
    if button:
        try:
            button.hover_enabled = False
            button.bar.setVisible(False)
            if getattr(button, 'anim', None) and button.anim.state() == QPropertyAnimation.State.Running:
                button.anim.stop()
            button.bar.setGeometry((button.base_width - 0)//2, button.base_height, 0, button.bar_height)
        except Exception:
            pass

    popup = PostToAllyPopup(parent)

    def _update_preview_after_popup(owner):
        try:
            employees = [
                owner.employee_table.item(r, 0).text().strip()
                for r in range(owner.employee_table.rowCount())
                if owner.employee_table.item(r, 0)
                and owner.employee_table.item(r, 0).text().strip()
            ]
            owner.pdf_preview.assign_employees_to_labels(employees, owner.task_table)
            owner.pdf_preview.update()
            print("✅ PDF preview refreshed after popup close.")
        except Exception as e:
            print(f"[WARN] Delayed preview update failed: {e}")


    def finished_handler(code):
        user_confirmed = (code == QDialog.DialogCode.Accepted)

        # Restore screen and re-enable hover
        if screen_elements:
            set_screen_opacity(screen_elements, 1.0)
        if button:
            QTimer.singleShot(100, lambda: setattr(button, 'hover_enabled', True))

        # Refocus parent window
        if parent:
            try:
                parent.activateWindow()
                parent.raise_()
            except Exception:
                pass

        if user_confirmed:
            selected = popup.get_result()  # list[str]
            if employee_field is not None and selected:
                if hasattr(employee_field, 'add_employees'):
                    employee_field.add_employees(selected)
                    if user_confirmed:
                        selected = popup.get_result()  # list[str]
                        if employee_field is not None and selected:
                            if hasattr(employee_field, 'add_employees'):
                                employee_field.add_employees(selected)
                            else:
                                prev = ''
                                try:
                                    prev = (employee_field.text() or '').strip()
                                except Exception:
                                    prev = ''
                                new_lines = "\n".join(s for s in selected if s and s.strip())
                                new_val = (prev + ("\n" if prev else "") + new_lines).strip()
                                try:
                                    employee_field.setText(new_val)
                                except Exception:
                                    pass

                        # ✅ Schedule preview update *after* popup fully closes and table updates
                        if owner and hasattr(owner, "pdf_preview"):
                            QTimer.singleShot(200, lambda: _update_preview_after_popup(owner))

                else:
                    prev = ''
                    try:
                        prev = (employee_field.text() or '').strip()
                    except Exception:
                        prev = ''
                    new_lines = "\n".join(s for s in selected if s and s.strip())
                    new_val = (prev + ("\n" if prev else "") + new_lines).strip()
                    try:
                        employee_field.setText(new_val)
                    except Exception:
                        pass

            # NEW: regenerate the PDF preview immediately
            try:
                if owner and hasattr(owner, 'send_and_update'):
                    QTimer.singleShot(0, owner.send_and_update)
            except Exception:
                pass

        popup.deleteLater()

    popup.finished.connect(finished_handler)
    popup.open()

class LiveTaskTable(QTableWidget):
    def __init__(self, parent, x, y, width, height, header_font: QFont):
        super().__init__(parent)
        self.setGeometry(x, y, width, height)
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["Employee", "Task", "Status", "Barcode"])
        self.verticalHeader().setVisible(False)
        self.setFrameShape(QTableWidget.Shape.Box)
        self.setFrameShadow(QTableWidget.Shadow.Plain)
        self.setLineWidth(1)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setShowGrid(True)
        self.setStyleSheet("""
            QTableWidget { 
                background-color: rgba(59,59,59,178); 
                color:white; 
                border:1px solid white; 
                gridline-color: white;
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
        self.horizontalHeader().setFont(header_font)

        # Adjust column widths
        col_width = width // 4
        for i in range(4):
            self.setColumnWidth(i, col_width)
            self.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        # Add search bars as first row
        self.insertRow(0)

        # --- Search Bars ---
        def make_search_box(placeholder):
            box = QLineEdit()
            box.setPlaceholderText(placeholder)
            box.setStyleSheet("""
                QLineEdit {
                    background-color: #3B3B3B;
                    color: white;
                    border: 1px solid white;
                    padding: 4px;
                    selection-background-color: #1AA0FF;
                }
            """)
            return box

        self.search_employee = make_search_box("Search employee...")
        self.search_task = make_search_box("Search task...")
        self.search_status = make_search_box("Search status...")
        self.search_barcode = make_search_box("Search barcode...")

        self.setCellWidget(0, 0, self.search_employee)
        self.setCellWidget(0, 1, self.search_task)
        self.setCellWidget(0, 2, self.search_status)
        self.setCellWidget(0, 3, self.search_barcode)

        # Connect search bars to filter
        self.search_employee.textChanged.connect(self.filter_tasks)
        self.search_task.textChanged.connect(self.filter_tasks)
        self.search_status.textChanged.connect(self.filter_tasks)
        self.search_barcode.textChanged.connect(self.filter_tasks)

        self.all_tasks = []

    def filter_tasks(self):
        """Filter tasks based on all four search bars."""
        employee_text = self.search_employee.text().strip().lower()
        task_text = self.search_task.text().strip().lower()
        status_text = self.search_status.text().strip().lower()
        barcode_text = self.search_barcode.text().strip().lower()

        for row in range(1, self.rowCount()):
            employee_item = self.item(row, 0)
            task_item = self.item(row, 1)
            status_item = self.item(row, 2)
            barcode_item = self.item(row, 3)

            employee_match = not employee_text or (employee_item and employee_text in employee_item.text().lower())
            task_match = not task_text or (task_item and task_text in task_item.text().lower())
            status_match = not status_text or (status_item and status_text in status_item.text().lower())
            barcode_match = not barcode_text or (barcode_item and barcode_text in barcode_item.text().lower())

            show_row = employee_match and task_match and status_match and barcode_match
            self.setRowHidden(row, not show_row)

    def populate_tasks(self, tasks):
        """Populate the table with task data."""
        print("\n[DEBUG] Populating LiveTaskTable with tasks:")
        for idx, row in enumerate(tasks):
            print(f"  Row {idx}: {row}")
        print(f"  → Total rows: {len(tasks)}\n")

        self.all_tasks = tasks
        self.setRowCount(1)

        if not tasks:
            self.insertRow(1)
            item = QTableWidgetItem("[NO TASKS FOUND]")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setForeground(QBrush(QColor("white")))
            self.setItem(1, 0, item)
            self.setSpan(1, 0, 1, 4)
            return

        for i, task_row in enumerate(tasks, start=1):
            if len(task_row) < 4:
                print(f"[DEBUG] Skipping malformed task row at index {i}: {task_row}")
                continue

            employee_name, live_task, status, barcode = task_row[:4]
            self.insertRow(i)

            # Helper to build cells cleanly
            def make_item(text, align_center=False):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setForeground(QBrush(QColor("white")))
                align = Qt.AlignmentFlag.AlignCenter if align_center else (Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(align)
                return item

            self.setItem(i, 0, make_item(employee_name))
            self.setItem(i, 1, make_item(live_task))
            self.setItem(i, 2, make_item(status, align_center=True))
            self.setItem(i, 3, make_item(barcode, align_center=True))


class EmployeeAssignmentTable(QTableWidget):
    def __init__(self, parent=None, width=260, height=120, header_text="Task Assignment"):
        super().__init__(parent)
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels([header_text])
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setFixedSize(width, height)
        self.on_changed = None

        # Dark styling to match app
        self.setStyleSheet(
            """
            QTableWidget { 
                background-color: rgba(59,59,59,178); 
                color:white; 
                border:1px solid white; 
                gridline-color: white;
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
            """
        )

    def _current_items_set(self):
        items = set()
        for r in range(self.rowCount()):
            it = self.item(r, 0)
            if it:
                items.add(it.text().strip().lower())
        return items

    def add_employees(self, names):
        if not names:
            return
        existing = self._current_items_set()
        for name in names:
            norm = (name or "").strip()
            if not norm:
                continue
            key = norm.lower()
            if key in existing:
                continue
            row = self.rowCount()
            self.insertRow(row)
            if callable(self.on_changed):
                self.on_changed()
            item = QTableWidgetItem(norm)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setForeground(QBrush(QColor("white")))
            self.setItem(row, 0, item)
            existing.add(key)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            sel = self.selectedItems()
            if sel:
                row = sel[0].row()
                self.removeRow(row)
                if callable(self.on_changed):
                    self.on_changed()
                return
        super().keyPressEvent(event)

class manualTaskScreen:
    def __init__(self, window, return_to_menu=None):
        self.window = window
        self.return_to_menu = return_to_menu

        # Element tracking for animations/layout mode toggles
        self.elements = []
        self.manual_ui_elements = []
        self.live_ui_elements = []
        self.orig_positions = {}

        # State
        self.current_ui_mode = "Manual Task Generation"

        self.setup_ui()

    # ---------------- UI ----------------
    def setup_ui(self):
        w, h = self.window.window_width, self.window.window_height
        padding = 10

        # Width for the task table (also used for ModeDial target width)
        table_width = int(w * 0.3)

        # ---------------- Home Button ----------------
        btn_path = resource_path("images/homeIcon.png")
        home_btn = AnimatedBarButton(btn_path, self.on_home_clicked, self.window, scale_factor=0.25)
        home_btn.move(w - home_btn.width() - padding, self.window.title_bar_height + padding)
        home_btn.show()
        self.elements.append(home_btn)

        # ---------------- Mode Dial ----------------
        self.mode_dial = ModeDial(self.window, window_width=w, height=home_btn.height(), target_width=table_width)
        self.mode_dial.move(padding, self.window.title_bar_height + padding)
        self.mode_dial.show()
        self.elements.append(self.mode_dial)

        original_next_mode = self.mode_dial.next_mode
        def next_mode_with_slide():
            old_mode = self.current_ui_mode
            original_next_mode()
            new_mode = self.mode_dial.MODES[self.mode_dial.current_index]
            self.current_ui_mode = new_mode
            QTimer.singleShot(0, lambda: self.handle_mode_change(old_mode, new_mode))
        self.mode_dial.next_mode = next_mode_with_slide

        # ---------------- Manual Task Generation UI ----------------
        y_offset = self.mode_dial.y() + self.mode_dial.height() + padding

        # Task table (left)
        table_x, table_y = padding, y_offset
        table_height = h - table_y - padding
        header_font = QFont()
        header_font.setPointSize(int(h * 0.025))
        header_font.setBold(True)

        self.task_table = TaskTable(self.window, table_x, table_y, table_width, table_height, header_font)
        self.task_table.show()
        self.elements.append(self.task_table)
        self.manual_ui_elements.append(self.task_table)
        self.orig_positions[self.task_table] = self.task_table.pos()

        # React to table changes
        try:
            self.task_table.itemChanged.connect(lambda: self.update_button_states())
            self.task_table.itemSelectionChanged.connect(lambda: self.update_button_states())
        except Exception:
            pass

        # ---------------- PDF Preview ----------------
        pdf_height = table_height
        pdf_width = int((pdf_height / 1.414) * 1.1)
        pdf_x = table_x + table_width + int(w * 0.08)
        pdf_y = table_y

        self.pdf_frame = QWidget(self.window)
        self.pdf_frame.setGeometry(pdf_x, pdf_y, pdf_width, pdf_height)
        self.pdf_frame.setStyleSheet("background-color: rgba(59,59,59,178); border: 1px solid white;")
        self.pdf_frame.show()
        self.elements.append(self.pdf_frame)
        self.manual_ui_elements.append(self.pdf_frame)
        self.orig_positions[self.pdf_frame] = self.pdf_frame.pos()

        self.page_counter_label = QLabel("Page 1 of 1", self.pdf_frame)
        self.page_counter_label.setStyleSheet("color: white; background-color: transparent;")
        self.page_counter_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.page_counter_label.setGeometry(10, 10, 150, 25)
        self.page_counter_label.show()

        preview_width = int((pdf_height / 1.414) * 0.8)
        preview_height = int(pdf_height * 0.8)
        preview_x = pdf_x + (pdf_width - preview_width) // 2
        preview_y = pdf_y + (pdf_height - preview_height) // 2

        self.pdf_preview = PDFPreview(self.window, preview_x, preview_y, preview_width, preview_height)
        self.pdf_preview.show()
        self.elements.append(self.pdf_preview)
        self.manual_ui_elements.append(self.pdf_preview)
        self.orig_positions[self.pdf_preview] = self.pdf_preview.pos()
        self.pdf_preview.page_changed = lambda: self.update_page_counter()

        # ---------------- Buttons ----------------
        # Create / Delete (between columns)
        create_btn_path = resource_path("images/addStation.png")
        create_btn = AnimatedBarButton(create_btn_path, None, self.window, scale_factor=0.25)
        create_btn.callback = lambda btn=create_btn: createNewTask(self.window, btn, self.task_table, self.elements)

        delete_btn_path = resource_path("images/binicon.png")
        self.delete_btn = AnimatedBarButton(delete_btn_path, lambda: self.delete_selected_task(), self.window, scale_factor=0.25)

        # Save (right column)
        export_btn_path = resource_path("images/save.png")
        self.export_btn = AnimatedBarButton(export_btn_path, self.export_to_pdf, self.window, scale_factor=0.25)

        # Ally (right column, top)
        ally_btn_path = resource_path("images/addEmp.png")
        self.ally_btn = AnimatedBarButton(ally_btn_path, None, self.window, scale_factor=0.25)
        self.ally_btn.callback = lambda btn=self.ally_btn: exportToAlly(
            self.window, btn, self.task_table, self.pdf_preview, self.elements,
            getattr(self, "employee_table", None),  # <-- defer lookup
            owner=self
        )

        # NEW: Activate (server posting)
        activate_btn_path = resource_path("images/sendToAlly.png")
        self.activate_btn = AnimatedBarButton(activate_btn_path, None, self.window, scale_factor=0.25)
        self.activate_btn.callback = lambda btn=self.activate_btn: self.activate_assigned_tasks()
        print("[DBG] activate_btn callback wired", flush=True)



        # Initial states
        self.export_btn.setEnabled(False)
        self.ally_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.activate_btn.setEnabled(False)

        for b in (create_btn, self.delete_btn, self.export_btn, self.ally_btn, self.activate_btn):
            b.show()

        # ---------------- Button Layout ----------------
        # geometry helpers
        table_right = self.task_table.x() + self.task_table.width()
        pdf_left = self.pdf_frame.x()
        gap_between_table_pdf = pdf_left - table_right
        vertical_gap = 20

        # ensure we have real widths (sizeHint fallback if needed)
        def _btn_size(btn):
            w, h = btn.width(), btn.height()
            if not w or not h:
                sh = btn.sizeHint()
                return sh.width(), sh.height()
            return w, h

        cr_w, cr_h = _btn_size(create_btn)
        dl_w, dl_h = _btn_size(self.delete_btn)
        al_w, al_h = _btn_size(self.ally_btn)
        ac_w, ac_h = _btn_size(self.activate_btn)
        sv_w, sv_h = _btn_size(self.export_btn)

        # use the widest button to center the column nicely
        max_w = max(cr_w, dl_w, al_w, ac_w, sv_w)

        # compute the common X so the column is horizontally centered in the gap
        middle_x = table_right + (gap_between_table_pdf - max_w) // 2

        # starting Y aligned with top of the task table
        y = self.task_table.y()

        # 1) Create
        create_btn.move(middle_x, y)
        create_btn.orig_x, create_btn.orig_y = create_btn.x(), create_btn.y()
        if create_btn not in self.elements: self.elements.append(create_btn)
        if create_btn not in self.manual_ui_elements: self.manual_ui_elements.append(create_btn)
        self.orig_positions[create_btn] = create_btn.pos()

        # 2) Delete
        y += cr_h + vertical_gap
        self.delete_btn.move(middle_x, y)
        self.delete_btn.orig_x, self.delete_btn.orig_y = self.delete_btn.x(), self.delete_btn.y()
        if self.delete_btn not in self.elements: self.elements.append(self.delete_btn)
        if self.delete_btn not in self.manual_ui_elements: self.manual_ui_elements.append(self.delete_btn)
        self.orig_positions[self.delete_btn] = self.delete_btn.pos()

        # 3) Ally
        ally_x = middle_x
        y += dl_h + vertical_gap
        self.ally_btn.move(middle_x, y)
        self.ally_btn.orig_x, self.ally_btn.orig_y = self.ally_btn.x(), self.ally_btn.y()
        if self.ally_btn not in self.elements: self.elements.append(self.ally_btn)
        if self.ally_btn not in self.manual_ui_elements: self.manual_ui_elements.append(self.ally_btn)
        self.orig_positions[self.ally_btn] = self.ally_btn.pos()

        # 4) Activate
        y += al_h + vertical_gap
        self.activate_btn.move(middle_x, y)
        self.activate_btn.orig_x, self.activate_btn.orig_y = self.activate_btn.x(), self.activate_btn.y()
        if self.activate_btn not in self.elements: self.elements.append(self.activate_btn)
        if self.activate_btn not in self.manual_ui_elements: self.manual_ui_elements.append(self.activate_btn)
        self.orig_positions[self.activate_btn] = self.activate_btn.pos()

        # 5) Save
        y += ac_h + vertical_gap
        self.export_btn.move(middle_x, y)
        self.export_btn.orig_x, self.export_btn.orig_y = self.export_btn.x(), self.export_btn.y()
        if self.export_btn not in self.elements: self.elements.append(self.export_btn)
        if self.export_btn not in self.manual_ui_elements: self.manual_ui_elements.append(self.export_btn)
        self.orig_positions[self.export_btn] = self.export_btn.pos()

        # ===== Assigned table to the RIGHT of the button column; PDF shifts further right =====
        side_gap = 16

        assign_x = middle_x + max_w + side_gap        # immediately to the right of the buttons
        assign_y = self.task_table.y()                # top edge aligned with Create

        # Fill down to the same bottom as the task table
        bottom_target = table_y + table_height
        table_width_px  = max(260, int(w * 0.16))     # sane width; adjust if you like
        table_height_px = max(80, bottom_target - assign_y)

        # Create / move the assignment table
        if hasattr(self, "employee_table") and self.employee_table is not None:
            self.employee_table.setFixedSize(table_width_px, table_height_px)
            self.employee_table.move(assign_x, assign_y)
        else:
            self.employee_table = EmployeeAssignmentTable(
                self.window, width=table_width_px, height=table_height_px, header_text="Task Assignment"
            )
            self.employee_table.move(assign_x, assign_y)
            self.employee_table.show()
            self.elements.append(self.employee_table)
            self.manual_ui_elements.append(self.employee_table)

        self.orig_positions[self.employee_table] = self.employee_table.pos()
        self.employee_table.on_changed = self.update_button_states

        # ---- Shift the PDF frame & preview further right to make room ----
        new_pdf_x = assign_x + table_width_px + side_gap
        pdf_y     = self.pdf_frame.y()     # unchanged
        pdf_w     = self.pdf_frame.width() # keep same width/height
        pdf_h     = self.pdf_frame.height()

        self.pdf_frame.move(new_pdf_x, pdf_y)
        self.orig_positions[self.pdf_frame] = self.pdf_frame.pos()

        # Re-center the PDFPreview within the moved frame
        prev_w, prev_h = self.pdf_preview.width(), self.pdf_preview.height()
        new_prev_x = self.pdf_frame.x() + (pdf_w - prev_w) // 2
        new_prev_y = self.pdf_frame.y() + (pdf_h - prev_h) // 2
        self.pdf_preview.move(new_prev_x, new_prev_y)
        self.orig_positions[self.pdf_preview] = self.pdf_preview.pos()

        vertical_gap = 20

        # 1) Compute intrinsic widths
        def _btn_size(btn):
            w_, h_ = btn.width(), btn.height()
            if not w_ or not h_:
                sh = btn.sizeHint()
                return sh.width(), sh.height()
            return w_, h_

        # Buttons column width = widest button
        cr_w, cr_h = _btn_size(create_btn)
        dl_w, dl_h = _btn_size(self.delete_btn)
        al_w, al_h = _btn_size(self.ally_btn)
        ac_w, ac_h = _btn_size(self.activate_btn)
        sv_w, sv_h = _btn_size(self.export_btn)
        buttons_col_w = max(cr_w, dl_w, al_w, ac_w, sv_w)

        # Assigned table target width (keep your previous choice / scale with window)
        assigned_w = max(260, int(w * 0.16))

        # PDF frame keeps its existing size; we’ll only move it
        pdf_w, pdf_h = self.pdf_frame.width(), self.pdf_frame.height()

        # 2) Solve equal gap G across the 4 columns
        # layout: [padding] TaskTable [G] Buttons [G] Assigned [G] PDF [padding]
        usable = w - 2 * padding
        total_fixed = table_width + buttons_col_w + assigned_w + pdf_w
        G = max(8, int((usable - total_fixed) / 3*0.6))  # >= 8px minimum gap

        # 3) Compute left edges for each column
        x_task     = table_x  # already padding-aligned
        x_buttons  = x_task + table_width + G
        x_assign   = x_buttons + buttons_col_w + G
        x_pdf      = x_assign + assigned_w + G

        # 4) Place the BUTTONS as a vertical stack at x_buttons (top aligned to task table)
        y = table_y
        create_btn.move(x_buttons, y)
        create_btn.orig_x, create_btn.orig_y = create_btn.x(), create_btn.y()
        self.orig_positions[create_btn] = create_btn.pos()
        if create_btn not in self.elements: self.elements.append(create_btn)
        if create_btn not in self.manual_ui_elements: self.manual_ui_elements.append(create_btn)

        y += cr_h + vertical_gap
        self.delete_btn.move(x_buttons, y)
        self.delete_btn.orig_x, self.delete_btn.orig_y = self.delete_btn.x(), self.delete_btn.y()
        self.orig_positions[self.delete_btn] = self.delete_btn.pos()
        if self.delete_btn not in self.elements: self.elements.append(self.delete_btn)
        if self.delete_btn not in self.manual_ui_elements: self.manual_ui_elements.append(self.delete_btn)

        y += dl_h + vertical_gap
        self.ally_btn.move(x_buttons, y)
        self.ally_btn.orig_x, self.ally_btn.orig_y = self.ally_btn.x(), self.ally_btn.y()
        self.orig_positions[self.ally_btn] = self.ally_btn.pos()
        if self.ally_btn not in self.elements: self.elements.append(self.ally_btn)
        if self.ally_btn not in self.manual_ui_elements: self.manual_ui_elements.append(self.ally_btn)

        y += al_h + vertical_gap
        self.activate_btn.move(x_buttons, y)
        self.activate_btn.orig_x, self.activate_btn.orig_y = self.activate_btn.x(), self.activate_btn.y()
        self.orig_positions[self.activate_btn] = self.activate_btn.pos()
        if self.activate_btn not in self.elements: self.elements.append(self.activate_btn)
        if self.activate_btn not in self.manual_ui_elements: self.manual_ui_elements.append(self.activate_btn)

        y += ac_h + vertical_gap
        self.export_btn.move(x_buttons, y)
        self.export_btn.orig_x, self.export_btn.orig_y = self.export_btn.x(), self.export_btn.y()
        self.orig_positions[self.export_btn] = self.export_btn.pos()
        if self.export_btn not in self.elements: self.elements.append(self.export_btn)
        if self.export_btn not in self.manual_ui_elements: self.manual_ui_elements.append(self.export_btn)

        # 5) Assigned table to the RIGHT of buttons, top aligned with Create
        assign_y = table_y
        assigned_h = max(80, (table_y + table_height) - assign_y)  # bottom-align with task table
        if hasattr(self, "employee_table") and self.employee_table is not None:
            self.employee_table.setFixedSize(assigned_w, assigned_h)
            self.employee_table.move(x_assign, assign_y)
        else:
            self.employee_table = EmployeeAssignmentTable(
                self.window, width=assigned_w, height=assigned_h, header_text="Task Assignment"
            )
            self.employee_table.move(x_assign, assign_y)
            self.employee_table.show()
            self.elements.append(self.employee_table)
            self.manual_ui_elements.append(self.employee_table)
        self.orig_positions[self.employee_table] = self.employee_table.pos()

        # 6) Shift the PDF frame to x_pdf (size unchanged)
        self.pdf_frame.move(x_pdf, self.pdf_frame.y())
        self.orig_positions[self.pdf_frame] = self.pdf_frame.pos()

        # Re-center the PDFPreview within the moved frame (keeping its size)
        prev_w, prev_h = self.pdf_preview.width(), self.pdf_preview.height()
        new_prev_x = self.pdf_frame.x() + (pdf_w - prev_w) // 2
        new_prev_y = self.pdf_frame.y() + (pdf_h - prev_h) // 2
        self.pdf_preview.move(new_prev_x, new_prev_y)
        self.orig_positions[self.pdf_preview] = self.pdf_preview.pos()


        # Final state sync & live view init
        self.update_button_states()
        self.create_live_tasks_table()
        QTimer.singleShot(0, self.populate_live_tasks)

    from PyQt6.QtCore import QTimer

    def show_tasks_live_popup(self):
        def do_show():
            if hasattr(self, "elements"):
                set_screen_opacity(self.elements, 0.3)

            popup = LiveSuccessPopup(self.window, message="Your Tasks are now Live!")

            def finished_handler(code):
                if hasattr(self, "elements"):
                    set_screen_opacity(self.elements, 1.0)
                if self.window:
                    try:
                        self.window.activateWindow()
                        self.window.raise_()
                    except Exception:
                        pass
                popup.deleteLater()

            popup.finished.connect(finished_handler)
            popup.open()

        # This queues it safely on the GUI thread even if you call it from a worker
        QTimer.singleShot(0, do_show)





    def update_button_states(self):
        """Enable/disable buttons based on table and preview state."""
        # Any non-zero value in the Barcodes column?
        has_barcodes_in_table = False
        for row in range(self.task_table.rowCount()):
            it = self.task_table.item(row, 2)  # Barcodes column
            if it:
                try:
                    if int(it.text()) > 0:
                        has_barcodes_in_table = True
                        break
                except ValueError:
                    continue

        has_preview_labels = len(self.pdf_preview.labels) > 0
        has_task_selected = bool(self.task_table.selectedItems())

        # Ally (UI-only) – leave as you had it; requires preview labels
        self.ally_btn.setEnabled(has_barcodes_in_table)

        # Delete requires a selected row
        self.delete_btn.setEnabled(has_task_selected)

        # NEW: Activate (server posting) requires assignees + labels
        try:
            has_assignees = hasattr(self, "employee_table") and self.employee_table.rowCount() > 0
        except Exception:
            has_assignees = False
        self.activate_btn.setEnabled(has_assignees and has_preview_labels)

        self.task_table.setEnabled(not has_assignees)


    def send_and_update(self):
        try:
            multiplier = max(1, getattr(self, "employee_table", None).rowCount())
        except Exception:
            multiplier = 1

        sendFormat(self.get_table_data(), self.pdf_preview, employee_multiplier=multiplier)
        self.update_page_counter()
        self.pdf_preview.setFocus()
        # Update button states after generating preview
        self.update_button_states()


    def handle_mode_change(self, old_mode, new_mode):
        """Handle sliding animations between modes."""
        slide_distance = self.window.window_width + 50
        animations = []

        if old_mode == new_mode:
            return

        # Manual → Live Ally Tasks
        if new_mode == "Live Ally Tasks":
            
            for elem in self.manual_ui_elements:
                anim = QPropertyAnimation(elem, b"pos")
                anim.setDuration(300)
                anim.setStartValue(elem.pos())
                anim.setEndValue(QPoint(self.orig_positions[elem].x() + slide_distance, elem.y()))
                anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
                anim.start()
                animations.append(anim)

            for elem in self.live_ui_elements:
                anim = QPropertyAnimation(elem, b"pos")
                anim.setDuration(300)
                anim.setStartValue(elem.pos())
                anim.setEndValue(self.orig_positions[elem])
                anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
                anim.start()
                animations.append(anim)

        # Live Ally Tasks → Manual
        else:
            for elem in self.manual_ui_elements:
                anim = QPropertyAnimation(elem, b"pos")
                anim.setDuration(300)
                anim.setStartValue(elem.pos())
                anim.setEndValue(self.orig_positions[elem])
                anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
                anim.start()
                animations.append(anim)

            for elem in self.live_ui_elements:
                anim = QPropertyAnimation(elem, b"pos")
                anim.setDuration(300)
                anim.setStartValue(elem.pos())
                anim.setEndValue(QPoint(-elem.width() - 50, elem.y()))
                anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
                anim.start()
                animations.append(anim)

        self._mode_animations = animations

    def delete_selected_task(self):
        task_name = self.task_table.get_selected_task()
        if not task_name:
            return

        def run_delete():
            response = edit_tasks(taskName=task_name, editFlag=False, debug=False)
            if response.get("status") == "success":
                # Remove row from table
                row = self.task_table.currentRow()
                self.task_table.removeRow(row)
            else:
                print(f"Failed to delete task '{task_name}': {response.get('message')}")

        threading.Thread(target=run_delete).start()

    def get_table_data(self):
        data = []
        rows = self.task_table.rowCount()
        cols = self.task_table.columnCount()

        for r in range(rows):
            row_data = []
            for c in range(cols):
                item = self.task_table.item(r, c)
                row_data.append(item.text() if item else "")
            data.append(row_data)
        return data


    # --- Activate button callback target: ships tasks to server safely ---
    def activate_assigned_tasks(self):
        """
        Send each employee their portion of tasks, using the actual barcodes
        generated in the PDF preview (in order by task label).
        Each employee gets a unique subset per task type.
        """
        from collections import defaultdict
        from clientCalls import update_employee_task
        import threading

        # 1) Gather employees
        employees = []
        if hasattr(self, "employee_table") and self.employee_table is not None:
            for row in range(self.employee_table.rowCount()):
                item = self.employee_table.item(row, 0)
                if item and item.text().strip():
                    employees.append(item.text().strip())

        if not employees:
            print("❌ No assigned employees found in table.")
            return

        # 2) Build mapping of {task_label: [barcodes]} from pdf_preview
        labels = getattr(self.pdf_preview, "labels", [])
        if not labels:
            print("❌ No labels found in PDF preview.")
            return

        task_barcodes = defaultdict(list)

        # Use the same starting number as the PDF preview
        start_num = 0
        if hasattr(self.pdf_preview, "startCode") and str(self.pdf_preview.startCode).startswith("m"):
            try:
                start_num = int(self.pdf_preview.startCode[1:])
            except ValueError:
                start_num = 0

        print(f"[DEBUG] Using barcode start number: {start_num}")

        # Generate barcodes exactly as the PDF preview did
        for global_idx, label in enumerate(labels):
            bc_num = start_num + global_idx
            bc = f"m{bc_num:010d}"
            task_barcodes[label].append(bc)


        # 3) Build list of tasks from table (label + count)
        tasks = []
        for row in range(1, self.task_table.rowCount()):
            task_item = self.task_table.item(row, 0)
            qty_item = self.task_table.item(row, 1)
            bc_item = self.task_table.item(row, 2)
            if not task_item:
                continue
            try:
                task_name = task_item.text().strip()
                qty = int(qty_item.text()) if qty_item else 0
                count = int(bc_item.text()) if bc_item else 0
            except Exception:
                continue
            if count <= 0:
                continue
            label = f"{task_name} x {qty}"
            tasks.append((label, count))

        self.show_tasks_live_popup()
        if not tasks:
            print("❌ No valid tasks found in table.")
            return

        # 4) Distribute barcodes for each task among employees
        def run_post_all():
            for emp in employees:
                print(f"\n🚀 Sending tasks to {emp}...")
                success = fail = 0
                for label, count in tasks:
                    barcodes_for_task = task_barcodes.get(label, [])
                    if not barcodes_for_task:
                        print(f"⚠️ No barcodes found for {label}.")
                        continue

                    # Divide barcodes evenly per employee
                    per_emp = max(1, len(barcodes_for_task) // len(employees))
                    start_idx = employees.index(emp) * per_emp
                    end_idx = start_idx + per_emp
                    if emp == employees[-1]:
                        # last one gets leftovers
                        end_idx = len(barcodes_for_task)

                    allocated = barcodes_for_task[start_idx:end_idx]
                    for bc in allocated:
                        try:
                            resp = update_employee_task(
                                employeeName=emp,
                                liveTask=label,
                                status="Pending",
                                isobarcode=bc,
                                erase=False
                            )
                            if resp.get("status") == "success":
                                success += 1
                                print(f"✅ {emp}: {label} | Barcode: {bc}")
                            else:
                                fail += 1
                                print(f"❌ {emp}: {label} | {resp.get('message')}")
                        except Exception as e:
                            fail += 1
                            print(f"⚠️ Error sending {label} to {emp}: {e}")

                print(f"📊 Summary for {emp}: {success} success, {fail} failed\n")

            # === FINAL UI STATE CHANGES ===
            print("🔒 Deactivating employee table and Ally button; enabling Save.")
            self.employee_table.setEnabled(False)
            self.ally_btn.setEnabled(False)
            self.export_btn.setEnabled(True)
            self.show_tasks_live_popup()

        threading.Thread(target=run_post_all).start()

    def update_page_counter(self):
        """Update the page counter label."""
        current = self.pdf_preview.current_page + 1
        total = self.pdf_preview.total_pages
        self.page_counter_label.setText(f"Page {current} of {total}")

    def export_to_pdf(self):
        """Export the preview to a printable PDF file."""
        if not self.pdf_preview.labels:
            print("[WARNING] No labels to export")
            return

        # Open file dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Export PDF",
            "manual_tasks.pdf",
            "PDF Files (*.pdf)"
        )

        if not file_path:
            return  # User cancelled

        try:
            # Create printer
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file_path)
            
            # Import QPageSize for PyQt6
            from PyQt6.QtGui import QPageSize
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)

            # Create painter
            painter = QPainter()
            if not painter.begin(printer):
                print("[ERROR] Failed to create painter")
                return

            # Get page dimensions
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            page_width = page_rect.width()
            page_height = page_rect.height()

            # Render each page
            for page_num in range(self.pdf_preview.total_pages):
                if page_num > 0:
                    printer.newPage()  # Start new page for all but first
                
                self.pdf_preview.render_page_to_painter(painter, page_num, page_width, page_height)

            painter.end()
            print(f"[SUCCESS] PDF exported to: {file_path}")

        except Exception as e:
            print(f"[ERROR] Failed to export PDF: {e}")
            import traceback
            traceback.print_exc()

    def update_live_delete_button(self):
        """Enable/disable live delete button based on selection."""
        has_selection = bool(self.live_tasks_table.selectedItems())
        self.live_delete_btn.setEnabled(has_selection)

    def delete_live_task(self):
        """Delete the selected live task."""
        selected_items = self.live_tasks_table.selectedItems()
        if not selected_items:
            return
        
        # Get the selected row (skip row 0 which is search bars)
        row = selected_items[0].row()
        if row == 0:
            return
        
        # Get task details from the row
        employee_item = self.live_tasks_table.item(row, 0)
        task_item = self.live_tasks_table.item(row, 1)
        
        if not employee_item or not task_item:
            return
        
        employee_name = employee_item.text()
        live_task = task_item.text()
    
        
        def run_delete():
            from clientCalls import update_employee_task
            
            # Call with erase=True to delete - but wait, we need to update the endpoint!
            # The current endpoint deletes ALL tasks for an employee when erase=True
            # We need a different approach...
            
            response = update_employee_task(
                employeeName=employee_name,
                liveTask=live_task,
                status=None,
                erase=True
            )
            
            if response.get("status") == "success":
                print(f"✅ Deleted: {employee_name} - {live_task}")
                # Refresh the table to reflect changes
                self.populate_live_tasks()
            else:
                print(f"❌ Failed to delete: {response.get('message')}")
        
        threading.Thread(target=run_delete).start()

    def create_live_tasks_table(self):
        """Create the live ally tasks table (initially off-screen to the left)."""
        w, h = self.window.window_width, self.window.window_height
        padding = 10
        
        # Width: 80% of window
        table_width = int(w * 0.8)
        
        # Match manual task table's y position and height
        y_offset = self.task_table.y()
        table_height = self.task_table.height()
        
        # On-screen x position: same as manual task table
        table_x = self.task_table.x()
        
        # Initial off-screen position (to the LEFT)
        initial_x = -table_width - 50
        
        header_font = QFont()
        header_font.setPointSize(int(h * 0.025))
        header_font.setBold(True)
        
        # Create table using the class
        self.live_tasks_table = LiveTaskTable(
            self.window,
            initial_x,
            y_offset,
            table_width,
            table_height,
            header_font
        )
        
        self.live_tasks_table.show()
        self.elements.append(self.live_tasks_table)
        self.live_ui_elements.append(self.live_tasks_table)
        
        # Store original on-screen position
        self.orig_positions[self.live_tasks_table] = QPoint(table_x, y_offset)
        
        # ---------------- Refresh Button ----------------
        refresh_btn_path = resource_path("images/refresh.png")
        self.refresh_btn = AnimatedBarButton(
            refresh_btn_path,
            self.populate_live_tasks,  # Call refresh when clicked
            self.window,
            scale_factor=0.25
        )
        
        # Calculate position: to the right of table with padding
        # Use same padding as manual task generation buttons
        horizontal_gap = int((self.window.window_width - table_width) * 0.05)  # matches your manual mode spacing
        refresh_x = table_x + table_width + horizontal_gap
        refresh_y = y_offset  # Top edge matches table top edge
        
        # Initial off-screen position (to the LEFT, same as table)
        refresh_initial_x = refresh_x - self.window.window_width - 50
        
        self.refresh_btn.move(refresh_initial_x, refresh_y)
        self.refresh_btn.orig_x = refresh_x
        self.refresh_btn.orig_y = refresh_y
        self.refresh_btn.show()
        
        self.elements.append(self.refresh_btn)
        self.live_ui_elements.append(self.refresh_btn)
        
        # Store original on-screen position
        self.orig_positions[self.refresh_btn] = QPoint(refresh_x, refresh_y)

        # ---------------- Delete Button ----------------
        delete_btn_path = resource_path("images/binicon.png")
        self.live_delete_btn = AnimatedBarButton(
            delete_btn_path,
            self.delete_live_task,
            self.window,
            scale_factor=0.25
        )
        
        # Position: below refresh button with vertical gap
        vertical_gap = 20  # Same as manual task generation
        delete_x = refresh_x
        delete_y = refresh_y + self.refresh_btn.height() + vertical_gap
        
        # Initial off-screen position (to the LEFT)
        delete_initial_x = delete_x - self.window.window_width - 50
        
        self.live_delete_btn.move(delete_initial_x, delete_y)
        self.live_delete_btn.orig_x = delete_x
        self.live_delete_btn.orig_y = delete_y
        self.live_delete_btn.setEnabled(False)  # Initially disabled
        self.live_delete_btn.show()
        
        self.elements.append(self.live_delete_btn)
        self.live_ui_elements.append(self.live_delete_btn)
        
        # Store original on-screen position
        self.orig_positions[self.live_delete_btn] = QPoint(delete_x, delete_y)
        
        # Connect selection change to update button state
        self.live_tasks_table.itemSelectionChanged.connect(self.update_live_delete_button)

    def populate_live_tasks(self):
        """Fetch and populate the live tasks table.""" 
        def run_fetch():
            try:
                tasks = fetch_employees_tasks()
                # Use the class method to populate
                self.live_tasks_table.populate_tasks(tasks)
            except Exception as e:
                print(f"[ERROR] Failed to fetch live tasks: {e}")
        
        threading.Thread(target=run_fetch).start()

    def on_home_clicked(self):
        if callable(self.return_to_menu):
            self.return_to_menu()

    def cleanup(self):
        for elem in self.elements:
            elem.setParent(None)
            elem.deleteLater()
        self.elements.clear()
        self.manual_ui_elements.clear()  # ADD THIS
        self.live_ui_elements.clear()    # ADD THIS
        self.orig_positions.clear()      # ADD THIS
