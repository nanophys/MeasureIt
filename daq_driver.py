# daq_driver.py

import nidaqmx, time
import qcodes as qc
from qcodes import (Instrument, validators as vals)
from qcodes.instrument.channel import InstrumentChannel

class Daq(Instrument):
    """
    QCoDeS instrument driver for the National Instruments DAQ. Defines Parameters for each of the IO channels.
    """
    def __init__(self, address="", name="Daq"):
        """
        Initialization for the DAQ driver. Takes in the machine given device address (typically "Dev1"), a user-defined
        name, and the number of ao and ai ports. Creates QCoDeS Parameters for each of the io channels.
        """
        
        super().__init__(address)
        system = nidaqmx.system.System.local()
        self.name=address
        self.device = system.devices[self.name]
        self.ao_num = len(self.device.ao_physical_chans.channel_names)
        self.ai_num = len(self.device.ai_physical_chans.channel_names)
        
        reader_tasks = []
        
        for a in range(self.ao_num):
            if int(a/8)%2 == 0:
                ch_name = 'ao'+str(a)
                channel = DaqAOChannel(self, self.device, self.name, ch_name)
                self.add_submodule(ch_name, channel)
        for b in range(self.ai_num):
            if int(b/8)%2 == 0:
                ch_name = 'ai'+str(b)
                channel = DaqAIChannel(self, self.device, self.name, ch_name)
                self.add_submodule(ch_name, channel)
                task=nidaqmx.Task("reading " + ch_name)
                channel.add_self_to_task(task)
                reader_tasks.append(task)
             
    def get_ao_num(self):
        return self.ao_num
    
    def get_ai_num(self):
        return self.ai_num
    
    def update_all_inputs(self):
        """
        Updates all the AI channel voltage values.
        """
        for chan_name in self.submodules:
            self.submodules[chan_name].get("voltage")
    
    def __del__(self):
        """
        Destructor method. Seemingly necessary for the nidaqmx library to not cause issues upon
        relaunching the software.
        """
        try:
            for a,c in self.submodules.items():
#               Removes all Task objects from the channels, so system doesn't complain
                if c.task is not None:
                    c.task.close()
        except:
            pass
        
        # Makes sure the Instrument destructor is called
        super().__del__()
        
        
class DaqAOChannel(InstrumentChannel):
    """
    
    """
    def get_gain(self):
        return (self.gain, self.parameters["gain"].unit)
    
    def set_gain(self, _gain):
        self.gain = _gain[0]
        self.parameters["gain"].unit=_gain[1]
#        if self.channel != None:
#            self.channel.ao_gain=_gain
        
    def get_voltage(self):
        return self._voltage
    
    def get_value(self):
        parts = self.parameters["gain"].unit.split("/")
        self.parameters["value"].unit=parts[0]
        self._value = self.gain * self._voltage
        return self._value
        
    def set_voltage(self, _voltage):
        if self.task != None:
            self.task.write(_voltage)
            self._voltage=_voltage
        
    def get_load_impedance(self):
        return self.impedance
    
    def set_load_impedance(self, _imp):
        self.impedance = _imp
        if self.channel != None:
            self.channel.ao_load_impedance=_imp
        
    def __init__(self, parent: Instrument, device, address, channel):
        super().__init__(parent, channel)
        self.device=device
        self.address=address
        self.channel=channel
        self.name=str(channel)
        self.fullname=self.address+"/"+self.name
        
        self.gain=1
        self._voltage=0
        self.impedance=None
        self._value=0
        
        self.task=None
        self.channel=None
        
        self.add_parameter('gain',
                           get_cmd=self.get_gain,
                           get_parser=str,
                           set_cmd=self.set_gain,
                           label='Output Gain',
                           unit='V/V',
                           val=vals.Numbers(0,1000)
                           )
        
        self.add_parameter('impedance',
                           get_cmd=self.get_load_impedance,
                           get_parser=float,
                           set_cmd=self.set_load_impedance,
                           label='Output Load Impedance',
                           vals=vals.Numbers(0,1000)
                           )
        
        self.add_parameter('value',
                           get_cmd=self.get_value,
                           get_parser=float,
                           label='Voltage * Factor',
                           val=vals.Numbers(0,10000000))
        
        self.add_parameter('voltage',
                           get_cmd=self.get_voltage,
                           get_parser=float,
                           set_cmd=self.set_voltage,
                           label='Output Voltage',
                           unit='V',
                           val=vals.Numbers(-10,10)
                           )
        
    def add_self_to_task(self, task):
        if self.task is not None:
            self.clear_task()
            
        task.ao_channels.add_ao_voltage_chan(self.fullname)
        self.task=task
        self.channel=nidaqmx._task_modules.channels.ao_channel.AOChannel(self.task._handle, self.channel)
        if self.gain != -1:
            task.ao_channels.ao_gain=self.gain
        if self.impedance != -1:
            task.ao_load_impedance=self.impedance
            
    def clear_task(self):
        if self.task is not None:
            self.task.close()
        self.task=None
        self.channel=None
        
    def __del__(self):
        self.clear_task()
    
    
        
