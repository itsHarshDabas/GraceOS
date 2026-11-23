# GraceOS Net overlay

`build/build-iso.sh net` builds GraceOS Net from the normal profile in `iso/` plus this directory:
`airootfs/` here is copied over the profile's `airootfs/`. The rest of the Net differences
(package list, boot entries, pinned package databases) are applied by `build-iso.sh`, and the
design is in [ADR 0009](../../docs/decisions/0009-graceos-net.md).
