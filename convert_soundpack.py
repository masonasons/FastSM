#!/usr/bin/env python3
"""
Convert TweeseCake or TWBlue soundpacks to FastSM format.

Usage:
    python convert_soundpack.py

This interactive script will guide you through converting a soundpack.
"""

import os
import sys
import shutil
import subprocess

# Mapping from TweeseCake sound names to FastSM names
# Includes both Mastodon-Default sounds and shared Default sounds
TWEESECAKE_MAP = {
    # Mastodon-specific sounds
    'favorite': 'like',
    'favorites': 'likes',
    'image': 'image',
    'max': 'max_length',
    'media': 'media',
    'mention': None,
    'new_dm': 'messages',
    'new_mention': 'mentions',
    'new_notification': 'notification',
    'new_search': 'search',
    'new_toot': 'home',
    'open_timeline': 'open',
    'poll': 'poll',
    'search_updated': 'search',
    'send_boost': 'send_repost',
    'send_dm': 'send_message',
    'send_reply': 'send_reply',
    'send_toot': 'send_post',
    'unfavorite': 'unlike',
    'user': 'user',
    'vote': None,  # No FastSM equivalent
    # Shared/Default sounds
    'boundary': 'boundary',
    'close_timeline': 'close',
    'error': 'error',
    'follow': 'follow',
    'media': 'media',
    'mention': 'mentions',
    'unfollow': 'unfollow',
}

# Mapping from TWBlue sound names to FastSM names
TWBLUE_MAP = {
    'audio': 'media',
    'create_timeline': 'open',
    'delete_timeline': 'close',
    'dm_received': 'messages',
    'dm_sent': 'send_message',
    'error': 'error',
    'favourite': 'like',
    'favourites_timeline_updated': 'likes',
    'image': 'image',
    'limit': 'boundary',
    'list_tweet': 'list',
    'max_length': 'max_length',
    'mention_received': 'mentions',
    'new_event': 'notification',
    'ready': 'ready',
    'reply_send': 'send_reply',
    'retweet_send': 'send_repost',
    'search_updated': 'search',
    'tweet_received': 'home',
    'tweet_send': 'send_post',
    'tweet_timeline': 'new',
    'update_followers': 'follow',
    'volume_changed': 'volume_changed',
    # Additional TWBlue sounds that don't have direct equivalents
    'geo': None,  # No equivalent
    'trends_updated': None,  # No equivalent
}


def find_ffmpeg():
    """Find ffmpeg executable."""
    # Check if ffmpeg is in PATH
    if shutil.which('ffmpeg'):
        return 'ffmpeg'

    # Check common Windows locations
    common_paths = [
        r'C:\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe',
        os.path.expanduser(r'~\ffmpeg\bin\ffmpeg.exe'),
    ]

    for path in common_paths:
        if os.path.isfile(path):
            return path

    return None


def convert_wav_to_ogg(input_path, output_path, ffmpeg_path='ffmpeg'):
    """Convert a WAV file to OGG using ffmpeg."""
    try:
        cmd = [
            ffmpeg_path,
            '-i', input_path,
            '-c:a', 'libvorbis',
            '-q:a', '4',  # Quality level (0-10, 4 is good balance)
            '-y',  # Overwrite output
            output_path
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )

        return result.returncode == 0
    except Exception as e:
        print(f"  Error converting: {e}")
        return False


def copy_ogg(input_path, output_path):
    """Copy an OGG file directly."""
    try:
        shutil.copy2(input_path, output_path)
        return True
    except Exception as e:
        print(f"  Error copying: {e}")
        return False


def get_sound_files(directory, extension):
    """Get all sound files with the given extension from a directory."""
    files = {}
    for filename in os.listdir(directory):
        if filename.lower().endswith(extension):
            name = os.path.splitext(filename)[0]
            files[name] = os.path.join(directory, filename)
    return files


