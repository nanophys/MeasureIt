# daq_driver.py

import nidaqmx, time, os
from configparser import ConfigParser
from qcodes import (Instrument, validators as vals)
from qcodes.instrument.channel import InstrumentChannel

class Daq(Instrument):
    """
    QCoDeS instrument driver for the National Instruments DAQ. Defines Parameters for each of the I/O channels.
    """
    def __init__(self, address="", name="Daq"):
        """
        Initialization for the DAQ driver. Takes in the machine given device address (typically "Dev1"), a user-defined
        name, and the number of ao and ai ports. Creates QCoDeS Parameters for each of the io channels.
        """
        
        # Initialize the DAQ system
        super().__init__(address)
        system = nidaqmx.system.System.local()
        self.name=address
        self.device = system.devices[self.name]
        # Grab the number of AO, AI channels
        self.ao_num = len(self.device.ao_physical_chans.channel_names)
        self.ai_num = len(self.device.ai_physical_chans.channel_names)
        
        # Read the config file
        self.cfg_fp = os.getenv('MeasureItHome') + '\\cfg\\daq_output.cfg'
        self.cfg_obj = ConfigParser()
        self.cfg_obj.read(self.cfg_fp)
        self.cfg_output = self.cfg_obj['OUTPUT']
        
        # For each output channel, create a corresponding DaqAOChannel object
        for a in range(self.ao_num):
            ch_name = 'ao'+str(a)
            channel = DaqAOChannel(self, self.device, self.name, ch_name)
            self.add_submodule(ch_name, channel)
            # We now automatically create a task to write on each channel (NECESSARY!)
            task=nidaqmx.Task("writing " + ch_name)
            channel.add_self_to_task(task)
        # Similarly, create a DaqAIChannel object for each (real) input channel
        for b in range(self.ai_num):
            # NI DAQs can use each of the coax pins as analog inputs separately, and
            # numbers them as such. (AI0-7 is voltage-part of coax reading for first 
            # 8 pins, 8-15 is ground reading of coax for first 8 pins).
            # We don't want this behavior, we use each port as one input (ground and 
            # voltage), so we make sure to only grab the "real" analog inputs
            count = 0
            if int(b/8)%2 == 0:
                ch_name = 'ai'+str(b)
                channel = DaqAIChannel(self, self.device, self.name, ch_name)
                self.add_submodule(ch_name, channel)
                task=nidaqmx.Task("reading " + ch_name)
                channel.add_self_to_task(task)
                count += 1
            # Update the actual number of ai ports
            self.ai_num = count
        
             
    def get_ao_num(self):
        """
        Utility function to retrieve the number of AO ports available.
        """
        return self.ao_num
    
    def get_ai_num(self):
        """
        Utility function to retrieve the number of AI ports available.
        """
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
                c.__del__()
        except:
            pass
        
        # Makes sure the Instrument destructor is called
        super().__del__()
        
        
class DaqAOChannel(InstrumentChannel):
    """
    Channel object representing AO channels. Defines the relevant Parameters:
        voltage, gain, impedance, and value (the multiplication of voltage and gain)
    Defines utility functions for each Parameter.
    """
    def get_gain_factor(self):
        """
        Returns the gain value and the unit conversion (e.g., mA/V) as a tuple.
        """
        return (self.gain, self.parameters["gain factor"].unit)
    
    def set_gain_factor(self, _gain):
        """
        Sets the gain value and the unit conversion (e.g., uV/V).
        Arguments:
            _gain = value
        """
        self.gain = _gain
