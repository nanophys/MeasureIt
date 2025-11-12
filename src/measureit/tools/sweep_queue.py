# sweep_queue.py
import importlib
import json
import logging
import os
import time
import types
from collections import deque
from collections.abc import Iterable
from functools import partial
from pathlib import Path

import qcodes as qc
from qcodes import Station, initialise_or_create_database_at

_USE_FAKE_QT = os.environ.get("MEASUREIT_FAKE_QT", "").lower() in {"1", "true", "yes"}

if not _USE_FAKE_QT:
    from PyQt5.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot  # type: ignore
else:
    class _FakeSignalInstance:
        def __init__(self):
            self._slots = []

        def connect(self, slot):
            self._slots.append(slot)

        def disconnect(self, slot):
            try:
                self._slots.remove(slot)
            except ValueError:
                pass

        def emit(self, *args, **kwargs):
            for slot in list(self._slots):
                slot(*args, **kwargs)

    class _FakeSignalDescriptor:
        def __init__(self):
            self._attr_name = None

        def __set_name__(self, owner, name):
            self._attr_name = f"__fake_signal_{name}"

        def __get__(self, obj, owner):
            if obj is None:
                return self
            signal = obj.__dict__.get(self._attr_name)
            if signal is None:
                signal = _FakeSignalInstance()
                obj.__dict__[self._attr_name] = signal
            return signal

    class QObject:
        def __init__(self, parent=None):
            self._parent = parent

        def deleteLater(self):
            pass

    class QTimer:
        @staticmethod
        def singleShot(delay, callback):
            callback()

    def pyqtSignal(*args, **kwargs):
        return _FakeSignalDescriptor()

    def pyqtSlot(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

from ..config import get_path
from ..logging_utils import get_sweep_logger
from ..sweep.base_sweep import BaseSweep
from ..sweep.simul_sweep import SimulSweep
from ..sweep.sweep0d import Sweep0D
from ..sweep.sweep1d import Sweep1D


class SweepQueue(QObject):
    """A modifieded double-ended queue meant for continuously running different sweeps.

    'newSweepSignal' is used to send the current sweep information to the BaseSweep
    parent each time that a new sweep is to begin. Data can be saved to different
    databases for each sweep using DatabaseEntry objects.

    Attributes:
    ---------
    inter_delay:
        The time (in seconds) taken between consecutive sweeps.
    queue:
        Double-ended queue used to store sweeps in desired order.
    current_sweep:
        The most recent sweep pulled from the queue.
    current_action:
        The most recent action, sweep or callable, pulled from the queue.
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

    def __init__(self, inter_delay=1, post_db_delay=1.0, debug=False):
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
        """
        QObject.__init__(self)
        self.queue = deque([])
        # Pointer to the sweep currently running
        self.current_sweep = None
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
        # Track previous action to detect DatabaseEntry->Sweep transitions
        self.previous_action = None

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
        return iter(self.queue)

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
        for item in self.queue:
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

    def append(self, *s):
        """Adds an arbitrary number of sweeps to the queue.

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
                # DatabaseEntry doesn't need a complete_func since it executes synchronously
                self.queue.append(sweep)
            else:
                self.log.warning(
                    "Invalid object queued: %s. Use append_handle() for callables.",
                    sweep,
                )

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
        self.queue.append(partial(fn_handle, *args, **kwargs))

    def delete(self, item):
        """Removes sweeps from the queue.

        Parameters
        ---------
        item: object to be removed from the queue
        """
        if isinstance(item, BaseSweep) or isinstance(item, DatabaseEntry):
            self.queue.remove(item)
        else:
            del self.queue[item]

    def replace(self, index, item):
        """Replaces sweep at the given index with a new sweep.

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
        """Begins running the first sweep in the queue.

        Parameters
        ---------
        rts: Optional parameter controlling 'ramp_to_start' keyword of sweep
        """
        # Check that there is something in the queue to run
        if len(self.queue) == 0:
            self.log.warning("No sweeps loaded!")
            return

        self.log.info("Starting sweeps")
        self.current_action = self.queue.popleft()
        if isinstance(self.current_action, BaseSweep):
            self.current_sweep = self.current_action
            # Ensure metadata shows this sweep was launched by SweepQueue
            self._attach_queue_metadata_provider(self.current_sweep)
            if isinstance(self.current_sweep, Sweep1D):
                self.log.info(
                    "Starting sweep of %s from %s (%s) to %s (%s)",
                    self.current_sweep.set_param.label,
                    self.current_sweep.begin,
                    self.current_sweep.set_param.unit,
                    self.current_sweep.end,
                    self.current_sweep.set_param.unit,
                )
            elif isinstance(self.current_sweep, Sweep0D):
                self.log.info(
                    "Starting 0D Sweep for %s seconds.", self.current_sweep.max_time
                )
            self.newSweepSignal.emit(self.current_sweep)
            self.current_sweep.start(ramp_to_start=rts)
        elif isinstance(self.current_action, DatabaseEntry):
            # DatabaseEntry changes the database and continues to next item
            self.current_action.start()
            # Continue with the next item in the queue
            self.begin_next()
        elif callable(self.current_action):
            # Schedule onto the Jupyter kernel thread if available
            self._exec_in_kernel(self.current_action)
        else:
            self.log.error(
                "Invalid action found in the queue! %s. Stopping execution.",
                self.current_action,
            )

    def pause(self):
        """Pauses any running sweeps."""
        if self.current_sweep is not None:
            self.current_sweep.pause()
        else:
            self.log.info("No sweep currently running, nothing to pause")

    def stop(self):
        """Stop/pause the current sweep. Alias for pause() for backward compatibility.

        This method pauses the currently running sweep in the queue, allowing it
        to be resumed later. This matches the behavior from older versions of MeasureIt.
        """
        self.pause()

    def resume(self):
        """Resumes any paused sweeps."""
        if self.current_sweep is not None:
            self.current_sweep.resume()
        else:
            self.log.info("No current sweep, nothing to resume!")

    def kill(self):
        """Kills any running sweeps."""
        if self.current_sweep is not None:
            self.current_sweep.kill()
        else:
            self.log.info("No current sweep, nothing to resume!")

    def state(self):
        """Get the state of the currently running sweep."""
        if self.current_sweep is not None:
            return self.current_sweep.progressState.state
        else:
            self.log.info("Sweep queue is not currently running")

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
            self.log.debug("begin_next() called, queue length: %s", len(self.queue))
            self.log.debug(
                "current_action type: %s",
                type(self.current_action).__name__ if self.current_action else "None",
            )

        try:
            # Handle completion messages for the previous action if it was a sweep
            if isinstance(self.current_action, BaseSweep):
                if isinstance(self.current_action, SimulSweep):
                    self.log.info("Finished %s", str(self.current_action))
                elif isinstance(self.current_action, Sweep1D):
                    self.log.info(
                        "Finished sweep of %s from %s (%s) to %s (%s)",
                        self.current_sweep.set_param.label,
                        self.current_sweep.begin,
                        self.current_sweep.set_param.unit,
                        self.current_sweep.end,
                        self.current_sweep.set_param.unit,
                    )
                elif isinstance(self.current_action, Sweep0D):
                    self.log.info(
                        "Finished 0D Sweep of %s seconds.",
                        self.current_sweep.max_time,
                    )
                else:
                    self.log.info(
                        "Finished %s", self.current_action.__class__.__name__
                    )

                # Clean up the sweep
                self.current_sweep.kill()
                self.current_sweep = None

            # Process queue items in a loop (no recursion)
            while self.queue:
                # Store previous action for context tracking
                self.previous_action = self.current_action
                self.current_action = self.queue.popleft()

                if self.debug:
                    self.log.debug(
                        "Processing: %s",
                        type(self.current_action).__name__,
                    )

                if isinstance(self.current_action, BaseSweep):
                    self.current_sweep = self.current_action

                    # Apply post-database delay if previous was DatabaseEntry
                    if isinstance(self.previous_action, DatabaseEntry):
                        self.log.info(
                            "Waiting %s s for database initialization...",
                            self.post_db_delay,
                        )
                        time.sleep(self.post_db_delay)

                    # Ensure metadata shows this sweep was launched by SweepQueue
                    self._attach_queue_metadata_provider(self.current_sweep)

                    # Print start message for ALL sweep types
                    if isinstance(self.current_sweep, SimulSweep):
                        self.log.info(str(self.current_sweep))
                    elif isinstance(self.current_sweep, Sweep1D):
                        self.log.info(
                            "Starting sweep of %s from %s (%s) to %s (%s)",
                            self.current_sweep.set_param.label,
                            self.current_sweep.begin,
                            self.current_sweep.set_param.unit,
                            self.current_sweep.end,
                            self.current_sweep.set_param.unit,
                        )
                    elif isinstance(self.current_sweep, Sweep0D):
                        self.log.info(
                            "Starting 0D Sweep for %s seconds.",
                            self.current_sweep.max_time,
                        )
                    else:
                        self.log.info(
                            "Starting %s", self.current_sweep.__class__.__name__
                        )

                    time.sleep(self.inter_delay)
                    self.newSweepSignal.emit(self.current_sweep)
                    self.current_sweep.start()
                    break  # Exit loop - sweep will call begin_next when done

                elif isinstance(self.current_action, DatabaseEntry):
                    # Process DatabaseEntry synchronously
                    self.log.info(str(self.current_action))
                    time.sleep(0.5)  # Small delay before database operation
                    self.current_action.start()
                    # Continue loop to process next item immediately

                elif callable(self.current_action):
                    # Execute callable
                    self._exec_in_kernel(self.current_action)
                    break  # Exit loop - callable will call begin_next when done

                else:
                    self.log.error(
                        "Invalid action found in the queue! %s. Stopping execution of the queue.",
                        self.current_action,
                    )
                    # Continue loop to try next item

            # Check if we've finished everything
            if not self.queue and self.current_sweep is None:
                self.log.info("Finished all sweeps!")

        finally:
            self._processing = False
            # If additional completion requests arrived during processing but
            # no retry is queued (e.g., caller invoked begin_next manually),
            # schedule one now so the queue keeps draining.
            if self._pending_begin_next and not self._retry_scheduled:
                self._retry_scheduled = True
                QTimer.singleShot(0, self.begin_next)


    def estimate_time(self, verbose=False):
        """Returns an estimate of the amount of time the sweep queue will take to complete.

        Parameters
        ----------
        verbose:
            Controls whether there will be a printout of the time estimate for each sweep in the queue,
            in the form of hh:mm:ss (default False)

        Returns:
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

        self.log.info(
            "Estimated time for the SweepQueue to run: %sh:%2.0fm:%2.0fs",
            hours,
            minutes,
            seconds,
        )

        return t_est



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
        return f"Database entry: {self.db} | Experiment: {self.exp} | Sample: {self.samp}"

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
                if "database is locked" in str(e) or "Rolling back due to unhandled exception" in str(e):
                    if attempt < max_retries - 1:
                        # Calculate exponential backoff delay
                        delay = base_delay * (2 ** attempt)
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
