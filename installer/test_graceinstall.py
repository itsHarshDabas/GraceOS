# python -m pytest installer/  (no root, no archinstall needed)
import importlib.machinery, importlib.util, json, shutil, subprocess
from pathlib import Path

import pytest

path = str(Path(__file__).with_name("graceinstall"))
spec = importlib.util.spec_from_loader("graceinstall", importlib.machinery.SourceFileLoader("graceinstall", path))
gi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gi)

PACKAGES = """# --- GraceOS base [minimal] ---
git
yay-bin
# a comment inside a section
# --- GraceOS desktop ---
hyprland

# --- GraceOS AI ---
cherrycolallm
"""


def test_package_sets():
    full, minimal = gi.package_sets(PACKAGES)
    assert full == ["git", "yay-bin", "hyprland", "cherrycolallm"]
    assert minimal == ["git", "yay-bin"]  # a plain comment doesn't end the [minimal] section


def test_full_with_user_override(tmp_path, monkeypatch):
    (tmp_path / "packages").write_text(PACKAGES)
    monkeypatch.setattr(gi, "SHARE", tmp_path)
    user = tmp_path / "user.json"
    mine = {"name": "mine", "url": "https://example.org", "sign_check": "Required", "sign_option": "TrustedOnly"}
    user.write_text(json.dumps({"hostname": "box", "mirror_config": {"custom_repositories": [mine]}}))

    config, rest = gi.merged_config(["--full", "--config", str(user), "--silent"])

    assert config["packages"] == ["git", "yay-bin", "hyprland", "cherrycolallm"]
    assert config["hostname"] == "box"  # user wins
    assert config["network_config"] == {"type": "nm"}  # default kept
    assert config["mirror_config"]["custom_repositories"] == [gi.GRACEOS_REPO, mine]  # GraceOS repo always kept
    assert "app_config" in config
    assert rest == ["--silent"]


def test_minimal_asks_and_has_no_desktop(tmp_path, monkeypatch):
    (tmp_path / "packages").write_text(PACKAGES)
    monkeypatch.setattr(gi, "SHARE", tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "2")

    config, rest = gi.merged_config([])

    assert config["packages"] == ["git", "yay-bin"]
    assert "app_config" not in config
    assert config["mirror_config"]["custom_repositories"] == [gi.GRACEOS_REPO]
    assert config["custom_commands"] == [gi.DEDUPE_PACMAN_CONF]


def test_user_commands_run_after_the_pacman_conf_fix(tmp_path, monkeypatch):
    (tmp_path / "packages").write_text(PACKAGES)
    monkeypatch.setattr(gi, "SHARE", tmp_path)
    user = tmp_path / "user.json"
    user.write_text(json.dumps({"custom_commands": ["echo hi"]}))

    config, _ = gi.merged_config(["--minimal", "--config", str(user)])

    assert config["custom_commands"] == [gi.DEDUPE_PACMAN_CONF, "echo hi"]


@pytest.mark.skipif(not shutil.which("sh") or not shutil.which("awk"), reason="needs sh and awk")
def test_dedupe_keeps_the_first_copy_of_each_section(tmp_path):
    conf = tmp_path / "etc" / "pacman.conf"
    conf.parent.mkdir()
    conf.write_text("[options]\nColor\n\n[core]\nInclude = m\n\n[graceos]\nServer = a\n\n"
                    "[graceos]\nServer = a\n\n[mine]\nServer = b\n\n[mine]\nServer = b\n")
    subprocess.run(["sh", "-c", gi.DEDUPE_PACMAN_CONF.replace("/etc/", f"{tmp_path.as_posix()}/etc/")], check=True)
    assert conf.read_text() == ("[options]\nColor\n\n[core]\nInclude = m\n\n[graceos]\nServer = a\n\n"
                                "[mine]\nServer = b\n\n")


def test_gpu_packages_only_for_full(tmp_path, monkeypatch):
    (tmp_path / "packages").write_text(PACKAGES)
    monkeypatch.setattr(gi, "SHARE", tmp_path)
    rtx = [("0x030000", "0x10de", "0x2684")]
    full = gi.defaults("full", rtx)
    assert full["packages"][-3:] == ["nvidia-open", "nvidia-utils", "libva-nvidia-driver"]
    assert any("nvidia_drm modeset=1" in c for c in full["custom_commands"])
    assert full["custom_commands"][0] == gi.DEDUPE_PACMAN_CONF
    minimal = gi.defaults("minimal", rtx)
    assert minimal["packages"] == ["git", "yay-bin"] and minimal["custom_commands"] == [gi.DEDUPE_PACMAN_CONF]


def test_graceinstall_flags_are_not_passed_to_archinstall(tmp_path, monkeypatch):
    (tmp_path / "packages").write_text(PACKAGES)
    monkeypatch.setattr(gi, "SHARE", tmp_path)
    allowed, rest = gi.take_flag(["--allow-erase", "/dev/sda", "--silent", "--allow-erase", "/dev/sdb"], "--allow-erase", True)
    assert allowed == ["/dev/sda", "/dev/sdb"] and rest == ["--silent"]
    config, rest = gi.merged_config(["--full", "--rtc-local", "--silent"])
    assert rest == ["--silent"] and config["custom_commands"][-1] == gi.dualboot.RTC_LOCAL_COMMAND
