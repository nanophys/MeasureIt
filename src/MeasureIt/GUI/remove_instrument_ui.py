# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'remove_instrument.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_removeInstrument(object):
    def setupUi(self, removeInstrument):
        removeInstrument.setObjectName("removeInstrument")
        removeInstrument.resize(327, 96)
        self.buttonBox = QtWidgets.QDialogButtonBox(removeInstrument)
        self.buttonBox.setGeometry(QtCore.QRect(230, 20, 81, 221))
        self.buttonBox.setOrientation(QtCore.Qt.Vertical)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.instrumentLabel = QtWidgets.QLabel(removeInstrument)
        self.instrumentLabel.setGeometry(QtCore.QRect(20, 30, 61, 16))
        self.instrumentLabel.setObjectName("instrumentLabel")
        self.instrumentBox = QtWidgets.QComboBox(removeInstrument)
        self.instrumentBox.setGeometry(QtCore.QRect(80, 30, 111, 22))
        self.instrumentBox.setObjectName("instrumentBox")

        self.retranslateUi(removeInstrument)
        self.buttonBox.accepted.connect(removeInstrument.accept)
        self.buttonBox.rejected.connect(removeInstrument.reject)
        QtCore.QMetaObject.connectSlotsByName(removeInstrument)

    def retranslateUi(self, removeInstrument):
        _translate = QtCore.QCoreApplication.translate
        removeInstrument.setWindowTitle(_translate("removeInstrument", "Dialog"))
        self.instrumentLabel.setText(_translate("removeInstrument", "Instrument:"))

