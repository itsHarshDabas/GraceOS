"""Serving-memory estimates for GGUF models.

Everything here is an estimate, and every number says so: weights are
approximated from the file size, the KV cache follows the standard formula
from known metadata only (never guessed), and runtime overhead is a fixed
documented allowance.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .gguf import GGUFInfo

__all__ = [
    "DEFAULT_KV_BYTES_PER_ELEM",
    "DEFAULT_OVERHEAD_BYTES",
    "MemoryEstimate",
    "estimate_memory",
]

#: Fixed runtime allowance used when the caller passes no overhead value:
#: 512 MiB for the runtime, buffers and fragmentation. Not measured.
DEFAULT_OVERHEAD_BYTES = 512 * 1024 * 1024

#: Default KV-cache element size: 2 bytes (fp16 / q8-style cache).
DEFAULT_KV_BYTES_PER_ELEM = 2


@dataclass(frozen=True)
class MemoryEstimate:
    weights_bytes: int
    kv_cache_bytes: int | None
    overhead_bytes: int
    total_bytes: int
    is_estimate: bool = True
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "weights_bytes": self.weights_bytes,
            "kv_cache_bytes": self.kv_cache_bytes,
            "overhead_bytes": self.overhead_bytes,
            "total_bytes": self.total_bytes,
            "is_estimate": self.is_estimate,
            "notes": list(self.notes),
        }


def estimate_memory(
    info: GGUFInfo,
    context_length: int | None = None,
    kv_bytes_per_elem: int = DEFAULT_KV_BYTES_PER_ELEM,
    overhead_bytes: int | None = None,
) -> MemoryEstimate:
    """Estimate serving memory for a parsed GGUF model.

    Args:
        info: result of :func:`read_gguf`.
        context_length: KV-cache context to plan for. Defaults to the
            model's own ``<arch>.context_length`` metadata.
        kv_bytes_per_elem: bytes per KV-cache element (default 2).
        overhead_bytes: fixed runtime allowance; defaults to
            :data:`DEFAULT_OVERHEAD_BYTES`.
    """
    notes: list[str] = []

    weights_bytes = info.file_size - info.header_size
    notes.append(
        "weights_bytes = file_size - header_size; an approximation that "
        "includes tensor data plus alignment padding, not an exact weight count."
    )

    if kv_bytes_per_elem is None or kv_bytes_per_elem <= 0:
        raise ValueError(
            f"kv_bytes_per_elem must be a positive number, got {kv_bytes_per_elem!r}"
        )

    if overhead_bytes is None:
        overhead = DEFAULT_OVERHEAD_BYTES
        notes.append(
            f"overhead_bytes assumes a fixed {overhead}-byte "
            "(512 MiB) allowance for the runtime, buffers and fragmentation; "
            "not measured."
        )
    else:
        if overhead_bytes < 0:
            raise ValueError(
                f"overhead_bytes must be >= 0, got {overhead_bytes!r}"
            )
        overhead = overhead_bytes
        notes.append("overhead_bytes uses the caller-provided value.")

    if context_length is not None:
        ctx = context_length
        notes.append(f"context length {ctx} supplied by the caller.")
    else:
        ctx = info.context_length
        if ctx is not None:
            notes.append(
                f"context length {ctx} taken from model metadata "
                f"({info.architecture}.context_length)."
            )

    def _ok(v: int | None) -> bool:
        return v is not None and not isinstance(v, bool) and v > 0

    # Models that declare per-head K/V widths (e.g. Gemma) must use them;
    # embedding_length / head_count is only the fallback head size.
    explicit_heads = _ok(info.key_length) and _ok(info.value_length)
    required = [
        ("block_count", info.block_count),
        ("context_length", ctx),
        ("head_count_kv", info.head_count_kv),
    ]
    if not explicit_heads:
        required += [
            ("embedding_length", info.embedding_length),
            ("head_count", info.head_count),
        ]
    missing = [label for label, value in required if not _ok(value)]

    kv_cache_bytes: int | None
    if missing:
        kv_cache_bytes = None
        notes.append(
            "kv_cache_bytes unknown: missing "
            + ", ".join(missing)
            + "; refusing to guess."
        )
    elif explicit_heads:
        assert ctx is not None and info.block_count and info.head_count_kv
        assert info.key_length and info.value_length
        kv_cache_bytes = (
            info.block_count
            * ctx
            * info.head_count_kv
            * (info.key_length + info.value_length)
            * kv_bytes_per_elem
        )
        notes.append(
            f"kv_cache_bytes = {info.block_count} blocks * {ctx} ctx * "
            f"{info.head_count_kv} kv-heads * ({info.key_length} key + "
            f"{info.value_length} value width) * {kv_bytes_per_elem} B/elem."
        )
    else:
        assert ctx is not None  # guaranteed: else "context_length" in missing
        assert info.block_count is not None
        assert info.embedding_length is not None
        assert info.head_count is not None
        assert info.head_count_kv is not None
        numerator = (
            2
            * info.block_count
            * ctx
            * info.embedding_length
            * info.head_count_kv
            * kv_bytes_per_elem
        )
        if numerator % info.head_count == 0:
            kv_cache_bytes = numerator // info.head_count
        else:
            kv_cache_bytes = int(round(numerator / info.head_count))
            notes.append(
                "KV-cache head dimensions do not divide evenly; "
                "kv_cache_bytes was rounded to the nearest byte."
            )
        notes.append(
            "kv_cache_bytes = 2 * "
            f"{info.block_count} blocks * {ctx} ctx * "
            f"({info.embedding_length} emb * "
            f"{info.head_count_kv} kv-heads / {info.head_count} heads) * "
            f"{kv_bytes_per_elem} B/elem."
        )

    total_bytes = weights_bytes + overhead + (kv_cache_bytes or 0)
    if kv_cache_bytes is None:
        notes.append("total_bytes excludes the KV cache (unknown).")

    return MemoryEstimate(
        weights_bytes=weights_bytes,
        kv_cache_bytes=kv_cache_bytes,
        overhead_bytes=overhead,
        total_bytes=total_bytes,
        is_estimate=True,
        notes=notes,
    )
