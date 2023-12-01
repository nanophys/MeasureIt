##Made by Dacen, copied over from cryocon_26 driver

from qcodes import VisaInstrument
from qcodes.utils.validators import Numbers, Enum, Ints, Bool
from time import sleep
from scipy.interpolate import interp1d
from numpy import loadtxt
from os.path import dirname, abspath

MAX_TEMP = 400 #K

dir = dirname(abspath(__file__))

class Cryocon_24(VisaInstrument):
    """
    Driver for the Cryo-con Model 24 temperature controller.
    """
    def __init__(self, name, address, terminator='\r\n', **kwargs):
        super().__init__(name, address, terminator=terminator, **kwargs)
        
        on_off_map = {True: 'ON ', False: 'OFF'}
        mapping_loop1 = {'high': 'HI ', 'medium': 'MID', 'low': 'LOW'}
        mapping_loop2 = {'high': 'HI ', 'low': 'LOW'}

        self.add_parameter('control_enabled',
                           get_cmd='control?',
                           val_mapping=on_off_map)

        self.add_parameter('chA_temperature',
                           get_cmd=self._get_chA_temperature,
                           get_parser=float,
                           unit = 'K'
                          )
        self.add_parameter('chB_temperature',
                           get_cmd=self._get_chB_temperature,
                           get_parser=float,
                           unit = 'K'
                          )
        for loop in [1, 2]:
            l = 'loop{}_'.format(loop)
            self.add_parameter(l + 'is_ramping',
                               get_cmd='loop {}:ramp?'.format(loop),
                               val_mapping=on_off_map,
                               snapshot_value=False
                              )
#             self.add_parameter(l + 'read_heater',
#                                get_cmd='loop {}:htrread?',
#                                get_parser=float,
#                                snapshot_value=False,
#                                unit='%')
#             self.add_parameter(l + 'output_power',
#                                get_cmd='loop {}:outp?',
#                                get_parser=float,
#                                snapshot_value=False,
#                                unit='%')

        self.add_parameter('loop1_load',
                           get_cmd=self._get_loop1_load,
                           set_cmd=self._set_loop1_load,
                           get_parser=int,
                           unit='Ohms',
                           vals=Enum(25, 50)
                          )
    
        if self.loop1_load() == 50:
            self.PID_TABLE_chA = loadtxt(dir + '/data/CyroCon24C_ChA_PID_Table_50Ohm.txt', skiprows = 2, delimiter = ',')
        elif self.loop1_load() == 25:
            self.PID_TABLE_chA = loadtxt(dir + '/data/CyroCon24C_ChA_PID_Table_25Ohm.txt', skiprows = 2, delimiter = ',')
            
            
        self.add_parameter('chA_units',
                           get_cmd='input A:units?',
                           get_parser=str,
                           set_cmd=self._set_chA_units,
                           vals=Enum('K', 'C', 'F', 'S')
                          )
        self.add_parameter('chB_units',
                           get_cmd='input B:units?',
                           get_parser=str,
                           set_cmd=self._set_chB_units,
                           vals=Enum('K', 'C', 'F', 'S')
                          )
        
        self.add_parameter('loop1_source',
                           get_cmd='loop 1:source?',
                           get_parser=float,
                           set_cmd=self._set_loop1_source,
                           vals=Enum('A', 'B'),
                           snapshot_value=False
                          )
        self.add_parameter('loop2_source',
                           get_cmd='loop 2:source?',
                           get_parser=float,
                           set_cmd=self._set_loop1_source,
                           vals=Enum('A', 'B'),
                           snapshot_value=False
                          )
        
        self.add_parameter('loop1_setpoint',
                           get_cmd=self._get_loop1_setpoint,
                           get_parser=float,
                           set_cmd=self._set_loop1_setpoint,
                           vals=Numbers(0, MAX_TEMP)
                          )
        self.add_parameter('loop2_setpoint',
                           get_cmd=self._get_loop2_setpoint,
                           get_parser=float,
                           set_cmd=self._set_loop2_setpoint,
                           vals=Numbers(0, MAX_TEMP)
                          )
        
        self.add_parameter('loop1_type',
                            get_cmd='loop 1:type?',
                            set_cmd=self._set_loop1_type,
                            val_mapping={
                                'off': 'OFF  ',
                                'manual': 'MAN  ',
                                'PID': 'PID  ',
                            }
                           )
        self.add_parameter('loop2_type',
                            get_cmd='loop 2:type?',
                            set_cmd=self._set_loop2_type,
                            val_mapping={
                                'off': 'OFF  ',
                                'manual': 'MAN  ',
                                'PID': 'PID  ',
                            }
                           )
        self.add_parameter('loop1_range',
                           get_cmd='loop 1:range?',
                           set_cmd=self._set_loop1_range,
                           val_mapping=mapping_loop1,
                           snapshot_value=False
                          )
        self.add_parameter('loop2_range',
                           get_cmd='loop 2:range?',
                           set_cmd=self._set_loop2_range,
                           val_mapping=mapping_loop2,
                           snapshot_value=False
                          )
        
        self.add_parameter('loop1_P',
                           get_cmd='loop 1:pgain?',
                           set_cmd=self._set_loop1_P,
                           get_parser=float,
                           vals=Numbers(0, 1000)
                          )
        self.add_parameter('loop1_I',
                           get_cmd='loop 1:igain?',
                           get_parser=float,
                           set_cmd=self._set_loop1_I,
                           vals=Numbers(0, 1000),
                          )
        self.add_parameter('loop1_D',
                           get_cmd='loop 1:dgain?',
                           get_parser=float,
                           set_cmd=self._set_loop1_D,
                           vals=Numbers(0, 1000),
                          )
        
        self.add_parameter('loop2_P',
                           get_cmd='loop 2:pgain?',
                           get_parser=float,
                           set_cmd=self._set_loop2_P,
                           vals=Numbers(0, 1000)
                          )
        self.add_parameter('loop2_I',
                           get_cmd='loop 2:igain?',
                           get_parser=float,
                           set_cmd=self._set_loop2_I,
                           vals=Numbers(0, 1000),
                          )
        self.add_parameter('loop2_D',
                           get_cmd='loop 2:dgain?',
                           get_parser=float,
                           set_cmd=self._set_loop2_D,
                           vals=Numbers(0, 1000),
                          )
        
        self.add_parameter('loop1_manual_power',
                           get_cmd='loop 1:pman?',
                           set_cmd=self._set_loop1_manual_power,
                           get_parser=float,
                           vals=Numbers(0, 100),
                           unit='%'
                          )
        self.add_parameter('loop2_manual_power',
                           get_cmd='loop 2:pman?',
                           set_cmd=self._set_loop2_manual_power,
                           get_parser=float,
                           vals=Numbers(0, 100),
                           unit='%'
                          )
        
        self.add_parameter('sample_temperature',
                           get_cmd=self._get_chA_temperature,
                           set_cmd=self._set_sample_temperature,
                           get_parser=float,
                           unit = 'K'
                          )
        
        self.add_parameter('vti_temperature',
                           get_cmd=self._get_chB_temperature,
                           set_cmd=self._set_vti_temperature,
                           get_parser=float,
                           unit = 'K'
                          )
        
        self.add_parameter('simultaneous_temperature',
                           set_cmd=self._set_simultaneous_temperature,
                           get_cmd=self._get_chA_temperature,
                           get_parser=float,
                           unit = 'K'
                          )

        
    def _execute(self, command):
        self.device_clear()
        self.write_raw(command)
        sleep(1.0)
        self.device_clear()
    def _ask(self, message):
        try:
            self.ask(message)
        except:
            sleep(1.0)
            self._ask(message)
        return self.ask(message)
    
