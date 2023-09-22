# runner_thread.py

from PyQt5.QtCore import QThread, pyqtSignal
from .util import ParameterException
import time


class RunnerThread(QThread):
    """
    Thread created to manage sweep data for saving and plotting.
    
    The sweeping object, Runner Thread, and Plotter Thread operate
    independently to improve efficiency. The Runner Thread gathers the
    data from the sweep, saves it to a database if desired, and passes
    it to a Plotter thread for live-plotting.
    
    Attributes
    ---------
    sweep:
        Defines the specific parent sweep (Sweep1D, Sweep2D, etc.).
    plotter:
        Enables a connection to a Plotter Thread.
    datasaver:
        Context manager to easily write data to a dataset.
    db_set:
        Monitors whether or not a database has been assigned.
    kill_flag:
        Flag to immediately end the sweep.
    flush_flag:
        Flushes any remaining data to database if sweep is stopped.
    runner:
        Runs measurement through QCoDeS.
        
    Methods
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
    send_data = pyqtSignal(list, int)

    def __init__(self, sweep):
        """
        Initializes the runner.
        
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
        kill_flag:
            Flag to immediately end the sweep.
        flush_flag:
            Flushes any remaining data to database if sweep is stopped.
        runner:
            Runs measurement through QCoDeS.
        """
        
        QThread.__init__(self)

        self.sweep = sweep
        self.plotter = None
        self.datasaver = None
        self.dataset = None
        self.db_set = False
        self.kill_flag = False
        self.flush_flag = False
        self.runner = None

    def __del__(self):
        """ Standard destructor. """

        self.wait()

    def add_plotter(self, plotter):
        """
        Adds the PlotterThread object.
        
        Parameters
        ---------
        plotter: 
            Desired Plotter Thread object, created by the parent sweep.
        """
        
        self.plotter = plotter
        self.send_data.connect(self.plotter.add_data)

    def _set_parent(self, sweep):
        """
        Sets a parent sweep if the Runner Thread is created independently.
        
        Parameters
        ---------
        sweep: 
            Desired type of sweep for runner to gather data for.
        """
        
        self.sweep = sweep

    def run(self):
        """
        Iterates the sweep and sends data to the plotter for live plotting.
        
        NOTE: start() is called externally to start the thread, but run() 
        defines the behavior of the thread.
        """
        
        # Check database status
        if self.sweep.save_data is True:
            self.runner = self.sweep.meas.run()
            self.datasaver = self.runner.__enter__()
            self.dataset = self.datasaver.dataset
            ds_dict = {}
            ds_dict['db'] = self.dataset.path_to_db
            ds_dict['run id'] = self.dataset.run_id
            ds_dict['exp name'] = self.dataset.exp_name
            ds_dict['sample name'] = self.dataset.sample_name
            self.get_dataset.emit(ds_dict)

        # print(f"called runner from thread: {QThread.currentThreadId()}")
        # Check if we are still running
        while self.kill_flag is False:
            t = time.monotonic()
            # print(f'kill flag = {str(self.kill_flag)}, is_running={self.sweep.is_running}')

            if self.sweep.is_running is True:
                # Get the new data
                try:
                    data = self.sweep.update_values()
                except ParameterException as e:
                    self.sweep.stop()
                    continue

                # Check if we've hit the end- update_values will return None
                if data is None:
                    continue

                # Send it to the plotter if we are going
                # Note: we check again if running, because we won't know if we are
                # done until we try to step the parameter once more
                if self.plotter is not None and self.sweep.plot_data is True:
                    self.send_data.emit(data, self.sweep.direction)

            # Smart sleep, by checking if the whole process has taken longer than
            # our sleep time
            sleep_time = self.sweep.inter_delay - (time.monotonic() - t)

            if sleep_time > 0:
                time.sleep(sleep_time)

            if self.flush_flag is True and self.sweep.save_data is True:
                self.datasaver.flush_data_to_database()
                self.flush_flag = False
            # print('at end of kill flag loop')

        self.exit_datasaver()

    def exit_datasaver(self):
        if self.datasaver is not None:
            if self.sweep.save_data is True:
                self.datasaver.flush_data_to_database()

            self.runner.__exit__(None, None, None)
            self.datasaver = None


