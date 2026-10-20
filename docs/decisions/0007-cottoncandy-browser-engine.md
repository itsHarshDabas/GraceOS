# 0007: CottonCandy, the GraceOS browser, is Chromium-based: Qt 6 + QtWebEngine through PySide6

- Status: accepted by Harsh, 2026-10-20.
  - The first draft recommended GTK4 + WebKitGTK. Harsh chose Chromium (QtWebEngine) for site compatibility and DevTools. Both options and their trade-offs are kept below.
- Implements: `docs/vision/MASTER_DIRECTIVE.md` §9.3 (Grace Browser). Task: T-022.
- Code lives in its own repo, [`itsHarshDabas/CottonCandy-Browser`](https://github.com/itsHarshDabas/CottonCandy-Browser). It's packaged the same way as Grace Candyland (ADR 0004, ADR 0006).

## Context
§9.3 asks for our own browser application on top of an established engine. It puts security and upstream update cadence ahead of novelty. It also asks us to research licensing, who is responsible for security updates, and packaging on Arch. Two more GraceOS rules apply:
- Page content is untrusted.
- Page text is never sent to a remote service. The optional summary (Phase 4) only uses the local `cherrycola` CLI.

What the shell already has:
- The shell is Quickshell (QML, Qt 6), so `qt6-base` and `qt6-declarative` are already on the ISO.
- **CandySole** (T-018), our terminal, is one Python file using **GTK4 + libadwaita + VTE through PyGObject**.
- Hyprland draws no server-side title bars (ADR 0004). A browser draws its own tab strip and toolbar either way, so this matters less for a browser than for other apps.
- The dock pins `firefox` (`grace-candyland/data/desktop.conf`), but `firefox` is **not** in `iso/packages.x86_64`. On the live ISO that pin points at nothing.

## Options

### A. Qt 6 + QtWebEngine (`qt6-webengine`) through PySide6: chosen
- **Engine:** Chromium. Qt pins one Chromium version per Qt release.
- **Arch packages** (all in `extra`):
  - `qt6-webengine` 6.11.1: about 94.5 MB to download, about 282.2 MB installed.
  - `pyside6` 6.11.1. Its package page lists `qt6-webengine` as the optional dependency for the "QtWebEngine bindings", so the bindings live in `pyside6` itself.
  - `qt6-base` is already on the ISO through Quickshell.
- **Security:** Qt pins Chromium at feature freeze, then cherry-picks later Chromium security fixes into Qt patch releases. A patch release gets pulled forward when Chrome fixes something critical.
  - In March 2026, Qt 6.11.0 and 6.10.3 were held back for new Chromium security issues.
  - A FreeBSD advisory lists seven Chromium security fixes backported into 6.10.2.
  - Downstream packagers often say QtWebEngine runs behind Chrome on fixes. We accept that lag.
  - Fixes reach us as ordinary `pacman -Syu` updates. We never build Chromium ourselves.
- **Sandbox:** Chromium's multi-process sandbox (seccomp-bpf plus namespaces), on by default.
  - CottonCandy must never pass `--no-sandbox` or set `QTWEBENGINE_DISABLE_SANDBOX`.
  - Chromium refuses to start its sandbox as root, so CottonCandy refuses to run as root instead of turning the sandbox off.
- **Site compatibility:** the best available without shipping Chrome itself. Google Docs and Meet, WebRTC-heavy apps and sites that sniff for Chrome all work. Chromium DevTools are built in (§9.3 "developer tools where supported").
  - Whether Arch's build includes the proprietary codecs (H.264, AAC) is **not verified** yet. Phase 3 has to check it on the live ISO.
  - Widevine DRM would need an AUR CDM, and AUR packages can't go on the ISO (AGENTS.md). So DRM streaming isn't a goal.
- **Licensing:** QtWebEngine is LGPL-3 or GPL, and Chromium itself is BSD.
  - **PySide6 is LGPL-3**, so it leaves CottonCandy's own license open (T-009).
  - **PyQt6 is not used:** it's GPL-3 or commercial, and would force CottonCandy to be GPL-3.

### B. GTK4 + WebKitGTK (`webkitgtk-6.0`) through PyGObject: not chosen
- **Engine:** WebKit, the Safari engine. Igalia maintains the Linux ports, and GNOME Web is built on it.
- **Arch packages** (all in `extra`): `webkitgtk-6.0` 2.52.x, about 35.8 MB to download and about 130.3 MB installed. The toolkit and bindings are already pulled in by `grace-candyland`.
- **Security:** WebKitGTK publishes its own advisories (WSA). Five came out in 2026 up to 2026-08-20, fixed in the 2.52.4 to 2.52.6 releases.
- **Sandbox:** bubblewrap, always on in the 6.0 API.
- **Site compatibility:** good, but below Chromium. Some sites sniff for Chrome, and there's no Widevine.
- **Licensing:** LGPL-2.1+ and BSD.
- **Shell fit:** the same stack and language as CandySole.

Why it lost:
- Site compatibility and Chromium DevTools matter more for an OS aimed at developers than install size and toolkit reuse.
- WebKitGTK also runs behind its parent browser (Safari), so neither option wins clearly on security.

### Not considered
- **Writing our own engine:** ruled out by §9.3.
- **CEF, Electron, or building and forking Chromium:**
  - CEF is AUR-only.
  - Electron is meant for trusted app code, not untrusted websites.
  - Building Chromium ourselves means tracking Chrome security fixes every week or two on our own. All three move the security update burden onto us, against §9.3.
- **Wrapping Firefox/Gecko:** there's no supported Gecko embedding API on desktop Linux.

## Decision
**Qt 6 Widgets + QtWebEngine through PySide6**, packaged with `depends=(python pyside6 qt6-webengine)`. It follows CandySole's structure and style:
- One executable Python script, `cottoncandy`, with pure, testable helpers at the top and the toolkit imported inside `main()`.
- An `org.graceos.CottonCandy.desktop` file, an SVG icon and a `test_cottoncandy.py` next to them.
- The Grace dark colors.

## Consequences
- **Two UI stacks** in Grace apps (GTK for CandySole and Qt for CottonCandy). The shell is Qt already, so the ISO adds no new toolkit, only `qt6-webengine` and `pyside6`.
- **Roughly 282 MB** more on the ISO, plus PySide6.
- **CottonCandy keeps Chromium's defaults on the safe side:**
  - It never turns the sandbox off.
  - Certificate errors are rejected, with no way to click through.
  - Unknown URL schemes are refused instead of being handed to `xdg-open`. Only `mailto:` is handed off.
  - Pop-ups need a user gesture.
  - Camera, microphone, location, screen sharing and notifications need a click on Allow, and that answer lasts until the browser quits.
  - Downloads only ever offer "Show in folder", never "Open".
- **History and bookmarks** live in SQLite (Python's stdlib `sqlite3`) at `$XDG_DATA_HOME/cottoncandy/cottoncandy.db`. Site data goes in the QtWebEngine profile under the same directory.
  - `--private` uses an off-the-record profile and writes no history.
  - There are no search suggestions: nothing is sent while you type in the address bar.
- **Phase 4 (optional summary):**
  - Off by default.
  - The page text is read with `runJavaScript` in `QWebEngineScript.ApplicationWorld`, an isolated world the page's own scripts can't reach or change.
  - The text is passed to the local `cherrycola` CLI on stdin as data, never as part of the prompt instructions.
  - There's never a network call.
- **Firefox stays installable** from `extra` for sites that still break.

## Package facts and how they were checked
Not verified with `pacman -Si`. The session that wrote this ADR ran on Ubuntu, and its network policy blocked archlinux.org and the Arch mirrors. The figures come from archlinux.org package pages found through web search. Those are cached snapshots, and they sometimes disagree on point versions.

The code was tested against the PyPI PySide6 wheel (6.12.0), not Arch's 6.11. The APIs it uses (`QWebEnginePermission`, `permissionRequested`) have been in Qt since 6.8.

Before Phase 3 changes `iso/packages.x86_64`, run this on Arch and correct the numbers here if they differ:

```sh
pacman -Si pyside6 qt6-webengine
pacman -Fl pyside6 | grep QtWebEngineWidgets   # the bindings really are in pyside6
```

Sources: archlinux.org package pages for `qt6-webengine`, `pyside6` and `webkitgtk-6.0`; the Qt blog post "Putting updates of Chromium in QtWebEngine on a timeline"; the Qt release-team minutes of 2026-03-17; the FreeBSD VuXML entry for qt6-webengine 6.10.2; webkitgtk.org/security (WSA-2026-0001 to 0005); the WebKitGTK "Migrating to 6.0" guide.

## Revisit when
- Arch's `qt6-webengine` runs more than one Qt patch release behind on a published critical Chromium fix.
- Qt drops PySide6 or LGPL licensing.
- Real use shows that `qt6-webengine` is too heavy for the low-end PCs in lite mode (T-021).
