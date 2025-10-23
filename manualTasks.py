import sys
import os
from io import BytesIO

from PyQt6.QtWidgets import (
    QWidget, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QStyledItemDelegate, QLineEdit
)
from PyQt6.QtCore import Qt, QRect, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QPixmap, QMouseEvent, QFont, QBrush, QColor, QPainter, QPen
from clientCalls import fetch_manual_tasks

try:
    from barcode import Code128
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False
    print("[WARNING] python-barcode not installed. Install with: pip install python-barcode pillow")

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
                gridline-color: white;   /* vertical and horizontal lines */
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

        self.setRowCount(1)
        self._set_placeholder()
        QTimer.singleShot(0, self.populate_tasks)

    def mousePressEvent(self, event: QMouseEvent):
        item = self.itemAt(event.pos())
        if item is None:
            self.clearSelection()
        else:
            super().mousePressEvent(event)


    def _set_placeholder(self):
        left_item = QTableWidgetItem("[SERVER RETURNED EMPTY]")
        left_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        left_item.setForeground(QBrush(QColor("white")))
        left_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.setItem(0, 0, left_item)

        quantity_item = QTableWidgetItem("0")
        quantity_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
        quantity_item.setForeground(QBrush(QColor("white")))
        quantity_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(0, 1, quantity_item)

        barcode_item = QTableWidgetItem("0")
        barcode_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
        barcode_item.setForeground(QBrush(QColor("white")))
        barcode_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(0, 2, barcode_item)

    def populate_tasks(self):
        try:
            task_names = fetch_manual_tasks()
        except Exception as e:
            task_names = []

        if not task_names:
            return

        self.setRowCount(len(task_names))
        for row, task_name in enumerate(task_names):
            left_item = QTableWidgetItem(task_name)
            left_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            left_item.setForeground(QBrush(QColor("white")))
            left_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self.setItem(row, 0, left_item)

            quantity_item = QTableWidgetItem("0")
            quantity_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
            quantity_item.setForeground(QBrush(QColor("white")))
            quantity_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 1, quantity_item)

            barcode_item = QTableWidgetItem("0")
            barcode_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
            barcode_item.setForeground(QBrush(QColor("white")))
            barcode_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 2, barcode_item)

# ---------------- Resource Path ----------------
def resource_path(relative_path):
    try:
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_path, relative_path)
    return path

