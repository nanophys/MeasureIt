from qcodes.instrument.visa import VisaInstrument
from qcodes.instrument.ip import IPInstrument

class SCM10(IPInstrument):

    def __init__(self, name, address='192.168.1.4', port=9760, timeout=5, terminator='\r\n', *args, **kwargs):
        super().__init__(name, address, port, timeout, terminator, *args, **kwargs)

        self.add_parameter('temperature',
                           label='temperature',
                           unit='K',
                           get_cmd='T?',
                           get_parser=lambda resp: float(resp.replace('T ', '')))

        self.add_parameter('sensor_reading',
                           label='sensor reading',
                           unit='V',
                           get_cmd='SDAT?',
                           get_parser=lambda resp: resp.replace('SDAT ', ''))

        self.add_parameter('error_status',
                           label='error status',
                           get_cmd='ERSTA?',
                           get_parser=lambda resp: resp.replace('ERSTA ', '')
                           )

        self.connect_message()
