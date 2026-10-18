# Grace Shell: desktop design

_Status: proposal from the brainstorm with Harsh, 2026-10-19. For review by the Shell lead, who owns Grace Shell (T-003)._
_Interactive mockup: [mockups/grace-shell-desktop.html](mockups/grace-shell-desktop.html). Open it in a browser: hover the bottom-middle edge for the dock, and use the Settings controls to change the desktop live._

## 1. Intent

GraceOS's desktop should look as polished and calm as GNOME, but give the user Hyprland's power: compositor-level control over gaps, corners, blur, tiling and animation. Themes and extensions from the AUR and other community sources should work, without locking users into a GraceOS-only system.

It must be **beginner-friendly**: everything works out of the box and every common option is in a graphical Settings app. Power users keep full **freedom** through a plain config file.

AI lives in **small moments**, never as a chatbot that takes over the screen. Examples: a one-line hint when a command fails, an "Ask Grace" field, a summary of a pile of notifications, and an approval prompt before an agent runs something.

The look is **elegant, modern and premium**, and **security** is visible and on by default.

What makes it special: one consistent, premium visual system in which AI is just part of the desktop, and a beginner and a Hyprland power user can both feel at home.

## 2. Goals, non-goals, anti-goals

**Goals (this design phase)**
- A complete visual and interaction spec for: the top bar, the tiled window frame, the auto-hiding dock, the agent approval prompt, the inline AI hint, the control center, and Settings → Appearance.
- A design system (color, accent, type, spacing, radius, elevation, icons, motion) that every Grace app can reuse.
- A Figma file implementing all of the above (see §7), shared with the Shell lead.

**Non-goals (not in this phase)**
- Choosing the compositor or UI toolkit. That is the Shell lead's ADR (T-003); this design is deliberately technology-neutral.
- Detailed designs for: light mode, the Activities/overview screen, the Ask Grace results list, workspaces UI, lock and login screens, multi-monitor, and other apps (Files, AI Studio, Agent Hub).
- Implementing any of it in code.

**Anti-goals (a failure even if it technically works)**
- A chatbot-first desktop, or AI that acts without the user's approval.
- A cheap look: emojis as icons, colored outlines around panels, misaligned or uneven spacing, cramped panels.
- Hard-coded brand colors (e.g. "everything purple") instead of the user's accent.
- Locking users out of AUR or community themes, or forcing beginners into config files.
- A desktop that is less usable when AI is off or unavailable.

## 3. Constraints

