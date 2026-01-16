#!/usr/bin/env python
"""Build script for FastSM using PyInstaller - supports Windows and macOS."""

import os
import subprocess
import sys
import shutil
import tempfile
import platform as platform_mod
from pathlib import Path

from version import APP_NAME, APP_VERSION, APP_DESCRIPTION, APP_COPYRIGHT, APP_VENDOR


def get_platform():
    """Get the current platform."""
    if sys.platform == "darwin":
        return "macos"
    elif sys.platform == "win32":
        return "windows"
    else:
        return "linux"


def get_hidden_imports():
    """Get list of hidden imports that PyInstaller might miss."""
    return [
        # wx submodules
        "wx.adv",
        "wx.html",
        "wx.xml",
        # mastodon
        "mastodon",
        "mastodon.Mastodon",
        # atproto
        "atproto",
        "atproto.xrpc_client",
        "atproto.xrpc_client.models",
        # Our packages
        "models",
        "models.user",
        "platforms",
        "platforms.base",
        "platforms.mastodon",
        "platforms.mastodon.account",
        "platforms.mastodon.models",
        "platforms.bluesky",
        "platforms.bluesky.account",
        "GUI",
        "GUI.main",
        "GUI.tweet",
        "GUI.view",
        "GUI.options",
        "GUI.account_options",
        "GUI.chooser",
        "GUI.misc",
        "GUI.lists",
        "GUI.custom_timelines",
        # Other modules
        "config",
        "timeline",
        "streaming",
        "mastodon_api",
        "application",
        "sound",
        "speak",
        "version",
        # keyboard_handler
        "keyboard_handler",
        "keyboard_handler.wx_handler",
        # Windows-specific
        "accessible_output2",
        "accessible_output2.outputs",
        "accessible_output2.outputs.auto",
        "sound_lib",
        "sound_lib.stream",
        "sound_lib.output",
        # requests/urllib
        "requests",
        "urllib3",
        "certifi",
        "charset_normalizer",
        "idna",
        # Other
        "json",
        "threading",
        "datetime",
        "pickle",
        "pyperclip",
        # Spell check
        "enchant",
    ]


def get_data_files(script_dir: Path):
    """Get list of data files to include in the bundle.

    Note: sounds, keymaps, and docs are copied separately to the root
    of the distribution folder after the build.
    """
    datas = []
    # Most data files are copied manually after build to keep them
    # at the root level, not inside _internal
    return datas


def copy_data_files(script_dir: Path, dest_dir: Path, include_docs: bool = True):
    """Copy data files to the distribution folder root.

    Args:
        script_dir: Source directory
        dest_dir: Destination directory
        include_docs: Whether to include docs folder (False for macOS app bundle)
    """
    # Sounds folder
    sounds_src = script_dir / "sounds"
    if sounds_src.exists():
        sounds_dst = dest_dir / "sounds"
        print("Copying sounds folder...")
        if sounds_dst.exists():
            shutil.rmtree(sounds_dst)
        shutil.copytree(sounds_src, sounds_dst)

    # Keymaps folder (invisible hotkeys only supported on Windows)
    keymaps_src = script_dir / "keymaps"
    if keymaps_src.exists():
        keymaps_dst = dest_dir / "keymaps"
        print("Copying keymaps folder...")
        if keymaps_dst.exists():
            shutil.rmtree(keymaps_dst)
        shutil.copytree(keymaps_src, keymaps_dst)

    # Docs folder (skip for macOS app bundle - goes in DMG instead)
    if include_docs:
        docs_src = script_dir / "docs"
        if docs_src.exists():
            docs_dst = dest_dir / "docs"
            print("Copying docs folder...")
            if docs_dst.exists():
                shutil.rmtree(docs_dst)
            shutil.copytree(docs_src, docs_dst)


def get_binaries():
    """Get platform-specific binaries to include."""
    binaries = []

    if sys.platform == "win32":
        # Include accessible_output2 lib folder
        try:
            import accessible_output2
            ao2_path = Path(accessible_output2.__file__).parent
            ao2_lib = ao2_path / "lib"
            if ao2_lib.exists():
                for dll in ao2_lib.glob("*.dll"):
                    binaries.append((str(dll), "accessible_output2/lib"))
        except ImportError:
            pass

        # Include sound_lib DLLs
        try:
            import sound_lib
            sl_path = Path(sound_lib.__file__).parent
            for dll in sl_path.glob("*.dll"):
                binaries.append((str(dll), "sound_lib"))
        except ImportError:
            pass

    return binaries


