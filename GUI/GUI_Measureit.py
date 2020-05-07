from PyQt5 import QtWidgets,QtCore,QtGui
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QTableWidgetItem, QMessageBox, QFileDialog,\
    QPushButton, QCheckBox, QHeaderView, QLineEdit, QDialog
from PyQt5.QtGui import QTextCursor
import sys,os
from datetime import datetime
import yaml
import matplotlib
from mainwindow_ui import Ui_MeasureIt
from GUI_Dialogs import *
from handlers import WriteStream, OutputThread
from queue import Queue

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
matplotlib.use('Qt5Agg')

sys.path.append("..")
import src
from src.daq_driver import Daq, DaqAOChannel, DaqAIChannel
from src.util import _value_parser, _name_parser
from src.sweep0d import Sweep0D
from src.sweep1d import Sweep1D
import qcodes as qc
from qcodes import Station, initialise_or_create_database_at
from qcodes.logger.logger import start_all_logging
from qcodes.dataset.data_set import DataSet
from qcodes.instrument_drivers.Lakeshore.Model_372 import Model_372
from qcodes.instrument_drivers.american_magnetics.AMI430 import AMI430
from qcodes.instrument_drivers.stanford_research.SR860 import SR860
from qcodes.instrument_drivers.tektronix.Keithley_2450 import Keithley2450
from qcodes.tests.instrument_mocks import DummyInstrument

