from qcodes import VisaInstrument, InstrumentChannel, ChannelList
from qcodes.instrument.group_parameter import Group, GroupParameter
from qcodes.utils.validators import Enum


class SensorChannel(InstrumentChannel):
    """
        Channel class for the Lakeshore 331.

        Args:
            parent: The parent Lakeshore 331.
            name: The channel name.
            channel: The channel ID.

        Attributes:
            channel: The channel ID.
        """

    _CHANNEL_VAL = Enum("A", "B")

    def __init__(self, parent, name, channel):
        super().__init__(parent, name)

        self._CHANNEL_VAL.validate(channel)
        self._channel = channel

        self.add_parameter('temperature',
                           get_cmd='KRDG? {}'.format(self._channel),
                           get_parser=float,
                           label='Temerature',
                           unit='K')

        self.add_parameter('sensor_raw',
                           get_cmd='SRDG? {}'.format(self.channel),
                           get_parser=float,
                           label='sensor raw {}'.format(self.channel))

        self.add_parameter('sensor_status',
                           get_cmd='RDGST? {}'.format(self._channel),
                           val_mapping={
                               'OK': 0,
                               'Invalid Reading': 1,
                               'Temp Underrange': 16,
                               'Temp Overrange': 32,
                               'Sensor Units Zero': 64,
                               'Sensor Units Overrange': 128},
                           label='Sensor_Status')


class Lakeshore_331(VisaInstrument):
    """
        Instrument class for the Lakeshore 331.

        Args:
            name: The channel name.
            address: The GPIB address.
        """

    _loop = 1

    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, terminator="\r\n", **kwargs)
        channels = ChannelList(self, "TempSensors", SensorChannel, snapshotable=False)
        for chan_name in ('A', 'B'):
            channel = SensorChannel(self, chan_name)
            channels.append(channel)
            self.add_submodule(chan_name, channel)
        channels.lock()
        self.add_submodule("channels", channels)

        # add parameters
        self.add_parameter('heater_output',
                           get_cmd='HTR?',
                           get_parser=float,
                           label='heater output',
                           unit='%')

        self.add_parameter('heater_range',
                           get_cmd='RANGE?',
                           get_parser=int,
                           set_cmd='RANGE {}',
                           val_mapping={
                               'off': 0,
                               '0.5W': 1,
                               '5W': 2,
                               '50W': 3},
                           label='heater range')

        self.add_parameter('input',
                           get_cmd=f'CSET? {self._loop}',
                           set_cmd=f'CSET {self._loop},{{input}},1,1,1',
                           get_parser=lambda ans: ans[0],
                           label='input')

        self.add_parameter('setpoint',
                           get_cmd='SETP? ' + str(self._loop),
                           set_cmd='SETP ' + str(self._loop) + ', {}',
                           get_parser=float,
                           label='setpoint',
                           unit='K')

        self.add_parameter('P',
                           label='P',
                           parameter_class=GroupParameter)

        self.add_parameter('I',
                           label='I',
                           parameter_class=GroupParameter)

        self.add_parameter('D',
                           label='D',
                           parameter_class=GroupParameter)

        self.measure_group = Group([self.P, self.I, self.D],
                                   get_cmd=f'PID? {self._loop}',
                                   set_cmd=f'PID {self._loop},{{P}},{{I}},{{D}}')

        self.connect_message()
