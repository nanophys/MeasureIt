# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'save_station.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_saveStation(object):
    def setupUi(self, saveStation):
        saveStation.setObjectName("saveStation")
        saveStation.resize(330, 164)
        self.buttonBox = QtWidgets.QDialogButtonBox(saveStation)
        self.buttonBox.setGeometry(QtCore.QRect(60, 120, 191, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.defaultBox = QtWidgets.QCheckBox(saveStation)
        self.defaultBox.setGeometry(QtCore.QRect(110, 70, 121, 17))
        self.defaultBox.setObjectName("defaultBox")
        self.locationLabel = QtWidgets.QLabel(saveStation)
        self.locationLabel.setGeometry(QtCore.QRect(20, 30, 47, 13))
        self.locationLabel.setObjectName("locationLabel")
        self.locationEdit = QtWidgets.QLineEdit(saveStation)
        self.locationEdit.setGeometry(QtCore.QRect(70, 30, 171, 20))
        self.locationEdit.setReadOnly(True)
        self.locationEdit.setObjectName("locationEdit")
        self.browseButton = QtWidgets.QPushButton(saveStation)
        self.browseButton.setGeometry(QtCore.QRect(250, 30, 61, 23))
        self.browseButton.setObjectName("browseButton")

        self.retranslateUi(saveStation)
        self.buttonBox.accepted.connect(saveStation.accept)
        self.buttonBox.rejected.connect(saveStation.reject)
        QtCore.QMetaObject.connectSlotsByName(saveStation)

    def retranslateUi(self, saveStation):
        _translate = QtCore.QCoreApplication.translate
        saveStation.setWindowTitle(_translate("saveStation", "Dialog"))
        self.defaultBox.setText(_translate("saveStation", "Set as default station?"))
        self.locationLabel.setText(_translate("saveStation", "Location:"))
        self.browseButton.setText(_translate("saveStation", "Browse"))

