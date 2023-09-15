#Cryomagnetics Model 4G Superconducting Magnet Power Supply
#Created by Dacen Waters for Yankowitz Lab VTI
#Last updated June 1st, 2021

import logging
from qcodes import VisaInstrument
from qcodes import validators as vals
from time import sleep
import pyvisa

log = logging.getLogger(__name__)

DEFAULT_LIMITS = {
            'RANGE0' : 40., #A
            'RANGE1' : 80.,
            'RANGE2' : 96.5,
            'RANGE3' : 98.,
            'RANGE4' : 99.,
        }
DEFAULT_RATES = {
            'RANGE0' : 0.04, #A/s
            'RANGE1' : 0.02,
            'RANGE2' : 0.01,
            'RANGE3' : 0.001,
            'RANGE4' : 0.001,
        }
MAX_RATES = {
            'RANGE0' : 0.0468, #A/s
            'RANGE1' : 0.0234,
            'RANGE2' : 0.0117,
            'RANGE3' : 0.001,
            'RANGE4' : 0.001,
}

MAX_SUPPLY_CURRENT = 100 #A
FIELD_TO_CURRENT = 1246.7/1e4 #T/A

MIN_FIELD = -12.0 #T
MAX_FIELD = 12.0

class M4G(VisaInstrument):
    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, terminator='\r\n', **kwargs)
    
        self.add_parameter(name = 'iout',
                          unit = 'A',
                          get_cmd=self._get_iout,
                          docstring='Output current')
        
        self.add_parameter(name = 'vout',
                           unit='V',
                           get_cmd=self._get_vout,
                           docstring='Output voltage'
                          )
        self.add_parameter(name = 'units',
                           get_cmd = 'UNITS?',
                           set_cmd = 'UNITS {}',
                           docstring='Units',
                           vals = vals.Enum('A', 'kG', 'T')
                            )
        
        self.add_parameter(name = 'ulim',
                           get_cmd = self._get_ulim,
                           set_cmd = 'ULIM {}',
                           docstring='Upper Limit',
                           get_parser=float
                          )
        self.add_parameter(name = 'llim',
                           get_cmd = self._get_llim,
                           set_cmd = 'LLIM {}',
                           docstring='Lower Limit',
                           get_parser=float
                          )
        self.add_parameter(name = 'field',
                           get_cmd = self._get_field,
                           set_cmd = self._set_field,
                           unit='T',
                           docstring='Magnetic Field',
                           vals=vals.Numbers(MIN_FIELD, MAX_FIELD)
                          )

        self.add_parameter('range0_rate',
                           unit = 'A/s',
                           get_cmd='RATE? 0',
                           set_cmd=self._set_range0_rate,
                           get_parser=float,
                           docstring='Ramp rate for Range 0',
                           vals=vals.Numbers(0, MAX_SUPPLY_CURRENT)
                          )
        self.add_parameter('range1_rate',
                           unit = 'A/s',
                           get_cmd='RATE? 1',
                           set_cmd=self._set_range1_rate,
                           get_parser=float,
                           docstring='Ramp rate for Range 1',
                           vals=vals.Numbers(0, MAX_SUPPLY_CURRENT)
                          )
        self.add_parameter('range2_rate',
                           unit = 'A/s',
                           get_cmd='RATE? 2',
                           set_cmd=self._set_range2_rate,
                           get_parser=float,
                           docstring='Ramp rate for Range 2',
                           vals=vals.Numbers(0, MAX_SUPPLY_CURRENT)
                          )
        self.add_parameter('range3_rate',
                           unit = 'A/s',
                           get_cmd='RATE? 3',
                           set_cmd=self._set_range3_rate,
                           get_parser=float,
                           docstring='Ramp rate for Range 3',
                           vals=vals.Numbers(0, MAX_SUPPLY_CURRENT)
                          )
        self.add_parameter('range4_rate',
                           unit = 'A/s',
                           get_cmd='RATE? 4',
                           set_cmd=self._set_range4_rate,
                           get_parser=float,
                           docstring='Ramp rate for Range 4',
                           vals=vals.Numbers(0, MAX_SUPPLY_CURRENT)
                          )
        self.add_parameter('range0_limit',
                           unit = 'A',
                           get_cmd='RANGE? 0',
                           set_cmd=self._set_range0_limit,
                           get_parser=float,
                           docstring='Ramp limit for Range 0',
                           vals=vals.Numbers(0, MAX_SUPPLY_CURRENT)
                          )
        self.add_parameter('range1_limit',
                           unit = 'A',
                           get_cmd='RANGE? 1',
                           set_cmd=self._set_range1_limit,
                           get_parser=float,
                           docstring='Ramp limit for Range 1',
                           vals=vals.Numbers(0, MAX_SUPPLY_CURRENT)
                          )
        self.add_parameter('range2_limit',
                           unit = 'A',
                           get_cmd='RANGE? 2',
                           set_cmd=self._set_range2_limit,
                           get_parser=float,
                           docstring='Ramp limit for Range 2',
                           vals=vals.Numbers(0, MAX_SUPPLY_CURRENT)
                          )
        self.add_parameter('range3_limit',
                           unit = 'A',
                           get_cmd='RANGE? 3',
                           set_cmd=self._set_range3_limit,
                           get_parser=float,
                           docstring='Ramp limit for Range 3',
                           vals=vals.Numbers(0, MAX_SUPPLY_CURRENT)
                          )
        self.add_parameter('range4_limit',
                           unit = 'A',
                           get_cmd='RANGE? 4',
                           set_cmd=self._set_range4_limit,
                           get_parser=float,
                           docstring='Ramp limit for Range 4',
                           vals=vals.Numbers(0, MAX_SUPPLY_CURRENT)
                          )
        
    def _get_iout(self): #Output current in current units
        result = self.ask('IMAG?')
        units = self.units()
        if units == 'A':
            return float(result[:-1])
        else:
            return (float(result[:-2]))
    def _get_vout(self): #Output voltage in volts
        result = self.ask('VOUT?')
        return float(result[:-1])
    def _get_ulim(self): #Get upper limit in current units
        result = self.ask('ULIM?')
        units = self.units()
        if units == 'A':
            return float(result[:-1])
        else:
            return (float(result[:-2]))
    def _get_llim(self): #Get lower limit in current units
        result = self.ask('LLIM?')
        units = self.units()
        if units == 'A':
            return float(result[:-1])
        else:
            return (float(result[:-2]))
        
    def _get_field(self): #Returns the field in Tesla (regardless of current units)
        result = self.ask('IMAG?')
        units = self.units()
        
        for i in range(10): #Sometimes the magnet returns the IMAG? query for some reason. If this happens, wait one second and try asking again
            try: 
                float(result[:-2])
                break
            except:
                print('Communication error: returned value ' + result)
                sleep(1.0)
                result = self.ask('IMAG?')
                
            
        if units == 'A':
            return float(result[:-1])*FIELD_TO_CURRENT
        else:
            return (float(result[:-2]))/10
        
    def _set_field(self, field): #Sweeps to the input field value (field in T)
        self.setpoint(field)
        if field == 0:
            self.write('SWEEP ZERO')
        else:
            self.write('SWEEP UP')
        self.log.info('Sweeping field to {} T'.format(field))