#     for channel in ['A', 'B']:
#             c = 'ch{}_'.format(channel)
#             self.add_parameter(c + 'temperature',
#                                get_cmd='input? {}'.format(channel),
#                                get_parser=float,
#                               )
    def _get_chA_temperature(self):
        return self._ask('input? A')
    def _get_chB_temperature(self):
        return self._ask('input? B')
    def _set_chA_units(self, units):
        self._execute('input A:units ' + units)
    def _set_chB_units(self, units):
        self._execute('input B:units ' + units)
    
    def _set_loop1_load(self, load):
        # Set the PID table values depending on what the load is set to
        self._execute('loop 1:load {}'.format(load))
        if load == 50:
            self.PID_TABLE_chA = loadtxt(dir + '/data/CyroCon24C_ChA_PID_Table_50Ohm.txt', skiprows = 2, delimiter = ',')
        elif load == 25:
            self.PID_TABLE_chA = loadtxt(dir + '/data/CyroCon24C_ChA_PID_Table_25Ohm.txt', skiprows = 2, delimiter = ',')         
    def _get_loop1_load(self):
        result = self._ask('loop 1:load?')
        return result
        
    
    def _set_loop1_source(self, channel):
        self._execute('loop 1:source ' + channel)
    def _set_loop2_source(self, channel):
        self._execute('loop 2:source ' + channel)
    def _get_loop1_setpoint(self):
        result = self.ask('loop 1:setpt?')
        return float(result[:-1])
    def _get_loop2_setpoint(self):
        result = self.ask('loop 2:setpt?')
        return float(result[:-1])
    def _set_loop1_setpoint(self, setpoint):
        self._execute('loop 1:setpt {}'.format(setpoint))
    def _set_loop2_setpoint(self, setpoint):
        self._execute('loop 2:setpt {}'.format(setpoint))
    def _set_loop1_type(self, type_):
        self._execute('loop 1:type ' + type_)
    def _set_loop2_type(self, type_):
        self._execute('loop 2:type ' + type_)
    def _set_loop1_range(self, range_):
        self._execute('loop 1:range ' + range_)
    def _set_loop2_range(self, range_):
        self._execute('loop 2:range ' + range_)
    
    def _set_loop1_P(self, P):
        self._execute('loop 1:pgain {}'.format(P))
    def _set_loop1_I(self, I):
        self._execute('loop 1:igain {}'.format(I))
    def _set_loop1_D(self, D):
        self._execute('loop 1:dgain {}'.format(D))
        
    def _set_loop2_P(self, P):
        self._execute('loop 2:pgain {}'.format(P))
    def _set_loop2_I(self, I):
        self._execute('loop 2:igain {}'.format(I))
    def _set_loop2_D(self, D):
        self._execute('loop 2:dgain {}'.format(D))
        
    def _set_loop1_manual_power(self, power):
        self._execute('loop 1:pman {}'.format(power))
    def _set_loop2_manual_power(self, power):
        self._execute('loop 2:pman {}'.format(power))
        
    def _set_sample_temperature(self, setpoint):
        check_set(self.loop1_setpoint, setpoint)
        self.update_sample_PID(setpoint)
    
    def _set_vti_temperature(self, setpoint):
        check_set(self.loop2_setpoint, setpoint)
        self.update_vti_PID(setpoint)
    
    def _set_simultaneous_temperature(self, setpoint):
        self._set_sample_temperature(setpoint)
        self._set_vti_temperature(setpoint)
        
    def update_sample_PID(self, setpoint):
