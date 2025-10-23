import os
import sys
from datetime import datetime

# ---- PyQt6 ----
from PyQt6.QtCore import (
    Qt, QRect, QPropertyAnimation, QEasingCurve, QPointF
)
from PyQt6.QtGui import (
    QPixmap, QMouseEvent, QPainter, QColor, QFont, QPen, QBrush, QIcon
)
from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QFrame,
    QGraphicsView, QGraphicsScene, QGraphicsTextItem, QGraphicsEllipseItem,
    QGraphicsLineItem
)

# ---- Project imports ----
from clientCalls import fetch_tracking_history


GLOBAL_SEARCH_RESULTS = []  # stores last search's full 2D list

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


# ---------------- Tick / Cross Buttons ----------------
class TickCrossButton(QWidget):
    def __init__(self, mode="tick", callback=None, parent=None):
        """
        mode: "tick", "cross", or "refresh"
        """
        super().__init__(parent)
        self.mode = mode
        self.bg_color = "#3B3B3B"
        self.callback = callback

    def enterEvent(self, event):
        self.bg_color = "#1AA0FF"
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
        painter.setPen(QPen(Qt.GlobalColor.white, 2))

        w, h = self.width(), self.height()

        if self.mode == "tick":
            painter.drawLine(int(w*0.28), int(h*0.5), int(w*0.45), int(h*0.7))
            painter.drawLine(int(w*0.45), int(h*0.7), int(w*0.75), int(h*0.3))

        elif self.mode == "cross":
            painter.drawLine(int(w*0.28), int(h*0.28), int(w*0.72), int(h*0.72))
            painter.drawLine(int(w*0.72), int(h*0.28), int(w*0.28), int(h*0.72))

        elif self.mode == "refresh":
            # Draw circular arrow
            center = QPointF(w/2, h/2)
            radius = w * 0.25
            start_angle = 45 * 16
            span_angle = 270 * 16
            painter.drawArc(int(center.x() - radius), int(center.y() - radius),
                            int(2 * radius), int(2 * radius),
                            start_angle, span_angle)

            # Draw arrowhead
            painter.drawLine(int(center.x() + radius*0.7),
                             int(center.y() - radius*0.5),
                             int(center.x() + radius*0.9),
                             int(center.y() - radius*0.7))
            painter.drawLine(int(center.x() + radius*0.9),
                             int(center.y() - radius*0.7),
                             int(center.x() + radius*0.6),
                             int(center.y() - radius*0.8))

    def mousePressEvent(self, event):
        if callable(self.callback):
            self.callback()

# ---------------- Search Bar ----------------
class StyledSearchBar(QWidget):
    def __init__(self, parent, callback, font=None):
        super().__init__(parent)
        self.callback = callback
        self.font = font or QFont("Arial", 14, QFont.Weight.Bold)

        self.line_edit = QLineEdit(self)
        self.line_edit.setFont(self.font)
        self.line_edit.setPlaceholderText("Search...")
        self.line_edit.returnPressed.connect(self._trigger_callback)
        self.line_edit.returnPressed.disconnect()  # Remove existing connection
        self.line_edit.returnPressed.connect(lambda: None)  # Enter does nothing


        self.line_edit.setStyleSheet(f"""
            QLineEdit {{
                background-color: #3B3B3B;
                color:white;
                border:1px solid white;
                padding:5px;
                border-radius:0px;
                font-size:{self.font.pointSize()}pt;
            }}
            QLineEdit::placeholder {{ color: rgba(255,255,255,150); }}
        """)

    def resizeEvent(self, event):
        self.line_edit.setGeometry(0, 0, self.width(), self.height())

    def _trigger_callback(self):
        if callable(self.callback):
            self.callback(self.line_edit.text().strip(), refresh=False)

    def _clear_text(self):
        """Clear search bar text and reset flowchart"""
        self.line_edit.setText("")
        # Clear the flowchart if parent has reference
        if hasattr(self.parent(), "flowchart_widget") and self.parent().flowchart_widget:
            self.parent().flowchart_widget.scene.clear()
        if callable(self.callback):
            self.callback("", refresh=False)

    def _refresh(self):
        """Safe refresh for refresh button"""
        if callable(self.callback):
            self.callback(self.line_edit.text().strip(), refresh=True)

