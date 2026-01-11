import time

import numpy as np
from PyQt5.QtCore import QObject

from ..tools.util import _autorange_srs, safe_get
from .progress import SweepState
from .sweep1d import Sweep1D


class GateLeakage(Sweep1D, QObject):
    """Extension of Sweep1D to perform gate leakage measurements.

    Sweeps 'set_param' (voltage) while monitoring 'track_param' (current) with
    noise-immune leak detection: triggers on 2 consecutive points exceeding max_I,
    clears after 5 consecutive safe points.

    Attributes:
    ---------
    set_param:
        The independent variable to be swept through a desired range.
    track_param:
        The followed parameter to be measured during the sweep.
    max_I:
        Maximum allowed absolute value for track_param. Sweep reverses when
        |track_param| >= max_I for 2 consecutive points.
    step:
        The step size for the independent variable sweep.
    limit:
        The end value for Sweep1D. Defaults to infinity.
    start:
        The start value for Sweep1D. Defaults to zero.
    flips:
        Tracks the number of times the sweep has changed direction.
    leak_trigger_count:
        Consecutive points where |track_param| >= max_I.
    safe_trigger_count:
        Consecutive points where |track_param| < max_I.
    leak_detected:
        True when leak confirmed (2 consecutive triggers), clears after 5 safe points.

    Methods:
    ---------
    step_param()
        Runs sweep once in both directions while measuring 'track_param'.
    update_values()
        Keeps record of independent variable data during sweep.
    flip_direction()
        Changes direction of the sweep.
    """

    def __init__(
        self, set_param, track_param, max_I, step, limit=np.inf, start=0, **kwargs
    ):
        self.max_I = max_I
        self.flips = 0
        self.track_param = track_param
        self.leak_trigger_count = 0
        self.safe_trigger_count = 0
        self.leak_detected = False

        Sweep1D.__init__(self, set_param, start, limit, step, **kwargs)
        QObject.__init__(self)

        self.follow_param(self.track_param)

    def step_param(self):
        """Runs Sweep1D in both directions by step size.

        Stores data of followed 'track_param' at each setpoint of 'set_param'.
        Changes direction when: (1) |track_param| >= max_I for 2 consecutive points,
        or (2) set_param reaches its limit. Leak detection clears after 5 consecutive
        safe points (|track_param| < max_I). Sweep ends after two direction changes.

        Returns:
        ---------
        A list containing the values of 'set_param' and 'track_param' for each
        setpoint until the sweep is stopped after 2 total flips.
        """
        # Our ending condition is if we end up back at 0 after going forwards and backwards
        if self.flips >= 2 and abs(self.setpoint) <= abs(self.step / (3 / 2)):
            self.flips = 0
            print(f"Done with the sweep, {self.set_param.label}={self.setpoint}")
            # Return None to signal completion without emitting a synthetic datapoint
            # that could violate parameter validators or pollute the dataset
            return None

        # Check if we're at the end (within half a step)
        at_end = abs(self.end) != np.inf and abs(self.setpoint - self.end) <= abs(self.step)

        if at_end:
            self.flip_direction()
            print("tripped output limit")
            return self.step_param()

        # Compute next setpoint and check bounds before setting
        next_setpoint = self.setpoint + self.step
        next_setpoint = self._snap_to_step(next_setpoint, self._snap_origin, self.step)

        # Check if next setpoint exceeds sweep bounds
        if abs(self.end) != np.inf:
            sweep_min = min(self.begin, self.end)
            sweep_max = max(self.begin, self.end)
            if next_setpoint < sweep_min or next_setpoint > sweep_max:
                # Would exceed bounds, treat as end of sweep
                self.flip_direction()
                print("tripped output limit (bounds check)")
                return self.step_param()

        self.setpoint = next_setpoint
        if not self.try_set(self.set_param, self.setpoint):
            return None

        v = safe_get(self.track_param)

        # Check if current exceeds threshold
        if abs(v) >= abs(self.max_I):
            self.leak_trigger_count += 1
            self.safe_trigger_count = 0

            if self.leak_trigger_count >= 2 and not self.leak_detected:
                self.leak_detected = True
                self.flip_direction()
                # After flip, compute and check next setpoint before setting
                post_flip_setpoint = self.setpoint + self.step
                post_flip_setpoint = self._snap_to_step(post_flip_setpoint, self._snap_origin, self.step)
                # Only set if within bounds
                if abs(self.end) != np.inf:
                    sweep_min = min(self.begin, self.end)
                    sweep_max = max(self.begin, self.end)
                    if sweep_min <= post_flip_setpoint <= sweep_max:
                        self.setpoint = post_flip_setpoint
                else:
                    self.setpoint = post_flip_setpoint
                print("tripped input limit")
        else:
            self.safe_trigger_count += 1
            self.leak_trigger_count = 0

            if self.safe_trigger_count >= 5 and self.leak_detected:
                self.leak_detected = False

        return [(self.set_param, self.setpoint), (self.track_param, v)]

    def update_values(self):
        """Iterates and keeps record of independent variable data during sweep.

        Iterates each 'set_param' individually beginning with time.
        If we are saving data, it happens here, and the data is returned.

        Returns:
        ---------
        data:
            A list of tuples with the new data. Each tuple is of the format
            (<QCoDeS Parameter>, measurement value). The tuples are passed in order of
            time, then set_param (if applicable), then all the followed params.
        """
        t = time.monotonic() - self.t0

        data = []
        data.append(("time", t))

        step_data = self.step_param()
        if step_data is None:
            if self.progressState.state != SweepState.KILLED:
                self.mark_done()
            return None

        data += step_data

        persist_param = None
        if self.persist_data is not None:
            data.append(self.persist_data)
            persist_param = self.persist_data[0]

        for i, (l, _, gain) in enumerate(self._srs):
            _autorange_srs(l, 3)

        for i, p in enumerate(self._params):
            if p is not persist_param and p is not self.track_param:
                v = safe_get(p)
                data.append((p, v))

        if self.save_data and self.progressState.state == SweepState.RUNNING:
            self.runner.datasaver.add_result(*data)

        self.send_updates()

        return data

    def flip_direction(self):
        """Changes direction of the sweep.

        Note: Unlike Sweep1D, GateLeakage sweeps from a center point (start, default 0)
        outward in both directions. After each flip, _snap_origin is updated to the new
        begin to ensure the step grid includes the current sweep's starting point.
        """
        self.flips += 1

        if self.flips >= 2 and self.setpoint > 0:
            self.step = (-1) * abs(self.step)
            self.end = (-1) * self.end
            self.begin = self.setpoint  # New sweep starts from current position
            self._snap_origin = self.begin
        elif self.flips >= 2 and self.setpoint < 0:
            self.step = abs(self.step)
            self.end = (-1) * self.end
            self.begin = self.setpoint  # New sweep starts from current position
            self._snap_origin = self.begin
        elif self.flips < 2:
            self.end = (-1) * self.end
            self.step = -1 * self.step
            self.begin = self.setpoint  # New sweep starts from current position
            self._snap_origin = self.begin
            self.setpoint -= self.step
            self.setpoint = self._snap_to_step(self.setpoint, self._snap_origin, self.step)

        # If backwards, go forwards, and vice versa
        if self.direction:
            self.direction = 0
        else:
            self.direction = 1

    def estimate_time(self, verbose=True):
        """Gate leakage sweeps are event-driven; report no deterministic estimate."""
        if verbose:
            self.print_main.emit(
                f"No estimated time remaining for {repr(self)} (non-deterministic sweep)."
            )
        return 0.0