#         if self.loop1_load() == 50:
#             P, I, D, heater_range = interpolate_PID_value(setpoint, PID_TABLE_chA_50Ohm, HEATER_RANGE_MAPPING_chA)
#         elif self.loop1_load() == 25:
#             P, I, D, heater_range = interpolate_PID_value(setpoint, PID_TABLE_chA_25Ohm, HEATER_RANGE_MAPPING_chA)  
        P, I, D, heater_range = interpolate_PID_value(setpoint, self.PID_TABLE_chA, HEATER_RANGE_MAPPING_chA)
        check_set(self.loop1_P, P)
        check_set(self.loop1_I, I)
        check_set(self.loop1_D, D)
        check_set(self.loop1_range, heater_range)
        
    def update_vti_PID(self, setpoint):
        P, I, D, heater_range = interpolate_PID_value(setpoint, PID_TABLE_chB, HEATER_RANGE_MAPPING_chB)
        check_set(self.loop2_P, P)
        check_set(self.loop2_I, I)
        check_set(self.loop2_D, D)
        check_set(self.loop2_range, heater_range)
    
    def stop(self):
        self.write_raw('stop')
        sleep(2.0)
        self.device_clear()
    def control(self):
        self.write_raw('control')
        sleep(2.0)
        self.device_clear()

# PID_TABLE_chA_50Ohm = loadtxt('./Drivers/Cryocon/CyroCon24C_ChA_PID_Table_50Ohm.txt', skiprows = 2, delimiter = ',')
# PID_TABLE_chA_25Ohm = loadtxt('./Drivers/Cryocon/CyroCon24C_ChA_PID_Table_25Ohm.txt', skiprows = 2, delimiter = ',')
HEATER_RANGE_MAPPING_chA = {
    0 : 'low',
    1 : 'medium',
    2 : 'high'
}

PID_TABLE_chB = loadtxt(dir + '/data/CyroCon24C_ChB_PID_Table.txt', skiprows = 2, delimiter = ',')
HEATER_RANGE_MAPPING_chB = {
    0 : 'low',
    1 : 'high'
}  
        
def interpolate_PID_value(T, PID_TABLE, HEATER_RANGE_MAPPING):
    #Interpolate the PID value for the temperature given in K
    P = float(interp1d(PID_TABLE[:, 0], PID_TABLE[:, 1])(T))
    I = float(interp1d(PID_TABLE[:, 0], PID_TABLE[:, 2])(T))
    D = float(interp1d(PID_TABLE[:, 0], PID_TABLE[:, 3])(T))
    heater_range = round(float(interp1d(PID_TABLE[:, 0], PID_TABLE[:, 4])(T)))
    return P, I, D, HEATER_RANGE_MAPPING[heater_range]
        
def check_set(param, setpoint):
    try:
        if param.get() == setpoint:
            return False
        else:
            param.set(setpoint)
            return True
    except:
        sleep(1.0)
        check_set(param, setpoint)