class SearchResultsTable(QTableWidget):
    def __init__(self, parent, x, y, width, height, header_font, data_list):
        """
        data_list: list of lists returned by search
        Each row: [containerID, isoBarcode, history_line1, history_line2, ...]
        """
        super().__init__(parent)
        self.setGeometry(x, y, width, height)
        self.setColumnCount(1)
        self.setHorizontalHeaderLabels(["Reference Code"])
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

        # Adjust header font
        header_font = QFont(header_font)
        header_font.setPointSize(int(header_font.pointSize()))
        self.horizontalHeader().setFont(header_font)

        # Load caution icon once
        caution_icon_path = resource_path("images/caution.png")
        self.caution_icon = QIcon(caution_icon_path)

        # Populate table
        self.populate_table(data_list)

        # Override selection to not hide highlight
        self.selectionModel().selectionChanged.connect(self.update_selection_color)

        self.show()

    def populate_table(self, data_list):
        if not data_list:
            self.setRowCount(1)
            item = QTableWidgetItem("[REFERENCE CODE NOT FOUND]")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsEditable)
            item.setForeground(QBrush(QColor("white")))
            self.setItem(0, 0, item)
            return

        self.setRowCount(len(data_list))
        for row, entry in enumerate(data_list):
            container_id = entry[0]
            iso = entry[1] if len(entry) > 1 else ""

            highlight = False
            display_text = iso

            # Highlight if ISO is missing
            if len(iso) < 1:
                display_text = "[Image Located Without Associated Barcode]"
                highlight = True

            # Highlight if containerID is missing
            if container_id is None or container_id == "":
                display_text = f"[{iso}: BARCODE FOUND WITH NO ASSOCIATED IMAGE]"
                highlight = True

            item = QTableWidgetItem(display_text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            if highlight:
                item.setBackground(QBrush(QColor("#F69220")))
                item.setForeground(QBrush(QColor("black")))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setIcon(self.caution_icon)
            else:
                item.setForeground(QBrush(QColor("white")))

            self.setItem(row, 0, item)

    def update_selection_color(self, selected, deselected):
        """
        Keep highlighted rows (orange) background when selected
        """
        for index in selected.indexes():
            item = self.item(index.row(), index.column())
            if item and item.background().color().name() == "#f69220":
                item.setBackground(QBrush(QColor("#F69220")))

class FlowChartWidget(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.setStyleSheet("""
            QGraphicsView {
                background-color: rgba(59,59,59,178);
                border: 1px solid white;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                width: 0px;
                height: 0px;
                background: transparent;
            }
        """)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self.node_radius = 20
        self.y_spacing = 100
        self.x_spacing = 300
        self.top_padding = 40
        self.bottom_padding = 40

    def display_flow(self, events):
        self.scene.clear()
        if not events:
            text = QGraphicsTextItem("No history found.")
            text.setDefaultTextColor(QColor("white"))
            self.scene.addItem(text)
            return

        blue_pen = QPen(QColor("#1AA0FF"))
        blue_pen.setWidth(2)

        current_x = self.top_padding
        current_y = self.top_padding
        prev_node_center = None

        max_x = current_x
        max_y = current_y

        for idx, event_str in enumerate(events):
            parts = event_str.split("|")
            timestamp_raw = parts[0].strip() if len(parts) > 0 else ""
            station = parts[1].strip() if len(parts) > 1 else ""
            person = parts[2].strip() if len(parts) > 2 else ""

            # Format timestamp
            timestamp_formatted = timestamp_raw
            try:
                dt = datetime.fromisoformat(timestamp_raw)
                day = dt.day
                day_suffix = 'th'
                if day in (1, 21, 31):
                    day_suffix = 'st'
                elif day in (2, 22):
                    day_suffix = 'nd'
                elif day in (3, 23):
                    day_suffix = 'rd'
                timestamp_formatted = f"{day}{day_suffix} {dt.strftime('%B %Y')} | {dt.strftime('%H:%M:%S')}"
            except Exception:
                pass

            is_reprint = station.upper() == "REPRINT"
            node_color = QColor("red") if is_reprint else QColor("#1AA0FF")
            node_pen = QPen(Qt.GlobalColor.transparent) if is_reprint else blue_pen

            # Draw node
            node = self.scene.addEllipse(
                current_x - self.node_radius, current_y,
                self.node_radius * 2, self.node_radius * 2,
                node_pen, node_color
            )

            # Draw label (same as normal nodes)
            text_item = QGraphicsTextItem(f"{timestamp_formatted}\n{station}\n{person}")
            text_item.setDefaultTextColor(QColor("white"))
            text_item.setPos(current_x + self.node_radius + 20, current_y - 5)
            self.scene.addItem(text_item)

            # Draw vertical line for normal nodes
            if not is_reprint and prev_node_center:
                self.scene.addLine(prev_node_center.x(), prev_node_center.y() + self.node_radius,
                                   current_x, current_y, blue_pen)

            # Update positions
            if is_reprint:
                # Start next column aligned horizontally with REPRINT node
                current_x += self.x_spacing
                current_y = current_y
                prev_node_center = None
            else:
                prev_node_center = QPointF(current_x, current_y)
                current_y += self.y_spacing

            # Update scene bounds
            max_x = max(max_x, current_x + self.node_radius * 2 + 200)
            max_y = max(max_y, current_y + self.node_radius + self.bottom_padding)

        self.scene.setSceneRect(0, 0, max_x, max_y)

    def wheelEvent(self, event):
        delta_y = event.angleDelta().y()
        vbar = self.verticalScrollBar()
        if vbar:
            step = int(delta_y / 2)
            vbar.setValue(vbar.value() - step)


# ---------------- Prodigally Screen ----------------
class ProdigallyScreen:
    def __init__(self, window, return_to_menu=None):
        self.window = window
        self.return_to_menu = return_to_menu
        self.elements = []  # all UI elements tracked for cleanup
        self.search_results_table = None  # table widget reference
        self.setup_ui()

    def setup_ui(self):
        w, h = self.window.window_width, self.window.window_height
        top_padding = self.window.title_bar_height + 10
        search_height = 50

        # --- Home Button ---
        btn_path = resource_path("images/homeIcon.png")
        self.home_btn = AnimatedBarButton(btn_path, self.on_home_clicked, self.window, scale_factor=0.25)
        self.home_btn.move(w - self.home_btn.width() - 20, top_padding)
        self.home_btn.show()
        self.elements.append(self.home_btn)

        # --- Search Bar ---
        search_width = int(w * 0.33)
        self.search_widget = StyledSearchBar(self.window, self.on_search)
        self.search_widget.setGeometry(20, top_padding, search_width, search_height)
        self.search_widget.show()
        self.elements.append(self.search_widget)

        # --- Table ---
        table_top = top_padding + search_height + 10
        bottom_padding = top_padding
        table_height = h - table_top - bottom_padding
        table_x = self.search_widget.x()
        table_width = self.search_widget.width()

        base_font = self.search_widget.line_edit.font()
        header_font = QFont(base_font.family())
        header_font.setPointSize(base_font.pointSize())
        header_font.setWeight(QFont.Weight.Bold)

        self.search_results_table = SearchResultsTable(
            parent=self.window,
            x=table_x,
            y=table_top,
            width=table_width,
            height=table_height,
            header_font=header_font,
            data_list=[]
        )
        self.elements.append(self.search_results_table)

        # --- Flowchart widget ---
        flowchart_x = table_x + table_width + 20
        flowchart_width = int(w * 0.5)
        self.flowchart_widget = FlowChartWidget(self.window)
        self.flowchart_widget.setGeometry(flowchart_x, table_top, flowchart_width, table_height)
        self.flowchart_widget.show()
        self.elements.append(self.flowchart_widget)

        # --- Tick / Cross / Refresh buttons ---
        btn_size = search_height
        tick_x = flowchart_x
        cross_x = tick_x + btn_size + 2
        refresh_x = cross_x + btn_size + 2

        # Tick button: original _trigger_callback + refresh
        self.tick_btn = TickCrossButton(
            "tick",
            lambda: self.safe_callback(
                lambda: (self.search_widget._trigger_callback(), self.search_widget._refresh()),
                "tick"
            ),
            self.window
        )

        self.tick_btn.setGeometry(tick_x, top_padding, btn_size, btn_size)
        self.tick_btn.show()
        self.elements.append(self.tick_btn)

        # Cross button: original _clear_text + refresh
        self.clear_btn = TickCrossButton(
            "cross",
            lambda: self.safe_callback(
                lambda: (self.search_widget._clear_text(), self.search_widget._refresh()),
                "cross"
            ),
            self.window
        )
        self.clear_btn.setGeometry(cross_x, top_padding, btn_size, btn_size)
        self.clear_btn.show()
        self.elements.append(self.clear_btn)

        self.refresh_btn = TickCrossButton("refresh", lambda: self.safe_callback(self.search_widget._refresh, "refresh"), self.window)
        self.refresh_btn.setGeometry(refresh_x, top_padding, btn_size, btn_size)
        self.refresh_btn.show()
        self.elements.append(self.refresh_btn)

        # Connect table click to flowchart
        self.search_results_table.currentCellChanged.connect(self.on_row_selected)


    def safe_callback(self, func, name):
        try:
            print(f"Callback triggered: {name}")
            func()
        except Exception as e:
            print(f"Error in callback {name}: {e}")

    def on_home_clicked(self):
        if callable(self.return_to_menu):
            self.return_to_menu()

    def on_search(self, text, refresh=False):
        global GLOBAL_SEARCH_RESULTS

        if len(text) == 8:
            res = fetch_tracking_history(orderNumber=text)
        elif len(text) == 10:
            res = fetch_tracking_history(leadBarcode=text)
        elif len(text) == 11:
            res = fetch_tracking_history(isoBarcode=text)
        else:
            res = {"status": "error", "history": []}

        history_list = []
        if res.get("status") == "success" and res.get("history"):
            history_list = [row for row in res["history"] if row]

        GLOBAL_SEARCH_RESULTS = history_list.copy()

        if self.search_results_table:
            self.search_results_table.populate_table(history_list)

            # Automatically select first row if available
            if self.search_results_table.rowCount() > 0:
                self.search_results_table.setCurrentCell(0, 0)
                # This will trigger on_row_selected automatically

        # If refresh and a row is selected, re-display flowchart
        if refresh and self.search_results_table:
            selected_items = self.search_results_table.selectedItems()
            if selected_items:
                row = selected_items[0].row()
                self.on_row_selected(row, 0)


    def on_row_selected(self, currentRow, currentColumn, previousRow=None, previousColumn=None):
        """Update flowchart when table selection changes"""
        global GLOBAL_SEARCH_RESULTS
        row = currentRow
        if not GLOBAL_SEARCH_RESULTS or row >= len(GLOBAL_SEARCH_RESULTS) or row < 0:
            # Nothing to display
            if self.flowchart_widget:
                self.flowchart_widget.scene.clear()
            return

        entry = GLOBAL_SEARCH_RESULTS[row]
        if not entry or len(entry) < 3:
            if self.flowchart_widget:
                self.flowchart_widget.scene.clear()
            return

        # Only pass the history events to the flowchart
        events = entry[2:]
        if self.flowchart_widget:
            self.flowchart_widget.display_flow(events)


    def cleanup(self):
        for elem in self.elements:
            elem.setParent(None)
            elem.deleteLater()
        self.elements.clear()

