# sweep0d.py

from src.base_sweep import BaseSweep

class Sweep0D(BaseSweep):
    """
    Class for the following/live plotting, i.e. "0-D sweep" class. As of now, is just an extension of
    BaseSweep, but has been separated for future convenience.
    """
    def __init__(self, runner = None, plotter = None, *args, **kwargs):
        """
        Initialization class. Simply calls the BaseSweep initialization, and saves a few extra variables.
        
        Arguments (distinct from BaseSweep):
            runner - RunnerThread object, if prepared ahead of time, i.e. if a GUI is creating these first.
            plotter - PlotterThread object, passed if a GUI has plots it wants the thread to use instead
                      of creating it's own automatically.
        """
        super().__init__(None, *args, **kwargs)
        
        self.runner = runner
        self.plotter = plotter
        # Direction variable, not used here, but kept to maintain consistency with Sweep1D.
        self.direction = 0
        
        
    def flip_direction(self):
        """
        Define the function so that when called, it will not throw an error.
        """
        print("Can't flip the direction, as we are not sweeping a parameter.")
        return