# daq_driver.py

import nidaqmx
import time
from qcodes import (Instrument, validators as vals)
from qcodes.instrument.channel import InstrumentChannel
from nidaqmx._base_interpreter import BaseInterpreter

class Daq(Instrument):
    """
    QCoDeS instrument driver for the National Instruments DAQ. 
    
    Attributes
    ---------
    name:
        The user-defined name for the instrument.
    address:
        The equipment address of the device, most commonly 'Dev1'.
    device:
        Connects the provided equipment address to the proper device in the
        NIDAQ system.
    ao_num:
        The number of AO channels.
    ai_num:
        The number of AI channels.
    max_out:
        The maximum voltage the device can produce.
    min_out:
        The minimum voltage the device can produce.
    max_in:
        The maximum voltage the device can receive.
    min_in:
        The minimum voltage the device can receive.
    """

    def __init__(self, name="Daq", address=""):
        """
        Initialization for the DAQ driver. 
        
        Takes in the machine given device address (typically "Dev1"), and a user-defined
        name. Creates QCoDeS Parameters for each of the I/O channels.
        """

        start_time = time.time()
        # Initialize the DAQ system
        super().__init__(name)
        self.system = nidaqmx.system.System.local()
        self._address = address
        try:
            self.device = self.system.devices[self._address]
            # Grab the number of AO, AI channels
            self.ao_num = len(self.device.ao_physical_chans.channel_names)
            self.ai_num = len(self.device.ai_physical_chans.channel_names)
        except nidaqmx.errors.DaqError as e:
            self.close()
            raise e
        self._interpreter = BaseInterpreter
        # Read the max/min output/input voltages
        self.max_out = max(self.device.ao_voltage_rngs)
        self.min_out = min(self.device.ao_voltage_rngs)
        self.max_in = max(self.device.ai_voltage_rngs)
        self.min_in = min(self.device.ai_voltage_rngs)

        # For each output channel, create a corresponding DaqAOChannel object
        # If the device is already in use, system will throw a 'DaqError'. If so,
        # let's catch it and close the device, removing the instance from qcodes,
        # then throw the error.
        try:
            for a in range(self.ao_num):
                ch_name = 'ao' + str(a)
                channel = DaqAOChannel(self, self.device, self._address, ch_name, self.min_out, self.max_out,
                                       self.min_in, self.max_in)
                self.add_submodule(ch_name, channel)
            # Similarly, create a DaqAIChannel object for each (real) input channel
            count = 0
            for b in range(self.ai_num):
                # NI DAQs can use each of the coax pins as analog inputs separately, and
                # numbers them as such. (AI0-7 is voltage-part of coax reading for first
                # 8 pins, 8-15 is ground reading of coax for first 8 pins).
                # We don't want this behavior, we use each port as one input (ground and
                # voltage), so we make sure to only grab the "real" analog inputs

                if int(b / 8) % 2 == 0:
                    ch_name = 'ai' + str(b)
                    channel = DaqAIChannel(self, self.device, self._address, ch_name, self.min_in, self.max_in)
                    self.add_submodule(ch_name, channel)
                    count += 1
            # Update the actual number of ai ports
            self.ai_num = count
        except nidaqmx.errors.DaqError as e:
            self.close()
            raise e

        self.connect_message()

    def get_idn(self):
        vendor = 'National Instruments'
        model = f'DAQ {self.device.product_type}'
        serial = self.device.dev_serial_num
        firmware = '.'.join([str(x) for x in self.system.driver_version])

        return dict(zip(('vendor', 'model', 'serial', 'firmware'), [vendor, model, serial, firmware]))

    def get_ao_num(self):
        """
        Returns the number of AO ports available.
        """
        
        return self.ao_num

    def get_ai_num(self):
        """
        Returns the number of AI ports available.
        """
        
        return self.ai_num

    def update_all_inputs(self):
        """
        Updates all the AI channel voltage values.
        """
        
        for chan_name in self.submodules:
            self.submodules[chan_name].get("voltage")

    def snapshot_base(self, update=False,
                      params_to_skip_update=None):
        """
        QCoDeS method to obstain the state of the instrument as a 
        JSON-compatible dictionary. 
        
        Supported by the custom JSON encoder class: 
        qcodes.utils.helpers.NumpyJSONEncoder
       
        Parameters
        ---------
        update: 
            If True, update the state by querying the instrument. 
            If None, only update if the state is known to be invalid. 
            If False, use the latest values in memory and do not update.
        params_to_skip_update: 
            List of parameter names that will be skipped in update even if
            update is True. This is useful if you have parameters that are 
            slow to update but can be updated in a different way (as in the qdac). 
            If you want to skip the update of certain parameters in all snapshots, 
            use the `snapshot_get` attribute of those parameters instead.
        
        Returns
        ---------
            Dictionary containing snapshot of information on base instrument
        """
        
        snap = super().snapshot_base(update=update,
                                     params_to_skip_update=params_to_skip_update)
        snap['address'] = self._address

        return snap

    def close(self):
        """
        Stops the QCoDeS instrument frees its resources.
        
        Closes all subclasses which may have other resources to close;
        writes the object configuration in the desired filepath.
        """
        
        if hasattr(self, 'submodules'):
            for a, c in self.submodules.items():
                c.close()

        super().close()

    def __del__(self):
        """
        Destructor method to close program. 
        
        Necessary for the nidaqmx library to avoid issues upon
        relaunching the software.
        """
        
        try:
            self.close()
        except Exception as e:
            print('Driver couldn\'t close properly.')
            print(e)

        try:
            for a, c in self.submodules.items():
                # Removes all Task objects from the channels, so system doesn't complain
                c.__del__()
        except:
            pass

        # Makes sure the Instrument destructor is called
        super().__del__()


