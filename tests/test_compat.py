"""The preset-dropdown workarounds are applied on import, idempotent, and effective."""

from __future__ import annotations

import pytest

from pymmcore_kinesis import _compat, apply_workarounds

pytest.importorskip("pymmcore_widgets")

from pymmcore_widgets import PresetsWidget  # noqa: E402


def test_patched_and_idempotent():
    for name in ("_update_if_props_not_match_preset", "_on_cfg_set"):
        fn = PresetsWidget.__dict__[name]
        assert getattr(fn, _compat.MARK, False)
        apply_workarounds()
        assert PresetsWidget.__dict__[name] is fn  # not wrapped twice


def test_dropdown_follows_preset_with_python_devices(qtbot, core):
    pw = PresetsWidget("channel", mmcore=core)
    qtbot.addWidget(pw)
    assert pw.value() == "NADH"  # the Startup angles equal the NADH preset

    core.setConfig("channel", "FAD")  # as the MDA / a script would
    qtbot.waitUntil(lambda: pw.value() == "FAD", timeout=2000)
    core.waitForSystem()
    # any later re-sync keeps the selection and applies nothing
    pw._update_if_props_not_match_preset()
    pw._on_property_changed("PumpBeamHWP", "Position", "60.0")
    qtbot.wait(50)
    assert pw.value() == "FAD"
    assert core.getCurrentConfig("channel") == "FAD"


def test_user_selection_is_not_hijacked(qtbot, core, fake_kinesis):
    """Selecting a preset must never end up applying a different one."""
    pw = PresetsWidget("channel", mmcore=core)
    qtbot.addWidget(pw)
    nd = fake_kinesis["27253344"]
    n_moves = len(nd.log)
    pw.setValue("FAD")  # what a mouse click does -> setConfig
    qtbot.wait(50)
    core.waitForSystem()
    pw._on_property_changed("PumpBeamHWP", "Position", "60.0")
    qtbot.wait(50)
    assert pw.value() == "FAD"
    assert [m for m in nd.log[n_moves:]] == ["move_to(295.0)"]  # exactly one move