class DaqAIChannel(InstrumentChannel):
    
    def get_gain(self):
        return (self.gain, self.parameters["gain"].unit)
    
    def set_gain(self, _gain):
        self.gain = _gain[0]
        self.parameters["gain"].unit=_gain[1]
#        if self.channel != None:
#            self.channel.ai_gain=_gain
        
    def get_voltage(self):
        if self.task != None:
            self._voltage = self.task.read()
        return self._voltage
        
    def get_value(self):
        parts = self.parameters["gain"].unit.split("/")
        self.parameters["value"].unit=parts[0]
        self._value = self.gain * self._voltage
        return self._value
    
    def get_load_impedance(self):
        return self.impedance
    
    def set_load_impedance(self, _imp):
        self.impedance = _imp
        if self.channel != None:
            self.channel.ai_load_impedance=_imp
        
    def __init__(self, parent: Instrument, device, address, channel):
        super().__init__(parent, channel)
        self.device=device
        self.address=address
        self.channel=channel
        self.name=str(channel)
        self.fullname=self.address+"/"+self.name
        
        self.gain=1
        self._voltage=0
        self.impedance=None
        self._value=0
        
        self.task=None
        self.channel=None
        
        self.add_parameter('gain',
                           get_cmd=self.get_gain,
                           get_parser=str,
                           set_cmd=self.set_gain,
                           label='Input Gain',
                           unit='V/V',
                           vals=vals.Numbers(0,1000)
                           )
        
        self.add_parameter('impedance',
                           get_cmd=self.get_load_impedance,
                           get_parser=float,
                           set_cmd=self.set_load_impedance,
                           label='Input Load Impedance',
                           vals=vals.Numbers(0,1000)
                           )
        
        self.add_parameter('value',
                           get_cmd=self.get_value,
                           get_parser=float,
                           label='Voltage * Factor',
                           vals=vals.Numbers(0,100000000))
        
        self.add_parameter('voltage',
                           get_cmd=self.get_voltage,
                           get_parser=float,
                           label='Input Voltage',
                           unit='V',
                           vals=vals.Numbers(-10,10)
                           )
        
    def add_self_to_task(self, task):
        if self.task is not None:
            self.clear_task()
        
        task.ai_channels.add_ai_voltage_chan(self.fullname)
        self.task=task
        self.channel=nidaqmx._task_modules.channels.ai_channel.AIChannel(self.task._handle, self.channel)
        if self.gain != -1:
            task.ai_channels.ai_gain=self.gain
        if self.impedance != -1:
            task.ai_load_impedance=self.impedance
        
        return 1
    
    def clear_task(self):
        if self.task is not None:
            self.task.close()
        self.task=None
        self.channel=None
        
    def __del__(self):
        self.clear_task()


            
def main():
    from util import _value_parser
    print(_value_parser('  -.005p'))
    print(_value_parser(' 2.1 '))
    print(_value_parser('2.5  u'))
    print(_value_parser('2.5 U'))
    print(_value_parser(' -2.5 G'))
    print(_value_parser('.'))
    print(_value_parser('2f'))
    print(_value_parser('.05f'))
    print(_value_parser('2.u'))
    
def main_daq():
    daq=Daq("Dev1","test",2,24)
    print(daq.ai1)
    print(daq.ao1)
    daq.ao1.set("gain",4)
    print(daq.ao1.get("gain"))
    writer=nidaqmx.Task()
    reader=nidaqmx.Task()
    daq.ao1.add_self_to_task(writer)
    daq.ai2.add_self_to_task(reader)
    daq.ao1.set("voltage",1)
    print(daq.ai2.get("voltage"))
    print(daq.ai2.get("voltage"))
    print(daq.ai2.get("voltage"))
    writer.close()
    time.sleep(3)
    print(daq.ai2.get("voltage"))
    reader.close()
    daq.close()






if __name__ == "__main__":
    main()