"""The settings registry and the store behind it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rich.cells import cell_len

from tcw._text import marker_text
from tcw.settings import (
    ConfigStore,
    Setting,
    SettingAction,
    all_settings,
    config,
)


def test_a_setting_left_alone_reads_its_default(settings_path: Path) -> None:
    ttl = Setting(key="ttl", label="ttl", description="", group="Cache", default=900)
    assert ConfigStore(settings_path).get(ttl) == 900


def test_setting_a_value_persists_it(settings_path: Path) -> None:
    ttl = Setting(key="ttl", label="ttl", description="", group="Cache", default=900)
    ConfigStore(settings_path).set(ttl, 60)
    assert ConfigStore(settings_path).get(ttl) == 60


def test_a_value_equal_to_the_default_is_not_written(settings_path: Path) -> None:
    ttl = Setting(key="ttl", label="ttl", description="", group="Cache", default=900)
    store = ConfigStore(settings_path)
    store.set(ttl, 60)
    store.set(ttl, 900)
    assert json.loads(settings_path.read_text(encoding="utf-8")) == {}


def test_a_wrong_type_in_the_file_falls_back_to_the_default(
    settings_path: Path,
) -> None:
    settings_path.write_text(json.dumps({"ttl": "nonsense"}), encoding="utf-8")
    ttl = Setting(key="ttl", label="ttl", description="", group="Cache", default=900)
    assert ConfigStore(settings_path).get(ttl) == 900


def test_a_bool_in_the_file_does_not_satisfy_an_int_setting(
    settings_path: Path,
) -> None:
    # bool is a subclass of int, so an isinstance check would accept this.
    settings_path.write_text(json.dumps({"ttl": True}), encoding="utf-8")
    ttl = Setting(key="ttl", label="ttl", description="", group="Cache", default=900)
    assert ConfigStore(settings_path).get(ttl) == 900


def test_a_corrupt_file_degrades_to_defaults(settings_path: Path) -> None:
    settings_path.write_text("{not json", encoding="utf-8")
    ttl = Setting(key="ttl", label="ttl", description="", group="Cache", default=900)
    assert ConfigStore(settings_path).get(ttl) == 900


def _instance_setting() -> Setting[str]:
    return Setting(
        key="runners",
        label="runners",
        description="",
        group="G",
        default="",
        per_instance=True,
    )


def test_reset_reverts_to_the_default(settings_path: Path) -> None:
    ttl = Setting(key="ttl", label="ttl", description="", group="Cache", default=900)
    store = ConfigStore(settings_path)
    store.set(ttl, 60)
    store.reset(ttl)
    assert store.get(ttl) == 900


def test_resetting_something_never_set_is_a_no_op(settings_path: Path) -> None:
    ttl = Setting(key="ttl", label="ttl", description="", group="Cache", default=900)
    ConfigStore(settings_path).reset(ttl)
    assert not settings_path.exists()


def test_parse_and_format_are_inferred_from_the_default_type() -> None:
    count = Setting(key="count", label="count", description="", group="G", default=7)
    ratio = Setting(key="ratio", label="ratio", description="", group="G", default=0.5)
    name = Setting(key="name", label="name", description="", group="G", default="x")
    assert count.parse("12") == 12
    assert count.format(12) == "12"
    assert ratio.parse("1.5") == 1.5
    assert name.parse(" y ") == " y "  # str is identity, not stripped


def test_resetting_an_instance_setting_needs_an_active_instance(
    settings_path: Path,
) -> None:
    setting = _instance_setting()
    with pytest.raises(ValueError, match="no instance"):
        ConfigStore(settings_path).reset(setting)


def test_declaring_a_setting_registers_it() -> None:
    Setting(key="ttl", label="ttl", description="", group="Cache", default=900)
    assert [entry.key for entry in all_settings()] == ["ttl"]


def test_entries_are_ordered_by_group_then_label() -> None:
    Setting(key="b", label="beta", description="", group="Zed", default=1)
    Setting(key="a", label="alpha", description="", group="Zed", default=1)
    Setting(key="c", label="gamma", description="", group="Alpha", default=1)
    assert [entry.key for entry in all_settings()] == ["c", "a", "b"]


def test_a_duplicate_key_is_refused() -> None:
    Setting(key="ttl", label="ttl", description="", group="Cache", default=1)
    with pytest.raises(ValueError, match="duplicate"):
        Setting(key="ttl", label="other", description="", group="Cache", default=1)


def test_the_instances_key_is_reserved() -> None:
    with pytest.raises(ValueError, match="reserved"):
        Setting(key="instances", label="x", description="", group="G", default=1)


def test_an_action_shares_the_key_namespace_with_settings() -> None:
    Setting(key="clear", label="clear", description="", group="G", default=1)
    with pytest.raises(ValueError, match="duplicate"):
        SettingAction(
            key="clear",
            label="clear",
            description="",
            group="G",
            button_label="Clear",
            callback=lambda: None,
        )


def test_an_action_is_listed_alongside_settings() -> None:
    Setting(key="ttl", label="ttl", description="", group="G", default=1)
    SettingAction(
        key="clear",
        label="clear now",
        description="",
        group="G",
        button_label="Clear",
        callback=lambda: None,
    )
    assert {entry.key for entry in all_settings()} == {"ttl", "clear"}


def test_an_unrecognised_boolean_raises_rather_than_meaning_false() -> None:
    flag = Setting(key="flag", label="flag", description="", group="G", default=False)
    assert flag.parse("yes") is True
    assert flag.parse("off") is False
    with pytest.raises(ValueError):
        flag.parse("perhaps")


def test_a_boolean_formats_back_to_something_it_can_parse() -> None:
    flag = Setting(key="flag", label="flag", description="", group="G", default=False)
    assert flag.parse(flag.format(True)) is True


def test_choices_default_to_none() -> None:
    """None, not an empty tuple, is "unconstrained" -- the dialog falls back
    to a free-typed Input for any setting that doesn't opt into a Select."""
    setting = Setting(key="x", label="x", description="", group="G", default=1)
    assert setting.choices is None


