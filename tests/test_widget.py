"""RotationStagesWidget against a UniMMCore with simulated stages (pytest-qt)."""

from __future__ import annotations

import pytest

pytest.importorskip("qtpy")

from pymmcore_kinesis import RotationStagesWidget  # noqa: E402


def angle(core, label: str) -> float:
    return float(core.getProperty(label, "Angle"))


def test_rows_follow_loaded_stages(qtbot, core):
    w = RotationStagesWidget(mmcore=core)
    qtbot.addWidget(w)
    assert [r.label for r in w.rows] == ["PumpBeamHWP", "SyncNDFilter"]
    assert w.rows[0].name.text().startswith("Pump beam HWP")  # DisplayName
    assert w.rows[1].name.text().startswith("SyncNDFilter")  # falls back to the label
    w.refresh()
    assert w.rows[0].status.text().strip().startswith("60.00")
    assert w.rows[1].target.text() == "300.00"


def test_target_home_stop(qtbot, core):
    w = RotationStagesWidget(mmcore=core)
    qtbot.addWidget(w)
    row = w.rows[1]
    row.target.setText("310")
    row.move_to_target()
    core.waitForDevice("SyncNDFilter")
    assert angle(core, "SyncNDFilter") == pytest.approx(310.0)

    row.home()
    assert core.deviceBusy("SyncNDFilter")
    core.waitForDevice("SyncNDFilter")
    assert angle(core, "SyncNDFilter") == pytest.approx(0.0)

    row.target.setText("200")
    row.move_to_target()
    row.stop()
    core.waitForDevice("SyncNDFilter")
    assert angle(core, "SyncNDFilter") < 200


def test_empty_core_then_config_loaded(qtbot, fake_kinesis, cfg_path):
    from pymmcore_plus.experimental.unicore import UniMMCore

    mmc = UniMMCore()
    mmc.setTimeoutMs(20_000)
    w = RotationStagesWidget(mmcore=mmc)
    qtbot.addWidget(w)
    assert w.rows == [] and "No KinesisRotationStage" in w._message.text()

    mmc.loadSystemConfiguration(str(cfg_path))  # systemConfigurationLoaded -> rebuild
    qtbot.waitUntil(lambda: len(w.rows) == 2, timeout=3000)
    assert w._message.text() == ""
    mmc.unloadAllDevices()


def test_plugin_construction_without_arguments(qtbot, monkeypatch, core):
    """napari constructs the widget with no core: it must find one itself."""
    import pymmcore_kinesis._widget as wmod

    monkeypatch.setattr(wmod, "find_core", lambda explicit=None: core)
    w = RotationStagesWidget()
    qtbot.addWidget(w)
    assert w.core is core and len(w.rows) == 2
