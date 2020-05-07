
from PyQt5 import uic
import os
ui_files = ['mainwindow.ui', 'add_device.ui', 'edit_parameter.ui', 'save_station.ui', 'remove_device.ui', 'save_data.ui']
for ui_file in ui_files:
    py_file = os.path.splitext(ui_file)[0] + "_ui.py"
    fp = open(py_file, "w")
    uic.compileUi(ui_file, fp, from_imports = True)
    fp.close()