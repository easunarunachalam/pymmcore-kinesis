"""
Simulated Kinesis controllers for tests and for developing without hardware.

``install_fake_kinesis()`` replaces ``pylablib.devices.Thorlabs.KinesisMotor``
and ``list_kinesis_devices`` with in-memory fakes and returns a registry of
the motors created (keyed by serial number).  ``uninstall_fake_kinesis()``
restores pylablib.  In pytest use the ``fake_kinesis`` fixture from
``pymmcore_kinesis.testing`` (see ``tests/conftest.py``).
"""

from __future__ import annotations

import time
from typing import Any

from pylablib.devices import Thorlabs

DEFAULT_FAKE_DEVICES: tuple[tuple[str, str], ...] = (
    ("27004338", "Brushed Motor Controller"),
    ("27253344", "Brushed Motor Controller"),
    ("27600587", "Brushed Motor Controller"),
)


class FakeDeviceInfo:
    def __init__(self, serial_no: str) -> None:
        self.serial_no = serial_no
        self.model_no = "KDC101"


class FakeKinesisMotor:
    """Minimal stand-in for ``pylablib.devices.Thorlabs.KinesisMotor``.

    Moves at ``speed_deg_per_s`` and homes in ``homing_time_s`` (class
    attributes; small values keep tests fast, larger ones exercise busy()).
    """

    speed_deg_per_s = 400.0
    homing_time_s = 0.3

    def __init__(self, conn: Any, scale: Any = "step", **kw: Any) -> None:
        self.serial = str(conn)
        self.scale = scale
        self._pos = 0.0
        self._target = 0.0
        self._start_pos = 0.0
        self._t_start = time.monotonic()
        self._homed = False
        self._home_until = 0.0
        self.closed = False
        self.log: list[str] = []

    # --- motion model
    def _update(self) -> None:
        now = time.monotonic()
        if self._home_until and now >= self._home_until:
            self._home_until = 0.0
            self._homed = True
            self._pos = self._target = 0.0
        if self._pos != self._target:
            d = self.speed_deg_per_s * (now - self._t_start)
            if d >= abs(self._target - self._start_pos):
                self._pos = self._target
            else:
                self._pos = self._start_pos + d * (1 if self._target > self._start_pos else -1)

    # --- pylablib API subset
    def get_position(self) -> float:
        self._update()
        return self._pos

    def move_to(self, pos: float) -> None:
        self._update()
        self.log.append(f"move_to({pos})")
        self._start_pos = self._pos
        self._target = float(pos)
        self._t_start = time.monotonic()

    def is_moving(self) -> bool:
        self._update()
        return self._pos != self._target

    def is_homing(self) -> bool:
        self._update()
        return bool(self._home_until)

    def is_homed(self) -> bool:
        self._update()
        return self._homed

    def get_status(self) -> list[str]:
        self._update()
        flags = ["connected", "enabled"]
        if self._home_until:
            flags += ["homing", "active"]
        elif self._pos != self._target:
            flags += ["moving_fw" if self._target > self._pos else "moving_bk", "active"]
        if self._homed:
            flags.append("homed")
        return flags

    def home(self, sync: bool = True, force: bool = False, timeout: Any = None) -> None:
        if self._homed and not force:
            return
        self.log.append("home")
        self._home_until = time.monotonic() + self.homing_time_s
        if sync:
            time.sleep(self.homing_time_s + 0.01)
            self._update()

    def stop(self, immediate: bool = False, sync: bool = True, timeout: Any = None) -> None:
        self._update()
        self._target = self._pos

    def set_position_reference(self, position: float = 0) -> None:
        self._update()
        self._pos = self._target = float(position)

    def get_stage(self) -> str | None:
        return "PRM1-Z8" if self.scale == "stage" else None

    def get_device_info(self) -> FakeDeviceInfo:
        return FakeDeviceInfo(self.serial)

    def close(self) -> None:
        self.closed = True


_originals: dict[str, Any] = {}


def install_fake_kinesis(
    devices: tuple[tuple[str, str], ...] = DEFAULT_FAKE_DEVICES,
) -> dict[str, FakeKinesisMotor]:
    """Patch pylablib with the fakes; returns the registry of created motors."""
    created: dict[str, FakeKinesisMotor] = {}

    def fake_motor(conn: Any, scale: Any = "step", **kw: Any) -> FakeKinesisMotor:
        m = FakeKinesisMotor(conn, scale=scale, **kw)
        created[m.serial] = m
        return m

    if not _originals:
        _originals["KinesisMotor"] = Thorlabs.KinesisMotor
        _originals["list_kinesis_devices"] = Thorlabs.list_kinesis_devices
    Thorlabs.KinesisMotor = fake_motor  # type: ignore[attr-defined]
    Thorlabs.list_kinesis_devices = lambda: list(devices)  # type: ignore[attr-defined]
    return created


def uninstall_fake_kinesis() -> None:
    if _originals:
        Thorlabs.KinesisMotor = _originals.pop("KinesisMotor")  # type: ignore[attr-defined]
        Thorlabs.list_kinesis_devices = _originals.pop("list_kinesis_devices")  # type: ignore[attr-defined]
