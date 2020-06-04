from functools import partial

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QTableWidgetItem, QMessageBox, QFileDialog, \
    QPushButton, QCheckBox, QHeaderView, QLineEdit, QListWidgetItem, QAction
from PyQt5.QtGui import QTextCursor
import sys, os
from datetime import datetime
import yaml
import matplotlib
from mainwindow_ui import Ui_MeasureIt
from GUI_Dialogs import *
from handlers import WriteStream, OutputThread
from queue import Queue

sys.path.append("..")
import src
from src.daq_driver import Daq, DaqAOChannel, DaqAIChannel
from src.util import _value_parser, _name_parser, save_to_csv
from src.base_sweep import BaseSweep
from src.sweep0d import Sweep0D
from src.sweep1d import Sweep1D
from src.sweep_queue import SweepQueue, DatabaseEntry
import qcodes as qc
from qcodes import Station, initialise_or_create_database_at
from qcodes.dataset.experiment_container import experiments
from qcodes.logger.logger import start_all_logging
from qcodes.dataset.data_set import DataSet, load_by_run_spec
from qcodes.instrument_drivers.Lakeshore.Model_372 import Model_372
from qcodes.instrument_drivers.american_magnetics.AMI430 import AMI430
from qcodes.instrument_drivers.stanford_research.SR860 import SR860
from qcodes.instrument_drivers.tektronix.Keithley_2450 import Keithley2450
from qcodes.tests.instrument_mocks import DummyInstrument, MockParabola

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
matplotlib.use('Qt5Agg')


