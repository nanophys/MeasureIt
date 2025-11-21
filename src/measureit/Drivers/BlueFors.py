# This Python file uses the following encoding: utf-8
# Etienne Dumur <etienne.dumur@gmail.com>, September 2020
# Jiaqi Cai <jiaqic@mit.edu>, Oct., 2025
# HTTP API rewrite inspired by BlueFTC (https://github.com/eliasankerhold/BlueFTC)

import logging
from functools import partial
from random import randint
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import requests
from qcodes.instrument.base import Instrument
from qcodes.utils.validators import Bool, Numbers
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning
from warnings import warn


class PIDConfigException(Exception):
    """Raised when PID configuration setup fails."""


class APIError(Exception):
    """Wrap errors returned by the BlueFors HTTP API."""

    def __init__(self, payload: Dict[str, Any]) -> None:
        error_block = payload.get("error", {})
        details = error_block.get("details")
        if isinstance(details, list) and details:
            messages = [
                f"Code: {entry.get('code')}, Reason: {entry.get('name')}"
                for entry in details
                if isinstance(entry, dict)
            ]
        elif error_block:
            messages = [
                f"Code: {error_block.get('code')}, Reason: {error_block.get('name')}"
            ]
        else:
            messages = ["Unknown BlueFors controller error."]
        description = error_block.get("description", "")
        message = (
            f"{error_block.get('name', 'BlueFors API error')}: "
            f"{description} {' | '.join(messages)}"
        ).strip()
        super().__init__(message)
        self.payload: Dict[str, Any] = payload


