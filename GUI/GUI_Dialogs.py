from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QListWidgetItem, QFileDialog
import sys, os
import matplotlib.pyplot as plt
from GUI_Measureit import *
from edit_parameter_ui import Ui_editParameter
from add_device_ui import Ui_addDevice
from save_station_ui import Ui_saveStation
from remove_device_ui import Ui_removeDevice
from save_data_ui import Ui_saveData
from edit_sweep_ui import Ui_editSweep
from view_dataset_ui import Ui_viewDataset
from qcodes.dataset.plotting import plot_dataset

sys.path.append("..")
import src
from qcodes import load_by_run_spec
from src.util import _value_parser, save_to_csv
from src.sweep0d import Sweep0D
from src.sweep1d import Sweep1D
from local_instruments import LOCAL_INSTRUMENTS

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"


class EditSweepGUI(QtWidgets.QDialog):
    def __init__(self, parent, sweep):
        super(EditSweepGUI, self).__init__(parent)
        self.parent = parent
        self.ui = Ui_editSweep()
        self.ui.setupUi(self)
        self.setWindowTitle("Edit Sweep")
        self.sweep = sweep

        self.ui.deleteButton.clicked.connect(lambda: self.done(2))

        self.ui.paramBox.addItem('time', 'time')
        for name, p in self.parent.set_params.items():
            self.ui.paramBox.addItem(p.label, p)
        if isinstance(self.sweep, Sweep0D):
            self.ui.paramBox.setCurrentIndex(0)
        elif isinstance(self.sweep, Sweep1D):
            for n in range(self.ui.paramBox.count()):
                if self.ui.paramBox.itemData(n) is sweep.set_param:
                    self.ui.paramBox.setCurrentIndex(n)
        txt = self.ui.paramBox.currentText()
        if self.ui.paramBox.currentText() != 'time':
            self.ui.startEdit.setReadOnly(False)
            p = self.ui.startEdit.palette()
            p.setColor(self.ui.startEdit.backgroundRole(), Qt.white)
            self.ui.startEdit.setPalette(p)
            self.ui.stepEdit.setReadOnly(False)
            q = self.ui.stepEdit.palette()
            q.setColor(self.ui.stepEdit.backgroundRole(), Qt.white)
            self.ui.stepEdit.setPalette(q)

            self.ui.startEdit.setText(str(sweep.begin))
            self.ui.endEdit.setText(str(sweep.end))
            self.ui.stepEdit.setText(str(sweep.step))
            self.ui.stepsecEdit.setText(str(1.0 / sweep.inter_delay))

            self.ui.bidirectionalBox.setChecked(sweep.bidirectional)
            self.ui.continualBox.setChecked(sweep.continuous)
        else:
            self.ui.startEdit.setReadOnly(True)
            p = self.ui.startEdit.palette()
            p.setColor(self.ui.startEdit.backgroundRole(), Qt.gray)
            self.ui.startEdit.setPalette(p)
            self.ui.stepEdit.setReadOnly(True)
            q = self.ui.stepEdit.palette()
            q.setColor(self.ui.stepEdit.backgroundRole(), Qt.gray)
            self.ui.stepEdit.setPalette(q)

            self.ui.endEdit.setText(str(sweep.max_time))
            self.ui.stepsecEdit.setText(str(1.0 / sweep.inter_delay))

        self.ui.saveBox.setChecked(sweep.save_data)
        self.ui.livePlotBox.setChecked(sweep.plot_data)
        self.ui.plotbinEdit.setText(str(sweep.plot_bin))
        self.ui.paramBox.currentIndexChanged.connect(self.update_param_combobox)

        for param in sweep._params:
            listitem = QListWidgetItem(param.label)
            listitem.setData(32, param)
            self.ui.followParamWidget.addItem(listitem)

    def update_param_combobox(self, index):
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

    def return_sweep(self):
        # Check if we're scanning time, then if so, do Sweep0D
        if self.ui.paramBox.currentText() == 'time':
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

            set_param = self.ui.paramBox.currentData()
            twoway = self.ui.bidirectionalBox.isChecked()
            continuous = self.ui.continualBox.isChecked()
            save = self.ui.saveBox.isChecked()
            plot = self.ui.livePlotBox.isChecked()

            sweep = Sweep1D(set_param, start, stop, step, inter_delay=1.0 / stepsec,
                            bidirectional=twoway, continual=continuous, save_data=save,
                            plot_data=plot, x_axis_time=0, plot_bin=plotbin)

        for n in range(self.ui.followParamWidget.count()):
            sweep.follow_param(self.ui.followParamWidget.item(n).data(32))

        sweep.update_signal.connect(self.parent.receive_updates)
        sweep.dataset_signal.connect(self.parent.receive_dataset)
        sweep.set_complete_func(self.parent.sweep_queue.begin_next)

        return sweep


