# sweep_queue.py

from src.base_sweep import BaseSweep
from collections import deque
import time
import qcodes as qc
from qcodes.dataset.database import initialise_or_create_database_at

class SweepQueue(object):
    """
    SweepQueue is a modifieded double-ended queue (deque) object meant for continuously
    running different sweeps. 
    """
    def __init__(self, inter_delay = 1):
        """
        Initializes the variables needed
        """
        self.queue = deque([])
        # Pointer to the sweep currently running
        self.current_sweep = None
        # Database information. Can be updated for each run.
        self.database = None
        self.inter_delay = inter_delay
        self.exp_name = ""
        self.sample_name = ""
    
    
    def append(self, *s):
        """
        Adds a sweep to the queue.
        
        Arguments:
            sweep - BaseSweep object to be added to queue
        """
        for sweep in s:
            if isinstance(sweep, list):
                for l in sweep:
                    # Set the finished signal to call the begin_next() function here
                    l.set_complete_func(self.begin_next)
                    # Add it to the queue
                    self.queue.append(l)
            elif isinstance(sweep, BaseSweep):
                sweep.set_complete_func(self.begin_next)
                self.queue.append(sweep)

        
    def start(self):
        """
        Starts the sweep. Takes the leftmost object in the queue and starts it.
        """
        # Check that there is something in the queue to run
        if len(self.queue) == 0:
            print("No sweeps loaded!")
            return
        
        print(f"Starting sweeps")
        self.current_sweep = self.queue.popleft()
        # Set the database info
        self.set_database()
        self.current_sweep._create_measurement()
        print(f"Starting sweep of {self.current_sweep.set_param.label} from {self.current_sweep.begin} \
              {self.current_sweep.set_param.unit} to {self.current_sweep.end} {self.current_sweep.set_param.unit}")
        self.current_sweep.start()
        
        
    def begin_next(self):
        """
        Function called when one sweep is finished and we want to run the next sweep.
        Connected to completed pyqtSignals in the sweeps.
        """
        print(f"Finished sweep of {self.current_sweep.set_param.label} from {self.current_sweep.begin} \
              {self.current_sweep.set_param.unit} to {self.current_sweep.end} {self.current_sweep.set_param.unit}")
        
        self.current_sweep.kill()
        
        if len(self.queue) > 0:
            self.current_sweep.plotter.clear()
            self.current_sweep = self.queue.popleft()
            self.set_database()
            self.current_sweep._create_measurement()
            print(f"Starting sweep of {self.current_sweep.set_param.label} from {self.current_sweep.begin} \
                  {self.current_sweep.set_param.unit} to {self.current_sweep.end} {self.current_sweep.set_param.unit}")
            time.sleep(self.inter_delay)
            self.current_sweep.start()
        else:
            print("Finished all sweeps!")
    
    
    def load_database_info(self, db, exps, samples):
        """
        Loads in database info for each of the sweeps. Can take in either asingle value for each
        of the database, experiment name, and sample name arguments, or a list of values, with
        length equal to the number of sweeps loaded into the queue.
        
        Arguments:
            db - name of the database file you want to run at, either list or string
            exps - name of experiment you want, can either be list or string
            samples - name of sample, can be either list or string
        """
        # Check if db was loaded correctly
        if isinstance(db, list):
            # Convert to a deque for easier popping from the queue
            self.database = deque(db)
        elif isinstance(db, str):
            self.database = db
        else:
            print("Database info loaded incorrectly!")
            
        # Check again for experiments
        if isinstance(exps, list):
            self.exp_name = deque(exps)
        elif isinstance(exps, str):
            self.exp_name = exps
        else:
            print("Database info loaded incorrectly!")
            
        # Check if samples were loaded correctly
        if isinstance(samples, list):
            self.sample_name = deque(samples)
        elif isinstance(samples, str):
            self.sample_name = samples
        else:
            print("Database info loaded incorrectly!")
    
    
    def set_database(self):
        """
        Changes the database for the next run. Pops out the next item in a list, if that
        is what was loaded, or keeps the same string.
        """
        # Grab the next database file name
        db = ""
        if isinstance(self.database, str):
            db = self.database
        elif isinstance(self.database, deque):
            db = self.database.popleft()
            
        # Grab the next sample name
        sample = ""
        if isinstance(self.sample_name, str):
            sample = self.sample_name
        elif isinstance(self.sample_name, deque):
            sample = self.sample_name.popleft()
    
        # Grab the next experiment name
        exp = ""
        if isinstance(self.exp_name, str):
            exp = self.exp_name
        elif isinstance(self.exp_name, deque):
            exp = self.exp_name.popleft()
        
        # Initialize the database
        try:
            initialise_or_create_database_at('C:\\Users\\erunb\\MeasureIt\\Databases\\' + db + '.db')
            qc.new_experiment(name=exp, sample_name=sample)
        except:
            print("Database info loaded incorrectly!")

