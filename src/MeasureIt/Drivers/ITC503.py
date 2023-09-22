import logging
import time
from qcodes.instrument import VisaInstrument
import qcodes.utils.validators as vals
from functools import partial

log = logging.getLogger(__name__)

class ITC503(VisaInstrument):
    _GET_STATUS_MODE = {
        0: 'Local',
        1: 'Remote'
    }

    _GET_LOCK_MODE = {
        0: 'Locked',
        1: 'Unlocked'
    }

    _GET_OUTPUT_MODE = {
        0: 'Manual',
        1: 'Auto'
    }

    _GET_AUTOPID_STATUS = {
        0: 'Disabled',
        1: 'Enabled'
    }

    _WRITE_WAIT = 100e-3

    def __init__(self, name, address, *args, **kwargs):

        connect_time = time.time()

        super().__init__(name, address, terminator='\r', **kwargs)

        self.add_parameter('identity',
                           label='identity',
                           get_cmd=self.identity_dict)

        self.add_parameter('control',
                           label='Control',
                           docstring='Specifies local or remote control',
                           vals=vals.Numbers(0, 1),
                           set_cmd=self._set_control_status,
                           get_cmd=self._get_control_status)

        self.add_parameter('control_lock',
                           label='Control lock',
                           vals=vals.Numbers(0,1),
                           set_cmd=self._set_control_lock_status,
                           get_cmd=self._get_control_lock_status)

        self.add_parameter('setpoint',
                           label='Temperature setpoint',
                           unit='K',
                           docstring='Specifies the temperature setpoint.',
                           vals=vals.Numbers(0, 500),
                           set_cmd=self._set_temperature_setpoint,
                           get_cmd=lambda: self._get_reading(0))

        self.add_parameter('temperature_1',
                           label='Temperature 1',
                           unit='K',
                           docstring='Temperature reading from sensor 1',
                           get_cmd=lambda: self._get_reading(1))

        self.add_parameter('temperature_2',
                           label='Temperature 2',
                           unit='K',
                           docstring='Temperature reading from sensor 2',
                           get_cmd=lambda: self._get_reading(2))

        self.add_parameter('temperature_3',
                           label='Temperature 3',
                           unit='K',
                           docstring='Temperature reading from sensor 3',
                           get_cmd=lambda: self._get_reading(3))

        self.add_parameter('temperature_error',
                           label='Temperature error',
                           get_cmd=lambda: self._get_reading(4))

        self.add_parameter('heater_output',
                           label='Heater Output (%)',
                           docstring="Output power of heater, expressed as percent of maximum output. Setting this "
                                     "parameter will change heater output to MANUAL mode.",
                           set_cmd=self._set_manual_output,
                           get_cmd=lambda: self._get_reading(5),
                           vals=vals.Numbers(0, 99.9))

        self.add_parameter('heater_output_volts',
                           label='Heater Output (V)',
                           unit='V',
                           get_cmd=lambda: self._get_reading(6))

        self.add_parameter('gas_flow',
                           label='Gas flow output',
                           get_cmd=lambda: self._get_reading(7))

        self.add_parameter('P',
                           label='Proportional band',
                           docstring='Proportional term for PID control loop.',
                           vals=vals.Numbers(0, 99.99),
                           set_cmd=self._set_P,
                           get_cmd=lambda: self._get_reading(8))

        self.add_parameter('I',
                           label='Integral action time',
                           docstring='Integral term for PID control loop.',
                           vals=vals.Numbers(0, 140),
                           set_cmd=self._set_I,
                           get_cmd=lambda: self._get_reading(9))

        self.add_parameter('D',
                           label='Derivative action time',
                           docstring='Derivative term for PID control loop.',
                           vals=vals.Numbers(0, 273),
                           set_cmd=self._set_D,
                           get_cmd=lambda: self._get_reading(10))

        self.add_parameter('heater_sensor',
                           label='Heater sensor',
                           docstring='Specifies the sensor to be used for automatic PID control.',
                           set_cmd=self._set_heater_sensor,
                           get_cmd=self._get_heater_sensor,
                           vals=vals.Numbers(1, 3))

        self.add_parameter('heater_mode',
                           label='heater mode',
                           set_cmd=self._set_output_mode,
                           get_cmd=self._get_output_mode,
                           vals=vals.Numbers(0, 1))

        self.add_parameter('gas_mode',
                           label='gas mode',
                           set_cmd=self._set_gas_mode,
                           get_cmd=self._get_gas_mode,
                           vals=vals.Numbers(0, 1))

        self.add_parameter('sweep',
                           label='Sweep',
                           set_cmd=self._set_sweep,
                           get_cmd=self._get_sweep_status,
                           vals=vals.Numbers(0, 1))

        self.connect_message(idn_param='identity', begin_time=connect_time)

    def _execute(self, message):
        self.log.info('Send the following command to the device: %s' % message)

        return self.visa_handle.query(message, self._WRITE_WAIT)

    def identify(self):
        """Identify the device"""
        self.log.info('Identify the device')
        return self._execute('V')

    def identity_dict(self):
        result = self._execute('V').split(' ')
        dictionary = {}
        dictionary['vendor'] = result[4]
        dictionary['model'] = result[0]
        dictionary['firmware'] = result[2]
        dictionary['serial'] = None

        return dictionary

    def examine(self):
        """Examine the status of the device"""
        self.log.info('Examine status')

        ex = self._execute('X')

        print(f'System status: {ex[1]}')
        print(f'Local/Remote Status: {self._GET_STATUS_MODE[int(ex[3])]}')
        print(f'Output Mode: {self._GET_OUTPUT_MODE[int(ex[5])]}')
        print(f'Sweep Status: {self._sweep_status(int(ex[7:9]))}')
        print(f'Control Sensor: {ex[10]}')
        print(f'Auto-PID Status: {self._GET_AUTOPID_STATUS[int(ex[12])]}')

    def _get_reading(self, n):
        result = self._execute(f'R{n}')

        return float(result[1:])

    def _set_temperature_setpoint(self, t):
        return self._execute(f'T{t}')

    def _set_P(self, P):
        return self._execute(f'P{P}')

    def _set_I(self, I):
        return self._execute(f'I{I}')

    def _set_D(self, D):
        return self._execute(f'D{D}')

    def _set_output_mode(self, n):
        gas = int(int(self._execute(f'X')[3])/2)
        return self._execute(f'A{int(n)+gas*2}')

    def _get_output_mode(self):
        result = self._execute(f'X')
        return self._GET_OUTPUT_MODE[int(result[3]) % 2]

    def _set_gas_mode(self, n):
        output = int(self._execute(f'X')[3]) % 2
        return self._execute(f'A{output+2*int(n)}')

    def _get_gas_mode(self):
        result = self._execute(f'X')
        return self._GET_OUTPUT_MODE[int(int(result[3])/2)]

    def _set_manual_output(self, n):
        return self._execute(f'O{n:.1f}')

    def _set_control_status(self, n):
        control_lock = int(int(self._execute(f'X')[5])/2)
        return self._execute(f'C{int(n)+2*control_lock}')

    def _get_control_status(self):
        result = self._execute(f'X')
        return self._GET_STATUS_MODE[int(result[5]) % 2]

    def _set_control_lock_status(self, n):
        control = int(self._execute(f'X')[5]) % 2
        return self._execute(f'C{control+2*int(n)}')

    def _get_control_lock_status(self):
        result = self._execute(f'X')
        return self._GET_LOCK_MODE[int(int(result[5])/2)]

    def _set_heater_sensor(self, n):
        return self._execute(f'H{int(n)}')

    def _get_heater_sensor(self):
        result = self._execute(f'X')
        return int(result[10])

    def _set_sweep(self, n):
        return self._execute(f'S{n}')

    def _get_sweep_status(self):
        result = self._execute(f'X')
        return self._sweep_status(int(result[7:9]))

    def _sweep_status(self, n):
        if n == 0:
            return 'Sweep not running'
        elif n % 2 == 1:
            return f'Sweeping to step {(int(n)+1)/2}'
        else:
            return f'Holding at step {int(n)/2}'
