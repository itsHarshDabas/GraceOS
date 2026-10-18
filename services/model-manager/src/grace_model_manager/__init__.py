"""grace_model_manager: GGUF metadata reader and memory estimator.

GraceOS task T-006. Reads GGUF file headers, metadata and tensor infos
without loading tensor data, and estimates serving memory. stdlib only.
"""

from .gguf import (
    DEFAULT_ALIGNMENT,
    GGUFArraySummary,
    GGUFError,
    GGUFInfo,
    LARGE_ARRAY_THRESHOLD,
    MAX_STRING_BYTES,
    SUPPORTED_VERSIONS,
    TensorInfo,
    read_gguf,
)
from .memory import (
    DEFAULT_KV_BYTES_PER_ELEM,
    DEFAULT_OVERHEAD_BYTES,
    MemoryEstimate,
    estimate_memory,
)

__all__ = [
    "DEFAULT_ALIGNMENT",
    "DEFAULT_KV_BYTES_PER_ELEM",
    "DEFAULT_OVERHEAD_BYTES",
    "GGUFArraySummary",
    "GGUFError",
    "GGUFInfo",
    "LARGE_ARRAY_THRESHOLD",
    "MAX_STRING_BYTES",
    "SUPPORTED_VERSIONS",
    "MemoryEstimate",
    "TensorInfo",
    "estimate_memory",
    "read_gguf",
]

__version__ = "0.1.0"