class UImain(QtWidgets.QMainWindow):
    # To add an instrument, import the driver then add it to our instrument
    # dictionary with the name as the key, and the class as the value
    SUPPORTED_INSTRUMENTS = {'Dummy': DummyInstrument,
                             'Test': MockParabola,
                             'NI DAQ': Daq,
                             'Model_372': Model_372,
                             'AMI430': AMI430,
                             'SR860': SR860,
                             'Keithley2450': Keithley2450}

    def __init__(self, parent=None, config_file=None):
        super(UImain, self).__init__(parent)
        self.ui = Ui_MeasureIt()
        self.ui.setupUi(self)
        self.setWindowTitle("MeasureIt")
        self.ui.scanValue.setText('False')
        self.ui.scanValue.setStyleSheet('color: red')
        self.ui.scanParameterBox.addItem('time', 'time')
        self.sweep_settings = {'time': {'start': '', 'end': '', 'step': '', 'step_sec': '', 'continual': False,
                                        'bidirectional': False, 'plot_bin': 1, 'save_data': True, 'plot_data': True,
                                        'ramp_to_start': True}}

        self.set_param_index = 0
        self.init_tables()
        self.make_connections()

        self.station = None
        self.sweep = None
        self.sweep_queue = SweepQueue(inter_delay=3)

        self.devices = {}
        self.track_params = {}
        self.set_params = {}
        self.shown_follow_params = []
        self.shown_set_params = []

        self.db = ''
        self.exp_name = ''
        self.sample_name = ''
        self.db_set = False
        self.datasets = []

        self.update_dev_menu()
        self.load_station_and_connect_instruments(config_file)
        self.update_datasets()

        self.start_logs()

        # Create Queue and redirect sys.stdout to this queue
        queue = Queue()
        sys.stdout = WriteStream(queue)

        self.thread = OutputThread(queue)
        self.thread.mysignal.connect(self.append_stdout)
        self.thread.start()

        self.show()

    def init_tables(self):
        follow_header = self.ui.followParamTable.horizontalHeader()
        follow_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        follow_header.resizeSection(0, 60)
        follow_header.setSectionResizeMode(1, QHeaderView.Fixed)
        follow_header.resizeSection(1, 60)
        follow_header.setSectionResizeMode(2, QHeaderView.Stretch)
        follow_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        follow_header.setSectionResizeMode(4, QHeaderView.Fixed)
        follow_header.resizeSection(4, 40)

        output_header = self.ui.outputParamTable.horizontalHeader()
        output_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        output_header.resizeSection(0, 60)
        output_header.setSectionResizeMode(1, QHeaderView.Fixed)
        output_header.resizeSection(1, 60)
        output_header.setSectionResizeMode(2, QHeaderView.Stretch)
        output_header.setSectionResizeMode(3, QHeaderView.Fixed)
        output_header.resizeSection(3, 40)
        output_header.setSectionResizeMode(4, QHeaderView.Fixed)
        output_header.resizeSection(4, 40)

    def make_connections(self):
        self.ui.editParameterButton.clicked.connect(self.edit_parameters)
        self.ui.startButton.clicked.connect(self.start_sweep)
        self.ui.pauseButton.clicked.connect(self.pause_resume_sweep)
        self.ui.flipDirectionButton.clicked.connect(self.flip_direction)
        self.ui.endButton.clicked.connect(self.end_sweep)
        self.ui.saveButton.clicked.connect(self.setup_save)

        self.ui.addSweepButton.clicked.connect(self.add_sweep_to_queue)
        self.ui.removeActionButton.clicked.connect(lambda: self.remove_action_from_queue(
            self.ui.sequenceWidget.currentRow()))
        self.ui.startSequenceButton.clicked.connect(self.start_sequence)
        self.ui.addSaveButton.clicked.connect(self.add_save_to_sequence)
        self.ui.upSequenceButton.clicked.connect(lambda: self.move_action_in_sequence(-1))
        self.ui.downSequenceButton.clicked.connect(lambda: self.move_action_in_sequence(+1))

        self.ui.actionSaveStation.triggered.connect(self.save_station)
        self.ui.actionLoadStation.triggered.connect(self.load_station)
        self.ui.actionQuit.triggered.connect(self.close)

        self.ui.actionLoad_Sweep.triggered.connect(self.load_sweep)
        self.ui.actionSave_Sweep.triggered.connect(self.save_sweep)
        self.ui.actionSave_Sequence.triggered.connect(self.save_sequence)
        self.ui.actionLoad_Sequence.triggered.connect(self.load_sequence)

        self.ui.sequenceWidget.itemDoubleClicked.connect(self.edit_sequence_item)

        self.ui.scanParameterBox.currentIndexChanged.connect(self.update_param_combobox)
        self.update_param_combobox(0)

    def update_param_combobox(self, index):
        old_set_param = self.ui.scanParameterBox.itemData(self.set_param_index)
        self.sweep_settings[old_set_param] = {'start': self.ui.startEdit.text(), 'end': self.ui.endEdit.text(),
                                              'step': self.ui.stepEdit.text(),
                                              'step_sec': self.ui.stepsecEdit.text(),
                                              'save_data': self.ui.saveBox.isChecked(),
                                              'plot_data': self.ui.livePlotBox.isChecked(),
                                              'plot_bin': self.ui.plotbinEdit.text(),
                                              'bidirectional': self.ui.bidirectionalBox.isChecked(),
                                              'continual': self.ui.continualBox.isChecked()}

        if index == 0:
            self.ui.startEdit.setReadOnly(True)
            p = self.ui.startEdit.palette()
            p.setColor(self.ui.startEdit.backgroundRole(), Qt.gray)
            self.ui.startEdit.setPalette(p)
            self.ui.stepEdit.setReadOnly(True)
            q = self.ui.stepEdit.palette()
            q.setColor(self.ui.stepEdit.backgroundRole(), Qt.gray)
            self.ui.stepEdit.setPalette(q)
        else:
            self.ui.startEdit.setReadOnly(False)
            p = self.ui.startEdit.palette()
            p.setColor(self.ui.startEdit.backgroundRole(), Qt.white)
            self.ui.startEdit.setPalette(p)
            self.ui.stepEdit.setReadOnly(False)
            q = self.ui.stepEdit.palette()
            q.setColor(self.ui.stepEdit.backgroundRole(), Qt.white)
            self.ui.stepEdit.setPalette(q)

        self.update_sweep_box(self.sweep_settings[self.ui.scanParameterBox.currentData()])
        self.set_param_index = index

    def start_logs(self):
        self.stdout_filename = os.environ['MeasureItHome'] + '\\logs\\stdout\\' + datetime.now().strftime(
            "%Y-%m-%d") + '.txt'
        self.stderr_filename = os.environ['MeasureItHome'] + '\\logs\\stderr\\' + datetime.now().strftime(
            "%Y-%m-%d") + '.txt'

        self.stdout_file = open(self.stdout_filename, 'a')
        sys.stderr = open(self.stderr_filename, 'a')

        self.stdout_file.write('Started program at  ' + datetime.now().strftime("%H:%M:%S") + '\n')
        print('Started program at  ' + datetime.now().strftime("%H:%M:%S"), file=sys.stderr)
        self.stdout_file.close()

        start_all_logging()

    def load_station(self):
        (fileName, x) = QFileDialog.getOpenFileName(self, "Load Station",
                                                    os.environ['MeasureItHome'] + "\\cfg\\",
                                                    "Stations (*.station.yaml)")

        if len(fileName) == 0:
            return

        for name in self.devices.keys():
            self.do_remove_device(name)
        self.load_station_and_connect_instruments(fileName)

    def load_station_and_connect_instruments(self, config_file=None):
        self.station = Station()
        try:
            self.station.load_config_file(config_file)
        except Exception as e:
            self.show_error("Error", "Couldn't open the station configuration file. Started new station.", e)
            return
        if self.station.config is None:
            return

        for name, instr in self.station.config['instruments'].items():
            try:
                dev = self.station.load_instrument(name)
                self.devices[str(name)] = dev
            except Exception as e:
                self.show_error('Instrument Error', f'Error connecting to {name}, '
                                                    'either the name is already in use or the device is unavailable.',
                                e)
        self.update_dev_menu()

    def save_station(self):
        ss_ui = SaveStationGUI(self)
        if ss_ui.exec_():
            fp = ss_ui.get_file()
            default = ss_ui.ui.defaultBox.isChecked()

            if len(fp) > 0:
                self.do_save_station(fp, default)

    def do_save_station(self, filename, set_as_default=False):
        def add_field(ss, instr, field, value):
            try:
                ss[field] = instr[value]
            except KeyError:
                pass

        if '.station.yaml' not in filename:
            filename += '.station.yaml'

        snap = {'instruments': {}}

        for name, instr in self.station.snapshot()['instruments'].items():
            snap['instruments'][name] = {}
            add_field(snap['instruments'][name], instr, 'type', '__class__')
            add_field(snap['instruments'][name], instr, 'address', 'address')
            snap['instruments'][name]['enable_forced_reconnect'] = True
            # Could also save parameter information here

        with open(filename, 'w') as file:
            yaml.dump(snap, file)
            if set_as_default:
                qc.config['station']['default_file'] = filename
                qc.config.save_config(os.environ['MeasureItHome'] + '\\cfg\\qcodesrc.json')

    def edit_parameters(self):
        param_ui = EditParameterGUI(self.devices, self.track_params, self.set_params, self)
        if param_ui.exec_():
            self.track_params = param_ui.new_track_params
            self.set_params = param_ui.new_set_params
            print('Here are the parameters currently being tracked:')
            for name, p in self.track_params.items():
                print(name)
            print('Here are the parameters available for sweeping:')
            for name, p in self.set_params.items():
                print(name)
            self.update_parameters()

    def update_parameters(self):

        # Set up the follow parameter table
        self.ui.followParamTable.clearContents()
        self.ui.followParamTable.setRowCount(0)
        for m, (name, p) in enumerate(self.track_params.items()):
            self.ui.followParamTable.insertRow(m)

            paramitem = QTableWidgetItem(name)
            paramitem.setData(32, p)
            paramitem.setFlags(Qt.ItemIsSelectable)
            self.ui.followParamTable.setItem(m, 0, paramitem)

            labelitem = QLineEdit(p.label)
            labelitem.editingFinished.connect(lambda p=p, labelitem=labelitem:
                                              self.update_labels(p, labelitem.text()))
            self.ui.followParamTable.setCellWidget(m, 1, labelitem)

            valueitem = QTableWidgetItem(str(p.get()))
            self.ui.followParamTable.setItem(m, 2, valueitem)

            includeBox = QCheckBox()
            includeBox.setChecked(True)
            self.ui.followParamTable.setCellWidget(m, 3, includeBox)

            updateButton = QPushButton("Get")
            updateButton.clicked.connect(lambda checked, m=m, p=p, valueitem=valueitem:
                                         valueitem.setText(str(p.get())))
            self.ui.followParamTable.setCellWidget(m, 4, updateButton)

        # Set up the output parameter table
        self.ui.outputParamTable.clearContents()
        self.ui.outputParamTable.setRowCount(0)
        self.ui.scanParameterBox.clear()
        self.ui.scanParameterBox.addItem('time', 'time')
        for n, (name, p) in enumerate(self.set_params.items()):
            self.ui.outputParamTable.insertRow(n)

            paramitem = QTableWidgetItem(name)
            paramitem.setData(32, p)
            paramitem.setFlags(Qt.ItemIsSelectable)
            self.ui.outputParamTable.setItem(n, 0, paramitem)

            labelitem = QLineEdit(p.label)
            labelitem.editingFinished.connect(lambda p=p, labelitem=labelitem:
                                              self.update_labels(p, labelitem.text()))
            self.ui.outputParamTable.setCellWidget(n, 1, labelitem)

            valueitem = QLineEdit(str(p.get()))
            self.ui.outputParamTable.setCellWidget(n, 2, valueitem)

            setButton = QPushButton("Set")
            setButton.clicked.connect(lambda checked, p=p, valueitem=valueitem:
                                      self.set_param(p, valueitem))
            self.ui.outputParamTable.setCellWidget(n, 3, setButton)

            getButton = QPushButton("Get")
            getButton.clicked.connect(lambda checked, p=p, valueitem=valueitem:
                                      valueitem.setText(str(p.get())))
            self.ui.outputParamTable.setCellWidget(n, 4, getButton)

            self.ui.scanParameterBox.addItem(p.label, p)
            if p not in list(self.sweep_settings.keys()):
                self.sweep_settings[p] = {'start': '', 'end': '', 'step': '', 'step_sec': '', 'continual': False,
                                          'bidirectional': False, 'plot_bin': 1, 'save_data': True, 'plot_data': True,
                                          'ramp_to_start': True}

    def set_param(self, p, valueitem):
        try:
            if "Int" in repr(p.vals) or "Number" in repr(p.vals):
                p.set(_value_parser(valueitem.text()))
            elif "String" in repr(p.vals):
                p.set(str(valueitem.text()))
            elif "Bool" in repr(p.vals):
                value = valueitem.text()
                if value == "false" or value == "False":
                    p.set(False)
                elif value == "true" or value == "True":
                    p.set(True)
            else:
                p.set(valueitem.text())
        except Exception as e:
            self.show_error('Error', 'Could not set the Parameter to the desired value. Check the command and try '
                                     'again.', e)

    def update_labels(self, p, newlabel):
        p.label = newlabel

        for n, (name, param) in enumerate(list(self.track_params.items())):
            self.ui.followParamTable.cellWidget(n, 1).setText(param.label)
        for n, (name, param) in enumerate(list(self.set_params.items())):
            self.ui.outputParamTable.cellWidget(n, 1).setText(param.label)
        for n in range(self.ui.scanParameterBox.count() - 1):
            param = self.ui.scanParameterBox.itemData(n + 1)
            self.ui.scanParameterBox.setItemText(n + 1, param.label)

    def create_sweep(self):
        # Check if we're scanning time, then if so, do Sweep0D
        if self.ui.scanParameterBox.currentText() == 'time':
            stop = _value_parser(self.ui.endEdit.text())
            stepsec = _value_parser(self.ui.stepsecEdit.text())
            plotbin = self.ui.plotbinEdit.text()
            plotbin = int(plotbin)
            if plotbin < 1:
                self.ui.plotbinEdit.setText('1')
                raise ValueError

            save = self.ui.saveBox.isChecked()
            plot = self.ui.livePlotBox.isChecked()

            sweep = Sweep0D(max_time=stop, inter_delay=1 / stepsec, save_data=save,
                            plot_data=plot, plot_bin=plotbin)
        # Set up Sweep1D if we're not sweeping time
        else:
            start = _value_parser(self.ui.startEdit.text())
            stop = _value_parser(self.ui.endEdit.text())
            step = _value_parser(self.ui.stepEdit.text())
            stepsec = _value_parser(self.ui.stepsecEdit.text())
            plotbin = self.ui.plotbinEdit.text()
            plotbin = int(plotbin)
            if plotbin < 1:
                self.ui.plotbinEdit.setText('1')
                raise ValueError

            set_param = self.ui.scanParameterBox.currentData()
            twoway = self.ui.bidirectionalBox.isChecked()
            continuous = self.ui.continualBox.isChecked()
            save = self.ui.saveBox.isChecked()
            plot = self.ui.livePlotBox.isChecked()

            sweep = Sweep1D(set_param, start, stop, step, inter_delay=1.0 / stepsec,
                            bidirectional=twoway, continual=continuous, save_data=save,
                            plot_data=plot, x_axis_time=0, plot_bin=plotbin)

        for n in range(self.ui.followParamTable.rowCount()):
            if self.ui.followParamTable.cellWidget(n, 3).isChecked():
                sweep.follow_param(self.ui.followParamTable.item(n, 0).data(32))

        sweep.update_signal.connect(self.receive_updates)
        sweep.dataset_signal.connect(self.receive_dataset)

        if isinstance(sweep, Sweep0D) and len(sweep._params) == 0 and sweep.plot_data:
            self.show_error("Error", "Can't plot time against nothing. Either select some parameters to follow or "
                                     "unselect \'plot data\'.")
            sweep = None

        return sweep

    def start_sweep(self):
        if self.sweep is not None:
            if self.sweep.is_running:
                alert = QMessageBox()
                new_sweep = alert.question(self, "Warning!",
                                           "A sweep is already running! Stop the current sweep and start a new one?",
                                           alert.Yes | alert.No)

                if new_sweep == alert.Yes:
                    self.sweep.stop()
                    self.sweep.kill()
                    self.sweep = None
                else:
                    return
            elif self.sweep.set_param == self.ui.scanParameterBox.currentData() \
                    and self.ui.rampToStartBox.isChecked() is False:
                alert = QMessageBox()
                new_sweep = alert.question(self, "Warning!",
                                           "You are about to start a new sweep of the parameter you just swept, "
                                           "without ramping from the current setpoint to the start value. Are you "
                                           "sure you wish to do so?", alert.Yes | alert.No)

                if new_sweep == alert.Yes:
                    self.sweep.kill()
                    self.sweep = None
                else:
                    return
            else:
                self.sweep.kill()

        try:
            self.sweep = self.create_sweep()
            if self.sweep is None:
                return
        except ValueError:
            self.show_error("Error", "One or more of the sweep input values are invalid. "
                                     "Valid inputs consist of a number optionally followed by "
                                     "suffix f/p/n/u/m/k/M/G.")
            return

        save = self.ui.saveBox.isChecked()
        if save and self.db_set is False:
            if not self.setup_save():
                self.show_error('Error',
                                "Database was not opened. Set save information before running the sweep again.")
                return

        self.sweep.start(ramp_to_start=self.ui.rampToStartBox.isChecked())

    def pause_resume_sweep(self):
        if self.sweep is None:
            return

        if self.sweep.is_running:
            self.sweep.stop()
            self.ui.pauseButton.setText("Resume")
        else:
            self.sweep.resume()
            self.ui.pauseButton.setText("Pause")

    def flip_direction(self):
        if self.sweep is None:
            return

        self.sweep.flip_direction()

    def end_sweep(self):
        if self.sweep is None:
            return

        print('trying to kill the sweep')
        self.sweep.kill()
        self.sweep = None

    def add_sweep_to_queue(self):
        try:
            sweep = self.create_sweep()
            if sweep is None:
                return
        except ValueError as e:
            self.show_error("Error", "One or more of the sweep input values are invalid. "
                                     "Valid inputs consist of a number optionally followed by "
                                     "suffix f/p/n/u/m/k/M/G.", e)
            return

        self.sweep_queue.append(sweep)
        self.update_sequence_table()

    def update_sequence_table(self, cursor=-1):
        self.ui.sequenceWidget.clear()
        for n, action in enumerate(self.sweep_queue.queue):
            item = QListWidgetItem(action.__repr__())
            item.setData(32, action)
            self.ui.sequenceWidget.addItem(item)

        self.ui.sequenceWidget.setCurrentRow(cursor)

    def remove_action_from_queue(self, action):
        if isinstance(action, int) and action >= 0:
            self.sweep_queue.delete(action)
            self.update_sequence_table()

    def move_action_in_sequence(self, change):
        row = self.ui.sequenceWidget.currentRow()
        if row == -1:
            return
        action = self.ui.sequenceWidget.currentItem().data(32)

        new_pos = self.sweep_queue.move(action, change)
        self.update_sequence_table(cursor=new_pos)

    def add_save_to_sequence(self):
        default_db = self.db
        default_exp = self.exp_name
        default_sample = self.sample_name
        for action in self.sweep_queue.queue:
            if isinstance(action, DatabaseEntry):
                default_db = action.db
                default_exp = action.exp
                default_sample = action.samp

        save_data_ui = SaveDataGUI(self, default_db, default_exp, default_sample)
        if save_data_ui.exec_():
            (db, exp_name, sample_name) = save_data_ui.get_save_info()
            db_entry = DatabaseEntry(db, exp_name, sample_name, self.sweep_queue.begin_next)
            self.sweep_queue.append(db_entry)
            self.update_sequence_table()

    def edit_sequence_item(self, action):
        n = -1
        for num, item in enumerate(self.sweep_queue.queue):
            if action.data(32) is item:
                n = num

        if n == -1:
            return

        if isinstance(self.sweep_queue.queue[n], BaseSweep):
            edit_sweep_ui = EditSweepGUI(self, self.sweep_queue.queue[n])
            r = edit_sweep_ui.exec_()
            if r == 1:
                self.sweep_queue.replace(n, edit_sweep_ui.return_sweep())
                self.update_sequence_table()
            elif r == 2:
                self.sweep_queue.delete(n)
                self.update_sequence_table()
        elif isinstance(self.sweep_queue.queue[n], DatabaseEntry):
            entry = self.sweep_queue.queue[n]
            save_data_ui = SaveDataGUI(self, entry.db, entry.exp, entry.samp)
            if save_data_ui.exec_():
                (db, exp_name, sample_name) = save_data_ui.get_save_info()
                db_entry = DatabaseEntry(db, exp_name, sample_name, self.sweep_queue.begin_next)
                self.sweep_queue.replace(n, db_entry)
                self.update_sequence_table()

    def start_sequence(self):
        if self.sweep is not None:
            if self.sweep.is_running:
                alert = QMessageBox()
                new_sweep = alert.question(self, "Warning!",
                                           "A sweep is already running! Stop the current sweep and start a new one?",
                                           alert.Yes | alert.No)

                if new_sweep == alert.Yes:
                    self.sweep.stop()
                    self.sweep.kill()
                    self.sweep = None
                else:
                    return
            else:
                self.sweep.kill()

        save_configured = False
        for s in self.sweep_queue.queue:
            if isinstance(s, DatabaseEntry):
                save_configured = True
            elif isinstance(s, BaseSweep):
                if s.save_data is True and save_configured is False:
                    self.show_error('Error', 'A sweep will try to save data before a database location is set. Fix '
                                             'and try again.')
                    return

        self.sweep_queue.newSweepSignal.connect(lambda sweep: self.new_queue_sweep(sweep))
        self.sweep_queue.start()

    def new_queue_sweep(self, sweep):
        self.sweep = sweep
        self.update_sequence_table()

    def setup_save(self):
        save_data_ui = SaveDataGUI(self, self.db, self.exp_name, self.sample_name)
        if save_data_ui.exec_():
            (self.db, self.exp_name, self.sample_name) = save_data_ui.get_save_info()

            try:
                initialise_or_create_database_at(self.db)
                qc.new_experiment(self.exp_name, self.sample_name)
                self.db_set = True
                return True
            except Exception as e:
                self.show_error('Error', "Error opening up database. Try again.", e)
                return False
        else:
            return False

    def save_sweep(self):
        if self.sweep is None:
            self.sweep = self.create_sweep()

        (filename, x) = QFileDialog.getSaveFileName(self, "Save Sweep as JSON",
                                                    f"{os.environ['MeasureItHome']}\\Experiments\\untitled_sweep.json",
                                                    "JSON (*.txt *.json)")

        if len(filename) > 0:
            self.sweep.export_json(filename)

    def load_sweep(self):
        (filename, x) = QFileDialog.getOpenFileName(self, "Load Sweep from JSON",
                                                    f"{os.environ['MeasureItHome']}\\Experiments\\",
                                                    "JSON (*.txt *.json)")

        if len(filename) > 0:
            try:
                new_sweep = BaseSweep.init_from_json(filename, self.station)
                self.sweep = new_sweep

                settings = {'start': self.sweep.begin, 'end': self.sweep.end, 'step': self.sweep.step,
                            'step_sec': 1/self.sweep.inter_delay, 'save_data': self.sweep.save_data,
                            'plot_data': self.sweep.plot_data, 'plot_bin': self.sweep.plot_bin,
                            'bidirectional': self.sweep.bidirectional, 'continual': self.sweep.continuous}

                self.update_sweep_box(settings)

                # Load parameters
                # TODO: set the set_param box

            except Exception as e:
                self.show_error('Error', "Could not load the sweep.", e)

    def update_sweep_box(self, settings):
        self.ui.startEdit.setText(str(settings['start']))
        self.ui.endEdit.setText(str(settings['end']))
        self.ui.stepEdit.setText(str(settings['step']))
        self.ui.stepsecEdit.setText(str(settings['step_sec']))
        self.ui.saveBox.setChecked(settings['save_data'])
        self.ui.livePlotBox.setChecked(settings['plot_data'])
        self.ui.plotbinEdit.setText(str(settings['plot_bin']))
        self.ui.bidirectionalBox.setChecked(settings['bidirectional'])
        self.ui.continualBox.setChecked(settings['continual'])

    def save_sequence(self):
        (filename, x) = QFileDialog.getSaveFileName(self, "Save Sequence as JSON",
                                                    f"{os.environ['MeasureItHome']}\\Experiments\\untitled.json",
                                                    "JSON (*.txt *.json)")

        if len(filename) > 0:
            self.sweep_queue.export_json(filename)

    def load_sequence(self):
        (filename, x) = QFileDialog.getOpenFileName(self, "Load Sequence from JSON",
                                                    f"{os.environ['MeasureItHome']}\\Experiments\\",
                                                    "JSON (*.txt *.json)")

        if len(filename) > 0:
            try:
                new_queue = SweepQueue.init_from_json(filename, self.station)
                self.sweep_queue = new_queue
                self.update_sequence_table()
                for sweep in self.sweep_queue.queue:
                    sweep.dataset_signal.connect(self.receive_dataset)
                    sweep.update_signal.connect(self.receive_updates)
            except Exception as e:
                self.show_error('Error', "Could not load the sequence.", e)

    def add_device(self):
        # TODO:
        #   Add in ability to pass args and kwargs to the constructor

        device_ui = AddDeviceGUI(self)
        if device_ui.exec_():
            d = device_ui.get_selected()
            try:
                d['name'] = _name_parser(d['name'])
            except ValueError as e:
                self.show_error("Error", "Instrument name must start with a letter.", e)
                return

            if device_ui.ui.nameEdit.text() in self.devices.keys():
                self.show_error("Error", "Already have an instrument with that name in the station.")
                return

            # Now, set up our initialization for each device, if it doesn't follow the standard initialization
            new_dev = None
            try:
                new_dev = self.connect_device(d['device'], d['class'], d['name'], d['address'], d['args'], d['kwargs'])
            except Exception as e:
                self.show_error("Error", f'Couldn\'t connect to the instrument. Check address and try again.', e)
                print(e, file=stderr)
                new_dev = None

            if new_dev is not None:
                self.devices[d['name']] = new_dev
                self.station.add_component(new_dev)
                self.update_dev_menu()

    def connect_device(self, device, classtype, name, address, args=[], kwargs={}):
        if device == 'Dummy' or device == 'Test':
            new_dev = classtype(name)
        else:
            new_dev = classtype(name, address, *args, **kwargs)
        print(args, kwargs)
        return new_dev

    def update_dev_menu(self):
        # TODO: 
        #   Add some clickable action to the name hanging out in the device menu
        self.ui.menuDevices.clear()

        self.ui.addDeviceAction = QAction("Add device...", self.ui.menuDevices)
        self.ui.addDeviceAction.setStatusTip("Connect to a new device")
        self.ui.addDeviceAction.triggered.connect(self.add_device)

        self.ui.removeDeviceAction = QAction("Remove device...", self.ui.menuDevices)
        self.ui.removeDeviceAction.setStatusTip("Disconnect a device")
        self.ui.removeDeviceAction.triggered.connect(self.remove_device)

        self.ui.menuDevices.addAction(self.ui.addDeviceAction)
        self.ui.menuDevices.addAction(self.ui.removeDeviceAction)
        self.ui.menuDevices.addSeparator()

        for name, dev in self.devices.items():
            act = self.ui.menuDevices.addAction(f"{dev.name} ({dev.__class__.__name__})")
            act.setData(dev)

    def remove_device(self):
        remove_ui = RemoveDeviceGUI(self.devices, self)
        if remove_ui.exec_():
            dev = remove_ui.ui.deviceBox.currentText()
            if len(dev) > 0:
                self.do_remove_device(dev)

    def do_remove_device(self, name):
        self.station.remove_component(name)
        dev = self.devices.pop(name)
        dev.close()
        self.update_dev_menu()

    @pyqtSlot(str)
    def append_stdout(self, text):
        self.ui.consoleEdit.moveCursor(QTextCursor.End)
        self.ui.consoleEdit.insertPlainText(text)

        self.stdout_file = open(self.stdout_filename, 'a')
        time = datetime.now().strftime("%H:%M:%S")
        self.stdout_file.write(time + '\t' + text)
        self.stdout_file.close()

    @pyqtSlot(dict)
    def receive_updates(self, update_dict):
        is_running = update_dict['status']
        set_param = update_dict['set_param']
        setpoint = update_dict['setpoint']
        direction = update_dict['direction']

        self.ui.scanValue.setText(f'{is_running}')
        if is_running:
            self.ui.scanValue.setStyleSheet('color: green')
            self.ui.pauseButton.setText('Pause')
        else:
            self.ui.scanValue.setStyleSheet('color: red')
            self.ui.pauseButton.setText('Resume')
        if set_param == 'time':
            self.ui.paramValue.setText('time')
        else:
            self.ui.paramValue.setText(f'{set_param.label}')
        if setpoint is not None:
            self.ui.setpointValue.setText(f'{str(setpoint)}')
        if direction:
            self.ui.directionValue.setText('Backward')
        else:
            self.ui.directionValue.setText('Forward')

    @pyqtSlot(dict)
    def receive_dataset(self, dataset):
        print("receiving dataset")
        self.datasets.append(dataset)
        self.update_datasets()

    def update_datasets(self):
        self.ui.menuData.clear()

        self.ui.loadDatabaseAction = QAction("Load Database", self)
        self.ui.loadDatabaseAction.setStatusTip("Load runs from database")
        self.ui.loadDatabaseAction.triggered.connect(self.load_database)

        self.ui.exportDatasetAction = QAction("Export All", self)
        self.ui.exportDatasetAction.setStatusTip("Export all datasets currently loaded to csv")
        self.ui.exportDatasetAction.triggered.connect(self.export_all_datasets)

        self.ui.removeDatasetAction = QAction("Remove All", self)
        self.ui.removeDatasetAction.setStatusTip("Remove all datasets currently loaded (does not delete data")
        self.ui.removeDatasetAction.triggered.connect(self.remove_all_datasets)

        self.ui.menuData.addAction(self.ui.loadDatabaseAction)
        self.ui.menuData.addAction(self.ui.exportDatasetAction)
        self.ui.menuData.addAction(self.ui.removeDatasetAction)
        self.ui.menuData.addSeparator()

        for ds in self.datasets:
            act = self.ui.menuData.addAction(f"{ds['run id']} - {ds['exp name']} / {ds['sample name']}")
            act.setData(ds)
            act.triggered.connect(partial(self.view_dataset, ds))

    def load_database(self):
        def check_existing_ds(ds):
            for old_ds in self.datasets:
                if str(ds['run id']) == str(old_ds['run id']) and str(ds['exp name']) == str(old_ds['exp name']) \
                        and str(ds['sample name']) == str(old_ds['sample name']) and str(ds['db']) == str(old_ds['db']):
                    return False
            return True

        gui = SaveDataGUI(self)

        if gui.exec_():
            (db, exp_name, sample_name) = gui.get_save_info()
            initialise_or_create_database_at(db)

            exps = experiments()
            new_datasets = 0
            for exp in exps:
                for ds in exp.data_sets():
                    if len(exp_name) == 0 or ds.exp_name == exp_name:
                        if len(sample_name) == 0 or ds.sample_name == sample_name:
                            new_ds = {}
                            new_ds['run id'] = ds.run_id
                            new_ds['exp name'] = ds.exp_name
                            new_ds['sample name'] = ds.sample_name
                            new_ds['db'] = ds.path_to_db

                            if check_existing_ds(new_ds) is True:
                                self.datasets.append(new_ds)
                                new_datasets += 1

            self.update_datasets()
            if new_datasets == 0:
                self.show_error('Error', 'No (new) data sets found with the specified experiment and sample name!')

    def view_dataset(self, ds):
        dataset_gui = ViewDatasetGUI(self, ds)
        dataset_gui.show()
        dataset_gui.activateWindow()

    def export_all_datasets(self):
        directory = QFileDialog.getExistingDirectory(self, "Save Data to .csv",
                                                     f'{os.environ["MeasureItHome"]}\\Origin Files\\')
        if len(directory) == 0:
            return

        unsaved_sets = []
        for ds_info in self.datasets:
            try:
                ds = load_by_run_spec(
                    experiment_name=ds_info['exp name'],
                    sample_name=ds_info['sample name'],
                    captured_run_id=ds_info['run id']
                )

                filename = f"{directory}\\{ds.run_id}_{ds.exp_name}_{ds.sample_name}.csv"
                save_to_csv(ds, filename)
            except:
                unsaved_sets.append(f"{ds.run_id}_{ds.exp_name}_{ds.sample_name}")

        if len(unsaved_sets) > 0:
            error_text = 'Failed to export the following datasets:\n\n'
            for i, ds in enumerate(unsaved_sets):
                error_text += ds
                if i + 1 != len(unsaved_sets):
                    error_text += ', '
            error_text += '.\n\nThis is possibly due to a file name conflict or due to no data being stored in that run.'
            self.show_error('Error', error_text)

    def remove_all_datasets(self):
        alert = QMessageBox()
        removal = alert.question(self, "Warning!",
                                 "You are about to remove all the currently loaded datasets. This will not delete "
                                 "the data, but you will have to reload each run to access them again here. Are you "
                                 "sure you want to do so?", alert.Yes | alert.No)

        if removal == alert.Yes:
            self.datasets = []
            self.update_datasets()

    def show_error(self, title, message, e=None):
        msg_box = QMessageBox()
        msg_box.setWindowTitle(title)
        if e is not None:
            message += f'\n\nPython message: {e}'
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

    def exit(self):
        for key, dev in self.devices.items():
            dev.close()

        if self.sweep is not None:
            self.sweep.kill()

        self.thread.stop = True
        self.thread.exit()
        if not self.thread.wait(5000):
            self.thread.terminate()
            print("Forced stdout thread to terminate.", file=sys.stderr)

        self.stdout_file = open(self.stdout_filename, 'a')
        self.stdout_file.write("Program exited at " + datetime.now().strftime("%H:%M:%S") + '\n')
        print("Program exited at " + datetime.now().strftime("%H:%M:%S"), file=sys.stderr)
        self.stdout_file.close()

        app = QtGui.QGuiApplication.instance()
        app.closeAllWindows()

    def closeEvent(self, event):
        are_you_sure = QMessageBox()
        close = are_you_sure.question(self, "Exit",
                                      "Are you sure you want to close all windows and exit the application?",
                                      are_you_sure.Yes | are_you_sure.No)

        if close == are_you_sure.Yes:
            self.exit()
            event.accept()
        else:
            event.ignore()
            return


def main():
    if os.path.isfile(os.environ['MeasureItHome'] + '\\cfg\\qcodesrc.json'):
        qc.config.update_config(os.environ['MeasureItHome'] + '\\cfg\\')

    app = QtWidgets.QApplication(sys.argv)
    app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app.setStyle('WindowsVista')

    window = UImain()
    window.setAttribute(QtCore.Qt.WA_StyledBackground)

    app.exec_()


if __name__ == "__main__":
    main()