class DaqAOChannel(InstrumentChannel):
    """
    Child class to represent AO channels for DAQ.
    
    Defines utility functions for each Parameter. Channels are created
    when DAQ Instrument is initialized.
    
    Attributes
    ---------
    parent:
        QCoDeS parent instrument, in this case the DAQ.
    device:
        Device address of the machine.
    address:
        Unique address used to connect to DAQ instrument.
    channel:
        Channel name for individual AO channels.
    my_name:
        Stores individual channel names.
    fullname:
        Device address combined with channel name.
    """
    
    def __init__(self, parent: Instrument, device, address, channel, min_output, max_output, min_in, max_in):
        """
        Initialization for the DAQ output channels. 
        
        Saves information about the DAQ, creates and initializes
        the QCoDeS values.
        """
        # Saves the information about the DAQ this channel belongs to
        super().__init__(parent, channel)
        self.device = device
        self.address = address
        self.channel = channel
        # Name, e.g. ao1
        self.my_name = str(channel)
        # Full name, e.g. Dev1/ao1
        self.fullname = self.address + "/" + self.my_name

        # Extrema
        self.max_V = max_output
        self.min_V = min_output
        self.min_in = min_in
        self.max_in = max_in

        self.write_task = None
        self.read_task = None
        self.channel = None
        self.channel_handle = None
        self.create_tasks()

        # Initializes the values of the Parameters
        self.gain = 1
        self._voltage = self.get_voltage()
        self.impedance = None
        self._value = 0

        # Add a Parameter for the output gain, set the unit to 'V/V' as default
        #self.add_parameter('gain_factor',
        #                    get_cmd=self.get_gain_factor,
        #                    set_cmd=self.set_gain_factor,
        #                    label=f'{self.my_name} Gain factor',
        #                    unit='V/V'
        #                    )

        # Create the Parameter for the units of gain
        #self.add_parameter('gain_units',
        #                   set_cmd=self.set_gain_units,
        #                   label=f'{self.my_name} Gain units',
        #                   )

        # Add a Parameter for the output impedance
        #self.add_parameter('impedance',
        #                   get_cmd=self.get_load_impedance,
        #                   get_parser=float,
        #                   set_cmd=self.set_load_impedance,
        #                   label=f'{self.my_name} Load Impedance',
        #                   vals=vals.Numbers(0, 1000)
        #                   )

        # Add a Parameter for the value
        #self.add_parameter('value',
        #                   get_cmd=self.get_value,
        #                   set_cmd=self.set_value,
        #                   label='Voltage * Factor'
        #                   )

        # Add a Parameter for the voltage
        self.add_parameter('voltage',
                           get_cmd=self.get_voltage,
                           get_parser=float,
                           set_cmd=self.set_voltage,
                           label=f'{self.my_name} Voltage',
                           unit='V',
                           vals=vals.Numbers(self.min_V, self.max_V)
                           )
        
    def get_gain_factor(self):
        """
        Returns the gain value and the unit conversion (e.g., mA/V) as a tuple.
        """
        
        return (self.gain, self.parameters["gain factor"].unit)

    def set_gain_factor(self, _gain):
        """
        Sets the gain value.
        
        Parameters
        ---------
        _gain: 
            Value to be set as gain attribute.
        """
        
        self.gain = _gain

    #        if self.channel != None:
    #            self.channel.ai_gain=_gain

    def set_gain_units(self, units):
        """
        Sets the gain unit conversion (e.g., uV/V).
        
        Parameters
        ---------
        units:
            Value of desired final units of gain.
            Default unit is the Volt. 
        """
        
        self.parameters["gain factor"].unit = units

    def get_voltage(self):
        """
        Returns the current output voltage.
        """
        
        if self.read_task is not None:
            self._voltage = self.read_task.read()

        return self._voltage

    def set_voltage(self, _voltage):
        """
        Sets the voltage to the desired value.
        """
        
        if self.write_task is not None:
            self.write_task.write(_voltage)

            self._voltage = _voltage

    def get_value(self):
        """
        Calculates, sets, and returns the value after the gain.
        
        Returns
        ---------
            Product of gain and voltage with associated units.
        """
        
        parts = self.parameters["gain factor"].unit.split("/")
        self.parameters["value"].unit = parts[0]
        self._value = self.gain * self.get_voltage()
        return (self._value, self.parameters["value"].unit)

    def set_value(self, value):
        """
        Sets the voltage to the appropriate value after considering the gain.
        
        Parameters
        ---------
        value:
            The product of voltage and gain.
        """
        
        self._value = value
        self.set_voltage(self._value / self.gain)

    def get_load_impedance(self):
        """
        Returns the load impedance.
        """
        
        return self.impedance

    def set_load_impedance(self, _imp):
        """
        Sets the load impedance.
        """
        
        self.impedance = _imp

    #        if self.channel != None:
    #            self.channel.ao_load_impedance=_imp

    def create_tasks(self):
        """
        Defines the tasks that should be used to conduct reads and writes to the port.
        """
        
        if self.write_task is not None or self.read_task is not None:
            self.clear_task()

        # We now create a task to read and write on each channel
        self.write_task = nidaqmx.Task(f"writing {self.address}_{self.my_name}")
        self.read_task = nidaqmx.Task(f"reading {self.address}_{self.my_name}")

        # Add the channel to the task
        self.write_task.ao_channels.add_ao_voltage_chan(self.fullname)
        self.read_task.ai_channels.add_ai_voltage_chan(f"{self.address}/_{self.my_name}_vs_aognd",
                                                  min_val=self.min_in, max_val=self.max_in)

        # Channel handler that can be used to communicate things like gain, impedance
        # back to the DAQ
        self.channel_handle = nidaqmx._task_modules.channels.ao_channel.AOChannel(self.write_task._handle, self.channel,BaseInterpreter)

    #        if self.gain != -1:
    #            task.ao_channels.ao_gain=self.gain
    #        if self.impedance != -1:
    #            task.ao_load_impedance=self.impedance

    def clear_task(self):
        """
        Clears the current task object for resource maintenance.
        """
        
        if self.read_task is not None:
            self.read_task.close()
        if self.write_task is not None:
            self.write_task.close()
        self.read_task = None
        self.write_task = None
        self.channel_handle = None

    def close(self):
        """
        Destructor, makes sure task is clean.
        """

        self.clear_task()


