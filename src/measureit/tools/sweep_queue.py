# sweep_queue.py
from __future__ import annotations

import importlib
import json
import logging
import os
import time
import types
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial
from numbers import Integral
from pathlib import Path
from typing import Optional

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
from ..sweep.progress import SweepState
from ..sweep.simul_sweep import SimulSweep
from ..sweep.sweep0d import Sweep0D
from ..sweep.sweep1d import Sweep1D


@dataclass
class QueueError:
    """Structured error information for queue-level errors.

    Attributes
    ----------
    message : str
        The error message describing what went wrong.
    sweep_type : str
        The class name of the sweep that caused the error (e.g., "Sweep1D").
    exception_type : str, optional
        The type name of the exception that was raised, if available.
    """

    message: str
    sweep_type: str
    exception_type: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "message": self.message,
            "sweep_type": self.sweep_type,
            "exception_type": self.exception_type,
        }


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
        # Queue-level error state (persists after sweep cleanup)
        self._last_error: Optional[QueueError] = None
        # Queue-level killed flag (persists after sweep cleanup)
        self._last_killed = False

    def _exec_in_kernel(self, fn):
        """Execute a callable synchronously.

        - Executes the callable
        - If the callable raises, prints the traceback and sets error state

        Note: The caller (begin_next while loop) will continue processing
        after this returns. We don't need to call begin_next() ourselves.
        """
        try:
            fn()
        except Exception as e:
            self.log.error("Callable raised: %s", e, exc_info=True)
            # Set error state so queue stops
            self._last_error = QueueError(
                message=f"Callable raised: {e}",
                sweep_type="callable",
                exception_type=type(e).__name__,
            )
        # Clear current_action so status() reports correctly
        self.current_action = None

    def _record_action_error(self, action_type: str, exc: Exception) -> None:
        """Record a queue-level error and log it."""
        self.log.error("%s error: %s", action_type, exc, exc_info=True)
        self._last_error = QueueError(
            message=f"{action_type} error: {exc}",
            sweep_type=action_type,
            exception_type=type(exc).__name__,
        )

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
                    # Mark as queued
                    l.progressState.is_queued = True
                    # Add it to the queue
                    self.queue.append(l)
            elif isinstance(sweep, BaseSweep):
                sweep.set_complete_func(self.begin_next)
                # Mark as queued
                sweep.progressState.is_queued = True
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
        item: object to be removed from the queue (BaseSweep, DatabaseEntry, or int index)
        """
        if isinstance(item, BaseSweep):
            self.queue.remove(item)
            # Clear is_queued only after successful removal
            item.progressState.is_queued = False
        elif isinstance(item, DatabaseEntry):
            self.queue.remove(item)
        elif isinstance(item, Integral):
            # Deleting by index - check if it's a sweep to clear is_queued
            removed = self.queue[item]
            del self.queue[item]
            # Clear is_queued only after successful removal
            if isinstance(removed, BaseSweep):
                removed.progressState.is_queued = False
        else:
            raise TypeError(f"delete() expects BaseSweep, DatabaseEntry, or integer index, got {type(item).__name__}")

    def replace(self, index, item):
        """Replaces sweep at the given index with a new sweep.

        Parameters
        ---------
        index:
            Position of sweep to be replaced (int).
        item:
            Sweep to be added to the queue at the indexed position.
        """
        # Get the old item before replacing
        old_item = self.queue[index]

        temp = deque([])

        for i in range(len(self.queue)):
            if i == index:
                temp.append(item)
            else:
                temp.append(self.queue[i])

        del self.queue[index]
        self.queue = temp

        # Clear is_queued on the removed item
        if isinstance(old_item, BaseSweep):
            old_item.progressState.is_queued = False

        # Set is_queued on the new item and register completion callback
        if isinstance(item, BaseSweep):
            item.set_complete_func(self.begin_next)
            item.progressState.is_queued = True

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
        # Clear kill flag once new work begins
        self._last_killed = False
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
            try:
                self.current_sweep.start(ramp_to_start=rts)
                # Clear previous error only after sweep actually starts
                # (preserves error info until new sweep is running)
                self._last_error = None
            except Exception as e:
                # If start() raises, record the error and clean up
                self.log.error("Failed to start sweep: %s", e)
                self._last_error = QueueError(
                    message=str(e),
                    sweep_type=self.current_sweep.__class__.__name__,
                    exception_type=type(e).__name__,
                )
                self.current_sweep.progressState.is_queued = False
                self.current_sweep = None
                self.current_action = None
        elif isinstance(self.current_action, DatabaseEntry):
            # DatabaseEntry changes the database and continues to next item
            try:
                self.current_action.start()
            except Exception as e:
                self._record_action_error("DatabaseEntry", e)
                self.current_action = None
                return
            # Continue with the next item in the queue
            self.begin_next()
        elif callable(self.current_action):
            # Execute callable synchronously, then continue to next item
            self._exec_in_kernel(self.current_action)
            # Continue with the next item in the queue (unless error occurred)
            if self._last_error is None:
                self.begin_next()
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
        """Kills the current sweep. Use kill_all() to also clear the queue."""
        if self.current_sweep is not None:
            self._last_killed = True
            # Clear current_sweep AND current_action before kill() to prevent
            # begin_next() from processing if kill() emits completion synchronously
            sweep_to_kill = self.current_sweep
            self.current_sweep = None
            self.current_action = None  # Prevent begin_next() from processing
            sweep_to_kill.progressState.is_queued = False
            sweep_to_kill.kill()
        else:
            self.log.info("No current sweep, nothing to kill!")

    def kill_all(self):
        """Kills the current sweep and clears all remaining sweeps from the queue.

        Also clears any error state, fully resetting the queue.
        Note: If a DatabaseEntry or callable is currently executing, it cannot be
        interrupted, but the queue will not continue after it completes.
        """
        had_work = (
            self.current_sweep is not None
            or self.current_action is not None
            or len(self.queue) > 0
        )
        # Save reference to sweep before clearing state
        sweep_to_kill = self.current_sweep

        # Clear all state BEFORE calling kill() to prevent race condition
        # if kill() emits completion synchronously
        self.current_sweep = None
        self.current_action = None

        # Clear is_queued for all remaining sweeps in the queue
        for item in self.queue:
            if isinstance(item, BaseSweep):
                item.progressState.is_queued = False
        self.queue.clear()

        # Clear error state for full reset
        self._last_error = None
        # Mark queue as killed if there was work to stop
        self._last_killed = had_work

        # Now safe to kill - even if completion fires, queue is empty
        if sweep_to_kill is not None:
            sweep_to_kill.progressState.is_queued = False
            sweep_to_kill.kill()

    def state(self):
        """Get the state of the currently running sweep.

        Returns
        -------
        SweepState or None
            The state of the current sweep, or None if no sweep is running.
            For a more comprehensive status that accounts for pending queue
            items, use the status() method instead.
        """
        if self.current_sweep is not None:
            return self.current_sweep.progressState.state
        return None

    def status(self):
        """Get comprehensive status of the sweep queue.

        Returns a dictionary with:
        - effective_state: Overall queue state accounting for pending items
          ("idle", "pending", "running", "paused", "killed", "error", "stopped")
        - current_sweep_state: State name of the currently executing sweep (or None)
        - queue_length: Number of items waiting in the queue
        - current_sweep_type: Class name of current sweep (or None)
        - current_action_type: Type of current non-sweep action (or None).
          Returns class name for DatabaseEntry, or "callable" for function/lambda.
          This tracks DatabaseEntry or callable execution.
        - last_error: Structured error info if queue stopped due to error (or None).
          Contains: message, sweep_type, exception_type (if available).

        The effective_state handles race conditions between sweep completion
        and the next sweep starting:
        - "idle": No current action, queue is empty, no error
        - "pending": Queue has items waiting, or an action is assigned but not running
        - "running": Current sweep is actively running/ramping, or a DatabaseEntry/callable
          is executing
        - "paused": Current sweep is paused
        - "killed": Queue stopped due to a kill() or kill_all() call. Call start() to resume.
        - "error": Current sweep is in error state (actively erroring)
        - "stopped": Queue stopped due to a previous error (check last_error for details).
                     Call clear_error() and start() to resume.

        Returns
        -------
        dict
            Status dictionary with effective_state, current_sweep_state,
            queue_length, current_sweep_type, current_action_type, and last_error.
            All values are JSON-serializable (enums converted to strings, QueueError to dict).
        """
        queue_length = len(self.queue)
        current_sweep_state = None
        current_sweep_type = None
        current_action_type = None

        # Track current action type for non-sweep actions (DatabaseEntry, callable)
        if self.current_action is not None and not isinstance(self.current_action, BaseSweep):
            if callable(self.current_action):
                current_action_type = "callable"
            else:
                current_action_type = self.current_action.__class__.__name__

        # Only BaseSweep has progressState; current_sweep should always be BaseSweep
        # but we guard defensively in case of future changes
        if self.current_sweep is not None and isinstance(self.current_sweep, BaseSweep):
            current_sweep_state = self.current_sweep.progressState.state
            current_sweep_type = self.current_sweep.__class__.__name__

        # Determine effective state
        if current_sweep_state is None:
            # No current sweep - check for non-sweep action or persisted error
            if current_action_type is not None:
                # DatabaseEntry or callable is executing
                effective_state = "running"
            elif self._last_error is not None:
                effective_state = "stopped"
            elif self._last_killed:
                effective_state = "killed"
            elif queue_length > 0:
                effective_state = "pending"
            else:
                effective_state = "idle"
        elif current_sweep_state == SweepState.ERROR:
            effective_state = "error"
        elif current_sweep_state == SweepState.KILLED:
            effective_state = "killed"
        elif current_sweep_state == SweepState.PAUSED:
            effective_state = "paused"
        elif current_sweep_state in (SweepState.RUNNING, SweepState.RAMPING):
            effective_state = "running"
        elif current_sweep_state == SweepState.READY:
            # Sweep assigned but not yet started
            effective_state = "pending"
        elif current_sweep_state == SweepState.DONE:
            # Sweep just finished (transient state before cleanup)
            if queue_length > 0:
                effective_state = "pending"
            else:
                effective_state = "idle"
        else:
            # Unexpected states with a current_sweep still set
            if queue_length > 0:
                effective_state = "pending"
            else:
                effective_state = "idle"

        # Provide error details even while a sweep is actively in ERROR
        if self._last_error is not None:
            last_error_payload = self._last_error.to_dict()
        elif current_sweep_state == SweepState.ERROR and self.current_sweep is not None:
            error_msg = getattr(self.current_sweep.progressState, "error_message", None)
            last_error_payload = QueueError(
                message=error_msg or "Unknown error",
                sweep_type=self.current_sweep.__class__.__name__,
                exception_type=None,
            ).to_dict()
        else:
            last_error_payload = None

        return {
            "effective_state": effective_state,
            # Return state name as string for JSON serialization
            "current_sweep_state": current_sweep_state.name if current_sweep_state else None,
            "queue_length": queue_length,
            "current_sweep_type": current_sweep_type,
            "current_action_type": current_action_type,
            # Convert QueueError to dict for JSON serialization
            "last_error": last_error_payload,
        }

    def clear_error(self):
        """Clear the queue's error state and any current sweep error.

        After a sweep error stops the queue, call this method to clear the error
        before calling start() to resume processing remaining items in the queue.

        This clears both:
        - The queue-level error flag (_last_error)
        - The current sweep's error state (if still set), resetting it to READY

        After calling this method, status() will report "idle" or "pending"
        (depending on queue contents) instead of "error" or "stopped".
        """
        self._last_error = None
        # Also clear current sweep's error state if it's still in ERROR
        if (self.current_sweep is not None and
                isinstance(self.current_sweep, BaseSweep) and
                self.current_sweep.progressState.state == SweepState.ERROR):
            self.current_sweep.clear_error()

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

        # Guard: if queue is in error or killed state, don't process further
        # This prevents re-entrancy from draining the queue after a stop
        if self._last_error is not None or self._last_killed:
            if self.debug:
                state = "error" if self._last_error is not None else "killed"
                self.log.debug("Queue in %s state, not processing further", state)
            self._processing = False
            return

        if self.debug:
            self.log.debug("begin_next() called, queue length: %s", len(self.queue))
            self.log.debug(
                "current_action type: %s",
                type(self.current_action).__name__ if self.current_action else "None",
            )

        try:
            # Guard: if current_action was cleared (e.g., by kill()), skip processing
            # This can happen if kill() triggers a completion signal synchronously
            if self.current_action is None:
                if self.debug:
                    self.log.debug("current_action is None, skipping to queue processing")
                # Fall through to process queue items below
                pass
            # Handle completion messages for the previous action if it was a sweep
            elif isinstance(self.current_action, BaseSweep):
                # Check if sweep ended with an error
                sweep_state = getattr(
                    self.current_action.progressState, "state", None
                )
                if sweep_state == SweepState.ERROR:
                    # Use fallback if error_message is None or missing
                    error_msg = getattr(
                        self.current_action.progressState, "error_message", None
                    ) or "Unknown error"
                    sweep_type = self.current_action.__class__.__name__
                    self.log.error(
                        "Sweep %s ended with error: %s",
                        sweep_type,
                        error_msg,
                    )
                    # Persist structured error at queue level (survives sweep cleanup)
                    # Note: exception_type is only available when we catch the actual
                    # exception (e.g., in start()). Here we only have the error message.
                    self._last_error = QueueError(
                        message=error_msg,
                        sweep_type=sweep_type,
                        exception_type=None,
                    )
                    # Clean up and stop the queue on error
                    # Guard against None in case of double completion signal
                    if self.current_sweep is not None:
                        self.current_sweep.progressState.is_queued = False
                        self.current_sweep.kill()
                        self.current_sweep = None
                    # Clear current_action to prevent re-processing on retry
                    self.current_action = None
                    self.log.error("Stopping queue due to sweep error.")
                    return  # Stop processing the queue

                # Log completion messages using current_action (which is the sweep)
                # Note: current_sweep may be None if kill() was called, so use current_action
                sweep = self.current_action
                if isinstance(sweep, SimulSweep):
                    self.log.info("Finished %s", str(sweep))
                elif isinstance(sweep, Sweep1D):
                    self.log.info(
                        "Finished sweep of %s from %s (%s) to %s (%s)",
                        sweep.set_param.label,
                        sweep.begin,
                        sweep.set_param.unit,
                        sweep.end,
                        sweep.set_param.unit,
                    )
                elif isinstance(sweep, Sweep0D):
                    self.log.info(
                        "Finished 0D Sweep of %s seconds.",
                        sweep.max_time,
                    )
                else:
                    self.log.info("Finished %s", sweep.__class__.__name__)

                # Clean up the sweep
                sweep.progressState.is_queued = False
                sweep.kill()
                self.current_sweep = None
                self.current_action = None

            else:
                # Handle completion of callable or DatabaseEntry
                # Just clear current_action so status() reports correctly
                if self.debug:
                    self.log.debug(
                        "Finished callable/DatabaseEntry: %s",
                        type(self.current_action).__name__
                        if self.current_action else "None",
                    )
                self.current_action = None

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
                    try:
                        self.current_sweep.start()
                        # Clear previous error on successful start
                        self._last_error = None
                    except Exception as e:
                        # If start() raises, record the error and clean up
                        self.log.error("Failed to start sweep: %s", e)
                        self._last_error = QueueError(
                            message=str(e),
                            sweep_type=self.current_sweep.__class__.__name__,
                            exception_type=type(e).__name__,
                        )
                        self.current_sweep.progressState.is_queued = False
                        self.current_sweep = None
                        self.current_action = None
                        break  # Exit loop - queue is stopped due to error
                    break  # Exit loop - sweep will call begin_next when done

                elif isinstance(self.current_action, DatabaseEntry):
                    # Process DatabaseEntry synchronously
                    self.log.info(str(self.current_action))
                    time.sleep(0.5)  # Small delay before database operation
                    try:
                        self.current_action.start()
                    except Exception as e:
                        self._record_action_error("DatabaseEntry", e)
                        self.current_action = None
                        break  # Exit loop - queue stopped due to error
                    # Continue loop to process next item immediately

                elif callable(self.current_action):
                    # Execute callable synchronously
                    self._exec_in_kernel(self.current_action)
                    # Check if callable raised an error
                    if self._last_error is not None:
                        break  # Exit loop - queue stopped due to error
                    # Continue loop to process next item immediately

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
