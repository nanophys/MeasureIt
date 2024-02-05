# util.py
# Utility function file

import re
import time
import os
import string
import qcodes as qc
import pandas as pd
from qcodes import initialise_or_create_database_at, Station
from pathlib import Path

unit_dict = {
    'f': 10 ** -15,
    'p': 10 ** -12,
    'n': 10 ** -9,
    'u': 10 ** -6,
    'm': 10 ** -3,
    'k': 10 ** 3,
    'M': 10 ** 6,
    'G': 10 ** 9,
    '': 10 ** 0
}

class ParameterException(Exception):
    def __init__(self, message, set=False):
        self.message = message
        self.set = set
        super().__init__(self)

    def __str__(self):
        return self.message


def safe_set(p, value, last_try=False):
    """
    Alerts the user when a parameter can not be set to the chosen value.
    
    Parameters
    ---------
    p:
        The parameter to be set.
    value:
        The desired value.
    last_try:
        Flag to stop attempting to set the value.
    """
    
    ret = None
    try:
        ret = p.set(value)
    except Exception as e:
        if last_try is False:
            print(f"Couldn't set {p.name} to {value}. Trying again.", e)
            time.sleep(1)
            return safe_set(p, value, last_try=True)
        else:
            print(f"Still couldn't set {p.name} to {value}. Giving up.", e)
            raise ParameterException(f"Couldn't set {p.name} to {value}.", set=True)
    return ret


def safe_get(p, last_try=False):
    """
    Alerts the user when a parameter's value can not be obtained.
    
    Parameters
    ---------
    p:
        The parameter to be measured.
    last_try:
        Flag to stop attempting to set the value.
    """
    
    ret = None
    try:
        ret = p.get()
    except Exception as e:
        if last_try is False:
            print(f"Couldn't get {p.name}. Trying again.", e)
            time.sleep(1)
            return safe_get(p, last_try=True)
        else:
            print(f"Still couldn't get {p.name}. Giving up.", e)
            raise ParameterException(f'Could not get {p.name}.', set=False)
    return ret


def connect_to_station(config_file=None):
    """
    Loads a QCoDeS station configuration file, or starts a new station.
    
    Parameters
    ---------
    config_file:
        The file path to the desired configuration file.
        
    Returns
    ---------
    A loaded or new QCoDeS station for conducting experiments.
    """
    
    if os.path.isfile(str(Path(os.environ['MeasureItHome'] + '\\cfg\\qcodesrc.json'))):
        qc.config.update_config(str(Path(os.environ['MeasureItHome'] + '\\cfg\\')))
    station = Station()
    try:
        station.load_config_file(config_file)
    except Exception:
        print("Couldn't open the station configuration file. Started new station.")

    return station


def connect_station_instruments(station):
    """
    Loads the instruments from the station to be used during the experiment.
    
    Parameters
    ---------
    station:
        The station configuration which contains the instrument information.
    
    Returns
    ---------
    The list of instruments obtained from the station.
    """
    devices = {}
    for name, instr in station.config['instruments'].items():
        try:
            dev = station.load_instrument(name)
            devices[str(name)] = dev
        except Exception:
            print(f'Error connecting to {name}, '
                  'either the name is already in use or the device is unavailable.')

    return devices


def save_to_csv(ds, fn=None, use_labels=True):
    """
    Saves the dataset as a CSV file.
    
    Parameters
    ---------
    ds:
        The dataset to be saved.
    fn=None:
        The filepath to store the CSV data. If no filepath is given, it will automatically set it to a folder within
        'Origin Files' with the database name and name the csv it by the run_id, exp_name, and sample_name.
    use_labels=True:
        Puts the parameter labels as the column names of the csv, as opposed to the parameter names.
    """
    
    def find_param_label(name):
        use_name = name
        unit = None
        for p_name, ps in ds.paramspecs.items():
            if name == p_name:
                unit = ps.unit
                if ps.label is not None:
                    use_name = ps.label

        if unit is not None:
            use_name = f'{use_name} ({unit})'
        return use_name

    df = ds.to_pandas_dataframe_dict()
    export_ds = pd.DataFrame()
    for key, value in df.items():
        if use_labels:
            export_key = find_param_label(key)
            value.index.name = find_param_label(value.index.name)
        else:
            export_key = key
        export_ds[[export_key]] = value[[key]]

    # Choose where you want the CSV saved
    if fn is not None:
        export_ds.to_csv(fn)
    else:
        db_path = ds.path_to_db.split('\\')
        db = db_path[len(db_path)-1].split('.')[0]

        fp = f'{os.environ["MeasureItHome"]}\\Origin Files\\{db}\\'
        if not os.path.isdir(fp):
            os.mkdir(fp)

        fn = f'{fp}{ds.run_id}_{ds.exp_name}_{ds.sample_name}.csv'
        fn = fn.translate({ord(i): '' for i in '?*<>"\''})
        export_ds.to_csv(fn)

