# 0001 Base on archiso `releng`, copied into the repo
Problem: need a reproducible Arch live ISO. Options: custom from scratch / `baseline` profile / copy `releng`. Chosen: copy `releng` (known-good hardware and network defaults), rebranded; upstream files are never edited in place. Trade-off: must track upstream changes manually. Revisit if the diff against upstream becomes unmanageable.
