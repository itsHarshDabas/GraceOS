# grace-model-manager (T-006)

GGUF metadata reader and serving-memory estimator for GraceOS.

- Parses GGUF headers, metadata KV pairs and tensor infos **without loading
  tensor data**. There is no model loading and no inference here.
- Estimates serving memory (weights approximation + KV cache + fixed
  overhead), always labelled as an estimate.
- CLI: `grace-model info <file.gguf> [--ctx N] [--json]`.

Spec: [GGUF format](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)
(file versions 2 and 3; little-endian). The official `gguf` Python package
(gguf-py, from the llama.cpp repo) is treated as ground truth: the test
suite generates fixtures with `gguf.GGUFWriter` and checks this parser
against them.

## Supported

- GGUF versions 2 and 3 (others are rejected with a clear error).
- All 13 metadata value types: UINT8, INT8, UINT16, INT16, UINT32, INT32,
  FLOAT32, BOOL, STRING, ARRAY, UINT64, INT64, FLOAT64.
- Arrays of strings and of scalar types. Arrays longer than 1024 elements
  are stored as a summary (`element_type` + `count`) and their bytes are
  skipped, so a tokenizer vocab cannot blow up memory.
- Tensor infos (name, shape, ggml type). Tensor data is never read.
- `GGUFInfo`: `version`, `tensor_count`, `metadata` dict, `architecture`
  (`general.architecture`), `name` (`general.name`), `file_type`
  (`general.file_type`), `context_length` / `block_count` /
  `embedding_length` / `head_count` / `head_count_kv` / `key_length` /
  `value_length` (each `None` when absent), `file_size`, `header_size`, and the tensor list.
- `estimate_memory(info, context_length, kv_bytes_per_elem=2,
  overhead_bytes=None)`: `weights_bytes` (file minus header, noted as an
  approximation), `kv_cache_bytes` via
  `blocks * ctx * kv_heads * (key_length + value_length) * bytes_per_elem`
  when the model declares its head widths (e.g. Gemma), otherwise
  `2 * blocks * ctx * (emb * kv_heads / heads) * bytes_per_elem` (`None`
  with a note when any input is missing — never guessed), and a default
  512 MiB overhead labelled as an assumption. Always `is_estimate=True`.
- Truncated or malformed files raise `GGUFError` with a clear message.
  Strings are bounded to 1 MiB and lengths larger than the remaining file
  are refused, so corrupt length fields cannot hang the reader or force
  huge allocations.

## Not supported (yet)

- No tensor loading, no dequantization, no inference or sampling.
- No GGUF writing (use the official `gguf` package for that).
- No big-endian files, no GGUF v1, no sharded-model handling.
- The memory estimate is a planning aid, not a measurement. It does not model
  sliding-window attention, MLA (compressed KV) or per-layer head counts
  stored as arrays; those fall back to the formulas above or to `None`.

## Verified against a real model
`stories260K.gguf` (ggml-org/models, llama arch): all 19 KV keys, 48 tensors
(names, types, shapes) and the data offset match `gguf.GGUFReader` exactly.

## Run the tests

Requires [uv](https://docs.astral.sh/uv/). From this directory:

```sh
uv run pytest -q
```

`uv` creates `.venv/` on first run and installs pytest plus the `gguf`
test-only fixture dependency (with numpy) from the `dev` group. The
`grace-model-manager` runtime itself is stdlib-only (requires-python
`>= 3.12`).

## CLI examples

```sh
uv run grace-model info model.gguf
uv run grace-model info model.gguf --ctx 8192
uv run grace-model info model.gguf --ctx 8192 --json
```
