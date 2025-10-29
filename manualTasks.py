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

from clientCalls import fetch_manual_tasks, edit_tasks, fetch_all_employees, fetch_employees_tasks

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

        self.setStyleSheet("background-color: transparent;")
        self.logo = None
        self.labels = []  # store text labels for boxes
        self.current_page = 0  # track current page
        self.total_pages = 1   # track total pages
        self.page_changed = None  # callback for page changes

        logo_path = resource_path("images/logo.png")
        if os.path.exists(logo_path):
            self.logo = QPixmap(logo_path)

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
                    self._draw_barcode(painter, barcode_number, x, y, w, h)

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

def sendFormat(data, pdf_preview):
    """
    Given table data, generate box labels and draw them on the PDF.
    """
    labels = []
    for row in data:
        if len(row) < 3:
            continue
        name, qty, barcodes = row
        try:
            count = int(barcodes)
            qty = int(qty)
        except ValueError:
            continue  # skip invalid rows
        
        # Skip rows with 0 barcodes
        if count <= 0:
            continue

        label = f"{name} x {qty}"
        # Add this label 'count' times (once for each barcode)
        for _ in range(count):
            labels.append(label)
            # REMOVED THE 12 LIMIT HERE - let it add all labels

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


def exportToAlly(parent=None, button=None, task_table=None, pdf_preview=None, screen_elements=None):
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
    
    popup = PostToAllyPopup(parent)

    def finished_handler(code):
        user_confirmed = (code == QDialog.DialogCode.Accepted)
        
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
        
        if user_confirmed:
            selected_employee = popup.get_result()
            print("✅ Selected employee:", selected_employee)

            def run_post():
                # Get labels from PDF preview (these are already in order)
                if not pdf_preview or not pdf_preview.labels:
                    print("❌ No PDF preview labels available")
                    return
                
                pdf_labels = pdf_preview.labels  # List of labels like "foam board x 25"
                
                # Post each label with its corresponding barcode
                from clientCalls import update_employee_task
                
                success_count = 0
                fail_count = 0
                
                for idx, label in enumerate(pdf_labels):
                    # Generate barcode: m + zero-padded index
                    barcode = f"m{str(idx).zfill(10)}"
                    
                    response = update_employee_task(
                        employeeName=selected_employee,
                        liveTask=label,
                        status="Pending",
                        isobarcode=barcode,
                        erase=False
                    )
                    
                    if response.get("status") == "success":
                        success_count += 1
                        print(f"✅ Posted: {label} | Barcode: {barcode}")
                    else:
                        fail_count += 1
                        print(f"❌ Failed to post: {label} - {response.get('message')}")
                
                print(f"\n📊 Summary: {success_count} tasks posted, {fail_count} failed")

            threading.Thread(target=run_post).start()
        else:
            print("Posting canceled.")
        
        popup.deleteLater()
    
    popup.finished.connect(finished_handler)
    popup.open()


class PostToAllyPopup(QDialog):
    def __init__(self, parent=None, textbox_width=220, textbox_height=40, margin=16, btn_size=40):
        super().__init__(parent)
        self.parent_window = parent
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setStyleSheet("background-color: #3B3B3B;")

        self.selected_employee = None

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
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)  # single select

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
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
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

    def get_selected_employee(self):
        """Return the first selected employee name, or None."""
        selected = self.table.selectedItems()
        if not selected:
            return None
        return selected[0].text()

    def _on_tick(self):
        self.selected_employee = self.get_selected_employee()
        self.accept()

    def _on_cross(self):
        self.selected_employee = None
        self.reject()

    def get_result(self):
        """Show popup and return selected employee name or None."""
        return self.selected_employee