#         sleep(0.05)
#         while self.field() != field:
#             sleep(0.05)
#         sleep(0.05)
            
    #Commands for setting the sweep rates
    #Each command checks that the corresponding limit does the maximum rate (error is raised if it does)
    def _set_range0_rate(self, rate):
        check_rate(self.range0_limit(), rate)
        self.write_raw('RATE 0 {}'.format(rate))
    def _set_range1_rate(self, rate):
        check_rate(self.range1_limit(), rate)
        self.write_raw('RATE 1 {}'.format(rate))
    def _set_range2_rate(self, rate):
        check_rate(self.range2_limit(), rate)
        self.write_raw('RATE 2 {}'.format(rate))
    def _set_range3_rate(self, rate):
        check_rate(self.range3_limit(), rate)
        self.write_raw('RATE 3 {}'.format(rate))
    def _set_range4_rate(self, rate):
        check_rate(self.range4_limit(), rate)
        self.write_raw('RATE 4 {}'.format(rate))
        
    #Commands for setting the current limits for each range
    #Each command raises an error if values don't corresponding to Rate i-1 > Rate i > Rate i+1 for each i
    def _set_range0_limit(self, limit):
        upper_limit = float(self.ask('RANGE? 1'))
        if limit < upper_limit:
            self.write_raw('RANGE 0 {}'.format(limit))
        else:
            raise ValueError('Range 0 limit must be lower than Range1 limit ({} A)'.format(upper_limit))
    def _set_range1_limit(self, limit):
        lower_limit = float(self.ask('RANGE? 0'))
        upper_limit = float(self.ask('RANGE? 2'))
        if limit > lower_limit and limit < upper_limit:
            self.write_raw('RANGE 1 {}'.format(limit))
        else:
            raise ValueError('Range 1 limit must be between Range 0 limit ({} A)'.format(lower_limit) + ' and Range 2 limit ({} A)'.format(upper_limit))
    def _set_range2_limit(self, limit):
        lower_limit = float(self.ask('RANGE? 1'))
        upper_limit = float(self.ask('RANGE? 3'))
        if limit > lower_limit and limit < upper_limit:
            self.write_raw('RANGE 2 {}'.format(limit))
        else:
            raise ValueError('Range 2 limit must be between Range 1 limit ({} A)'.format(lower_limit) + ' and Range 3 limit ({} A)'.format(upper_limit))
    def _set_range3_limit(self, limit):
        lower_limit = float(self.ask('RANGE? 2'))
        upper_limit = float(self.ask('RANGE? 4'))
        if limit > lower_limit and limit < upper_limit:
            self.write_raw('RANGE 3 {}'.format(limit))
        else:
            raise ValueError('Range 3 limit must be between Range 2 limit ({} A)'.format(lower_limit) + ' and Range 4 limit ({} A)'.format(upper_limit))
    def _set_range4_limit(self, limit):
        lower_limit = float(self.ask('RANGE? 3'))
        if limit > lower_limit:
            self.write_raw('RANGE 4 {}'.format(limit))
        else:
            raise ValueError('Range 4 limit must be higher than Range 3 limit ({} A)'.format(lower_limit))
    

    
    #Standard commands for switching between remote and local control
    def remote(self):
        self.write_raw('REMOTE')
        self.is_remote() #Runs the the test above for remote connection, if not, throws an error to notify the user
    def local(self):
        self.write_raw('LOCAL')
        #Command to quickly test if the remote connection works
    def is_remote(self):
        init_val = float(self.ask('RATE? 5'))
        if init_val > 0.1:
            Delta = -0.1
        else:
            Delta = +0.1
        self.write_raw('RATE 5 {}'.format(init_val+Delta))
        test_val = self.ask('RATE? 5')
        try:
            test_val = float(test_val)
        except:
            print('Connection test error. RATE? 5 returned: ', test_val)
            print('Reattempting remote test.')
            sleep(1.0)
            self.is_remote()
        self.write_raw('RATE 5 {}'.format(init_val))
        if test_val != init_val:
            pass
        else:
            raise RemoteError('Remote control not enabled (toggle the Local button on the front panel until the purple \'Local\' text vanishes from the screen)')       
           
    def examine(self):
        for r in range(5):
            limit = float(self.ask('RANGE? {}'.format(r)))
            rate = float(self.ask('RATE? {}'.format(r)))
            print('Range {}:'.format(r) + 'Limit = {} A, '.format(limit) + 'Rate = {} A/s'.format(rate))
        print('Field: {} T'.format(self.field()))
        print('Sweep status: ' + self.sweep_status())
        
    #This command sets all the rates and corresponding limits to the default values, which are hard coded above
    def set_defaults(self):
        for r in range(5):
            rate_ = DEFAULT_RATES['RANGE{}'.format(r)]
            limit_ = DEFAULT_LIMITS['RANGE{}'.format(r)]
            self.write_raw('RATE {} '.format(r) + '{}'.format(rate_))
            self.write_raw('RANGE {} '.format(r) + '{}'.format(limit_))
            sleep(0.1)
            
    #Checks sweep status
    def sweep_status(self):
        return self.ask('SWEEP?')
    
    #Function to establish the upper limit as the setpoint with the lower limit to be gauranteed to less than the upper limit
    def setpoint(self, field): #field in Tesla
        units = self.units()
        llim_field = field - 0.1
        if units == 'A':
            ulim_setpoint = field/FIELD_TO_CURRENT
            llim_setpoint = llim_field/FIELD_TO_CURRENT
        else:
            ulim_setpoint = field*10
            llim_setpoint = llim_field*10
        self.write('LLIM {}'.format(llim_setpoint))
        sleep(0.05)
        self.write('ULIM {}'.format(ulim_setpoint))
        
    
    #Sets the first three rates to a constant value, with the usual buffers for RANGES 3 and 4
    def constant_rate(self, rate):
        check_rate(DEFAULT_LIMITS['RANGE2'], rate) #Desired rate can't be faster than the DEFAULT_LIMIT for RANGE 2
        for r in range(3):
            limit = DEFAULT_LIMITS['RANGE{}'.format(r)]
            self.write_raw('RATE {} '.format(r) + '{}'.format(rate))
            self.write_raw('RANGE {} '.format(r) + '{}'.format(limit))
            sleep(0.1)
        for r in range(3, 5):
            limit = DEFAULT_LIMITS['RANGE{}'.format(r)]
            rate_ = DEFAULT_RATES['RANGE{}'.format(r)]
            self.write_raw('RATE {} '.format(r) + '{}'.format(rate_))
            self.write_raw('RANGE {} '.format(r) + '{}'.format(limit))
            sleep(0.1)
        

#The following two commands are for testing that the input rates are not higher than the max rates, hard coded above
def find_range(current):
    current = abs(current)
    if current <= DEFAULT_LIMITS['RANGE0']:
        return 'RANGE0'
    if current >= DEFAULT_LIMITS['RANGE4']:
        return 'RANGE4'
    for i in range(1,5):
        if DEFAULT_LIMITS['RANGE{}'.format(i-1)] < current <= DEFAULT_LIMITS['RANGE{}'.format(i)]:
            return 'RANGE{}'.format(i)

def check_rate(current, rate):
    range_ = find_range(current)
    if rate > MAX_RATES[range_]:
        raise ValueError('Rate is too high for desired current range. Check MAX_RATES and corresponding DEFAULT_LIMITS (Page 20 of Manual, Table 5-1)')
    else:
        pass
    
class RemoteError(Exception):
    pass