"""
Live angle / manual target panel for every :class:`KinesisRotationStage`
loaded in the Micro-Manager core.

Works as a napari plugin dock widget (``Plugins > Thorlabs Kinesis > Rotation
Stages``): napari constructs it with no arguments, and it finds the core that
napari-micromanager is using.  It can also be embedded in any Qt app with an
explicit ``mmcore``.

Everything goes through the devices' properties (``Angle``, ``Position``,
``Home``, ``Stop``); per-channel preset angles are *not* kept here, they live
in the Micro-Manager config groups and are applied by the core / MDA engine.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any

from qtpy.QtCore import QTimer
from qtpy.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ._core import find_core, py_devices_named
from ._device import KinesisRotationStage

__all__ = ["RotationStagesWidget", "kinesis_stage_labels"]

# status changes of the rows (a launcher can route this logger into its session log)
_log = logging.getLogger(__name__)


def kinesis_stage_labels(core: Any) -> list[str]:
    """Labels of the KinesisRotationStage devices loaded in ``core``."""
    return py_devices_named(core, KinesisRotationStage.name())


class _StageRow:
    """One row: name, live angle, target entry, Home and Stop buttons."""

    def __init__(self, core: Any, label: str, display_name: str) -> None:
        self.core = core
        self.label = label

        self.name = QLabel(f"{display_name} (deg):")
        self.status = QLineEdit("")
        self.status.setReadOnly(True)
        self.target = QLineEdit("")
        self.target.setPlaceholderText("target")
        self.home_button = QPushButton("Home")
        self.stop_button = QPushButton("Stop")

        self.widgets = QHBoxLayout()
        self.widgets.addWidget(self.status)
        self.widgets.addWidget(self.target)
        self.widgets.addWidget(self.home_button)
        self.widgets.addWidget(self.stop_button)

        self.target.editingFinished.connect(self.move_to_target)
        self.home_button.clicked.connect(self.home)
        self.stop_button.clicked.connect(self.stop)
        self._last_logged = ""

    def refresh(self) -> None:
        try:
            angle = float(self.core.getProperty(self.label, "Angle"))
            busy = self.core.deviceBusy(self.label)
        except Exception as e:  # device gone / comm error
            self.status.setText(f"error: {e}")
            self._log_state(f"error: {e}")
            return
        self.status.setText(f"{angle:7.2f}" + ("  (moving)" if busy else ""))
        if not self.target.text() and not busy:
            self.target.setText(f"{angle:.2f}")
        # one line when a move starts and one with the angle it settled at, not one per poll
        self._log_state("moving" if busy else f"at {angle:.2f} deg")

    def _log_state(self, text: str) -> None:
        if text != self._last_logged:
            self._last_logged = text
            _log.info("%s: %s", self.label, text)

    def move_to_target(self) -> None:
        text = self.target.text().strip()
        try:
            float(text)
        except ValueError:
            warnings.warn(f"Invalid position for {self.label}; enter a number.", stacklevel=2)
            return
        self.core.setProperty(self.label, "Position", text)

    def home(self) -> None:
        self.core.setProperty(self.label, "Home", "Yes")

    def stop(self) -> None:
        self.core.setProperty(self.label, "Stop", "Yes")


class RotationStagesWidget(QWidget):
    """Panel with one row per KinesisRotationStage loaded in the core.

    Parameters
    ----------
    mmcore : CMMCorePlus | None
        Core to use.  ``None`` (the napari plugin case) means "the core
        napari-micromanager is using", re-resolved on every refresh so a core
        swap by napari-micromanager is followed.
    napari_viewer :
        Injected by napari; unused.
    poll_ms : int
        Angle refresh period.
    """

    def __init__(
        self,
        mmcore: Any = None,
        napari_viewer: Any = None,
        parent: QWidget | None = None,
        poll_ms: int = 500,
    ) -> None:
        super().__init__(parent=parent)
        self._explicit_core = mmcore
        self._core: Any = None
        self._rows: list[_StageRow] = []
        self.setWindowTitle("Rotation Stages")

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(4, 4, 4, 4)
        self._message = QLabel("")
        self._outer.addWidget(self._message)
        self._form_host = QWidget()
        self._form = QFormLayout(self._form_host)
        self._outer.addWidget(self._form_host)
        self._outer.addStretch(1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(poll_ms)

        self.destroyed.connect(self._disconnect_core)
        self._tick()

    # ------------------------------------------------------------------ core

    @property
    def core(self) -> Any:
        return self._core

    @property
    def rows(self) -> list[_StageRow]:
        return self._rows

    def _attach_core(self, core: Any) -> None:
        self._disconnect_core()
        self._core = core
        try:
            core.events.systemConfigurationLoaded.connect(self.rebuild)
        except Exception:
            pass

    def _disconnect_core(self, *_: Any) -> None:
        if self._core is not None:
            try:
                self._core.events.systemConfigurationLoaded.disconnect(self.rebuild)
            except Exception:
                pass

    # ------------------------------------------------------------------ rows

    def rebuild(self, *_: Any) -> None:
        """(Re)discover the stages in the core and rebuild the rows."""
        while self._form.rowCount():
            self._form.removeRow(0)
        self._rows = []
        core = self._core
        labels = kinesis_stage_labels(core) if core is not None else []
        if not labels:
            self._message.setText("No KinesisRotationStage devices are loaded in Micro-Manager.")
            return
        self._message.setText("")
        header = QHBoxLayout()
        header.addWidget(QLabel("Current (deg)"))
        header.addWidget(QLabel("Target (deg)"))
        header.addWidget(QLabel(""))
        header.addWidget(QLabel(""))
        self._form.addRow(QLabel(""), header)
        for label in labels:
            try:
                name = str(core.getProperty(label, "DisplayName")) or label
            except Exception:
                name = label
            row = _StageRow(core, label, name)
            self._form.addRow(row.name, row.widgets)
            self._rows.append(row)
        self.refresh()

    def refresh(self) -> None:
        for row in self._rows:
            row.refresh()

    def _tick(self) -> None:
        try:
            core = find_core(self._explicit_core)
        except Exception as e:
            self._message.setText(f"No Micro-Manager core: {e}")
            return
        if core is not self._core:
            self._attach_core(core)
            self.rebuild()
            return
        self.refresh()
