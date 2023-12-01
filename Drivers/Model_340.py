# Model_340.py

from typing import ClassVar, Dict, Any

from qcodes.instrument.group_parameter import GroupParameter, Group
from qcodes.instrument_drivers.Lakeshore.lakeshore_base import LakeshoreBase, BaseOutput, BaseSensorChannel
import qcodes.utils.validators as vals

from typing import Dict, ClassVar, List, Any
import time
from bisect import bisect

import numpy as np

from qcodes import VisaInstrument, InstrumentChannel, ChannelList
from qcodes.instrument.group_parameter import GroupParameter, Group


class Model_340_Channel(InstrumentChannel):
    """
    Class for Lakeshore Temperature Controller Model 340 channels

    Args:
        parent
            instrument instance that this channel belongs to
        name
            name of the channel
        channel
            string identifier of the channel as referenced in commands;
            for example, 'A' or 'B' for Model 340
    """

    # A dictionary of sensor statuses that assigns a string representation of
    # the status to a status bit weighting (e.g. {4: 'VMIX OVL'})
    SENSOR_STATUSES: ClassVar[Dict[int, str]] = {0: 'OK',
                                                 1: 'Invalid Reading',
                                                 16: 'Temp Underrange',
                                                 32: 'Temp Overrange',
                                                 64: 'Sensor Units Zero',
                                                 128: 'Sensor Units Overrange'}

    def __init__(self, parent, name, channel):
        super().__init__(parent, name)

        self._channel = channel  # Channel on the temperature controller

        # Add the various channel parameters
        self.add_parameter('temperature',
                           get_cmd='KRDG? {}'.format(self._channel),
                           get_parser=float,
                           label='Temperature',
                           unit='K')

        self.add_parameter('mode',
                           label='Remote/local control',
                           get_cmd='MODE?',
                           set_cmd='MODE {{mode}}',
                           val_mapping={'local': 1,
                                        'remote': 2,
                                        'remote and locked': 3})

        self.add_parameter('sensor_raw',
                           get_cmd=f'SRDG? {self._channel}',
                           get_parser=float,
                           label='Raw reading',
                           unit='Ohms')

        self.add_parameter('sensor_status',
                           get_cmd=f'RDGST? {self._channel}',
                           get_parser=self._decode_sensor_status,
                           label='Sensor status')

        self.add_parameter('input_curve',
                           label='Input curve',
                           get_cmd=f'INCRV? {self._channel}',
                           set_cmd=f'INCRV {self._channel}, {{input_curve}}',
                           vals=vals.Ints(0, 60))

        # Parameters related to Input Type Parameter Command (INTYPE)
        self.add_parameter('sensor_type',
                           label='Input sensor type',
                           docstring='Specifies input sensor type',
                           val_mapping={'Special': 0,
                                        'Si diode': 1,
                                        'GaAlAs diode': 2,
                                        '100 ohm Pt/250': 3,
                                        '100 ohm Pt/500': 4,
                                        '1000 ohm Pt': 5,
                                        'Rhodium Iron': 6,
                                        'Carbon-glass': 7,
                                        'Cernox': 8,
                                        'RuOx': 9,
                                        'Germanium': 10,
                                        'Capacitor': 11,
                                        'Thermocouple': 12},
                           parameter_class=GroupParameter)

        self.add_parameter('sensor_units',
                           label='Input sensor units',
                           val_mapping={'Special': 0,
                                        'volts': 1,
                                        'ohms': 2},
                           parameter_class=GroupParameter)

        self.add_parameter('sensor_coefficient',
                           label='Input coefficient',
                           val_mapping={'Special': 0,
                                        'negative': 1,
                                        'positive': 2},
                           parameter_class=GroupParameter)

        self.add_parameter('sensor_excitation',
                           label='Input sensor excitation',
                           val_mapping={'Off': 0,
                                        '30 nA': 1,
                                        '100 nA': 2,
                                        '300 nA': 3,
                                        '1 uA': 4,
                                        '3 uA': 5,
                                        '10 uA': 6,
                                        '30 uA': 7,
                                        '100 uA': 8,
                                        '300 uA': 9,
                                        '1 mA': 10,
                                        '10 mV': 11,
                                        '1 mV': 12},
                           parameter_class=GroupParameter)

        self.add_parameter('sensor_range',
                           label='Input sensor range',
                           val_mapping={'Special': 0,
                                        '1 mV': 1,
                                        '2.5 mV': 2,
                                        '5 mV': 3,
                                        '10 mV': 4,
                                        '25 mV': 5,
                                        '50 mV': 6,
                                        '100 mV': 7,
                                        '250 mV': 8,
                                        '500 mV': 9,
                                        '1 V': 10,
                                        '2.5 V': 11,
                                        '5 V': 12,
                                        '7.5 V': 13},
                           parameter_class=GroupParameter)

        self.sensor_group = Group([self.sensor_type, self.sensor_units, self.sensor_coefficient, self.sensor_excitation,
                                   self.sensor_range],
                                  set_cmd=f'INTYPE {self._channel}, '
                                          f'{{sensor_type}}, {{sensor_units}}, {{sensor_coefficient}}, '
                                          f'{{sensor_excitation}}, {{sensor_range}}',
                                  get_cmd=f'INTYPE? {self._channel}')

        self.add_parameter('input_enabled',
                           label='input enabled',
                           val_mapping={False: 0,
                                        True: 1},
                           vals=vals.Bool(),
                           parameter_class=GroupParameter)

        self.add_parameter('input_compensation',
                           label='input compensation',
                           val_mapping={'off': 0,
                                        'on': 1,
                                        'pause': 2},
                           parameter_class=GroupParameter)

        self.input_group = Group([self.input_enabled, self.input_compensation],
                                 set_cmd=f'INSET {self._channel}, {{input_enabled}}, {{input_compensation}}',
                                 get_cmd=f'INSET? {self._channel}')

    def _decode_sensor_status(self, sum_of_codes: str):
        """
        Parses the sum of status code according to the `SENSOR_STATUSES` using
        an algorithm defined in `_get_sum_terms` method.

        Args:
            sum_of_codes
                sum of status codes, it is an integer value in the form of a
                string (e.g. "32"), as returned by the corresponding
                instrument command
        """
        codes = self._get_sum_terms(list(self.SENSOR_STATUSES.keys()),
                                    int(sum_of_codes))
        return ", ".join([self.SENSOR_STATUSES[k] for k in codes])

    @staticmethod
    def _get_sum_terms(available_terms: List[int], number: int):
        """
        Returns a list of terms which make the given number when summed up

        This method is intended to be used for cases where the given list
        of terms contains powers of 2, which corresponds to status codes
        that an instrument returns. With that said, this method is not
        guaranteed to work for an arbitrary number and an arbitrary list of
        available terms.

        Zeros are treated as a special case. If number is equal to 0,
        then [0] is returned as a list of terms. Moreover, the function
        assumes that the list of available terms contains 0 because this
        is a usually the default status code for success.

        Example:
        >>> terms = [1, 16, 32, 64, 128]
        >>> get_sum_terms(terms, 96)
        ... [64, 32]  # This is correct because 96=64+32
        """
        terms_in_number: List[int] = []

        # Sort the list of available_terms from largest to smallest
        terms_left = np.sort(available_terms)[::-1]

        # Get rid of the terms that are bigger than the number because they
        # will obviously will not make it to the returned list; and also get
        # rid of '0' as it will make the loop below infinite
        terms_left = np.array(
            [term for term in terms_left if term <= number and term != 0])

        # Handle the special case of number being 0
        if number == 0:
            terms_left = np.empty(0)
            terms_in_number = [0]

        # Keep subtracting the largest term from `number`, and always update
        # the list of available_terms so that they are always smaller than
        # the current value of `number`, until there are no more available_terms
        # to subtract
        while len(terms_left) > 0:
            term = terms_left[0]
            number -= term
            terms_in_number.append(term)
            terms_left = terms_left[terms_left <= number]

        return terms_in_number