def test_a_setting_can_declare_a_fixed_set_of_choices() -> None:
    setting = Setting(
        key="x", label="x", description="", group="G", default=1, choices=(1, 2, 3)
    )
    assert setting.choices == (1, 2, 3)


# ------------------------------------------------------------ instance scope


def test_an_instance_setting_needs_an_active_instance(settings_path: Path) -> None:
    setting = _instance_setting()
    store = ConfigStore(settings_path)
    with pytest.raises(ValueError, match="no instance"):
        store.get(setting)
    with pytest.raises(ValueError, match="no instance"):
        store.set(setting, "x")


def test_instance_values_are_independent_per_instance(settings_path: Path) -> None:
    setting = _instance_setting()
    store = ConfigStore(settings_path)
    store.current_instance = "host.a"
    store.set(setting, "a-value")
    store.current_instance = "host.b"
    assert store.get(setting) == ""
    store.set(setting, "b-value")
    store.current_instance = "host.a"
    assert store.get(setting) == "a-value"


def test_instance_values_live_under_the_instances_key(settings_path: Path) -> None:
    setting = _instance_setting()
    store = ConfigStore(settings_path)
    store.current_instance = "host.a"
    store.set(setting, "a-value")
    assert json.loads(settings_path.read_text(encoding="utf-8")) == {
        "instances": {"host.a": {"runners": "a-value"}}
    }


def test_resetting_the_last_instance_value_prunes_the_empty_buckets(
    settings_path: Path,
) -> None:
    setting = _instance_setting()
    store = ConfigStore(settings_path)
    store.current_instance = "host.a"
    store.set(setting, "a-value")
    store.reset(setting)
    assert json.loads(settings_path.read_text(encoding="utf-8")) == {}


def test_resetting_one_instance_leaves_the_others_alone(settings_path: Path) -> None:
    setting = _instance_setting()
    store = ConfigStore(settings_path)
    store.current_instance = "host.a"
    store.set(setting, "a-value")
    store.current_instance = "host.b"
    store.set(setting, "b-value")
    store.reset(setting)
    assert json.loads(settings_path.read_text(encoding="utf-8")) == {
        "instances": {"host.a": {"runners": "a-value"}}
    }


# ------------------------------------------------------------- global config


def test_the_global_store_reports_how_to_configure_it() -> None:
    store = ConfigStore()
    with pytest.raises(RuntimeError, match="configure"):
        _ = store.path


def test_configure_points_the_global_store_at_a_file(tmp_path: Path) -> None:
    ttl = Setting(key="ttl", label="ttl", description="", group="Cache", default=900)
    config.set(ttl, 5)
    assert json.loads(config.path.read_text(encoding="utf-8")) == {"ttl": 5}
    assert config.path.parent == tmp_path


# ---------------------------------------------------------------- rendering


def test_a_marker_and_its_absence_are_the_same_width() -> None:
    """A wider glyph must still leave unmarked rows lined up with marked
    ones -- the blank is measured from the glyph, not assumed to be one cell.
    """
    for glyph in ("◐", "⚠️", "**"):
        marked = marker_text(glyph, "cyan", present=True)
        blank = marker_text(glyph, "cyan", present=False)
        assert cell_len(marked.plain) == cell_len(blank.plain)
        assert blank.plain.strip() == ""


def test_a_marker_carries_the_style_it_was_given() -> None:
    """`tcw` picks no colour of its own; the caller resolves one."""
    marked = marker_text("◐", "bold magenta", present=True)
    assert marked.style == "bold magenta"
