# Remove this once QCoDeS/Qcodes#1156 goes in.

from qcodes import VisaInstrument, InstrumentChannel, ChannelList
from qcodes.utils.validators import Enum


class SensorChannel(InstrumentChannel):
    _CHANNEL_VAL = Enum("A", "B")
    def __init__(self, parent, name, channel):
        super().__init__(parent, name)

        self._CHANNEL_VAL.validate(channel)
        self._channel = channel

        self.add_parameter('temperature', get_cmd='KRDG? {}'.format(self._channel),
                           get_parser=float,
                           label='Temerature',
                           unit='K')
        self.add_parameter('sensor_status', get_cmd='RDGST? {}'.format(self._channel),
                           val_mapping={'OK': 0, 'Invalid Reading': 1, 'Temp Underrange': 16, 'Temp Overrange': 32,
                           'Sensor Units Zero': 64, 'Sensor Units Overrange': 128}, label='Sensor_Status')


class Lakeshore_331(VisaInstrument):
    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, terminator="\r\n", **kwargs)
        channels = ChannelList(self, "TempSensors", SensorChannel, snapshotable=False)
        for chan_name in ('A', 'B'):
            channel = SensorChannel(self, 'Chan{}'.format(chan_name), chan_name)
            channels.append(channel)
            self.add_submodule(chan_name, channel)
        channels.lock()
        self.add_submodule("channels", channels)

        self.connect_message()
