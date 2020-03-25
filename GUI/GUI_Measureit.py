from PyQt5 import QtWidgets,QtCore
import sys,os
from mainwindow_ui import Ui_MainWindow
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

class UImain(QtWidgets.QMainWindow):
    def __init__(self,parent = None):
        super(UImain,self).__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        


        self.show()

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app.setStyle('WindowsVista')
    window = UImain()
    window.setAttribute(QtCore.Qt.WA_StyledBackground)
    app.exec_()

if __name__ ==  "__main__":
    main()