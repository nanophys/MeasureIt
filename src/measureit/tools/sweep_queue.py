# sweep_queue.py
import importlib
import json
import logging
import time
import types
from collections.abc import Iterable
from functools import partial

import qcodes as qc
from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from qcodes import Station, initialise_or_create_database_at

from ..logging_utils import get_sweep_logger
from ..sweep.abstract_sweep import AbstractSweep, SweepState
from ..sweep.base_sweep import BaseSweep
from ..sweep.simul_sweep import SimulSweep
from ..sweep.sweep0d import Sweep0D
from ..sweep.sweep1d import Sweep1D
from .sweep_queue_gui_thread import QueueGuiWindow, SweepQueueGuiThread


class SweepQueue(AbstractSweep):
    """A queue manager meant for continuously running different sweeps.

    'newSweepSignal' is used to send the current sweep information to the BaseSweep
    parent each time that a new sweep is to begin. Data can be saved to different
    databases for each sweep using DatabaseEntry objects.

    Attributes:
    ---------
    inter_delay:
        The time (in seconds) taken between consecutive sweeps.
    future_actions:
        List of pending actions (sweeps, database entries, callables) in chronological order.
    past_actions:
        List storing finished actions in reverse chronological order (most recent first).
    current_action:
        The action currently running, if any.
    rts:
        Defaults to true when sweep is started.

    Methods:
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
    kill()
        Kills any running sweeps.
    resume()
        Resumes any paused sweeps.
    is_running()
        Flag to determine whether a sweep is currently running.
    begin_next()
        Begins the next sweep in the queue upon the completion of a sweep.
    """

    newSweepSignal = pyqtSignal(BaseSweep)

    def __init__(self, inter_delay=1, post_db_delay=1.0, debug=False, show_gui=True):
        """Initializes the queue.

        Parameters
        ---------
        inter_delay:
            The time (in seconds) taken between consecutive sweeps.
        post_db_delay:
            The time (in seconds) to wait after a DatabaseEntry before starting
            the next sweep. This ensures the database context is fully initialized.
            Default is 1.0 second.
        debug:
            If True, enables debug output for troubleshooting queue execution.
        show_gui:
            If True, displays a progress window that refreshes every 200 ms.
        """
        super().__init__()
        self.future_actions = []
        self.past_actions = []
        self.current_action = None
        self.inter_delay = inter_delay
        self.post_db_delay = post_db_delay
        self.debug = debug
        self.log = get_sweep_logger("queue")
        if self.debug:
            base_logger = get_sweep_logger()
            for handler in base_logger.handlers:
                handler.setLevel(logging.DEBUG)
        self.rts = True
        # Flag to prevent concurrent begin_next() calls
        self._processing = False
        self._pending_begin_next = False
        self._retry_scheduled = False
        self._monitor_thread = None
        self._monitor_interval_ms = 200
        self.show_gui = show_gui
        self._gui_window = None
        self._gui_thread = None
        self._gui_interval_ms = 200
        self._gui_internal_close = False

    def _exec_in_kernel(self, fn):
        """Schedule a callable to run on the Jupyter kernel thread (asyncio loop) if present.

        - In a notebook/JupyterLab, ipykernel runs an asyncio loop; we schedule via
          loop.call_soon_threadsafe so that print() and logging appear in the notebook output.
        - If no running loop is detected (e.g., plain Python), execute inline.
        - If the callable raises in the scheduled path, we print the traceback and DO NOT
          advance the queue; in the inline path, the exception propagates naturally.
        """
        try:
            import asyncio
            import traceback

            # Prefer running loop (kernel thread); this raises in non-kernel threads
            loop = asyncio.get_running_loop()

            def _runner():
                try:
                    fn()
                except Exception:
                    traceback.print_exc()
                    return
                self.begin_next()

            # Schedule onto the kernel loop from any thread
            loop.call_soon_threadsafe(_runner)
        except Exception:
            # Fallback: no running loop in this thread/environment; execute inline
            fn()
            self.begin_next()

    def _attach_queue_metadata_provider(self, sweep: BaseSweep):
        """Attach a metadata provider wrapper so datasets record they were launched by SweepQueue.

        The wrapper delegates to the sweep's current provider (if any) and injects
        attributes['launched_by'] = 'SweepQueue' into the exported JSON.
        """
        try:
            # Resolve the current provider before wrapping
            provider_fn = getattr(sweep, "get_metadata_provider", None)
            base_provider = (
                provider_fn()
                if callable(provider_fn)
                else getattr(sweep, "metadata_provider", None)
            )
            if base_provider is None:
                base_provider = sweep

            class _QueueMetaProvider:
                def __init__(self, inner):
                    self._inner = inner

                def export_json(self, fn=None):
                    meta = self._inner.export_json(fn=None)
                    try:
                        attrs = meta.setdefault("attributes", {})
                        if isinstance(attrs, dict):
                            attrs["launched_by"] = "SweepQueue"
                    except Exception:
                        pass
                    return meta

            sweep.metadata_provider = _QueueMetaProvider(base_provider)
        except Exception:
            # Non-fatal; do not block the queue on metadata decoration issues
            pass

    def __iter__(self):
        """Makes sweep_queue objects iterable."""
        return iter(self.future_actions)

    @classmethod
    def init_from_json(cls, fn, station=Station()):
        """Loads previously saved sweep information.

        Sends the sweep attributes to the import_json module.

        Parameters
        ---------
        fn:
            Filename path where sweep information is stored.
        station:
            Initializes a QCoDeS station.

        Returns:
        ---------
        Located data is sent to import_json method.
        """
        with open(fn) as json_file:
            data = json.load(json_file)
            return SweepQueue.import_json(data, station)

    def export_json(self, fn=None):
        """Saves sweep queue attributes as JSON dictionary.

        Called to save sweep setup to avoid repetitive input of commonly
        used sweeps.

        Parameters
        ---------
        fn:
            Represents optional filename to be opened. A copy of the station
            information will be saved in this file.

        Returns:
        ---------
        Dictionary containing all current instruments, parameters, and sweep
        attributes.
        """
        json_dict = {}
        json_dict["module"] = self.__class__.__module__
        json_dict["class"] = self.__class__.__name__

        json_dict["inter_delay"] = self.inter_delay
        json_dict["queue"] = []
        for item in self.future_actions:
            json_dict["queue"].append(item.export_json())

        if fn is not None:
            with open(fn, "w") as outfile:
                json.dump(json_dict, outfile)

        return json_dict

    @classmethod
    def import_json(cls, json_dict, station=Station()):
        """Loads desired attributes into current SweepQueue."""
        sq = SweepQueue(json_dict["inter_delay"])

        for item_json in json_dict["queue"]:
            item_module = importlib.import_module(item_json["module"])
            item_class = getattr(item_module, item_json["class"])
            item = item_class.import_json(item_json, station)
            sq.append(item)

        return sq

    def _enqueue_action(self, action):
        """Prepare an action and append it to the future actions list."""
        if isinstance(action, BaseSweep) or isinstance(action, DatabaseEntry):
            self.future_actions.append(action)
        elif callable(action):
            self.future_actions.append(action)
        else:
            self.log.warning(
                "Invalid object queued: %s. Use append_handle() for callables.",
                action,
            )

    def _complete_current_action(self):
        """Move the running action into past_actions."""
        action = self.current_action
        if action is None:
            return
        if action in self.past_actions:
            self.past_actions.remove(action)
        self.past_actions.insert(0, action)
        if isinstance(action, BaseSweep):
            action.parent_sweep = None
            action.kill()
        self.current_action = None

    def append(self, *s):
        """Adds an arbitrary number of sweeps to the queue.

        Parameters
        ---------
        *s:
            A sweep or DatabaseEntry, or list of them, to be added to the queue.
        """
        for sweep in s:
            if isinstance(
                sweep,
                Iterable,
            ) and not isinstance(sweep, (BaseSweep, DatabaseEntry, types.FunctionType)):
                for action in sweep:
                    self._enqueue_action(action)
            else:
                self._enqueue_action(sweep)

    def __iadd__(self, item):
        """Overload += to replace append and append_handle.
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
        """Adds an arbitrary function call to the queue.

        Parameters
        ---------
        fn_handle:
            Any callable object to be added to the queue.
        *args:
            Arguments to be passed to the function
        **kwargs:
            Keyword arguments to be passed to the function
        """
        # Store a partial to be executed on the main thread by our executor slot
        self.future_actions.append(partial(fn_handle, *args, **kwargs))

    def delete(self, item):
        """Removes sweeps from the queue.

        Parameters
        ---------
        item: object to be removed from the queue
        """
        if isinstance(item, int):
            del self.future_actions[item]
        else:
            self.future_actions.remove(item)

    def replace(self, index, item):
        """Replaces sweep at the given index with a new sweep.

        Parameters
        ---------
        index:
            Position of sweep to be replaced (int).
        item:
            Sweep to be added to the queue at the indexed position.
        """
        self.future_actions[index] = item

    def move(self, item, distance):
        """Moves a sweep to a new position in the queue.

        Parameters
        ---------
        item:
            The name of the sweep to be moved.
        distance:
            The number of index positions for the sweep to be moved.

        Returns:
        ---------
        The new index position of the targeted sweep.
        """
        index = -1
        for i, action in enumerate(self.future_actions):
            if action is item:
                index = i

        new_pos = index + distance
        if index == -1:
            raise ValueError(f"Couldn't find {str(item)} in the queue.")
        elif new_pos < 0:
            new_pos = 0
        elif new_pos >= len(self.future_actions):
            new_pos = len(self.future_actions) - 1

        action = self.future_actions.pop(index)
        self.future_actions.insert(new_pos, action)
        return new_pos

    def _process_next_action(self, *, ramp_to_start=None, apply_inter_delay=True):
        """Activate the next pending action if available."""
        next_ramp = ramp_to_start
        while self.future_actions:
            if self.progress_state.state != SweepState.RUNNING:
                return
            previous = self.past_actions[0] if self.past_actions else None
            action = self.future_actions.pop(0)
            self.current_action = action
            if isinstance(action, BaseSweep):
                action.parent_sweep = self
                self.child_sweep = action

            if self.debug:
                self.log.debug("Processing: %s", type(action).__name__)

            # Ensure ramp_to_start is used only once (for the first candidate)
            if isinstance(action, BaseSweep):
                if isinstance(previous, DatabaseEntry):
                    self.log.info(
                        "Waiting %s s for database initialization...",
                        self.post_db_delay,
                    )
                    time.sleep(self.post_db_delay)

                self._attach_queue_metadata_provider(action)

                if isinstance(action, SimulSweep):
                    self.log.info(str(action))
                elif isinstance(action, Sweep1D):
                    self.log.info(
                        "Starting sweep of %s from %s (%s) to %s (%s)",
                        action.set_param.label,
                        action.begin,
                        action.set_param.unit,
                        action.end,
                        action.set_param.unit,
                    )
                elif isinstance(action, Sweep0D):
                    self.log.info(
                        "Starting 0D Sweep for %s seconds.",
                        action.max_time,
                    )
                else:
                    self.log.info("Starting %s", action.__class__.__name__)

                if apply_inter_delay:
                    time.sleep(self.inter_delay)

                self.newSweepSignal.emit(action)
                self._start_monitor()
                action_ramp = next_ramp
                next_ramp = None
                if action_ramp is None:
                    action.start()
                else:
                    action.start(ramp_to_start=action_ramp)
                break

            if isinstance(action, DatabaseEntry):
                self.log.info(str(action))
                time.sleep(0.5)
                action.start()
                self._complete_current_action()
                if self.progress_state.state != SweepState.RUNNING:
                    break
                continue

            if callable(action):
                self._exec_in_kernel(action)
                break

            self.log.error(
                "Invalid action found in the queue! %s. Stopping execution of the queue.",
                action,
            )
            self._complete_current_action()
            if self.progress_state.state != SweepState.RUNNING:
                break

        if not self.future_actions and self.current_action is None:
            previous_state = self.progress_state.state
            self.mark_done()
            if previous_state != SweepState.DONE:
                self.update_progress()
            self.log.info("Finished all sweeps!")

    def start(self, rts=True):
        """Begins running the first sweep in the queue.

        Parameters
        ---------
        rts: Optional parameter controlling 'ramp_to_start' keyword of sweep
        """
        # Check that there is something in the queue to run
        if not self.future_actions:
            self.log.warning("No sweeps loaded!")
            return
        if self.current_action is not None:
            self.log.info("Sweep queue already running.")
            return

        run_start = super().start()
        if run_start is None:
            return
        self.log.info("Starting sweeps")
        self._start_monitor()
        self._ensure_gui()
        self._process_next_action(ramp_to_start=rts, apply_inter_delay=False)

    def kill(self, update_parent=True, update_child=True):
        """Kills any running sweeps."""
        self._stop_monitor()
        self._stop_gui()
        super().kill(update_parent, update_child)
        if self.current_action is None:
            self.log.info("No current action to kill.")

    def mark_done(self):
        self._stop_monitor()
        super().mark_done()
        if self._gui_window is not None:
            self._gui_window.refresh()

    @pyqtSlot()
    def begin_next(self):
        """Begins the next sweep in the queue upon the completion of a sweep.

        Connected to completed pyqtSignals in the sweeps.
        Refactored to eliminate recursion and race conditions.
        """
        # If a deferred retry is landing back here, clear the scheduled flag
        if self._retry_scheduled and not self._processing:
            self._retry_scheduled = False

        # Prevent concurrent executions of begin_next()
        if self._processing:
            if self.debug:
                self.log.debug(
                    "begin_next() called but already processing, scheduling retry"
                )
            self._pending_begin_next = True
            if not self._retry_scheduled:
                self._retry_scheduled = True
                QTimer.singleShot(0, self.begin_next)
            return
        self._processing = True
        self._pending_begin_next = False

        if self.debug:
            self.log.debug(
                "begin_next() called, queue length: %s", len(self.future_actions)
            )
            current = self.current_action
            self.log.debug(
                "current_action type: %s",
                type(current).__name__ if current else "None",
            )

        try:
            current_action = self.current_action
            if isinstance(current_action, BaseSweep):
                if isinstance(current_action, SimulSweep):
                    self.log.info("Finished %s", str(current_action))
                elif isinstance(current_action, Sweep1D):
                    self.log.info(
                        "Finished sweep of %s from %s (%s) to %s (%s)",
                        current_action.set_param.label,
                        current_action.begin,
                        current_action.set_param.unit,
                        current_action.end,
                        current_action.set_param.unit,
                    )
                elif isinstance(current_action, Sweep0D):
                    self.log.info(
                        "Finished 0D Sweep of %s seconds.",
                        current_action.max_time,
                    )
                else:
                    self.log.info("Finished %s", current_action.__class__.__name__)
                self._complete_current_action()
            elif current_action is not None:
                # Non-sweep actions complete immediately once we're here
                self._complete_current_action()

            self._process_next_action(apply_inter_delay=True)

        finally:
            self._processing = False
            # If additional completion requests arrived during processing but
            # no retry is queued (e.g., caller invoked begin_next manually),
            # schedule one now so the queue keeps draining.
            if self._pending_begin_next and not self._retry_scheduled:
                self._retry_scheduled = True
                QTimer.singleShot(0, self.begin_next)

    def _start_monitor(self):
        if self._monitor_thread is not None:
            return
        self._monitor_thread = _SweepQueueMonitor(
            self, interval_ms=self._monitor_interval_ms
        )
        self._monitor_thread.tick.connect(self._on_monitor_tick)
        self._monitor_thread.start()

    def _stop_monitor(self):
        if self._monitor_thread is None:
            return
        try:
            self._monitor_thread.tick.disconnect(self._on_monitor_tick)
        except Exception:
            pass
        self._monitor_thread.stop()
        self._monitor_thread.wait(500)
        self._monitor_thread = None

    @pyqtSlot()
    def _on_monitor_tick(self):
        if not self.show_gui and (
            self._gui_window is not None or self._gui_thread is not None
        ):
            self._stop_gui()
        if self.show_gui:
            self._ensure_gui()
        if self.progress_state.state not in (SweepState.RUNNING, SweepState.RAMPING):
            return

        current = self.current_action
        if isinstance(current, BaseSweep):
            state = current.progress_state.state
            if state in (SweepState.DONE, SweepState.KILLED) and not self._processing:
                self.begin_next()

        self.update_progress()

    def _ensure_gui(self):
        if not self.show_gui:
            return
        if self._gui_window is None:
            self._gui_window = QueueGuiWindow(self, on_close=self._on_gui_closed)
            self._gui_window.show()
        if self._gui_thread is None:
            self._gui_thread = SweepQueueGuiThread(
                interval_ms=self._gui_interval_ms, parent=self
            )
            self._gui_thread.tick.connect(self._gui_window.refresh)
            self._gui_thread.start()

    def _detach_gui(self):
        thread = self._gui_thread
        window = self._gui_window
        if thread is not None:
            try:
                if window is not None:
                    thread.tick.disconnect(window.refresh)
            except Exception:
                pass
            thread.stop()
            thread.wait(500)
        self._gui_thread = None
        self._gui_window = None

    def _stop_gui(self):
        if self._gui_window is not None:
            self._gui_internal_close = True
            try:
                self._gui_window.close()
                self._gui_window.deleteLater()
            finally:
                self._gui_internal_close = False
        self._detach_gui()

    def _on_gui_closed(self):
        if self._gui_internal_close:
            return
        self._detach_gui()
        self.show_gui = False

    def estimate_time(self, verbose=False):
        """Returns an estimate of the amount of time the sweep queue will take to complete.

        Parameters
        ----------
        verbose:
            Controls whether there will be a printout of the time estimate for the queue,
            in the form of hh:mm:ss (default False)

        Returns:
        -------
        Time estimate for the sweep, in seconds
        """
        remaining = 0.0
        current = self.current_action
        if isinstance(current, AbstractSweep):
            t = current.estimate_time(verbose=False)
            if t is None:
                return None
            remaining += t
        for s in self.future_actions:
            if isinstance(s, BaseSweep):
                t = s.estimate_time(verbose=False)
                if t is None:
                    return None
                remaining += t

        hours, minutes, seconds = self._split_hms(remaining)
        self.log.info(
            "Estimated time for the SweepQueue to run: %sh:%2.0fm:%2.0fs",
            hours,
            minutes,
            seconds,
        )

        return remaining


class DatabaseEntry(QObject):
    """Class for database saving configuration for use with SweepQueue

    Attributes:
    ---------
    db:
        String with path to database file (.db)
    exp:
        Experiment name for the save data
    samp:
        Sample name for the save data
    callback:
        Function handle for callback function after 'start' completes

    Methods:
    ---------
    start()
        Sets the target database to save with experiment name 'exp' and sample name 'samp'
    set_callback(func)
        Sets the callback function to 'func'
    """

    def __init__(self, db="", exp="", samp="", callback=None):
        """Parameters
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
        self.log = get_sweep_logger("database")

    def __str__(self):
        return (
            f"Database entry: {self.db} | Experiment: {self.exp} | Sample: {self.samp}"
        )

    def __repr__(self):
        return f"Save File: ({self.db}, {self.exp}, {self.samp})"

    @classmethod
    def init_from_json(cls, fn):
        with open(fn) as json_file:
            data = json.load(json_file)
            return DatabaseEntry.import_json(data)

    def export_json(self, fn=None):
        json_dict = {}
        json_dict["module"] = self.__class__.__module__
        json_dict["class"] = self.__class__.__name__

        json_dict["attributes"] = {}
        json_dict["attributes"]["database"] = self.db
        json_dict["attributes"]["experiment"] = self.exp
        json_dict["attributes"]["sample"] = self.samp

        if fn is not None:
            with open(fn, "w") as outfile:
                json.dump(json_dict, outfile)

        return json_dict

    @classmethod
    def import_json(cls, json_dict):
        db = json_dict["attributes"]["database"]
        exp = json_dict["attributes"]["experiment"]
        sample = json_dict["attributes"]["sample"]

        return DatabaseEntry(db, exp, sample)

    def start(self):
        """Sets the database to the values given at initialization, then calls the callback function.

        Includes retry logic with exponential backoff to handle database lock errors.
        """
        import sqlite3
        import time

        # Retry logic for database operations
        max_retries = 5
        base_delay = 0.5  # Start with 0.5 seconds

        for attempt in range(max_retries):
            try:
                initialise_or_create_database_at(self.db)
                qc.new_experiment(name=self.exp, sample_name=self.samp)
                # If successful, break out of retry loop
                break
            except (sqlite3.OperationalError, RuntimeError) as e:
                # Check if it's a database lock error
                if "database is locked" in str(
                    e
                ) or "Rolling back due to unhandled exception" in str(e):
                    if attempt < max_retries - 1:
                        # Calculate exponential backoff delay
                        delay = base_delay * (2**attempt)
                        self.log.warning(
                            "Database is locked. Retrying in %.1f seconds... (attempt %s/%s)",
                            delay,
                            attempt + 1,
                            max_retries,
                        )
                        time.sleep(delay)
                    else:
                        # Final attempt failed, re-raise the error
                        self.log.error(
                            "Failed to create experiment after %s attempts. Database may still be locked.",
                            max_retries,
                        )
                        raise
                else:
                    # Not a database lock error, re-raise immediately
                    raise

        if self.callback is not None and callable(self.callback):
            self.callback()

    def set_complete_func(self, func, *args, **kwargs):
        """Sets the callback function to the given function

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


class _SweepQueueMonitor(QThread):
    """Background thread that periodically updates queue progress and completion."""

    tick = pyqtSignal()

    def __init__(self, parent, interval_ms=200):
        super().__init__(parent)
        self._interval_ms = interval_ms
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        self._stop = False
        while not self._stop:
            self.tick.emit()
            self.msleep(self._interval_ms)
