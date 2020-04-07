from PyQt5 import QtWidgets,QtCore
import sys,os
from addparameter_ui import Ui_AddParameter
from adddevice_ui import Ui_AddDevice
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# TODO: Create a dictionary with class typings as the key, and common parameters as the values
# TODO: From main window, grab the selected parameters when 'accept' registers

class AddParameterGUI(QtWidgets.QDialog):
    def __init__(self,parent = None):
        super(AddParameterGUI,self).__init__(parent)
        self.ui = Ui_AddParameter()
        self.ui.setupUi(self)
        
        self.connect_buttons()

        self.devices = {}
        self.all_params = {}
        self.track_params = {}
        
        
        
        self.show()