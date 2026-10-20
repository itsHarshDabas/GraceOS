from cherrycola import hardware as hw

GB = 1024**3


def _dev(root, name, cls, vendor, vram=None):
    d = root / name
    d.mkdir()
    (d / "class").write_text(cls + "\n")
    (d / "vendor").write_text(vendor + "\n")
    if vram is not None:
        (d / "mem_info_vram_total").write_text(f"{vram}\n")


def test_detect_gpus_from_sysfs(tmp_path, monkeypatch):
    _dev(tmp_path, "0000_00_02.0", "0x030000", "0x8086")
    _dev(tmp_path, "0000_03_00.0", "0x030000", "0x1002", 8 * GB)
    _dev(tmp_path, "0000_00_1f.3", "0x040300", "0x8086")  # audio
    monkeypatch.setattr(hw, "_nvidia_vram", lambda: 0)
    assert hw.detect_gpus(tmp_path) == [hw.Gpu("intel", 0),
                                        hw.Gpu("amd", 8 * GB)]
    assert hw.detect_gpus(tmp_path / "missing") == []


def test_engine_package():
    assert hw.engine_package([hw.Gpu("nvidia", 0)])[0] == "ollama-cuda"
    assert hw.engine_package([hw.Gpu("amd", 8 * GB)])[0] == "ollama-vulkan"
    # An APU's small carve-out isn't worth it.
    assert hw.engine_package([hw.Gpu("amd", GB // 2)])[0] == "ollama"
    assert hw.engine_package([])[0] == "ollama"


def test_recommend_cpu_only():
    r = hw.recommend(16 * GB, [hw.Gpu("intel", 0)])
    assert r["runs_on"] == "cpu" and r["engine"] == "ollama"
    assert r["recommended"] == "qwen3:8b"
    by = {m["model"]: m for m in r["models"]}
    assert by["qwen3:14b"]["fits"] and by["qwen3:14b"]["slow"]
    assert not by["qwen3:32b"]["fits"]


def test_recommend_gpu():
    r = hw.recommend(32 * GB, [hw.Gpu("nvidia", 12 * GB)])
    assert r["runs_on"] == "gpu" and r["engine"] == "ollama-cuda"
    assert r["recommended"] == "qwen3:14b"
    by = {m["model"]: m for m in r["models"]}
    assert by["qwen2.5-coder:14b"]["fits"] and not by["gpt-oss:20b"]["fits"]
    assert not any(m["slow"] for m in r["models"])


def test_recommend_tiny_pc():
    r = hw.recommend(3 * GB, [])
    assert r["recommended"] == "qwen3:1.7b" or r["recommended"] == "qwen3:0.6b"
