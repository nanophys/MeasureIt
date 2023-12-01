# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'add_instrument.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_addInstrument(object):
    def setupUi(self, addInstrument):
        addInstrument.setObjectName("addInstrument")
        addInstrument.resize(241, 201)
        self.dialogBox = QtWidgets.QDialogButtonBox(addInstrument)
        self.dialogBox.setGeometry(QtCore.QRect(40, 160, 161, 32))
        self.dialogBox.setOrientation(QtCore.Qt.Horizontal)
        self.dialogBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.dialogBox.setObjectName("dialogBox")
        self.horizontalLayoutWidget = QtWidgets.QWidget(addInstrument)
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
        self.instrumentBox = QtWidgets.QComboBox(self.horizontalLayoutWidget)
        self.instrumentBox.setObjectName("instrumentBox")
        self.verticalLayout_2.addWidget(self.instrumentBox)
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

        self.retranslateUi(addInstrument)
        self.dialogBox.accepted.connect(addInstrument.accept)
        self.dialogBox.rejected.connect(addInstrument.reject)
        QtCore.QMetaObject.connectSlotsByName(addInstrument)

    def retranslateUi(self, addInstrument):
        _translate = QtCore.QCoreApplication.translate
        addInstrument.setWindowTitle(_translate("addInstrument", "Dialog"))
        self.instrumentLabel.setText(_translate("addInstrument", "Instrument"))
        self.nameLabel.setText(_translate("addInstrument", "Name"))
        self.addressLabel.setText(_translate("addInstrument", "Address"))
        self.argsLabel.setText(_translate("addInstrument", "args"))
        self.kwargsLabel.setText(_translate("addInstrument", "kwargs"))