class SaveDataGUI(QtWidgets.QDialog):
    def __init__(self, parent=None, db='', exp='', sample=''):
        super(SaveDataGUI, self).__init__(parent)
        self.parent = parent
        self.ui = Ui_saveData()
        self.ui.setupUi(self)
        self.setWindowTitle("Select Database")
        self.url = db
        self.ui.locationEdit.setText(self.url)
        self.ui.expEdit.setText(exp)
        self.ui.sampleEdit.setText(sample)

        self.ui.browseButton.clicked.connect(self.select_db)

    def select_db(self):
        fileName = QFileDialog.getSaveFileName(self, "Select Database",
                                               f"{os.environ['MeasureItHome']}\\Databases\\",
                                               "Database (*.db)", options=QFileDialog.DontConfirmOverwrite)
        if len(fileName[0]) > 0:
            self.url = fileName[0]
            if '.db' not in self.url:
                self.url += '.db'

            self.ui.locationEdit.setText(self.url)

    def get_save_info(self):
        return self.url, self.ui.expEdit.text(), self.ui.sampleEdit.text()


class SaveStationGUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SaveStationGUI, self).__init__(parent)
        self.parent = parent
        self.ui = Ui_saveStation()
        self.ui.setupUi(self)
        self.setWindowTitle("Save Current Station")
        self.url = None

        self.ui.browseButton.clicked.connect(self.select_file)

    def select_file(self):
        fileName = QFileDialog.getSaveFileName(self, "Save Station",
                                               os.environ['MeasureItHome'] + "\\cfg\\new_station.station.yaml",
                                               "Stations (*.station.yaml)")
        if len(fileName[0]) > 0:
            self.url = fileName[0]
            if '.station' not in self.url and '.yaml' not in self.url:
                self.url += '.station.yaml'
            elif '.station' in self.url and '.yaml' not in self.url:
                self.url += '.station.yaml'
            self.ui.locationEdit.setText(self.url)

    def get_file(self):
        return self.url


class EditParameterGUI(QtWidgets.QDialog):
    def __init__(self, devices, track_params, set_params, parent=None):
        super(EditParameterGUI, self).__init__(parent)
        self.parent = parent
        self.devices = devices
        self.ui = Ui_editParameter()
        self.ui.setupUi(self)

        self.make_connections()
        self.new_track_params = {}
        self.new_set_params = {}

        for name, dev in self.devices.items():
            self.ui.deviceBox.addItem(name, dev)

        for name, p in track_params.items():
            listitem = QListWidgetItem(p.full_name)
            listitem.setData(32, p)
            self.ui.followParamsWidget.addItem(listitem)
            self.new_track_params[p.full_name] = p
        for name, p in set_params.items():
            listitem = QListWidgetItem(p.full_name)
            listitem.setData(32, p)
            self.ui.setParamsWidget.addItem(listitem)
            self.new_set_params[p.full_name] = p

        self.update_avail_device_params(0)

        self.show()

    def update_avail_device_params(self, index):
        self.ui.allParamsWidget.clear()
        if len(self.devices) > 0:
            device = self.ui.deviceBox.currentData()
            for key, p in device.parameters.items():
                listitem = QListWidgetItem(p.full_name)
                listitem.setData(32, p)
                self.ui.allParamsWidget.addItem(listitem)
            for name, submodule in device.submodules.items():
                if hasattr(submodule, 'parameters'):
                    for key, p in submodule.parameters.items():
                        listitem = QListWidgetItem(p.full_name)
                        listitem.setData(32, p)
                        self.ui.allParamsWidget.addItem(listitem)

    def make_connections(self):
        self.ui.addFollowButton.clicked.connect(lambda: self.add_param(self.new_track_params,
                                                                       self.ui.followParamsWidget, 0))
        self.ui.delFollowButton.clicked.connect(lambda: self.del_param(self.new_track_params,
                                                                       self.ui.followParamsWidget))
        self.ui.addSetButton.clicked.connect(lambda: self.add_param(self.new_set_params,
                                                                    self.ui.setParamsWidget, 1))
        self.ui.delSetButton.clicked.connect(lambda: self.del_param(self.new_set_params,
                                                                    self.ui.setParamsWidget))
        self.ui.deviceBox.activated.connect(self.update_avail_device_params)

    def add_param(self, param_dict, widget, setting):
        params = self.ui.allParamsWidget.selectedItems()

        for p in params:
            name = p.data(32).full_name
            if name not in param_dict.keys():
                if (setting == 0 and p.data(32).gettable) or (setting == 1 and p.data(32).settable):
                    listitem = QListWidgetItem(name)
                    listitem.setData(32, p.data(32))
                    widget.addItem(listitem)
                    param_dict[name] = p.data(32)

    def del_param(self, param_dict, widget):
        params = widget.selectedItems()
        for p in params:
            widget.takeItem(widget.row(p))
            param_dict.pop(p.data(32).full_name)


class AddDeviceGUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AddDeviceGUI, self).__init__(parent)
        self.parent = parent
        self.ui = Ui_addDevice()
        self.ui.setupUi(self)
        self.setWindowTitle("Add Device")

        for name, dev in LOCAL_INSTRUMENTS.items():
            self.ui.deviceBox.addItem(name, dev)

        self.show()

    def get_selected(self):
        selected = {}
        selected['device'] = self.ui.deviceBox.currentText()
        selected['class'] = self.ui.deviceBox.currentData()
        selected['name'] = self.ui.nameEdit.text()
        selected['address'] = self.ui.addressEdit.text()
        selected['args'] = []

        for arg in self.ui.argsEdit.text().replace(" ", "").split(','):
            if len(arg) > 0:
                if arg.isnumeric():
                    if '.' in arg:
                        arg = float(arg)
                    else:
                        arg = int(arg)
                elif arg == 'True' or arg == 'true':
                    arg = True
                elif arg == 'False' or arg == 'false':
                    arg = False
                selected['args'].append(arg)

        kwargs = {}
        kw_text = self.ui.kwargsEdit.text().replace(" ", "")
        if len(kw_text) > 0:
            kw_pairs = kw_text.split(",")
            for kwpair in kw_pairs:
                [key, value] = kwpair.split('=', 1)

                if value.isnumeric():
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                elif value == 'True' or value == 'true':
                    value = True
                elif value == 'False' or value == 'false':
                    value = False

                kwargs[key] = value

        selected['kwargs'] = kwargs

        return selected


class RemoveDeviceGUI(QtWidgets.QDialog):
    def __init__(self, devices, parent=None):
        super(RemoveDeviceGUI, self).__init__(parent)
        self.parent = parent
        self.ui = Ui_removeDevice()
        self.ui.setupUi(self)
        self.setWindowTitle("Remove Device")

        for name, dev in devices.items():
            self.ui.deviceBox.addItem(name, dev)

        self.show()


class ViewDatasetGUI(QtWidgets.QDialog):

    def __init__(self, parent, ds):
        super(ViewDatasetGUI, self).__init__(parent)
        self.parent = parent
        self.ui = Ui_viewDataset()
        self.ui.setupUi(self)
        self.setWindowTitle("View Dataset")

        self.ui.databaseLabel.setText(ds['db'])
        self.ui.experimentLabel.setText(str(ds['exp name']))
        self.ui.sampleLabel.setText(str(ds['sample name']))
        self.ui.runIDLabel.setText(str(ds['run id']))

        self.ui.saveToTxtButton.clicked.connect(self.save_to_txt)
        self.ui.plotButton.clicked.connect(self.quick_plot)
        self.ui.removeButton.clicked.connect(self.remove_ds)

        self.ds_info = ds
        self.ds = load_by_run_spec(
            experiment_name=ds['exp name'],
            sample_name=ds['sample name'],
            captured_run_id=ds['run id']
        )

    def save_to_txt(self):
        fileName = QFileDialog.getSaveFileName(self, "Save Data to .csv",
                                               f'{os.environ["MeasureItHome"]}\\Origin Files\\'
                                               f'{self.ds.run_id}_{self.ds.exp_name}_{self.ds.sample_name}.csv',
                                               "Data files (*.csv)")
        if len(fileName[0]) == 0:
            return

        try:
            save_to_csv(self.ds, fileName[0])
        except Exception as e:
            self.parent.show_error('Error', "Couldn't save the data (likely due to a lack of data)", e)

    def quick_plot(self):
        try:
            plot_dataset(self.ds)
            plt.show(block=True)
        except Exception as e:
            self.parent.show_error('Error', "Couldn't plot the data (likely due to a lack of data)", e)

    def remove_ds(self):
        new_datasets = []
        for ds in self.parent.datasets:
            if str(ds['run id']) == str(self.ds.run_id) and str(ds['exp name']) == str(self.ds.exp_name) \
                    and str(ds['sample name']) == str(self.ds.sample_name) and str(ds['db']) == str(self.ds_info['db']):
                continue
            else:
                new_datasets.append(ds)

        self.parent.datasets = new_datasets
        self.parent.update_datasets()
        self.done(1)
