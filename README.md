# pymmcore-kinesis

A small pymmcore plugin to control Thorlabs Kinesis **KDC101** rotation stage devices (PRM1-Z8 half-wave plate mounts,
ND filter mounts, ...) as pure-Python Micro-Manager devices for
[pymmcore-plus](https://github.com/pymmcore-plus/pymmcore-plus) /
[napari-micromanager](https://github.com/pymmcore-plus/napari-micromanager),
plus a small napari panel.  The controllers are driven through
[pylablib](https://pylablib.readthedocs.io) (Kinesis / APT protocol over
USB); no C++ device adapter is needed.

**Disclaimer:** This software is provided "as is", without warranty of any
kind. There is no guarantee that it works, that it is fit for any purpose, or
that it will not damage your hardware, your data or your computer. The authors
accept no liability for any such damage. See [LICENSE](LICENSE).

## Install

```powershell
pip install -e ".[napari,test]"
```

Requirements: pymmcore-plus 0.18.x (the Python-device layer `UniMMCore` is
still under `pymmcore_plus.experimental`, so the version is pinned
deliberately), napari-micromanager 0.3.x with a Qt6 binding (PyQt6).

## Devices in the config file

Lines starting with `#py ` are Python devices; the classic C++ Micro-Manager
ignores them.  Load such a file with a `UniMMCore` (napari-micromanager 0.3
switches to one automatically when it sees `#py` lines).

```
#py pyDevice,PumpBeamHWP,pymmcore_kinesis,KinesisRotationStage
#py Property,PumpBeamHWP,SerialNumber,27004338
#py Property,PumpBeamHWP,Scale,stage
#py Property,PumpBeamHWP,DisplayName,Pump beam HWP

#py ConfigGroup,channel,NADH,PumpBeamHWP,Position,60.0
#py ConfigGroup,channel,FAD,PumpBeamHWP,Position,60.0
```

| pre-init property | meaning |
|---|---|
| `SerialNumber` | KDC101 serial number; `python -m pymmcore_kinesis.list` prints the connected ones (`#N` = N-th enumerated controller) |
| `Scale` | `stage` = pylablib autodetects the stage; or a number = encoder counts per degree (e.g. `1920`) |
| `HomeOnInitialize` | `Yes`/`No`, home on start-up unless already homed |
| `DisplayName` | name shown in the panel instead of the label |

The device is driven entirely through properties (it is deliberately *not* a
Micro-Manager "Stage": those are focus drives in micrometres, and
napari-micromanager's Stages Control panel would show every rotation mount
as a Z drive with "10 µm" buttons):

| property | access | meaning |
|---|---|---|
| `Position` | read/write | target angle in degrees (0-360); usable in config presets |
| `Angle` | read-only | live angle in degrees |
| `Home` | read/write | set `Yes` to home (reads `Yes` while homing) |
| `Stop` | read/write | set `Yes` to stop a move |
| `Homed`, `Stage`, `SerialNumberActual` | read-only | diagnostics |

The device is *busy* while moving or homing, so the MDA engine and
`waitForSystem()` wait for it.  Every preset of a group must set the same
properties (Micro-Manager convention, enforced by the napari-micromanager
widgets).

## Panel

`Plugins > Thorlabs Kinesis > Rotation Stages` in napari (no launcher code:
the widget finds napari-micromanager's core itself and lists every
`KinesisRotationStage` loaded, re-discovering them when a config is loaded).
Or, in your own Qt code:

```python
from pymmcore_kinesis import RotationStagesWidget
w = RotationStagesWidget(mmcore=core)
```

## Preset workarounds

Importing `pymmcore_kinesis` (which loading the config does) applies two
small runtime fixes to pymmcore-widgets' preset dropdown, needed for presets
that contain Python devices: its `configSet` handler runs before the Python
devices are applied (`UniMMCore.setConfig` emits early; we defer the handler
by one event-loop turn), and it re-selects and *applies* the last preset when
its `<no match>` entry is removed (we block signals during that re-sync).
`PYMMCORE_PYDEVICE_NO_WORKAROUNDS=1` disables them.  See
`src/pymmcore_kinesis/_compat.py`.

## Tests

```powershell
python -m pytest
```

The tests run against simulated controllers (`pymmcore_kinesis.testing`),
which you can also use to develop without hardware.