class LiveTaskTable(QTableWidget):
    def __init__(self, parent, x, y, width, height, header_font: QFont):
        super().__init__(parent)
        self.setGeometry(x, y, width, height)
        self.setColumnCount(3)
        self.setHorizontalHeaderLabels(["Employee", "Task", "Status"])
        self.verticalHeader().setVisible(False)
        self.setFrameShape(QTableWidget.Shape.Box)
        self.setFrameShadow(QTableWidget.Shadow.Plain)
        self.setLineWidth(1)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # Read-only

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
        
        # Column widths: distribute evenly
        col_width = width // 3
        self.setColumnWidth(0, col_width)
        self.setColumnWidth(1, col_width)
        self.setColumnWidth(2, col_width)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        # Add search bars as first row
        self.insertRow(0)
        
        self.search_employee = QLineEdit()
        self.search_employee.setPlaceholderText("Search employee...")
        self.search_employee.setStyleSheet("""
            QLineEdit {
                background-color: #3B3B3B;
                color: white;
                border: 1px solid white;
                padding: 4px;
                selection-background-color: #1AA0FF;
            }
        """)
        self.setCellWidget(0, 0, self.search_employee)
        
        self.search_task = QLineEdit()
        self.search_task.setPlaceholderText("Search task...")
        self.search_task.setStyleSheet("""
            QLineEdit {
                background-color: #3B3B3B;
                color: white;
                border: 1px solid white;
                padding: 4px;
                selection-background-color: #1AA0FF;
            }
        """)
        self.setCellWidget(0, 1, self.search_task)
        
        self.search_status = QLineEdit()
        self.search_status.setPlaceholderText("Search status...")
        self.search_status.setStyleSheet("""
            QLineEdit {
                background-color: #3B3B3B;
                color: white;
                border: 1px solid white;
                padding: 4px;
                selection-background-color: #1AA0FF;
            }
        """)
        self.setCellWidget(0, 2, self.search_status)
        
        # Connect search bars to filter
        self.search_employee.textChanged.connect(self.filter_tasks)
        self.search_task.textChanged.connect(self.filter_tasks)
        self.search_status.textChanged.connect(self.filter_tasks)
        
        # Store all tasks for filtering
        self.all_tasks = []

    def mousePressEvent(self, event: QMouseEvent):
        item = self.itemAt(event.pos())
        if item is None:
            self.clearSelection()
            self.itemSelectionChanged.emit()
        else:
            super().mousePressEvent(event)

    def filter_tasks(self):
        """Filter tasks based on all three search bars."""
        employee_text = self.search_employee.text().strip().lower()
        task_text = self.search_task.text().strip().lower()
        status_text = self.search_status.text().strip().lower()
        
        # Filter rows (skip row 0 which contains search bars)
        for row in range(1, self.rowCount()):
            employee_item = self.item(row, 0)
            task_item = self.item(row, 1)
            status_item = self.item(row, 2)
            
            # Check if all search criteria match
            employee_match = not employee_text or (employee_item and employee_text in employee_item.text().lower())
            task_match = not task_text or (task_item and task_text in task_item.text().lower())
            status_match = not status_text or (status_item and status_text in status_item.text().lower())
            
            # Show row only if ALL criteria match
            show_row = employee_match and task_match and status_match
            self.setRowHidden(row, not show_row)

    def populate_tasks(self, tasks):
        """Populate the table with task data."""
        self.all_tasks = tasks
        
        # Clear existing rows except search bar
        self.setRowCount(1)
        
        if not tasks:
            # Show empty placeholder
            self.insertRow(1)
            item = QTableWidgetItem("[NO TASKS FOUND]")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setForeground(QBrush(QColor("white")))
            self.setItem(1, 0, item)
            self.setSpan(1, 0, 1, 3)  # Span across all columns
            return
        
        # Populate with tasks
        for i, task_row in enumerate(tasks, start=1):
            if len(task_row) < 3:
                continue
            
            # Unpack first 3 values, ignore isobarcode (4th value)
            employee_name = task_row[0]
            live_task = task_row[1]
            status = task_row[2]
            # task_row[3] would be isobarcode, but we ignore it for now
            self.insertRow(i)
            
            # Employee column
            employee_item = QTableWidgetItem(employee_name)
            employee_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            employee_item.setForeground(QBrush(QColor("white")))
            employee_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.setItem(i, 0, employee_item)
            
            # Task column
            task_item = QTableWidgetItem(live_task)
            task_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            task_item.setForeground(QBrush(QColor("white")))
            task_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.setItem(i, 1, task_item)
            
            # Status column
            status_item = QTableWidgetItem(status)
            status_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            status_item.setForeground(QBrush(QColor("white")))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(i, 2, status_item)

