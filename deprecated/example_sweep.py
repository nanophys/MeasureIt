# example_sweep.py
# Example script to run a simple sweep with the DAQ and the sweep/plotting class

from sweep import Sweep1D, Sweep2D
from daq_driver import Daq, DaqAOChannel, DaqAIChannel
import nidaqmx
import numpy as np
import qcodes as qc
from qcodes.dataset.measurements import Measurement
from qcodes.dataset.database import initialise_or_create_database_at
from qcodes.dataset.data_export import get_data_by_id

def do_1d_sweep(_min_v, _max_v, _step, _freq, _expName, _sampleName):
    # Create the DAQ object
    daq = Daq("Dev1", "testdaq")
    
    # Initialize the database you want to save data to
    try:
        experimentName = _expName
        sampleName = _sampleName
        initialise_or_create_database_at('C:\\Users\\erunb\\MeasureIt\\Databases\\testdatabase.db')
        qc.new_experiment(name=experimentName, sample_name=sampleName)
    except:
        print("Error opening database")
        daq.device.reset_device()
        daq.__del__()
        quit()

    # Set our sweeping parameters
    min_v = _min_v
    max_v = _max_v
    step = _step
    freq = _freq
 
    # Create the sweep argument, tell it which channel to listen to
    s = Sweep1D(daq.submodules["ao0"].voltage, min_v, max_v, step, freq, bidirectional=True, meas=None, plot=True, auto_figs=True)
    s.follow_param(daq.submodules["ai3"].voltage)
    s._create_measurement((s.set_param))
    
    # Run the sweep automatically
    s.autorun()

    # Clean up the DAQ
    daq.__del__()
        
    # Show the experiment data
    ex = qc.dataset.experiment_container.load_experiment_by_name(experimentName, sampleName)
    fii = get_data_by_id(ex.data_sets()[0].run_id)
    print(fii)

def do_2d_sweep():
    # Create the DAQ object
    daq = Daq("Dev1", "testdaq")
    
    # Initialize the database you want to save data to
    try:
        experimentName = "testexp-2d_5"
        sampleName = "sampletest-2d"
        initialise_or_create_database_at('C:\\Users\\erunb\\MeasureIt\\Databases\\testdatabase.db')
        qc.new_experiment(name=experimentName, sample_name=sampleName)
    except:
        print("Error opening database")
        daq.device.reset_device()
        daq.__del__()
        quit()

    # Create the sweep argument, tell it which channel to listen to
    # Sweep parameter arguments are:
    # [ <QCoDeS Parameter>, start value, stop value, step value ]
    in_sweep_params = [daq.submodules["ao0"].voltage, 0, 1, 0.1]
    out_sweep_params = [daq.submodules["ao1"].voltage, 0, 5, 1]
    freq = 1000
    # "measured" parameter
    param = daq.submodules["ai3"].voltage
    s = Sweep2D(in_sweep_params, out_sweep_params, freq, param)
    
    # Run the sweep automatically
    s.autorun()

    # Clean up the DAQ
    daq.__del__()
        
    # Show the experiment data
    #ex = qc.dataset.experiment_container.load_experiment_by_name(experimentName, sampleName)
    #fii = get_data_by_id(ex.data_sets()[0].run_id)
    #print(fii)




#do_1d_sweep(0, 0.1, 0.001, 1000, "test_exp", "example_sample1")
do_2d_sweep()





