# GS Build

A build hook to generate the **init**.py file and bundle the optional Rust
`graph_sitter_py` PyO3 extension into wheels.

Set `GRAPH_SITTER_SKIP_RUST_EXTENSION_BUILD=1` to build a Python-only wheel.
Set `GRAPH_SITTER_RUST_EXTENSION_PROFILE=debug` to use Cargo's debug profile.
