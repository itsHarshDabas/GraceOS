# 0007: CottonCandy, the GraceOS browser, is GTK4 + WebKitGTK through PyGObject

- Status: accepted by Harsh, 2026-10-20.
- Implements: `docs/vision/MASTER_DIRECTIVE.md` §9.3 (Grace Browser). Task: T-022.
- Code will live in its own repo, [`itsHarshDabas/CottonCandy-Browser`](https://github.com/itsHarshDabas/CottonCandy-Browser). It gets packaged the same way as Grace Candyland (ADR 0004, ADR 0006).

## Context
§9.3 asks for our own browser application on top of an established engine. It puts security and upstream update cadence ahead of novelty. It also asks us to research licensing, who is responsible for security updates, and packaging on Arch. Two more GraceOS rules apply:
- Page content is untrusted.
- Page text is never sent to a remote service. The optional summary (Phase 4) only uses the local `cherrycola` CLI.

What the shell already has:
- **CandySole** (T-018), our terminal, is one Python file. It uses **GTK4 + libadwaita + VTE through PyGObject**, with argparse and a pytest file next to it.
- `grace-candyland` already depends on `python-gobject gtk4 libadwaita vte4` (`packaging/arch/PKGBUILD`).
- The shell itself is Quickshell (QML, Qt 6). So `qt6-base` and `qt6-declarative` are on the ISO too.
- Hyprland draws no server-side title bars (ADR 0004). Only apps that draw their own get the Grace traffic lights. Today those are GTK4/libadwaita apps and Grace Settings. T-011, which would add bars to the rest, is still `todo`.
- The dock pins `firefox` (`grace-candyland/data/desktop.conf`), but `firefox` is **not** in `iso/packages.x86_64`. On the live ISO that pin points at nothing.

## Options

### A. GTK4 + WebKitGTK (`webkitgtk-6.0`) through PyGObject
- **Engine:** WebKit, the Safari engine. The Linux ports are maintained by Igalia, and GNOME Web (Epiphany) is built on it.
- **Arch packages** (all in `extra`): `webkitgtk-6.0` 2.52.x, about 35.8 MB to download and about 130.3 MB installed (taken from the 2.52.4-1 page). `python-gobject`, `gtk4` and `libadwaita` are already pulled in by `grace-candyland`.
- **Security:** WebKitGTK and WPE publish their own advisories (WSA).
  - Five came out in 2026 up to 2026-08-20 (WSA-2026-0001 to 0005). They were fixed in the 2.52.4, 2.52.5 and 2.52.6 point releases.
  - Arch moves through the 2.52.x point releases quickly. Archived package pages show 2.52.4, 2.52.5 and 2.52.6 in `extra`.
  - Fixes reach us as normal `pacman -Syu` updates of a shared library. We never rebuild the engine ourselves.
- **Sandbox:** the 6.0 API always runs the web process in a bubblewrap sandbox. The switch to turn it off was removed. So "page content is untrusted" holds by default.
- **Site compatibility:** good, but below Chromium.
  - Some sites sniff for Chrome or Safari, so a Safari-like user agent may be needed for a few of them.
  - Video depends on the GStreamer plugins that are installed.
  - There is no Widevine DRM on Linux, so Netflix-style streaming will not play.
  - Web Inspector is built in (§9.3 "developer tools where supported").
- **Licensing:** WebKitGTK is LGPL-2.1+ and BSD. PyGObject is LGPL-2.1+. That puts no constraint on CottonCandy's own license (GraceOS's license is still open, T-009).
- **Shell fit:** this is the same stack, language, packaging and test style as CandySole.
  - libadwaita draws its own header bar, so the window gets Grace traffic lights on Hyprland today.
  - Dark Style already switches GTK. No new toolkit gets added to the ISO.
- **Isolated scripts (for Phase 4):** `evaluate_javascript` accepts a world name. Page text can be read from an isolated script world that the page's own scripts can't reach or change.

### B. Qt 6 + QtWebEngine (`qt6-webengine`) through PyQt6 or PySide6
- **Engine:** Chromium, pinned per Qt release.
- **Arch packages** (all in `extra`): `qt6-webengine` 6.11.1, about 94.5 MB to download and about 282.2 MB installed. The Python bindings are `python-pyqt6-webengine` (6.11.0). `qt6-base` is already on the ISO through Quickshell.
- **Security:** Qt pins the Chromium version at feature freeze. Later Chromium fixes get cherry-picked into Qt patch releases, and a patch release is pulled forward if Chrome fixes something critical.
  - This works, but the fixes are tied to Qt's release train.
  - In March 2026, Qt 6.11.0 and 6.10.3 were held back for new Chromium security issues.
  - Downstream packagers often describe QtWebEngine as running behind Chrome on security fixes.
