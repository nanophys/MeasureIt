from .sweep1d import Sweep1D

def safe_ramp(param, setpoint, rate = 0.01, plot_data = True):
    #Rate is by default 0.01 V/s
    sweep_args = {
    'bidirectional' : False,
    'plot_data' : plot_data,
    'save_data' : False,
    'inter_delay' : 0.05,
    'x_axis_time' : 0, #If x_axis_time = 1, then plots of each follow_param is shown as a function of time. If x_axis_time = 0, then plots are done as a function of sweep variable
    'plot_bin' : 1 #If you are doing a large number of points in your sweep, you can increase thise to an integer > 1 to only plot every so many points
    }
    
    #Example sweep here is voltage
    start = param()
    stop = setpoint #stop voltage
    
    if start != stop:
        N = int(abs(stop-start)/rate)
        dV = abs(start-stop)/N #Calculates the interval
        sweep = Sweep1D(param, start, stop, dV, **sweep_args) #Define the sweep (doesn't start it)
        sweep.start()
        return sweep
    else:
        print(f'Already at setpoint: {setpoint}')
        return None