def set_magnet_ramp_ranges(magnet, ranges):
    """ 
    Defines the rate and maximum current for magnet sweeps.
    
    Parameters
    ---------
    magnet:
        The device used to sweep the magnetic field.
    ranges:
        A list which gives the index, rate, and maximum current for ramping.
    """
    
    if not isinstance(ranges, list):
        print("Must pass a list of current ranges, formatted as follows:\
             [(1, <rate>, <max applicable current>), (2, <rate>, <max applicable current>), ..., \
             (n, <rate>, <max applicable current>]")
        return

    magnet.write('CONF:RAMP:RATE:SEG {}'.format(len(ranges)))
    time.sleep(0.5)
    for r in ranges:
        if len(r) != 3:
            print("Must pass a list of current ranges, formatted as follows:\
             [(1, <rate>, <max applicable current>), (2, <rate>, <max applicable current>), ..., \
             (n, <rate>, <max applicable current>]")
            return
        magnet.write(f'CONF:RAMP:RATE:CURR {r[0]},{r[1]},{r[2]}')
        time.sleep(0.5)


def set_experiment_sample_names(sweep, exp, samp):
    """ Creates a new measurement with desired experiment and sample names. """
    
    if sweep.save_data is True:
        qc.new_experiment(exp, samp)
    sweep._create_measurement()


def init_database(db, exp, samp, sweep=None):
    """
    Initializes a new database with exp and sample names and creates a new measurement if a sweep is set.
    
    Parameters
    ---------
    db:
        The desired path of the new database.
    exp:
        The experiment name.
    sample:
        The sample name.
    sweep=None:
        Optional weep object for creating new runs for existing sweeps
    """
    if '.db' not in db:
        db = f'{db}.db'
        
    if str(Path(f'{os.environ["MeasureItHome"]}/Databases/')) in db:
        initialise_or_create_database_at(db)
    else:
        initialise_or_create_database_at(str(Path(os.environ['MeasureItHome'] + '/Databases/' + db)))
    qc.new_experiment(exp, samp)

    if sweep is not None:
        sweep._create_measurement()

def export_db_to_txt(db_fn, exp_name=None, sample_name=None):
    """ Prints all experiment and sample names to the console. """
    
    if '.db' in db_fn:
        initialise_or_create_database_at(os.environ['MeasureItHome'] + '\\Databases\\' + db_fn)
    else:
        initialise_or_create_database_at(os.environ['MeasureItHome'] + '\\Databases\\' + db_fn + '.db')
    experiments = []
    for exp in qc.dataset.experiment_container.experiments():
        if exp_name is None or exp.name is exp_name:
            experiments.append(exp)
            newpath = os.environ['MeasureItHome'] + '\\Origin Files\\' + exp.name
            if not os.path.exists(newpath):
                os.makedirs(newpath)

    count = 0
    for exp in experiments:
        print("exp name: " + exp.name)
        if sample_name is None or exp.sample_name is sample_name:
            print("sample name: " + exp.sample_name)
            write_sample_to_txt(exp, count)
            count += 1

def _value_parser(value):
    """
    Parses user input for a float and a unit prefix character. 
    
    Returns
    ---------
    A float and a single character.
    """
    if len(str(value)) == 0:
        raise ParameterException('No value given.')
        return

    value = str(value).strip()

    if value[0] == '.':
        value = '0' + value
    # regex testing stripped value as valid factor string
    # must be exactly a number followed by (space optional) single valid factor char 
    # f = femto p = pico u = micro m = milli k = kilo M = Mega G = Giga
    regex = re.compile(r"^([-+]?[\d]*\.?[\d]*[\s]?)([fpnumkMG]?)$")

    parsedVal = regex.search(value)
    if not parsedVal:
        raise ParameterException(f'Could not parse the input "{value}".')
        return

    parsedNum = float(parsedVal.groups(' ')[0])
    parsedUnit = parsedVal.groups(' ')[1]
    parsedValue = parsedNum * unit_dict[parsedUnit]

    return parsedValue


def _name_parser(_name):
    """
    Parses an instrument name. Must not lead with a numeric character.
    """
    name = str(_name).strip()

    if len(name) == 0:
        raise ValueError('Invalid. Must provide an instrument name.')
        return ''

    if any(c in name for c in string.whitespace):
        raise ValueError(f'Invalid name: {name}. No spaces allowed within instrument name.')
        return ''
    elif not name[0].isalpha():
        raise ValueError(f'Invalid name: {name}. First character must be a letter.')
        return ''

    return name


def _autorange_srs(srs, max_changes=1):
    """
    Autoranges the SR lockins
    """

    def autorange_once():
        r = srs.R.get()
        sens = srs.sensitivity.get()
        if r > 0.9 * sens:
            increment_sensitivity()
            return True
        elif r < 0.1 * sens:
            decrement_sensitivity()
            return True
        return False

    def increment_sensitivity():
        if srs.signal_input() == 'voltage':
            sense = srs._VOLT_TO_N[srs.sensitivity.get()]
            srs.sensitivity.set(srs._N_TO_VOLT[int(sense - 1)])
        else:
            sense = srs._CURR_TO_N[srs.sensitivity.get()]
            srs.sensitivity.set(srs._N_TO_CURR[int(sense - 1)])

    def decrement_sensitivity():
        if srs.signal_input() == 'voltage':
            sense = srs._VOLT_TO_N[srs.sensitivity.get()]
            srs.sensitivity.set(srs._N_TO_VOLT[int(sense + 1)])
        else:
            sense = srs._CURR_TO_N[srs.sensitivity.get()]
            srs.sensitivity.set(srs._N_TO_CURR[int(sense + 1)])

    sets = 0
    while sets < max_changes and autorange_once():
        sets += 1
        time.sleep(10 * srs.time_constant.get())