def convert_soundpack(source_dir, dest_dir, pack_type, ffmpeg_path=None):
    """Convert a soundpack from TweeseCake or TWBlue format to FastSM format."""

    # Select the appropriate mapping
    if pack_type == 'tweesecake':
        mapping = TWEESECAKE_MAP
        extension = '.wav'
        needs_conversion = True
    else:
        mapping = TWBLUE_MAP
        extension = '.ogg'
        needs_conversion = False

    # Create destination directory
    os.makedirs(dest_dir, exist_ok=True)

    # Get source files
    source_files = get_sound_files(source_dir, extension)

    if not source_files:
        print(f"No {extension} files found in {source_dir}")
        return False

    print(f"\nFound {len(source_files)} sound files to process.\n")

    converted = 0
    skipped = 0
    failed = 0
    unmapped = []

    for source_name, source_path in sorted(source_files.items()):
        # Look up the FastSM name (case insensitive)
        source_name_lower = source_name.lower()
        fastsm_name = mapping.get(source_name_lower)

        if fastsm_name is None:
            if source_name_lower in mapping:
                # Explicitly mapped to None (no equivalent)
                print(f"  Skipping {source_name}{extension} (no FastSM equivalent)")
                skipped += 1
            else:
                # Unknown sound
                unmapped.append(source_name)
            continue

        dest_path = os.path.join(dest_dir, fastsm_name + '.ogg')

        print(f"  {source_name}{extension} -> {fastsm_name}.ogg", end='')

        if needs_conversion:
            if convert_wav_to_ogg(source_path, dest_path, ffmpeg_path):
                print(" [OK]")
                converted += 1
            else:
                print(" [FAILED]")
                failed += 1
        else:
            if copy_ogg(source_path, dest_path):
                print(" [OK]")
                converted += 1
            else:
                print(" [FAILED]")
                failed += 1

    # Report unmapped files
    if unmapped:
        print(f"\nThe following sounds were not recognized and skipped:")
        for name in unmapped:
            print(f"  - {name}{extension}")
        print("\nYou may want to manually copy and rename these if needed.")

    print(f"\nConversion complete!")
    print(f"  Converted: {converted}")
    print(f"  Skipped:   {skipped}")
    print(f"  Failed:    {failed}")
    print(f"  Unmapped:  {len(unmapped)}")

    return failed == 0


def main():
    print("=" * 60)
    print("FastSM Soundpack Converter")
    print("=" * 60)
    print()
    print("This tool converts soundpacks from TweeseCake or TWBlue")
    print("format to FastSM format.")
    print()

    # Ask for source type
    while True:
        print("What type of soundpack are you converting?")
        print("  1. TweeseCake (WAV files)")
        print("  2. TWBlue (OGG files)")
        print()
        choice = input("Enter 1 or 2: ").strip()

        if choice == '1':
            pack_type = 'tweesecake'
            break
        elif choice == '2':
            pack_type = 'twblue'
            break
        else:
            print("Please enter 1 or 2.\n")

    # For TweeseCake, check for ffmpeg
    ffmpeg_path = None
    if pack_type == 'tweesecake':
        print("\nTweeseCake uses WAV files, which need to be converted to OGG.")
        print("Checking for ffmpeg...")

        ffmpeg_path = find_ffmpeg()

        if ffmpeg_path:
            print(f"Found ffmpeg: {ffmpeg_path}")
        else:
            print("\nffmpeg not found!")
            print("Please install ffmpeg and make sure it's in your PATH,")
            print("or enter the full path to ffmpeg.exe:")
            custom_path = input("Path (or press Enter to abort): ").strip()

            if custom_path and os.path.isfile(custom_path):
                ffmpeg_path = custom_path
            else:
                print("Cannot convert WAV files without ffmpeg. Aborting.")
                return 1

    # Ask for source directory
    print()
    print("Enter the path to the source soundpack directory:")
    source_dir = input("> ").strip().strip('"')

    if not os.path.isdir(source_dir):
        print(f"Directory not found: {source_dir}")
        return 1

    # Ask for destination directory/name
    print()
    print("Enter a name for the new soundpack (will be created in FastSM/sounds/):")
    pack_name = input("> ").strip()

    if not pack_name:
        print("No name provided. Aborting.")
        return 1

    # Sanitize pack name
    pack_name = "".join(c for c in pack_name if c.isalnum() or c in '._- ')

    # Determine destination path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dest_dir = os.path.join(script_dir, 'sounds', pack_name)

    if os.path.exists(dest_dir):
        print(f"\nWarning: {dest_dir} already exists.")
        overwrite = input("Overwrite? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("Aborting.")
            return 1

    print(f"\nConverting soundpack to: {dest_dir}")
    print("-" * 60)

    # Perform conversion
    success = convert_soundpack(source_dir, dest_dir, pack_type, ffmpeg_path)

    if success:
        print()
        print("=" * 60)
        print(f"Soundpack '{pack_name}' has been created!")
        print()
        print("To use this soundpack in FastSM:")
        print("  1. Open FastSM")
        print("  2. Go to Account Options (Ctrl+Shift+A)")
        print("  3. Select the soundpack from the dropdown")
        print("=" * 60)

    return 0 if success else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)
