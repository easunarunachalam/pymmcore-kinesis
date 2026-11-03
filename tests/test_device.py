"""KinesisRotationStage loaded from a config file into a UniMMCore (simulated motors)."""

from __future__ import annotations

import time

import pytest
from pymmcore_plus import DeviceType


def angle(core, label: str) -> float:
    return float(core.getProperty(label, "Angle"))


def test_load_and_startup(core, fake_kinesis):
    assert {"PumpBeamHWP", "SyncNDFilter"} <= set(core.getLoadedDevices())
    assert core.getDeviceName("PumpBeamHWP") == "KinesisRotationStage"
    # NOT a Micro-Manager stage: keeps it out of the Z-stage control panels
    assert core.getDeviceType("PumpBeamHWP") == DeviceType.Generic
    assert core.getLoadedDevicesOfType(DeviceType.Stage) == ()
    assert core.getProperty("PumpBeamHWP", "DisplayName") == "Pump beam HWP"
    assert core.getProperty("SyncNDFilter", "DisplayName") == ""

    # serial number resolution: explicit and "#index"
    assert fake_kinesis["27004338"].scale == "stage"
    assert fake_kinesis["27253344"].scale == 1920.0
    assert core.getProperty("PumpBeamHWP", "SerialNumberActual") == "27004338"
    assert core.getProperty("PumpBeamHWP", "Stage") == "PRM1-Z8"

    # homed on initialise (async), then the Startup preset was applied
    assert all("home" in m.log and m.is_homed() for m in fake_kinesis.values())
    assert core.getProperty("PumpBeamHWP", "Homed") == "Yes"
    assert angle(core, "PumpBeamHWP") == pytest.approx(60.0)
    assert angle(core, "SyncNDFilter") == pytest.approx(300.0)
    assert core.getChannelGroup() == "channel"


def test_presets_busy_and_readback(core, fake_kinesis):
    core.setConfig("channel", "FAD")
    assert core.deviceBusy("SyncNDFilter")  # moving 300 -> 295
    core.waitForSystem()
    assert not core.systemBusy()
    assert angle(core, "SyncNDFilter") == pytest.approx(295.0)
    # the property reads back the preset text once there, so presets match
    assert core.getProperty("SyncNDFilter", "Position") == "295.0"
    assert core.getCurrentConfig("channel") == "FAD"
    assert core.getCurrentConfigFromCache("channel") == "FAD"

    core.setConfig("channel", "NADH")
    core.waitForSystem()
    assert core.getCurrentConfig("channel") == "NADH"


def test_position_property_text_and_limits(core):
    core.setProperty("PumpBeamHWP", "Position", "45")
    core.waitForDevice("PumpBeamHWP")
    assert core.getProperty("PumpBeamHWP", "Position") == "45"  # exact text
    assert core.getProperty("PumpBeamHWP", "Angle") == "45.00"
    with pytest.raises(Exception):
        core.setProperty("PumpBeamHWP", "Position", 400)
    with pytest.raises(Exception):
        core.setProperty("PumpBeamHWP", "Position", "abc")


def test_home_and_stop_via_properties(core, fake_kinesis):
    core.setProperty("PumpBeamHWP", "Home", "Yes")
    assert core.deviceBusy("PumpBeamHWP") and core.getProperty("PumpBeamHWP", "Home") == "Yes"
    core.waitForDevice("PumpBeamHWP")
    assert core.getProperty("PumpBeamHWP", "Home") == "No"
    assert angle(core, "PumpBeamHWP") == pytest.approx(0.0)
    assert core.getProperty("PumpBeamHWP", "Position") == "0.00"  # live value after homing

    core.setProperty("PumpBeamHWP", "Position", "200")
    time.sleep(0.05)
    core.setProperty("PumpBeamHWP", "Stop", "Yes")
    core.waitForDevice("PumpBeamHWP")
    assert 0 < angle(core, "PumpBeamHWP") < 200
    assert core.getProperty("PumpBeamHWP", "Stop") == "No"
    assert core.getProperty("PumpBeamHWP", "Position") != "200"  # not at the setpoint


def test_busy_uses_one_status_query(core, fake_kinesis):
    m = fake_kinesis["27004338"]
    calls = {"n": 0}
    orig = m.get_status

    def counting():
        calls["n"] += 1
        return orig()

    m.get_status = counting  # type: ignore[method-assign]
    core.deviceBusy("PumpBeamHWP")
    assert calls["n"] == 1


def test_mda_event_property_moves_the_stage(core):
    """The MDA engine applies event properties with setProperty; a Position works."""
    from useq import MDAEvent

    core.mda.engine.setup_event(MDAEvent(properties=[("SyncNDFilter", "Position", 310.0)]))
    assert angle(core, "SyncNDFilter") == pytest.approx(310.0)


def test_config_roundtrip(core, tmp_path):
    out = tmp_path / "saved.cfg"
    core.saveSystemConfiguration(str(out))
    text = out.read_text()
    assert "#py pyDevice,PumpBeamHWP,pymmcore_kinesis,KinesisRotationStage" in text
    assert "#py Property,PumpBeamHWP,DisplayName,Pump beam HWP" in text
    assert "#py ConfigGroup,channel,FAD,SyncNDFilter,Position,295" in text


def test_unload_closes_motors(core, fake_kinesis):
    core.unloadAllDevices()
    assert all(m.closed for m in fake_kinesis.values())


def test_bad_serial_index(fake_kinesis):
    from pymmcore_plus import DeviceInitializationState
    from pymmcore_plus.experimental.unicore import UniMMCore

    from pymmcore_kinesis import KinesisRotationStage

    mmc = UniMMCore()
    dev = KinesisRotationStage()
    mmc.loadPyDevice("X", dev)
    mmc.setProperty("X", "SerialNumber", "#9")
    mmc.initializeDevice("X")  # UniMMCore logs initialisation errors instead of raising
    assert mmc.getDeviceInitializationState("X") != DeviceInitializationState.InitializedSuccessfully
    assert "cannot resolve SerialNumber" in str(dev._initialized_)
    mmc.unloadAllDevices()
