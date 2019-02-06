import io, sys
import time
import numpy as np
import qcodes as qc
from qcodes.dataset.measurements import Measurement
from qcodes.dataset.database import initialise_or_create_database_at
from daq_driver import Daq
import PyQt5 as qt
from PyQt5.QtWidgets import QSizePolicy, QWidget, QApplication, QLabel, QMainWindow, QPushButton, QComboBox, QMessageBox, QLineEdit, QMenu, QMenuBar, QStatusBar, QGridLayout
from PyQt5.QtCore import Qt
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
#from IPython import display
from qcodes.dataset.data_export import get_data_by_id 
import nidaqmx


class Sweep(object):
    def __init__(self):
        self._sr830s = []
        self._params = []
    
    def follow_param(self, p):
        self._params.append(p)

    def follow_sr830(self, l, name, gain=1.0):
        self._sr830s.append((l, name, gain))

    def _create_measurement(self, *set_params):
        meas = Measurement()
        for p in set_params:
            meas.register_parameter(p)
        meas.register_custom_parameter('time', label='Time', unit='s')
        for p in self._params:
            meas.register_parameter(p, setpoints=(*set_params, 'time',))
        for l, _, _ in self._sr830s:
            meas.register_parameter(l.X, setpoints=(*set_params, 'time',))
            meas.register_parameter(l.Y, setpoints=(*set_params, 'time',))
        return meas
    
    def sweep(self, set_param, vals, inter_delay=None):
        plt.switch_backend('Qt5Agg')
        if inter_delay is not None:
            d = len(vals)*inter_delay
            h, m, s = int(d/3600), int(d/60) % 60, int(d) % 60
            print(f'Minimum duration: {h}h {m}m {s}s')

        fig = plt.figure(figsize=(4*(2 + len(self._params) + len(self._sr830s)),4))
        grid = plt.GridSpec(4, 1 + len(self._params) + len(self._sr830s), hspace=0)
        setax = fig.add_subplot(grid[:, 0])
        setax.set_xlabel('Time (s)')
        setax.set_ylabel(f'{set_param.label} ({set_param.unit})')
        setaxline = setax.plot([], [])[0]

        paxs = []
        plines = []
        for i, p in enumerate(self._params):
            ax = fig.add_subplot(grid[:, 1 + i])
            ax.set_xlabel(f'{set_param.label} ({set_param.unit})')
            ax.set_ylabel(f'{p.label} ({p.unit})')
            paxs.append(ax)
            plines.append(ax.plot([], [])[0])

        laxs = []
        llines = []
        for i, (l, name, _) in enumerate(self._sr830s):
            ax0 = fig.add_subplot(grid[:-1, 1 + len(self._params) + i])
            ax0.set_ylabel(f'{name} (V)')
            fmt = ScalarFormatter()
            fmt.set_powerlimits((-3, 3))
            ax0.get_yaxis().set_major_formatter(fmt)
            laxs.append(ax0)
            llines.append(ax0.plot([], [])[0])
            ax1 = fig.add_subplot(grid[-1, 1 + len(self._params) + i], sharex=ax0)
            ax1.set_ylabel('Phase (°)')
            ax1.set_xlabel(f'{set_param.label} ({set_param.unit})')
            laxs.append(ax1)
            llines.append(ax1.plot([], [])[0])
            plt.setp(ax0.get_xticklabels(), visible=False)

        fig.tight_layout()
        fig.show()

        meas = self._create_measurement(set_param)
        with meas.run() as datasaver:
            t0 = time.monotonic()
            for setpoint in vals:
                t = time.monotonic() - t0
                set_param.set(setpoint)
                
                setaxline.set_xdata(np.append(setaxline.get_xdata(), t))
                setaxline.set_ydata(np.append(setaxline.get_ydata(), setpoint))
                setax.relim()
                setax.autoscale_view()
                
                if inter_delay is not None:
                    plt.pause(inter_delay)

                data = [
                    (set_param, setpoint),
                    ('time', t)
                ]
                for i, p in enumerate(self._params):
                    v = p.get()
                    data.append((p, v))
                    plines[i].set_xdata(np.append(plines[i].get_xdata(), setpoint))
                    plines[i].set_ydata(np.append(plines[i].get_ydata(), v))
                    paxs[i].relim()
                    paxs[i].autoscale_view()


                datasaver.add_result(*data)
                
                fig.tight_layout()
                fig.canvas.draw()
                plt.show()
                plt.pause(0.001)

            d = time.monotonic() - t0
            h, m, s = int(d/3600), int(d/60) % 60, int(d) % 60
            print(f'Completed in: {h}h {m}m {s}s')

            b = io.BytesIO()
            fig.savefig(b, format='png')
