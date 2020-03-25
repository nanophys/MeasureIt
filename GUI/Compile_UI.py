
from PyQt5 import uic
import os
ui_file = 'mainwindow.ui'
py_file = os.path.splitext(ui_file)[0] + "_ui.py"
fp = open(py_file, "w")
uic.compileUi(ui_file, fp, from_imports = True)
fp.close()