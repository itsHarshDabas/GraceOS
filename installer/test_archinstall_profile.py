# python -m pytest installer/  (no archinstall needed)
import ast, importlib.machinery, importlib.util, json
from pathlib import Path

HERE = Path(__file__).parent
CONFIG = json.loads((HERE / "archinstall/grace-candyland.json").read_text())

spec = importlib.util.spec_from_loader("graceinstall", importlib.machinery.SourceFileLoader("graceinstall", str(HERE / "graceinstall")))
gi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gi)


def profile_returns(prop: str) -> list[str]:
    """The list a property of the profile class returns, read without importing archinstall."""
    tree = ast.parse((HERE / "archinstall/grace_candyland.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == prop:
            ret = next(n for n in ast.walk(node) if isinstance(n, ast.Return))
            return ast.literal_eval(ret.value)
    raise AssertionError(f"no {prop} in the profile")


def test_same_repo_and_fix_as_graceinstall():
    assert CONFIG["mirror_config"]["custom_repositories"] == [gi.GRACEOS_REPO]
    assert CONFIG["custom_commands"][0] == gi.DEDUPE_PACMAN_CONF


def test_config_selects_the_profile_file():
    profile = CONFIG["profile_config"]["profile"]
    assert profile["main"] == "Desktop" and profile["details"] == ["Grace Candyland"]
    assert (HERE / "archinstall" / profile["path"]).is_file()
    assert "Grace Candyland" in (HERE / "archinstall/grace_candyland.py").read_text()


def test_profile_installs_the_meta_package():
    packages = profile_returns("packages")
    assert "grace-candyland-desktop" in packages
    assert (HERE.parent / "packages/grace-candyland-desktop/PKGBUILD").is_file()
