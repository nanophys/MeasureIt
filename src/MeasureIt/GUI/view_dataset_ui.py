# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'view_dataset.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_viewDataset(object):
    def setupUi(self, viewDataset):
        viewDataset.setObjectName("viewDataset")
        viewDataset.resize(253, 234)
        self.buttonBox = QtWidgets.QDialogButtonBox(viewDataset)
        self.buttonBox.setGeometry(QtCore.QRect(140, 140, 91, 61))
        self.buttonBox.setOrientation(QtCore.Qt.Vertical)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.horizontalLayoutWidget = QtWidgets.QWidget(viewDataset)
        self.horizontalLayoutWidget.setGeometry(QtCore.QRect(20, 20, 211, 91))
        self.horizontalLayoutWidget.setObjectName("horizontalLayoutWidget")
        self.descriptionLayout = QtWidgets.QHBoxLayout(self.horizontalLayoutWidget)
        self.descriptionLayout.setContentsMargins(0, 0, 0, 0)
        self.descriptionLayout.setObjectName("descriptionLayout")
        self.labelLayout = QtWidgets.QVBoxLayout()
        self.labelLayout.setObjectName("labelLayout")
        self.databaseBoxLabel = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.databaseBoxLabel.setObjectName("databaseBoxLabel")
        self.labelLayout.addWidget(self.databaseBoxLabel)
        self.experimentBoxLabel = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.experimentBoxLabel.setObjectName("experimentBoxLabel")
        self.labelLayout.addWidget(self.experimentBoxLabel)
        self.sampleBoxLabel = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.sampleBoxLabel.setObjectName("sampleBoxLabel")
        self.labelLayout.addWidget(self.sampleBoxLabel)
        self.runIDBoxLabel = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.runIDBoxLabel.setObjectName("runIDBoxLabel")
        self.labelLayout.addWidget(self.runIDBoxLabel)
        self.descriptionLayout.addLayout(self.labelLayout)
        self.valueLayout = QtWidgets.QVBoxLayout()
        self.valueLayout.setObjectName("valueLayout")
        self.databaseLabel = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.databaseLabel.setObjectName("databaseLabel")
        self.valueLayout.addWidget(self.databaseLabel)
        self.experimentLabel = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.experimentLabel.setObjectName("experimentLabel")
        self.valueLayout.addWidget(self.experimentLabel)
        self.sampleLabel = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.sampleLabel.setObjectName("sampleLabel")
        self.valueLayout.addWidget(self.sampleLabel)
        self.runIDLabel = QtWidgets.QLabel(self.horizontalLayoutWidget)
        self.runIDLabel.setObjectName("runIDLabel")
        self.valueLayout.addWidget(self.runIDLabel)
        self.descriptionLayout.addLayout(self.valueLayout)
        self.saveToTxtButton = QtWidgets.QPushButton(viewDataset)
        self.saveToTxtButton.setGeometry(QtCore.QRect(20, 130, 91, 23))
        self.saveToTxtButton.setObjectName("saveToTxtButton")
        self.plotButton = QtWidgets.QPushButton(viewDataset)
        self.plotButton.setGeometry(QtCore.QRect(20, 160, 91, 23))
        self.plotButton.setObjectName("plotButton")
        self.removeButton = QtWidgets.QPushButton(viewDataset)
        self.removeButton.setGeometry(QtCore.QRect(20, 190, 91, 23))
        self.removeButton.setObjectName("removeButton")

        self.retranslateUi(viewDataset)
        self.buttonBox.accepted.connect(viewDataset.accept)
        self.buttonBox.rejected.connect(viewDataset.reject)
        QtCore.QMetaObject.connectSlotsByName(viewDataset)

    def retranslateUi(self, viewDataset):
        _translate = QtCore.QCoreApplication.translate
        viewDataset.setWindowTitle(_translate("viewDataset", "Dialog"))
        self.databaseBoxLabel.setText(_translate("viewDataset", "Database"))
        self.experimentBoxLabel.setText(_translate("viewDataset", "Experiment"))
        self.sampleBoxLabel.setText(_translate("viewDataset", "Sample"))
        self.runIDBoxLabel.setText(_translate("viewDataset", "Run ID"))
        self.databaseLabel.setText(_translate("viewDataset", "TextLabel"))
        self.experimentLabel.setText(_translate("viewDataset", "TextLabel"))
        self.sampleLabel.setText(_translate("viewDataset", "TextLabel"))
        self.runIDLabel.setText(_translate("viewDataset", "TextLabel"))
        self.saveToTxtButton.setText(_translate("viewDataset", "Save to txt"))
        self.plotButton.setText(_translate("viewDataset", "Plot"))
        self.removeButton.setText(_translate("viewDataset", "Remove"))