#        if self.channel != None:
#            self.channel.ai_gain=_gain
        
    def set_gain_units(self, units):
        """
        Sets the gain unit conversion (e.g., uV/V).
        Arguments:
            units = string for characters
        """
        self.parameters["gain factor"].unit=units
        
    def get_voltage(self):
        """
        Returns the current output voltage.
        """
        self._voltage=float(self.cfg_output[self.name])
        return self._voltage
        
    def set_voltage(self, _voltage):
        """
        Sets the voltage to the value passed as '_voltage'
        """
        if self.task != None:
            self.task.write(_voltage)
            self.cfg_output[self.name]=str(_voltage)
            with open(self.parent.cfg_fp, 'w') as conf:
                self.parent.cfg_obj.write(conf)
            
            self._voltage=_voltage
       
    def get_value(self):
        """
        This function calculates, sets, and returns the value after the gain.
        Returns:
            ( value, unit )
        """
        parts = self.parameters["gain factor"].unit.split("/")
        self.parameters["value"].unit=parts[0]
        self._value = self.gain * self.get_voltage()
        return (self._value, self.parameters["value"].unit)
    
    def set_value(self, value):
        """
        Sets the voltage to the appropriate value, given the gain.
        """
        self._value = value
        self.set_voltage(self._value/self.gain)
        
    def get_load_impedance(self):
        """
        Returns the impedance
        """
        return self.impedance
    
    def set_load_impedance(self, _imp):
        """
        Sets the impedance
        """
        self.impedance = _imp
#        if self.channel != None:
#            self.channel.ao_load_impedance=_imp
        
    def __init__(self, parent: Instrument, device, address, channel):
        """
        Initialization function. Saves information about the DAQ, creates and initializes
        the QCoDeS values.
        """
        # Saves the information about the DAQ this channel belongs to
        super().__init__(parent, channel)
        self.device=device
        self.address=address
        self.channel=channel
        # Name, e.g. ao1
        self.name=str(channel)
        # Full name, e.g. Dev1/ao1
        self.fullname=self.address+"/"+self.name
        
        # Initializes the values of the Parameters
        self.gain=1
        self._voltage=float(self.cfg_output[self.name])
        self.impedance=None
        self._value=0
        
        self.task=None
        self.channel=None
        
        # Add a Parameter for the output gain, set the unit to 'V/V' as default
        self.add_parameter('gain_factor',
                           get_cmd=self.get_gain_factor,
                           set_cmd=self.set_gain_factor,
                           label=f'{self.name} Gain factor',
                           unit='V/V'
                           )
        
        # Create the Parameter for the units of gain
        self.add_parameter('gain_units',
                           set_cmd=self.set_gain_units,
                           label=f'{self.name} Gain units',
                           )
        
        # Add a Parameter for the output impedance
        self.add_parameter('impedance',
                           get_cmd=self.get_load_impedance,
                           get_parser=float,
                           set_cmd=self.set_load_impedance,
                           label=f'{self.name} Load Impedance',
                           vals=vals.Numbers(0,1000)
                           )
        
        # Add a Parameter for the value
        self.add_parameter('value',
                           get_cmd=self.get_value,
                           set_cmd=self.set_value,
                           label='Voltage * Factor'
                           )
        
        # Add a Parameter for the voltage
        self.add_parameter('voltage',
                           get_cmd=self.get_voltage,
                           get_parser=float,
                           set_cmd=self.set_voltage,
                           label=f'{self.name} Voltage',
                           unit='V',
                           val=vals.Numbers(-10,10)
                           )
        
    def add_self_to_task(self, task):
        """
        Utility function to define the task that should be used to conduct writes
        to the port.
        Arguments:
            task - task to be used for writing
        """
        if self.task is not None:
            self.clear_task()
            
        # Add the channel to the task
        task.ao_channels.add_ao_voltage_chan(self.fullname)
        self.task=task
        # Channel handler that can be used to communicate things like gain, impedance
        # back to the DAQ
        self.channel_handle=nidaqmx._task_modules.channels.ao_channel.AOChannel(self.task._handle, self.channel)
#        if self.gain != -1:
#            task.ao_channels.ao_gain=self.gain
#        if self.impedance != -1:
#            task.ao_load_impedance=self.impedance
            
    def clear_task(self):
        """
        Utility function to clean the task object for resource maintenance reasons
        """
        if self.task is not None:
            self.task.close()
        self.task=None
        self.channel_handle=None
        
    def __del__(self):
        """
        Destructor, makes sure task is clean.
        """
        self.clear_task()
    
        
