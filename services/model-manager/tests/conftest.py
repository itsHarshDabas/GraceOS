"""Shared fixtures: tiny GGUF files generated with the official writer."""

import numpy as np
import pytest
from gguf import GGUFWriter

ARCH = "testarch"


def write_full(path, *, big_vocab: int = 0, arch: str = ARCH, head_dims: tuple[int, int] | None = None):
    """Write a tiny GGUF covering every scalar type, an array, and a tensor."""
    w = GGUFWriter(str(path), arch)
    w.add_uint8("t_uint8", 250)
    w.add_int8("t_int8", -120)
    w.add_uint16("t_uint16", 60000)
    w.add_int16("t_int16", -30000)
    w.add_uint32("t_uint32", 3_000_000_000)
    w.add_int32("t_int32", -2_000_000_000)
    w.add_float32("t_float32", 1.5)
    w.add_bool("t_bool", True)
    w.add_string("t_string", "hello-gguf")
    w.add_uint64("t_uint64", 2**64 - 7)
    w.add_int64("t_int64", -(2**62))
    w.add_float64("t_float64", 2.5)
    w.add_array("t_small_array", [10, 20, 30])
    w.add_array("t_str_array", ["alpha", "beta"])
    if big_vocab:
        w.add_array("tokenizer_vocab", [f"tok-{i}" for i in range(big_vocab)])
    w.add_context_length(4096)
    w.add_block_count(4)
    w.add_embedding_length(32)
    w.add_head_count(8)
    w.add_head_count_kv(2)
    if head_dims:
        w.add_key_length(head_dims[0])
        w.add_value_length(head_dims[1])
    w.add_name("tiny-test-model")
    w.add_file_type(2)
    tensor = np.arange(6, dtype=np.float32).reshape(2, 3)
    w.add_tensor("blk.0.weight", tensor)
    w.write_header_to_file()
    w.write_kv_data_to_file()
    w.write_tensors_to_file()
    w.close()
    return path


@pytest.fixture()
def full_gguf(tmp_path):
    return write_full(tmp_path / "full.gguf")


@pytest.fixture()
def big_array_gguf(tmp_path):
    return write_full(tmp_path / "big.gguf", big_vocab=2048)
