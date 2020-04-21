from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QListWidgetItem, QFileDialog
import sys,os
from GUI_Measureit import *
from edit_parameter_ui import Ui_editParameter
from add_device_ui import Ui_addDevice
from save_station_ui import Ui_saveStation
from remove_device_ui import Ui_removeDevice

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# TODO: Create a dictionary with class typings as the key, and common parameters as the values
# TODO: From main window, grab the selected parameters when 'accept' registers

class SaveStationGUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SaveStationGUI,self).__init__(parent)
        self.parent = parent
        self.ui = Ui_saveStation()
        self.ui.setupUi(self)
        self.setWindowTitle("Save Current Station")
        self.url = None
        
        self.ui.browseButton.clicked.connect(self.select_file)
        
        
    def select_file(self):
        #fd = QFileDialog(self, directory=os.environ['MeasureItHome']+'\\cfg\\')
        #fd.setFileMode(QFileDialog.AnyFile)
        #fd.setNameFilter(tr("Station Files (*.station.yaml)"))
        #if fd.exec_():
        #    fileNames = fd.selectedFiles()
        fileName = QFileDialog.getSaveFileName(self, "Save Station",
                                       os.environ['MeasureItHome']+"\\cfg\\new_station.station.yaml",
                                       "Stations (*.station.yaml)")
        if len(fileName[0]) > 0:
            self.url = fileName[0]
            if '.station' not in self.url and '.yaml' not in self.url:
                self.url += '.station.yaml'
            elif '.station' in self.url and '.yaml' not in self.url:
                self.url += '.station.yaml'
            self.ui.locationEdit.setText(self.url)
            
    def get_file(self):
        return self.url

class EditParameterGUI(QtWidgets.QDialog):
    def __init__(self, devices, track_params, parent = None):
        super(EditParameterGUI,self).__init__(parent)
        self.parent = parent
        self.devices = devices
        self.ui = Ui_editParameter()
        self.ui.setupUi(self)
                
        self.make_connections()
        self.new_track_params = {}
        
        for name, dev in self.devices.items():
            self.ui.deviceBox.addItem(name, dev)
            
        for p in self.parent.track_params:
            listitem = QListWidgetItem(p.full_name) 
            listitem.setData(32, p)
            self.ui.activeParamsWidget.addItem(listitem)
            self.new_track_params[p.full_name] = p
            
        self.update_avail_device_params(0)
        
        self.show()
        
        
    def update_avail_device_params(self, index):
        self.ui.allParamsWidget.clear()
        if len(self.devices) > 0:
            for key, p in self.ui.deviceBox.currentData().parameters.items():
                listitem = QListWidgetItem(p.full_name) 
                listitem.setData(32, p)
                self.ui.allParamsWidget.addItem(listitem)
            
    def make_connections(self):
        self.ui.addParamButton.clicked.connect(self.add_param)
        self.ui.delParamButton.clicked.connect(self.del_param)
        
        self.ui.deviceBox.activated.connect(self.update_avail_device_params)
        
        
    def add_param(self):
        params = self.ui.allParamsWidget.selectedItems()
        
        for p in params:
            name = p.data(32).full_name
            if name not in self.new_track_params.keys():
                listitem = QListWidgetItem(name)
                listitem.setData(32, p.data(32))
                self.ui.activeParamsWidget.addItem(listitem)
                self.new_track_params[name] = p.data(32)
    
    
    def del_param(self):
        params = self.ui.activeParamsWidget.selectedItems()
        for p in params:
            self.ui.activeParamsWidget.takeItem(self.ui.activeParamsWidget.row(p))
            self.new_track_params.pop(p.name)
            
            
    def get_new_track_params(self):
        return self.new_track_params
        
        
class AddDeviceGUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AddDeviceGUI,self).__init__(parent)
        self.parent = parent
        self.ui = Ui_addDevice()
        self.ui.setupUi(self)
        self.setWindowTitle("Add Device")
        
        for name, dev in UImain.SUPPORTED_INSTRUMENTS.items():
            self.ui.deviceBox.addItem(name, dev)
            
        self.show()
            
        
    def get_selected(self):
        selected = {}
        selected['device'] = self.ui.deviceBox.currentText()
        selected['class'] = self.ui.deviceBox.currentData()
        selected['name'] = self.ui.nameEdit.text()
        selected['address'] = self.ui.addressEdit.text()
        return selected
    
    
class RemoveDeviceGUI(QtWidgets.QDialog):
    def __init__(self, devices, parent=None):
        super(RemoveDeviceGUI,self).__init__(parent)
        self.parent = parent
        self.ui = Ui_removeDevice()
        self.ui.setupUi(self)
        self.setWindowTitle("Remove Device")
        
        for name, dev in devices.items():
            self.ui.deviceBox.addItem(name, dev)
            
        self.show()