def build_windows(script_dir: Path, output_dir: Path) -> tuple:
    """Build for Windows using PyInstaller.

    Returns:
        Tuple of (success: bool, artifact_path: Path or None)
    """
    dist_dir = output_dir / "dist"
    build_dir = output_dir / "build"

    # Clean previous build
    for d in [dist_dir, build_dir]:
        if d.exists():
            print(f"Cleaning {d}...")
            shutil.rmtree(d)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Build PyInstaller command
    main_script = script_dir / "FastSM.pyw"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--windowed",  # No console window
        "--noconfirm",  # Overwrite without asking
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        f"--specpath={output_dir}",
    ]

    # Add hidden imports
    for imp in get_hidden_imports():
        cmd.extend(["--hidden-import", imp])

    # Add data files
    for src, dst in get_data_files(script_dir):
        cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])

    # Add binaries
    for src, dst in get_binaries():
        cmd.extend(["--add-binary", f"{src}{os.pathsep}{dst}"])

    # Collect all submodules for key packages
    cmd.extend(["--collect-all", "accessible_output2"])
    cmd.extend(["--collect-all", "sound_lib"])
    cmd.extend(["--collect-all", "keyboard_handler"])
    cmd.extend(["--collect-all", "enchant"])

    # Add main script
    cmd.append(str(main_script))

    print(f"Building {APP_NAME} v{APP_VERSION} for Windows...")
    print(f"Output: {output_dir}")
    print()

    result = subprocess.run(cmd, cwd=script_dir)

    if result.returncode != 0:
        return False, None

    # The output will be in dist_dir / APP_NAME
    app_dir = dist_dir / APP_NAME
    if not app_dir.exists():
        print("Error: Build output not found")
        return False, None

    # Copy data files to root of distribution folder
    copy_data_files(script_dir, app_dir)

    # Create zip file for distribution
    zip_path = create_windows_zip(output_dir, app_dir)

    return True, zip_path


def create_windows_zip(output_dir: Path, app_dir: Path) -> Path:
    """Create a zip file of the Windows build for distribution."""
    import zipfile

    zip_name = f"{APP_NAME}-{APP_VERSION}-Windows.zip"
    zip_path = output_dir / zip_name

    if zip_path.exists():
        zip_path.unlink()

    print(f"Creating zip: {zip_name}...")

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in app_dir.rglob('*'):
            if file_path.is_file():
                arc_name = Path(APP_NAME) / file_path.relative_to(app_dir)
                zipf.write(file_path, arc_name)

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Zip created: {zip_path}")
    print(f"Zip size: {zip_size_mb:.1f} MB")

    return zip_path


def build_macos(script_dir: Path, output_dir: Path) -> tuple:
    """Build for macOS using PyInstaller.

    Returns:
        Tuple of (success: bool, artifact_path: Path or None)
    """
    import plistlib

    dist_dir = output_dir / "dist"
    build_dir = output_dir / "build"

    # Clean previous build
    for d in [dist_dir, build_dir]:
        if d.exists():
            print(f"Cleaning {d}...")
            shutil.rmtree(d)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Bundle identifier
    bundle_id = f"me.masonasons.{APP_NAME.lower()}"

    main_script = script_dir / "FastSM.pyw"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--windowed",  # Create .app bundle
        "--noconfirm",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        f"--specpath={output_dir}",
        f"--osx-bundle-identifier={bundle_id}",
    ]

    # Add hidden imports
    for imp in get_hidden_imports():
        cmd.extend(["--hidden-import", imp])

    # Add data files
    for src, dst in get_data_files(script_dir):
        cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])

    # Collect keyboard_handler
    cmd.extend(["--collect-all", "keyboard_handler"])

    # Add main script
    cmd.append(str(main_script))

    print(f"Building {APP_NAME} v{APP_VERSION} for macOS...")
    print(f"Output: {output_dir}")
    print()

    result = subprocess.run(cmd, cwd=script_dir)

    if result.returncode != 0:
        return False, None

    # The app bundle will be in dist_dir
    app_path = dist_dir / f"{APP_NAME}.app"
    if not app_path.exists():
        print("Error: App bundle not found")
        return False, None

    # Update Info.plist
    plist_path = app_path / "Contents" / "Info.plist"
    if plist_path.exists():
        print("Updating Info.plist...")
        with open(plist_path, 'rb') as f:
            plist = plistlib.load(f)

        plist.update({
            'CFBundleName': APP_NAME,
            'CFBundleDisplayName': APP_NAME,
            'CFBundleIdentifier': bundle_id,
            'CFBundleVersion': APP_VERSION,
            'CFBundleShortVersionString': APP_VERSION,
            'NSHumanReadableCopyright': APP_COPYRIGHT,
            'LSMinimumSystemVersion': '10.13',
            'NSHighResolutionCapable': True,
            'NSAppleEventsUsageDescription': f'{APP_NAME} needs accessibility access for screen reader support.',
        })

        with open(plist_path, 'wb') as f:
            plistlib.dump(plist, f)

    # Copy data files to Resources folder (docs go in DMG, not app)
    resources_dir = app_path / "Contents" / "Resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    copy_data_files(script_dir, resources_dir, include_docs=False)

    # Code sign the app
    sign_macos_app(app_path)

    # Create DMG
    dmg_path = create_macos_dmg(output_dir, app_path, script_dir)

    return True, dmg_path


