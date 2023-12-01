# sweep_queue.py
import importlib
import json
import os
import time
import types
from collections import deque
from collections.abc import Iterable
from functools import partial

import qcodes as qc
from qcodes import initialise_or_create_database_at, Station
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from .base_sweep import BaseSweep
from .sweep0d import Sweep0D
from .sweep1d import Sweep1D


class SweepQueue(QObject):
    """
    A modifieded double-ended queue meant for continuously running different sweeps.

    'newSweepSignal' is used to send the current sweep information to the BaseSweep
    parent each time that a new sweep is to begin. Data can be saved to different
    databases for each sweep, allowing simple organization of experiments.

    Attributes
    ---------
    inter_delay:
        The time (in seconds) taken between consecutive sweeps.
    queue:
        Double-ended queue used to store sweeps in desired order.
    current_sweep:
        The most recent sweep pulled from the queue.
    current_action:
        The most recent action, sweep or callable, pulled from the queue.
    database:
        Path used for saving the sweep data; able to store different databases
        for individual sweeps.
    exp_name:
        User-defined experiment name.
    sample_name:
        User-defined sample name.
    rts:
        Defaults to true when sweep is started.

    Methods
    ---------
    init_from_json(fn, station=Station())
        Loads previously saved sweep information and runs the 'import_json' method.
    export_json(fn=None)
        Creates JSON dictionary to store queue information.
    import_json(json_dict, station=Station())
        Updates SweepQueue attributes from chosen file.
    append(*s)
        Adds an arbitrary number of sweeps to the queue.
    delete(item)
        Removes/deletes sweeps from the queue.
    replace(index, item)
        Replaces sweep at the given index with a new sweep.
    move(item, distance)
        Moves a sweep to a new position in the queue.
    start(rts=True)
        Begins running the first sweep in the queue.
    stop()
        Stops/pauses any running sweeps.
    resume()
        Resumes any paused sweeps.
    is_running()
        Flag to determine whether a sweep is currently running.
    begin_next()
        Begins the next sweep in the queue upon the completion of a sweep.
    load_database_info(db, exps, samples):
        Loads the database information for each sweep in the queue.
    set_database(self):
        Sets the loaded database information for each sweep before running.
    """

    newSweepSignal = pyqtSignal(BaseSweep)

    def __init__(self, inter_delay=1):
        """
        Initializes the queue.

        Parameters
        ---------
        inter_delay:
            The time (in seconds) taken between consecutive sweeps.
        """

        QObject.__init__(self)
        self.queue = deque([])
        # Pointer to the sweep currently running
        self.current_sweep = None
        self.current_action = None
        # Database information. Can be updated for each run.
        self.database = None
        self.inter_delay = inter_delay
        self.exp_name = ""
        self.sample_name = ""
        self.rts = True

    def __iter__(self):
        """
        Makes sweep_queue objects iterable.
        """
        return iter(self.queue)

    @classmethod
    def init_from_json(cls, fn, station=Station()):
        """
        Loads previously saved sweep information.

        Sends the sweep attributes to the import_json module.

        Parameters
        ---------
        fn:
            Filename path where sweep information is stored.
        station:
            Initializes a QCoDeS station.

        Returns
        ---------
        Located data is sent to import_json method.
        """

        with open(fn) as json_file:
            data = json.load(json_file)
            return SweepQueue.import_json(data, station)

    def export_json(self, fn=None):
        """
        Saves sweep queue attributes as JSON dictionary.

        Called to save sweep setup to avoid repetitive input of commonly
        used sweeps.

        Parameters
        ---------
        fn:
            Represents optional filename to be opened. A copy of the station
            information will be saved in this file.

        Returns
        ---------
        Dictionary containing all current instruments, parameters, and sweep
        attributes.
        """

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
        """Loads desired attributes into current SweepQueue."""

        sq = SweepQueue(json_dict['inter_delay'])

        for item_json in json_dict['queue']:
            item_module = importlib.import_module(item_json['module'])
            item_class = getattr(item_module, item_json['class'])
            item = item_class.import_json(item_json, station)
            sq.append(item)

        return sq

    def append(self, *s):
        """
        Adds an arbitrary number of sweeps to the queue.
        
        Parameters
        ---------
        *s:
            A sweep or DatabaseEntry, or list of them, to be added to the queue.
        """

        for sweep in s:
            if isinstance(sweep, Iterable):
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
            else:
                print(f"Invalid object: {str(sweep)}.\nIf this is a function handle or other callable, add it with "
                      f"the 'append_handle' function.")

    def __iadd__(self, item):
        """
        Overload += to replace append and append_handle.
        Function and parameters should be packed as a tuple(func, arg).
        Database entry and sweep should be pacted as a tuple(db_entry, sweep)

        Paramters
        ---------
        item:
            The object to be added to the sweep_queue. It can be a sweep object, function handle,
            or a tuple for function (func_handle, argument) or database entry (db_entry,sweep).
        """

        if isinstance(item, tuple):
            item, *args = item
            # Unpack the tuple.
            if isinstance(item, types.FunctionType):
                self.append_handle(item, *args)
            else:
                self.append(item, *args)
                # Support db_entry when doing this.
        else:
            # proceed.
            if isinstance(item, types.FunctionType):
                self.append_handle(item)
            else:
                self.append(item)
        return self

    def append_handle(self, fn_handle, *args, **kwargs):
        """
        Adds an arbitrary function call to the queue.

        Parameters
        ---------
        fn_handle:
            Any callable object to be added to the queue.
        *args:
            Arguments to be passed to the function
        **kwargs:
            Keyword arguments to be passed to the function
        """

        # Wrapper around the function to ensure 'begin_next()' is called upon function completion
        def wrap(fn, *w_args, **w_kwargs):
            fn(*w_args, **w_kwargs)
            self.begin_next()

        # Add the wrapped function to the queue
        self.queue.append(partial(wrap, fn_handle, *args, **kwargs))

    def delete(self, item):
        """
        Removes sweeps from the queue.

        Parameters
        ---------
        item: object to be removed from the queue
        """

        if isinstance(item, BaseSweep) or isinstance(item, DatabaseEntry):
            self.queue.remove(item)
        else:
            del self.queue[item]

    def replace(self, index, item):
        """
        Replaces sweep at the given index with a new sweep.

        Parameters
        ---------
        index:
            Position of sweep to be replaced (int).
        item:
            Sweep to be added to the queue at the indexed position.
        """

        temp = deque([])

        for i in range(len(self.queue)):
            if i == index:
                temp.append(item)
            else:
                temp.append(self.queue[i])

        del self.queue[index]
        self.queue = temp

    def move(self, item, distance):
        """
        Moves a sweep to a new position in the queue.

        Parameters
        ---------
        item:
            The name of the sweep to be moved.
        distance:
            The number of index positions for the sweep to be moved.

        Returns
        ---------
        The new index position of the targeted sweep.
        """

        index = -1
        for i, action in enumerate(self.queue):
            if action is item:
                index = i

        new_pos = index + distance
        if index == -1:
            raise ValueError(f"Couldn't find {str(item)} in the queue.")
        elif new_pos < 0:
            new_pos = 0
        elif new_pos >= len(self.queue):
            new_pos = len(self.queue) - 1

        self.queue.remove(item)
        self.queue.insert(new_pos, item)
        return new_pos

    def start(self, rts=True):
        """
        Begins running the first sweep in the queue.

        Parameters
        ---------
        rts: Optional parameter controlling 'ramp_to_start' keyword of sweep
        """

        # Check that there is something in the queue to run
        if len(self.queue) == 0:
            print("No sweeps loaded!")
            return

        print(f"Starting sweeps")
        self.current_action = self.queue.popleft()
        if isinstance(self.current_action, BaseSweep):
            self.current_sweep = self.current_action
            if isinstance(self.current_sweep, Sweep1D):
                print(f"Starting sweep of {self.current_sweep.set_param.label} from {self.current_sweep.begin} "
                      f"({self.current_sweep.set_param.unit}) to {self.current_sweep.end} "
                      f"({self.current_sweep.set_param.unit})")
            elif isinstance(self.current_sweep, Sweep0D):
                print(f"Starting 0D Sweep for {self.current_sweep.max_time} (s).")
            self.newSweepSignal.emit(self.current_sweep)
            self.current_sweep.start(ramp_to_start=rts)
        elif isinstance(self.current_action, DatabaseEntry):
            self.current_action.start()
        elif callable(self.current_action):
            self.current_action()
        else:
            print(f"Invalid action found in the queue!: {str(self.current_action)}"
                  f"Stopping execution of the queue.")

    def stop(self):
        """ Stops/pauses any running sweeps. """

        if self.current_sweep is not None:
            self.current_sweep.stop()
        else:
            print("No sweep currently running, nothing to stop")

    def resume(self):
        """ Resumes any paused sweeps. """

        if self.current_sweep is not None:
            self.current_sweep.resume()
        else:
            print("No current sweep, nothing to resume!")

    def is_running(self):
        """ Flag to determine whether a sweep is currently running. """

        if self.current_sweep is not None:
            return self.current_sweep.is_running
        else:
            print("Sweep queue is not currently running")

    @pyqtSlot()
    def begin_next(self):
        """
        Begins the next sweep in the queue upon the completion of a sweep.

        Connected to completed pyqtSignals in the sweeps.
        """

        if isinstance(self.current_action, Sweep1D):
            print(f"Finished sweep of {self.current_sweep.set_param.label} from {self.current_sweep.begin} "
                  f"({self.current_sweep.set_param.unit}) to {self.current_sweep.end} "
                  f"({self.current_sweep.set_param.unit})")
        elif isinstance(self.current_action, Sweep0D):
            print(f"Finished 0D Sweep of {self.current_sweep.max_time} (s).")

        if isinstance(self.current_action, BaseSweep):
            self.current_sweep.kill()
            self.current_sweep = None

        if len(self.queue) > 0:
            self.current_action = self.queue.popleft()
            if isinstance(self.current_action, BaseSweep):
                self.current_sweep = self.current_action
                if isinstance(self.current_sweep, Sweep1D):
                    print(f"Starting sweep of {self.current_sweep.set_param.label} from {self.current_sweep.begin} "
                          f"({self.current_sweep.set_param.unit}) to {self.current_sweep.end} "
                          f"({self.current_sweep.set_param.unit})")
                elif isinstance(self.current_sweep, Sweep0D):
                    print(f"Starting 0D Sweep for {self.current_sweep.max_time} seconds.")
                time.sleep(self.inter_delay)
                self.newSweepSignal.emit(self.current_sweep)
                self.current_sweep.start()
            elif isinstance(self.current_action, DatabaseEntry):
                self.current_action.start()
            elif callable(self.current_action):
                self.current_action()
            else:
                print(f"Invalid action found in the queue!: {str(self.current_action)}"
                      f"Stopping execution of the queue.")
        else:
            print("Finished all sweeps!")

    def load_database_info(self, db, exps, samples):
        """
        Loads the database information for each sweep in the queue.

        Can take in either (1) a single value for all database, experiment name,
        and sample name arguments, or (2) a list of values, with length equal to
        the number of sweeps loaded into the queue.
        
        Paramters
        ---------
        db:
            The name of the database file for each sweep (list or string).
        exps:
            The name of experiment for each sweep (list or string).
        samples:
            The name of sample for each sweep (list or string).
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

    def estimate_time(self, verbose=False):
        """
        Returns an estimate of the amount of time the sweep queue will take to complete.

        Parameters
        ----------
        verbose:
            Controls whether there will be a printout of the time estimate for each sweep in the queue,
            in the form of hh:mm:ss (default False)

        Returns
        -------
        Time estimate for the sweep, in seconds
        """

        t_est = 0
        for s in self.queue:
            if isinstance(s, BaseSweep):
                t_est += s.estimate_time(verbose=verbose)

        hours = int(t_est / 3600)
        minutes = int((t_est % 3600) / 60)
        seconds = t_est % 60

        print(f'Estimated time for the SweepQueue to run: {hours}h:{minutes:2.0f}m:{seconds:2.0f}s')

        return t_est

    def set_database(self):
        """
        Sets the loaded database information for each sweep before running.

        Database information must be previously loaded using the 'load_database_info'
        method. Creates path for database and begins a new QCoDeS experiment.
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
    """
    Class for database saving configuration for use with SweepQueue

    Attributes
    ---------
    db:
        String with path to database file (.db)
    exp:
        Experiment name for the save data
    samp:
        Sample name for the save data
    callback:
        Function handle for callback function after 'start' completes

    Methods
    ---------
    start()
        Sets the target database to save with experiment name 'exp' and sample name 'samp'
    set_callback(func)
        Sets the callback function to 'func'
    """

    def __init__(self, db='', exp='', samp='', callback=None):
        """
        Parameters
        ---------
        db:
            Path to database (.db) file
        exp:
            Experiment name for saving
        samp:
            Sample name for saving
        callback:
            Optional argument for a callback function to call after 'start' is run
        """

        QObject.__init__(self)
        self.db = db
        self.exp = exp
        self.samp = samp
        self.callback = callback

    def __str__(self):
        return f'Database entry saving to {self.db} with experiment name {self.exp} and sample name {self.samp}.'

    def __repr__(self):
        return f'Save File: ({self.db}, {self.exp}, {self.samp})'

    @classmethod
    def init_from_json(cls, fn):
        with open(fn) as json_file:
            data = json.load(json_file)
            return DatabaseEntry.import_json(data)

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
    def import_json(cls, json_dict):
        db = json_dict['attributes']['database']
        exp = json_dict['attributes']['experiment']
        sample = json_dict['attributes']['sample']

        return DatabaseEntry(db, exp, sample)

    def start(self):
        """
        Sets the database to the values given at initialization, then calls the callback function
        """

        initialise_or_create_database_at(self.db)
        qc.new_experiment(name=self.exp, sample_name=self.samp)
        if self.callback is not None and callable(self.callback):
            self.callback()

    def set_complete_func(self, func, *args, **kwargs):
        """
        Sets the callback function to the given function

        Parameters
        ---------
        func:
            Function handle to call upon completion of database setting
        *args:
            Arbitrary arguments to pass to the callback function
        **kwargs:
            Arbitrary keyword arguments to pass to the callback function
        """

        self.callback = partial(func, *args, **kwargs)
