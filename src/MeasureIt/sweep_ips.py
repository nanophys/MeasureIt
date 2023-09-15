# sweep_ips.py

from .base_sweep import BaseSweep
from .sweep0d import Sweep0D
from .util import _autorange_srs, safe_get, safe_set
from PyQt5.QtCore import QObject
import time


class SweepIPS(Sweep0D, QObject):
    """
    Child of Sweep0D specialized for Oxford IPS120 Magnet Power Supply.
    
    Attributes
    ---------
    magnet:
        Assigns the IPS magnet to the sweep.
    setpoint:
        Determines the starting magnetic field strength (T).
    persistent_magnet:
        Sets the magnet to persistent mode when True.
        
    Methods
    ---------
    update_values()
        Obtains sweep data and sends signal for saving/plotting.
    """

    def __init__(self, magnet, setpoint, persistent_magnet=False, *args, **kwargs):
        QObject.__init__(self)
        Sweep0D.__init__(self, *args, **kwargs)

        self.magnet = magnet
        self.setpoint = setpoint
        self.persistent_magnet = persistent_magnet

        self.initialized = False
        self.follow_param(self.magnet.field)

    def __str__(self):
        return f"Sweeping IPS to {self.setpoint} T."

    def __repr__(self):
        return f"SweepIPS({self.setpoint} T, persistent_magnet={self.persistent_magnet})"

    def update_values(self):
        """
        Obtains all parameter values for each sweep step.
        
        Sends data through signal for saving and/or live-plotting.
        
        Returns
        ---------
        data:
            A list of tuples with the new data. Each tuple is of the format 
            (<QCoDeS Parameter>, measurement value). The tuples are passed in order of
            time, set_param (if applicable), then all the followed parameters.
        """
        
        if not self.initialized:
            self.print_main.emit("Checking the status of the magnet and switch heater.")
            self.magnet.leave_persistent_mode()
            time.sleep(1)

            # Set the field setpoint
            self.magnet.field_setpoint.set(self.setpoint)
            time.sleep(0.5)
            # Set us to go to setpoint
            self.magnet.activity(1)
            self.initialized = True

        data = []
        t = time.monotonic() - self.t0

        data.append(('time', t))

        # Check our stop conditions- being at the end point
        if self.magnet.mode2() == 'At rest':
            self.is_running = False
            if self.save_data:
                self.runner.datasaver.flush_data_to_database()
            self.print_main.emit(f"Done with the sweep, B={self.magnet.field.get():.2f} (T), t={t:.2f} (s).")

            # Set status to 'hold'
            self.magnet.activity(0)
            time.sleep(1)
            self.magnet_initialized = False

            self.print_main.emit("Done with the sweep!")

            if self.persistent_magnet is True:
                self.magnet.set_persistent()

            self.completed.emit()

        persist_param = None
        if self.persist_data is not None:
            data.append(self.persist_data)
            persist_param = self.persist_data[0]

        for i, (l, _, gain) in enumerate(self._srs):
            _autorange_srs(l, 3)

        for i, p in enumerate(self._params):
            if p is not persist_param:
                v = safe_get(p)
                data.append((p, v))

        if self.save_data and self.is_running:
            self.runner.datasaver.add_result(*data)

        self.send_updates()

        return data

    def stop(self):
        """ Stops running any currently active sweeps. """

        BaseSweep.stop(self)
        safe_set(self.instrument.activity, 0)
        self.initialized = False

    def estimate_time(self, verbose=True):
        """
        Returns an estimate of the amount of time the sweep will take to complete.

        Parameters
        ----------
        verbose:
            Controls whether the function will print out the estimate in the form hh:mm:ss (default True)

        Returns
        -------
        Time estimate for the sweep, in seconds
        """

        rate = safe_get(self.magnet.sweeprate_field)
        B_range = abs(safe_get(self.magnet.field) - self.setpoint)

        t_est = B_range * 60 / rate

        hours = int(t_est / 3600)
        minutes = int((t_est % 3600) / 60)
        seconds = t_est % 60
        if verbose is True:
            self.print_main.emit(f'Estimated time for {repr(self)} to run: {hours}h:{minutes:2.0f}m:{seconds:2.0f}s')
        return t_est
