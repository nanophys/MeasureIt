from PyQt5 import QtWidgets,QtCore,QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTableWidgetItem, QMessageBox, QFileDialog,\
    QPushButton, QCheckBox, QHeaderView, QLineEdit
import sys,os
import yaml
import matplotlib
from mainwindow_ui import Ui_MeasureIt
from GUI_Dialogs import *
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
matplotlib.use('Qt5Agg')

sys.path.append("..")
import src
from src.daq_driver import Daq, DaqAOChannel, DaqAIChannel
from src.util import _value_parser, _name_parser
from src.sweep1d import Sweep1D
import qcodes as qc
from qcodes import Station
from qcodes.instrument_drivers.Lakeshore.Model_372 import Model_372
from qcodes.instrument_drivers.american_magnetics.AMI430 import AMI430
from qcodes.instrument_drivers.stanford_research.SR860 import SR860
from qcodes.instrument_drivers.tektronix.Keithley_2450 import Keithley2450
from qcodes.tests.instrument_mocks import DummyInstrument
from qcodes.instrument.base import InstrumentBase

class UImain(QtWidgets.QMainWindow):
    
     # To add an instrument, import the driver then add it to our instrument 
     # dictionary with the name as the key, and the class as the value
    SUPPORTED_INSTRUMENTS = {'Dummy':DummyInstrument,
                             'NI DAQ':Daq, 
                             'Model_372':Model_372, 
                             'AMI430':AMI430, 
                             'SR860':SR860, 
                             'Keithley2450':Keithley2450}
    
    def __init__(self,parent = None, config_file = None):
        super(UImain,self).__init__(parent)
        self.ui = Ui_MeasureIt()
        self.ui.setupUi(self)
        self.setWindowTitle("MeasureIt")
        
        self.init_tables()
        self.connect_buttons()

        self.station = None
        self.devices = {}
        self.actions = {}
        self.track_params = {}
        self.set_params = {}
        self.shown_follow_params = []
        self.shown_set_params = []
        
        self.load_station_and_connect_instruments(config_file)
        
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
        
        
    def connect_buttons(self):
        self.ui.editParameterButton.clicked.connect(self.edit_parameters)
        self.ui.startButton.clicked.connect(self.start_sweep)
        self.ui.addDeviceAction.triggered.connect(self.add_device)
        self.ui.removeDeviceAction.triggered.connect(self.remove_device)
        self.ui.actionSaveStation.triggered.connect(self.save_station)
        self.ui.actionLoadStation.triggered.connect(self.load_station)
        self.ui.actionQuit.triggered.connect(self.close)
        
        
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
        self.ui.followParamTable.clearContents()
        for name, p in self.track_params.items():
            if name not in self.shown_follow_params:
                n = self.ui.followParamTable.rowCount()
                self.ui.followParamTable.insertRow(n)
                paramitem = QTableWidgetItem(name)
                paramitem.setFlags(Qt.ItemIsSelectable)
                self.ui.followParamTable.setItem(n, 0, paramitem)
                labelitem = QLineEdit(p.label)
                labelitem.editingFinished.connect(lambda: self.update_labels(p, labelitem.text()))
                self.ui.followParamTable.setCellWidget(n, 1, labelitem)
                valueitem = QTableWidgetItem(str(p.get()))
                self.ui.followParamTable.setItem(n, 2, valueitem)
                includeBox = QCheckBox()
                includeBox.setChecked(True)
                self.ui.followParamTable.setCellWidget(n, 3, includeBox)
                updateButton = QPushButton("Get")
                updateButton.clicked.connect(lambda: self.ui.followParamTable.item(n, 2).setText(str(p.get())))
                self.ui.followParamTable.setCellWidget(n, 4, updateButton)
                
                self.shown_follow_params.append(name)
        
        self.ui.outputParamTable.clearContents()
        self.ui.scanParameterBox.clear()
        self.ui.scanParameterBox.addItem('time')
        for name, p in self.set_params.items():
            if name not in self.shown_set_params:
                n = self.ui.outputParamTable.rowCount()
                self.ui.outputParamTable.insertRow(n)
                paramitem = QTableWidgetItem(name)
                paramitem.setFlags(Qt.ItemIsSelectable)
                self.ui.outputParamTable.setItem(n, 0, paramitem)
                labelitem = QLineEdit(p.label)
                labelitem.editingFinished.connect(lambda: self.update_labels(p, labelitem.text()))
                self.ui.outputParamTable.setCellWidget(n, 1, labelitem)
                valueitem = QLineEdit(str(p.get()))
                self.ui.outputParamTable.setCellWidget(n, 2, valueitem)
                setButton = QPushButton("Set")
                setButton.clicked.connect(lambda: p.set(_value_parser(self.ui.outputParamTable.cellWidget(n,2).text())))
                self.ui.outputParamTable.setCellWidget(n, 3, setButton)
                getButton = QPushButton("Get")
                getButton.clicked.connect(lambda: self.ui.outputParamTable.cellWidget(n, 2).setText(str(p.get())))
                self.ui.outputParamTable.setCellWidget(n, 4, getButton)
                
                self.ui.scanParameterBox.addItem(p.label, p)
                self.shown_set_params.append(name)

    
    def update_labels(self, p, newlabel):
        p.label = newlabel
        
        for n, (name, param) in enumerate(list(self.track_params.items())):
            self.ui.followParamTable.cellWidget(n,1).setText(param.label)
        for n, (name, param) in enumerate(list(self.set_params.items())):
            self.ui.outputParamTable.cellWidget(n,1).setText(param.label)
        for n in range(self.ui.scanParameterBox.count()-1):
            param = self.ui.scanParameterBox.itemData(n+1)
            self.ui.scanParameterBox.setItemText(n+1, param.label)
        
        
    def start_sweep(self):
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
        
        self.sweep = Sweep1D(set_param, start, stop, step, inter_delay = 1/stepsec, 
                             bidirectional = twoway, continual = continuous, save_data = save, 
                             plot_data = plot, x_axis_time = 0, plot_bin=plotbin)
        self.sweep.follow_param(list(self.track_params.values()))
        if save:
            self.setup_save()
        
        self.sweep.start()
    

    def setup_save(self):
        pass
    
    
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
    
    
    def show_error(self, title, message):
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_() 
        
        
    def exit(self):
        for key, dev in self.devices.items():
            dev.close()
        
        app = QtGui.QGuiApplication.instance()
        app.closeAllWindows()
    
    
    def closeEvent(self, event):
        are_you_sure = QMessageBox()
        close = are_you_sure.question(self, "Exit",
                                      "Are you sure you want to close all windows and exit the application ?",
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