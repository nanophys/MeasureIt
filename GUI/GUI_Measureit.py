from PyQt5 import QtWidgets,QtCore
import sys,os
from mainwindow_ui import Ui_MainWindow
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

class UImain(QtWidgets.QMainWindow):
    
    SUPPORTED_INSTRUMENTS = []
    
    def __init__(self,parent = None):
        super(UImain,self).__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        self.connect_buttons()

        self.devices = {}
        self.all_params = {}
        self.track_params = {}
        
        
        
        self.show()
    
    
    def connect_buttons(self):
        self.ui.addParameterButton.clicked.connect(self.add_parameter())
        self.ui.deleteParameterButton.clicked.connect(self.delete_parameter())
        self.ui.startButton.clicked.connect(self.start_sweep())
        self.ui.addDeviceAction.triggered.connect(self.add_device())
        
        
    def add_parameter(self):
        pass
    def delete_parameter(self):
        pass
    def start_sweep(self):
        pass
    def add_device(self):
        pass
    
    
def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app.setStyle('WindowsVista')
    window = UImain()
    window.setAttribute(QtCore.Qt.WA_StyledBackground)
    app.exec_()

if __name__ ==  "__main__":
    main()