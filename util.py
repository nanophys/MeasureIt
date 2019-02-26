# util.py
# Utility function file

import re
import time

def _value_parser(value):
    """
    Parses user input for a float and a unit prefix character. Returns a float
    and a single char
    """
    value = str(value).strip()
    
    if value[0] == '.':
        value = '0' + value
    # regex testing stripped value as valid factor string
    # must be exactly a number followed by (space optional) single valid factor char 
    # f = femto p = pico u = micro m = milli k = kilo M = Mega G = Giga
    regex = re.compile(r"^([-]?[\d]*.?[\d]+[\s]?)([fpnumkMG]?)$")
    
    parsedVal = regex.search(value)
    if not parsedVal:
        return -1
    
    return (float(parsedVal.groups(' ')[0]), parsedVal.groups(' ')[1])

def _autorange_srs(srs, max_changes=1):
    """
    Joe's code, unedited
    """
    def autorange_once():
        r = srs.R.get()
        sens = srs.sensitivity.get()
        if r > 0.9 * sens:
            return srs.increment_sensitivity()
        elif r < 0.1 * sens:
            return srs.decrement_sensitivity()
        return False
    sets = 0
    while autorange_once() and sets < max_changes:
        sets += 1
        time.sleep(10*srs.time_constant.get())