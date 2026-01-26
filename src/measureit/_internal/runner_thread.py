# runner_thread.py

import io
import json
import logging
import time
import traceback
import weakref
from contextlib import redirect_stderr, redirect_stdout

from PyQt5.QtCore import QThread, pyqtSignal

from ..sweep.progress import SweepState
from ..tools.util import ParameterException

logger = logging.getLogger(__name__)


class RunnerThread(QThread):
    """Thread created to manage sweep data for saving and plotting.

    The sweeping object, Runner Thread, and Plotter Thread operate
    independently to improve efficiency. The Runner Thread gathers the
    data from the sweep, saves it to a database if desired, and passes
    it to a Plotter thread for live-plotting.

    Attributes:
    ---------
    sweep:
        Defines the specific parent sweep (Sweep1D, Sweep2D, etc.).
    plotter:
        Enables a connection to a Plotter Thread.
    datasaver:
        Context manager to easily write data to a dataset.
    db_set:
        Monitors whether or not a database has been assigned.
    runner:
        Runs measurement through QCoDeS.

    Methods:
    ---------
    __del__()
        A standard destructor.
    add_plotter(plotter)
        Connects to desired Plotter Thread to forward data for plotting.
    _set_parent(sweep)
        Sets the type of parent sweep if the runner is created independently.
    run()
        Iterates the sweep and sends data to the plotter.
    """

    # Track live RunnerThreads so test teardown can stop any stragglers
    _instances = weakref.WeakSet()

    get_dataset = pyqtSignal(dict)
    send_data = pyqtSignal(object, int)

    def __init__(self, sweep):
        """Initializes the runner.

        Takes in the parent sweep object, initializes the
        plotter object, and calls the QThread initialization.

        Parameters
        ---------
        sweep:
            Defines the specific parent sweep (Sweep1D, Sweep2D, etc.).
        plotter:
            Enables a connection to a Plotter Thread.
        datasaver:
            Context manager to easily write data to a dataset.
        db_set:
            Monitors whether or not a database has been assigned.
        runner:
            Runs measurement through QCoDeS.
        """
        QThread.__init__(self)

        self.sweep = sweep
        self.plotter = None
        self.datasaver = None
        self.dataset = None
        self.db_set = False
        self.runner = None
        self._instances.add(self)

    def __del__(self):
        """Standard destructor with timeout to prevent hanging."""
        # Use a short timeout to avoid hanging during garbage collection.
        # If thread doesn't stop, just let it be - Python will terminate anyway.
        try:
            if self.isRunning():
                self.quit()
                self.wait(500)  # 500ms timeout
        except Exception:
            pass

    @classmethod
    def cleanup_all(cls, timeout_ms: int = 1000) -> None:
        """Best-effort shutdown for any RunnerThread left alive."""
        for runner in list(cls._instances):
            try:
                if runner.isRunning():
                    runner.quit()
                    if not runner.wait(timeout_ms):
                        runner.terminate()
                        runner.wait(timeout_ms)
            except Exception:
                # Never raise during teardown; keep looping through others
                continue

    def add_plotter(self, plotter):
        """Adds the PlotterThread object.

        Parameters
        ---------
        plotter:
            Desired Plotter Thread object, created by the parent sweep.
        """
        self.plotter = plotter
        self.send_data.connect(self.plotter.add_data)

    def _run_step(self) -> bool:
        """Run a single sweep step; return False when the loop should exit."""
        t = time.monotonic()
        state = getattr(self.sweep.progressState, "state", None)

        if state == SweepState.RUNNING:
            data = self.sweep.update_values()
            self.sweep.update_progress()

            if self.plotter is not None and self.sweep.plot_data is True:
                self.send_data.emit(data, self.sweep.direction)

        # Smart sleep: compensate for time spent executing update
        sleep_time = self.sweep.inter_delay - (time.monotonic() - t)
        if sleep_time > 0:
            time.sleep(sleep_time)

        # Refresh state after possible updates
        state = getattr(self.sweep.progressState, "state", None)
        if state in (SweepState.DONE, SweepState.KILLED, SweepState.ERROR):
            if self.sweep.save_data is True and self.datasaver is not None:
                self.datasaver.flush_data_to_database()
            return False

        return True

    def _set_parent(self, sweep):
        """Sets a parent sweep if the Runner Thread is created independently.

        Parameters
        ---------
        sweep:
            Desired type of sweep for runner to gather data for.
        """
        self.sweep = sweep

    def run(self):
        """Iterates the sweep and sends data to the plotter for live plotting.

        NOTE: start() is called externally to start the thread, but run()
        defines the behavior of the thread.
        """
        # Check database status and initialize datasaver if save_data is True
        if self.sweep.save_data is True:
            try:
                capture = io.StringIO()
                with redirect_stdout(capture), redirect_stderr(capture):
                    self.runner = self.sweep.meas.run()
                    self.datasaver = self.runner.__enter__()
                self.dataset = self.datasaver.dataset
                banner = capture.getvalue().strip()
                if banner:
                    for line in banner.splitlines():
                        self.sweep.print_main.emit(line)
                # Attach MeasureIt sweep metadata once per dataset, using provider if set
                try:
                    provider = getattr(self.sweep, "get_metadata_provider", None)
                    provider = provider() if callable(provider) else None
                    if provider is None:
                        provider = (
                            getattr(self.sweep, "metadata_provider", None) or self.sweep
                        )
                    meta = provider.export_json(fn=None)
                    try:
                        # Preferred signature used historically in this project
                        self.dataset.add_metadata(
                            tag="measureit", metadata=json.dumps(meta)
                        )
                    except TypeError:
                        # Fallback for older qcodes versions
                        self.dataset.add_metadata("measureit", json.dumps(meta))
                except Exception:
                    # Never break the run on metadata errors
                    pass
                ds_dict = {}
                ds_dict["db"] = self.dataset.path_to_db
                ds_dict["run id"] = self.dataset.run_id
                ds_dict["exp name"] = self.dataset.exp_name
                ds_dict["sample name"] = self.dataset.sample_name
                self.get_dataset.emit(ds_dict)
            except Exception as e:
                # Database initialization failed - mark sweep as ERROR and exit
                # Common causes: no experiment created, database not initialized
                error_msg = f"Database initialization failed: {e}"

                # Log the full traceback for debugging
                logger.error(
                    "%s\n%s",
                    error_msg,
                    traceback.format_exc()
                )

                # Also log any captured stdout/stderr from the failed initialization
                # Log at warning level so it's visible under typical log levels
                captured_output = capture.getvalue().strip()
                if captured_output:
                    logger.warning("Captured output during failed DB init:\n%s", captured_output)

                self.sweep.mark_error(error_msg, _from_runner=True)
                self.sweep.emit_error_completed()
                return  # Exit run() early - no point entering the main loop

        # print(f"called runner from thread: {QThread.currentThreadId()}")
        try:
            while True:
                try:
                    should_continue = self._run_step()
                except ParameterException as e:
                    # safe_set already retried once and gave up - immediately transition to ERROR
                    # This prevents the sweep from continuing to the next setpoint with bad data
                    # Don't emit completed signal here - defer it until after loop exits
                    # to avoid blocking the main event loop
                    self.sweep.mark_error(
                        f"Parameter operation failed: {e}",
                        _from_runner=True,
                    )
                    break  # Exit loop immediately to avoid race conditions
                except (KeyboardInterrupt, SystemExit):
                    raise
                except Exception as e:
                    # Catch-all: ensure unexpected exceptions mark the sweep as ERROR
                    logger.error(
                        "Unhandled exception in runner thread: %s\n%s",
                        e,
                        traceback.format_exc(),
                    )
                    try:
                        self.sweep.mark_error(
                            f"Unhandled runner error: {e}",
                            _from_runner=True,
                        )
                    except Exception:
                        pass
                    break

                if not should_continue:
                    break
        finally:
            self.exit_datasaver()

        # Emit completed signal for ERROR state after loop exits
        # This is deferred to avoid blocking the main event loop during exception handling
        # Note: Use progressState.state (not local state var) since break may occur before state refresh
        if self.sweep.progressState.state == SweepState.ERROR:
            self.sweep.emit_error_completed()

    def exit_datasaver(self):
        if self.datasaver is not None:
            try:
                if self.sweep.save_data is True:
                    self.datasaver.flush_data_to_database()
            except Exception:
                logger.error("Failed to flush datasaver:\n%s", traceback.format_exc())
            try:
                if self.runner is not None:
                    self.runner.__exit__(None, None, None)
            except Exception:
                logger.error("Failed to close datasaver:\n%s", traceback.format_exc())
            self.datasaver = None