class DaqAIChannel(InstrumentChannel):
    """
    Channel object representing AI channels. Defines the relevant Parameters:
        voltage, gain, impedance, and value (the multiplication of voltage and gain)
    Defines utility functions for each Parameter.
    """
    def get_gain_factor(self):
        """
        Returns the gain value and the unit conversion (e.g., mA/V) as a tuple.
        """
        return (self.gain, self.parameters["gain factor"].unit)
    
    def set_gain_factor(self, _gain):
        """
        Sets the gain value and the unit conversion (e.g., uV/V).
        Arguments:
            _gain = value
        """
        self.gain = _gain
#        if self.channel != None:
#            self.channel.ai_gain=_gain
        
    def set_gain_units(self, units):
        """
        Sets the gain unit conversion (e.g., uV/V).
        Arguments:
            units = string for characters
        """
        self.parameters["gain"].unit=units
        
    def get_voltage(self):
        """
        Returns the current input voltage.
        """
        if self.task != None:
            self._voltage = self.task.read()
        return self._voltage
        
    def get_value(self):
        """
        This function calculates, sets, and returns the value after the gain.
        Returns:
            ( value, unit )
        """
        parts = self.parameters["gain factor"].unit.split("/")
        self.parameters["value"].unit=parts[0]
        self._value = self.gain * self.get_voltage()
        return (self._value, self.parameters["value"].unit)
    
    def get_load_impedance(self):
        """
        Returns the impedance
        """
        return self.impedance
    
    def set_load_impedance(self, _imp):
        """
        Sets the impedance
        """
        self.impedance = _imp
#        if self.channel != None:
#            self.channel.ai_load_impedance=_imp
        
    def __init__(self, parent: Instrument, device, address, channel):
        """
        Initialization function. Saves information about the DAQ, creates and initializes
        the QCoDeS values.
        """
        # Saves the information about the DAQ this channel belongs to
        super().__init__(parent, channel)
        self.device=device
        self.address=address
        self.channel=channel
        self.name=str(channel)
        self.fullname=self.address+"/"+self.name
        
        # Set the default Parameter values
        self.gain=1
        self._voltage=0
        self.impedance=None
        self._value=0
        
        self.task=None
        self.channel=None
        
        # Create the Parameter for gain, with default unit 'V/V'
        self.add_parameter('gain_factor',
                           get_cmd=self.get_gain_factor,
                           set_cmd=self.set_gain_factor,
                           label=f'{self.name} gain',
                           unit='V/V'
                           )
        
        # Create the Parameter for the units of gain
        self.add_parameter('gain_units',
                           set_cmd=self.set_gain_units,
                           label=f'{self.name} gain units',
                           )
        
        # Create the Parameter for impedance
        self.add_parameter('impedance',
                           get_cmd=self.get_load_impedance,
                           get_parser=float,
                           set_cmd=self.set_load_impedance,
                           label=f'{self.name} Load Impedance',
                           vals=vals.Numbers(0,1000)
                           )
        
        # Create the Parameter for value, which is the voltage * gain
        self.add_parameter('value',
                           get_cmd=self.get_value,
                           label='Voltage * Factor')
        
        # Create the Parameter for input voltage
        self.add_parameter('voltage',
                           get_cmd=self.get_voltage,
                           get_parser=float,
                           label=f'{self.name} Voltage',
                           unit='V',
                           vals=vals.Numbers(-10,10)
                           )
        
    def add_self_to_task(self, task):
        """
        Utility function to define the task that should be used to conduct writes
        to the port.
        Arguments:
            task - task to be used for writing
        """
        if self.task is not None:
            self.clear_task()
        
        # Add the channel to the task
        task.ai_channels.add_ai_voltage_chan(self.fullname)
        self.task=task
        # Channel handler that can be used to communicate things like gain, impedance
        # back to the DAQ
        self.channel_handle=nidaqmx._task_modules.channels.ai_channel.AIChannel(self.task._handle, self.channel)
#        if self.gain != -1:
#            task.ai_channels.ai_gain=self.gain
#        if self.impedance != -1:
#            task.ai_load_impedance=self.impedance
        
        return 1
    
    def clear_task(self):
        """
        Utility function to clean the task object for resource maintenance reasons
        """
        if self.task is not None:
            self.task.close()
        self.task=None
        self.channel_handle=None
        
    def __del__(self):
        """
        Destructor, makes sure task is clean.
        """
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
    daq.ao1.set("gain factor",4)
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