- Arch Linux and Wayland underneath, with AUR compatibility (see `docs/vision/MASTER_DIRECTIVE.md` §3).
- Every Settings option maps to a key in a plain-text config file (proposed path: `~/.config/grace/desktop.conf`). The GUI and the file must never disagree.
- AI safety: agent approvals are enforced by the system, outside the model. Prompts never auto-accept. Local-first: the "Local AI" status always shows whether work runs on this device. One master switch turns every AI touch off.
- Accessibility: respect the system's reduce-motion setting, keep text contrast at WCAG AA or better in both themes, and make every control usable from the keyboard.
- Fonts and icons must be redistributable in an OS image (Inter is SIL OFL; the icon set's license must be checked by the builder).

## 4. What was decided (Harsh's calls)

### 4.1 Layout
- **Top bar (GNOME-style), full width, 30 px tall:**
  - Left: "Activities" pill.
  - Center: "Ask Grace…" field with a sparkle icon and its shortcut hint (Super + Space).
  - Right: the tray pill (Wi-Fi, volume and battery icons, battery %, clock). Clicking it opens the control center, and the pill turns brighter while the panel is open.
- **Windows auto-tile, Hyprland-style,** with rounded corners and equal gaps on every side.
- **Window title bars:** macOS-style red, yellow and green controls on the left, with the title centered.
- **Dock:**
  - Hidden by default. It slides up only when the pointer touches the bottom-middle edge of the screen, and a small handle line hints at it.
  - Apps show their **real, full-color icons** from the active icon theme, so community icon themes work as usual. Every icon is the same size.
  - AI Studio uses its own app icon, like any other app: no colored ring, no special size.
  - The mockup's line-icon dock is a placeholder for this.
  - Line icons stay for **system UI** only: the top bar, control center, Settings sidebar and rows, notifications.
  - A dot under an icon means the app is running. A divider separates apps from the AI, Agents and Settings icons.
- **Agent approval prompt (adopted from mockup C):** "Claude Code wants to run `npm install express` in ~/graceos", with **Allow once**, **Deny** and **Details**.
  - When the control center is closed, it appears as a floating prompt at the top right, just below the top bar, on the same gap grid.
  - It stays until answered.
  - It is also pinned at the top of the control center's notifications.
- **Inline AI hint:** appears inside the terminal only after something fails. It is one line with Explain, Fix it and Dismiss.

### 4.2 Visual language
- **Base:** neutral dark. The only color comes from the accent the user chooses.
- **Accent picker:** nine swatches the user chooses from, like GNOME. The exact colors and contrast handling are in §5, items 14–15.
- **What the accent fills:** only small things, namely toggles in their on state, sliders, primary buttons, AI sparkle icons, and the selected style card in Settings.
- **No colored outlines** on panels, cards or the tray. Surfaces use a hairline edge (`rgba(255,255,255,0.08)`), soft shadows and background blur.
- **No emojis.** System UI uses one consistent line-icon set (1.7 px stroke at 24 px, round caps and joins). App icons in the dock are the apps' own (see §4.1).
- **Typeface:** Inter.
- **Alignment:** everything is centered and on one spacing grid. A single **gap** value sets the screen-edge margins, the gaps between windows, the top bar's side padding and the control center's insets. So the control center's top, right and bottom edges line up exactly with the windows next to it, and the tray pill's right edge lines up with the panel's right edge.

### 4.3 Control center
It is one panel, opened from the tray pill and anchored to the top right on the shared gap grid.
- **Fixed top section** (never scrolls), with 14 px between sections:
  1. A header with battery % and time left, plus round Settings and Power buttons.
  2. Six quick toggles in a 2×3 grid. All are pill-shaped, the same height (48 px), with icon and label centered vertically and an optional subtitle: Wi-Fi (network name), Bluetooth (device), Do Not Disturb, Dark Style, Power Mode (Balanced), Night Light.
  3. Volume and brightness sliders.
  4. A **Local AI card:**
     - A title ("Local AI · on this device") with the master AI on/off switch.
     - The running model and its VRAM use, with **Stop**.
     - The active agent and what it is doing, with **Open**.
     - Every row stays on one line.
- **Notifications:** a fixed header ("Notifications", "Clear all"), then a list that scrolls on its own with a soft fade at the bottom and no visible scrollbar.
  - Pending agent approvals are pinned at the top.
  - Bundled messages get a one-line AI summary.

### 4.4 Settings app
- **Window:** standard title bar with the traffic-light controls, and a sidebar with search.
- **Sidebar groups:**
  - General: Wi-Fi, Bluetooth, Displays, Sound, Power.
  - **Desktop:** Appearance, Windows & Workspaces, Keyboard & Shortcuts.
  - **Intelligence:** AI & Models, Agents.
  - **System:** Privacy & Security, Updates & Software, About.
- **Appearance page:**
  - Style: Light or Dark preview cards.
  - Accent color.
  - Window gaps slider (0–24 px).
  - Corner roundness (0–22 px).
  - Background blur on/off.
  - Window layout: Auto-tile or Floating.
  - Animations: Off, Calm, Smooth or Snappy, noting that it follows the reduce-motion setting.
  - Dock behaviour dropdown.
  - "Get themes & extensions": a browser for community themes, including AUR packages, with a preview before installing.
  - "Edit config file".
- Changes apply **live**: in the mockup, the gap, corner, blur and accent controls update the desktop immediately.

## 5. My calls (Claude's), for review

These were proposed during the brainstorm and not objected to. Each is easy to change.

1. **Default accent:** Blue until a GraceOS signature accent is chosen.
2. **Approval prompts:** if ignored, they wait and never default to Allow. "Details" shows the full command, the working directory and which agent asked.
3. **The Local AI master switch** disables every AI touch at once: hints, summaries, Ask Grace's AI answers and AI Studio autostart. App search via Ask Grace keeps working without AI.
4. **The dock** also appears when the Super key is pressed.
5. **Light mode** mirrors dark with the same accents (to be designed later).
6. **The wallpaper** picks up a faint tint of the accent.
7. **Default dimensions from the mockup:**
   - Top bar 30 px, default gap 10 px, window radius 12 px, panel radius = window radius + 8 px.
   - Toggles 48 px tall; dock tiles 44 px with a 22 px icon.
   - Body text 12–13 px Inter, page titles 20 px at weight 650.
8. **Default animation preset "Smooth".** The dock reveal takes 380 ms with `cubic-bezier(.2,.9,.25,1.15)` (a slight overshoot). Fades take 250 ms. "Off" disables all motion; "Calm" uses roughly 1.5× the durations without overshoot; "Snappy" uses roughly 0.6×.
9. **Running-app indicator:** a 4 px dot under the dock icon.
10. **Notification history:** in the control center only. There is no separate notification drawer.
11. **Approval "Details"** expands inline inside the prompt. It shows the full command, the working directory, which agent asked, and what access it needs (files, network, privileges).
    - **Allow once:** the prompt shows a short "Running…" state, then closes.
    - **Deny:** the agent is told it was refused, and the prompt closes.
12. **Pending approvals:** while one is pending, the tray pill shows a small accent dot.
13. **Notification banners:**
    - Regular notifications appear as a banner at the top right for about 5 seconds, then move into the control center.
    - Do Not Disturb hides those banners.
    - Agent approvals still appear under Do Not Disturb, silently, because the agent is blocked until someone answers.
14. **Accent swatches** use GNOME's accent palette (Claude's pick; Harsh decided only that the accent is user-chosen): Blue `#3584e4`, Teal `#2190a4`, Green `#3a944a`, Yellow `#c88800`, Orange `#ed5b00`, Red `#e62d42`, Pink `#d56199`, Purple `#9141ac`, Slate `#6f8396`.
15. **Accent contrast:** white 12 px text on most of these swatches is below WCAG AA (4.5:1). Each swatch therefore defines three tokens:
    - `accent-fill`: the swatch darkened just enough that a white label reaches 4.5:1. Used for toggles, primary buttons and slider fills.
    - `accent-on-fill`: white.
    - `accent-fg`: the swatch lightened just enough to reach 4.5:1 for text, or 3:1 for icons, on the dark surfaces. Used for sparkle icons and accent text.
    - The swatch hex stays the identity shown in the picker.
