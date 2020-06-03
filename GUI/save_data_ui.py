# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'save_data.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_saveData(object):
    def setupUi(self, saveData):
        saveData.setObjectName("saveData")
        saveData.resize(330, 164)
        self.buttonBox = QtWidgets.QDialogButtonBox(saveData)
        self.buttonBox.setGeometry(QtCore.QRect(80, 120, 161, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.locationLabel = QtWidgets.QLabel(saveData)
        self.locationLabel.setGeometry(QtCore.QRect(20, 30, 61, 21))
        self.locationLabel.setObjectName("locationLabel")
        self.locationEdit = QtWidgets.QLineEdit(saveData)
        self.locationEdit.setGeometry(QtCore.QRect(80, 30, 161, 20))
        self.locationEdit.setReadOnly(True)
        self.locationEdit.setObjectName("locationEdit")
        self.browseButton = QtWidgets.QPushButton(saveData)
        self.browseButton.setGeometry(QtCore.QRect(250, 30, 61, 23))
        self.browseButton.setObjectName("browseButton")
        self.expEdit = QtWidgets.QLineEdit(saveData)
        self.expEdit.setGeometry(QtCore.QRect(120, 60, 121, 20))
        self.expEdit.setObjectName("expEdit")
        self.sampleEdit = QtWidgets.QLineEdit(saveData)
        self.sampleEdit.setGeometry(QtCore.QRect(120, 90, 121, 20))
        self.sampleEdit.setObjectName("sampleEdit")
        self.expLabel = QtWidgets.QLabel(saveData)
        self.expLabel.setGeometry(QtCore.QRect(20, 60, 91, 21))
        self.expLabel.setObjectName("expLabel")
        self.sampleLabel = QtWidgets.QLabel(saveData)
        self.sampleLabel.setGeometry(QtCore.QRect(20, 90, 91, 21))
        self.sampleLabel.setObjectName("sampleLabel")

        self.retranslateUi(saveData)
        self.buttonBox.accepted.connect(saveData.accept)
        self.buttonBox.rejected.connect(saveData.reject)
        QtCore.QMetaObject.connectSlotsByName(saveData)

    def retranslateUi(self, saveData):
        _translate = QtCore.QCoreApplication.translate
        saveData.setWindowTitle(_translate("saveData", "Dialog"))
        self.locationLabel.setText(_translate("saveData", "Database:"))
        self.browseButton.setText(_translate("saveData", "Browse"))
        self.expLabel.setText(_translate("saveData", "Experiment name:"))
        self.sampleLabel.setText(_translate("saveData", "Sample name:"))

