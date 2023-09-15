import numpy as np
import matplotlib as mpl

def track_setpoint(sweep, lines, setpoint, steps = 100):
    if isinstance(lines, list):
        fwd_line = lines[0]
        bkw_line = lines[1]
    else:
        fwd_line = lines
        
    def find_point(line):
        min_diff = float("inf")
        best_x = 0
        best_y = 0
        x_data, y_data = line.get_data()
        
        for i,y in enumerate(y_data):
            if abs(y-setpoint)<min_diff:
                min_diff = abs(y-setpoint)
                best_x = x_data[i]
                best_y = y
        return (best_x, best_y)
    
    fwd_peak = find_point(fwd_line)
    bkw_peak = find_point(bkw_line)
    
    avg_peak_pos = (fwd_peak[0]+bkw_peak[0])/2
    
    adjust_endpoints(sweep, steps, avg_peak_pos)

      
def track_peak(sweep, lines, steps = 100):
    fwd_line = lines[0]
    bkw_line = lines[1]
    
    def get_peak(line):
        max_y = float("-inf")
        max_x = 0
        x_data, y_data = line.get_data()
        
        for i,y in enumerate(y_data):
            if y > max_y:
                max_y = y
                max_x = x_data[i]
        return (max_x, max_y)
            
    fwd_peak = get_peak(fwd_line)
    bkw_peak = get_peak(bkw_line)
    
    avg_peak_pos = (fwd_peak[0]+bkw_peak[0])/2
    
    adjust_endpoints(sweep, steps, avg_peak_pos)
    
    
def track_jump(sweep, lines, pos_jump=True, steps=100):
    fwd_line = lines[0]
    bkw_line = lines[1]
    
    d_fwd_line = mpl.lines.Line2D(fwd_line.get_xdata(), np.gradient(fwd_line.get_ydata()))
    d_bkw_line = mpl.lines.Line2D(bkw_line.get_xdata(), np.gradient(bkw_line.get_ydata()))
    
    def get_peak(line):
        if pos_jump:
            best_y = float("-inf")
        else:
            best_y = float("inf")
        best_x = 0
        x_data, y_data = line.get_data()
        
        for i,y in enumerate(y_data):
            if pos_jump and y > best_y:
                best_y = y
                best_x = x_data[i]
            elif not pos_jump and y < best_y:
                best_y = y
                best_x = x_data[i]
        return (best_x, best_y)
    
    d_fwd_peak = get_peak(d_fwd_line)
    d_bkw_peak = get_peak(d_bkw_line)
    
    avg_peak_pos = (d_fwd_peak[0]+d_bkw_peak[0])/2
    
    adjust_endpoints(sweep, steps, avg_peak_pos)
    
    
def adjust_endpoints(sweep, steps, avg_peak_pos):
    new_begin = avg_peak_pos - (steps/2*sweep.step)
    new_end = new_begin + sweep.step*steps 
    
    if sweep.begin < sweep.end:
        if new_begin > sweep.begin:
            sweep.begin = new_begin
        if new_end < sweep.end:
            sweep.end = new_end
    else:
        if new_begin < sweep.begin:
            sweep.begin = new_begin
        if new_end > sweep.end:
            sweep.end = new_end