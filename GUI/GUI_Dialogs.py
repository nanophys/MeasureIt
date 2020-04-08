from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QListWidgetItem
import sys,os
from GUI_Measureit import *
from edit_parameter_ui import Ui_editParameter
from add_device_ui import Ui_addDevice
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# TODO: Create a dictionary with class typings as the key, and common parameters as the values
# TODO: From main window, grab the selected parameters when 'accept' registers

class EditParameterGUI(QtWidgets.QDialog):
    def __init__(self, parent = None):
        super(EditParameterGUI,self).__init__(parent)
        self.parent = parent
        self.ui = Ui_editParameter()
        self.ui.setupUi(self)
                
        self.make_connections()
        self.new_track_params = []
        for name, dev in self.parent.devices.items():
            self.ui.deviceBox.addItem(name, dev)
        self.load_param_lists()
        
        self.show()
        
    
    def load_param_lists(self):
        for p in self.parent.track_params:
            listitem = QListWidgetItem(str(p)) 
            listitem.setData(32, p)
            self.ui.activeParamsWidget.addItem(listitem)
            self.new_track_params.append(p)
            
        self.update_avail_device_params(0)
        
    def update_avail_device_params(self, index):
        self.ui.allParamsWidget.clear()
        if len(self.parent.devices) > 0:
            for key, p in self.parent.all_params[self.ui.deviceBox.currentText()].items():
                listitem = QListWidgetItem(str(p)) 
                listitem.setData(32, p)
                self.ui.allParamsWidget.addItem(listitem)
            
    def make_connections(self):
        self.ui.addParamButton.clicked.connect(self.add_param)
        self.ui.delParamButton.clicked.connect(self.del_param)
        
        self.ui.deviceBox.activated.connect(self.update_avail_device_params)
        
        
    def add_param(self):
        params = self.ui.allParamsWidget.selectedItems()
        
        for p in params:
            if p.data(32) not in self.new_track_params:
                listitem = QListWidgetItem(str(p.data(32)))
                listitem.setData(32, p.data(32))
                self.ui.activeParamsWidget.addItem(listitem)
                self.new_track_params.append(p.data(32))
    
    
    def del_param(self):
        params = self.ui.activeParamsWidget.selectedItems()
        for p in params:
            self.ui.activeParamsWidget.takeItem(self.ui.activeParamsWidget.row(p))
            self.new_track_params.remove(p.data(32))
            
            
    def get_new_track_params(self):
        return self.new_track_params
        
        
class AddDeviceGUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AddDeviceGUI,self).__init__(parent)
        self.parent = parent
        self.ui = Ui_addDevice()
        self.ui.setupUi(self)
        self.setWindowTitle("Add Device")
        
        self.selected = {}
        self.selected['device'] = '(none)'
        self.ui.deviceBox.addItem('(none)')
        for name, dev in UImain.SUPPORTED_INSTRUMENTS.items():
            self.ui.deviceBox.addItem(name)
            
        self.ui.deviceBox.activated.connect(self.select_device)
        self.show()
            
    def select_device(self, index):
        self.selected['device'] = self.ui.deviceBox.itemText(index)
        
    def get_selected(self):
        self.selected['name'] = self.ui.nameEdit.text()
        self.selected['address'] = self.ui.addressEdit.text()
        return self.selected