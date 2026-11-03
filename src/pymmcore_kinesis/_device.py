"""
Thorlabs KDC101 rotation stage as a Micro-Manager (pymmcore-plus UniMMCore)
Python device.

It is deliberately a *generic* device, not a Micro-Manager "Stage": stage
devices are single-axis focus drives in micrometres, and napari-micromanager's
Stages Control panel would show every rotation mount as a Z drive with
"10 µm" buttons.  Everything is done through properties instead, which is
also how config presets and the MDA engine apply values:

===============  ==========  =====================================================
property         access      meaning
===============  ==========  =====================================================
``Position``     read/write  target angle in degrees (0-360); usable in presets
``Angle``        read-only   live angle in degrees
``Home``         read/write  set ``Yes`` to home; reads ``Yes`` while homing
``Stop``         read/write  set ``Yes`` to stop a move
``Homed``        read-only   ``Yes``/``No``
``Stage``, ``SerialNumberActual``  read-only diagnostics
===============  ==========  =====================================================

The device reports *busy* while moving or homing, so ``waitForSystem()`` /
``waitForDevice()`` block until it has arrived.

Declare it in a Micro-Manager config file (``#py`` lines are ignored by the
classic C++ loader)::

    #py pyDevice,PumpBeamHWP,pymmcore_kinesis,KinesisRotationStage
    #py Property,PumpBeamHWP,SerialNumber,27004338
    #py Property,PumpBeamHWP,Scale,stage
    #py Property,PumpBeamHWP,DisplayName,Pump beam HWP

    #py ConfigGroup,channel,NADH,PumpBeamHWP,Position,60.0

Pre-init properties
-------------------
SerialNumber
    Kinesis serial number of the KDC101 (``python -m pymmcore_kinesis.list``
    prints the connected ones).  ``#N`` selects the N-th device in pylablib's
    ``list_kinesis_devices()`` order; prefer real serial numbers.
Scale
    ``stage`` lets pylablib autodetect the stage (PRM1-Z8 etc.), or a number
    giving encoder counts per degree (e.g. ``1920`` for a mount whose Kinesis
    "DeviceUnitsPerRevolution" is 345519/180).
HomeOnInitialize
    ``Yes``/``No``: home (asynchronously) on initialisation unless the
    controller already reports a homed state.
DisplayName
    Free text shown by the widgets instead of the device label.
"""

from __future__ import annotations

import threading
from typing import Any

from pylablib.devices import Thorlabs
from pymmcore_plus.experimental.unicore import GenericDevice, pymm_property

YES_NO = ["Yes", "No"]


