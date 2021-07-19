# nidaq.py

import numpy as np
import time, sys, signal
import collections

from qcodes import VisaInstrument
from qcodes.instrument.parameter import ArrayParameter
from qcodes.utils.validators import Numbers, Ints, Enum, Strings
import nidaqmx

class NIDaq():
    """
    This is the driver for the National Instruments DAQ
    """
    
    def __init__(self, _name, _address, ao_num, ai_num):
        self.name = _name
        self.address = _address
        system = nidaqmx.system.System.local()
        self.device = system.devices[self.address]
        self.ao_chan = nidaqmx.Task("ao init")
        self.ai_chan = nidaqmx.Task("ai init")
        self.ao=[]
        self.ai=[]
        self.ao_num=ao_num
        self.ai_num=ai_num
        self.current_output_values=[0 for a in range(ao_num)]
        self.outputting_volts=[True for a in range(ao_num)]
        
        self.sample_rate=10
        self.ao_gain=[1 for a in range(ao_num)]
        self.ai_gain=[1 for a in range(ai_num)]
        self.pause = False
        
        for ao in range(ao_num):
            ao_name = self.address + "/ao" + str(ao)
            self.ao_chan.ao_channels.add_ao_voltage_chan(ao_name)
            self.ao.append(self.device.ao_physical_chans["ao"+str(ao)])
        for ai in range(ai_num):
            ai_name = self.address + "/ai" + str(ai)
            self.ai_chan.ai_channels.add_ai_voltage_chan(ai_name)
            self.ai.append(self.device.ai_physical_chans["ai"+str(ai)])
        
        self.ao_chan.close()
        self.ai_chan.close()
        self.test_task=nidaqmx.Task()
        self.testing=nidaqmx._task_modules.channels.ao_channel.AOChannel(self.test_task,self.address+"/ao1")
        self.testing=nidaqmx._task_modules.ao_channel_collection.
        print(self.testing)
        #self.testing.ao_max(10)
        print(self.testing.ao_max())
        x=nidaqmx.system.storage.persisted_channel.PersistedChannel
        
    def test_init(self):
        writer = nidaqmx.Task("writer")
        reader = nidaqmx.Task("reader")
        writer.ao_voltage_units=10344
        writer.ao_output_type=10322
        reader.ai_voltage_units=10344
        reader.ai_output_type=10322
        writer.ao_channels.add_ao_voltage_chan(self.address+"/ao1")
        reader.ai_channels.add_ai_voltage_chan(self.address+"/ai1")
        
        writer.start()
        reader.start()
        writer.write([1.3,2.4])
        print(reader.read())
        for i in range(5):
            time.sleep(3)
            print(reader.read())

    def set_ao_gain(self, channel, gain):
        if (channel not in range(self.ao_num)):
            return -1
        gain=float(gain)
        if ( gain > 0 and gain < 1000 ):
            self.ao_gain[channel]=gain
        else:
            return -2
        
    def set_ai_gain(self, channel, gain):
        if (channel not in range(self.ai_num)):
            return -1
        gain=float(gain)
        if ( gain > 0 and gain < 1000 ):
            self.ai_gain[channel]=gain
        else:
            return -2
    
    def set_sample_rate(self,rate):
        rate=float(rate)
        if ( rate > 0 and rate < 1000 ):
            self.sample_rate=rate
            return self.sample_rate
        else:
            return -1
        
    def get_output(self, channel=None):
        rets=[]
        if channel==None:
            for c,v in enumerate(self.current_output_values):
                rets.append((c,v,self.outputting_volts[c]))
        else:
            channel = self.get_iterable(channel)
            rets = [(c, self.current_output_values[c], self.outputting_volts[c]) for c in channel]
        return rets
    
    def sweep_voltage(self, time_duration, time_step, chan_in, chan_out, min_v, max_v, v_step):
        writer = nidaqmx.Task("writer")
        reader = nidaqmx.Task("reader")
        writer.ao_voltage_units=10344
        writer.ao_output_type=10322
        reader.ai_voltage_units=10344
        reader.ai_output_type=10322
        writer.ao_channels.add_ao_voltage_chan(self.address+"/ao"+str(chan_out))
        reader.ai_channels.add_ai_voltage_chan(self.address+"/ai"+str(chan_in))
        
        self.outputting_volts[chan_out] = True
        
        writer.start()
        reader.start()
        for v in np.linspace(min_v,max_v,(max_v-min_v)/v_step+1):
            a=writer.write(v)
            b=reader.read()
            self.current_output_values[chan_out]=v
            print((v,b))
            time.pause(self.sample_rate) 
        writer.stop()
        reader.stop()
        writer.close()
        reader.close()
    
    def read_task(self,reader):
        print(reader.read())
        
    def close(self):
        self.ao_chan.close()
        self.ai_chan.close()
        self.device.reset_device()
        
    def get_iterable(x):
        if isinstance(x, collections.Iterable):
            return x
        else:
            return (x,)

def main():        
    test = NIDaq("testdaq", "Dev1", 2, 24)
    #test.test_init()

if __name__ == "__main__":
    main()

