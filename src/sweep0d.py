# sweep0d.py

import time
import src.base_sweep
from src.base_sweep import BaseSweep
from PyQt5.QtCore import pyqtSignal, pyqtSlot


class Sweep0D(BaseSweep):
    """
    Class for the following/live plotting, i.e. "0-D sweep" class. As of now, is just an extension of
    BaseSweep, but has been separated for future convenience.
    """

    # Signal for when the sweep is completed
    completed = pyqtSignal()

    def __init__(self, runner=None, plotter=None, max_time=None, complete_func=None, *args, **kwargs):
        """
        Initialization class. Simply calls the BaseSweep initialization, and saves a few extra variables.
        
        Arguments (distinct from BaseSweep):
            runner - RunnerThread object, if prepared ahead of time, i.e. if a GUI is creating these first.
            plotter - PlotterThread object, passed if a GUI has plots it wants the thread to use instead
                      of creating it's own automatically.
            max_time - int counting seconds of the amount of time to run the sweep
        """
        super().__init__(None, *args, **kwargs)

        self.runner = runner
        self.plotter = plotter
        # Direction variable, not used here, but kept to maintain consistency with Sweep1D.
        self.direction = 0
        # Amount of time to run
        self.max_time = max_time

        # Set the function to call when we are finished
        if complete_func is None:
            complete_func = self.no_change
        self.completed.connect(complete_func)

    def __str__(self):
        if self.max_time is None:
            return "Continuous 0D Sweep"
        else:
            return f"0D Sweep for {self.max_time} seconds."

    def __repr__(self):
        return f"Sweep0D({self.max_time}, {1.0 / self.inter_delay})"

    def flip_direction(self):
        """
        Define the function so that when called, it will not throw an error.
        """
        print("Can't flip the direction, as we are not sweeping a parameter.")
        return

    def update_values(self):
        """
        Iterates our data points, changing our setpoint if we are sweeping, and refreshing
        the values of all our followed parameters. If we are saving data, it happens here,
        and the data is returned.
        
        Returns:
            data - A list of tuples with the new data. Each tuple is of the format 
                   (<QCoDeS Parameter>, measurement value). The tuples are passed in order of
                   time, then set_param (if applicable), then all the followed params.
        """
        t = time.monotonic() - self.t0

        data = []

        if t >= self.max_time:
            if self.save_data:
                self.runner.datasaver.flush_data_to_database()
            self.is_running = False
            print(f"Done with the sweep, t={t} s")
            self.completed.emit()

            return None
        else:
            data.append(('time', t))

        persist_param = None
        if self.persist_data is not None:
            data.append(self.persist_data)
            persist_param = self.persist_data[0]

        for i, (l, _, gain) in enumerate(self._srs):
            _autorange_srs(l, 3)

        for i, p in enumerate(self._params):
            if p is not persist_param:
                v = p.get()
                data.append((p, v))

        if self.save_data and self.is_running:
            self.runner.datasaver.add_result(*data)

        self.send_updates()

        # print(data)
        return data