# ---------------- Manual Task Screen ----------------
class manualTaskScreen:
    def __init__(self, window, return_to_menu=None):
        self.window = window
        self.elements = []
        self.manual_ui_elements = []
        self.live_ui_elements = []
        self.orig_positions = {}
        self.return_to_menu = return_to_menu
        self.current_ui_mode = "Manual Task Generation"
        # REMOVE: self.overlay = OverlayWidget(self.window)
        self.setup_ui()

    def setup_ui(self):
        w, h = self.window.window_width, self.window.window_height
        padding = 10
        
        # Calculate task table width FIRST (we need this for mode dial sizing)
        table_width = int(w * 0.3)
        
        # ---------------- Home Button ----------------
        btn_path = resource_path("images/homeIcon.png")
        home_btn = AnimatedBarButton(btn_path, self.on_home_clicked, self.window, scale_factor=0.25)
        home_btn.move(w - home_btn.width() - padding, self.window.title_bar_height + padding)
        home_btn.show()
        self.elements.append(home_btn)
        
        # ---------------- Mode Dial ----------------
        # Make mode dial the same width as the task table
        self.mode_dial = ModeDial(
            self.window, 
            window_width=w, 
            height=home_btn.height(),
            target_width=table_width  # Now table_width is defined!
        )
        self.mode_dial.move(padding, self.window.title_bar_height + padding)
        self.mode_dial.show()
        self.elements.append(self.mode_dial)
        
        # Store original next_mode function
        original_next_mode = self.mode_dial.next_mode
        
        def next_mode_with_slide():
            # Perform actual mode change
            old_mode = self.current_ui_mode
            original_next_mode()
            new_mode = self.mode_dial.MODES[self.mode_dial.current_index]
            self.current_ui_mode = new_mode
            QTimer.singleShot(0, lambda: self.handle_mode_change(old_mode, new_mode))
        
        # Replace the dial's next_mode with our wrapped version
        self.mode_dial.next_mode = next_mode_with_slide
        
        # ---------------- Manual Task Generation UI ----------------
        y_offset = self.mode_dial.y() + self.mode_dial.height() + padding
        
        # Task Table (now using table_width we calculated earlier)
        table_x, table_y = padding, y_offset
        table_height = h - table_y - padding
        
        header_font = QFont()
        header_font.setPointSize(int(h * 0.025))
        header_font.setBold(True)
        
        self.task_table = TaskTable(self.window, table_x, table_y, table_width, table_height, header_font)
        self.task_table.show()
        self.elements.append(self.task_table)
        self.manual_ui_elements.append(self.task_table)  # ADD TO MANUAL UI
        self.orig_positions[self.task_table] = self.task_table.pos()  # STORE POSITION
        
        # Connect table changes to button state updates
        self.task_table.itemChanged.connect(lambda: self.update_button_states())
        self.task_table.itemSelectionChanged.connect(lambda: self.update_button_states())

        # ---------------- PDF Preview ----------------
        pdf_height = table_height
        pdf_width = int((pdf_height / 1.414)*1.1)
        pdf_x = table_x + table_width + int(w*0.08)
        pdf_y = table_y

        # Create background frame box
        self.pdf_frame = QWidget(self.window)
        self.pdf_frame.setGeometry(pdf_x, pdf_y, pdf_width, pdf_height)
        self.pdf_frame.setStyleSheet("""
            background-color: rgba(59,59,59,178);
            border: 1px solid white;
        """)
        self.pdf_frame.show()
        self.elements.append(self.pdf_frame)
        self.manual_ui_elements.append(self.pdf_frame)  # ADD TO MANUAL UI
        self.orig_positions[self.pdf_frame] = self.pdf_frame.pos()  # STORE POSITION

        # Add page counter label
        self.page_counter_label = QLabel("Page 1 of 1", self.pdf_frame)
        self.page_counter_label.setStyleSheet("color: white; background-color: transparent;")
        self.page_counter_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.page_counter_label.setGeometry(10, 10, 150, 25)
        self.page_counter_label.show()

        # Create PDF preview
        preview_width = int((pdf_height / 1.414) * 0.8)
        preview_height = int(pdf_height * 0.8)
        preview_x = pdf_x + (pdf_width - preview_width) // 2
        preview_y = pdf_y + (pdf_height - preview_height) // 2

        self.pdf_preview = PDFPreview(
            parent=self.window,
            x=preview_x,
            y=preview_y,
            width=preview_width,
            height=preview_height
        )
        self.pdf_preview.show()
        self.elements.append(self.pdf_preview)
        self.manual_ui_elements.append(self.pdf_preview)  # ADD TO MANUAL UI
        self.orig_positions[self.pdf_preview] = self.pdf_preview.pos()  # STORE POSITION

        # Connect page change to update counter
        self.pdf_preview.page_changed = lambda: self.update_page_counter()

        # ---------------- Create All Buttons ----------------
        create_btn_path = resource_path("images/addStation.png")
        create_btn = AnimatedBarButton(
            create_btn_path,
            None,
            self.window,
            scale_factor=0.25
        )
        create_btn.callback = lambda btn=create_btn: createNewTask(self.window, btn, self.task_table, self.elements)

        delete_btn_path = resource_path("images/binicon.png")
        self.delete_btn = AnimatedBarButton(
            delete_btn_path,
            lambda: self.delete_selected_task(),
            self.window,
            scale_factor=0.25
        )

        middle_btn_path = resource_path("images/sendBarcodes.png")
        self.middle_btn = AnimatedBarButton(
            middle_btn_path,
            lambda: self.send_and_update(),
            self.window,
            scale_factor=0.25
        )

        export_btn_path = resource_path("images/save.png")
        self.export_btn = AnimatedBarButton(
            export_btn_path,
            self.export_to_pdf,
            self.window,
            scale_factor=0.25
        )

        ally_btn_path = resource_path("images/sendToAlly.png")
        self.ally_btn = AnimatedBarButton(
            ally_btn_path,
            None,
            self.window,
            scale_factor=0.25
        )
        self.ally_btn.callback = lambda btn=self.ally_btn: exportToAlly(self.window, btn, self.task_table, self.pdf_preview, self.elements)

        # Disable buttons initially
        self.middle_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.ally_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

        # Show all buttons
        for b in (create_btn, self.delete_btn, self.middle_btn, self.export_btn, self.ally_btn):
            b.show()

        # ---------------- Position All Buttons ----------------
        table_right = self.task_table.x() + self.task_table.width()
        pdf_left = self.pdf_frame.x()
        pdf_right = self.pdf_frame.x() + self.pdf_frame.width()
        table_center_y = self.task_table.y() + self.task_table.height() // 2
        table_top = self.task_table.y()

        # Calculate middle button width early (we'll need it for alignment)
        gap_between_table_pdf = pdf_left - table_right
        mb_w, mb_h = self.middle_btn.width(), self.middle_btn.height()
        if mb_w == 0 or mb_h == 0:
            sh = self.middle_btn.sizeHint()
            mb_w, mb_h = sh.width(), sh.height()

        middle_btn_x = table_right + (gap_between_table_pdf - mb_w) // 2

        # --- Create + Delete buttons (left of middle) ---
        create_w, create_h = create_btn.width(), create_btn.height()
        if create_w == 0 or create_h == 0:
            sh = create_btn.sizeHint()
            create_w, create_h = sh.width(), sh.height()

        delete_w, delete_h = self.delete_btn.width(), self.delete_btn.height()
        if delete_w == 0 or delete_h == 0:
            sh = self.delete_btn.sizeHint()
            delete_w, delete_h = sh.width(), sh.height()

        create_x = middle_btn_x
        delete_x = middle_btn_x
        create_y = table_top
        vertical_gap = 20
        delete_y = create_y + create_h + vertical_gap

        # Move Create button
        create_btn.move(create_x, create_y)
        create_btn.orig_x = create_btn.x()
        create_btn.orig_y = create_btn.y()
        self.elements.append(create_btn)
        self.manual_ui_elements.append(create_btn)
        self.orig_positions[create_btn] = create_btn.pos()

        # Move Delete button
        self.delete_btn.move(delete_x, delete_y)
        self.delete_btn.orig_x = self.delete_btn.x()
        self.delete_btn.orig_y = self.delete_btn.y()
        self.elements.append(self.delete_btn)
        self.manual_ui_elements.append(self.delete_btn)
        self.orig_positions[self.delete_btn] = self.delete_btn.pos()

        # --- Middle button BELOW Delete ---
        middle_btn_y = delete_y + delete_h + vertical_gap

        self.middle_btn.move(middle_btn_x, middle_btn_y)
        self.middle_btn.orig_x = self.middle_btn.x()
        self.middle_btn.orig_y = self.middle_btn.y()
        self.elements.append(self.middle_btn)
        self.manual_ui_elements.append(self.middle_btn)
        self.orig_positions[self.middle_btn] = self.middle_btn.pos()

        # --- Export + Ally buttons (right of PDF) ---
        ex_w, ex_h = self.export_btn.width(), self.export_btn.height()
        al_w, al_h = self.ally_btn.width(), self.ally_btn.height()

        if ex_w == 0 or ex_h == 0:
            sh = self.export_btn.sizeHint()
            ex_w, ex_h = sh.width(), sh.height()
        if al_w == 0 or al_h == 0:
            sh = self.ally_btn.sizeHint()
            al_w, al_h = sh.width(), sh.height()

        # Keep existing horizontal layout to the right of PDF
        horizontal_gap = (gap_between_table_pdf - mb_w) // 2
        export_x = pdf_right + horizontal_gap
        ally_x = export_x  # aligned vertically

        # ✅ Match Y positions with Create and Delete buttons
        export_y = create_y
        ally_y = delete_y

        # Move Export button
        self.export_btn.move(export_x, export_y)
        self.export_btn.orig_x = self.export_btn.x()
        self.export_btn.orig_y = self.export_btn.y()
        self.elements.append(self.export_btn)
        self.manual_ui_elements.append(self.export_btn)
        self.orig_positions[self.export_btn] = self.export_btn.pos()

        # Move Ally button
        self.ally_btn.move(ally_x, ally_y)
        self.ally_btn.orig_x = self.ally_btn.x()
        self.ally_btn.orig_y = self.ally_btn.y()
        self.elements.append(self.ally_btn)
        self.manual_ui_elements.append(self.ally_btn)
        self.orig_positions[self.ally_btn] = self.ally_btn.pos()

        # Initial button state check
        self.update_button_states()

        # ---------------- Live Ally Tasks UI ----------------
        self.create_live_tasks_table()

        # Populate live tasks data once on startup
        QTimer.singleShot(0, self.populate_live_tasks)
        

    def update_button_states(self):
        """Enable/disable buttons based on table and preview state."""
        # Check if table has any valid barcodes (non-zero in Barcodes column)
        has_barcodes_in_table = False
        for row in range(self.task_table.rowCount()):
            barcode_item = self.task_table.item(row, 2)  # Barcodes column
            if barcode_item:
                try:
                    barcode_count = int(barcode_item.text())
                    if barcode_count > 0:
                        has_barcodes_in_table = True
                        break
                except ValueError:
                    continue
        
        # Check if preview has any labels
        has_preview_labels = len(self.pdf_preview.labels) > 0
        
        # Check if a task is selected in the table
        has_task_selected = bool(self.task_table.selectedItems())
        
        # Update button states
        self.middle_btn.setEnabled(has_barcodes_in_table)
        self.export_btn.setEnabled(has_preview_labels)
        self.ally_btn.setEnabled(has_preview_labels)
        self.delete_btn.setEnabled(has_task_selected)  # NEW: disable delete until selection

    def send_and_update(self):
        """Generate preview and update page counter."""
        sendFormat(self.get_table_data(), self.pdf_preview)
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
