# 0003 Python for first service and CLI prototypes

Problem: the Agent Hub, model manager and hardware detection need a language now, so parallel contributors don't each pick a different one.

Options: Python, Rust, Go.

Chosen: Python 3, stdlib first, `uv` for dependencies, `pytest` for tests. Python and uv already ship on the live ISO (`iso/packages.x86_64`); it is fastest to prototype in; and the GGUF tooling (`gguf` package) and ML ecosystem are Python-native.

Trade-offs: higher memory and startup cost than Rust or Go for long-running daemons; packaging needs care in PKGBUILDs.

Revisit: when a service becomes a long-running daemon on the hot path (e.g. the inference API proxy or the Intelligence Layer broker), or when profiling shows Python is the bottleneck.

Not covered: UI toolkits. The desktop shell decides its own stack in its own ADR (T-003).
