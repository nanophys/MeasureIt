from qcodes.instrument.ip import IPInstrument
from qcodes.instrument.group_parameter import Group, GroupParameter
import qcodes.utils.validators as vals


class LM510(IPInstrument):

    def __init__(self, name, address='192.168.1.152', port=4266, timeout=5, *args, **kwargs):
        super().__init__(name, address, port, timeout, *args, **kwargs)

        self.add_parameter('setpoint',
                           label='Pressure setpoint',
                           unit='psi',
                           get_cmd='PSET?',
                           set_cmd=f'PSET {{}}',
                           vals=vals.Numbers(0.15, 14.25),
                           get_parser=lambda resp: float(resp.replace(' PSI\r\n', '')))

        self.add_parameter('heater_limit',
                           label='Heater limit',
                           unit='W',
                           get_cmd='HLIM?',
                           set_cmd=f'HLIM {{}}',
                           vals=vals.Numbers(0.1, 10),
                           get_parser=lambda resp: resp.replace(' Watts\r\n', ''))

        self.add_parameter('heater_enabled',
                           label='Heater enabled',
                           get_cmd='HEAT?',
                           set_cmd=f'HEAT {{}}',
                           vals=vals.Enum('ON', 'OFF'),
                           get_parser=lambda resp: resp.replace('\r\n', '')
                           )

        self.chan = 2
        self.add_parameter('channel',
                           label='Channel',
                           docstring='Channel for measuring.',
                           set_cmd=self.set_channel,
                           get_cmd=self.get_channel,
                           vals=vals.Ints(1, 2))

        self.add_parameter('pressure',
                           label='Pressure',
                           unit='psi',
                           parameter_class=GroupParameter)

        self.add_parameter('heater_output',
                           label='Heater output',
                           unit='W',
                           parameter_class=GroupParameter)

        self.measure_group = Group([self.pressure, self.heater_output],
                                   get_cmd=f'MEAS? {self.chan}',
                                   get_parser=self._measure)

        self.connect_message()

    def set_channel(self, n):
        self.chan = n

    def get_channel(self):
        return self.chan

    def _measure(self, resp):
        values = resp.split('  ')

        p_dict = {}
        p_dict['pressure'] = float(values[0].split(' ')[0])
        p_dict['heater_output'] = float(values[1].split(' ')[0])
        return p_dict