#            display.display(display.Image(data=b.getbuffer(), format='png'))


def do_sweep():
    s=Sweep()
    daq=Daq("Dev1", "daq", 2, 24)
    initialise_or_create_database_at('C:\\Users\\erunb\\MeasureIt\\currentdatabase.db')
    qc.new_experiment(name='daqtest', sample_name='trying1')
    print(daq.ai2.voltage)
    s.follow_param(daq.ai2.voltage)
    writer=nidaqmx.Task()
    reader=nidaqmx.Task()
    daq.ao0.add_self_to_task(writer)
    daq.ai2.add_self_to_task(reader)
    s.sweep(daq.ao0.voltage, np.linspace(0,1,50), inter_delay=.01)
    
class MeasureItWindow(QMainWindow):
    
    def __init__(self, *args, **kwargs):
        super(MeasureItWindow, self).__init__(*args, **kwargs)
        
        self.daq=None
        try:
            self.daq = Daq("Dev1", "daq", 2, 24)
        except:
            print("Could not connect to the specified National Instruments DAQ")
        
        
        self.init_window()
        
        
        
    def init_window(self):
        self.setGeometry(50, 50, 640, 480)
        self.setWindowTitle("MeasureIt, Version Python")
        
        self.statusBar()
        
        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&File')
        editMenu = mainMenu.addMenu('&Edit')
        experimentMenu = mainMenu.addMenu('&Experiment')
        
        # Sweep button
        self.sweep_button = QPushButton('Sweep', self)
        self.sweep_button.clicked.connect(self.start_sweep)
        self.sweep_button.move(0,200)
        
        # Input channel selection
        self.input_chan_label = QLabel("Input Channel",self)
        self.input_chan_label.move(0,80)
        self.input_chan = QComboBox(self)
        self.input_chan.move(100,80)
        for ai in range(self.daq.get_ai_num()):
            self.input_chan.addItem(str(ai))
            
        self.input_chan.activated[str].connect(self.set_ai_text)
        
        # Output channel selection
        self.output_chan_label = QLabel("Output Channel",self)
        self.output_chan_label.move(0,50)
        self.output_chan = QComboBox(self)
        self.output_chan.move(100,50)
        
        for ao in range(self.daq.get_ao_num()):
            self.output_chan.addItem(str(ao))
        
        # Voltage sweep settings
        self.start_voltage_label = QLabel("Start voltage", self)
        self.end_voltage_label = QLabel("End voltage", self)
        self.v_step_label = QLabel("Voltage step", self)
        self.t_step_label = QLabel("Steps/second", self)
        
        
    def set_ai_text(self):
        pass
    
    def set_ao_text(self):
        pass
        
    def start_sweep(self):
        pass
        
    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Message',
            "Are you sure to quit?", QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            if self.daq is not None:
                self.daq.__del__()
                event.accept()
        else:
            event.ignore()
        

    
    
#    qc.dataset.experiment_container.experiments()
#    ex = qc.dataset.experiment_container.load_experiment(0)
    