class _BlueForsAPIClient:
    """
    Helper that talks to the BlueFors Controller HTTP API.

    The implementation follows the reference BlueFTC driver but is trimmed for
    integration inside a QCoDeS instrument.
    """

    def __init__(
        self,
        host: str,
        api_key: str,
        *,
        port: int = 49098,
        mixing_chamber_channel_id: Optional[int] = None,
        mixing_chamber_heater_id: Optional[int] = None,
        pid_calibration_path: Optional[str] = None,
        enable_maxigauge: bool = False,
        emulate: bool = False,
        verify_ssl: bool = False,
        timeout: float = 5.0,
        auto_pid_calibration: bool = True,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if not host:
            raise PIDConfigException("A valid host/IP address is required.")
        if not api_key:
            raise PIDConfigException(
                "An API key is required to access the BlueFors controller."
            )

        self._base_url = f"https://{host}:{port}"
        self._key = api_key
        self._timeout = timeout
        self._verify_ssl = verify_ssl
        self._session = requests.Session()
        self._maxigauge_pressure = enable_maxigauge
        self._emulate = emulate
        self._auto_pid_calibration = auto_pid_calibration
        self._log = logger or logging.getLogger(__name__)
        self._mixing_chamber_channel_id = mixing_chamber_channel_id
        self._mixing_chamber_heater = (
            f"driver.bftc.data.heaters.heater_{mixing_chamber_heater_id}"
            if mixing_chamber_heater_id is not None
            else None
        )
        self._has_mxc = mixing_chamber_channel_id is not None

        if not verify_ssl:
            disable_warnings(InsecureRequestWarning)

        self._valid_pid_config = False
        self._pid_calib_setpoints: Optional[np.ndarray] = None
        self._pid_calib_pid: Optional[np.ndarray] = None
        if pid_calibration_path is not None:
            self._load_pid_config(pid_calibration_path)

    @staticmethod
    def _device_key(device: str, target: str) -> str:
        return f"{device}.{target}"

    def _value_url(self, device: str, target: str) -> str:
        path = device.replace(".", "/")
        return (
            f"{self._base_url}/values/{path}/{target}/"
            f"?prettyprint=1&key={self._key}"
        )

    def _post_url(self) -> str:
        return f"{self._base_url}/values/?prettyprint=1&key={self._key}"

    def _nan_payload(
        self, device: str, target: str, status: str = "ERROR"
    ) -> Dict[str, Any]:
        key = self._device_key(device, target)
        return {
            "data": {
                key: {
                    "content": {
                        "latest_valid_value": {"value": float("nan"), "status": status}
                    }
                }
            }
        }

    def _mock_value(self, device: str, target: str) -> Dict[str, Any]:
        key = self._device_key(device, target)
        value = randint(1, 100)
        if target in ("active", "pid_mode"):
            mock_value: Any = "1" if value % 2 else "0"
        else:
            mock_value = float(value)
        return {
            "data": {
                key: {
                    "content": {
                        "latest_valid_value": {"value": mock_value, "status": "SYNCHRONIZED"}
                    }
                }
            }
        }

    def _get_value_request(self, device: str, target: str) -> Dict[str, Any]:
        if self._emulate:
            self._log.debug("EMULATE GET %s.%s", device, target)
            return self._mock_value(device, target)

        url = self._value_url(device, target)
        self._log.debug("GET %s", url)
        try:
            response = self._session.get(
                url,
                timeout=self._timeout,
                verify=self._verify_ssl,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as err:
            self._log.error("BlueFors GET %s failed: %s", url, err)
            return self._nan_payload(device, target)

    def _set_value_request(self, device: str, target: str, value: Any) -> None:
        if self._emulate:
            self._log.debug("EMULATE POST %s.%s = %s", device, target, value)
            return

        body = {
            "data": {
                self._device_key(device, target): {"content": {"value": value}}
            }
        }
        url = self._post_url()
        self._log.debug("POST %s payload=%s", url, body)
        response = self._session.post(
            url,
            json=body,
            timeout=self._timeout,
            verify=self._verify_ssl,
        )
        response.raise_for_status()

    def _apply_values_request(self, device: str) -> None:
        if self._emulate:
            self._log.debug("EMULATE APPLY %s", device)
            return

        body = {
            "data": {
                self._device_key(device, "write"): {"content": {"call": 1}}
            }
        }
        url = self._post_url()
        self._log.debug("POST %s payload=%s", url, body)
        response = self._session.post(
            url,
            json=body,
            timeout=self._timeout,
            verify=self._verify_ssl,
        )
        response.raise_for_status()

    def _get_synchronization_status(
        self, data: Dict[str, Any], device: str, target: str
    ) -> str:
        key = self._device_key(device, target)
        try:
            return data["data"][key]["content"]["latest_valid_value"]["status"]
        except KeyError:
            self._log.warning(
                "Could not verify synchronization status for %s.%s",
                device,
                target,
            )
            return "INVALID"

    @staticmethod
    def _handle_status_response(
        status: str, target: str, set_operation: bool = False
    ) -> int:
        info = " while setting value" if set_operation else ""
        if status == "INVALID":
            print(f"Warning{info}: The target '{target}' is invalid.")
            return 0
        if status in ("CHANGED", "SYNCHRONIZED", "INDEPENDENT"):
            return 1
        if status == "DISCONNECTED":
            print(
                f"Warning{info}: Target '{target}' is disconnected on the controller."
            )
            return 0
        if status == "QUEUED":
            print(
                f"Warning{info}: Target '{target}' is queued; verify synchronization."
            )
            return 2
        print(f"Warning{info}: Received invalid status '{status}' for '{target}'.")
        return 0

    def _get_value_from_response(
        self, data: Dict[str, Any], device: str, target: str
    ) -> Any:
        status = self._get_synchronization_status(data, device, target)
        self._handle_status_response(status=status, target=target)
        key = self._device_key(device, target)
        return data["data"][key]["content"]["latest_valid_value"]["value"]

    @staticmethod
    def _device_for_channel(channel: int) -> str:
        return f"mapper.heater_mappings_bftc.device.c{channel}"

    def get_channel_data(self, channel: int, target: str) -> Any:
        device = self._device_for_channel(channel)
        data = self._get_value_request(device, target)
        try:
            return self._get_value_from_response(data, device, target)
        except KeyError as err:
            raise APIError(data) from err

    def get_channel_temperature(self, channel: int) -> float:
        return float(self.get_channel_data(channel, "temperature"))

    def get_channel_resistance(self, channel: int) -> float:
        return float(self.get_channel_data(channel, "resistance"))

    def _ensure_mxc_channel(self) -> int:
        if not self._has_mxc or self._mixing_chamber_channel_id is None:
            raise PIDConfigException("Mixing chamber channel ID not configured.")
        return int(self._mixing_chamber_channel_id)

    def _ensure_mxc_heater(self) -> str:
        if self._mixing_chamber_heater is None:
            raise PIDConfigException("Mixing chamber heater ID not configured.")
        return self._mixing_chamber_heater

    def get_mxc_temperature(self) -> float:
        channel = self._ensure_mxc_channel()
        return self.get_channel_temperature(channel)

    def get_mxc_resistance(self) -> float:
        channel = self._ensure_mxc_channel()
        return self.get_channel_resistance(channel)

    def get_mxc_heater_value(self, target: str) -> Any:
        heater = self._ensure_mxc_heater()
        data = self._get_value_request(heater, target)
        try:
            return self._get_value_from_response(data, heater, target)
        except KeyError as err:
            raise APIError(data) from err

    def check_heater_value_synced(self, target: str) -> bool:
        heater = self._ensure_mxc_heater()
        data = self._get_value_request(heater, target)
        status = self._get_synchronization_status(data, heater, target)
        return bool(
            self._handle_status_response(status, target=target, set_operation=True)
        )

    def set_mxc_heater_value(self, target: str, value: Any) -> bool:
        heater = self._ensure_mxc_heater()
        self._log.info("Mixing chamber heater: setting %s to %s", target, value)
        self._set_value_request(heater, target, value)
        self._apply_values_request(heater)
        synced = self.check_heater_value_synced(target)
        if synced:
            self._log.info("Mixing chamber heater: %s synced", target)
        return synced

    def get_mxc_heater_status(self) -> bool:
        return self.get_mxc_heater_value("active") == "1"

    def set_mxc_heater_status(self, enabled: bool) -> bool:
        new_value = "1" if enabled else "0"
        return self.set_mxc_heater_value("active", new_value)

    def toggle_mxc_heater(self, status: str) -> bool:
        if status not in {"on", "off"}:
            raise PIDConfigException("Status must be 'on' or 'off'.")
        return self.set_mxc_heater_status(status == "on")

    def get_mxc_heater_power(self) -> float:
        return float(self.get_mxc_heater_value("power")) * 1e6

    def set_mxc_heater_power(self, power_uW: float) -> bool:
        if power_uW < 0 or power_uW > 5000:
            raise PIDConfigException(
                "Power should be in the range of 0 to 5000 microwatts."
            )
        return self.set_mxc_heater_value("power", power_uW / 1e6)

    def get_mxc_heater_setpoint(self) -> float:
        return float(self.get_mxc_heater_value("setpoint"))

    def set_mxc_heater_setpoint(
        self, temperature_mK: float, use_pid_calib: Optional[bool] = None
    ) -> bool:
        if temperature_mK >= 1e3:
            raise PIDConfigException(
                f"Mixing chamber setpoint cannot be over 1 K. Requested {temperature_mK} mK."
            )

        apply_pid = (
            self._auto_pid_calibration if use_pid_calib is None else use_pid_calib
        )
        if apply_pid and self._valid_pid_config:
            if self._pid_calib_setpoints is None or self._pid_calib_pid is None:
                warn("PID calibration table not initialized.")
            else:
                temperature_k = temperature_mK * 1e-3
                closest = int(
                    np.argmin(np.abs(self._pid_calib_setpoints - temperature_k))
                )
                target_mk = self._pid_calib_setpoints[closest] * 1e3
                self._log.info(
                    "Using PID calibration closest to %.3f mK.", target_mk
                )
                self.set_mxc_heater_pid_config(*self._pid_calib_pid[closest])
        elif apply_pid and not self._valid_pid_config:
            warn(
                "PID calibration requested but no valid table is available; "
                "using current PID values."
            )

        return self.set_mxc_heater_value("setpoint", temperature_mK)

    def get_mxc_heater_mode(self) -> bool:
        return self.get_mxc_heater_value("pid_mode") == "1"

    def set_mxc_heater_mode(self, enable: bool) -> bool:
        value = "1" if enable else "0"
        return self.set_mxc_heater_value("pid_mode", value)

    def get_mxc_heater_pid_config(self) -> List[float]:
        pid_values: List[float] = []
        for axis in ("p", "i", "d"):
            pid_values.append(float(self.get_mxc_heater_value(f"pid_{axis}")))
        return pid_values

    def set_mxc_heater_pid_config(
        self, p: Optional[float] = None, i: Optional[float] = None, d: Optional[float] = None
    ) -> bool:
        success = True
        for value, axis in zip((p, i, d), ("p", "i", "d")):
            if value is not None:
                success &= self.set_mxc_heater_value(f"pid_{axis}", value)
        return success

    def get_maxigauge_channel(self, channel: int) -> float:
        if not self._maxigauge_pressure:
            raise PIDConfigException(
                "Activate Maxigauge reading to query pressure values."
            )
        device = "driver.maxigauge.pressures"
        target = f"p{channel}"
        data = self._get_value_request(device, target)
        try:
            value = self._get_value_from_response(data, device, target)
            return float(value) * 1e3
        except KeyError as err:
            raise APIError(data) from err

    def _load_pid_config(self, path: str) -> None:
        try:
            pid_config = np.loadtxt(path, dtype="float", delimiter=",", skiprows=1)
        except FileNotFoundError as err:
            warn(
                f"Encountered error while loading PID config '{path}': {err}.\n"
                "Continuing without automatic PID parameter adjustment."
            )
            return

        pid_config = np.atleast_2d(pid_config)
        if pid_config.shape[1] < 4:
            warn(
                "PID calibration file must contain at least four columns: "
                "[setpoint (mK), P, I, D]."
            )
            return

        setpoints = pid_config[:, 0]
        pid_values = pid_config[:, 1:4]
        sort_index = np.argsort(setpoints)
        self._pid_calib_setpoints = setpoints[sort_index] * 1e-3
        self._pid_calib_pid = pid_values[sort_index]
        self._valid_pid_config = True
        self._log.info(
            "PID calibration loaded from %s (%d entries).",
            path,
            len(self._pid_calib_setpoints),
        )


class BlueFors(Instrument):
    """
    QCoDeS driver for BlueFors fridges using the HTTP API exposed by
    the BlueFors Temperature Controller software.

    Temperatures, resistances, pressures and mixing chamber heater controls
    are queried from the controller directly, which avoids the latency of
    scraping log files on disk.
    """

    def __init__(
        self,
        name: str,
        folder_path: Optional[str],
        channel_vacuum_can: Optional[int],
        channel_pumping_line: Optional[int],
        channel_compressor_outlet: Optional[int],
        channel_compressor_inlet: Optional[int],
        channel_mixture_tank: Optional[int],
        channel_venting_line: Optional[int],
        channel_50k_plate: Optional[int],
        channel_4k_plate: Optional[int],
        channel_still: Optional[int],
        channel_mixing_chamber: Optional[int],
        channel_magnet: Optional[int] = None,
        channel_fse: Optional[int] = None,
        *,
        host: str,
        api_key: str,
        port: int = 49098,
        mixing_chamber_heater_id: Optional[int] = None,
        pid_calibration_path: Optional[str] = None,
        enable_maxigauge: bool = False,
        emulate: bool = False,
        verify_ssl: bool = False,
        timeout: float = 5.0,
        auto_pid_calibration: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(name=name, **kwargs)

        if folder_path:
            self.log.info(
                "The folder_path argument is ignored because this driver now "
                "talks to the controller over HTTP."
            )

        temperature_entries: List[Tuple[str, Optional[int], str]] = [
            ("50k_plate", channel_50k_plate, "50 K plate"),
            ("4k_plate", channel_4k_plate, "4 K plate"),
            ("still", channel_still, "still"),
            ("mixing_chamber", channel_mixing_chamber, "mixing chamber"),
            ("magnet", channel_magnet, "magnet"),
            ("fse", channel_fse, "FSE"),
        ]

        pressure_entries: List[Tuple[str, Optional[int], str]] = [
            ("vacuum_can", channel_vacuum_can, "vacuum can"),
            ("pumping_line", channel_pumping_line, "pumping line"),
            ("compressor_outlet", channel_compressor_outlet, "compressor outlet"),
            ("compressor_inlet", channel_compressor_inlet, "compressor inlet"),
            ("mixture_tank", channel_mixture_tank, "mixture tank"),
            ("venting_line", channel_venting_line, "venting line"),
        ]

        has_pressure_channels = any(channel is not None for _, channel, _ in pressure_entries)
        enable_maxigauge = enable_maxigauge or has_pressure_channels

        self._api = _BlueForsAPIClient(
            host=host,
            api_key=api_key,
            port=port,
            mixing_chamber_channel_id=channel_mixing_chamber,
            mixing_chamber_heater_id=mixing_chamber_heater_id,
            pid_calibration_path=pid_calibration_path,
            enable_maxigauge=enable_maxigauge,
            emulate=emulate,
            verify_ssl=verify_ssl,
            timeout=timeout,
            auto_pid_calibration=auto_pid_calibration,
            logger=self.log,
        )

        for parameter_name, channel, description in temperature_entries:
            self._register_temperature_parameter(parameter_name, channel, description)

        for parameter_name, channel, description in pressure_entries:
            self._register_pressure_parameter(parameter_name, channel, description)

        self._has_heater_controls = (
            mixing_chamber_heater_id is not None and channel_mixing_chamber is not None
        )
        if self._has_heater_controls:
            self._register_heater_parameters()

        self.connect_message()

    def _register_temperature_parameter(
        self, parameter_name: str, channel: Optional[int], description: str
    ) -> None:
        if channel is None:
            return
        self.add_parameter(
            name=f"temperature_{parameter_name}",
            unit="K",
            get_parser=float,
            get_cmd=partial(self.get_temperature, channel),
            docstring=f"Temperature of the {description}.",
        )
        self.add_parameter(
            name=f"resistance_{parameter_name}",
            unit="Ohm",
            get_parser=float,
            get_cmd=partial(self.get_resistance, channel),
            docstring=f"Sensor resistance of the {description}.",
        )

    def _register_pressure_parameter(
        self, parameter_name: str, channel: Optional[int], description: str
    ) -> None:
        if channel is None:
            return
        self.add_parameter(
            name=f"pressure_{parameter_name}",
            unit="mBar",
            get_parser=float,
            get_cmd=partial(self.get_pressure, channel),
            docstring=f"Pressure of the {description}.",
        )

    def _register_heater_parameters(self) -> None:
        self.add_parameter(
            "mxc_heater_status",
            unit="",
            get_cmd=self._get_mxc_heater_status,
            set_cmd=self._set_mxc_heater_status,
            vals=Bool(),
            docstring="True if the mixing chamber heater output is active.",
        )
        self.add_parameter(
            "mxc_heater_pid_mode",
            unit="",
            get_cmd=self._get_mxc_heater_mode,
            set_cmd=self._set_mxc_heater_mode,
            vals=Bool(),
            docstring="PID mode toggle for the mixing chamber heater.",
        )
        self.add_parameter(
            "mxc_heater_power",
            unit="uW",
            get_cmd=self._get_mxc_heater_power,
            set_cmd=self._set_mxc_heater_power,
            vals=Numbers(min_value=0, max_value=5000),
            docstring="Mixing chamber heater power in microwatts.",
        )
        self.add_parameter(
            "mxc_heater_setpoint_mK",
            unit="mK",
            get_cmd=self._get_mxc_heater_setpoint,
            set_cmd=self._set_mxc_heater_setpoint,
            vals=Numbers(min_value=0, max_value=1000),
            docstring="Mixing chamber heater temperature setpoint in millikelvin.",
        )
        for axis in ("p", "i", "d"):
            self.add_parameter(
                f"mxc_heater_pid_{axis}",
                unit="",
                get_cmd=partial(self._get_mxc_pid_term, axis),
                set_cmd=partial(self._set_mxc_pid_term, axis),
                docstring=f"{axis.upper()} term of the mixing chamber heater PID loop.",
            )

    def _safe_api_call(self, func: Callable[[], Any], failure_value: Any) -> Any:
        try:
            return func()
        except Exception as err:  # pragma: no cover - hardware/IO dependent
            self.log.warning("BlueFors API call failed: %s", err)
            return failure_value

    def _execute_api(self, func: Callable[[], Any]) -> None:
        try:
            func()
        except Exception as err:  # pragma: no cover - hardware/IO dependent
            self.log.warning("BlueFors API command failed: %s", err)

    def get_temperature(self, channel: int) -> float:
        return float(
            self._safe_api_call(
                lambda: self._api.get_channel_temperature(channel),
                np.nan,
            )
        )

    def get_resistance(self, channel: int) -> float:
        return float(
            self._safe_api_call(
                lambda: self._api.get_channel_resistance(channel),
                np.nan,
            )
        )

    def get_pressure(self, channel: int) -> float:
        return float(
            self._safe_api_call(
                lambda: self._api.get_maxigauge_channel(channel),
                np.nan,
            )
        )

    def get_mxc_temperature(self) -> float:
        return float(self._safe_api_call(self._api.get_mxc_temperature, np.nan))

    def get_mxc_resistance(self) -> float:
        return float(self._safe_api_call(self._api.get_mxc_resistance, np.nan))

    def set_mxc_heater_setpoint(
        self, temperature_mK: float, use_pid_calibration: Optional[bool] = None
    ) -> bool:
        return bool(
            self._safe_api_call(
                lambda: self._api.set_mxc_heater_setpoint(
                    temperature_mK, use_pid_calib=use_pid_calibration
                ),
                False,
            )
        )

    def set_mxc_heater_power(self, power_uW: float) -> bool:
        return bool(
            self._safe_api_call(
                lambda: self._api.set_mxc_heater_power(power_uW), False
            )
        )

    def get_mxc_heater_pid_config(self) -> List[float]:
        return self._safe_api_call(self._api.get_mxc_heater_pid_config, [np.nan] * 3)

    def set_mxc_heater_pid_config(
        self, p: Optional[float] = None, i: Optional[float] = None, d: Optional[float] = None
    ) -> bool:
        return bool(
            self._safe_api_call(
                lambda: self._api.set_mxc_heater_pid_config(p, i, d), False
            )
        )

    def _get_mxc_heater_status(self) -> bool:
        return bool(self._safe_api_call(self._api.get_mxc_heater_status, False))

    def _set_mxc_heater_status(self, value: bool) -> None:
        self._execute_api(lambda: self._api.set_mxc_heater_status(bool(value)))

    def _get_mxc_heater_mode(self) -> bool:
        return bool(self._safe_api_call(self._api.get_mxc_heater_mode, False))

    def _set_mxc_heater_mode(self, value: bool) -> None:
        self._execute_api(lambda: self._api.set_mxc_heater_mode(bool(value)))

    def _get_mxc_heater_power(self) -> float:
        return float(self._safe_api_call(self._api.get_mxc_heater_power, np.nan))

    def _set_mxc_heater_power(self, value: float) -> None:
        self._execute_api(lambda: self._api.set_mxc_heater_power(float(value)))

    def _get_mxc_heater_setpoint(self) -> float:
        return float(self._safe_api_call(self._api.get_mxc_heater_setpoint, np.nan))

    def _set_mxc_heater_setpoint(self, value: float) -> None:
        self._execute_api(lambda: self._api.set_mxc_heater_setpoint(float(value)))

    def _get_mxc_pid_term(self, axis: str) -> float:
        return float(
            self._safe_api_call(
                lambda: self._api.get_mxc_heater_value(f"pid_{axis}"),
                np.nan,
            )
        )

    def _set_mxc_pid_term(self, axis: str, value: float) -> None:
        self._execute_api(
            lambda: self._api.set_mxc_heater_value(f"pid_{axis}", float(value))
        )
