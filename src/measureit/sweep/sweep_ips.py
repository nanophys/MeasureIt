# sweep_ips.py

import time

from PyQt5.QtCore import QObject

from ..tools.util import _autorange_srs, safe_get, safe_set
from .base_sweep import BaseSweep
from .progress import SweepState
from .sweep0d import Sweep0D


class SweepIPS(Sweep0D, QObject):
    """Child of Sweep0D specialized for Oxford IPS120 Magnet Power Supply.

    Attributes:
    ---------
    magnet:
        Assigns the IPS magnet to the sweep.
    setpoint:
        Determines the starting magnetic field strength (T).
    persistent_magnet:
        Sets the magnet to persistent mode when True.

    Methods:
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
        self._completion_pending = False
        self.follow_param(self.magnet.field)

    def __str__(self):
        return f"Sweeping IPS to {self.setpoint} T."

    def __repr__(self):
        return (
            f"SweepIPS({self.setpoint} T, persistent_magnet={self.persistent_magnet})"
        )

    def update_values(self):
        """Obtains all parameter values for each sweep step.

        Sends data through signal for saving and/or live-plotting.

        Returns:
        ---------
        data:
            A list of tuples with the new data. Each tuple is of the format
            (<QCoDeS Parameter>, measurement value). The tuples are passed in order of
            time, set_param (if applicable), then all the followed parameters.
        """
        if self._completion_pending:
            self._completion_pending = False
            self.mark_done()
            return None

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

        data.append(("time", t))

        # Check our stop conditions- being at the end point
        if self.magnet.mode2() == "At rest":
            self.print_main.emit(
                f"Done with the sweep, B={self.magnet.field.get():.2f} (T), t={t:.2f} (s)."
            )

            # Set status to 'hold'
            self.magnet.activity(0)
            time.sleep(1)
            self.magnet_initialized = False

            self.print_main.emit("Done with the sweep!")

            if self.persistent_magnet is True:
                self.magnet.set_persistent()

            self._completion_pending = True

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

        if self.save_data and self.progressState.state == SweepState.RUNNING:
            self.runner.datasaver.add_result(*data)

        self.send_updates()

        return data

    def pause(self):
        """Pauses any currently active sweeps."""
        BaseSweep.pause(self)
        safe_set(self.instrument.activity, 0)
        self.initialized = False
