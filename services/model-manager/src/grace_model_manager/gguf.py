"""Read-only GGUF metadata parser.

Parses the GGUF header, metadata key/value pairs and tensor infos without
loading any tensor data. Tensor data bytes are never read or memory-mapped.

Spec: https://github.com/ggml-org/ggml/blob/master/docs/gguf.md
(file versions 2 and 3, little-endian).

Safety: untrusted length fields are always bounded. Any single string is
limited to 1 MiB, lengths larger than the remaining file are refused, and
large arrays are summarised instead of materialised, so a corrupt file can
only produce a GGUFError, never a hang or a giant allocation.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_ALIGNMENT",
    "GGUFArraySummary",
    "GGUFError",
    "GGUFInfo",
    "LARGE_ARRAY_THRESHOLD",
    "MAGIC",
    "MAX_STRING_BYTES",
    "SUPPORTED_VERSIONS",
    "TensorInfo",
    "read_gguf",
]

MAGIC = b"GGUF"
SUPPORTED_VERSIONS = (2, 3)
MAX_STRING_BYTES = 1024 * 1024  # 1 MiB bound on any single string
LARGE_ARRAY_THRESHOLD = 1024  # arrays longer than this become summaries
DEFAULT_ALIGNMENT = 32  # GGUF_DEFAULT_ALIGNMENT in the reference writer
_MAX_KV_COUNT = 10_000_000  # implausibility caps: no real file is near
_MAX_TENSOR_COUNT = 10_000_000  # these; they only stop corrupt counts.
_MAX_DIMS = 64  # spec allows 4 (GGML_MAX_DIMS); 64 is generous headroom.

# GGUF value type ids (spec section "metadata").
VT_UINT8 = 0
VT_INT8 = 1
VT_UINT16 = 2
VT_INT16 = 3
VT_UINT32 = 4
VT_INT32 = 5
VT_FLOAT32 = 6
VT_BOOL = 7
VT_STRING = 8
VT_ARRAY = 9
VT_UINT64 = 10
VT_INT64 = 11
VT_FLOAT64 = 12

_VALUE_TYPE_NAMES = {
    VT_UINT8: "UINT8",
    VT_INT8: "INT8",
    VT_UINT16: "UINT16",
    VT_INT16: "INT16",
    VT_UINT32: "UINT32",
    VT_INT32: "INT32",
    VT_FLOAT32: "FLOAT32",
    VT_BOOL: "BOOL",
    VT_STRING: "STRING",
    VT_ARRAY: "ARRAY",
    VT_UINT64: "UINT64",
    VT_INT64: "INT64",
    VT_FLOAT64: "FLOAT64",
}

# Scalar value type -> struct format character (little-endian by caller).
_SCALAR_FORMATS = {
    VT_UINT8: "B",
    VT_INT8: "b",
    VT_UINT16: "H",
    VT_INT16: "h",
    VT_UINT32: "I",
    VT_INT32: "i",
    VT_FLOAT32: "f",
    VT_UINT64: "Q",
    VT_INT64: "q",
    VT_FLOAT64: "d",
}

_FIXED_SIZES = {
    VT_UINT8: 1,
    VT_INT8: 1,
    VT_UINT16: 2,
    VT_INT16: 2,
    VT_UINT32: 4,
    VT_INT32: 4,
    VT_FLOAT32: 4,
    VT_BOOL: 1,
    VT_UINT64: 8,
    VT_INT64: 8,
    VT_FLOAT64: 8,
}


class GGUFError(ValueError):
    """Raised when a file is not a readable GGUF file."""


@dataclass(frozen=True)
class GGUFArraySummary:
    """Placeholder for a metadata array too large to materialise."""

    element_type: str
    element_type_id: int
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_type": self.element_type,
            "element_type_id": self.element_type_id,
            "count": self.count,
            "content": "skipped (large array)",
        }


@dataclass(frozen=True)
class TensorInfo:
    """One tensor entry from the GGUF tensor-info table (no data)."""

    name: str
    shape: tuple[int, ...]  # dims in the order stored in the file
    ggml_type: int


@dataclass(frozen=True)
class GGUFInfo:
    """Parsed GGUF metadata and tensor infos (never tensor data)."""

    version: int
    tensor_count: int
    metadata: dict[str, Any]
    architecture: str | None
    name: str | None
    file_type: int | None
    context_length: int | None
    block_count: int | None
    embedding_length: int | None
    head_count: int | None
    head_count_kv: int | None
    key_length: int | None  # per-head K width, when the model declares it
    value_length: int | None  # per-head V width, when the model declares it
    file_size: int
    header_size: int  # aligned offset where tensor data starts
    alignment: int
    tensors: list[TensorInfo]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "tensor_count": self.tensor_count,
            "metadata": {k: _jsonable(v) for k, v in self.metadata.items()},
            "architecture": self.architecture,
            "name": self.name,
            "file_type": self.file_type,
            "context_length": self.context_length,
            "block_count": self.block_count,
            "embedding_length": self.embedding_length,
            "head_count": self.head_count,
            "head_count_kv": self.head_count_kv,
            "key_length": self.key_length,
            "value_length": self.value_length,
            "file_size": self.file_size,
            "header_size": self.header_size,
            "alignment": self.alignment,
            "tensors": [
                {"name": t.name, "shape": list(t.shape), "ggml_type": t.ggml_type}
                for t in self.tensors
            ],
        }


class _Cursor:
    """Bounded little-endian reader over a fixed-size file."""

    __slots__ = ("_fh", "_size")

    def __init__(self, fh: Any, size: int) -> None:
        self._fh = fh
        self._size = size

    def tell(self) -> int:
        return self._fh.tell()

    @property
    def remaining(self) -> int:
        return self._size - self._fh.tell()

    def take(self, n: int, what: str) -> bytes:
        if n < 0:
            raise GGUFError(f"{what}: negative length {n}; file is corrupt")
        data = self._fh.read(n)
        if len(data) != n:
            raise GGUFError(
                f"truncated file while reading {what}: "
                f"needed {n} bytes, got {len(data)} "
                f"at offset {self._fh.tell() - len(data)}"
            )
        return data

    def skip(self, n: int, what: str) -> None:
        if n < 0:
            raise GGUFError(f"{what}: negative skip {n}; file is corrupt")
        if n > self.remaining:
            raise GGUFError(
                f"truncated file while skipping {what}: "
                f"needed {n} bytes, only {self.remaining} remain"
            )
        self._fh.seek(n, os.SEEK_CUR)

    def u32(self, what: str) -> int:
        return struct.unpack("<I", self.take(4, what))[0]

    def u64(self, what: str) -> int:
        return struct.unpack("<Q", self.take(8, what))[0]

    def string(self, what: str = "string") -> str:
        (length,) = struct.unpack("<Q", self.take(8, f"{what} length"))
        if length > MAX_STRING_BYTES:
            raise GGUFError(
                f"{what}: length {length} bytes exceeds the "
                f"{MAX_STRING_BYTES}-byte safety limit; file is corrupt"
            )
        if length > self.remaining:
            raise GGUFError(
                f"{what}: length {length} bytes exceeds "
                f"{self.remaining} remaining bytes; file is truncated"
            )
        raw = self.take(length, what)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GGUFError(f"{what}: invalid UTF-8: {exc}") from exc


def _read_scalar(cur: _Cursor, vtype: int, what: str) -> Any:
    if vtype == VT_BOOL:
        return cur.take(1, what)[0] != 0
    fmt = _SCALAR_FORMATS.get(vtype)
    if fmt is None:
        raise GGUFError(f"{what}: unknown value type id {vtype}; file is corrupt")
    size = _FIXED_SIZES[vtype]
    return struct.unpack("<" + fmt, cur.take(size, what))[0]


def _check_array_fits(cur: _Cursor, elem: int, count: int, what: str) -> None:
    min_size = 8 if elem == VT_STRING else _FIXED_SIZES[elem]
    if count * min_size > cur.remaining:
        raise GGUFError(
            f"{what}: array of {count} x "
            f"{_VALUE_TYPE_NAMES.get(elem, elem)} needs at least "
            f"{count * min_size} bytes but only {cur.remaining} remain; "
            "file is truncated"
        )


def _skip_array(cur: _Cursor, elem: int, count: int, what: str) -> None:
    if elem == VT_STRING:
        for i in range(count):
            length = cur.u64(f"{what}[{i}] length")
            if length > MAX_STRING_BYTES:
                raise GGUFError(
                    f"{what}[{i}]: length {length} bytes exceeds the "
                    f"{MAX_STRING_BYTES}-byte safety limit; file is corrupt"
                )
            if length > cur.remaining:
                raise GGUFError(
                    f"{what}[{i}]: length {length} bytes exceeds "
                    f"{cur.remaining} remaining bytes; file is truncated"
                )
            cur.skip(length, f"{what}[{i}] data")
    else:
        cur.skip(count * _FIXED_SIZES[elem], f"{what} array data")


def _read_value(cur: _Cursor, vtype: int, what: str) -> Any:
    if vtype in _SCALAR_FORMATS or vtype == VT_BOOL:
        return _read_scalar(cur, vtype, what)
    if vtype == VT_STRING:
        return cur.string(what)
    if vtype == VT_ARRAY:
        elem = cur.u32(f"{what} array element type")
        count = cur.u64(f"{what} array length")
        if elem == VT_ARRAY:
            raise GGUFError(f"{what}: nested arrays are not supported")
        if elem not in _VALUE_TYPE_NAMES:
            raise GGUFError(
                f"{what}: unknown array element type id {elem}; file is corrupt"
            )
        _check_array_fits(cur, elem, count, what)
        if count > LARGE_ARRAY_THRESHOLD:
            _skip_array(cur, elem, count, what)
            return GGUFArraySummary(
                element_type=_VALUE_TYPE_NAMES[elem],
                element_type_id=elem,
                count=count,
            )
        if elem == VT_STRING:
            return [cur.string(f"{what}[{i}]") for i in range(count)]
        if count == 0:
            return []
        fmt = _SCALAR_FORMATS[elem]
        size = _FIXED_SIZES[elem]
        raw = cur.take(count * size, f"{what} array data")
        return list(struct.unpack("<" + fmt * count, raw))
    raise GGUFError(f"{what}: unknown value type id {vtype}; file is corrupt")


def read_gguf(path: str | os.PathLike[str]) -> GGUFInfo:
    """Parse GGUF metadata from *path* without loading tensor data."""
    p = Path(path)
    try:
        fh = p.open("rb")
    except OSError as exc:
        raise GGUFError(f"cannot open {p}: {exc}") from exc
    with fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(0)
        cur = _Cursor(fh, size)

        magic = fh.read(4)
        if len(magic) != 4:
            raise GGUFError(
                f"{p}: file is {size} bytes; too small for a GGUF header"
            )
        if magic != MAGIC:
            raise GGUFError(
                f"{p}: bad magic {magic!r}; expected b'GGUF' (not a GGUF file)"
            )

        version = cur.u32("version")
        if version not in SUPPORTED_VERSIONS:
            raise GGUFError(
                f"{p}: unsupported GGUF version {version}; "
                f"supported versions are {list(SUPPORTED_VERSIONS)}"
            )
        tensor_count = cur.u64("tensor count")
        kv_count = cur.u64("metadata KV count")
        if tensor_count > _MAX_TENSOR_COUNT:
            raise GGUFError(
                f"{p}: tensor count {tensor_count} is implausibly large; "
                "file is likely corrupt"
            )
        if kv_count > _MAX_KV_COUNT:
            raise GGUFError(
                f"{p}: metadata KV count {kv_count} is implausibly large; "
                "file is likely corrupt"
            )
        # Lower bounds: any KV pair needs >= 13 bytes of header,
        # any tensor info needs >= 24 bytes.
        if kv_count * 13 > cur.remaining:
            raise GGUFError(
                f"{p}: metadata KV count {kv_count} exceeds the "
                f"{cur.remaining} remaining bytes; file is truncated"
            )
        if tensor_count * 24 > cur.remaining:
            raise GGUFError(
                f"{p}: tensor count {tensor_count} exceeds the "
                f"{cur.remaining} remaining bytes; file is truncated"
            )

        metadata: dict[str, Any] = {}
        for i in range(kv_count):
            key = cur.string(f"metadata key #{i}")
            vtype = cur.u32(f"value type of {key!r}")
            metadata[key] = _read_value(cur, vtype, f"value of {key!r}")

        tensors: list[TensorInfo] = []
        for i in range(tensor_count):
            tname = cur.string(f"tensor #{i} name")
            n_dims = cur.u32(f"dimension count of tensor {tname!r}")
            if n_dims > _MAX_DIMS:
                raise GGUFError(
                    f"tensor {tname!r}: dimension count {n_dims} exceeds "
                    f"{_MAX_DIMS}; file is corrupt"
                )
            if n_dims * 8 > cur.remaining:
                raise GGUFError(
                    f"tensor {tname!r}: {n_dims} dimensions need "
                    f"{n_dims * 8} bytes but only {cur.remaining} remain; "
                    "file is truncated"
                )
            dims = tuple(
                cur.u64(f"dimension {d} of tensor {tname!r}") for d in range(n_dims)
            )
            ggml_type = cur.u32(f"type of tensor {tname!r}")
            offset = cur.u64(f"offset of tensor {tname!r}")
            if offset > size:
                raise GGUFError(
                    f"tensor {tname!r}: data offset {offset} exceeds "
                    f"file size {size}; file is truncated"
                )
            tensors.append(TensorInfo(name=tname, shape=dims, ggml_type=ggml_type))

        raw_alignment = metadata.get("general.alignment")
        alignment = (
            raw_alignment
            if isinstance(raw_alignment, int)
            and not isinstance(raw_alignment, bool)
            and raw_alignment > 0
            else DEFAULT_ALIGNMENT
        )
        header_size = _align_up(cur.tell(), alignment)
        if header_size > size:
            raise GGUFError(
                f"{p}: header extends to byte {header_size} but the file is "
                f"only {size} bytes; file is truncated"
            )

        architecture = _as_str(metadata.get("general.architecture"))
        if architecture is not None:
            prefix = architecture + "."
            context_length = _as_int(metadata.get(prefix + "context_length"))
            block_count = _as_int(metadata.get(prefix + "block_count"))
            embedding_length = _as_int(metadata.get(prefix + "embedding_length"))
            head_count = _as_int(metadata.get(prefix + "attention.head_count"))
            head_count_kv = _as_int(
                metadata.get(prefix + "attention.head_count_kv")
            )
            key_length = _as_int(metadata.get(prefix + "attention.key_length"))
            value_length = _as_int(metadata.get(prefix + "attention.value_length"))
        else:
            context_length = block_count = embedding_length = None
            head_count = head_count_kv = key_length = value_length = None

        return GGUFInfo(
            version=version,
            tensor_count=tensor_count,
            metadata=metadata,
            architecture=architecture,
            name=_as_str(metadata.get("general.name")),
            file_type=_as_int(metadata.get("general.file_type")),
            context_length=context_length,
            block_count=block_count,
            embedding_length=embedding_length,
            head_count=head_count,
            head_count_kv=head_count_kv,
            key_length=key_length,
            value_length=value_length,
            file_size=size,
            header_size=header_size,
            alignment=alignment,
            tensors=tensors,
        )


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _jsonable(value: Any) -> Any:
    if isinstance(value, GGUFArraySummary):
        return value.to_dict()
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _align_up(n: int, alignment: int) -> int:
    return ((n + alignment - 1) // alignment) * alignment