class Loop_340(InstrumentChannel):
    """
    Base class for the outputs of Lakeshore temperature controllers

    Args:
        parent
            instrument that this channel belongs to
        output_name
            name of this loop
        self._loop
            identifier for this output that is used in VISA commands of the
            instrument
        has_pid
            if True, then the output supports closed loop control,
            hence it will have three parameters to set it up: 'P', 'I', and 'D'
    """

    MODES: ClassVar[Dict[str, int]] = {
        'Manual PID': 1,
        'Zone': 2,
        'Open Loop': 3,
        'AutoTune PID': 4,
        'AutoTune PI': 5,
        'AutoTune P': 6}

    RANGES: ClassVar[Dict[str, int]] = {
        'off': 0,
        'low': 1,
        'medium': 2,
        'high': 3}

    def __init__(self, parent, output_name, loop, has_pid: bool = True) \
            -> None:
        super().__init__(parent, output_name)

        self.INVERSE_RANGES: Dict[int, str] = {
            v: k for k, v in self.RANGES.items()}

        self._has_pid = has_pid
        self._loop = loop

        self.add_parameter('mode',
                           label='Control mode',
                           docstring='Specifies the control mode',
                           val_mapping=self.MODES,
                           set_cmd=f'CMODE {self._loop} {{}}',
                           get_cmd=f'CMODE? {self._loop}')

        self.add_parameter('input_channel',
                           label='Input channel',
                           docstring='Specifies which measurement input to '
                                     'control from (note that only '
                                     'measurement inputs are available)',
                           parameter_class=GroupParameter)

        self.add_parameter('units',
                           label='Setpoint units',
                           val_mapping={'kelvin': 1, 'celsius': 2, 'sensor units': 3},
                           parameter_class=GroupParameter)

        self.add_parameter('current_or_power',
                           label='output unit',
                           docstring='Specifies whether output displays in current or power.',
                           val_mapping={'current': 1, 'power': 2},
                           parameter_class=GroupParameter)

        self.add_parameter('enabled',
                           label='Control loop on/off',
                           docstring='Specifies whether the control loop is on or off.',
                           val_mapping={'on': 0, 'off': 1},
                           parameter_class=GroupParameter)

        self.add_parameter('powerup_enable',
                           label='Power-up enable on/off',
                           docstring='Specifies whether the output remains on '
                                     'or shuts off after power cycle.',
                           val_mapping={True: 1, False: 0},
                           parameter_class=GroupParameter)

        self.output_group = Group([self.input_channel, self.units,
                                   self.enabled, self.powerup_enable],
                                  set_cmd=f'CSET {self._loop}, {{input_channel}}, '
                                          f'{{units}}, '
                                          f'{{enabled}},'
                                          f'{{powerup_enable}}',
                                  get_cmd=f'CSET? {self._loop}')

        # Parameters for Closed Loop PID Parameter Command
        if self._has_pid:
            self.add_parameter('P',
                               label='P',
                               docstring='The value for closed control loop '
                                         'Proportional (gain)',
                               vals=vals.Numbers(0, 1000),
                               get_parser=float,
                               parameter_class=GroupParameter)
            self.add_parameter('I',
                               label='I',
                               docstring='The value for closed control loop '
                                         'Integral (reset)',
                               vals=vals.Numbers(0, 1000),
                               get_parser=float,
                               parameter_class=GroupParameter)
            self.add_parameter('D',
                               label='D',
                               docstring='The value for closed control loop '
                                         'Derivative (rate)',
                               vals=vals.Numbers(0, 1000),
                               get_parser=float,
                               parameter_class=GroupParameter)
            self.pid_group = Group([self.P, self.I, self.D],
                                   set_cmd=f'PID {self._loop}, '
                                           f'{{P}}, {{I}}, {{D}}',
                                   get_cmd=f'PID? {self._loop}')

        self.add_parameter('output_range',
                           label='Heater range',
                           docstring='Specifies heater output range. The range '
                                     'setting has no effect if an output is in '
                                     'the `Off` mode, and does not apply to '
                                     'an output in `Monitor Out` mode. '
                                     'An output in `Monitor Out` mode is '
                                     'always on.',
                           set_cmd=f'RANGE {{}}',
                           get_cmd=f'RANGE?')

        self.add_parameter('output',
                           label='Output',
                           unit='% of heater range',
                           docstring='Specifies heater output in percent of '
                                     'the current heater output range.\n'
                                     'Note that when the heater is off, '
                                     'this parameter will return the value of 0.005.',
                           get_parser=float,
                           get_cmd=f'HTR?',
                           set_cmd=False)

        self.add_parameter('setpoint',
                           label='Setpoint value (in sensor units)',
                           docstring='The value of the setpoint in the '
                                     'preferred units of the control loop '
                                     'sensor (which is set via '
                                     '`input_channel` parameter)',
                           vals=vals.Numbers(0, 400),
                           get_parser=float,
                           set_cmd=f'SETP {self._loop}, {{}}',
                           get_cmd=f'SETP? {self._loop}')

        # Additional non-Visa parameters

        self.add_parameter('range_limits',
                           set_cmd=None,
                           get_cmd=None,
                           vals=vals.Sequence(vals.Numbers(0, 400),
                                              require_sorted=True,
                                              length=len(self.RANGES) - 1),
                           label='Temperature limits for output ranges',
                           unit='K',
                           docstring='Use this parameter to define which '
                                     'temperature corresponds to which output '
                                     'range; then use the '
                                     '`set_range_from_temperature` method to '
                                     'set the output range via temperature '
                                     'instead of doing it directly')

        self.add_parameter('wait_cycle_time',
                           set_cmd=None,
                           get_cmd=None,
                           vals=vals.Numbers(0, 100),
                           label='Waiting cycle time',
                           docstring='Time between two readings when waiting '
                                     'for temperature to equilibrate',
                           unit='s')
        self.wait_cycle_time(0.1)

        self.add_parameter('wait_tolerance',
                           set_cmd=None,
                           get_cmd=None,
                           vals=vals.Numbers(0, 100),
                           label='Waiting tolerance',
                           docstring='Acceptable tolerance when waiting for '
                                     'temperature to equilibrate',
                           unit='')
        self.wait_tolerance(0.1)

        self.add_parameter('wait_equilibration_time',
                           set_cmd=None,
                           get_cmd=None,
                           vals=vals.Numbers(0, 100),
                           label='Waiting equilibration time',
                           docstring='Duration during which temperature has to '
                                     'be within tolerance',
                           unit='s')
        self.wait_equilibration_time(0.5)

        self.add_parameter('blocking_t',
                           label='Setpoint value with blocking until it is '
                                 'reached',
                           docstring='Sets the setpoint value, and input '
                                     'range, and waits until it is reached. '
                                     'Added for compatibility with Loop. Note '
                                     'that if the setpoint value is in '
                                     'a different range, this function may '
                                     'wait forever because that setpoint '
                                     'cannot be reached within the current '
                                     'range.',
                           vals=vals.Numbers(0, 400),
                           set_cmd=self._set_blocking_t,
                           snapshot_exclude=True)


    def _set_blocking_t(self, temperature):
        self.set_range_from_temperature(temperature)
        self.setpoint(temperature)
        self.wait_until_set_point_reached()

    def set_range_from_temperature(self, temperature: float):
        """
        Sets the output range of this given heater from a given temperature.

        The output range is determined by the limits given through the parameter
        `range_limits`. The output range is used for temperatures between
        the limits `range_limits[i-1]` and `range_limits[i]`; that is
        `range_limits` is the upper limit for using a certain heater current.

        Args:
            temperature
                temperature to set the range from

        Returns:
            the value of the resulting `output_range`, that is also available
            from the `output_range` parameter itself
        """
        if self.range_limits.get_latest() is None:
            raise RuntimeError('Error when calling set_range_from_temperature: '
                               'You must specify the output range limits '
                               'before automatically setting the range '
                               '(e.g. inst.range_limits([0.021, 0.1, 0.2, '
                               '1.1, 2, 4, 8]))')
        range_limits = self.range_limits.get_latest()
        i = bisect(range_limits, temperature)
        # if temperature is larger than the highest range, then bisect returns
        # an index that is +1 from the needed index, hence we need to take
        # care of this corner case here:
        i = min(i, len(range_limits) - 1)
        # there is a `+1` because `self.RANGES` includes `'off'` as the first
        # value.

        orange = self.INVERSE_RANGES[i + 1]  # this is `output range` not the fruit
        self.log.debug(f'setting output range from temperature '
                       f'({temperature} K) to {orange}.')
        self.output_range(orange)
        return self.output_range()

    def set_setpoint_and_range(self, temperature: float):
        """
        Sets the range from the given temperature, and then sets the setpoint
        to this given temperature.

        Note that the preferred units of the heater output are expected to be
        kelvin.

        Args:
            temperature
                temperature in K
        """
        self.set_range_from_temperature(temperature)
        self.setpoint(temperature)

    def wait_until_set_point_reached(self,
                                     wait_cycle_time: float = None,
                                     wait_tolerance: float = None,
                                     wait_equilibration_time: float = None):
        """
        This function runs a loop that monitors the value of the heater's
        input channel until the read values is close to the setpoint value
        that has been set before.

        Note that if the setpoint value is in a different range,
        this function may wait forever because that setpoint cannot be
        reached within the current range.

        Args:
            wait_cycle_time
                this time is being waited between the readings (same as
                `wait_cycle_time` parameter); if None, then the value of the
                corresponding `wait_cycle_time` parameter is used
            wait_tolerance
                this value is used to determine if the reading value is
                close enough to the setpoint value according to the
                following formula:
                `abs(t_reading - t_setpoint)/t_reading < wait_tolerance`
                (same as `wait_tolerance` parameter); if None, then the
                value of the corresponding `wait_tolerance` parameter is used
            wait_equilibration_time:
                within this time, the reading value has to stay within the
                defined tolerance in order for this function to return (same as
                `wait_equilibration_time` parameter); if None, then the value
                of the corresponding `wait_equilibration_time` parameter is used
        """
        wait_cycle_time = wait_cycle_time or self.wait_cycle_time.get_latest()
        tolerance = wait_tolerance or self.wait_tolerance.get_latest()
        equilibration_time = (wait_equilibration_time or
                              self.wait_equilibration_time.get_latest())

        active_channel_id = self.input_channel()
        active_channel_name_on_instrument = (self.root_instrument
            .input_channel_parameter_values_to_channel_name_on_instrument[active_channel_id])
        active_channel = getattr(self.root_instrument, active_channel_name_on_instrument)

        if active_channel.units() != 'kelvin':
            raise ValueError(f"Waiting until the setpoint is reached requires "
                             f"channel's {active_channel._channel!r} units to "
                             f"be set to 'kelvin'.")

        t_setpoint = self.setpoint()

        time_now = time.perf_counter()
        time_enter_tolerance_zone = time_now

        while time_now - time_enter_tolerance_zone < equilibration_time:
            time_now = time.perf_counter()

            t_reading = active_channel.temperature()

            if abs(t_reading - t_setpoint) / t_reading > tolerance:
                # Reset time_enter_tolerance_zone to time_now because we left
                # the tolerance zone here (if we even were inside one)
                time_enter_tolerance_zone = time_now

            time.sleep(wait_cycle_time)


class Model_340(LakeshoreBase):
    """
    Lakeshore Model 340 Temperature Controller Driver
    """
    channel_name_command: Dict[str, str] = {'A': 'A', 'B': 'B'}

    CHANNEL_CLASS = Model_340_Channel

    input_channel_parameter_values_to_channel_name_on_instrument = \
        channel_name_command

    def __init__(self, name: str, address: str, **kwargs) -> None:
        super().__init__(name, address, **kwargs)

        self.loop_1 = Loop_340(self, 'loop_1', 1)
        self.loop_2 = Loop_340(self, 'loop_2', 2)
        self.add_submodule('loop_1', self.loop_1)
        self.add_submodule('loop_2', self.loop_2)
