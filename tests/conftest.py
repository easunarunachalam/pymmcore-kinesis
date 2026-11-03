"""pytest configuration: simulated Kinesis controllers (pytest-qt provides ``qtbot``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pymmcore_kinesis.testing import FakeKinesisMotor, install_fake_kinesis, uninstall_fake_kinesis

# Two rotation stages, one by serial number and one by enumeration index,
# with a Startup preset and a channel group (only #py lines: no C++ devices,
# so no Micro-Manager device-adapter installation is needed).
TEST_CFG = """\
Property,Core,Initialize,0

#py pyDevice,PumpBeamHWP,pymmcore_kinesis,KinesisRotationStage
#py pyDevice,SyncNDFilter,pymmcore_kinesis,KinesisRotationStage

#py Property,PumpBeamHWP,SerialNumber,27004338
#py Property,PumpBeamHWP,Scale,stage
#py Property,PumpBeamHWP,DisplayName,Pump beam HWP
#py Property,SyncNDFilter,SerialNumber,#1
#py Property,SyncNDFilter,Scale,1920

Property,Core,Initialize,1

#py ConfigGroup,System,Startup,PumpBeamHWP,Position,60.0
#py ConfigGroup,System,Startup,SyncNDFilter,Position,300.0

#py ConfigGroup,channel,NADH,PumpBeamHWP,Position,60.0
#py ConfigGroup,channel,NADH,SyncNDFilter,Position,300.0
#py ConfigGroup,channel,FAD,PumpBeamHWP,Position,60.0
#py ConfigGroup,channel,FAD,SyncNDFilter,Position,295.0

Property,Core,ChannelGroup,channel
"""


@pytest.fixture
def fake_kinesis():
    FakeKinesisMotor.homing_time_s = 0.2
    FakeKinesisMotor.speed_deg_per_s = 400.0
    created = install_fake_kinesis()
    yield created
    uninstall_fake_kinesis()


@pytest.fixture
def cfg_path(tmp_path: Path) -> Path:
    p = tmp_path / "test.cfg"
    p.write_text(TEST_CFG)
    return p


@pytest.fixture
def core(fake_kinesis, cfg_path):
    from pymmcore_plus.experimental.unicore import UniMMCore

    mmc = UniMMCore()
    mmc.setTimeoutMs(20_000)
    mmc.loadSystemConfiguration(str(cfg_path))
    yield mmc
    mmc.unloadAllDevices()
