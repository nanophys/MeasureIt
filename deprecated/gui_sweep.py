import importlib
import sys

# from IPython import display
import nidaqmx
import PyQt5 as qt
from daq_driver import Daq
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QWidget,
)
from sweep_window import Sweep1DWindow

#    qc.dataset.experiment_container.experiments()
#    ex = qc.dataset.experiment_container.load_experiment(0)

#    fii = get_data_by_id(ex.data_sets()[0].run_id)
#    print(fii)


class Daq_Main_Window(QMainWindow):
    def __init__(self, *args, **kwargs):
        super(Daq_Main_Window, self).__init__(*args, **kwargs)

        self.daq = None

        self.connect()
        self.setupUi()

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, "Message", "Are you sure to quit?", QMessageBox.Yes, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.daq is not None:
                self.daq.__del__()
                event.accept()
        else:
            event.ignore()

    def connect(self):
        try:
            importlib.reload(nidaqmx)
            self.daq = Daq("Dev1", "daq")
        except:
            msg = QMessageBox()
            msg.setText("Could not connect to the DAQ")
            msg.setWindowTitle("Connection Attempt")
            msg.setStandardButtons(QMessageBox.Close)
            msg.exec_()

    def reconnect(self):
        if self.daq is not None:
            msg = QMessageBox()
            msg.setText("Already connected to a DAQ")
            msg.setWindowTitle("Connection Attempt")
            msg.setStandardButtons(QMessageBox.Close)
            msg.exec_()
        else:
            self.connect()

    def setupUi(self):
        self.setObjectName("Main Window")
        self.resize(800, 338)
        self.centralwidget = QWidget(self)
        self.centralwidget.setObjectName("centralwidget")
        self.input_channels = QLabel(self.centralwidget)
        self.input_channels.setGeometry(qt.QtCore.QRect(20, 20, 73, 13))
        self.input_channels.setObjectName("input_channels")
        self.ai_grid = QWidget(self.centralwidget)
        self.ai_grid.setGeometry(qt.QtCore.QRect(20, 50, 301, 231))
        self.ai_grid.setObjectName("ai_grid")
        self.gridLayout = QGridLayout(self.ai_grid)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)
        self.gridLayout.setObjectName("gridLayout")
        self.ai0_val = QLabel(self.ai_grid)
        self.ai0_val.setObjectName("ai0_val")
        self.gridLayout.addWidget(self.ai0_val, 0, 1, 1, 1)
        self.ai21_label = QLabel(self.ai_grid)
        self.ai21_label.setObjectName("ai21_label")
        self.gridLayout.addWidget(self.ai21_label, 5, 2, 1, 1)
        self.ai18_val = QLabel(self.ai_grid)
        self.ai18_val.setObjectName("ai18_val")
        self.gridLayout.addWidget(self.ai18_val, 2, 3, 1, 1)
        self.ai19_label = QLabel(self.ai_grid)
        self.ai19_label.setObjectName("ai19_label")
        self.gridLayout.addWidget(self.ai19_label, 3, 2, 1, 1)
        self.ai17_label = QLabel(self.ai_grid)
        self.ai17_label.setObjectName("ai17_label")
        self.gridLayout.addWidget(self.ai17_label, 1, 2, 1, 1)
        self.ai22_label = QLabel(self.ai_grid)
        self.ai22_label.setObjectName("ai22_label")
        self.gridLayout.addWidget(self.ai22_label, 6, 2, 1, 1)
        self.ai20_label = QLabel(self.ai_grid)
        self.ai20_label.setObjectName("ai20_label")
        self.gridLayout.addWidget(self.ai20_label, 4, 2, 1, 1)
        self.ai18_label = QLabel(self.ai_grid)
        self.ai18_label.setObjectName("ai18_label")
        self.gridLayout.addWidget(self.ai18_label, 2, 2, 1, 1)
        self.ai16_label = QLabel(self.ai_grid)
        self.ai16_label.setObjectName("ai16_label")
        self.gridLayout.addWidget(self.ai16_label, 0, 2, 1, 1)
        self.ai17_val = QLabel(self.ai_grid)
        self.ai17_val.setObjectName("ai17_val")
        self.gridLayout.addWidget(self.ai17_val, 1, 3, 1, 1)
        self.ai22_val = QLabel(self.ai_grid)
        self.ai22_val.setObjectName("ai22_val")
        self.gridLayout.addWidget(self.ai22_val, 6, 3, 1, 1)
        self.ai21_val = QLabel(self.ai_grid)
        self.ai21_val.setObjectName("ai21_val")
        self.gridLayout.addWidget(self.ai21_val, 5, 3, 1, 1)
        self.ai20_val = QLabel(self.ai_grid)
        self.ai20_val.setObjectName("ai20_val")
        self.gridLayout.addWidget(self.ai20_val, 4, 3, 1, 1)
        self.ai23_val = QLabel(self.ai_grid)
        self.ai23_val.setObjectName("ai23_val")
        self.gridLayout.addWidget(self.ai23_val, 7, 3, 1, 1)
        self.ai7_label = QLabel(self.ai_grid)
        self.ai7_label.setObjectName("ai7_label")
        self.gridLayout.addWidget(self.ai7_label, 7, 0, 1, 1)
        self.ai7_val = QLabel(self.ai_grid)
        self.ai7_val.setObjectName("ai7_val")
        self.gridLayout.addWidget(self.ai7_val, 7, 1, 1, 1)
        self.ai6_val = QLabel(self.ai_grid)
        self.ai6_val.setObjectName("ai6_val")
        self.gridLayout.addWidget(self.ai6_val, 6, 1, 1, 1)
        self.ai23_label = QLabel(self.ai_grid)
        self.ai23_label.setObjectName("ai23_label")
        self.gridLayout.addWidget(self.ai23_label, 7, 2, 1, 1)
        self.ai19_val = QLabel(self.ai_grid)
        self.ai19_val.setObjectName("ai19_val")
        self.gridLayout.addWidget(self.ai19_val, 3, 3, 1, 1)
        self.ai16_val = QLabel(self.ai_grid)
        self.ai16_val.setObjectName("ai16_val")
        self.gridLayout.addWidget(self.ai16_val, 0, 3, 1, 1)
        self.ai6_label = QLabel(self.ai_grid)
        self.ai6_label.setObjectName("ai6_label")
        self.gridLayout.addWidget(self.ai6_label, 6, 0, 1, 1)
        self.ai1_label = QLabel(self.ai_grid)
        self.ai1_label.setObjectName("ai1_label")
        self.gridLayout.addWidget(self.ai1_label, 1, 0, 1, 1)
        self.ai1_val = QLabel(self.ai_grid)
        self.ai1_val.setObjectName("ai1_val")
        self.gridLayout.addWidget(self.ai1_val, 1, 1, 1, 1)
        self.ai2_val = QLabel(self.ai_grid)
        self.ai2_val.setObjectName("ai2_val")
        self.gridLayout.addWidget(self.ai2_val, 2, 1, 1, 1)
        self.ai3_label = QLabel(self.ai_grid)
        self.ai3_label.setObjectName("ai3_label")
        self.gridLayout.addWidget(self.ai3_label, 3, 0, 1, 1)
        self.ai5_label = QLabel(self.ai_grid)
        self.ai5_label.setObjectName("ai5_label")
        self.gridLayout.addWidget(self.ai5_label, 5, 0, 1, 1)
        self.ai4_label = QLabel(self.ai_grid)
        self.ai4_label.setObjectName("ai4_label")
        self.gridLayout.addWidget(self.ai4_label, 4, 0, 1, 1)
        self.ai0_label = QLabel(self.ai_grid)
        self.ai0_label.setObjectName("ai0_label")
        self.gridLayout.addWidget(self.ai0_label, 0, 0, 1, 1)
        self.ai3_val = QLabel(self.ai_grid)
        self.ai3_val.setObjectName("ai3_val")
        self.gridLayout.addWidget(self.ai3_val, 3, 1, 1, 1)
        self.ai2_label = QLabel(self.ai_grid)
        self.ai2_label.setObjectName("ai2_label")
        self.gridLayout.addWidget(self.ai2_label, 2, 0, 1, 1)
        self.ai5_val = QLabel(self.ai_grid)
        self.ai5_val.setObjectName("ai5_val")
        self.gridLayout.addWidget(self.ai5_val, 5, 1, 1, 1)
        self.ai4_val = QLabel(self.ai_grid)
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
        self.ao0_set.setMaximumSize(61, 20)
        self.ao0_set.setSizePolicy(QSizePolicy(0, 0))
        self.OutputChannels.addWidget(self.ao0_set, 0, 2, 1, 1)
        self.ao1_set = QLineEdit(self.formLayoutWidget_2)
        self.ao1_set.setObjectName("ao1_set")
        self.ao1_set.setMaximumSize(61, 20)
        self.OutputChannels.addWidget(self.ao1_set, 1, 2, 1, 1)
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

        # Buttons
        self.updateButton = QPushButton(self.centralwidget)
        self.updateButton.setGeometry(qt.QtCore.QRect(410, 170, 201, 41))
        self.updateButton.setObjectName("updateButton")
        self.updateButton.clicked.connect(self.set_vals)
        self.connectButton = QPushButton(self.centralwidget)
        self.connectButton.setGeometry(qt.QtCore.QRect(410, 220, 201, 41))
        self.connectButton.setObjectName("connectButton")
        self.connectButton.clicked.connect(self.reconnect)

        # Menu Bar
        self.menubar = QMenuBar(self)
        self.menubar.setGeometry(qt.QtCore.QRect(0, 0, 800, 21))
        self.menubar.setObjectName("menubar")

        # File Menu
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        quitAction = QAction("&Quit", self)
        quitAction.triggered.connect(self.close)
        self.menuFile.addAction(quitAction)

        # Experiment Menu
        self.menuExperiments = QMenu(self.menubar)
        self.menuExperiments.setObjectName("menuExperiments")
        sweep1dAction = QAction("&1D Sweep", self)
        sweep1dAction.triggered.connect(self.disp_1D_Sweep)
        self.menuExperiments.addAction(sweep1dAction)
        sweep2dAction = QAction("&2D Sweep", self)
        sweep2dAction.triggered.connect(self.disp_2D_Sweep)
        self.menuExperiments.addAction(sweep2dAction)

        self.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(self)
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuExperiments.menuAction())

        self.set_label_names()
        self.input_vals = [
            self.ai0_val,
            self.ai1_val,
            self.ai2_val,
            self.ai3_val,
            self.ai4_val,
            self.ai5_val,
            self.ai6_val,
            self.ai7_val,
            self.ai16_val,
            self.ai17_val,
            self.ai18_val,
            self.ai19_val,
            self.ai20_val,
            self.ai21_val,
            self.ai22_val,
            self.ai23_val,
        ]
        self.output_vals = [self.ao0_val, self.ao1_val]

        self.update_vals()

        qt.QtCore.QMetaObject.connectSlotsByName(self)

    def disp_1D_Sweep(self):
        self.sweep_window = Sweep1DWindow(parent=self)
        self.sweep_window.show()

    def disp_2D_Sweep(self):
        pass

    def set_label_names(self):
        self.setWindowTitle("DAQ Controller - MeasureIt")
        self.input_channels.setText("Input Channels")
        self.ai0_val.setText("TextLabel")
        self.ai21_label.setText("AI21")
        self.ai18_val.setText("TextLabel")
        self.ai19_label.setText("AI19")
        self.ai17_label.setText("AI17")
        self.ai22_label.setText("AI22")
        self.ai20_label.setText("AI20")
        self.ai18_label.setText("AI18")
        self.ai16_label.setText("AI16")
        self.ai17_val.setText("TextLabel")
        self.ai22_val.setText("TextLabel")
        self.ai21_val.setText("TextLabel")
        self.ai20_val.setText("TextLabel")
        self.ai16_val.setText("TextLabel")
        self.ai7_label.setText("AI7")
        self.ai6_val.setText("TextLabel")
        self.ai7_val.setText("TextLabel")
        self.ai23_label.setText("AI23")
        self.ai19_val.setText("TextLabel")
        self.ai23_val.setText("TextLabel")
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
        self.connectButton.setText("Connect DAQ")
        self.out_cha.setText("Channel")
        self.out_val.setText("Value")
        self.out_set.setText("Set Value")
        self.menuFile.setTitle("File")
        self.menuExperiments.setTitle("Experiments")

    def update_vals(self):
        if self.daq is not None:
            self.daq.update_all_inputs()
            for n, num in enumerate(
                [0, 1, 2, 3, 4, 5, 6, 7, 16, 17, 18, 19, 20, 21, 22, 23]
            ):
                name = "ai" + str(num)
                channel = self.daq.submodules[name]
                self.input_vals[n].setText(str(channel.get("voltage"))[0:7])

            for n, num in enumerate([0, 1]):
                name = "ao" + str(num)
                channel = self.daq.submodules[name]
                self.output_vals[n].setText(str(channel.get("voltage"))[0:7])

    def set_vals(self):
        if self.daq is not None:
            invalid = 0
            try:
                value0 = float(self.ao0_set.text())

                task = nidaqmx.Task()
                self.daq.submodules["ao0"].add_self_to_task(task)
                self.daq.ao0.set("voltage", float(value0))
                self.daq.submodules["ao0"].clear_task()
                task.close()

            except ValueError:
                invalid += 1

            try:
                value1 = float(self.ao1_set.text())

                task = nidaqmx.Task()
                self.daq.submodules["ao1"].add_self_to_task(task)
                self.daq.ao1.set("voltage", float(value1))
                self.daq.submodules["ao1"].clear_task()
                task.close()
            except ValueError:
                invalid += 1

            if invalid == 2:
                msg = QMessageBox()
                msg.setText("No valid inputs given")
                msg.setWindowTitle("Error")
                msg.setStandardButtons(QMessageBox.Close)
                msg.exec_()

            self.update_vals()


def main():
    #    do_sweep()
    app = QApplication(sys.argv)

    window = Daq_Main_Window()
    window.show()

    app.exec_()


if __name__ == "__main__":
    main()
