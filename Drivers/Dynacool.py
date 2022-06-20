from typing import Dict, List, Optional, Sequence, Any, Union
import numpy as np
import logging
log = logging.getLogger(__name__)
import qcodes as qc
from qcodes.instrument.base import Instrument
import qcodes.utils.validators as vals
from MultiPyVu import MultiVuClient as mvc

class DynacoolBase(Instrument):
    """Qcodes drvier for QuantumDesign Dynacool. 

    This drivier is to get and acquire important data from Opticool
    PPMS's code should be similar. 

    Args:
        name: Name of instrument
        deviceIP: ipaddress of the Dynacool PC
    """
    def __init__(self, name: str, address: str,**kwargs) -> None:
        super().__init__(name, **kwargs)
        self.client = mvc.MultiVuClient(host = address)
        self.client.open()
        log.info(f'Successfully connectied to {name} with ip address {address}.')
        self.temp_ramp_method = self.client.temperature.approach_mode.fast_settle
        self.field_ramp_method = self.client.field.approach_mode.linear
        self.rate_K_per_min = 1.0
        self.add_parameter('temperature',
                        label='temperature',
                        unit='K',
                        get_cmd=self._get_temperature,
                        get_parser=float,
                        set_cmd=self._set_temperature)
        self.add_parameter('temperature_state',
                        label = 'Temperature tracking state',
                        get_parser=str,
                        get_cmd=self._get_temp_status)
        self.add_parameter('field',
                        label = 'Field',
                        unit = 'Oe',
                        get_cmd = self._get_field,
                        get_parser=float)
        self.add_parameter('magnet_state',
                        label = 'Magnet state',
                        get_parser=str,
                        get_cmd=self._get_field_status)    
    def ramp(self,target,rate):
        self._set_field(target,rate)


    def _set_temperature(self,set_point: float):
        """
        Parameter:
        set_point: temperature set point
        rate_K_per_min: 
        """
        self.client.set_temperature(set_point,self.rate_K_per_min,self.temp_ramp_method)
    def _get_temperature(self):
        temperature, status = self.client.get_temperature()
        return temperature
    def _get_temp_status(self):
        temperature, status = self.client.get_temperature()
        return status
    
    def _set_field(self, target, ramp_rate):
        self.client.set_field(target,ramp_rate,self.field_ramp_method)

    def _get_field(self):
        field, status = self.client.get_field()
        return field
    def _get_field_status(self):
        field, status = self.client.get_field()
        return status

    def close(self) -> None:
        """
        make sure to close the connection
        """
        self.log.debug('closing the connection')
        self.client.close_server()
