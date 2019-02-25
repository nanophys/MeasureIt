import PyQt5.Qt as qt
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import sys, time
import matplotlib
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from sweep import Sweep, SweepThread
from daq_driver import _value_parser, Daq
import qcodes as qc
import nidaqmx
from qcodes.dataset.measurements import Measurement
from qcodes.dataset.database import initialise_or_create_database_at

class Sweep1DWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__()
        self.parent=parent
        self.sweeping = False
        self.running = False
        self.daq = self.parent.daq
        
        self.setupUi()
        self.create_frame()
        
    def setupUi(self):
        self.setObjectName("1D Sweep")
        self.resize(640, 480)
        self.centralwidget = QWidget(self)
        self.centralwidget.setObjectName("centralwidget")
        self.sweep1d_label = QLabel(self.centralwidget)
        self.sweep1d_label.setGeometry(QRect(9, 9, 106, 16))
        self.sweep1d_label.setObjectName("sweep1d_label")
        self.formLayoutWidget = QWidget(self.centralwidget)
        self.formLayoutWidget.setGeometry(QRect(10, 40, 160, 166))
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
        self.formLayout.setWidget(4, QFormLayout.LabelRole, self.input_label)
        self.factor_label = QLabel(self.formLayoutWidget)
        self.factor_label.setObjectName("factor_label")
        self.formLayout.setWidget(5, QFormLayout.LabelRole, self.factor_label)
        self.output_label = QLabel(self.formLayoutWidget)
        self.output_label.setObjectName("output_label")
        self.factor_val = QLineEdit(self.formLayoutWidget)
        self.factor_val.setObjectName("factor_val")
        self.formLayout.setWidget(5, QFormLayout.FieldRole, self.factor_val)
        self.factor_box = QComboBox(self.formLayoutWidget)
        self.factor_box.setObjectName("factor_box")
        self.formLayout.setWidget(6, QFormLayout.FieldRole, self.factor_box)
        self.factor_box.addItem("A/V")
        self.factor_box.addItem("V/V")
        self.formLayout.setWidget(7, QFormLayout.LabelRole, self.output_label)
        self.in_chan_box = QComboBox(self.formLayoutWidget)
        self.in_chan_box.setObjectName("in_chan_box")
        self.out_chan_box = QComboBox(self.formLayoutWidget)
        self.out_chan_box.setObjectName("out_chan_box")
        self.formLayout.setWidget(4, QFormLayout.FieldRole, self.in_chan_box)
        self.formLayout.setWidget(7, QFormLayout.FieldRole, self.out_chan_box)
        for ai in range(self.daq.ai_num):
            self.in_chan_box.addItem(str(ai))
        for ao in range(self.daq.ao_num):
            self.out_chan_box.addItem(str(ao))
        self.sweepButton = QPushButton(self.centralwidget)
        self.sweepButton.setGeometry(QRect(10, 220, 161, 41))
        self.sweepButton.setObjectName("sweepButton")
        self.pauseButton = QPushButton(self.centralwidget)
        self.pauseButton.setGeometry(QRect(10, 270, 161, 41))
        self.pauseButton.setObjectName("pauseButton")
        
        self.dbfile_label = QLabel(self.centralwidget)
        self.dbfile_label.setObjectName("dbfile_label")
        self.dbfile = QLabel(self.centralwidget)
        self.dbfile.setObjectName("db file")
        
        self.sample_label = QLabel(self.centralwidget)
        self.sample_label.setObjectName("sample_label")
        self.sample_label.move(10, 400)
        self.sample = QLabel(self.centralwidget)
        self.sample.setObjectName("sample")
        self.sample.move(60, 400)
        self.edit_file_button = QPushButton(self.centralwidget)
        self.edit_file_button.setGeometry(QRect(10, 350, 161, 41))
        self.edit_file_button.setObjectName("db_button")
        
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
        self.factor_label.setText("Input Factor")
        self.output_label.setText("Output Channel")
        self.dbfile_label.setText("Database File:")
        self.sample_label.setText("Sample Name:")
        self.sweepButton.setText("Start Sweep")
        self.sweepButton.clicked.connect(self.init_sweep)
        self.pauseButton.setText("Pause Sweep")
        self.pauseButton.clicked.connect(self.pause)
        self.edit_file_button.setText("Edit . . .")
        self.edit_file_button.clicked.connect(self.select_db_file)
        
        QMetaObject.connectSlotsByName(self)
        
    def select_db_file(self):
        box = QFileDialog()
        box.setFileMode(QFileDialog.AnyFile)
        box.setNameFilter("Database files (*.db)")
        box.fileSelected.connect(self.set_file)
        
        box.exec_()

    def set_file(self, file):
        self.db_name = file
        self.dbfile_label.setText(self.db_name)
        
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
        if self.daq is None:
            msg = QMessageBox()
            msg.setText("DAQ is not connected!")
            msg.setWindowTitle("Sweep Error")
            msg.setStandardButtons(QMessageBox.Close)
            msg.exec_()
            return
        
        self.v_start = _value_parser(self.min_v_val.text())
        self.v_end = _value_parser(self.max_v_val.text())
        
        try:
            self.v_step = float(self.step_v_val.text())
            if self.v_step > 0 and self.v_end < self.v_start:
                self.v_step = -1*self.v_step
        except ValueError:
            self.v_step = (self.v_end-self.v_start)/1000
        try:
            self.freq = float(self.steprate_val.text())
        except ValueError:
            self.freq = 10
        
        ichannel = "ai" + str(int(self.in_chan_box.currentText()))
        self.ochannel = "ao" + str(int(self.out_chan_box.currentText()))
        
        self.sweep_task = nidaqmx.Task()
        self.daq.submodules[self.ochannel].add_self_to_task(self.sweep_task)
        self.s = Sweep()
        self.s.follow_param(self.daq.submodules[ichannel].voltage)
        self.meas = self.s.init_sweep(self.daq.submodules[self.ochannel].voltage, self.v_start, self.v_end, self.v_step, self.freq)
        
        self.counter=0
        self.init_plot(self.daq.submodules[self.ochannel].voltage, self.daq.submodules[ichannel].voltage)
        
        initialise_or_create_database_at('C:\\Users\\erunb\\MeasureIt\\Databases\\testdb.db')
        qc.new_experiment(name='demotest3', sample_name='my best sample3')
        
        self.sweeping = True
        self.running = True
        self.curr_val = self.v_start
        self.run()
        
    def run(self):
        self.pauseButton.setText("Pause Sweep")
        self.sweepThread = SweepThread(self, self.s)
        self.sweepThread.start()
        
    def init_plot(self, set_param, p):
        self.axes_v.set_xlabel('Time (s)')
        self.axes_v.set_ylabel(f'{set_param.label} ({set_param.unit})')
        self.setaxline = self.axes_v.plot([], [])[0]
        
        self.axes_c.set_xlabel(f'{set_param.label} ({set_param.unit})')
        self.axes_c.set_ylabel(f'{p.label} ({p.unit})')

        self.plines = self.axes_c.plot([], [])[0]
        
    def update_plot(self, data):
        self.setaxline.set_xdata(np.append(self.setaxline.get_xdata(), data[1][1]))
        self.setaxline.set_ydata(np.append(self.setaxline.get_ydata(), data[0][1]))
        self.axes_v.relim()
        self.axes_v.autoscale_view()
        
        self.plines.set_xdata(np.append(self.plines.get_xdata(), data[0][1]))
        self.plines.set_ydata(np.append(self.plines.get_ydata(), data[2][1]))
        self.axes_c.relim()
        self.axes_c.autoscale_view()
        
        if self.counter % int(self.freq/2) == 0:
            self.fig.tight_layout()
            self.fig.canvas.draw()
        self.counter += 1
        
    def thread_finished(self):
        self.daq.submodules[self.ochannel].clear_task()
        self.sweeping = False
        self.running = False
        
        msg = QMessageBox()
        msg.setText("Sweep finished")
        msg.setWindowTitle("Info")
        msg.setStandardButtons(QMessageBox.Close)
        msg.exec_()
        
    def pause(self):
        if self.sweeping == True and self.running == True:
            self.pauseButton.setText("Resume Sweep")
            self.running = False
        elif self.sweeping == True and self.running == False:
            self.sweepThread.quit()
            self.sweepThread.wait()
            self.running = True
            self.run()
    
def main():
    app = QApplication(sys.argv)
    
    window = Sweep1DWindow()
    window.show()
    
    app.exec_()
    
    
if __name__ == "__main__":
    main()
    
    