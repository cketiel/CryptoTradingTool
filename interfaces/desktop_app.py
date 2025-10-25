import sys
import time
import os
import pickle
from datetime import datetime, timedelta

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QTableView, QPushButton, QLabel, QHeaderView, QRadioButton,
                               QGroupBox, QLineEdit, QStyledItemDelegate, QStyle, QDialog,
                               QTextEdit, QProgressBar)
from PySide6.QtCore import (Qt, QAbstractTableModel, QTimer, QThread, Signal,
                            QObject, QSortFilterProxyModel, QSize, QRect)
from PySide6.QtGui import QColor, QFont, QPixmap, QPainter, QPalette, QPainterPath

try:
    from core.kucoin_client import KuCoinClient
    from config.intervals import all_interval, small_interval, big_interval
except ModuleNotFoundError:
    sys.exit("Error: Run this application using 'python main.py --interface desktop'")

def log_message(message):
    print(f"[LOG {datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {message}")

CACHE_DIR = 'cache'
CACHE_FILE = os.path.join(CACHE_DIR, 'scan_results.pkl')
TIMEFRAME_DURATIONS = {
    '15m': timedelta(minutes=15), '30m': timedelta(minutes=30), '1h': timedelta(hours=1),
    '2h': timedelta(hours=2), '4h': timedelta(hours=4), '8h': timedelta(hours=8),
    '1d': timedelta(days=1), '1w': timedelta(weeks=1)
}
def save_cache(data_dict):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, 'wb') as f: pickle.dump(data_dict, f)
        log_message(f"Cache saved successfully to {CACHE_FILE}")
    except Exception as e: log_message(f"Error saving cache: {e}")
def load_cache():
    if not os.path.exists(CACHE_FILE):
        log_message("Cache file not found. Returning empty dictionary.")
        return {}
    try:
        with open(CACHE_FILE, 'rb') as f: data = pickle.load(f)
        log_message(f"Cache loaded successfully from {CACHE_FILE}. Found data for {list(data.keys())} timeframes.")
        return data
    except Exception as e:
        log_message(f"Error loading cache: {e}. Returning empty dictionary.")
        return {}
class LogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Log"); self.setMinimumSize(600, 400)
        layout = QVBoxLayout(self)
        self.log_text_edit = QTextEdit(); self.log_text_edit.setReadOnly(True)
        layout.addWidget(self.log_text_edit)
        self.close_button = QPushButton("Close"); self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button)
    def append_log(self, message):
        self.log_text_edit.append(message)
        self.log_text_edit.verticalScrollBar().setValue(self.log_text_edit.verticalScrollBar().maximum())

class NameColumnDelegate(QStyledItemDelegate):
    def __init__(self, kucoin_client):
        super().__init__(); self.kucoin_client = kucoin_client
    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        full_symbol = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        details = self.kucoin_client.get_asset_details(full_symbol)
        ticker, full_name = full_symbol.split('/')[0], details['name']
        self.initStyleOption(option, index)
        painter.fillRect(option.rect, option.palette.base())
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        padding, icon_size = 5, 24
        icon_rect = QRect(
            option.rect.x() + padding,
            option.rect.y() + (option.rect.height() - icon_size) // 2,
            icon_size,
            icon_size
        )
        if details.get('icon_path') and os.path.exists(details['icon_path']):
            pixmap = QPixmap(details['icon_path'])
            painter.save()
            path = QPainterPath()
            path.addEllipse(icon_rect)
            painter.setClipPath(path)
            painter.drawPixmap(icon_rect, pixmap)
            painter.restore()
        x = icon_rect.right() + padding
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        ticker_width = painter.fontMetrics().boundingRect(ticker).width()
        painter.drawText(x, option.rect.y(), ticker_width, option.rect.height(), Qt.AlignmentFlag.AlignVCenter, ticker)
        x += ticker_width + padding
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(option.palette.color(QPalette.ColorRole.PlaceholderText))
        painter.drawText(x, option.rect.y(), option.rect.width() - x, option.rect.height(), Qt.AlignmentFlag.AlignVCenter, full_name)
        painter.restore()
    def sizeHint(self, option, index):
        return QSize(200, 36)

class Worker(QObject):
    finished = Signal(dict); progress = Signal(int, int); log = Signal(str)
    def __init__(self, kucoin_client, timeframes_to_scan):
        super().__init__(); self.kucoin_client = kucoin_client; self.timeframes_to_scan = timeframes_to_scan
    def run(self):
        results_list = self.kucoin_client.scan_for_candle_streaks(
            timeframes=self.timeframes_to_scan, top_n_volume=50, min_streak_count=3,
            progress_callback=lambda c, t: self.progress.emit(c, t),
            log_callback=lambda m: self.log.emit(m)
        )
        newly_scanned_results = {}
        for symbol, count, timeframe, color, last_price in results_list:
            if timeframe not in newly_scanned_results: newly_scanned_results[timeframe] = []
            newly_scanned_results[timeframe].append((symbol, count, timeframe, color, last_price))
        self.finished.emit(newly_scanned_results)

