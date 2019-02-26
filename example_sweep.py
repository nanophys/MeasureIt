# Example script to run a simple sweep with the DAQ and the sweep/plotting class

from sweep import Sweep1D
from daq_driver import Daq, DaqAOChannel, DaqAIChannel
import nidaqmx
import numpy as np
import qcodes as qc
from qcodes.dataset.measurements import Measurement
from qcodes.dataset.database import initialise_or_create_database_at
from qcodes.dataset.data_export import get_data_by_id


# Create the DAQ object
daq = Daq("Dev1", "testdaq")
    
# Initialize the database you want to save data to
try:
    experimentName = 'demotest4'
    sampleName = 'daq sample5'
    initialise_or_create_database_at('C:\\Users\\erunb\\MeasureIt\\testdatabase.db')
    qc.new_experiment(name=experimentName, sample_name=sampleName)
except:
    print("Error opening database")
    daq.device.reset_device()
    daq.__del__()
    quit()

# Set our sweeping parameters
min_v = 0
max_v = .1
step = 0.001
freq = 10000.0
 
# Create the sweep argument, tell it which channel to listen to
s = Sweep1D(daq.submodules["ao0"].voltage, min_v, max_v, step, freq, meas=None, plot=True, auto_figs=True)
s.follow_param(daq.submodules["ai3"].voltage)

# Need to add a task to the output channels! VERY IMPORTANT!
task = nidaqmx.Task()
daq.submodules["ao0"].add_self_to_task(task)
    
# Run the sweep automatically
s.autorun()

# Clean up the DAQ
daq.submodules["ao0"].clear_task()
task.close()
daq.__del__()
    
# Show the experiment data
ex = qc.dataset.experiment_container.load_experiment_by_name(experimentName, sampleName)
fii = get_data_by_id(ex.data_sets()[0].run_id)
print(fii)

