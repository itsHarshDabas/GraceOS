# python -m pytest installer/  (no root, no archinstall needed)
import importlib.machinery, importlib.util, json
from pathlib import Path

path = str(Path(__file__).with_name("graceinstall"))
spec = importlib.util.spec_from_loader("graceinstall", importlib.machinery.SourceFileLoader("graceinstall", path))
gi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gi)


def test_defaults_and_user_override(tmp_path, monkeypatch):
    (tmp_path / "packages").write_text("hyprland\n# comment\n\nfoot\n")
    monkeypatch.setattr(gi, "SHARE", tmp_path)
    user = tmp_path / "user.json"
    user.write_text(json.dumps({"hostname": "box", "custom_commands": ["echo hi"]}))

    config, rest = gi.merged_config(["--config", str(user), "--silent"])

    assert config["packages"] == ["hyprland", "foot"]
    assert config["hostname"] == "box"  # user wins
    assert config["network_config"] == {"type": "nm"}  # default kept
    assert config["custom_commands"] == gi.GRACE_COMMANDS + ["echo hi"]  # GraceOS step always runs first
    assert rest == ["--silent"]


def test_add_grace_refuses_without_live_files(tmp_path, monkeypatch):
    monkeypatch.setattr(gi, "FROM_LIVE", ["definitely/not/here"])
    try:
        gi.add_grace(tmp_path)
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")