class UImain(QtWidgets.QMainWindow):
    
     # To add an instrument, import the driver then add it to our instrument 
     # dictionary with the name as the key, and the class as the value
    SUPPORTED_INSTRUMENTS = {'Dummy':DummyInstrument,
                             'NI DAQ':Daq, 
                             'Model_372':Model_372, 
                             'AMI430':AMI430, 
                             'SR860':SR860, 
                             'Keithley2450':Keithley2450}
    
    def __init__(self, parent = None, config_file = None):
        super(UImain,self).__init__(parent)
        self.ui = Ui_MeasureIt()
        self.ui.setupUi(self)
        self.setWindowTitle("MeasureIt")
        self.ui.scanValue.setText('False')
        self.ui.scanValue.setStyleSheet('color: red')
        
        self.init_tables()
        self.make_connections()

        self.station = None
        self.sweep = None
        self.devices = {}
        self.actions = {}
        self.track_params = {}
        self.set_params = {}
        self.shown_follow_params = []
        self.shown_set_params = []
        
        self.db = ''
        self.exp_name = ''
        self.sample_name = ''
        self.db_set = False
        self.datasets = []
        
        self.load_station_and_connect_instruments(config_file)
        
        self.start_logs()
        
        # Create Queue and redirect sys.stdout to this queue
        queue = Queue()
        sys.stdout = WriteStream(queue)
    
        self.thread = OutputThread(queue)
        self.thread.mysignal.connect(self.append_stdout)
        self.thread.start()
        
        self.show()
    
    
    def init_tables(self):
        follow_header = self.ui.followParamTable.horizontalHeader()
        follow_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        follow_header.resizeSection(0, 60)
        follow_header.setSectionResizeMode(1, QHeaderView.Fixed)
        follow_header.resizeSection(1, 60)
        follow_header.setSectionResizeMode(2, QHeaderView.Stretch)
        follow_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        follow_header.setSectionResizeMode(4, QHeaderView.Fixed)
        follow_header.resizeSection(4, 40)
        
        output_header = self.ui.outputParamTable.horizontalHeader()
        output_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        output_header.resizeSection(0, 60)
        output_header.setSectionResizeMode(1, QHeaderView.Fixed)
        output_header.resizeSection(1, 60)
        output_header.setSectionResizeMode(2, QHeaderView.Stretch)
        output_header.setSectionResizeMode(3, QHeaderView.Fixed)
        output_header.resizeSection(3, 40)
        output_header.setSectionResizeMode(4, QHeaderView.Fixed)
        output_header.resizeSection(4, 40)
        
        
    def make_connections(self):
        self.ui.editParameterButton.clicked.connect(self.edit_parameters)
        self.ui.startButton.clicked.connect(self.start_sweep)
        self.ui.pauseButton.clicked.connect(self.pause_resume_sweep)
        self.ui.flipDirectionButton.clicked.connect(self.flip_direction)
        self.ui.endButton.clicked.connect(self.end_sweep)
        self.ui.rampButton.clicked.connect(self.start_ramp)
        self.ui.saveButton.clicked.connect(self.setup_save)
        self.ui.addDeviceAction.triggered.connect(self.add_device)
        self.ui.removeDeviceAction.triggered.connect(self.remove_device)
        self.ui.actionSaveStation.triggered.connect(self.save_station)
        self.ui.actionLoadStation.triggered.connect(self.load_station)
        self.ui.actionQuit.triggered.connect(self.close)
        
    
    def start_logs(self):
        self.stdout_filename = os.environ['MeasureItHome'] + '\\logs\\stdout\\' + datetime.now().strftime("%Y-%m-%d") + '.txt'
        self.stderr_filename = os.environ['MeasureItHome'] + '\\logs\\stderr\\' + datetime.now().strftime("%Y-%m-%d") + '.txt'
        
        self.stdout_file = open(self.stdout_filename, 'a')
        sys.stderr = open(self.stderr_filename, 'a')
        
        self.stdout_file.write('Started program at  '+ datetime.now().strftime("%H:%M:%S")+'\n')
        print('Started program at  '+ datetime.now().strftime("%H:%M:%S"), file=sys.stderr)
        self.stdout_file.close()
        
        start_all_logging()
        
        
    def load_station(self):
        (fileName, x) = QFileDialog.getOpenFileName(self, "Load Station",
                                       os.environ['MeasureItHome']+"\\cfg\\",
                                       "Stations (*.station.yaml)")
        
        if len(fileName) == 0:
            return
        
        for name in self.devices.keys():
            self.do_remove_device(name)
        self.load_station_and_connect_instruments(fileName)
    
    
    def load_station_and_connect_instruments(self, config_file=None):
        self.station = Station()
        try:
            self.station.load_config_file(config_file)
        except Exception:
            self.show_error("Error", "Couldn't open the station configuration file. Started new station.")
            return
        
        if self.station.config == None:
            return

        for name,instr in self.station.config['instruments'].items():
            try:
                dev = self.station.load_instrument(name)
                self.devices[str(name)] = dev
                self.add_dev_to_menu(dev)
            except:
                self.show_error('Instrument Error', f"Error connectiong to {name}, \
                                either the name is already in use or the device is unavailable.")
        
        
    def save_station(self):
        ss_ui = SaveStationGUI(self)
        if ss_ui.exec_():
            fp = ss_ui.get_file()
            default = ss_ui.ui.defaultBox.isChecked()
            
            if len(fp) > 0:
                self.do_save_station(fp, default)
        
        
    def do_save_station(self, filename, set_as_default = False):
        def add_field(ss, instr, field, value):
            try:
                ss[field] = instr[value]
            except KeyError:
                pass
            
        if '.station.yaml' not in filename:
            filename += '.station.yaml'
            
        snap = {}
        snap['instruments'] = {}
        
        for name, instr in self.station.snapshot()['instruments'].items():
            snap['instruments'][name] = {}
            add_field(snap['instruments'][name], instr, 'type', '__class__')
            add_field(snap['instruments'][name], instr, 'address', 'address')
            snap['instruments'][name]['enable_forced_reconnect'] = True
            # Could also save parameter information here
        
        
        with open(filename, 'w') as file:
            yaml.dump(snap, file)
            if set_as_default:
                qc.config['station']['default_file'] = filename
                qc.config.save_config(os.environ['MeasureItHome']+'\\cfg\\qcodesrc.json')
    
        
    def edit_parameters(self):
        param_ui = EditParameterGUI(self.devices, self.track_params, self.set_params, self)
        if param_ui.exec_():
            self.track_params = param_ui.new_track_params
            self.set_params = param_ui.new_set_params
            print('Here are the parameters currently being tracked:')
            for name, p in self.track_params.items():
                print(name)
            print('Here are the parameters available for sweeping:')
            for name, p in self.set_params.items():
                print(name)
            self.update_parameters()
    
    
    def update_parameters(self):
        # This function is a horrible mess, but it finally works properly (I think!)
        self.ui.followParamTable.clearContents()
        self.ui.followParamTable.setRowCount(0)
        
        self.ui.followUpdateButtons = []
        for m, (name, p) in enumerate(self.track_params.items()):
            self.ui.followParamTable.insertRow(m)
            paramitem = QTableWidgetItem(name)
            paramitem.setData(32, p)
            paramitem.setFlags(Qt.ItemIsSelectable)
            self.ui.followParamTable.setItem(m, 0, paramitem)
            labelitem = QLineEdit(p.label)
            self.ui.followParamTable.setCellWidget(m, 1, labelitem)
            labelitem.editingFinished.connect(lambda x=m: self.update_labels(
                self.ui.followParamTable.item(x,0).data(32), self.ui.followParamTable.cellWidget(x,1).text()))
            valueitem = QTableWidgetItem(str(p.get()))
            self.ui.followParamTable.setItem(m, 2, valueitem)
            includeBox = QCheckBox()
            includeBox.setChecked(True)
            self.ui.followParamTable.setCellWidget(m, 3, includeBox)
            self.ui.followUpdateButtons.append(QPushButton("Get"))
            self.ui.followUpdateButtons[m].clicked.connect(
                lambda a, y=m: self.ui.followParamTable.item(y, 2).setText(str(
                    self.ui.followParamTable.item(y,0).data(32).get())))
            self.ui.followParamTable.setCellWidget(m, 4, self.ui.followUpdateButtons[m])
        
        self.ui.outputParamTable.clearContents()
        self.ui.outputParamTable.setRowCount(0)
        self.ui.scanParameterBox.clear()
        self.ui.scanParameterBox.addItem('time')
        
        self.ui.outputSetButtons = []
        self.ui.outputGetButtons = []
        for n, (name, p) in enumerate(self.set_params.items()):
            self.ui.outputParamTable.insertRow(n)
            paramitem = QTableWidgetItem(name)
            paramitem.setData(32, p)
            paramitem.setFlags(Qt.ItemIsSelectable)
            self.ui.outputParamTable.setItem(n, 0, paramitem)
            labelitem = QLineEdit(p.label)
            self.ui.outputParamTable.setCellWidget(n, 1, labelitem)
            labelitem.editingFinished.connect(lambda i=n: self.update_labels(
                self.ui.outputParamTable.item(i,0).data(32), self.ui.outputParamTable.cellWidget(i,1).text()))
            valueitem = QLineEdit(str(p.get()))
            self.ui.outputParamTable.setCellWidget(n, 2, valueitem)
            self.ui.outputSetButtons.append(QPushButton("Set"))
            self.ui.outputSetButtons[n].clicked.connect(
                lambda a, j=n: self.ui.outputParamTable.item(j,0).data(32).set(
                    _value_parser(self.ui.outputParamTable.cellWidget(j,2).text())))
            self.ui.outputParamTable.setCellWidget(n, 3, self.ui.outputSetButtons[n])
            self.ui.outputGetButtons.append(QPushButton("Get"))
            self.ui.outputGetButtons[n].clicked.connect(
                lambda a, k=n: self.ui.outputParamTable.cellWidget(k, 2).setText(str(
                    self.ui.outputParamTable.item(k,0).data(32).get())))
            self.ui.outputParamTable.setCellWidget(n, 4, self.ui.outputGetButtons[n])
            
            self.ui.scanParameterBox.addItem(p.label, p)

    
    def update_labels(self, p, newlabel):
        p.label = newlabel
        
        for n, (name, param) in enumerate(list(self.track_params.items())):
            self.ui.followParamTable.cellWidget(n,1).setText(param.label)
        for n, (name, param) in enumerate(list(self.set_params.items())):
            self.ui.outputParamTable.cellWidget(n,1).setText(param.label)
        for n in range(self.ui.scanParameterBox.count()-1):
            param = self.ui.scanParameterBox.itemData(n+1)
            self.ui.scanParameterBox.setItemText(n+1, param.label)


    def start_ramp(self):
        if self.ui.scanParameterBox.currentText() == 'time':
            return
        
        try:
            start = self.ui.scanParameterBox.currentData().get()
            stop = _value_parser(self.ui.endEdit.text())
            step = _value_parser(self.ui.stepEdit.text())
            stepsec = _value_parser(self.ui.stepsecEdit.text())
            plotbin = self.ui.plotbinEdit.text()
            plotbin = int(plotbin)
            if plotbin < 1:
                self.ui.plotbinEdit.setText('1')
                raise ValueError
        except ValueError as e:
            self.show_error("Error", "One or more of the sweep input values are invalid.\
                                Valid inputs consist of a number optionally followed by \
                                suffix f/p/n/u/m/k/M/G.")
            return
        
        
    def start_sweep(self):
        if self.sweep is not None:
            if self.sweep.is_running:
                alert = QMessageBox()
                new_sweep = alert.question(self, "Warning!",
                                      "A sweep is already running! Stop the current sweep and start a new one?",
                                      alert.Yes | alert.No)

                if new_sweep == alert.Yes:
                    self.sweep.stop()
                    self.sweep.kill()
                    self.sweep = None
                else:
                    return
            else:
                self.sweep.kill()
                
        # Check if we're scanning time, then if so, do Sweep0D
        if self.ui.scanParameterBox.currentText() == 'time':
            try:
                stop = _value_parser(self.ui.endEdit.text())
                stepsec = _value_parser(self.ui.stepsecEdit.text())
                plotbin = self.ui.plotbinEdit.text()
                plotbin = int(plotbin)
                if plotbin < 1:
                    self.ui.plotbinEdit.setText('1')
                    raise ValueError
            except ValueError as e:
                self.show_error("Error", "One or more of the sweep input values are invalid.\
                                Valid inputs consist of a number optionally followed by \
                                suffix f/p/n/u/m/k/M/G.")
                return
            
            save = self.ui.saveBox.isChecked()
            plot = self.ui.livePlotBox.isChecked()
            
            self.sweep = Sweep0D(max_time = stop, inter_delay = 1/stepsec, save_data = save, 
                                 plot_data = plot, plot_bin=plotbin)
        # Set up Sweep1D if we're not sweeping time
        else:
            try:
                start = _value_parser(self.ui.startEdit.text())
                stop = _value_parser(self.ui.endEdit.text())
                step = _value_parser(self.ui.stepEdit.text())
                stepsec = _value_parser(self.ui.stepsecEdit.text())
                plotbin = self.ui.plotbinEdit.text()
                plotbin = int(plotbin)
                if plotbin < 1:
                    self.ui.plotbinEdit.setText('1')
                    raise ValueError
            except ValueError as e:
                self.show_error("Error", "One or more of the sweep input values are invalid.\
                                Valid inputs consist of a number optionally followed by \
                                suffix f/p/n/u/m/k/M/G.")
                return
        
            set_param = self.ui.scanParameterBox.currentData()
            twoway = self.ui.bidirectionalBox.isChecked()
            continuous = self.ui.continualBox.isChecked()
            save = self.ui.saveBox.isChecked()
            plot = self.ui.livePlotBox.isChecked()
        
            self.sweep = Sweep1D(set_param, start, stop, step, inter_delay = 1.0/stepsec, 
                                 bidirectional = twoway, continual = continuous, save_data = save, 
                                 plot_data = plot, x_axis_time = 0, plot_bin=plotbin)
        
        for n in range(self.ui.followParamTable.rowCount()):
            if self.ui.followParamTable.cellWidget(n, 3).isChecked():
                self.sweep.follow_param(self.ui.followParamTable.item(n, 0).data(32))
                 
        if save and self.db_set is False:
            if not self.setup_save():
                self.show_error('Error', "Database was not opened. Set save information before running the sweep again.")
                return
        
        self.sweep.update_signal.connect(self.receive_updates)
        self.sweep.dataset_signal.connect(self.receive_dataset)
        self.sweep.start()
    
    
    def pause_resume_sweep(self):
        if self.sweep is None:
            return
        
        if self.sweep.is_running:
            self.sweep.stop()
            self.ui.pauseButton.setText("Resume")
        else:
            self.sweep.resume()
            self.ui.pauseButton.setText("Pause")
            
    
    def flip_direction(self):
        if self.sweep is None:
            return
        
        self.sweep.flip_direction()
        
       
    def end_sweep(self):
        if self.sweep is None:
            return
        
        print('trying to kill the sweep')
        self.sweep.kill()
        self.sweep = None
            
    def setup_save(self):
        save_data_ui = SaveDataGUI(self)
        if save_data_ui.exec_():
            (self.db, self.exp_name, self.sample_name) = save_data_ui.get_save_info()
            
            try:
                initialise_or_create_database_at(os.environ['MeasureItHome'] + '\\Databases\\' + self.db)
                qc.new_experiment(self.exp_name, self.sample_name)
                self.db_set = True
                return True
            except Exception:
                self.show_error('Error', "Error opening up database. Try again.")
                return False
        else:
            return False
    
    def add_device(self):
        # TODO:
        #   Add in ability to pass args and kwargs to the constructor
        
        device_ui = AddDeviceGUI(self)
        if device_ui.exec_():
            d = device_ui.get_selected()
            try:
                d['name'] = _name_parser(d['name'])
            except ValueError:
                self.show_error("Error", "Instrument name must start with a letter.")
                return
            
            if device_ui.ui.nameEdit.text() in self.devices.keys():
                self.show_error("Error", "Already have an instrument with that name in the station.")
                return
            
            # Now, set up our initialization for each device, if it doesn't follow the standard initialization
            new_dev = None
            try:
                new_dev = self.connect_device(d['device'], d['class'], d['name'], d['address'])
            except Exception as e:
                self.show_error("Error", "Couldn't connect to the instrument. Check address and try again.")
                new_dev = None
                
            if new_dev is not None:
                self.devices[d['name']] = new_dev
                self.station.add_component(new_dev)
                self.add_dev_to_menu(new_dev)
            
    
    def connect_device(self, device, classtype, name, address):
        if device == 'AMI430':
            new_dev = classtype(name, address=address, port=7180)
        elif device == 'Dummy':
            new_dev = classtype(name)
        else:
            new_dev = classtype(name, address)
            
        return new_dev
        
    def add_dev_to_menu(self, dev):
        # TODO: 
        #   Add some clickable action to the name hanging out in the device menu
        act = self.ui.menuDevices.addAction(f"{dev.name} ({dev.__class__.__name__})")
        act.setData(dev)
        self.actions[dev.name] = act
        
    
    def remove_device(self):
        remove_ui = RemoveDeviceGUI(self.devices, self)
        if remove_ui.exec_():
            dev = remove_ui.ui.deviceBox.currentText()
            if len(dev) > 0:
                self.do_remove_device(dev)
                
                
    def do_remove_device(self, name):
        self.station.remove_component(name)
        dev=self.devices.pop(name)
        dev.close()
        self.ui.menuDevices.removeAction(self.actions.pop(name))
    
    
    @pyqtSlot(str)
    def append_stdout(self, text):
        self.ui.consoleEdit.moveCursor(QTextCursor.End)
        self.ui.consoleEdit.insertPlainText(text)
        
        self.stdout_file = open(self.stdout_filename, 'a')
        time = datetime.now().strftime("%H:%M:%S")
        self.stdout_file.write(time + '\t' + text)
        self.stdout_file.close()
    
    
    @pyqtSlot(dict)
    def receive_updates(self, update_dict):
        is_running = update_dict['status']
        set_param = update_dict['set_param']
        setpoint = update_dict['setpoint']
        direction = update_dict['direction']
        
        self.ui.scanValue.setText(f'{is_running}')
        if is_running:
            self.ui.scanValue.setStyleSheet('color: green')
        else:
            self.ui.scanValue.setStyleSheet('color: red')
        if set_param == 'time':
            self.ui.paramValue.setText('time')
        else:
            self.ui.paramValue.setText(f'{set_param.label}')
        self.ui.setpointValue.setText(f'{str(setpoint)}')
        if direction:
            self.ui.directionValue.setText('Backward')
        else:
            self.ui.directionValue.setText('Forward')
            
            
    @pyqtSlot(DataSet)
    def receive_dataset(self, dataset):
        self.datasets.append(dataset)
        
        
    def show_error(self, title, message):
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_() 
        
        
    def exit(self):
        for key, dev in self.devices.items():
            dev.close()
        
        if self.sweep is not None:
            self.sweep.kill()
            
        self.thread.stop=True
        self.thread.exit()
        if not self.thread.wait(5000):
            self.thread.terminate()
            print("Forced stdout thread to terminate.", file=sys.stderr)
        
        self.stdout_file = open(self.stdout_filename, 'a')
        self.stdout_file.write("Program exited at "+datetime.now().strftime("%H:%M:%S")+'\n')
        print("Program exited at "+datetime.now().strftime("%H:%M:%S"), file=sys.stderr)
        self.stdout_file.close()
        
        app = QtGui.QGuiApplication.instance()
        app.closeAllWindows()
    
    
    def closeEvent(self, event):
        are_you_sure = QMessageBox()
        close = are_you_sure.question(self, "Exit",
                                      "Are you sure you want to close all windows and exit the application?",
                                      are_you_sure.Yes | are_you_sure.No)

        if close == are_you_sure.Yes:
            self.exit()
            event.accept()
        else:
            event.ignore()
            return
    
    
def main():
    if os.path.isfile(os.environ['MeasureItHome']+'\\cfg\\qcodesrc.json'):
        qc.config.update_config(os.environ['MeasureItHome']+'\\cfg\\')
    
    app = QtWidgets.QApplication(sys.argv)
    app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app.setStyle('WindowsVista')
    
    window = UImain()
    window.setAttribute(QtCore.Qt.WA_StyledBackground)
    
    app.exec_()

if __name__ ==  "__main__":
    main()