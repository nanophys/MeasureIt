# util.py
# Utility function file

import re
import string
import time
from pathlib import Path

import pandas as pd
import qcodes as qc  # moved to tools
from qcodes import Station, initialise_or_create_database_at

from ..config import get_path

unit_dict = {
    "f": 10**-15,
    "p": 10**-12,
    "n": 10**-9,
    "u": 10**-6,
    "m": 10**-3,
    "k": 10**3,
    "M": 10**6,
    "G": 10**9,
    "": 10**0,
}


def get_measureit_home() -> str:
    """Return the root data directory used by MeasureIt (legacy helper).

    This proxies :func:`measureit.config.get_path` so older code that expects a
    string path continues to work.
    """
    return str(get_path("databases").parent)


class ParameterException(Exception):
    def __init__(self, message, set=False):
        self.message = message
        self.set = set
        super().__init__(self)

    def __str__(self):
        return self.message


def safe_set(p, value, last_try=False):
    """Alerts the user when a parameter can not be set to the chosen value.

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
    """Alerts the user when a parameter's value can not be obtained.

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
            raise ParameterException(f"Could not get {p.name}.", set=False)
    return ret


def connect_to_station(config_file=None):
    """Loads a QCoDeS station configuration file, or starts a new station.

    Parameters
    ---------
    config_file:
        The file path to the desired configuration file.

    Returns:
    ---------
    A loaded or new QCoDeS station for conducting experiments.
    """
    cfg_dir = get_path("cfg")
    cfg_json = cfg_dir / "qcodesrc.json"
    if cfg_json.is_file():
        qc.config.update_config(str(cfg_dir))
    station = Station()
    try:
        station.load_config_file(config_file)
    except Exception:
        print("Couldn't open the station configuration file. Started new station.")

    return station


def connect_station_instruments(station):
    """Loads the instruments from the station to be used during the experiment.

    Parameters
    ---------
    station:
        The station configuration which contains the instrument information.

    Returns:
    ---------
    The list of instruments obtained from the station.
    """
    devices = {}
    for name, instr in station.config["instruments"].items():
        try:
            dev = station.load_instrument(name)
            devices[str(name)] = dev
        except Exception:
            print(
                f"Error connecting to {name}, "
                "either the name is already in use or the device is unavailable."
            )

    return devices


def save_to_csv(ds, fn=None, use_labels=True):
    """Saves the dataset as a CSV file.

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
            use_name = f"{use_name} ({unit})"
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
        db_name = Path(ds.path_to_db).name.split(".")[0]
        fp = get_path("origin_files") / db_name
        fp.mkdir(parents=True, exist_ok=True)
        fn_path = fp / f"{ds.run_id}_{ds.exp_name}_{ds.sample_name}.csv"
        # sanitize filename
        safe = {ord(i): "" for i in "?*<>\"'"}
        fn_clean = fn_path.name.translate(safe)
        fn_path = fn_path.with_name(fn_clean)
        export_ds.to_csv(str(fn_path))


def set_magnet_ramp_ranges(magnet, ranges):
    """Defines the rate and maximum current for magnet sweeps.

    Parameters
    ---------
    magnet:
        The device used to sweep the magnetic field.
    ranges:
        A list which gives the index, rate, and maximum current for ramping.
    """
    if not isinstance(ranges, list):
        print(
            "Must pass a list of current ranges, formatted as follows:\
             [(1, <rate>, <max applicable current>), (2, <rate>, <max applicable current>), ..., \
             (n, <rate>, <max applicable current>]"
        )
        return

    magnet.write(f"CONF:RAMP:RATE:SEG {len(ranges)}")
    time.sleep(0.5)
    for r in ranges:
        if len(r) != 3:
            print(
                "Must pass a list of current ranges, formatted as follows:\
             [(1, <rate>, <max applicable current>), (2, <rate>, <max applicable current>), ..., \
             (n, <rate>, <max applicable current>]"
            )
            return
        magnet.write(f"CONF:RAMP:RATE:CURR {r[0]},{r[1]},{r[2]}")
        time.sleep(0.5)


def set_experiment_sample_names(sweep, exp, samp):
    """Creates a new measurement with desired experiment and sample names."""
    if sweep.save_data is True:
        qc.new_experiment(exp, samp)
    sweep._create_measurement()


def init_database(db, exp, samp, sweep=None):
    """Initializes a new database with exp and sample names and creates a new measurement if a sweep is set.

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
    # Normalize db path
    db_path = Path(db)
    if db_path.suffix != ".db":
        db_path = db_path.with_suffix(".db")
    if not db_path.is_absolute():
        db_path = get_path("databases") / db_path
    initialise_or_create_database_at(str(db_path))
    qc.new_experiment(exp, samp)

    if sweep is not None:
        sweep._create_measurement()


