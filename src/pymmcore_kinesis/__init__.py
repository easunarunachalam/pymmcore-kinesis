"""Thorlabs Kinesis (KDC101) rotation stages for pymmcore-plus / napari-micromanager.

* :class:`KinesisRotationStage` - a pure-Python Micro-Manager device
  (angles in degrees, driven through its ``Position`` / ``Angle`` / ``Home`` /
  ``Stop`` properties), declared in a Micro-Manager config file::

      #py pyDevice,PumpBeamHWP,pymmcore_kinesis,KinesisRotationStage
      #py Property,PumpBeamHWP,SerialNumber,27004338
      #py Property,PumpBeamHWP,DisplayName,Pump beam HWP

* :class:`RotationStagesWidget` - a Qt panel listing every such stage loaded in
  the core (``Plugins > Thorlabs Kinesis > Rotation Stages`` in napari).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._compat import apply_workarounds
from ._device import KinesisRotationStage

__version__ = "0.1.0"

__all__ = ["KinesisRotationStage", "RotationStagesWidget", "apply_workarounds", "__version__"]

# Preset handling with Python devices needs two small runtime fixes in the
# pymmcore-widgets preset dropdown (see _compat.py).  Applying them here means
# that loading a config file that references this module is enough; no
# launcher code.  PYMMCORE_PYDEVICE_NO_WORKAROUNDS=1 disables this.
apply_workarounds()

if TYPE_CHECKING:
    from ._widget import RotationStagesWidget


def __getattr__(name: str):  # lazy: the widget pulls in Qt
    if name == "RotationStagesWidget":
        from ._widget import RotationStagesWidget

        return RotationStagesWidget
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
