# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'mainwindow.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_MeasureIt(object):
    def setupUi(self, MeasureIt):
        MeasureIt.setObjectName("MeasureIt")
        MeasureIt.resize(1249, 738)
        self.centralwidget = QtWidgets.QWidget(MeasureIt)
        self.centralwidget.setObjectName("centralwidget")
        self.scanGroupBox = QtWidgets.QGroupBox(self.centralwidget)
        self.scanGroupBox.setGeometry(QtCore.QRect(500, 20, 401, 441))
        self.scanGroupBox.setObjectName("scanGroupBox")
        self.groupBox = QtWidgets.QGroupBox(self.scanGroupBox)
        self.groupBox.setGeometry(QtCore.QRect(10, 260, 161, 171))
        self.groupBox.setObjectName("groupBox")
        self.verticalLayoutWidget_3 = QtWidgets.QWidget(self.groupBox)
        self.verticalLayoutWidget_3.setGeometry(QtCore.QRect(10, 20, 141, 141))
        self.verticalLayoutWidget_3.setObjectName("verticalLayoutWidget_3")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout(self.verticalLayoutWidget_3)
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.scanLabel = QtWidgets.QLabel(self.verticalLayoutWidget_3)
        self.scanLabel.setObjectName("scanLabel")
        self.verticalLayout.addWidget(self.scanLabel)
        self.paramLabel = QtWidgets.QLabel(self.verticalLayoutWidget_3)
        self.paramLabel.setObjectName("paramLabel")
        self.verticalLayout.addWidget(self.paramLabel)
        self.setpointLabel = QtWidgets.QLabel(self.verticalLayoutWidget_3)
        self.setpointLabel.setObjectName("setpointLabel")
        self.verticalLayout.addWidget(self.setpointLabel)
        self.directionLabel = QtWidgets.QLabel(self.verticalLayoutWidget_3)
        self.directionLabel.setObjectName("directionLabel")
        self.verticalLayout.addWidget(self.directionLabel)
        self.horizontalLayout.addLayout(self.verticalLayout)
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.scanValue = QtWidgets.QLabel(self.verticalLayoutWidget_3)
        self.scanValue.setObjectName("scanValue")
        self.verticalLayout_2.addWidget(self.scanValue)
        self.paramValue = QtWidgets.QLabel(self.verticalLayoutWidget_3)
        self.paramValue.setObjectName("paramValue")
        self.verticalLayout_2.addWidget(self.paramValue)
        self.setpointValue = QtWidgets.QLabel(self.verticalLayoutWidget_3)
        self.setpointValue.setObjectName("setpointValue")
        self.verticalLayout_2.addWidget(self.setpointValue)
        self.directionValue = QtWidgets.QLabel(self.verticalLayoutWidget_3)
        self.directionValue.setObjectName("directionValue")
        self.verticalLayout_2.addWidget(self.directionValue)
        self.horizontalLayout.addLayout(self.verticalLayout_2)
        self.verticalLayout_3.addLayout(self.horizontalLayout)
        self.controlBox = QtWidgets.QGroupBox(self.scanGroupBox)
        self.controlBox.setGeometry(QtCore.QRect(180, 280, 201, 131))
        self.controlBox.setObjectName("controlBox")
        self.startButton = QtWidgets.QPushButton(self.controlBox)
        self.startButton.setGeometry(QtCore.QRect(10, 30, 81, 31))
        self.startButton.setObjectName("startButton")
        self.flipDirectionButton = QtWidgets.QPushButton(self.controlBox)
        self.flipDirectionButton.setGeometry(QtCore.QRect(110, 80, 81, 31))
        self.flipDirectionButton.setObjectName("flipDirectionButton")
        self.pauseButton = QtWidgets.QPushButton(self.controlBox)
        self.pauseButton.setGeometry(QtCore.QRect(10, 80, 71, 31))
        self.pauseButton.setObjectName("pauseButton")
        self.endButton = QtWidgets.QPushButton(self.controlBox)
        self.endButton.setGeometry(QtCore.QRect(110, 30, 81, 31))
        self.endButton.setObjectName("endButton")
        self.setupBox = QtWidgets.QGroupBox(self.scanGroupBox)
        self.setupBox.setGeometry(QtCore.QRect(10, 20, 371, 241))
        self.setupBox.setObjectName("setupBox")
        self.layoutWidget = QtWidgets.QWidget(self.setupBox)
        self.layoutWidget.setGeometry(QtCore.QRect(200, 20, 161, 211))
        self.layoutWidget.setObjectName("layoutWidget")
        self.sweepOptionsLayout = QtWidgets.QVBoxLayout(self.layoutWidget)
        self.sweepOptionsLayout.setContentsMargins(0, 0, 0, 0)
        self.sweepOptionsLayout.setObjectName("sweepOptionsLayout")
        self.bidirectionalBox = QtWidgets.QCheckBox(self.layoutWidget)
        self.bidirectionalBox.setObjectName("bidirectionalBox")
        self.sweepOptionsLayout.addWidget(self.bidirectionalBox)
        self.continualBox = QtWidgets.QCheckBox(self.layoutWidget)
        self.continualBox.setObjectName("continualBox")
        self.sweepOptionsLayout.addWidget(self.continualBox)
        self.rampToStartBox = QtWidgets.QCheckBox(self.layoutWidget)
        self.rampToStartBox.setChecked(True)
        self.rampToStartBox.setObjectName("rampToStartBox")
        self.sweepOptionsLayout.addWidget(self.rampToStartBox)
        self.saveLayout = QtWidgets.QHBoxLayout()
        self.saveLayout.setObjectName("saveLayout")
        self.saveBox = QtWidgets.QCheckBox(self.layoutWidget)
        self.saveBox.setChecked(True)
        self.saveBox.setObjectName("saveBox")
        self.saveLayout.addWidget(self.saveBox)
        self.saveButton = QtWidgets.QPushButton(self.layoutWidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.saveButton.sizePolicy().hasHeightForWidth())
        self.saveButton.setSizePolicy(sizePolicy)
        self.saveButton.setMinimumSize(QtCore.QSize(40, 0))
        self.saveButton.setObjectName("saveButton")
        self.saveLayout.addWidget(self.saveButton)
        self.sweepOptionsLayout.addLayout(self.saveLayout)
        self.livePlotBox = QtWidgets.QCheckBox(self.layoutWidget)
        self.livePlotBox.setChecked(True)
        self.livePlotBox.setObjectName("livePlotBox")
        self.sweepOptionsLayout.addWidget(self.livePlotBox)
        self.plotbinLayout = QtWidgets.QHBoxLayout()
        self.plotbinLayout.setObjectName("plotbinLayout")
        self.plotbinLabel = QtWidgets.QLabel(self.layoutWidget)
        self.plotbinLabel.setObjectName("plotbinLabel")
        self.plotbinLayout.addWidget(self.plotbinLabel)
        self.plotbinEdit = QtWidgets.QLineEdit(self.layoutWidget)
        self.plotbinEdit.setObjectName("plotbinEdit")
        self.plotbinLayout.addWidget(self.plotbinEdit)
        self.sweepOptionsLayout.addLayout(self.plotbinLayout)
        self.layoutWidget1 = QtWidgets.QWidget(self.setupBox)
        self.layoutWidget1.setGeometry(QtCore.QRect(20, 60, 171, 171))
        self.layoutWidget1.setObjectName("layoutWidget1")
        self.scanHorizontalLayout = QtWidgets.QHBoxLayout(self.layoutWidget1)
        self.scanHorizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.scanHorizontalLayout.setObjectName("scanHorizontalLayout")
        self.scanLabelVerticalLayout = QtWidgets.QVBoxLayout()
        self.scanLabelVerticalLayout.setObjectName("scanLabelVerticalLayout")
        self.startLabel = QtWidgets.QLabel(self.layoutWidget1)
        self.startLabel.setObjectName("startLabel")
        self.scanLabelVerticalLayout.addWidget(self.startLabel)
        self.endLabel = QtWidgets.QLabel(self.layoutWidget1)
        self.endLabel.setObjectName("endLabel")
        self.scanLabelVerticalLayout.addWidget(self.endLabel)
        self.stepLabel = QtWidgets.QLabel(self.layoutWidget1)
        self.stepLabel.setObjectName("stepLabel")
        self.scanLabelVerticalLayout.addWidget(self.stepLabel)
        self.stepsecLabel = QtWidgets.QLabel(self.layoutWidget1)
        self.stepsecLabel.setObjectName("stepsecLabel")
        self.scanLabelVerticalLayout.addWidget(self.stepsecLabel)
        self.scanHorizontalLayout.addLayout(self.scanLabelVerticalLayout)
        self.scanValuesLayout = QtWidgets.QVBoxLayout()
        self.scanValuesLayout.setObjectName("scanValuesLayout")
        self.startEdit = QtWidgets.QLineEdit(self.layoutWidget1)
        self.startEdit.setReadOnly(True)
        self.startEdit.setObjectName("startEdit")
        self.scanValuesLayout.addWidget(self.startEdit)
        self.endEdit = QtWidgets.QLineEdit(self.layoutWidget1)
        self.endEdit.setObjectName("endEdit")
        self.scanValuesLayout.addWidget(self.endEdit)
        self.stepEdit = QtWidgets.QLineEdit(self.layoutWidget1)
        self.stepEdit.setObjectName("stepEdit")
        self.scanValuesLayout.addWidget(self.stepEdit)
        self.stepsecEdit = QtWidgets.QLineEdit(self.layoutWidget1)
        self.stepsecEdit.setObjectName("stepsecEdit")
        self.scanValuesLayout.addWidget(self.stepsecEdit)
        self.scanHorizontalLayout.addLayout(self.scanValuesLayout)
        self.scanParameterBox = QtWidgets.QComboBox(self.setupBox)
        self.scanParameterBox.setGeometry(QtCore.QRect(100, 20, 81, 22))
        self.scanParameterBox.setObjectName("scanParameterBox")
        self.scanParameterLabel = QtWidgets.QLabel(self.setupBox)
        self.scanParameterLabel.setGeometry(QtCore.QRect(20, 20, 61, 21))
        self.scanParameterLabel.setObjectName("scanParameterLabel")
        self.setupBox.raise_()
        self.groupBox.raise_()
        self.controlBox.raise_()
        self.parameterGroupBox = QtWidgets.QGroupBox(self.centralwidget)
        self.parameterGroupBox.setGeometry(QtCore.QRect(10, 10, 471, 661))
        self.parameterGroupBox.setObjectName("parameterGroupBox")
        self.inputGroupBox = QtWidgets.QGroupBox(self.parameterGroupBox)
        self.inputGroupBox.setGeometry(QtCore.QRect(10, 20, 451, 301))
        self.inputGroupBox.setObjectName("inputGroupBox")
        self.followParamTable = QtWidgets.QTableWidget(self.inputGroupBox)
        self.followParamTable.setGeometry(QtCore.QRect(10, 20, 431, 271))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.followParamTable.sizePolicy().hasHeightForWidth())
        self.followParamTable.setSizePolicy(sizePolicy)
        self.followParamTable.setObjectName("followParamTable")
        self.followParamTable.setColumnCount(5)
        self.followParamTable.setRowCount(0)
        item = QtWidgets.QTableWidgetItem()
        self.followParamTable.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.followParamTable.setHorizontalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.followParamTable.setHorizontalHeaderItem(2, item)
        item = QtWidgets.QTableWidgetItem()
        self.followParamTable.setHorizontalHeaderItem(3, item)
        item = QtWidgets.QTableWidgetItem()
        self.followParamTable.setHorizontalHeaderItem(4, item)
        self.followParamTable.horizontalHeader().setCascadingSectionResizes(True)
        self.followParamTable.horizontalHeader().setDefaultSectionSize(79)
        self.followParamTable.horizontalHeader().setMinimumSectionSize(10)
        self.followParamTable.horizontalHeader().setSortIndicatorShown(True)
        self.followParamTable.horizontalHeader().setStretchLastSection(True)
        self.editParameterButton = QtWidgets.QToolButton(self.parameterGroupBox)
        self.editParameterButton.setGeometry(QtCore.QRect(160, 600, 151, 41))
        self.editParameterButton.setObjectName("editParameterButton")
        self.outputGroupBox = QtWidgets.QGroupBox(self.parameterGroupBox)
        self.outputGroupBox.setGeometry(QtCore.QRect(10, 330, 451, 261))
        self.outputGroupBox.setObjectName("outputGroupBox")
        self.outputParamTable = QtWidgets.QTableWidget(self.outputGroupBox)
        self.outputParamTable.setGeometry(QtCore.QRect(10, 20, 431, 231))
        self.outputParamTable.setObjectName("outputParamTable")
        self.outputParamTable.setColumnCount(5)
        self.outputParamTable.setRowCount(0)
        item = QtWidgets.QTableWidgetItem()
        self.outputParamTable.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.outputParamTable.setHorizontalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.outputParamTable.setHorizontalHeaderItem(2, item)
        item = QtWidgets.QTableWidgetItem()
        self.outputParamTable.setHorizontalHeaderItem(3, item)
        item = QtWidgets.QTableWidgetItem()
        self.outputParamTable.setHorizontalHeaderItem(4, item)
        self.consoleBox = QtWidgets.QGroupBox(self.centralwidget)
        self.consoleBox.setGeometry(QtCore.QRect(500, 470, 401, 201))
        self.consoleBox.setObjectName("consoleBox")
        self.consoleEdit = QtWidgets.QTextEdit(self.consoleBox)
        self.consoleEdit.setGeometry(QtCore.QRect(10, 20, 381, 161))
        self.consoleEdit.setReadOnly(True)
        self.consoleEdit.setObjectName("consoleEdit")
        self.sequenceGroup = QtWidgets.QGroupBox(self.centralwidget)
        self.sequenceGroup.setGeometry(QtCore.QRect(910, 10, 321, 661))
        self.sequenceGroup.setObjectName("sequenceGroup")
        self.addSweepButton = QtWidgets.QPushButton(self.sequenceGroup)
        self.addSweepButton.setGeometry(QtCore.QRect(30, 580, 131, 31))
        self.addSweepButton.setObjectName("addSweepButton")
        self.removeActionButton = QtWidgets.QPushButton(self.sequenceGroup)
        self.removeActionButton.setGeometry(QtCore.QRect(30, 620, 131, 31))
        self.removeActionButton.setObjectName("removeActionButton")
        self.startSequenceButton = QtWidgets.QPushButton(self.sequenceGroup)
        self.startSequenceButton.setGeometry(QtCore.QRect(170, 620, 141, 31))
        self.startSequenceButton.setObjectName("startSequenceButton")
        self.sequenceWidget = QtWidgets.QListWidget(self.sequenceGroup)
        self.sequenceWidget.setGeometry(QtCore.QRect(10, 20, 301, 501))
        self.sequenceWidget.setObjectName("sequenceWidget")
        self.addSaveButton = QtWidgets.QPushButton(self.sequenceGroup)
        self.addSaveButton.setGeometry(QtCore.QRect(170, 580, 141, 31))
        self.addSaveButton.setObjectName("addSaveButton")
        self.upSequenceButton = QtWidgets.QPushButton(self.sequenceGroup)
        self.upSequenceButton.setGeometry(QtCore.QRect(100, 540, 51, 23))
        self.upSequenceButton.setObjectName("upSequenceButton")
        self.downSequenceButton = QtWidgets.QPushButton(self.sequenceGroup)
        self.downSequenceButton.setGeometry(QtCore.QRect(180, 540, 41, 23))
        self.downSequenceButton.setObjectName("downSequenceButton")
        MeasureIt.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MeasureIt)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1249, 21))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        self.menuInstruments = QtWidgets.QMenu(self.menubar)
        self.menuInstruments.setObjectName("menuInstruments")
        self.menuExperiment = QtWidgets.QMenu(self.menubar)
        self.menuExperiment.setObjectName("menuExperiment")
        self.menuData = QtWidgets.QMenu(self.menubar)
        self.menuData.setObjectName("menuData")
        self.menu2D_Sweep = QtWidgets.QMenu(self.menubar)
        self.menu2D_Sweep.setObjectName("menu2D_Sweep")
        self.menuStation = QtWidgets.QMenu(self.menubar)
        self.menuStation.setObjectName("menuStation")
        MeasureIt.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MeasureIt)
        self.statusbar.setObjectName("statusbar")
        MeasureIt.setStatusBar(self.statusbar)
        self.addInstrumentAction = QtWidgets.QAction(MeasureIt)
        self.addInstrumentAction.setObjectName("addInstrumentAction")
        self.actionQuit = QtWidgets.QAction(MeasureIt)
        self.actionQuit.setObjectName("actionQuit")
        self.removeInstrumentAction = QtWidgets.QAction(MeasureIt)
        self.removeInstrumentAction.setObjectName("removeInstrumentAction")
        self.actionSaveStation = QtWidgets.QAction(MeasureIt)
        self.actionSaveStation.setObjectName("actionSaveStation")
        self.actionLoadStation = QtWidgets.QAction(MeasureIt)
        self.actionLoadStation.setObjectName("actionLoadStation")
        self.actionSave_Sweep = QtWidgets.QAction(MeasureIt)
        self.actionSave_Sweep.setObjectName("actionSave_Sweep")
        self.actionLoad_Sweep = QtWidgets.QAction(MeasureIt)
        self.actionLoad_Sweep.setObjectName("actionLoad_Sweep")
        self.actionSave_Sequence = QtWidgets.QAction(MeasureIt)
        self.actionSave_Sequence.setObjectName("actionSave_Sequence")
        self.actionLoad_Sequence = QtWidgets.QAction(MeasureIt)
        self.actionLoad_Sequence.setObjectName("actionLoad_Sequence")
        self.menuFile.addAction(self.actionQuit)
        self.menuInstruments.addAction(self.addInstrumentAction)
        self.menuInstruments.addAction(self.removeInstrumentAction)
        self.menuInstruments.addSeparator()
        self.menuExperiment.addAction(self.actionSave_Sweep)
        self.menuExperiment.addAction(self.actionLoad_Sweep)
        self.menuExperiment.addSeparator()
        self.menuExperiment.addAction(self.actionSave_Sequence)
        self.menuExperiment.addAction(self.actionLoad_Sequence)
        self.menuStation.addAction(self.actionSaveStation)
        self.menuStation.addAction(self.actionLoadStation)
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuStation.menuAction())
        self.menubar.addAction(self.menuInstruments.menuAction())
        self.menubar.addAction(self.menuExperiment.menuAction())
        self.menubar.addAction(self.menuData.menuAction())
        self.menubar.addAction(self.menu2D_Sweep.menuAction())

        self.retranslateUi(MeasureIt)
        QtCore.QMetaObject.connectSlotsByName(MeasureIt)

    def retranslateUi(self, MeasureIt):
        _translate = QtCore.QCoreApplication.translate
        MeasureIt.setWindowTitle(_translate("MeasureIt", "MainWindow"))
        self.scanGroupBox.setTitle(_translate("MeasureIt", "Variable scan"))
        self.groupBox.setTitle(_translate("MeasureIt", "Status"))
        self.scanLabel.setText(_translate("MeasureIt", "Scanning?"))
        self.paramLabel.setText(_translate("MeasureIt", "Parameter"))
        self.setpointLabel.setText(_translate("MeasureIt", "Setpoint"))
        self.directionLabel.setText(_translate("MeasureIt", "Direction"))
        self.scanValue.setText(_translate("MeasureIt", "False"))
        self.paramValue.setText(_translate("MeasureIt", "--"))
        self.setpointValue.setText(_translate("MeasureIt", "--"))
        self.directionValue.setText(_translate("MeasureIt", "--"))
        self.controlBox.setTitle(_translate("MeasureIt", "Controls"))
        self.startButton.setText(_translate("MeasureIt", "Start"))
        self.flipDirectionButton.setText(_translate("MeasureIt", "Flip direction"))
        self.pauseButton.setText(_translate("MeasureIt", "Pause"))
        self.endButton.setText(_translate("MeasureIt", "End"))
        self.setupBox.setTitle(_translate("MeasureIt", "Setup"))
        self.bidirectionalBox.setText(_translate("MeasureIt", "Bidirectional"))
        self.continualBox.setText(_translate("MeasureIt", "Continual"))
        self.rampToStartBox.setText(_translate("MeasureIt", "Ramp to start"))
        self.saveBox.setText(_translate("MeasureIt", "Save data"))
        self.saveButton.setText(_translate("MeasureIt", "Setup"))
        self.livePlotBox.setText(_translate("MeasureIt", "Live plot"))
        self.plotbinLabel.setText(_translate("MeasureIt", "Plot bin"))
        self.plotbinEdit.setText(_translate("MeasureIt", "1"))
        self.startLabel.setText(_translate("MeasureIt", "Start"))
        self.endLabel.setText(_translate("MeasureIt", "End"))
        self.stepLabel.setText(_translate("MeasureIt", "Step"))
        self.stepsecLabel.setText(_translate("MeasureIt", "Step/sec"))
        self.scanParameterLabel.setText(_translate("MeasureIt", "Parameter:"))
        self.parameterGroupBox.setTitle(_translate("MeasureIt", "Parameters"))
        self.inputGroupBox.setTitle(_translate("MeasureIt", "Inputs (followed parameters)"))
        item = self.followParamTable.horizontalHeaderItem(0)
        item.setText(_translate("MeasureIt", "Parameter"))
        item = self.followParamTable.horizontalHeaderItem(1)
        item.setText(_translate("MeasureIt", "Label"))
        item = self.followParamTable.horizontalHeaderItem(2)
        item.setText(_translate("MeasureIt", "Value"))
        item = self.followParamTable.horizontalHeaderItem(3)
        item.setText(_translate("MeasureIt", "Use"))
        item = self.followParamTable.horizontalHeaderItem(4)
        item.setText(_translate("MeasureIt", "Update"))
        self.editParameterButton.setText(_translate("MeasureIt", "Edit Parameters"))
        self.outputGroupBox.setTitle(_translate("MeasureIt", "Outputs (set/sweeping parameters)"))
        item = self.outputParamTable.horizontalHeaderItem(0)
        item.setText(_translate("MeasureIt", "Parameter"))
        item = self.outputParamTable.horizontalHeaderItem(1)
        item.setText(_translate("MeasureIt", "Label"))
        item = self.outputParamTable.horizontalHeaderItem(2)
        item.setText(_translate("MeasureIt", "Value"))
        item = self.outputParamTable.horizontalHeaderItem(3)
        item.setText(_translate("MeasureIt", "Set"))
        item = self.outputParamTable.horizontalHeaderItem(4)
        item.setText(_translate("MeasureIt", "Get"))
        self.consoleBox.setTitle(_translate("MeasureIt", "Console"))
        self.sequenceGroup.setTitle(_translate("MeasureIt", "Sequence"))
        self.addSweepButton.setText(_translate("MeasureIt", "Add Current Sweep"))
        self.removeActionButton.setText(_translate("MeasureIt", "Remove Selected"))
        self.startSequenceButton.setText(_translate("MeasureIt", "Start Sequence"))
        self.addSaveButton.setText(_translate("MeasureIt", "Add Save Destination"))
        self.upSequenceButton.setText(_translate("MeasureIt", "Up"))
        self.downSequenceButton.setText(_translate("MeasureIt", "Down"))
        self.menuFile.setTitle(_translate("MeasureIt", "File"))
        self.menuInstruments.setTitle(_translate("MeasureIt", "Instruments"))
        self.menuExperiment.setTitle(_translate("MeasureIt", "Experiment"))
        self.menuData.setTitle(_translate("MeasureIt", "Data"))
        self.menu2D_Sweep.setTitle(_translate("MeasureIt", "2D Sweep"))
        self.menuStation.setTitle(_translate("MeasureIt", "Station"))
        self.addInstrumentAction.setText(_translate("MeasureIt", "Add instrument..."))
        self.actionQuit.setText(_translate("MeasureIt", "Quit"))
        self.actionQuit.setShortcut(_translate("MeasureIt", "Ctrl+Q"))
        self.removeInstrumentAction.setText(_translate("MeasureIt", "Remove instrument..."))
        self.actionSaveStation.setText(_translate("MeasureIt", "Save Station"))
        self.actionLoadStation.setText(_translate("MeasureIt", "Load Station"))
        self.actionSave_Sweep.setText(_translate("MeasureIt", "Save Sweep"))
        self.actionLoad_Sweep.setText(_translate("MeasureIt", "Load Sweep"))
        self.actionSave_Sequence.setText(_translate("MeasureIt", "Save Sequence"))
        self.actionLoad_Sequence.setText(_translate("MeasureIt", "Load Sequence"))
