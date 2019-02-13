import PyQt5 as qt
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import sys, time
import matplotlib
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from sweep import Sweep
import qcodes as qc
import nidaqmx
from qcodes.dataset.measurements import Measurement
from qcodes.dataset.database import initialise_or_create_database_at

class Sweep1DWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__()
        self.parent=parent
        self.setupUi()
        self.create_frame()
        
        self.sweeping = False
        self.running = False
        
        
    def setupUi(self):
        self.setObjectName("1D Sweep")
        self.resize(640, 480)
        self.centralwidget = QWidget(self)
        self.centralwidget.setObjectName("centralwidget")
        self.sweep1d_label = QLabel(self.centralwidget)
        self.sweep1d_label.setGeometry(QRect(9, 9, 106, 16))
        self.sweep1d_label.setObjectName("sweep1d_label")
        self.formLayoutWidget = QWidget(self.centralwidget)
        self.formLayoutWidget.setGeometry(QRect(10, 40, 160, 126))
        self.formLayoutWidget.setObjectName("formLayoutWidget")
        self.formLayout = QFormLayout(self.formLayoutWidget)
        self.formLayout.setContentsMargins(0, 0, 0, 0)
        self.formLayout.setObjectName("formLayout")
        self.min_v_label = QLabel(self.formLayoutWidget)
        self.min_v_label.setObjectName("min_v_label")
        self.formLayout.setWidget(0, QFormLayout.LabelRole, self.min_v_label)
        self.max_v_label = QLabel(self.formLayoutWidget)
        self.max_v_label.setObjectName("max_v_label")
        self.formLayout.setWidget(1, QFormLayout.LabelRole, self.max_v_label)
        self.step_v_label = QLabel(self.formLayoutWidget)
        self.step_v_label.setObjectName("step_v_label")
        self.formLayout.setWidget(2, QFormLayout.LabelRole, self.step_v_label)
        self.steprate_label = QLabel(self.formLayoutWidget)
        self.steprate_label.setObjectName("steprate_label")
        self.formLayout.setWidget(3, QFormLayout.LabelRole, self.steprate_label)
        self.min_v_val = QLineEdit(self.formLayoutWidget)
        self.min_v_val.setObjectName("min_v_val")
        self.formLayout.setWidget(0, QFormLayout.FieldRole, self.min_v_val)
        self.max_v_val = QLineEdit(self.formLayoutWidget)
        self.max_v_val.setObjectName("max_v_val")
        self.formLayout.setWidget(1, QFormLayout.FieldRole, self.max_v_val)
        self.step_v_val = QLineEdit(self.formLayoutWidget)
        self.step_v_val.setObjectName("step_v_val")
        self.formLayout.setWidget(2, QFormLayout.FieldRole, self.step_v_val)
        self.steprate_val = QLineEdit(self.formLayoutWidget)
        self.steprate_val.setObjectName("steprate_val")
        self.formLayout.setWidget(3, QFormLayout.FieldRole, self.steprate_val)
        self.input_label = QLabel(self.formLayoutWidget)
        self.input_label.setObjectName("input_label")
        self.output_label = QLabel(self.formLayoutWidget)
        self.output_label.setObjectName("output_label")
        self.formLayout.setWidget(4, QFormLayout.LabelRole, self.input_label)
        self.formLayout.setWidget(5, QFormLayout.LabelRole, self.output_label)
        self.in_chan_box = QSpinBox(self.formLayoutWidget)
        self.in_chan_box.setObjectName("in_chan_box")
        self.out_chan_box = QSpinBox(self.formLayoutWidget)
        self.out_chan_box.setObjectName("out_chan_box")
        self.formLayout.setWidget(4, QFormLayout.FieldRole, self.in_chan_box)
        self.formLayout.setWidget(5, QFormLayout.FieldRole, self.out_chan_box)
        self.sweepButton = QPushButton(self.centralwidget)
        self.sweepButton.setGeometry(QRect(10, 180, 161, 41))
        self.sweepButton.setObjectName("sweepButton")
        self.pauseButton = QPushButton(self.centralwidget)
        self.pauseButton.setGeometry(QRect(10, 230, 161, 41))
        self.pauseButton.setObjectName("pauseButton")
        
        self.menubar = QMenuBar(self)
        self.menubar.setGeometry(QRect(0, 0, 640, 21))
        self.menubar.setObjectName("menubar")
        self.setMenuBar(self.menubar)

        self.setWindowTitle("1D Sweep")
        self.sweep1d_label.setText("1D Sweep Parameters")
        self.min_v_label.setText("Min V")
        self.max_v_label.setText("Max V")
        self.step_v_label.setText("V Step")
        self.steprate_label.setText("Steps/sec")
        self.input_label.setText("Input Channel")
        self.output_label.setText("Output Channel")
        self.sweepButton.setText("Start Sweep")
        self.sweepButton.clicked.connect(self.init_sweep)
        self.pauseButton.setText("Pause Sweep")
        self.pauseButton.clicked.connect(self.pause)
        
        QMetaObject.connectSlotsByName(self)
        
    def create_frame(self):
        self.dpi = 100
        self.fig = Figure((5.0, 4.0), dpi=self.dpi)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setParent(self.centralwidget)
        self.canvas.setGeometry(QRect(250, 0, 400, 480))
        self.axes_v = self.fig.add_subplot(211, xlabel="Time (s)", ylabel="Voltage (V)")
        self.axes_c = self.fig.add_subplot(212, xlabel="Output Voltage (V)", ylabel="Input Voltage (V)")
        self.fig.tight_layout()
        
        self.setCentralWidget(self.centralwidget)
        
    def init_sweep(self):
        self.daq = self.parent.daq
        
        if self.daq is None:
            msg = QMessageBox()
            msg.setText("DAQ is not connected!")
            msg.setWindowTitle("Sweep Error")
            msg.setStandardButtons(QMessageBox.Close)
            msg.exec_()
            return
        
        self.v_start = float(self.min_v_val.text())
        self.v_end = float(self.max_v_val.text())
        
        try:
            self.v_step = float(self.step_v_val.text())
            if self.v_step > 0 and self.v_end < self.v_start:
                self.v_step = -1*self.v_step
        except ValueError:
            self.v_step = (self.v_end-self.v_start)/1000
        try:
            freq = float(self.steprate_val.text())
        except ValueError:
            freq = 10
        
        ichannel = "ai" + str(int(self.in_chan_box.value()))
        ochannel = "ao" + str(int(self.out_chan_box.value()))
        
        self.sweep_task = nidaqmx.Task()
        self.daq.submodules[ochannel].add_self_to_task(self.sweep_task)
        self.s = Sweep()
        self.s.follow_param(self.daq.submodules[ichannel].voltage)
        self.meas = self.s.init_sweep(self.daq.submodules[ochannel].voltage, self.v_start, self.v_end, self.v_step, freq)
        
        par = []
        par.append(self.axes_c)
        self.s.set_figs(self.fig, self.axes_v, par)
        
        initialise_or_create_database_at('C:\\Users\\erunb\\MeasureIt\\Databases\\testdb.db')
        qc.new_experiment(name='demotest3', sample_name='my best sample3')
        
        self.sweeping = True
        self.running = True
        self.curr_val = self.v_start
        self.run(ochannel)
        
    def run(self, ochannel):
        with self.meas.run() as datasaver:
            while abs(self.curr_val - self.v_end) > abs(self.v_step):
                if self.running is True:
                    data = self.s.iterate(datasaver)
                    self.curr_val = data[0][1]
            self.daq.submodules[ochannel].clear_task()
            self.sweep_task.close()
            self.sweeping = False
            self.running = False
        
    def pause(self):
        self.running = False
    
def main():
    app = QApplication(sys.argv)
    
    window = Sweep1DWindow()
    window.show()
    
    app.exec_()
    
    
if __name__ == "__main__":
    main()
    
    