class DaqAIChannel(InstrumentChannel):
    """
    Child class to represent AO channels for DAQ.
    
    Defines utility functions for each Parameter. Channels are created
    when DAQ Instrument is initialized.
    
    Attributes
    ---------
    parent:
        QCoDeS parent instrument, in this case the DAQ.
    device:
        Device address of the machine.
    address:
        Unique address used to connect to DAQ instrument.
    channel:
        Channel name for individual AI channels.
    my_name:
        Stores individual channel names.
    fullname:
        Device address combined with channel name.
    """

    def __init__(self, parent: Instrument, device, address, channel, min_input, max_input):
        """
        Initialization for DAQ input channels. 
        
        Saves information about the DAQ, creates and initializes
        the QCoDeS values.
        """
        # Saves the information about the DAQ this channel belongs to
        super().__init__(parent, channel)
        self.device = device
        self.address = address
        self.channel = channel
        self.my_name = str(channel)
        self.fullname = self.address + "/" + self.my_name

        # Set our maximum input/output
        self.max_in = max_input
        self.min_in = min_input

        self.task = None
        self.channel = None
        self.channel_handle = None
        self.create_task()

        # Set the default Parameter values
        self.gain = 1
        self._voltage = self.get_voltage()
        self.impedance = None
        self._value = 0



        # Create the Parameter for gain, with default unit 'V/V'
        #self.add_parameter('gain_factor',
        #                    get_cmd=self.get_gain_factor,
        #                    set_cmd=self.set_gain_factor,
        #                    label=f'{self.my_name} gain',
        #                    unit='V/V'
        #                    )

        # Create the Parameter for the units of gain
        #self.add_parameter('gain_units',
        #                   set_cmd=self.set_gain_units,
        #                   label=f'{self.my_name} gain units',
        #                   )

        # Create the Parameter for impedance
        #self.add_parameter('impedance',
        #                   get_cmd=self.get_load_impedance,
        #                   get_parser=float,
        #                   set_cmd=self.set_load_impedance,
        #                   label=f'{self.my_name} Load Impedance',
        #                   vals=vals.Numbers(0, 1000)
        #                   )

        # Create the Parameter for value, which is the voltage * gain
        #self.add_parameter('value',
        #                   get_cmd=self.get_value,
        #                   label='Voltage * Factor')

        # Create the Parameter for input voltage
        self.add_parameter('voltage',
                           get_cmd=self.get_voltage,
                           get_parser=float,
                           label=f'{self.my_name} Voltage',
                           unit='V',
                           vals=vals.Numbers(self.min_in, self.max_in)
                           )
        
    def get_gain_factor(self):
        """
        Returns the gain factor unit conversion.
        """
        
        return (self.gain, self.parameters["gain factor"].unit)

    def set_gain_factor(self, _gain):
        """
        Sets the gain factor value.
        
        Parameters
        ---------
            _gain:
                Value to be set as gain attribute.
        """
        
        self.gain = _gain
    #        if self.channel != None:
    #            self.channel.ai_gain=_gain

    def set_gain_units(self, units):
        """
        Sets the gain unit conversion (e.g., uV/V).
        
        Parameters
        ---------
        units:
            Value of desired final units of gain.
            Default unit is the Volt. 
        """
        
        self.parameters["gain"].unit = units

    def get_voltage(self):
        """
        Returns the current input voltage.
        """
        
        if self.task is not None:
            self._voltage = self.task.read()
        return self._voltage

    def get_value(self):
        """
        Calculates, sets, and returns the value after the gain.
        
        Returns
        ---------
            Product of gain and voltage with associated units.
        """
        parts = self.parameters["gain factor"].unit.split("/")
        self.parameters["value"].unit = parts[0]
        self._value = self.gain * self.get_voltage()
        return (self._value, self.parameters["value"].unit)

    def get_load_impedance(self):
        """
        Returns the load impedance.
        """
        
        return self.impedance

    def set_load_impedance(self, _imp):
        """
        Sets the load impedance.
        """
        
        self.impedance = _imp
    #        if self.channel != None:
    #            self.channel.ai_load_impedance=_imp

    def create_task(self):
        """
        Defines the task that should be used to conduct reads from the port.

        """
        
        if self.task is not None:
            self.clear_task()

        self.task = nidaqmx.Task(f"reading {self.address}_{self.my_name}")

        # Add the channel to the task
        self.task.ai_channels.add_ai_voltage_chan(self.fullname, min_val=self.min_in, max_val=self.max_in)

        # Channel handler that can be used to communicate things like gain, impedance
        # back to the DAQ
        self.channel_handle = nidaqmx._task_modules.channels.ai_channel.AIChannel(self.task._handle, self.channel,BaseInterpreter)
        #        if self.gain != -1:
        #            task.ai_channels.ai_gain=self.gain
        #        if self.impedance != -1:
        #            task.ai_load_impedance=self.impedance

    def clear_task(self):
        """
        Utility function to clear the task object for resource maintenance.
        """
        
        if self.task is not None:
            self.task.close()
        self.task = None
        self.channel_handle = None

    def close(self):
        """
        Destructor, makes sure task is clean.
        """

        self.clear_task()
