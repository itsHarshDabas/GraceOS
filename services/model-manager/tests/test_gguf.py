"""Parser tests: ground truth is files written by gguf.GGUFWriter."""

import struct

import pytest

from conftest import write_full
from grace_model_manager import (
    GGUFArraySummary,
    GGUFError,
    GGUFInfo,
    estimate_memory,
    read_gguf,
)


def test_ground_truth_all_value_types(full_gguf):
    info = read_gguf(full_gguf)
    assert isinstance(info, GGUFInfo)
    assert info.version in (2, 3)
    md = info.metadata
    assert md["t_uint8"] == 250
    assert md["t_int8"] == -120
    assert md["t_uint16"] == 60000
    assert md["t_int16"] == -30000
    assert md["t_uint32"] == 3_000_000_000
    assert md["t_int32"] == -2_000_000_000
    assert md["t_float32"] == pytest.approx(1.5)
    assert md["t_bool"] is True
    assert md["t_string"] == "hello-gguf"
    assert md["t_uint64"] == 2**64 - 7
    assert md["t_int64"] == -(2**62)
    assert md["t_float64"] == pytest.approx(2.5)
    assert md["t_small_array"] == [10, 20, 30]
    assert md["t_str_array"] == ["alpha", "beta"]
    # derived fields
    assert info.architecture == "testarch"
    assert info.name == "tiny-test-model"
    assert info.file_type == 2
    assert info.context_length == 4096
    assert info.block_count == 4
    assert info.embedding_length == 32
    assert info.head_count == 8
    assert info.head_count_kv == 2
    # tensor list (no data loaded)
    assert info.tensor_count == 1
    assert len(info.tensors) == 1
    (tensor,) = info.tensors
    assert tensor.name == "blk.0.weight"
    assert tensor.ggml_type == 0  # F32
    # GGUF stores dims in reverse order vs numpy (the reference GGUFReader
    # reverses them back); (2, 3) is stored as [3, 2].
    assert list(tensor.shape) == [3, 2]
    # weights_bytes = file - header and is positive but smaller than file
    est = estimate_memory(info)
    assert 0 < est.weights_bytes < info.file_size
    assert est.weights_bytes == info.file_size - info.header_size


def test_large_array_is_summarised(big_array_gguf):
    info = read_gguf(big_array_gguf)
    summary = info.metadata["tokenizer_vocab"]
    assert isinstance(summary, GGUFArraySummary)
    assert summary.count == 2048
    # full list must not be materialised
    assert info.metadata["t_small_array"] == [10, 20, 30]


def test_kv_cache_math_matches_hand_calculation(full_gguf):
    info = read_gguf(full_gguf)
    ctx = 2048
    est = estimate_memory(info, context_length=ctx, kv_bytes_per_elem=2)
    # 2 * 4 blocks * 2048 ctx * (32 emb * 2 kv / 8 heads) * 2 B
    expected = 2 * 4 * 2048 * (32 * 2 // 8) * 2
    assert est.kv_cache_bytes == expected
    assert est.total_bytes == est.weights_bytes + expected + est.overhead_bytes
    assert est.is_estimate is True
    assert any("kv_cache_bytes" in n for n in est.notes)
    # default ctx falls back to model metadata (4096)
    est_default = estimate_memory(info)
    assert est_default.kv_cache_bytes == 2 * expected


def test_kv_cache_uses_declared_head_widths(tmp_path):
    # Gemma-style: declared head width (16) differs from embedding/heads (32/8 = 4).
    from conftest import write_full

    info = read_gguf(write_full(tmp_path / "gemma_like.gguf", head_dims=(16, 16)))
    assert (info.key_length, info.value_length) == (16, 16)
    est = estimate_memory(info, context_length=1024, kv_bytes_per_elem=2)
    # 4 blocks * 1024 ctx * 2 kv-heads * (16 + 16) * 2 B
    assert est.kv_cache_bytes == 4 * 1024 * 2 * (16 + 16) * 2
    # without declared widths the fallback formula applies
    assert read_gguf(write_full(tmp_path / "plain.gguf")).key_length is None


def test_kv_cache_missing_inputs_give_none(full_gguf):
    info = read_gguf(full_gguf)
    assert info.head_count_kv == 2
    object.__setattr__  # frozen dataclass guard: rebuild instead
    import dataclasses

    bare = dataclasses.replace(
        info,
        architecture=None,
        block_count=None,
        embedding_length=None,
        head_count=None,
        head_count_kv=None,
        context_length=None,
    )
    est = estimate_memory(bare, context_length=None)
    assert est.kv_cache_bytes is None
    assert est.total_bytes == est.weights_bytes + est.overhead_bytes
    assert any("refusing to guess" in n for n in est.notes)


def _write(path, payload: bytes) -> str:
    path.write_bytes(payload)
    return str(path)


def _minimal_header(version=3, n_tensors=0, n_kv=0):
    return b"GGUF" + struct.pack("<IQQ", version, n_tensors, n_kv)


def test_bad_magic(tmp_path):
    with pytest.raises(GGUFError, match="[Bb]ad magic"):
        read_gguf(_write(tmp_path / "x.gguf", b"BAD!" + b"\x00" * 64))


def test_unsupported_version(tmp_path):
    with pytest.raises(GGUFError, match="[Uu]nsupported.*version 1"):
        read_gguf(_write(tmp_path / "x.gguf", _minimal_header(version=1)))


def test_truncated_header_tmp(tmp_path):
    with pytest.raises(GGUFError, match="[Tt]runcat"):
        read_gguf(_write(tmp_path / "x.gguf", b"GG"))


def test_truncated_file_tmp(tmp_path, full_gguf):
    data = full_gguf.read_bytes()
    with pytest.raises(GGUFError, match="[Tt]runcat"):
        read_gguf(_write(tmp_path / "x.gguf", data[: len(data) // 2]))


def test_oversized_string_length_tmp(tmp_path):
    key = b"k"
    payload = (
        _minimal_header(n_kv=1)
        + struct.pack("<Q", len(key))
        + key
        + struct.pack("<I", 8)  # STRING
        + struct.pack("<Q", 2**40)  # absurd length
    )
    with pytest.raises(GGUFError, match="safety limit|exceeds"):
        read_gguf(_write(tmp_path / "x.gguf", payload))


def test_corrupt_kv_count_tmp(tmp_path, full_gguf):
    data = bytearray(full_gguf.read_bytes())
    struct.pack_into("<Q", data, 4 + 4 + 8, 2**60)
    with pytest.raises(GGUFError, match="implausibly|truncated|exceeds"):
        read_gguf(_write(tmp_path / "x.gguf", bytes(data)))


def test_against_writer_metadata_count(tmp_path):
    path = write_full(tmp_path / "counted.gguf")
    info = read_gguf(path)
    # writer always adds general.architecture (+ our keys); all must parse
    assert "general.architecture" in info.metadata
    assert len(info.metadata) >= 20
