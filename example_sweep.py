# Example script to run a simple sweep with the DAQ and the sweep/plotting class

from joe_sweep import Sweep
from daq_driver import Daq, DaqAOChannel, DaqAIChannel
import nidaqmx
import numpy as np
import qcodes as qc
from qcodes.dataset.measurements import Measurement
from qcodes.dataset.database import initialise_or_create_database_at
from qcodes.dataset.data_export import get_data_by_id


# Create the DAQ object
daq = Daq("Dev1", "testdaq", 2, 24)
    
# Initialize the database you want to save data to
experimentName = 'demotest1'
sampleName = 'daq sample1'
initialise_or_create_database_at('C:\\Users\\nanouser\\MeasureIt\\testdatabase.db')
qc.new_experiment(name=experimentName, sample_name=sampleName)
    
# Create the sweep argument, tell it which channel to listen to
s = Sweep()
s.follow_param(daq.submodules["ai3"].voltage)

# Need to add a task to the output channels!
task = nidaqmx.Task()
daq.submodules["ao0"].add_self_to_task(task)
    
# Set our sweeping parameters
min_v = 0
max_v = 5
step = 0.1
freq = 10

# Run the sweep
s.sweep(daq.submodules["ao0"].voltage, np.linspace(min_v, max_v, (max_v-min_v)/step+1), inter_delay=1/freq)

# Clean up the DAQ
daq.submodules["ao0"].clear_task()
task.close()
daq.device.reset_device()
daq.__del__()
    
# Show the experiment data
ex = qc.dataset.experiment_container.load_experiment_by_name(experimentName, sampleName)
fii = get_data_by_id(ex.data_sets()[0].run_id)
print(fii)

