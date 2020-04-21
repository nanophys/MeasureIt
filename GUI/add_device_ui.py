# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'add_device.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_addDevice(object):
    def setupUi(self, addDevice):
        addDevice.setObjectName("addDevice")
        addDevice.resize(330, 164)
        self.buttonBox = QtWidgets.QDialogButtonBox(addDevice)
        self.buttonBox.setGeometry(QtCore.QRect(60, 120, 191, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.defaultBox = QtWidgets.QCheckBox(addDevice)
        self.defaultBox.setGeometry(QtCore.QRect(110, 70, 121, 17))
        self.defaultBox.setObjectName("defaultBox")
        self.locationLabel = QtWidgets.QLabel(addDevice)
        self.locationLabel.setGeometry(QtCore.QRect(20, 30, 47, 13))
        self.locationLabel.setObjectName("locationLabel")
        self.locationEdit = QtWidgets.QLineEdit(addDevice)
        self.locationEdit.setGeometry(QtCore.QRect(70, 30, 171, 20))
        self.locationEdit.setReadOnly(True)
        self.locationEdit.setObjectName("locationEdit")
        self.browseButton = QtWidgets.QPushButton(addDevice)
        self.browseButton.setGeometry(QtCore.QRect(250, 30, 61, 23))
        self.browseButton.setObjectName("browseButton")

        self.retranslateUi(addDevice)
        self.buttonBox.accepted.connect(addDevice.accept)
        self.buttonBox.rejected.connect(addDevice.reject)
        QtCore.QMetaObject.connectSlotsByName(addDevice)

    def retranslateUi(self, addDevice):
        _translate = QtCore.QCoreApplication.translate
        addDevice.setWindowTitle(_translate("addDevice", "Dialog"))
        self.defaultBox.setText(_translate("addDevice", "Set as default station?"))
        self.locationLabel.setText(_translate("addDevice", "Location:"))
        self.browseButton.setText(_translate("addDevice", "Browse"))

