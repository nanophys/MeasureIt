# sweep_queue.py
import importlib

from src.base_sweep import BaseSweep
from src.sweep0d import Sweep0D
from src.sweep1d import Sweep1D
from collections import deque
import time, os, json
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
import qcodes as qc
from qcodes import initialise_or_create_database_at, Station


class SweepQueue(QObject):
    """
    SweepQueue is a modifieded double-ended queue (deque) object meant for continuously
    running different sweeps. 
    """
    newSweepSignal = pyqtSignal(BaseSweep)

    def __init__(self, inter_delay=1):
        """
        Initializes the variables needed
        """
        super(SweepQueue, self).__init__()
        self.queue = deque([])
        # Pointer to the sweep currently running
        self.current_sweep = None
        # Database information. Can be updated for each run.
        self.database = None
        self.inter_delay = inter_delay
        self.exp_name = ""
        self.sample_name = ""
        self.rts=True

    @classmethod
    def init_from_json(cls, fn, station=Station()):
        with open(fn) as json_file:
            data = json.load(json_file)
            return SweepQueue.import_json(data, station)

    def export_json(self, fn=None):
        json_dict = {}
        json_dict['module'] = self.__class__.__module__
        json_dict['class'] = self.__class__.__name__

        json_dict['inter_delay'] = self.inter_delay
        json_dict['queue'] = []
        for item in self.queue:
            json_dict['queue'].append(item.export_json())

        if fn is not None:
            with open(fn, 'w') as outfile:
                json.dump(json_dict, outfile)

        return json_dict

    @classmethod
    def import_json(cls, json_dict, station=Station()):
        sq = SweepQueue(json_dict['inter_delay'])

        for item_json in json_dict['queue']:
            item_module = importlib.import_module(item_json['module'])
            item_class = getattr(item_module, item_json['class'])
            item = item_class.import_json(item_json, station)
            sq.append(item)

        return sq

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
            elif isinstance(sweep, DatabaseEntry):
                sweep.set_complete_func(self.begin_next)
                self.queue.append(sweep)

    def delete(self, item):
        if isinstance(item, BaseSweep) or isinstance(item, DatabaseEntry):
            self.queue.remove(item)
        else:
            del self.queue[item]

    def replace(self, index, item):
        temp = deque([])

        for i in range(len(self.queue)):
            if i == index:
                temp.append(item)
            else:
                temp.append(self.queue[i])

        del self.queue[index]
        self.queue = temp

    def move(self, item, distance):
        index = -1
        for i, action in enumerate(self.queue):
            if action is item:
                index = i

        new_pos = index+distance
        if index == -1:
            raise ValueError
        elif new_pos < 0:
            new_pos = 0
        elif new_pos >= len(self.queue):
            new_pos = len(self.queue) - 1

        self.queue.remove(item)
        self.queue.insert(new_pos, item)
        return new_pos

    def start(self, rts=True):
        """
        Starts the sweep. Takes the leftmost object in the queue and starts it.
        """
        # Check that there is something in the queue to run
        if len(self.queue) == 0:
            print("No sweeps loaded!")
            return

        print(f"Starting sweeps")
        self.current_sweep = self.queue.popleft()
        if isinstance(self.current_sweep, BaseSweep):
            # Set the database info
            self.set_database()
            self.current_sweep._create_measurement()
            if isinstance(self.current_sweep, Sweep1D):
                print(f"Starting sweep of {self.current_sweep.set_param.label} from {self.current_sweep.begin} \
                      {self.current_sweep.set_param.unit} to {self.current_sweep.end} {self.current_sweep.set_param.unit}")
            elif isinstance(self.current_sweep, Sweep0D):
                print(f"Starting 0D Sweep for {self.current_sweep.max_time} seconds.")
            self.newSweepSignal.emit(self.current_sweep)
        self.current_sweep.start()

    @pyqtSlot()
    def begin_next(self):
        """
        Function called when one sweep is finished and we want to run the next sweep.
        Connected to completed pyqtSignals in the sweeps.
        """
        if isinstance(self.current_sweep, Sweep1D):
            print(f"Finished sweep of {self.current_sweep.set_param.label} from {self.current_sweep.begin} \
                  {self.current_sweep.set_param.unit} to {self.current_sweep.end} {self.current_sweep.set_param.unit}")
        elif isinstance(self.current_sweep, Sweep0D):
            print(f"Finished 0D Sweep of {self.current_sweep.max_time} seconds.")

        self.current_sweep.kill()

        if len(self.queue) > 0:
            self.current_sweep = self.queue.popleft()
            if isinstance(self.current_sweep, BaseSweep):
                self.set_database()
                self.current_sweep._create_measurement()
                if isinstance(self.current_sweep, Sweep1D):
                    print(f"Starting sweep of {self.current_sweep.set_param.label} from {self.current_sweep.begin} \
                          {self.current_sweep.set_param.unit} to {self.current_sweep.end} {self.current_sweep.set_param.unit}")
                elif isinstance(self.current_sweep, Sweep0D):
                    print(f"Starting 0D Sweep for {self.current_sweep.max_time} seconds.")
                time.sleep(self.inter_delay)
                self.newSweepSignal.emit(self.current_sweep)
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
        if self.database is None:
            return

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
            initialise_or_create_database_at(os.environ['MeasureItHome'] + '\\Databases\\' + db + '.db')
            qc.new_experiment(name=exp, sample_name=sample)
        except:
            print("Database info loaded incorrectly!")


class DatabaseEntry(QObject):

    def __init__(self, db='', exp='', samp='', callback=None):
        super(DatabaseEntry, self).__init__()
        self.db = db
        self.exp = exp
        self.samp = samp
        self.callback = callback

    def __str__(self):
        return f'Database entry saving to {self.db} with experiment name {self.exp} and sample name {self.samp}.'

    def __repr__(self):
        return f'Save File: ({self.db}, {self.exp}, {self.samp})'

    @classmethod
    def init_from_json(cls, fn, station=Station()):
        with open(fn) as json_file:
            data = json.load(json_file)
            return DatabaseEntry.import_json(data, station)

    def export_json(self, fn=None):
        json_dict = {}
        json_dict['module'] = self.__class__.__module__
        json_dict['class'] = self.__class__.__name__

        json_dict['attributes'] = {}
        json_dict['attributes']['database'] = self.db
        json_dict['attributes']['experiment'] = self.exp
        json_dict['attributes']['sample'] = self.samp

        if fn is not None:
            with open(fn, 'w') as outfile:
                json.dump(json_dict, outfile)

        return json_dict

    @classmethod
    def import_json(cls, json_dict, station={'instruments': {}}):
        db = json_dict['attributes']['database']
        exp = json_dict['attributes']['experiment']
        sample = json_dict['attributes']['sample']

        return DatabaseEntry(db, exp, sample)

    def start(self):
        initialise_or_create_database_at(self.db)
        qc.new_experiment(name=self.exp, sample_name=self.samp)
        self.callback()

    def set_complete_func(self, func):
        self.callback = func

    def kill(self):
        pass
