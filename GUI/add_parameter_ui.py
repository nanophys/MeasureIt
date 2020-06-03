# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'add_parameter.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_addParameter(object):
    def setupUi(self, addParameter):
        addParameter.setObjectName("addParameter")
        addParameter.resize(322, 240)
        self.buttonBox = QtWidgets.QDialogButtonBox(addParameter)
        self.buttonBox.setGeometry(QtCore.QRect(90, 200, 151, 32))
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayoutWidget = QtWidgets.QWidget(addParameter)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(40, 20, 251, 171))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.deviceLabel = QtWidgets.QLabel(self.verticalLayoutWidget)
        self.deviceLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.deviceLabel.setObjectName("deviceLabel")
        self.horizontalLayout_3.addWidget(self.deviceLabel)
        self.deviceBox = QtWidgets.QComboBox(self.verticalLayoutWidget)
        self.deviceBox.setObjectName("deviceBox")
        self.horizontalLayout_3.addWidget(self.deviceBox)
        self.verticalLayout.addLayout(self.horizontalLayout_3)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.label_2 = QtWidgets.QLabel(self.verticalLayoutWidget)
        self.label_2.setAlignment(QtCore.Qt.AlignCenter)
        self.label_2.setObjectName("label_2")
        self.verticalLayout_2.addWidget(self.label_2)
        self.commonParamsWidget = QtWidgets.QListWidget(self.verticalLayoutWidget)
        self.commonParamsWidget.setObjectName("commonParamsWidget")
        self.verticalLayout_2.addWidget(self.commonParamsWidget)
        self.horizontalLayout.addLayout(self.verticalLayout_2)
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.label_3 = QtWidgets.QLabel(self.verticalLayoutWidget)
        self.label_3.setAlignment(QtCore.Qt.AlignCenter)
        self.label_3.setObjectName("label_3")
        self.verticalLayout_3.addWidget(self.label_3)
        self.allParamsWidget = QtWidgets.QListWidget(self.verticalLayoutWidget)
        self.allParamsWidget.setObjectName("allParamsWidget")
        self.verticalLayout_3.addWidget(self.allParamsWidget)
        self.horizontalLayout.addLayout(self.verticalLayout_3)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(addParameter)
        self.buttonBox.accepted.connect(addParameter.accept)
        self.buttonBox.rejected.connect(addParameter.reject)
        QtCore.QMetaObject.connectSlotsByName(addParameter)

    def retranslateUi(self, addParameter):
        _translate = QtCore.QCoreApplication.translate
        addParameter.setWindowTitle(_translate("addParameter", "Dialog"))
        self.deviceLabel.setText(_translate("addParameter", "Device"))
        self.label_2.setText(_translate("addParameter", "Common Parameters"))
        self.label_3.setText(_translate("addParameter", "All Parameters"))