# ---------------- Screen Header ----------------
class ScreenHeader(QWidget):
    """
    Styled header/title bar for a screen.
    Static, no buttons, mimics ModeDial styling.
    """
    def __init__(self, parent=None, width=300, height=50, title="Manual Task Generation"):
        super().__init__(parent)

        try:
            self.setFixedSize(width, height)
            self.title = title

            # Container
            self.text_container = QWidget(self)
            self.text_container.setGeometry(0, 0, width, height)
            # Remove white border
            self.text_container.setStyleSheet("background-color: #3B3B3B;")

            # Label
            self.label = QLabel(title, self.text_container)
            self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.label.setStyleSheet("color: white;")
            self.label.setGeometry(0, 0, width, height)

            # Adjust font size to be 80% of header height
            self._adjust_font(height)

        except Exception as e:
            print(f"[ERROR] ScreenHeader.__init__ exception: {e}")

    def _adjust_font(self, header_height):
        font_size = int(header_height * 0.45)  # 80% of header height
        font = QFont("Arial", font_size, QFont.Weight.Bold)
        self.label.setFont(font)


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
        if w > 0 and h > 0 and not self.pixmap.isNull():
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
        self.anim.setEndValue(QRect((self.width() - target_width)//2, self.base_height, target_width, self.bar_height))
        self.anim.start()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and callable(self.callback):
            self.callback()

class PDFPreview(QWidget):
    def __init__(self, parent=None, x=0, y=0, width=300, height=400):
        super().__init__(parent)
        self.setGeometry(x, y, width, height)
        self.setMinimumSize(width, height)

        self.setStyleSheet("background-color: transparent;")
        self.logo = None
        self.labels = []  # store text labels for boxes

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
        self.labels = labels[:12]  # max 12
        self.update()  # triggers paintEvent()

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

            # --- Draw box labels (top center), barcodes (bottom), and barcode images (center) ---
            painter.setPen(QPen(Qt.GlobalColor.black))
            painter.setFont(QFont("Arial", 8, QFont.Weight.Medium))

            # Iterate through ALL boxes, not just labeled ones
            for box_idx in range(len(boxes)):
                x, y, w, h = boxes[box_idx]
                
                # Generate unique barcode number for this box
                barcode_number = f"m{str(box_idx).zfill(10)}"  # e.g., m0000000000, m0000000001, etc.

                # Only draw label if we have one for this box
                if box_idx < len(self.labels):
                    text = self.labels[box_idx]
                    
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
            if len(labels) >= 12:  # Stop at 12 boxes
                break
        
        if len(labels) >= 12:  # Stop at 12 boxes
            break

    # Update PDF
    pdf_preview.update_labels(labels)


# ---------------- Manual Task Screen ----------------
class manualTaskScreen:
    def __init__(self, window, return_to_menu=None):
        self.window = window
        self.elements = []
        self.return_to_menu = return_to_menu
        self.setup_ui()

    def setup_ui(self):
        w, h = self.window.window_width, self.window.window_height
        y_offset = self.window.title_bar_height + 10

        # ---------------- Home Button ----------------
        btn_path = resource_path("images/homeIcon.png")
        home_btn = AnimatedBarButton(btn_path, self.on_home_clicked, self.window, scale_factor=0.25)
        home_btn.move(w - home_btn.width() - 20, y_offset)
        home_btn.orig_x = home_btn.x()
        home_btn.orig_y = home_btn.y()
        home_btn.show()
        self.elements.append(home_btn)

        # ---------------- Task Table ----------------
        table_x, table_y = 20, y_offset + 60
        table_width, table_height = int(w * 0.3), int(h * 0.8)

        header_font = QFont()
        header_font.setPointSize(int(h * 0.025))
        header_font.setBold(True)

        self.task_table = TaskTable(self.window, table_x, table_y, table_width, table_height, header_font)
        self.task_table.show()
        self.elements.append(self.task_table)

        # ---------------- Screen Header ----------------
        header_height = 50
        self.screen_header = ScreenHeader(
            parent=self.window,
            width=self.task_table.width(),
            height=header_height,
            title="Manual Task Generation"
        )
        self.screen_header.move(self.task_table.x(), self.task_table.y() - header_height - 10)
        self.screen_header.show()
        self.elements.append(self.screen_header)

        # ---------------- PDF Preview ----------------
        # Height matches table, width proportional to A4 portrait
        pdf_height = table_height
        pdf_width = int((pdf_height / 1.414)*1.1)  # A4 ratio
        pdf_x = table_x + table_width + int(w*0.08)  # 10px gap
        pdf_y = table_y

        # Create background frame box FIRST
        self.pdf_frame = QWidget(self.window)
        self.pdf_frame.setGeometry(pdf_x, pdf_y, pdf_width, pdf_height)
        self.pdf_frame.setStyleSheet("""
            background-color: rgba(59,59,59,178);
            border: 1px solid white;
        """)
        self.pdf_frame.show()
        self.elements.append(self.pdf_frame)

        # Now create PDF preview at 80% of frame size, centered on top
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

        # ---------------- Middle Home Button ----------------
        middle_btn_path = resource_path("images/sendBarcodes.png")
        middle_btn = AnimatedBarButton(
            middle_btn_path,
            lambda: sendFormat(self.get_table_data(), self.pdf_preview),
            self.window,
            scale_factor=0.25
        )

        # Position: horizontally between table and PDF frame
        table_right = self.task_table.x() + self.task_table.width()
        pdf_left = self.pdf_frame.x()
        middle_btn_x = table_right + (pdf_left - table_right - middle_btn.width()) // 2

        # Vertically centered relative to the table
        table_top = self.task_table.y()
        table_height = self.task_table.height()
        middle_btn_y = table_top + (table_height - middle_btn.height()) // 2

        middle_btn.move(middle_btn_x, middle_btn_y)
        middle_btn.orig_x = middle_btn.x()
        middle_btn.orig_y = middle_btn.y()
        middle_btn.show()
        self.elements.append(middle_btn)

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


    def on_home_clicked(self):
        if callable(self.return_to_menu):
            self.return_to_menu()

    def cleanup(self):
        for elem in self.elements:
            elem.setParent(None)
            elem.deleteLater()
        self.elements.clear()
