# runner_thread.py

from PyQt5.QtCore import QThread
import time

class RunnerThread(QThread):
    """
    Class to separate to a new thread the communications with the instruments.
    """
    
    def __init__(self, sweep):
        """
        Initializes the object by taking in the parent sweep object, initializing the 
        plotter object, and calling the QThread initialization.
        
        Arguments:
            sweep - Object of type BaseSweep (or its children) that is controlling
                    this thread
        """
        self.sweep = sweep
        self.plotter = None
        self.datasaver = None
        self.db_set = False
        self.kill_flag = False
        self.flush_flag = False
        
        QThread.__init__(self)
        
        
    def __del__(self):
        """
        Standard destructor.
        """
        self.wait()
    
    
    def add_plotter(self, plotter):
        """
        Adds the PlotterThread object, so the Runner knows where to send the new
        data for plotting.
        
        Arguments:
            plotter - PlotterThread object, should be same plotter created by parent
                      sweep
        """
        self.plotter = plotter
        
        
    def _set_parent(self, sweep):
        """
        Function to tell the runner who the parent is, if created independently.
        
        Arguments:
            sweep - Object of type BaseSweep, that Runner will be taking data for
        """
        self.sweep = sweep
        
        
    def run(self):
        """
        Function that is called when new thread is created. NOTE: start() is called
        externally to start the thread, but run() defines the behavior of the thread.
        Iterates the sweep, then hands the data to the plotter for live plotting.
        """
        # Check database status
        if self.db_set == False and self.sweep.save_data == True:
            self.datasaver = self.sweep.meas.run().__enter__()
        
        #print(f"called runner from thread: {QThread.currentThreadId()}")
        # Check if we are still running
        while self.kill_flag is False:
            t = time.monotonic()
            
            if self.sweep.is_running is True:
                # Get the new data
                data = self.sweep.update_values()
                
                # Send it to the plotter if we are going
                # Note: we check again if running, because we won't know if we are
                # done until we try to step the parameter once more
                if self.sweep.is_running is True and self.plotter is not None and self.sweep.plot_data is True:
                    self.plotter.add_data_to_queue(data, self.sweep.direction)
                
            # Smart sleep, by checking if the whole process has taken longer than
            # our sleep time
            sleep_time = self.sweep.inter_delay - (time.monotonic() - t)
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            if self.flush_flag == True and self.sweep.save_data is True:
                self.datasaver.flush_data_to_database()
                self.flush_flag = False