def get_signing_identity():
    """Find a code signing identity."""
    try:
        result = subprocess.run(
            ["security", "find-identity", "-v", "-p", "codesigning"],
            capture_output=True, text=True
        )

        if result.returncode == 0:
            output = result.stdout
            for line in output.split('\n'):
                if 'Developer ID Application' in line:
                    parts = line.split('"')
                    if len(parts) >= 2:
                        return parts[1]

            for line in output.split('\n'):
                if 'Apple Development' in line or 'Mac Developer' in line:
                    parts = line.split('"')
                    if len(parts) >= 2:
                        return parts[1]

            return "-"  # Ad-hoc signing
    except FileNotFoundError:
        pass

    return "-"


def sign_macos_app(app_path: Path):
    """Sign the macOS app bundle."""
    signing_identity = get_signing_identity()
    print(f"Signing app with identity: {signing_identity}")

    # Clear extended attributes
    subprocess.run(["xattr", "-cr", str(app_path)], capture_output=True)

    # Collect binaries to sign
    binaries = []
    for ext in ['*.so', '*.dylib']:
        binaries.extend(app_path.rglob(ext))

    main_exec = app_path / "Contents" / "MacOS" / APP_NAME
    if main_exec.exists():
        binaries.append(main_exec)

    binaries.sort(key=lambda p: len(p.parts), reverse=True)

    print(f"Signing {len(binaries)} binaries...")

    # Remove signatures
    for binary in binaries:
        subprocess.run(["codesign", "--remove-signature", str(binary)], capture_output=True)

    # Sign binaries
    for binary in binaries:
        subprocess.run(["codesign", "--force", "--sign", signing_identity, str(binary)], capture_output=True)

    # Sign app bundle
    result = subprocess.run(
        ["codesign", "--force", "--sign", signing_identity, str(app_path)],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        print("Code signing successful!")
    else:
        print(f"Code signing warning: {result.stderr}")


def create_macos_dmg(output_dir: Path, app_path: Path, script_dir: Path) -> Path:
    """Create a DMG disk image for macOS distribution."""
    dmg_name = f"{APP_NAME}-{APP_VERSION}.dmg"
    dmg_path = output_dir / dmg_name

    if dmg_path.exists():
        dmg_path.unlink()

    print(f"Creating DMG: {dmg_name}...")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy app
        temp_app = temp_path / app_path.name
        shutil.copytree(app_path, temp_app, symlinks=True)

        # Copy docs
        docs_src = script_dir / "docs"
        if docs_src.exists():
            shutil.copytree(docs_src, temp_path / "Documentation", dirs_exist_ok=True)

        # Create Applications symlink
        try:
            (temp_path / "Applications").symlink_to("/Applications")
        except OSError:
            pass

        # Create DMG
        result = subprocess.run([
            "hdiutil", "create",
            "-volname", APP_NAME,
            "-srcfolder", str(temp_path),
            "-ov",
            "-format", "UDZO",
            "-imagekey", "zlib-level=9",
            str(dmg_path)
        ], capture_output=True, text=True)

        if result.returncode == 0:
            dmg_size_mb = dmg_path.stat().st_size / (1024 * 1024)
            print(f"DMG created: {dmg_path}")
            print(f"DMG size: {dmg_size_mb:.1f} MB")
        else:
            print(f"DMG creation failed: {result.stderr}")
            return None

    # Sign DMG
    signing_identity = get_signing_identity()
    if signing_identity and signing_identity != "-":
        subprocess.run([
            "codesign", "--force", "--sign", signing_identity,
            "--timestamp", str(dmg_path)
        ], capture_output=True)

    return dmg_path


def main():
    """Build FastSM executable using PyInstaller."""
    script_dir = Path(__file__).parent.resolve()

    platform = get_platform()
    print(f"Detected platform: {platform}")

    output_dir = Path.home() / "app_dist" / APP_NAME

    print(f"Building {APP_NAME} v{APP_VERSION} with PyInstaller...")
    print(f"Output: {output_dir}")
    print()

    if platform == "windows":
        success, artifact_path = build_windows(script_dir, output_dir)
    elif platform == "macos":
        success, artifact_path = build_macos(script_dir, output_dir)
    else:
        print(f"Unsupported platform: {platform}")
        sys.exit(1)

    if success:
        print()
        print("=" * 50)
        print("Build completed successfully!")
        print(f"Output: {output_dir}")

        if artifact_path and artifact_path.exists():
            dest_path = script_dir / artifact_path.name
            print(f"Copying to source folder: {dest_path}")
            shutil.copy2(artifact_path, dest_path)
            print(f"Artifact: {dest_path}")

        print("=" * 50)
    else:
        print()
        print("=" * 50)
        print("Build failed!")
        print("=" * 50)
        sys.exit(1)


if __name__ == "__main__":
    main()
