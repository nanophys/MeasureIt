import os
import sys
import types
from pathlib import Path

# Use a writable location for qcodes user data/logs inside the repo workspace
os.environ.setdefault("QCODES_USER_PATH", str(Path.cwd() / ".qcodes_test"))
os.environ.setdefault("MEASUREIT_FAKE_QT", "1")

# Provide lightweight PyQt5 stubs when running in fake-Qt mode to avoid GUI crashes.
if os.environ.get("MEASUREIT_FAKE_QT", "").lower() in {"1", "true", "yes"}:
    qt_module = types.ModuleType("PyQt5")
    qtcore = types.ModuleType("PyQt5.QtCore")
    qtgui = types.ModuleType("PyQt5.QtGui")
    qttest = types.ModuleType("PyQt5.QtTest")
    qtwidgets = types.ModuleType("PyQt5.QtWidgets")
    uic_module = types.ModuleType("PyQt5.uic")
    sip_module = types.ModuleType("sip")

    class _FakeSignal:
        def __init__(self, *args, **kwargs):
            self._slots = []

        def connect(self, slot):
            self._slots.append(slot)

        def disconnect(self, slot):
            try:
                self._slots.remove(slot)
            except ValueError:
                pass

        def emit(self, *args, **kwargs):
            for slot in list(self._slots):
                try:
                    slot(*args, **kwargs)
                except Exception:
                    pass

    def pyqtSignal(*args, **kwargs):
        return _FakeSignal()

    def pyqtSlot(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    class QObject:
        def __init__(self, *args, **kwargs):
            super().__init__()


    class QThread:
        def __init__(self, *args, **kwargs):
            self._running = False

        def start(self):
            self._running = True
            if hasattr(self, "run"):
                self.run()

        def run(self):
            pass

        def quit(self):
            self._running = False

        def terminate(self):
            self._running = False

        def wait(self, timeout=None):
            return True

        def isRunning(self):
            return self._running

    class QMetaObject:
        @staticmethod
        def invokeMethod(obj, method_name, connection=None):
            fn = getattr(obj, method_name, None)
            if callable(fn):
                return fn()

    class _Qt:
        QueuedConnection = 0
        # Key/focus constants used by plotter stubs
        Key_Space = 0x20
        Key_Escape = 0x01000000
        Key_Return = 0x01000004
        Key_Enter = 0x01000005
        StrongFocus = 0

    Qt = _Qt()

    class QApplication:
        def __init__(self, *args, **kwargs):
            pass

        @staticmethod
        def instance():
            return None

        def processEvents(self):
            pass

    class QCoreApplication:
        @staticmethod
        def processEvents():
            pass

    class QTimer:
        def __init__(self, *args, **kwargs):
            self._callback = None
            self._interval = None

        def start(self, interval):
            self._interval = interval
            if self._callback:
                self._callback()

        def stop(self):
            pass

        def timeout(self, cb):
            self._callback = cb

        @staticmethod
        def singleShot(delay, callback):
            try:
                callback()
            except Exception:
                pass

    class QTest:
        @staticmethod
        def qWait(ms=0):
            pass

    class QGuiApplication(QApplication):
        pass

    class QWidget:
        def __init__(self, *args, **kwargs):
            pass

        def setWindowTitle(self, *args, **kwargs):
            pass

        def resize(self, *args, **kwargs):
            pass

        def setFocusPolicy(self, *args, **kwargs):
            pass

        def close(self):
            pass

        def show(self):
            pass

    class _BaseLayout:
        def __init__(self, *args, **kwargs):
            self.children = []

        def setContentsMargins(self, *args, **kwargs):
            pass

        def setSpacing(self, *args, **kwargs):
            pass

        def addWidget(self, widget):
            self.children.append(widget)

        def addLayout(self, layout):
            self.children.append(layout)

        def addStretch(self, *args, **kwargs):
            pass

    class QHBoxLayout(_BaseLayout):
        pass

    class QVBoxLayout(_BaseLayout):
        pass

    class QLabel:
        def __init__(self, *args, **kwargs):
            self._text = ""

        def setFont(self, *args, **kwargs):
            pass

        def setStyleSheet(self, *args, **kwargs):
            pass

        def setText(self, text):
            self._text = text

    class QProgressBar:
        def __init__(self, *args, **kwargs):
            self._value = 0

        def setRange(self, *args, **kwargs):
            pass

        def setValue(self, value):
            self._value = value

        def setTextVisible(self, *args, **kwargs):
            pass

        def setFormat(self, *args, **kwargs):
            pass

    class QFont:
        def __init__(self, *args, **kwargs):
            pass

    class QCheckBox:
        def __init__(self, *args, **kwargs):
            self._checked = False
            self._cb = None

        def setChecked(self, val):
            self._checked = bool(val)

        def isChecked(self):
            return self._checked

        def stateChanged(self, cb):
            self._cb = cb

    class QComboBox:
        def __init__(self, *args, **kwargs):
            self._items = []
            self._index = 0
            self._cb = None

        def addItems(self, items):
            self._items.extend(items)

        def currentIndexChanged(self, cb):
            self._cb = cb

        def setCurrentIndex(self, idx):
            self._index = idx
            if self._cb:
                try:
                    self._cb(idx)
                except Exception:
                    pass

    class QPushButton:
        def __init__(self, *args, **kwargs):
            self._cb = None

        def setEnabled(self, val):
            pass

        def clicked(self, cb):
            self._cb = cb

    qtcore.QObject = QObject
    qtcore.pyqtSignal = pyqtSignal
    qtcore.pyqtSlot = pyqtSlot
    qtcore.QMetaObject = QMetaObject
    qtcore.Qt = Qt
    qtcore.QCoreApplication = QCoreApplication
    qtcore.QTimer = QTimer
    qtcore.QThread = QThread
    qtcore.PYQT_VERSION = 0x050f00  # 5.15.0
    qtcore.PYQT_VERSION_STR = "5.15.0"
    qtcore.QT_VERSION_STR = "5.15.0"
    qtcore.qDebug = lambda *args, **kwargs: None
    qtcore.qWarning = lambda *args, **kwargs: None
    qtcore.qCritical = lambda *args, **kwargs: None
    qtcore.qFatal = lambda *args, **kwargs: None
    qtcore.pyqtProperty = property
    qtcore._message_handler = None
    qtcore.qVersion = lambda: "5.15.0"
    def _install(handler):
        prev = qtcore._message_handler
        qtcore._message_handler = handler
        return prev
    def _remove(handler=None):
        qtcore._message_handler = None
    qtcore.qInstallMessageHandler = _install
    qtcore.qRemoveMessageHandler = _remove
    qtgui.QGuiApplication = QGuiApplication
    qtgui.QFont = QFont
    qtwidgets.QWidget = QWidget
    qtwidgets.QHBoxLayout = QHBoxLayout
    qtwidgets.QVBoxLayout = QVBoxLayout
    qtwidgets.QLabel = QLabel
    qtwidgets.QProgressBar = QProgressBar
    qtwidgets.QCheckBox = QCheckBox
    qtwidgets.QComboBox = QComboBox
    qtwidgets.QPushButton = QPushButton
    qttest.QTest = QTest
    qtwidgets.QApplication = QApplication

    qt_module.QtCore = qtcore
    qt_module.QtGui = qtgui
    qt_module.QtTest = qttest
    qt_module.QtWidgets = qtwidgets
    qt_module.uic = uic_module

    sys.modules["PyQt5"] = qt_module
    sys.modules["PyQt5.QtCore"] = qtcore
    sys.modules["PyQt5.QtGui"] = qtgui
    sys.modules["PyQt5.QtTest"] = qttest
    sys.modules["PyQt5.QtWidgets"] = qtwidgets
    sys.modules["PyQt5.uic"] = uic_module
    sys.modules["PyQt5.sip"] = sip_module
    sys.modules["sip"] = sip_module

    # Minimal pyqtgraph stub to avoid importing real Qt/pyqtgraph stack in headless tests
    pg_module = types.ModuleType("pyqtgraph")

    def setConfigOptions(**kwargs):
        return None

    def setConfigOption(key, value):
        return None

    def mkPen(*args, **kwargs):
        return {"args": args, "kwargs": kwargs}

    class PlotDataItem:
        def __init__(self):
            self.xData = []
            self.yData = []

        def setData(self, x, y=None):
            # Accept either (x, y) or a single iterable
            if y is None and isinstance(x, (list, tuple)):
                if len(x) >= 2:
                    x, y = x[0], x[1]
            self.xData = x
            self.yData = y

    class Plot:
        def setLabel(self, *args, **kwargs):
            return None

        def showGrid(self, *args, **kwargs):
            return None

        def plot(self, *args, **kwargs):
            return PlotDataItem()

    class GraphicsLayoutWidget:
        def addPlot(self, *args, **kwargs):
            return Plot()

    pg_module.setConfigOptions = setConfigOptions
    pg_module.setConfigOption = setConfigOption
    pg_module.mkPen = mkPen
    pg_module.GraphicsLayoutWidget = GraphicsLayoutWidget
    pg_module.PlotDataItem = PlotDataItem
    # Provide minimal Qt namespace compatible with measureit plotter
    pg_module.QtCore = types.SimpleNamespace(Qt=Qt)
    pg_module.Qt = types.SimpleNamespace(QtCore=pg_module.QtCore, QtGui=qtgui, QtWidgets=qtwidgets)

    sys.modules["pyqtgraph"] = pg_module
    sys.modules["pyqtgraph.Qt"] = pg_module.Qt
