# util.py
# Utility function file

import re
import time
import os
import qcodes as qc
from qcodes.dataset.database import initialise_or_create_database_at
from qcodes.dataset.data_export import get_data_by_id

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

def set_magnet_ramp_ranges(magnet, ranges):
    if not isinstance(ranges, list):
        print("Must pass a list of current ranges, formatted as follows:\
             [(1, <rate>, <max applicable current>), (2, <rate>, <max applicable current>), ..., (n, <rate>, <max applicable current>]")
        return
    
    magnet.write('CONF:RAMP:RATE:SEG {}'.format(len(ranges)))
    for r in ranges:
        if len(ranges) != 3:
            print("Must pass a list of current ranges, formatted as follows:\
             [(1, <rate>, <max applicable current>), (2, <rate>, <max applicable current>), ..., (n, <rate>, <max applicable current>]")
            return
        magnet.write(f'CONF:RAMP:RATE:CURR {r[0], r[1], r[2]}')
        
def set_experiment_sample_names(sweep, exp, samp):
    if sweep.save_data is True:
        qc.new_experiment(exp, samp)
    sweep._create_measurement()

def init_database(db, exp, samp, sweep = None):
    initialise_or_create_database_at(os.environ['MeasureItHome'] + '\\Databases\\' + db)
    qc.new_experiment(exp, samp)
    if sweep is not None:
        sweep._create_measurement()
    
def export_db_to_txt(db_fn, exp_name = None, sample_name = None):
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
            
    
def write_sample_to_txt(exp, count = 0): 
    #print(exp.data_sets())
    for a in exp.data_sets():
        print(a.run_id)
        data = get_data_by_id(a.run_id)
        print(data)
        for dataset in data:
            file_name = "{:02d}".format(count) + "_" + exp.sample_name + '.txt'
            print(file_name)
            file_path = os.environ['MeasureItHome'] + '\\Origin Files\\' + exp.name + "\\" + file_name
            print(file_path)
            file = open(file_path, "w")
            count += 1
            num_params = len(dataset)
    
            for param in dataset:
                file.write(param['label'] + " (" + param['unit'] + ")\t")
        
            file.write("\n")
    
            for i in range(len(dataset[0]['data'])):
                for param in dataset:
                    file.write(str(param['data'][i]) + "\t")
                file.write("\n")
            file.close()
    

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
                 
                 
                 