def export_db_to_txt(db_fn, exp_name=None, sample_name=None):
    """Prints all experiment and sample names to the console."""
    db_file = Path(db_fn)
    if db_file.suffix != ".db":
        db_file = db_file.with_suffix(".db")
    if not db_file.is_absolute():
        db_file = get_path("databases") / db_file
    initialise_or_create_database_at(str(db_file))
    experiments = []
    for exp in qc.dataset.experiment_container.experiments():
        if exp_name is None or exp.name is exp_name:
            experiments.append(exp)
            newpath = get_path("origin_files") / exp.name
            newpath.mkdir(parents=True, exist_ok=True)

    count = 0
    for exp in experiments:
        print("exp name: " + exp.name)
        if sample_name is None or exp.sample_name is sample_name:
            print("sample name: " + exp.sample_name)
            write_sample_to_txt(exp, count)
            count += 1


def _value_parser(value):
    """Parses user input for a float and a unit prefix character.

    Returns:
    ---------
    A float and a single character.
    """
    if len(str(value)) == 0:
        raise ParameterException("No value given.")
        return

    value = str(value).strip()

    if value[0] == ".":
        value = "0" + value
    # regex testing stripped value as valid factor string
    # must be exactly a number followed by (space optional) single valid factor char
    # f = femto p = pico u = micro m = milli k = kilo M = Mega G = Giga
    regex = re.compile(r"^([-+]?[\d]*\.?[\d]*[\s]?)([fpnumkMG]?)$")

    parsedVal = regex.search(value)
    if not parsedVal:
        raise ParameterException(f'Could not parse the input "{value}".')
        return

    parsedNum = float(parsedVal.groups(" ")[0])
    parsedUnit = parsedVal.groups(" ")[1]
    parsedValue = parsedNum * unit_dict[parsedUnit]

    return parsedValue


def _name_parser(_name):
    """Parses an instrument name. Must not lead with a numeric character."""
    name = str(_name).strip()

    if len(name) == 0:
        raise ValueError("Invalid. Must provide an instrument name.")
        return ""

    if any(c in name for c in string.whitespace):
        raise ValueError(
            f"Invalid name: {name}. No spaces allowed within instrument name."
        )
        return ""
    elif not name[0].isalpha():
        raise ValueError(f"Invalid name: {name}. First character must be a letter.")
        return ""

    return name


def _autorange_srs(srs, max_changes=1):
    """Autoranges the SR lockins"""

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
        if srs.signal_input() == "voltage":
            sense = srs._VOLT_TO_N[srs.sensitivity.get()]
            srs.sensitivity.set(srs._N_TO_VOLT[int(sense - 1)])
        else:
            sense = srs._CURR_TO_N[srs.sensitivity.get()]
            srs.sensitivity.set(srs._N_TO_CURR[int(sense - 1)])

    def decrement_sensitivity():
        if srs.signal_input() == "voltage":
            sense = srs._VOLT_TO_N[srs.sensitivity.get()]
            srs.sensitivity.set(srs._N_TO_VOLT[int(sense + 1)])
        else:
            sense = srs._CURR_TO_N[srs.sensitivity.get()]
            srs.sensitivity.set(srs._N_TO_CURR[int(sense + 1)])

    sets = 0
    while sets < max_changes and autorange_once():
        sets += 1
        time.sleep(10 * srs.time_constant.get())
