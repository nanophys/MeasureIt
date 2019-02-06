# daq_driver.py

import nidaqmx, time
import qcodes as qc
from qcodes import (Instrument, validators as vals)
from qcodes.instrument.channel import InstrumentChannel

class Daq(Instrument):
    
    def __init__(self, address, name, ao_num, ai_num):
        super().__init__(address)
        system = nidaqmx.system.System.local()
        self.name=address
        self.device = system.devices[self.name]
        self.ao_num = ao_num
        self.ai_num = ai_num
        
        reader_tasks = []
        
        for a in range(ao_num):
            ch_name = 'ao'+str(a)
            channel = DaqAOChannel(self, self.device, self.name, ch_name)
            self.add_submodule(ch_name, channel)
        for b in range(ai_num):
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
        for a in range(self.ai_num):
            ch_name = 'ai' + str(a)
            channel = self.submodules[ch_name]
            
            channel.get("voltage")
    
    def __del__(self):
        try:
            for a,c in self.submodules.items():
                if c.task is not None:
                    c.task.close()
        except:
            pass
        
        super().__del__()
        
        
class DaqAOChannel(InstrumentChannel):
    def get_gain(self):
        return self.gain
    
    def set_gain(self, _gain):
        self.gain = _gain
        if self.channel != None:
            self.channel.ao_gain=_gain
        
    def get_voltage(self):
        return self._voltage
    
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
        
        self.gain=-1
        self._voltage=0
        self.impedance=-1
        
        self.task=None
        self.channel=None
        
        self.add_parameter('gain',
                           get_cmd=self.get_gain,
                           get_parser=float,
                           set_cmd=self.set_gain,
                           label='Output Gain',
                           val=vals.Numbers(0,1000)
                           )
        
        self.add_parameter('impedance',
                           get_cmd=self.get_load_impedance,
                           get_parser=float,
                           set_cmd=self.set_load_impedance,
                           label='Output Load Impedance',
                           vals=vals.Numbers(0,1000)
                           )
        
        self.add_parameter('voltage',
                           get_cmd=self.get_voltage,
                           get_parser=float,
                           set_cmd=self.set_voltage,
                           label='Current Voltage Output',
                           unit='V',
                           val=vals.Numbers(-10,10)
                           )
        
    def add_self_to_task(self, task):
        task.ao_channels.add_ao_voltage_chan(self.fullname)
        self.task=task
        self.channel=nidaqmx._task_modules.channels.ao_channel.AOChannel(self.task._handle, self.channel)
        if self.gain != -1:
            task.ao_channels.ao_gain=self.gain
        if self.impedance != -1:
            task.ao_load_impedance=self.impedance
            
    def clear_task(self):
        self.task=None
        self.channel=None
        
    def __del__(self):
        self.clear_task()
    
    
        
class DaqAIChannel(InstrumentChannel):
    
    def get_gain(self):
        return self.gain
    
    def set_gain(self, _gain):
        self.gain = _gain
        if self.channel != None:
            self.channel.ai_gain=_gain
        
    def get_voltage(self):
        if self.task != None:
            self._voltage = self.task.read()
        return self._voltage
        
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
        
        self.gain=-1
        self._voltage=0
        self.impedance=-1
        
        self.task=None
        self.channel=None
        
        self.add_parameter('gain',
                           get_cmd=self.get_gain,
                           get_parser=float,
                           set_cmd=self.set_gain,
                           label='Input Gain',
                           vals=vals.Numbers(0,1000)
                           )
        
        self.add_parameter('impedance',
                           get_cmd=self.get_load_impedance,
                           get_parser=float,
                           set_cmd=self.set_load_impedance,
                           label='Input Load Impedance',
                           vals=vals.Numbers(0,1000)
                           )
        
        self.add_parameter('voltage',
                           get_cmd=self.get_voltage,
                           get_parser=float,
                           label='Current Voltage Input',
                           unit='V',
                           vals=vals.Numbers(-10,10)
                           )
        
    def add_self_to_task(self, task):
        if self.task is not None:
            return 0
        
        task.ai_channels.add_ai_voltage_chan(self.fullname)
        self.task=task
        self.channel=nidaqmx._task_modules.channels.ai_channel.AIChannel(self.task._handle, self.channel)
        if self.gain != -1:
            task.ai_channels.ai_gain=self.gain
        if self.impedance != -1:
            task.ai_load_impedance=self.impedance
        
        return 1
    
    def clear_task(self):
        self.task=None
        self.channel=None
        
    def __del__(self):
        self.clear_task()
        
        
def main():
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