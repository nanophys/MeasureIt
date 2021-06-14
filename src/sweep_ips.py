# sweep_ips.py

from src.sweep0d import Sweep0D
from src.util import _autorange_srs
from PyQt5.QtCore import QObject
import time


class SweepIPS(Sweep0D, QObject):

    def __init__(self, magnet, setpoint, persistent_magnet=False, *args, **kwargs):
        Sweep0D.__init__(self, *args, **kwargs)
        QObject.__init__(self)

        self.magnet = magnet
        self.setpoint = setpoint
        self.persistent_magnet = persistent_magnet

        self.initialized = False
        self.follow_param(self.magnet.field)

    def __str__(self):
        return f"Sweeping IPS to {self.setpoint} T."

    def __repr__(self):
        return f"SweepIPS({self.setpoint} T)"

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
        if not self.initialized:
            print("Checking the status of the magnet and switch heater.")
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
            print(f"Done with the sweep, B={self.magnet.field.get():.2f} T, t={t:.2f} s.")

            # Set status to 'hold'
            self.magnet.activity(0)
            time.sleep(1)
            self.magnet_initialized = False

            print("Done with the sweep!")

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
                v = p.get()
                data.append((p, v))

        if self.save_data and self.is_running:
            self.runner.datasaver.add_result(*data)

        self.send_updates()

        # print(data)
        return data