class KinesisRotationStage(GenericDevice):
    """Thorlabs KDC101-driven rotation mount (angles in degrees, property-driven)."""

    # angle (deg) within which the stage counts as "at" its setpoint
    SETPOINT_TOLERANCE_DEG = 0.05

    _BUSY_FLAGS = ("moving_fw", "moving_bk", "jogging_fw", "jogging_bk", "active", "homing")

    def __init__(self) -> None:
        super().__init__()
        self._serial_number: str = ""
        self._scale: str = "stage"
        self._home_on_init: str = "Yes"
        self._display_name: str = ""
        self._motor: Any = None
        # last commanded angle, and the exact text it was set with through the
        # Position property (so the property reads back byte-identical to the
        # preset value once the stage is there; see Position)
        self._setpoint: float | None = None
        self._setpoint_text: str | None = None
        # pylablib device objects are not thread-safe; the core serialises
        # calls via the device lock, but widgets may poll from the Qt thread.
        # Guard every hardware call.
        self._hw_lock = threading.RLock()

    # ------------------------------------------------------------------ pre-init
    # NOTE: all getters return str on purpose (like C++ device properties):
    # pymmcore-widgets forwards getProperty() values into str-typed Qt signals.

    @pymm_property(is_pre_init=True, property_type=str)
    def SerialNumber(self) -> str:
        return self._serial_number

    @SerialNumber.setter
    def SerialNumber(self, value: str) -> None:
        self._serial_number = str(value).strip()

    @pymm_property(is_pre_init=True, property_type=str)
    def Scale(self) -> str:
        return self._scale

    @Scale.setter
    def Scale(self, value: str) -> None:
        self._scale = str(value).strip()

    @pymm_property(is_pre_init=True, allowed_values=YES_NO, property_type=str)
    def HomeOnInitialize(self) -> str:
        return self._home_on_init

    @HomeOnInitialize.setter
    def HomeOnInitialize(self, value: str) -> None:
        self._home_on_init = str(value)

    @pymm_property(is_pre_init=True, property_type=str)
    def DisplayName(self) -> str:
        return self._display_name

    @DisplayName.setter
    def DisplayName(self, value: str) -> None:
        self._display_name = str(value).strip()

    # ------------------------------------------------------------------ runtime

    @pymm_property(property_type=float)
    def Position(self) -> str:
        """Target angle in degrees (0-360). Settable so it can be used in config presets.

        While the stage is at the angle last set through this property, the
        *exact text* it was set with is returned (e.g. "60.0"), because the
        preset widgets compare the cached property value with the preset text
        character by character.  Otherwise (homed, stopped, still moving) the
        live angle is returned, so the preset correctly shows as not matching.
        """
        live = self.angle()
        if (
            self._setpoint is not None
            and self._setpoint_text is not None
            and abs(live - self._setpoint) <= self.SETPOINT_TOLERANCE_DEG
        ):
            return self._setpoint_text
        return f"{live:.2f}"

    @Position.setter
    def Position(self, value: Any) -> None:
        # no `limits=` on the property: the core would coerce the value to
        # float before it reaches us and we would lose the original text
        text = str(value).strip()
        try:
            target = float(text)
        except ValueError as e:
            raise ValueError(f"{self.get_label()}: Position must be a number, got {value!r}") from e
        if not 0.0 <= target <= 360.0:
            raise ValueError(f"{self.get_label()}: Position {target} out of range 0-360 deg")
        self.move_to(target, text)

    @pymm_property(is_read_only=True, property_type=float)
    def Angle(self) -> str:
        """Live angle in degrees."""
        return f"{self.angle():.2f}"

    @pymm_property(allowed_values=YES_NO, property_type=str)
    def Home(self) -> str:
        """Set to ``Yes`` to home the stage; reads ``Yes`` while homing."""
        with self._hw_lock:
            if self._motor is None:
                return "No"
            return "Yes" if "homing" in self._motor.get_status() else "No"

    @Home.setter
    def Home(self, value: str) -> None:
        if str(value) == "Yes":
            self.home()

    @pymm_property(allowed_values=YES_NO, property_type=str)
    def Stop(self) -> str:
        """Set to ``Yes`` to stop the current move."""
        return "No"

    @Stop.setter
    def Stop(self, value: str) -> None:
        if str(value) == "Yes":
            self.stop()

    @pymm_property(is_read_only=True, allowed_values=YES_NO, property_type=str)
    def Homed(self) -> str:
        with self._hw_lock:
            if self._motor is None:
                return "No"
            return "Yes" if self._motor.is_homed() else "No"

    @pymm_property(is_read_only=True, property_type=str)
    def Stage(self) -> str:
        with self._hw_lock:
            if self._motor is None:
                return ""
            return str(self._motor.get_stage() or "unknown")

    @pymm_property(is_read_only=True, property_type=str)
    def SerialNumberActual(self) -> str:
        with self._hw_lock:
            if self._motor is None:
                return ""
            return str(self._motor.get_device_info().serial_no)

    # ------------------------------------------------------------------ lifecycle

    def _resolve_serial(self) -> str:
        sn = self._serial_number
        if not sn:
            raise ValueError(
                f"{self.get_label()}: SerialNumber pre-init property is not set "
                "(python -m pymmcore_kinesis.list prints the connected controllers)."
            )
        if sn.startswith("#"):
            devices = Thorlabs.list_kinesis_devices()
            try:
                sn = devices[int(sn[1:])][0]
            except (ValueError, IndexError) as e:
                raise ValueError(
                    f"{self.get_label()}: cannot resolve SerialNumber {sn!r}; "
                    f"connected Kinesis devices: {devices}"
                ) from e
        return sn

    def _resolve_scale(self) -> str | float:
        try:
            return float(self._scale)
        except ValueError:
            return self._scale  # "stage" (autodetect) or a pylablib stage name

    def initialize(self) -> None:
        serial = self._resolve_serial()
        with self._hw_lock:
            self._motor = Thorlabs.KinesisMotor(serial, scale=self._resolve_scale())
            if self._home_on_init == "Yes" and not self._motor.is_homed():
                # asynchronous: busy() reports True until homing completes, so
                # the core's waitForSystem()/waitForDevice() will block on it.
                self._motor.home(sync=False)
        super().initialize()

    def shutdown(self) -> None:
        with self._hw_lock:
            if self._motor is not None:
                try:
                    self._motor.close()
                finally:
                    self._motor = None
        super().shutdown()

    def description(self) -> str:
        return "Thorlabs Kinesis (KDC101) rotation mount; angles in degrees"

    # ------------------------------------------------------------------ motion API

    def _require_motor(self) -> Any:
        if self._motor is None:
            raise RuntimeError(f"{self.get_label()}: device not initialised")
        return self._motor

    def busy(self) -> bool:
        # one status query (pylablib's is_moving() + is_homing() would be two)
        with self._hw_lock:
            if self._motor is None:
                return False
            status = self._motor.get_status()
            return any(flag in status for flag in self._BUSY_FLAGS)

    def angle(self) -> float:
        """Live angle in degrees."""
        with self._hw_lock:
            return float(self._require_motor().get_position())

    def move_to(self, target: float, text: str | None = None) -> None:
        """Start moving to ``target`` degrees (returns immediately; see ``busy()``)."""
        with self._hw_lock:
            self._require_motor().move_to(float(target))
            self._setpoint = float(target)
            self._setpoint_text = text

    def home(self) -> None:
        """Start homing (returns immediately; see ``busy()``)."""
        with self._hw_lock:
            self._require_motor().home(sync=False, force=True)
            self._setpoint = self._setpoint_text = None

    def stop(self) -> None:
        with self._hw_lock:
            self._require_motor().stop(immediate=False, sync=False)
            self._setpoint = self._setpoint_text = None


# UniMMCore writes `pyDevice,<label>,<class.__module__>,<class name>` when a
# config is saved: use the public import path rather than this private module.
KinesisRotationStage.__module__ = "pymmcore_kinesis"