16. **AI-off state** (master switch off). The desktop stays fully usable:
    - The "Ask Grace…" field becomes "Search…" with a magnifier icon, and still searches apps, files and settings.
    - Inline hints and notification summaries disappear.
    - The Local AI card collapses to one row, "Local AI · Off", with its switch, so it can be turned back on.
    - AI Studio stays in the dock, because it is where models are managed.
17. **Dock with real icons:**
    - Each item is the app icon at 40 px with no tile background behind it, so colorful icons don't sit on gray squares.
    - Hover gives a subtle lift and highlight; the 4 px running dot stays.
    - GraceOS's own apps (Files, Terminal, AI Studio, Agent Hub, Settings) need full-color app icons in one shared GraceOS style, designed in Figma.
18. **Figma on the Starter plan:** Harsh's Figma team is on Starter, which allows only one mode per variable collection.
    - The accent is built as nine swatch variable groups plus an `accent/*` alias set. You switch accents by re-pointing the aliases.
    - Dark and light are separate collections rather than modes.
    - If the plan is upgraded later, these can become modes.

## 6. Left to the builder

- The compositor and toolkit (the Shell lead's T-003 ADR). Whether "compositor-level customisation" is delivered by extending Hyprland, a wlroots compositor or something else is their decision. The visual spec above must hold regardless.
- Exact pixel values for screens not designed here, provided they follow the tokens in §4.2 and §5.
- The icon set (an existing open-source line-icon set is fine if its license allows redistribution) and any missing glyphs.
- The config file format and key names, provided it is plain text, documented, and round-trips with Settings.

## 7. Figma deliverable

A single Figma file, shared with Harsh and the Shell lead:
1. **Foundations:**
   - Color variables for dark (light as a stub), and the accent set up as in §5 item 18, with the three tokens per swatch from item 15.
   - Type scale (Inter), spacing (the gap scale), radius and elevation (hairline plus shadow levels) tokens.
   - The icon set.
2. **Components:**
   - Top-bar pill, Ask Grace field and tray pill.
   - Window frame with traffic lights.
   - Dock (with a hover variant), dock item using a real app icon (with running and hover variants), quick toggle (on and off), slider, switch, segmented control.
   - Full-color app icons for GraceOS's own apps: Files, Terminal, AI Studio, Agent Hub, Settings.
   - The floating approval prompt (collapsed, Details expanded and Running variants), and the tray pill with a pending-approval dot.
   - Local AI card, notification (default, approval and summary variants).
   - Settings sidebar item (with a selected variant) and settings row (with slider, switch, segmented, dropdown and link variants).
3. **Screens:**
   - The tiled desktop.
   - The desktop with the control center open.
   - The dock revealed.
   - Settings → Appearance.
   - The desktop and control center with AI switched off (§5 item 16).
4. **Prototype:** tray click opens the control center, the bottom-edge hover reveals the dock, and the approval buttons work.

The mockup HTML in `docs/design/mockups/` is the visual reference. Where the Figma file and this document disagree, update both.
