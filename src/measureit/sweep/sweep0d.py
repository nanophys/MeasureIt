# sweep0d.py

import time

from PyQt5.QtCore import QObject

from ..tools.util import _autorange_srs
from .base_sweep import BaseSweep
from .progress import SweepState


class Sweep0D(BaseSweep, QObject):
    """Class for the following/live plotting of one parameter against monotonic time.

    As of now, is just an extension of BaseSweep, but has been separated for
    future convenience. The default independent variable for Sweep0D Measurements
    is time. The measured data is transferred in real-time (through QObject slot
    and signal connections) from the Sweep classes to the Runner and Plotter Threads
    to organize, save, and live-plot the tracked parameters.

    Attributes:
    ---------
    max_time:
        The cutoff time (in seconds) where the sweep will end itself.
    *args:
        Used to set Runner and Plotter threads if previously created by GUI.
    **kwargs:
        Passes any keyword arguments to BaseSweep class.
    direction:
        Not utilized in Sweep0D.

    Methods:
    ---------
    flip_direction()
        Informs user that direction can not be flipped in Sweep0D.
    update_values()
        Returns dictionary of updated [parameter:value] pairs.
    """

    def __init__(self, max_time=1e6, *args, **kwargs):
        """Calls the BaseSweep initialization with any extra variables.

        Parameters
        ---------
        max_time:
            The cutoff time (in seconds) where the sweep will end itself.
        *args:
            Used to set Runner and Plotter threads if previously created by GUI.
        **kwargs:
            Passes any keyword arguments to BaseSweep class.
        direction:
            Not utilized in Sweep0D.
        """
        QObject.__init__(self)
        BaseSweep.__init__(self, set_param=None, *args, **kwargs)

        # Amount of time to run
        self.max_time = max_time
        self.progressState.progress = 0.0
        self.update_progress()

    def __str__(self):
        if self.max_time is None:
            return "Continuous 0D Sweep"
        else:
            return f"0D Sweep for {self.max_time} seconds."

    def __repr__(self):
        return f"Sweep0D({self.max_time}, {1.0 / self.inter_delay})"

    def flip_direction(self):
        """The independent variable can not be flipped in Sweep0D.

        The default independent variable is time, and can not be flipped.
        The function is defined so that it will not cause an error if called.
        """
        self.print_main.emit(
            "Can't flip the direction, as we are not sweeping a parameter."
        )
        return

    def update_values(self):
        """Obtains all current parameter values.

        Data is collected in parameter-value pairs, saved to a database if
        desired, and a signal is emitted sending this data to the slots of
        the sweep.

        Returns:
        ---------
        data:
            A list of tuples with the new data. Each tuple is of the format
            (<QCoDeS Parameter>, measurement value). The tuples are passed in order
            of time, set_param (if applicable), then all the followed parameters.
        """
        t = self.progressState.time_elapsed

        data = []

        if t >= self.max_time:
            if (
                self.save_data
                and self.runner is not None
                and self.runner.datasaver is not None
            ):
                self.runner.datasaver.flush_data_to_database()
            self.progressState.state = SweepState.DONE
            self.print_main.emit(f"Done with the sweep, t={t} (s)")
            self.completed.emit()

            return None
        else:
            data.append(("time", t))

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

        if self.save_data and self.progressState.state == SweepState.RUNNING:
            self.runner.datasaver.add_result(*data)

        self.send_updates()

        return data

    def estimate_time(self, verbose=True):
        """Returns an estimate of the amount of time the sweep will take to complete.

        Parameters
        ----------
        verbose:
            Controls whether the function will print out the estimate in the form hh:mm:ss (default True)

        Returns:
        -------
        Time estimate for the sweep, in seconds
        """
        if self.progressState.state in (SweepState.READY, SweepState.RAMPING):
            remaining = self.max_time
        elif self.progressState.state == SweepState.DONE:
            remaining = 0
        else:
            remaining = max(self.max_time - self.progressState.time_elapsed, 0.0)

        if verbose:
            hours, minutes, seconds = self._split_hms(remaining)
            self.print_main.emit(
                f"Estimated time remaining for {repr(self)}: {hours}h:{minutes:02d}m:{seconds:02d}s"
            )

        return remaining

    # --- JSON export/import hooks ---
    def _export_json_specific(self, json_dict: dict) -> dict:
        json_dict["set_param"] = None
        json_dict["attributes"]["max_time"] = self.max_time
        return json_dict

    @classmethod
    def from_json(cls, json_dict, station):
        attrs = json_dict.get("attributes", {})
        # Sweep0D takes max_time plus common BaseSweep kwargs
        max_time = attrs.pop("max_time", 1e6)
        return cls(max_time=max_time, **attrs)