#    fii = get_data_by_id(ex.data_sets()[0].run_id)
#    print(fii)
    
    
class Daq_Main_Window(QMainWindow):
    def __init__(self, *args, **kwargs):
        super(Daq_Main_Window, self).__init__(*args, **kwargs)
        
        self.daq=None
        try:
            self.daq = Daq("Dev1", "daq", 2, 24)
        except:
            print("Could not connect to the specified National Instruments DAQ")
        
        self.setupUi()
        
    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Message',
            "Are you sure to quit?", QMessageBox.Yes, QMessageBox.No)

        if reply == QMessageBox.Yes:
            if self.daq is not None:
                self.daq.__del__()
                event.accept()
        else:
            event.ignore()
        
    def setupUi(self):
        self.setObjectName("Main Window")
        self.resize(800, 338)
        self.centralwidget = QWidget(self)
        self.centralwidget.setObjectName("centralwidget")
        self.input_channels = QLabel(self.centralwidget)
        self.input_channels.setGeometry(qt.QtCore.QRect(20, 20, 73, 13))
        self.input_channels.setObjectName("input_channels")
        self.formLayoutWidget_3 = QWidget(self.centralwidget)
        self.formLayoutWidget_3.setGeometry(qt.QtCore.QRect(20, 50, 301, 231))
        self.formLayoutWidget_3.setObjectName("formLayoutWidget_3")
        self.gridLayout = QGridLayout(self.formLayoutWidget_3)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setObjectName("gridLayout")
        self.ai0_val = QLabel(self.formLayoutWidget_3)
        self.ai0_val.setObjectName("ai0_val")
        self.gridLayout.addWidget(self.ai0_val, 0, 1, 1, 1)
        self.ai13_label = QLabel(self.formLayoutWidget_3)
        self.ai13_label.setObjectName("ai13_label")
        self.gridLayout.addWidget(self.ai13_label, 5, 2, 1, 1)
        self.ai10_val = QLabel(self.formLayoutWidget_3)
        self.ai10_val.setObjectName("ai10_val")
        self.gridLayout.addWidget(self.ai10_val, 2, 3, 1, 1)
        self.ai11_label = QLabel(self.formLayoutWidget_3)
        self.ai11_label.setObjectName("ai11_label")
        self.gridLayout.addWidget(self.ai11_label, 3, 2, 1, 1)
        self.ai9_label = QLabel(self.formLayoutWidget_3)
        self.ai9_label.setObjectName("ai9_label")
        self.gridLayout.addWidget(self.ai9_label, 1, 2, 1, 1)
        self.ai14_label = QLabel(self.formLayoutWidget_3)
        self.ai14_label.setObjectName("ai14_label")
        self.gridLayout.addWidget(self.ai14_label, 6, 2, 1, 1)
        self.ai12_label = QLabel(self.formLayoutWidget_3)
        self.ai12_label.setObjectName("ai12_label")
        self.gridLayout.addWidget(self.ai12_label, 4, 2, 1, 1)
        self.ai10_label = QLabel(self.formLayoutWidget_3)
        self.ai10_label.setObjectName("ai10_label")
        self.gridLayout.addWidget(self.ai10_label, 2, 2, 1, 1)
        self.ai8_label = QLabel(self.formLayoutWidget_3)
        self.ai8_label.setObjectName("ai8_label")
        self.gridLayout.addWidget(self.ai8_label, 0, 2, 1, 1)
        self.ai9_val = QLabel(self.formLayoutWidget_3)
        self.ai9_val.setObjectName("ai9_val")
        self.gridLayout.addWidget(self.ai9_val, 1, 3, 1, 1)
        self.ai14_val = QLabel(self.formLayoutWidget_3)
        self.ai14_val.setObjectName("ai14_val")
        self.gridLayout.addWidget(self.ai14_val, 6, 3, 1, 1)
        self.ai13_val = QLabel(self.formLayoutWidget_3)
        self.ai13_val.setObjectName("ai13_val")
        self.gridLayout.addWidget(self.ai13_val, 5, 3, 1, 1)
        self.ai12_val = QLabel(self.formLayoutWidget_3)
        self.ai12_val.setObjectName("ai12_val")
        self.gridLayout.addWidget(self.ai12_val, 4, 3, 1, 1)
        self.ai15_val = QLabel(self.formLayoutWidget_3)
        self.ai15_val.setObjectName("ai15_val")
        self.gridLayout.addWidget(self.ai15_val, 7, 3, 1, 1)
        self.ai7_label = QLabel(self.formLayoutWidget_3)
        self.ai7_label.setObjectName("ai7_label")
        self.gridLayout.addWidget(self.ai7_label, 7, 0, 1, 1)
        self.ai7_val = QLabel(self.formLayoutWidget_3)
        self.ai7_val.setObjectName("ai7_val")
        self.gridLayout.addWidget(self.ai7_val, 7, 1, 1, 1)
        self.ai6_val = QLabel(self.formLayoutWidget_3)
        self.ai6_val.setObjectName("ai6_val")
        self.gridLayout.addWidget(self.ai6_val, 6, 1, 1, 1)
        self.ai15_label = QLabel(self.formLayoutWidget_3)
        self.ai15_label.setObjectName("ai15_label")
        self.gridLayout.addWidget(self.ai15_label, 7, 2, 1, 1)
        self.ai11_val = QLabel(self.formLayoutWidget_3)
        self.ai11_val.setObjectName("ai11_val")
        self.gridLayout.addWidget(self.ai11_val, 3, 3, 1, 1)
        self.ai8_val = QLabel(self.formLayoutWidget_3)
        self.ai8_val.setObjectName("ai8_val")
        self.gridLayout.addWidget(self.ai8_val, 0, 3, 1, 1)
        self.ai6_label = QLabel(self.formLayoutWidget_3)
        self.ai6_label.setObjectName("ai6_label")
        self.gridLayout.addWidget(self.ai6_label, 6, 0, 1, 1)
        self.ai1_label = QLabel(self.formLayoutWidget_3)
        self.ai1_label.setObjectName("ai1_label")
        self.gridLayout.addWidget(self.ai1_label, 1, 0, 1, 1)
        self.ai1_val = QLabel(self.formLayoutWidget_3)
        self.ai1_val.setObjectName("ai1_val")
        self.gridLayout.addWidget(self.ai1_val, 1, 1, 1, 1)
        self.ai2_val = QLabel(self.formLayoutWidget_3)
        self.ai2_val.setObjectName("ai2_val")
        self.gridLayout.addWidget(self.ai2_val, 2, 1, 1, 1)
        self.ai3_label = QLabel(self.formLayoutWidget_3)
        self.ai3_label.setObjectName("ai3_label")
        self.gridLayout.addWidget(self.ai3_label, 3, 0, 1, 1)
        self.ai5_label = QLabel(self.formLayoutWidget_3)
        self.ai5_label.setObjectName("ai5_label")
        self.gridLayout.addWidget(self.ai5_label, 5, 0, 1, 1)
        self.ai4_label = QLabel(self.formLayoutWidget_3)
        self.ai4_label.setObjectName("ai4_label")
        self.gridLayout.addWidget(self.ai4_label, 4, 0, 1, 1)
        self.ai0_label = QLabel(self.formLayoutWidget_3)
        self.ai0_label.setObjectName("ai0_label")
        self.gridLayout.addWidget(self.ai0_label, 0, 0, 1, 1)
        self.ai3_val = QLabel(self.formLayoutWidget_3)
        self.ai3_val.setObjectName("ai3_val")
        self.gridLayout.addWidget(self.ai3_val, 3, 1, 1, 1)
        self.ai2_label = QLabel(self.formLayoutWidget_3)
        self.ai2_label.setObjectName("ai2_label")
        self.gridLayout.addWidget(self.ai2_label, 2, 0, 1, 1)
        self.ai5_val = QLabel(self.formLayoutWidget_3)
        self.ai5_val.setObjectName("ai5_val")
        self.gridLayout.addWidget(self.ai5_val, 5, 1, 1, 1)
        self.ai4_val = QLabel(self.formLayoutWidget_3)
        self.ai4_val.setObjectName("ai4_val")
        self.gridLayout.addWidget(self.ai4_val, 4, 1, 1, 1)
        self.output_channels = QLabel(self.centralwidget)
        self.output_channels.setGeometry(qt.QtCore.QRect(410, 10, 81, 20))
        self.output_channels.setObjectName("output_channels")
        self.formLayoutWidget_2 = QWidget(self.centralwidget)
        self.formLayoutWidget_2.setGeometry(qt.QtCore.QRect(410, 80, 201, 61))
        self.formLayoutWidget_2.setObjectName("formLayoutWidget_2")
        self.OutputChannels = QGridLayout(self.formLayoutWidget_2)
        self.OutputChannels.setContentsMargins(0, 0, 0, 0)
        self.OutputChannels.setObjectName("OutputChannels")
        self.ao1_val = QLabel(self.formLayoutWidget_2)
        self.ao1_val.setObjectName("ao1_val")
        self.OutputChannels.addWidget(self.ao1_val, 1, 1, 1, 1)
        self.ao0_label = QLabel(self.formLayoutWidget_2)
        self.ao0_label.setObjectName("ao0_label")
        self.OutputChannels.addWidget(self.ao0_label, 0, 0, 1, 1)
        self.ao1_label = QLabel(self.formLayoutWidget_2)
        self.ao1_label.setObjectName("ao1_label")
        self.OutputChannels.addWidget(self.ao1_label, 1, 0, 1, 1)
        self.ao0_val = QLabel(self.formLayoutWidget_2)
        self.ao0_val.setObjectName("ao0_val")
        self.OutputChannels.addWidget(self.ao0_val, 0, 1, 1, 1)
        self.ao0_set = QLineEdit(self.formLayoutWidget_2)
        self.ao0_set.setObjectName("ao0_set")
        self.ao0_set.setMaximumSize(61,20)
        self.ao0_set.setSizePolicy(QSizePolicy(0,0))
        self.OutputChannels.addWidget(self.ao0_set, 0, 2, 1, 1)
        self.ao1_set = QLineEdit(self.formLayoutWidget_2)
        self.ao1_set.setObjectName("ao1_set")
        self.ao1_set.setMaximumSize(61,20)
        self.OutputChannels.addWidget(self.ao1_set, 1, 2, 1, 1)
        self.updateButton = QPushButton(self.centralwidget)
        self.updateButton.setGeometry(qt.QtCore.QRect(410, 170, 201, 61))
        self.updateButton.setObjectName("updateButton")
        self.updateButton.clicked.connect(self.set_vals)
        self.out_cha = QLabel(self.centralwidget)
        self.out_cha.setGeometry(qt.QtCore.QRect(410, 50, 61, 20))
        self.out_cha.setObjectName("out_cha")
        self.out_val = QLabel(self.centralwidget)
        self.out_val.setGeometry(qt.QtCore.QRect(480, 40, 61, 41))
        self.out_val.setObjectName("out_val")
        self.out_set = QLabel(self.centralwidget)
        self.out_set.setGeometry(qt.QtCore.QRect(550, 50, 51, 20))
        self.out_set.setObjectName("out_set")
        self.setCentralWidget(self.centralwidget)
        
        # Menu Bar
        self.menubar = QMenuBar(self)
        self.menubar.setGeometry(qt.QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        self.menuExperiments = QMenu(self.menubar)
        self.menuExperiments.setObjectName("menuExperiments")
        
        self.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(self)
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuExperiments.menuAction())

        self.set_label_names()
        self.input_vals = [self.ai0_val, self.ai1_val, self.ai2_val, self.ai3_val, self.ai4_val, self.ai5_val, self.ai6_val, 
                           self.ai7_val, self.ai8_val, self.ai9_val, self.ai10_val, self.ai11_val, self.ai12_val, self.ai13_val, 
                           self.ai14_val, self.ai15_val]
        self.output_vals = [self.ao0_val, self.ao1_val]
        
        
        self.update_vals()
        
        qt.QtCore.QMetaObject.connectSlotsByName(self)

    def set_label_names(self):
        self.setWindowTitle("DAQ Controller - MeasureIt")
        self.input_channels.setText("Input Channels")
        self.ai0_val.setText("TextLabel")
        self.ai13_label.setText("AI13")
        self.ai10_val.setText("TextLabel")
        self.ai11_label.setText("AI11")
        self.ai9_label.setText("AI9")
        self.ai14_label.setText("AI14")
        self.ai12_label.setText("AI12")
        self.ai10_label.setText("AI10")
        self.ai8_label.setText("AI8")
        self.ai9_val.setText("TextLabel")
        self.ai14_val.setText("TextLabel")
        self.ai13_val.setText("TextLabel")
        self.ai12_val.setText("TextLabel")
        self.ai15_val.setText("TextLabel")
        self.ai7_label.setText("AI7")
        self.ai6_val.setText("TextLabel")
        self.ai7_val.setText("TextLabel")
        self.ai15_label.setText("AI15")
        self.ai11_val.setText("TextLabel")
        self.ai8_val.setText("TextLabel")
        self.ai6_label.setText("AI6")
        self.ai1_label.setText("AI1")
        self.ai1_val.setText("TextLabel")
        self.ai2_val.setText("TextLabel")
        self.ai3_label.setText("AI3")
        self.ai5_label.setText("AI5")
        self.ai4_label.setText("AI4")
        self.ai0_label.setText("AI0")
        self.ai3_val.setText("TextLabel")
        self.ai2_label.setText("AI2")
        self.ai5_val.setText("TextLabel")
        self.ai4_val.setText("TextLabel")
        self.output_channels.setText("Output Channels")
        self.ao1_val.setText("TextLabel")
        self.ao0_label.setText("AO0")
        self.ao1_label.setText("AO1")
        self.ao0_val.setText("TextLabel")
        self.updateButton.setText("Update Output")
        self.out_cha.setText("Channel")
        self.out_val.setText("Value")
        self.out_set.setText("Set Value")
        self.menuFile.setTitle("File")
        self.menuExperiments.setTitle("Experiments")

    def update_vals(self):
        if self.daq is not None:
            self.daq.update_all_inputs()
            for num, label in enumerate(self.input_vals):
                name = "ai"+str(num)
                channel = self.daq.submodules[name]
                label.setText(str(channel.get("voltage"))[0:7])
                
            for num, label in enumerate(self.output_vals):
                name = "ao"+str(num)
                channel = self.daq.submodules[name]
                label.setText(str(channel.get("voltage"))[0:7])
    
    def set_vals(self):
        if self.daq is not None:
            value0 = self.ao0_set.text()
            value1 = self.ao1_set.text()
            
            if value0.isdigit():
                task=nidaqmx.Task()
                self.daq.submodules["ao0"].add_self_to_task(task)
                self.daq.ao0.set("voltage", float(value0))
                self.daq.submodules["ao0"].clear_task()
                task.close()
            if value1.isdigit():
                task=nidaqmx.Task()
                self.daq.submodules["ao1"].add_self_to_task(task)
                self.daq.ao1.set("voltage", float(value1))
                self.daq.submodules["ao1"].clear_task()
            
            self.update_vals()
            
def main():
#    do_sweep()
    app = QApplication(sys.argv)
    
    window = Daq_Main_Window()
    window.show()
    
    app.exec_()
    
    
if __name__ == "__main__":
    main()
    
    
    
    