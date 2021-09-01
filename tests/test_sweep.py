import os,time,sys
import time

import nidaqmx
import numpy as np
import qcodes as qc
from qcodes import Station, initialise_or_create_database_at, load_by_run_spec
from qcodes.tests.instrument_mocks import MockParabola
sys.path.append(os.environ['MeasureItHome'])
import src
from drivers.daq_driver import Daq
from src.base_sweep import BaseSweep
from src.simul_sweep import SimulSweep
from src.sweep0d import Sweep0D
from src.sweep1d import Sweep1D
from src.util import (connect_station_instruments, connect_to_station,
                      init_database)
import matplotlib             
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
matplotlib.use('Qt5Agg')
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtWidgets import QTableWidgetItem, QMessageBox, QFileDialog, \
    QPushButton, QCheckBox, QHeaderView, QLineEdit, QListWidgetItem, QAction
from PyQt5.QtGui import QTextCursor



def window():
    app = QtWidgets.QApplication(sys.argv)
    app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app.setStyle('WindowsVista')
    widget = QtWidgets.QWidget()
    widget.setGeometry(50,50,320,200)
    widget.setWindowTitle('Sweep test')
    button0D = QPushButton(widget)
    button0D.setText("Sweep0D")
    button0D.move(64,32)
    button0D.clicked.connect(button0D_clicked)

    button1D = QPushButton(widget)
    button1D.setText("Sweep1D")
    button1D.move(64,64)
    button1D.clicked.connect(button1D_clicked)
    widget.show()
    sys.exit(app.exec_())

def button0D_clicked():
    testInstrument = MockParabola(name='test0D')
    testInstrument.noise(1)
    sweep = Sweep0D(max_time=600, save_data=True,inter_delay = 0.3)
    follow_parameters = {
        testInstrument.parabola,
        testInstrument.skewed_parabola,
    }
    sweep.follow_param(*follow_parameters)
    database_name = "test_sweep.db"
    exp_name = __name__
    sample_name = 'test0D'
    init_database(database_name, exp_name, sample_name, sweep)
    sweep.start()

def button1D_clicked():
    testInstrument = MockParabola(name='test1D')
    testInstrument.noise(1)
    sweep = Sweep1D(testInstrument.x,start=0,stop=1,step = 0.01, save_data=True,inter_delay = 0.3)
    follow_parameters = {
        testInstrument.parabola,
        testInstrument.skewed_parabola,
    }
    sweep.follow_param(*follow_parameters)
    database_name = "test_sweep.db"
    exp_name = __name__
    sample_name = 'test1D'
    init_database(database_name, exp_name, sample_name, sweep)
    sweep.start()



if __name__ == "__main__":
    if os.path.isfile(os.environ['MeasureItHome'] + '\\cfg\\qcodesrc.json'):
        qc.config.update_config(os.environ['MeasureItHome'] + '\\cfg\\')
    window()
