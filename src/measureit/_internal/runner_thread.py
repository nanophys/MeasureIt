# runner_thread.py

import io
import json
import time
from contextlib import redirect_stderr, redirect_stdout

from PyQt5.QtCore import QThread, pyqtSignal

from ..sweep.progress import SweepState
from ..tools.util import ParameterException


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

    def __del__(self):
        """Standard destructor."""
        self.wait()

    def add_plotter(self, plotter):
        """Adds the PlotterThread object.

        Parameters
        ---------
        plotter:
            Desired Plotter Thread object, created by the parent sweep.
        """
        self.plotter = plotter
        self.send_data.connect(self.plotter.add_data)

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
        # Check database status
        if self.sweep.save_data is True:
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

        # print(f"called runner from thread: {QThread.currentThreadId()}")
        while True:
            t = time.monotonic()
            state = getattr(self.sweep.progressState, "state", None)

            data = None
            if state == SweepState.RUNNING:
                try:
                    data = self.sweep.update_values()
                except ParameterException:
                    self.sweep.pause()
                    continue
                self.sweep.update_progress()

                if (
                    self.plotter is not None
                    and self.sweep.plot_data is True
                ):
                    self.send_data.emit(data, self.sweep.direction)

            # Smart sleep: compensate for time spent executing update
            sleep_time = self.sweep.inter_delay - (time.monotonic() - t)

            if sleep_time > 0:
                time.sleep(sleep_time)

            # Refresh state after possible updates
            state = getattr(self.sweep.progressState, "state", None)
            if state in (SweepState.DONE, SweepState.KILLED):
                if self.sweep.save_data is True and self.datasaver is not None:
                    self.datasaver.flush_data_to_database()
                if state == SweepState.KILLED:
                    break
                # Allow DONE sweeps to exit after flushing
                break

        self.exit_datasaver()

    def exit_datasaver(self):
        if self.datasaver is not None:
            if self.sweep.save_data is True:
                self.datasaver.flush_data_to_database()

            self.runner.__exit__(None, None, None)
            self.datasaver = None
