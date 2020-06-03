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
        addDevice.resize(241, 201)
        self.dialogBox = QtWidgets.QDialogButtonBox(addDevice)
        self.dialogBox.setGeometry(QtCore.QRect(40, 160, 161, 32))
        self.dialogBox.setOrientation(QtCore.Qt.Horizontal)
        self.dialogBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.dialogBox.setObjectName("dialogBox")
        self.horizontalLayoutWidget = QtWidgets.QWidget(addDevice)
        self.horizontalLayoutWidget.setGeometry(QtCore.QRect(30, 20, 182, 128))
        self.horizontalLayoutWidget.setObjectName("horizontalLayoutWidget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.instrumentLabel = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.instrumentLabel.setObjectName("instrumentLabel")
        self.verticalLayout.addWidget(self.instrumentLabel)
        self.nameLabel = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.nameLabel.setObjectName("nameLabel")
        self.verticalLayout.addWidget(self.nameLabel)
        self.addressLabel = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.addressLabel.setObjectName("addressLabel")
        self.verticalLayout.addWidget(self.addressLabel)
        self.argsLabel = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.argsLabel.setObjectName("argsLabel")
        self.verticalLayout.addWidget(self.argsLabel)
        self.kwargsLabel = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.kwargsLabel.setObjectName("kwargsLabel")
        self.verticalLayout.addWidget(self.kwargsLabel)
        self.horizontalLayout.addLayout(self.verticalLayout)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.deviceBox = QtWidgets.QComboBox(self.horizontalLayoutWidget)
        self.deviceBox.setObjectName("deviceBox")
        self.verticalLayout_2.addWidget(self.deviceBox)
        self.nameEdit = QtWidgets.QLineEdit(self.horizontalLayoutWidget)
        self.nameEdit.setObjectName("nameEdit")
        self.verticalLayout_2.addWidget(self.nameEdit)
        self.addressEdit = QtWidgets.QLineEdit(self.horizontalLayoutWidget)
        self.addressEdit.setObjectName("addressEdit")
        self.verticalLayout_2.addWidget(self.addressEdit)
        self.argsEdit = QtWidgets.QLineEdit(self.horizontalLayoutWidget)
        self.argsEdit.setObjectName("argsEdit")
        self.verticalLayout_2.addWidget(self.argsEdit)
        self.kwargsEdit = QtWidgets.QLineEdit(self.horizontalLayoutWidget)
        self.kwargsEdit.setObjectName("kwargsEdit")
        self.verticalLayout_2.addWidget(self.kwargsEdit)
        self.horizontalLayout.addLayout(self.verticalLayout_2)

        self.retranslateUi(addDevice)
        self.dialogBox.accepted.connect(addDevice.accept)
        self.dialogBox.rejected.connect(addDevice.reject)
        QtCore.QMetaObject.connectSlotsByName(addDevice)

    def retranslateUi(self, addDevice):
        _translate = QtCore.QCoreApplication.translate
        addDevice.setWindowTitle(_translate("addDevice", "Dialog"))
        self.instrumentLabel.setText(_translate("addDevice", "Instrument"))
        self.nameLabel.setText(_translate("addDevice", "Name"))
        self.addressLabel.setText(_translate("addDevice", "Address"))
        self.argsLabel.setText(_translate("addDevice", "args"))
        self.kwargsLabel.setText(_translate("addDevice", "kwargs"))

