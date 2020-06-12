# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'remove_device.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_removeDevice(object):
    def setupUi(self, removeDevice):
        removeDevice.setObjectName("removeDevice")
        removeDevice.resize(327, 96)
        self.buttonBox = QtWidgets.QDialogButtonBox(removeDevice)
        self.buttonBox.setGeometry(QtCore.QRect(230, 20, 81, 221))
        self.buttonBox.setOrientation(QtCore.Qt.Vertical)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.deviceLabel = QtWidgets.QLabel(removeDevice)
        self.deviceLabel.setGeometry(QtCore.QRect(20, 30, 47, 13))
        self.deviceLabel.setObjectName("deviceLabel")
        self.deviceBox = QtWidgets.QComboBox(removeDevice)
        self.deviceBox.setGeometry(QtCore.QRect(70, 30, 111, 22))
        self.deviceBox.setObjectName("deviceBox")

        self.retranslateUi(removeDevice)
        self.buttonBox.accepted.connect(removeDevice.accept)
        self.buttonBox.rejected.connect(removeDevice.reject)
        QtCore.QMetaObject.connectSlotsByName(removeDevice)

    def retranslateUi(self, removeDevice):
        _translate = QtCore.QCoreApplication.translate
        removeDevice.setWindowTitle(_translate("removeDevice", "Dialog"))
        self.deviceLabel.setText(_translate("removeDevice", "Device:"))

