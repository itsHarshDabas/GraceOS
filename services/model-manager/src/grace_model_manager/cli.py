"""CLI: ``grace-model info <file.gguf> [--ctx N] [--json]``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .gguf import GGUFArraySummary, GGUFError, read_gguf
from .memory import estimate_memory

__all__ = ["build_parser", "main", "run"]

_MAX_TENSORS_SHOWN = 50
_MAX_VALUE_REPR = 160


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grace-model", description="GraceOS model manager (GGUF metadata)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    info = sub.add_parser("info", help="show GGUF metadata and a memory estimate")
    info.add_argument("file", help="path to a .gguf file")
    info.add_argument(
        "--ctx",
        type=int,
        default=None,
        help="context length to plan the KV cache for "
        "(default: the model's own <arch>.context_length)",
    )
    info.add_argument(
        "--json",
        action="store_true",
        help="print machine-readable JSON instead of human-readable text",
    )
    return parser


def _fmt_bytes(n: int | None) -> str:
    if n is None:
        return "unknown"
    if n >= 1024**3:
        return f"{n} bytes ({n / 1024**3:.2f} GiB)"
    if n >= 1024**2:
        return f"{n} bytes ({n / 1024**2:.1f} MiB)"
    if n >= 1024:
        return f"{n} bytes ({n / 1024:.1f} KiB)"
    return f"{n} bytes"


def _short(value: Any) -> str:
    text = repr(value)
    if len(text) > _MAX_VALUE_REPR:
        return text[: _MAX_VALUE_REPR - 1] + "…"
    return text


def _jsonable_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, GGUFArraySummary):
            out[key] = value.to_dict()
        elif isinstance(value, (list, tuple)):
            out[key] = list(value)
        else:
            out[key] = value
    return out


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "info":
        try:
            info = read_gguf(args.file)
        except GGUFError as exc:
            print(f"grace-model: error: {exc}", file=sys.stderr)
            return 1
        estimate = estimate_memory(info, context_length=args.ctx)
        if args.json:
            payload = {
                "file": str(args.file),
                "metadata": _jsonable_metadata(info.metadata),
                "architecture": info.architecture,
                "name": info.name,
                "file_type": info.file_type,
                "context_length": info.context_length,
                "block_count": info.block_count,
                "embedding_length": info.embedding_length,
                "head_count": info.head_count,
                "head_count_kv": info.head_count_kv,
                "file_size": info.file_size,
                "header_size": info.header_size,
                "tensors": info.to_dict()["tensors"],
                "estimate": estimate.to_dict(),
            }
            print(json.dumps(payload, indent=2))
            return 0
        lines = [
            f"File:         {args.file}",
            f"Model:        {info.name if info.name is not None else '-'}",
            f"Architecture: {info.architecture if info.architecture is not None else '-'}",
            f"GGUF version: {info.version}",
            f"File type:    {info.file_type if info.file_type is not None else '-'}",
            f"Tensors:      {len(info.tensors)}",
            f"Context:      {info.context_length if info.context_length is not None else '-'}",
            f"Blocks:       {info.block_count if info.block_count is not None else '-'}",
            f"Embedding:    {info.embedding_length if info.embedding_length is not None else '-'}",
            f"Heads:        {info.head_count if info.head_count is not None else '-'}"
            + (
                f" (kv: {info.head_count_kv})"
                if info.head_count_kv is not None
                else ""
            ),
            f"File size:    {_fmt_bytes(info.file_size)}",
            f"Weights:      {_fmt_bytes(estimate.weights_bytes)} (estimate)",
            f"KV cache:     {_fmt_bytes(estimate.kv_cache_bytes)} (estimate)",
            f"Overhead:     {_fmt_bytes(estimate.overhead_bytes)} (assumption)",
            f"Total:        {_fmt_bytes(estimate.total_bytes)} (estimate)",
            "",
            f"Metadata ({len(info.metadata)} keys):",
        ]
        for key, value in info.metadata.items():
            lines.append(f"  {key} = {_short(value)}")
        lines.append("")
        lines.append(f"Tensor infos ({len(info.tensors)}):")
        for tensor in info.tensors[:_MAX_TENSORS_SHOWN]:
            lines.append(
                f"  {tensor.name} shape={list(tensor.shape)} "
                f"ggml_type={tensor.ggml_type}"
            )
        if len(info.tensors) > _MAX_TENSORS_SHOWN:
            lines.append(
                f"  … and {len(info.tensors) - _MAX_TENSORS_SHOWN} more"
            )
        lines.append("")
        lines.append("Notes:")
        for note in estimate.notes:
            lines.append(f"  - {note}")
        print("\n".join(lines))
        return 0
    return 2  # pragma: no cover - argparse enforces the subcommand


def main(argv: Sequence[str] | None = None) -> int:
    """Console-script entry point (``[project.scripts]``)."""
    return run(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
