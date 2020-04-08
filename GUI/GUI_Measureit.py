from PyQt5 import QtWidgets,QtCore
import sys,os
from mainwindow_ui import Ui_MeasureIt
from GUI_Dialogs import *
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

sys.path.append("..")
import src
import nidaqmx
from src.daq_driver import Daq, DaqAOChannel, DaqAIChannel
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
    
    def __init__(self,parent = None):
        super(UImain,self).__init__(parent)
        self.ui = Ui_MeasureIt()
        self.ui.setupUi(self)
        
        self.connect_buttons()

        self.devices = {}
        self.all_params = {}
        self.track_params = []
        
        self.show()
    
    
    def connect_buttons(self):
        self.ui.editParameterButton.clicked.connect(self.edit_parameter)
        self.ui.startButton.clicked.connect(self.start_sweep)
        self.ui.addDeviceAction.triggered.connect(self.add_device)
        
        
    def edit_parameter(self):
        param_ui = EditParameterGUI(self)
        if param_ui.exec_():
            self.track_params = param_ui.get_new_track_params()
            print('Here are the parameters currently being tracked:')
            for p in self.track_params:
                print(str(p))
    
    
    
    def start_sweep(self):
        pass
    
    
    def add_device(self):
        device_ui = AddDeviceGUI(self)
        if device_ui.exec_():
            d = device_ui.get_selected()
            
            if d['device'] == '(none)':
                return
            if d['name'] in self.devices.keys():
                # TODO: throw an error if the name is already here
                pass
            
            # Now, set up our initialization for each device, if it doesn't follow the standard initialization
            new_dev = None
            try:
                if d['device'] == 'AMI430':
                    new_dev = AMI430(d['name'], address=d['address'], port=7180)
                elif d['device'] == 'Dummy':
                    new_dev = DummyInstrument(d['name'])
                else:
                    new_dev = UImain.SUPPORTED_INSTRUMENTS['device'](d['name'], d['address'])
                self.devices[d['name']] = new_dev
                self.add_dev_to_menu(d)
                self.all_params[d['name']] = new_dev.parameters
               
            except Exception as e:
                # TODO: Catch errors in device initialization
                pass
            
            
    def add_dev_to_menu(self, dev):
        # TODO: Add some clickable action to the name hanging out in the device menu
        self.ui.menuDevices.addAction(f"{dev['name']} ({dev['device']})")
        
        
            
    
    
def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app.setStyle('WindowsVista')
    window = UImain()
    window.setAttribute(QtCore.Qt.WA_StyledBackground)
    app.exec_()

if __name__ ==  "__main__":
    main()