- **Sandbox:** Chromium's own multi-process sandbox (on by default).
- **Site compatibility:** better. It's the Chromium engine, so Google Docs and Meet, WebRTC-heavy apps and sites that sniff for Chrome all work. Chromium DevTools are available.
  - Whether Arch's build includes the proprietary codecs (H.264, AAC) is **not verified**.
  - Widevine is possible with an AUR CDM, but that's untested and we couldn't put it on the ISO anyway (AGENTS.md says no AUR packages there).
- **Licensing:** QtWebEngine is LGPL-3 or GPL. **PyQt6 is GPL-3 (or commercial)**, so using it forces CottonCandy to be GPL-3. PySide6 is LGPL-3 and avoids that, but it's another binding to check.
- **Shell fit:** it matches Quickshell's toolkit, but not CandySole's. A Qt window has **no title bar** on Hyprland until T-011 lands, and it would be the first Python-Qt app in the project. Embedding it in the Quickshell process isn't wanted anyway: a browser should be its own process.

### Not considered
- **Writing our own engine:** ruled out by §9.3.
- **CEF or Electron:** we would have to bundle and update Chromium ourselves, which puts the security update burden on us. That's the opposite of §9.3.
- **Wrapping Firefox/Gecko:** there's no supported Gecko embedding API on desktop Linux.

## Decision
**Option A: GTK4 + libadwaita + `webkitgtk-6.0` through PyGObject**, in CandySole's structure and style:
- One executable Python script, `cottoncandy`, and an `org.graceos.CottonCandy.desktop` file.
- An SVG icon and a `test_cottoncandy.py` next to them.

Reasons, in order of §9.3's priorities:
1. **Security responsibility stays upstream and shared.** Engine fixes arrive as ordinary Arch library updates, with a dedicated advisory stream.
2. **Sandboxed by default, with no way to turn it off.**
3. **Smallest addition to the ISO.** About 130 MB installed versus about 282 MB, and the toolkit and bindings are already there.
4. **It fits the shell today.** It gets a title bar with traffic lights on Hyprland, the same stack as CandySole, and no GPL-3 binding forced on the project.

Both engines run behind their parent browsers (Safari and Chrome). Neither patches as fast as Firefox or Chromium themselves. That's the cost of having our own browser at all, so we should say it plainly and not hide it.

## Consequences
- **Some sites will be worse than in Chrome or Firefox,** and DRM streaming won't play. Mitigations:
  - Keep `firefox` installable (it's in Arch `extra`). Add an "Open in another browser" menu item that uses `xdg-open` and only appears when another browser is installed.
  - Allow a per-site user-agent override if real breakage turns up.
- **GStreamer plugins decide video support.** Phase 3 must check which `gst-plugins-*` packages land on the ISO and play an H.264 and a VP9/AV1 video on the live ISO.
- **History and bookmarks** live in SQLite (Python's stdlib `sqlite3`) under `$XDG_DATA_HOME/cottoncandy/`. Website data and cookies go to WebKit's own `NetworkSession` directory under the same root.
- **Phase 4 (optional summary):**
  - Off by default.
  - The page text comes from an isolated script world, so the page can't change what gets read.
  - The text is passed to the local `cherrycola` CLI on stdin as data, never as part of the prompt instructions.
  - There's never a network call.

## Package facts and how they were checked
Not verified with `pacman -Si`. The session that wrote this ADR ran on Ubuntu, and its network policy blocked archlinux.org and the Arch mirrors. The figures above come from archlinux.org package pages found through web search. Those are cached snapshots, and they disagree on point versions. Before Phase 3 changes `iso/packages.x86_64`, run this on Arch and correct the numbers here if they differ:

```sh
pacman -Si webkitgtk-6.0 python-gobject gtk4 libadwaita gst-plugins-good gst-plugins-bad gst-libav
pacman -Si qt6-webengine python-pyqt6-webengine   # only to keep the comparison honest
```

Sources: archlinux.org package pages for `webkitgtk-6.0`, `qt6-webengine` and `python-pyqt6-webengine`; webkitgtk.org/security (WSA-2026-0001 to 0005); the WebKitGTK "Migrating to 6.0" guide (the sandbox is always on); the Qt blog post "Putting updates of Chromium in QtWebEngine on a timeline"; the Qt release-team minutes of 2026-03-17; the FreeBSD VuXML entry for qt6-webengine 6.10.2.

## Revisit when
- Site breakage reported by users is mostly sites that only work in Chromium. Option B, or a different product decision, would then be on the table.
- WebKitGTK advisories start reaching Arch more slowly than about a week after they're published.
- T-011 gives Qt apps proper title bars, and a GPL-3 or PySide6 license question has been settled. That removes two of B's costs.