class StreakTableModel(QAbstractTableModel):
    def __init__(self, data=[]):
        super().__init__()
        self._data = data
        self.headers = ["Rank", "Change", "Name", "Symbol", "Streak Count", "Last Close", "Timeframe"]
        self.previous_ranks = {}
    def rowCount(self, parent=None): return len(self._data)
    def columnCount(self, parent=None): return len(self.headers)
    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal: return self.headers[section]
        return None
    def data(self, index, role):
        if not index.isValid(): return None
        row_data, col = self._data[index.row()], index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 5 and row_data[col] is not None:
                return f"{row_data[col]:.4f}"
            return str(row_data[col])
        if role == Qt.ItemDataRole.EditRole:
            if col in [0, 4]: return int(row_data[col])
            if col == 5 and row_data[col] is not None: return float(row_data[col])
            if col == 1:
                s = str(row_data[col])
                if "▲" in s: return int(s.split(" ")[1])
                elif "▼" in s: return -int(s.split(" ")[1])
                return 0
            if col in [2, 3]: return str(row_data[2])
            return str(row_data[col])
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in [0, 1, 4, 5]: return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft
        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 1:
                s = str(row_data[col])
                if "▲" in s: return QColor("green")
                if "▼" in s: return QColor("red")
            if col in [4, 5]:
                streak_color = row_data[7]
                if streak_color == 'green':
                    return QColor(Qt.GlobalColor.darkGreen)
                if streak_color == 'red':
                    return QColor(Qt.GlobalColor.red)
        return None
    def update_data(self, new_data):
        sorted_by_streak = sorted(new_data, key=lambda x: x[1], reverse=True)
        current_ranks = {item[0] + item[2]: i for i, item in enumerate(sorted_by_streak)}
        processed_data = []
        for i, (symbol, count, timeframe, color, last_price) in enumerate(sorted_by_streak):
            rank, key = i + 1, symbol + timeframe
            prev_rank, change_str = self.previous_ranks.get(key), "-"
            if prev_rank is not None:
                diff = prev_rank - rank
                if diff > 0: change_str = f"▲ {diff}"
                elif diff < 0: change_str = f"▼ {-diff}"
            processed_data.append([rank, change_str, symbol, symbol, count, last_price, timeframe, color])
        self.previous_ranks = current_ranks
        self.beginResetModel(); self._data = processed_data; self.endResetModel()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        log_message("MainWindow.__init__() started.")
        self.setWindowTitle("Crypto Trading Tool - Streak Scanner")
        self.setGeometry(100, 100, 1000, 700)
        self.setup_ui()
        log_message("Initializing KuCoinClient...")
        self.kucoin_client = KuCoinClient()
        log_message("KuCoinClient initialized.")
        self.source_model = StreakTableModel()
        self.proxy_model = QSortFilterProxyModel(); self.proxy_model.setSourceModel(self.source_model)
        self.proxy_model.setSortRole(Qt.ItemDataRole.EditRole); self.proxy_model.setFilterKeyColumn(3)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.table_view.setModel(self.proxy_model)
        self.table_view.setItemDelegateForColumn(2, NameColumnDelegate(self.kucoin_client))
        self.setup_table_style()
        self.worker_thread = None; self.worker = None; self.update_start_time = None
        self.current_filter = all_interval
        log_message("Loading initial data from cache...")
        self.cached_results = load_cache()
        self.log_dialog = LogDialog(self)
        self.setup_connections()
        self.sync_timer = QTimer(self); self.sync_timer.setInterval(60 * 1000)
        self.sync_timer.timeout.connect(self.check_sync_point)
        log_message("Performing initial display from cache...")
        self._display_from_cache()
        log_message("Triggering initial data scan on startup.")
        self.manual_refresh()
        log_message("Starting sync timer for subsequent updates.")
        self.sync_timer.start()
        log_message("MainWindow.__init__() finished.")

    def setup_ui(self):
        self.central_widget = QWidget(); self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.status_layout = QHBoxLayout()
        self.last_updated_label = QLabel("Last Updated: Never"); self.update_duration_label = QLabel("Duration: N/A")
        self.status_layout.addWidget(self.last_updated_label); self.status_layout.addStretch(); self.status_layout.addWidget(self.update_duration_label)
        self.filter_groupbox = QGroupBox("Timeframe Filter"); self.filter_layout = QHBoxLayout(); self.filter_groupbox.setLayout(self.filter_layout)
        self.radio_all = QRadioButton("All"); self.radio_small = QRadioButton("Small"); self.radio_big = QRadioButton("Big"); self.radio_all.setChecked(True)
        self.filter_layout.addWidget(self.radio_all); self.filter_layout.addWidget(self.radio_small); self.filter_layout.addWidget(self.radio_big); self.filter_layout.addStretch()
        self.search_bar = QLineEdit(); self.search_bar.setPlaceholderText("Search Symbol...")
        self.progress_bar = QProgressBar(); self.progress_bar.setVisible(False)
        self.log_button = QPushButton("View Log"); self.log_button.setFixedWidth(100)
        progress_layout = QHBoxLayout(); progress_layout.addWidget(self.progress_bar); progress_layout.addWidget(self.log_button)
        self.refresh_button = QPushButton("Refresh Now"); self.table_view = QTableView()
        self.layout.addLayout(self.status_layout); self.layout.addWidget(self.filter_groupbox)
        self.layout.addWidget(self.search_bar); self.layout.addLayout(progress_layout)
        self.layout.addWidget(self.refresh_button); self.layout.addWidget(self.table_view)
    def setup_connections(self):
        self.radio_all.toggled.connect(self._on_filter_changed); self.radio_small.toggled.connect(self._on_filter_changed); self.radio_big.toggled.connect(self._on_filter_changed)
        self.search_bar.textChanged.connect(self.proxy_model.setFilterFixedString)
        self.refresh_button.clicked.connect(self.manual_refresh)
        self.log_button.clicked.connect(self.log_dialog.show)
    def setup_table_style(self):
        self.table_view.setSortingEnabled(True); self.table_view.sortByColumn(4, Qt.SortOrder.DescendingOrder); self.table_view.setAlternatingRowColors(True)
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table_view.verticalHeader().setVisible(False); self.table_view.verticalHeader().setDefaultSectionSize(36)
        bold_font = QFont(); bold_font.setBold(True); header.setFont(bold_font)
    def check_sync_point(self):
        now = datetime.now()
        log_message(f"check_sync_point() called by timer at {now.strftime('%H:%M:%S')}.")
        self.manual_refresh()
    def manual_refresh(self):
        log_message("manual_refresh() triggered.")
        if self.worker_thread and self.worker_thread.isRunning():
            log_message("Refresh is already in progress. Skipping request.")
            return
        log_message("Checking for stale timeframes...")
        timeframes = self._get_stale_timeframes()
        if not timeframes:
            log_message("Cache is up to date. Nothing to refresh.")
            self.last_updated_label.setText(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Up to date)")
            return
        log_message(f"Found {len(timeframes)} stale timeframes to scan: {timeframes}")
        self.log_dialog.log_text_edit.clear()
        self.progress_bar.setVisible(True); self.progress_bar.setValue(0)
        self.refresh_button.setEnabled(False); self.refresh_button.setText("Refreshing...")
        self.update_start_time = time.perf_counter()
        log_message("Setting up new Worker and QThread.")
        self.worker_thread = QThread()
        self.worker = Worker(self.kucoin_client, timeframes)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.log.connect(self.log_dialog.append_log); self.worker.log.connect(log_message)
        self.worker.progress.connect(lambda c, t: self.progress_bar.setValue(int(c/t * 100) if t > 0 else 0))
        self.worker.finished.connect(self.on_scan_complete)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self.cleanup_thread_references)
        log_message("Starting worker thread...")
        self.worker_thread.start()
    def on_scan_complete(self, new_data_dict):
        log_message("on_scan_complete() slot triggered.")
        if self.update_start_time:
            duration = time.perf_counter() - self.update_start_time
            log_message(f"Scan took {duration:.2f} seconds.")
            self.update_duration_label.setText(f"Duration: {duration:.2f}s")
        now = datetime.now()
        for timeframe, data_list in new_data_dict.items():
            log_message(f"Updating cache for timeframe '{timeframe}' with {len(data_list)} items.")
            self.cached_results[timeframe] = {'timestamp': now, 'data': data_list}
        save_cache(self.cached_results)
        self._display_from_cache()
        self.last_updated_label.setText(f"Last Updated: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        self.refresh_button.setEnabled(True); self.refresh_button.setText("Refresh Now")
        self.progress_bar.setVisible(False)
    def cleanup_thread_references(self):
        log_message("Cleaning up worker and thread references.")
        self.worker, self.worker_thread = None, None
    def _get_stale_timeframes(self):
        stale, now = set(), datetime.now()
        for tf in all_interval:
            if tf not in self.cached_results:
                stale.add(tf)
        for tf, entry in self.cached_results.items():
            if now - entry.get('timestamp', datetime.min) >= TIMEFRAME_DURATIONS.get(tf, timedelta(0)):
                stale.add(tf)
        stale.update(self._get_current_sync_timeframes(now))
        return list(stale)
    def _get_current_sync_timeframes(self, now):
        tfs = set()
        minute = now.minute
        if minute % 15 == 1: tfs.add('15m')
        if minute % 30 == 1: tfs.add('30m')
        if minute == 1: tfs.update(['1h', '2h', '4h', '8h', '1d', '1w'])
        return list(tfs)
    def _on_filter_changed(self):
        log_message("Filter changed.")
        if self.radio_small.isChecked(): self.current_filter = small_interval
        elif self.radio_big.isChecked(): self.current_filter = big_interval
        else: self.current_filter = all_interval
        self._display_from_cache()
    def _display_from_cache(self):
        log_message("Displaying data from cache...")
        items = []
        for tf, entry in self.cached_results.items():
            if tf in self.current_filter:
                items.extend(entry.get('data', []))
        log_message(f"Found {len(items)} items matching current filter to display.")
        self.source_model.update_data(items)
    def closeEvent(self, event):
        log_message("Close event detected. Saving cache before exiting.")
        save_cache(self.cached_results)
        event.accept()

def run_desktop():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    run_desktop()