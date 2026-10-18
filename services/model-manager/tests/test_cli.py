"""CLI tests: grace-model info in human and JSON modes."""

import json
import subprocess
import sys

import pytest

from grace_model_manager.cli import run


def test_info_human_output(full_gguf, capsys):
    assert run(["info", str(full_gguf)]) == 0
    out = capsys.readouterr().out
    assert "tiny-test-model" in out
    assert "testarch" in out
    assert "KV cache" in out
    assert "estimate" in out.lower()


def test_info_json_output(full_gguf, capsys):
    assert run(["info", str(full_gguf), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["architecture"] == "testarch"
    assert payload["context_length"] == 4096
    assert payload["estimate"]["is_estimate"] is True
    assert payload["estimate"]["kv_cache_bytes"] is not None
    assert len(payload["tensors"]) == 1


def test_info_json_with_ctx(full_gguf, capsys):
    assert run(["info", str(full_gguf), "--ctx", "512", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    expected = 2 * 4 * 512 * (32 * 2 // 8) * 2
    assert payload["estimate"]["kv_cache_bytes"] == expected


def test_info_missing_file(capsys):
    assert run(["info", "does-not-exist.gguf"]) == 1
    assert "error" in capsys.readouterr().err.lower()


def test_info_bad_file(tmp_path, capsys):
    bad = tmp_path / "bad.gguf"
    bad.write_bytes(b"not a gguf file at all..............")
    assert run(["info", str(bad)]) == 1
    assert "error" in capsys.readouterr().err.lower()


def test_console_script_entrypoint(full_gguf):
    proc = subprocess.run(
        [sys.executable, "-m", "grace_model_manager.cli", "info", str(full_gguf)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert "tiny-test-model" in proc.stdout


def test_big_array_json_is_summary(big_array_gguf, capsys):
    assert run(["info", str(big_array_gguf), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["metadata"]["tokenizer_vocab"]["count"] == 2048


@pytest.mark.parametrize("overhead", [-1])
def test_bad_overhead_rejected(full_gguf, overhead):
    from grace_model_manager import estimate_memory, read_gguf

    with pytest.raises(ValueError, match="overhead_bytes"):
        estimate_memory(read_gguf(full_gguf), overhead_bytes=overhead)
