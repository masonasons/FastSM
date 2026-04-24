# FastSM

FastSM is a fast, accessible Mastodon/Bluesky client, built with blind users in mind. It descends from the code for the [Quinter](https://github.com/QuinterApp/Quinter) Twitter app written alongside [Quin](https://github.com/trypsynth) in 2021, but is heavily modified and modernized — the goal is a Mastodon/Bluesky app with the same keyboard-first, earcon-driven feel as Quinter.

## Features

- Multi-account support for both Mastodon and Bluesky
- Timeline caching for faster startup
- Gap detection for missed posts
- Position restore across restarts
- Audio player with YouTube/Twitter support via yt-dlp
- AI-powered image descriptions (GPT/Gemini)
- Customizable soundpacks
- Invisible interface mode (Windows)
- Explore/Discover dialog for finding users and content
- Poll support (viewing and voting)
- Content warning handling
- Server-side filters (Mastodon)
- Timeline filtering by user or text

## Downloads

Prebuilt binaries for every commit to `master` are published at the [latest release](https://github.com/masonasons/FastSM/releases/tag/latest):

- **Windows Installer**: `FastSMInstaller.exe` (recommended)
- **Windows Portable**: `FastSM-Windows-Portable.zip`
- **macOS**: `FastSM-<version>.dmg`
- **Linux Portable**: `FastSM-Linux-Portable.tar.gz`

## Running from source

Python 3.10+ is required. Clone the repo, install dependencies, and run:

```bash
pip install -r requirements.txt
python FastSM.pyw
```

### Linux system dependencies

On Debian/Ubuntu, install these before `pip install`:

```bash
sudo apt install libgtk-3-0 libnotify4 libsdl2-2.0-0 libasound2 libpulse0 \
                 libgstreamer1.0-0 libgstreamer-plugins-base1.0-0
```

wxPython on Linux does not have a universal pip wheel — pull it from the wxPython extras index matching your distro:

```bash
pip install -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-22.04 wxpython
```

(Swap the Ubuntu codename for your release.)

### macOS notes

Speech uses AV Speech (via prism) and must run on the main thread; `speak.py` handles that automatically with `wx.CallAfter` when called off-thread.

### Portable mode

Dropping a `userdata/` folder next to the executable (or at the repo root when running from source) switches FastSM to portable mode — config and accounts live there instead of in the OS config directory.

## Building

`build.py` is the single entry point for all platforms. It detects the host OS and runs the matching PyInstaller flow:

```bash
python build.py
```

Output lands in `~/app_dist/FastSM/`.

### Windows

Produces both a portable zip and an Inno Setup installer (requires Inno Setup 6 on `PATH`). The CI workflow does this automatically.

### macOS

Produces a signed `.app` inside a DMG. Uses ad-hoc signing (`-`) if no Developer ID is on the keychain; pass a real identity via `security find-identity` ahead of time for distribution builds.

### Linux

Produces a `.tar.gz` of a PyInstaller onedir bundle. The build script post-processes the bundle to remove libraries that must come from the user's system (GLib family, libasound, libpulse, util-linux, etc.) — bundling these causes ABI mismatches on distros newer than the build runner.

### Continuous integration

`.github/workflows/build.yml` runs the Windows, macOS, and Linux jobs on every push to `master` and republishes the `latest` release with fresh artifacts.

## Options

The options dialog (Application menu → Global Options) is organized into:

- **General**: Basic application settings
- **Timelines**: Dismiss confirmations, timeline reversal, home-timeline position sync, cache settings
- **Audio**: Media/navigation/error sounds and output device selection
- **YouTube**: yt-dlp path, cookies, Deno path for YouTube/Twitter audio extraction
- **Templates**: Post display templates, demojify, 24-hour time
- **Invisible Interface** (Windows only): Invisible interface settings and keymap selection
- **Advanced**: API and general settings
- **Confirmation**: Per-action confirm toggles (follow, boost, favorite, block, etc.)
- **AI**: GPT/Gemini API keys and prompts for AI image descriptions
