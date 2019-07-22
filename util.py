# util.py
# Utility function file

import re
import time
import qcodes as qc
from qcodes.dataset.database import initialise_or_create_database_at
from qcodes.dataset.data_export import get_data_by_id
from qcodes.instrument_drivers.stanford_research.SR860 import SR860

unit_dict = [
        {'f', 10**-15},
        {'p', 10**-12},
        {'n', 10**-9},
        {'u', 10**-6},
        {'m', 10**-3},
        {'k', 10**3},
        {'M', 10**6},
        {'G', 10**9}
        ]

def set_experiment_sample_names(sweep, exp, samp):
    if sweep.save_data is True:
        qc.new_experiment(exp, samp)
    sweep._create_measurement()
    
def export_db_to_txt(db_fn, exp_name = None, sample_name = None):
    initialise_or_create_database_at('C:\\Users\\nanouser\\Documents\\MeasureIt\\Databases\\' + db_fn)
    experiments = []
    for exp in qc.dataset.experiment_container.experiments():
        if exp_name is None or exp.name is exp_name:
            experiments.append(exp)
    
    for exp in experiments:
        
        if sample_name is None or exp.sample_name is sample_name:
            write_sample_to_txt(exp)
            
    
def write_sample_to_txt(exp):
    file_path = "Origin Files\\" + exp.name + "\\"
    

def _value_parser(value):
    """
    Parses user input for a float and a unit prefix character. Returns a float
    and a single char
    """
    value = str(value).strip()
    
    if value[0] == '.':
        value = '0' + value
    # regex testing stripped value as valid factor string
    # must be exactly a number followed by (space optional) single valid factor char 
    # f = femto p = pico u = micro m = milli k = kilo M = Mega G = Giga
    regex = re.compile(r"^([-]?[\d]*.?[\d]+[\s]?)([fpnumkMG]?)$")
    
    parsedVal = regex.search(value)
    if not parsedVal:
        return -1
    
    return (float(parsedVal.groups(' ')[0]), parsedVal.groups(' ')[1])
    
def _autorange_srs(srs, max_changes=1):
    """
    Joe's code, unedited
    """
    def autorange_once():
        r = srs.R.get()
        sens = srs.sensitivity.get()
        if r > 0.9 * sens:
            return srs.increment_sensitivity()
        elif r < 0.1 * sens:
            return srs.decrement_sensitivity()
        return False
    sets = 0
    while autorange_once() and sets < max_changes:
        sets += 1
        time.sleep(10*srs.time_constant.get())