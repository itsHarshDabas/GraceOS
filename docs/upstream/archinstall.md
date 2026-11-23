# archinstall: what we send upstream, and when

Status (2026-11-23): **drafts, nothing submitted.** Harsh approves the final text before anything
goes to github.com/archlinux/archinstall.

## What archinstall accepts
- Built-in profiles (`archinstall/default_profiles/desktops/*.py`) install only packages from
  Arch's official repos. Its README: "archinstall will not offer or bundle AUR helpers or AUR
  packages due to a current consensus" (arch-dev-public thread linked there).
- A profile that adds a third-party repo (our `[graceos]`) would be the same thing by another
  route, so we don't propose one.
- What works today without upstream: `archinstall --config-url` with our own profile file
  (`installer/archinstall/`). Every Arch ISO user can do that now.

So there are two upstream steps, in this order.

## Step 1 (ready now): fix loading a profile from a URL
`ProfileHandler._import_profile_from_url` (`archinstall/lib/profile/profiles_handler.py`) parses
the downloaded file, calls `remove_custom_profiles(profiles)` and never `add_custom_profiles`, so a
profile given by URL in a config's `profile_config.profile.path` is silently dropped
("No profile definition found"). The local-file branch right above it does both.

Patch: [`archinstall-profile-from-url.patch`](archinstall-profile-from-url.patch) (one line plus a
test), against master `2c25540`. Checked:
- `pytest tests/test_profile_url.py`: fails on master ("assert None is not None"), passes with the fix.
- `ruff check` and `ruff format --check` on both files: clean.
- Our real profile served over HTTP: master prints "No profile definition found: Grace
  Candyland" and selects nothing; with the fix, Grace Candyland is selected with its packages.

### Issue text
> **Title:** Profiles loaded from a URL (`profile_config.profile.path`) are dropped
>
> **Which ISO version are you using?** archinstall master (`2c25540`); the code is the same in the current release.
>
> **Describe the problem**
> A config whose profile points at a URL, for example
> ```json
> "profile_config": {"profile": {"main": "Desktop", "details": ["My Desktop"], "path": "https://example.com/my_desktop.py"}}
> ```
> downloads and parses the file, but the profile never becomes available: archinstall logs
> `No profile definition found: My Desktop` and installs no desktop. A local `path` to the same file works.
>
> `ProfileHandler._import_profile_from_url` calls `self.remove_custom_profiles(profiles)` after
> parsing and never `self.add_custom_profiles(profiles)`, which the local-file branch in
> `parse_profile_config` does.
>
> **Steps:** serve any profile file over HTTP, put its URL in `path`, run `archinstall --config <file>`
> (or `--config-url`) and look at the selected profile.

### PR text
> **Title:** Register profiles imported from a URL
>
> Fixes #<issue>.
>
> `_import_profile_from_url` removed any existing profiles with the imported names but never added
> the imported ones, so a profile given by URL in `profile_config.profile.path` was dropped and
> `parse_profile_config` reported "No profile definition found". This adds them back, the same as
> the local-file branch does.
>
> Tests: `tests/test_profile_url.py` loads a profile from a mocked URL and checks it is registered and
> selected. It fails before this change and passes after. `ruff check` and `ruff format --check` are clean.

## Step 2 (later): a built-in "Grace Candyland" profile
Only once `grace-candyland` (and the packages it depends on) are in `[extra]`. Getting there:
1. Publish to the AUR (the `aur` workflow) and keep the packages clean: real licenses in
   grace-candyland, CherryColaLLM and CottonCandy (they are `LicenseRef-unspecified` today),
   tagged releases instead of commit pins, signed `[graceos]` packages.
2. Ask an Arch package maintainer to adopt them into `[extra]` (votes and popularity on the AUR
   are what they look at). We can't do this step ourselves.
3. Then open the profile PR: `installer/archinstall/grace_candyland.py`, with its packages limited
   to what's in `[extra]`, goes to `archinstall/default_profiles/desktops/grace_candyland.py`
   (`ruff check` and `ruff format --check` already pass with archinstall's config).

### Profile PR text (for step 2)
> **Title:** Add Grace Candyland desktop profile
>
> Adds "Grace Candyland" to the Desktop menu: Hyprland with the Grace shell (Quickshell), from
> `[extra]`. It installs `grace-candyland-desktop`, `polkit` and `qt6-wayland`, enables
> `bluetooth`, and defaults to SDDM, which lists the `grace-candyland` Wayland session.
> Tested with a full guided install in QEMU: <results>.
