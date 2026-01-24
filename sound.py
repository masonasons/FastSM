import os
import sys
import sound_lib
from sound_lib import stream
from sound_lib import output as o
import speak
import re

def _setup_vlc_path():
	"""Set up VLC library path for bundled or system VLC."""
	def _configure_vlc_env(vlc_path):
		"""Configure environment for a VLC installation path. Returns True if valid."""
		if sys.platform == 'win32':
			lib_path = os.path.join(vlc_path, 'libvlc.dll')
		elif sys.platform == 'darwin':
			lib_path = os.path.join(vlc_path, 'lib', 'libvlc.dylib')
		else:
			lib_path = os.path.join(vlc_path, 'libvlc.so')

		# Only set env vars if the library file actually exists
		if not os.path.isfile(lib_path):
			return False

		os.environ['PYTHON_VLC_MODULE_PATH'] = vlc_path
		os.environ['PYTHON_VLC_LIB_PATH'] = lib_path
		# Set VLC_PLUGIN_PATH so VLC can find its plugins
		os.environ['VLC_PLUGIN_PATH'] = os.path.join(vlc_path, 'plugins')
		# Also add to PATH for DLL loading on Windows
		if sys.platform == 'win32':
			os.environ['PATH'] = vlc_path + os.pathsep + os.environ.get('PATH', '')
		return True

	# Check for bundled VLC libraries first (vlc folder next to app)
	if getattr(sys, 'frozen', False):
		# Running as frozen app (PyInstaller)
		if sys.platform == 'darwin':
			# macOS: check in Resources/vlc
			base = os.path.join(os.path.dirname(sys.executable), '..', 'Resources')
		else:
			# Windows: check in vlc subfolder next to executable
			base = os.path.dirname(sys.executable)

		vlc_path = os.path.join(base, 'vlc')
		if os.path.exists(vlc_path) and _configure_vlc_env(vlc_path):
			return vlc_path
	else:
		# Development mode - check for vlc folder in project
		vlc_path = os.path.join(os.path.dirname(__file__), 'vlc')
		if os.path.exists(vlc_path) and _configure_vlc_env(vlc_path):
			return vlc_path

	# Check system VLC installation paths
	if sys.platform == 'win32':
		system_paths = [
			os.path.join(os.environ.get('PROGRAMFILES', ''), 'VideoLAN', 'VLC'),
			os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'VideoLAN', 'VLC'),
			'C:\\Program Files\\VideoLAN\\VLC',
			'C:\\Program Files (x86)\\VideoLAN\\VLC',
		]
		for path in system_paths:
			if path and os.path.exists(path) and _configure_vlc_env(path):
				return path
	elif sys.platform == 'darwin':
		system_paths = [
			'/Applications/VLC.app/Contents/MacOS',
			os.path.expanduser('~/Applications/VLC.app/Contents/MacOS'),
		]
		for path in system_paths:
			if os.path.exists(path) and _configure_vlc_env(path):
				return path

	return None

# Disable VLC entirely on macOS - causes crashes
if sys.platform == 'darwin':
	VLC_AVAILABLE = False
	vlc = None
	_vlc_path = None
else:
	# Set up VLC path before importing
	_vlc_path = _setup_vlc_path()

	# Clear any stale PYTHON_VLC_LIB_PATH if we didn't set it ourselves
	# This prevents errors when users have invalid paths in their environment
	if _vlc_path is None and 'PYTHON_VLC_LIB_PATH' in os.environ:
		del os.environ['PYTHON_VLC_LIB_PATH']
	if _vlc_path is None and 'PYTHON_VLC_MODULE_PATH' in os.environ:
		del os.environ['PYTHON_VLC_MODULE_PATH']

	try:
		import vlc
		# Test that VLC libraries are actually available
		_test_instance = vlc.Instance('--quiet')
		if _test_instance:
			_test_instance.log_unset()
			_test_instance.release()
			VLC_AVAILABLE = True
		else:
			VLC_AVAILABLE = False
	except (ImportError, OSError, FileNotFoundError, AttributeError, Exception) as e:
		# Catch all exceptions - VLC import can fail in various ways
		VLC_AVAILABLE = False
		vlc = None

def _find_ytdlp_executable():
	"""Find yt-dlp executable path."""
	import shutil
	from application import get_app

	# Determine executable name based on platform
	exe_name = 'yt-dlp.exe' if sys.platform == 'win32' else 'yt-dlp'

	# Check user-configured path first
	try:
		app = get_app()
		custom_path = getattr(app.prefs, 'ytdlp_path', '')
		if custom_path and os.path.isfile(custom_path):
			return custom_path
	except:
		pass

	# Check config directory (where download button saves it)
	try:
		app = get_app()
		config_path = os.path.join(app.confpath, exe_name)
		if os.path.isfile(config_path):
			return config_path
	except:
		pass

	# Check bundled location
	if getattr(sys, 'frozen', False):
		# Frozen app - check next to executable
		bundled = os.path.join(os.path.dirname(sys.executable), exe_name)
		if os.path.isfile(bundled):
			return bundled
	else:
		# Development - check in project folder
		bundled = os.path.join(os.path.dirname(__file__), exe_name)
		if os.path.isfile(bundled):
			return bundled

	# Check system PATH
	system_ytdlp = shutil.which('yt-dlp') or shutil.which('yt-dlp.exe')
	if system_ytdlp:
		return system_ytdlp

	return None

YTDLP_PATH = _find_ytdlp_executable()

out = None  # Will be initialized with selected device
handles = []  # List of active sound handles for concurrent playback
player = None  # Media player for URL streams (VLC or sound_lib)
player_type = None  # 'vlc' or 'soundlib' to track which player is active
vlc_instance = None  # VLC instance (reused for efficiency)

def get_output_devices():
	"""Get list of available audio output devices.

	Returns:
		List of tuples: (device_index, device_name)
	"""
	devices = []
	try:
		from ctypes import byref

		# Enumerate devices - device 0 is "no sound", real devices start at 1
		i = 1
		while True:
			info = o.BASS_DEVICEINFO()
			if not o.BASS_GetDeviceInfo(i, byref(info)):
				break
			# Only include enabled devices with valid names
			if info.name and (info.flags & o.BASS_DEVICE_ENABLED):
				try:
					name = info.name.decode('utf-8', errors='replace')
					if name.strip():  # Only add non-empty names
						devices.append((i, name))
				except:
					pass
			i += 1
	except Exception as e:
		# Log the error for debugging
		import logging
		logging.warning(f"Could not enumerate audio devices: {e}")

	# If no devices found, add a default entry so the UI isn't empty
	if not devices:
		devices.append((1, "Default audio device"))

	return devices

def init_audio_output(device_index=1):
	"""Initialize audio output with the specified device. Call from application after prefs load."""
	global out, vlc_instance

	# Free existing output first
	if out is not None:
		try:
			out.free()
		except:
			pass
		out = None

	try:
		out = o.Output(device=device_index)
	except Exception as e:
		# Fall back to device 1 (default) if device selection fails
		try:
			out = o.Output(device=1)
		except:
			pass

	# Reset VLC instance so it gets recreated with new settings on next playback
	if vlc_instance is not None:
		try:
			vlc_instance.release()
		except:
			pass
		vlc_instance = None

# Initialize with default device (1) for now - will be reinited from application.py with selected device
init_audio_output(1)

def _extract_stream_url(url):
	"""Use yt-dlp executable to extract direct stream URL from YouTube and similar services."""
	import subprocess

	# Re-check for yt-dlp in case user configured it after startup
	global YTDLP_PATH
	if not YTDLP_PATH:
		YTDLP_PATH = _find_ytdlp_executable()
	if not YTDLP_PATH:
		return url

	# Only use yt-dlp for URLs it supports (YouTube, etc.)
	youtube_patterns = [
		'youtube.com', 'youtu.be',
		'twitter.com', 'x.com',
		'tiktok.com',
		'twitch.tv',
	]

	if not any(pattern in url.lower() for pattern in youtube_patterns):
		return url

	try:
		from application import get_app
		speak.speak("Extracting audio...")

		# Build command with optional cookies and environment
		# Use --no-warnings and -q to suppress non-URL output that pollutes stdout
		cmd = [YTDLP_PATH, '-f', 'bestaudio/best', '-g', '--no-playlist', '--no-warnings', '-q']

		# Add cookies file if configured
		cookies_path = getattr(get_app().prefs, 'ytdlp_cookies', '')
		if cookies_path and os.path.isfile(cookies_path):
			cmd.extend(['--cookies', cookies_path])

		cmd.append(url)

		# Set up environment with Deno path if configured
		env = os.environ.copy()
		deno_path = getattr(get_app().prefs, 'deno_path', '')
		if deno_path:
			# Support both file path to deno executable and directory containing it
			if os.path.isfile(deno_path):
				deno_dir = os.path.dirname(deno_path)
				deno_exe = deno_path
			elif os.path.isdir(deno_path):
				deno_dir = deno_path
				# Check for deno executable in the directory
				if sys.platform == 'win32':
					deno_exe = os.path.join(deno_path, 'deno.exe')
				else:
					deno_exe = os.path.join(deno_path, 'deno')
			else:
				deno_dir = None
				deno_exe = None

			if deno_dir and os.path.exists(deno_dir):
				# Add Deno's directory to PATH (at the front so it's found first)
				env['PATH'] = deno_dir + os.pathsep + env.get('PATH', '')
				# Set DENO_DIR to help yt-dlp find Deno cache
				if 'DENO_DIR' not in env:
					env['DENO_DIR'] = os.path.join(deno_dir, '.deno')
				# Some extractors look for DENO_INSTALL_ROOT
				if 'DENO_INSTALL_ROOT' not in env:
					env['DENO_INSTALL_ROOT'] = deno_dir

		result = subprocess.run(
			cmd,
			capture_output=True,
			text=True,
			timeout=60,
			env=env,
			creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
		)
		if result.returncode == 0 and result.stdout.strip():
			return result.stdout.strip().split('\n')[0]  # First URL if multiple
		# yt-dlp failed - show error
		if result.stderr.strip():
			speak.speak(f"yt-dlp error: {result.stderr.strip()[:100]}")
	except subprocess.TimeoutExpired:
		speak.speak("Timed out extracting stream URL (yt-dlp took too long)")
	except Exception as e:
		speak.speak(f"Could not extract stream URL: {e}")
	return url

def return_url(url):
	return url

media_matchlist = [
	{"match": r"https://sndup.net/[a-zA-Z0-9]+/[ad]$", "func":return_url},
	# Audio/video file extensions (non-greedy, allows query strings)
	{"match": r"^https?://[^\s]+?\.(mp3|m4a|ogg|opus|flac|wav|aac|mp4|webm|mov|avi)(\?[^\s]*)?$", "func":return_url},
	# Streaming URLs with port numbers
	{"match": r"^https?://[^\s:]+:\d+(\/[^\s]*)?$", "func":return_url},
	{"match": r"https?://twitter.com/.+/status/.+/video/.+", "func":return_url},
	{"match": r"https?://twitch.tv/.+", "func":return_url},
	{"match": r"https?://vm.tiktok.com/.+", "func":return_url},
	{"match": r"https?://soundcloud.com/.+", "func":return_url},
	{"match": r"https?://t.co/.+", "func":return_url},
]

# URLs that need yt-dlp extraction (YouTube, etc.) - work with VLC or sound_lib
ytdlp_matchlist = [
	{"match": r"https?://(www\.)?(youtube\.com|youtu\.be)/.+", "func":return_url},
]

def get_media_urls(urls):
	result = []
	for u in urls:
		# Check standard media URLs (work with both VLC and sound_lib)
		for service in media_matchlist:
			if re.match(service['match'], u.lower()) != None:
				result.append({"url":u, "func":service['func']})
				break
		else:
			# Check yt-dlp supported URLs (YouTube, etc.)
			# These work with both VLC and sound_lib via yt-dlp stream extraction
			for service in ytdlp_matchlist:
				if re.match(service['match'], u.lower()) != None:
					# Prefer VLC if available, but sound_lib works too
					result.append({"url":u, "func":service['func'], "vlc_only": VLC_AVAILABLE})
					break
	return result

def has_audio_attachment(status):
	"""Check if a status has an audio attachment."""
	media_attachments = getattr(status, 'media_attachments', []) or []
	for attachment in media_attachments:
		media_type = getattr(attachment, 'type', '') or ''
		if media_type.lower() == 'audio':
			return True
	return False

def has_image_attachment(status):
	"""Check if a status has an image attachment."""
	media_attachments = getattr(status, 'media_attachments', []) or []
	for attachment in media_attachments:
		media_type = getattr(attachment, 'type', '') or ''
		if media_type.lower() == 'image':
			return True
	return False

def get_media_type_for_earcon(status):
	"""Get the appropriate earcon type for a status's media.
	Returns 'image' for images, 'media' for other media types, None if no media."""
	media_attachments = getattr(status, 'media_attachments', []) or []
	has_image = False
	has_other_media = False
	for attachment in media_attachments:
		# Handle both objects (from API) and dicts (from cache)
		if isinstance(attachment, dict):
			media_type = attachment.get('type', '') or ''
		else:
			media_type = getattr(attachment, 'type', '') or ''
		media_type = media_type.lower()
		if media_type == 'image':
			has_image = True
		elif media_type in ('video', 'gifv', 'audio'):
			has_other_media = True
	# Prioritize image sound if there are images
	if has_image:
		return 'image'
	elif has_other_media:
		return 'media'
	return None

def _cleanup_finished_handles():
	"""Remove handles that have finished playing."""
	global handles
	active = []
	for h in handles:
		try:
			# Check if still playing (is_playing property or similar)
			if h.is_playing:
				active.append(h)
			else:
				try:
					h.free()
				except sound_lib.main.BassError:
					pass
		except (sound_lib.main.BassError, AttributeError):
			# Handle is invalid or already freed, skip it
			pass
	handles = active

def _get_bundled_path():
	"""Get the path to bundled resources (for PyInstaller frozen apps)."""
	import sys
	import platform
	if getattr(sys, 'frozen', False):
		# Running as frozen app (PyInstaller)
		if platform.system() == 'Darwin':
			# macOS .app bundle: Resources are in Contents/Resources
			# sys.executable is at Contents/MacOS/AppName
			return os.path.join(os.path.dirname(sys.executable), '..', 'Resources')
		else:
			# Windows/Linux: sounds/keymaps are in the same directory as the executable
			# (not in _MEIPASS/_internal, which is for Python modules)
			return os.path.dirname(sys.executable)
	return None

def play(account, filename, pack="", wait=False):
	global handles
	app = account.app

	# Clean up finished handles before playing new sound
	_cleanup_finished_handles()

	# Get bundled path for frozen apps (macOS app bundle, Windows exe)
	bundled_path = _get_bundled_path()

	path = None
	# Check user config first (highest priority)
	if os.path.exists(app.confpath + "/sounds/" + account.prefs.soundpack + "/" + filename + ".ogg"):
		path = app.confpath + "/sounds/" + account.prefs.soundpack + "/" + filename + ".ogg"
	# Check relative path (for development)
	elif os.path.exists("sounds/" + account.prefs.soundpack + "/" + filename + ".ogg"):
		path = "sounds/" + account.prefs.soundpack + "/" + filename + ".ogg"
	# Check bundled path (for frozen apps)
	elif bundled_path and os.path.exists(bundled_path + "/sounds/" + account.prefs.soundpack + "/" + filename + ".ogg"):
		path = bundled_path + "/sounds/" + account.prefs.soundpack + "/" + filename + ".ogg"
	# Fall back to default soundpack - user config
	elif os.path.exists(app.confpath + "/sounds/default/" + filename + ".ogg"):
		path = app.confpath + "/sounds/default/" + filename + ".ogg"
	# Fall back to default - relative path
	elif os.path.exists("sounds/default/" + filename + ".ogg"):
		path = "sounds/default/" + filename + ".ogg"
	# Fall back to default - bundled path
	elif bundled_path and os.path.exists(bundled_path + "/sounds/default/" + filename + ".ogg"):
		path = bundled_path + "/sounds/default/" + filename + ".ogg"

	if not path:
		return
	try:
		handle = stream.FileStream(file=path)
		handle.pan = account.prefs.soundpan
		# Use per-account soundpack volume (with fallback for old configs)
		handle.volume = getattr(account.prefs, 'soundpack_volume', 1.0)
		handle.looping = False
		if wait:
			handle.play_blocking()
		else:
			handle.play()
			handles.append(handle)
	except sound_lib.main.BassError:
		pass

def play_url(url, vlc_only=False):
	global player, player_type, vlc_instance
	from application import get_app

	# Stop any existing playback
	stop()

	# Try VLC first if available
	if VLC_AVAILABLE:
		try:
			# Create VLC instance if needed
			if vlc_instance is None:
				# Use --quiet like TWBlue does, add network caching for streams
				# --no-video disables video output (prevents DirectX window from appearing)
				# --vout=dummy is a fallback to ensure no video window
				vlc_args = ['--quiet', '--network-caching=1000', '--no-video', '--vout=dummy']
				# If using bundled VLC, set paths
				if _vlc_path:
					vlc_args.append(f'--data-path={_vlc_path}')
				vlc_instance = vlc.Instance(' '.join(vlc_args))
				vlc_instance.log_unset()

			# Extract actual stream URL for YouTube and similar services
			stream_url = _extract_stream_url(url)

			# Create media player
			player = vlc_instance.media_player_new()
			media = vlc_instance.media_new(stream_url)
			player.set_media(media)
			# Apply media volume from preferences (VLC uses 0-100)
			volume = int(getattr(get_app().prefs, 'media_volume', 1.0) * 100)
			player.audio_set_volume(volume)
			player.play()
			player_type = 'vlc'
			# Auto-open audio player if setting enabled
			if getattr(get_app().prefs, 'auto_open_audio_player', False):
				try:
					from GUI import audio_player
					audio_player.auto_show_audio_player()
				except:
					pass
			return
		except Exception as e:
			# VLC failed, fall through to sound_lib (unless vlc_only)
			if vlc_only:
				speak.speak(f"VLC failed to play: {e}")
				return

	# If this URL requires VLC and VLC isn't available, inform user
	if vlc_only and not VLC_AVAILABLE:
		speak.speak("This URL requires VLC media player which is not available.")
		return

	# Fall back to sound_lib
	# Extract actual stream URL for YouTube and similar services
	stream_url = _extract_stream_url(url)

	try:
		player = stream.URLStream(url=stream_url)
		# Apply media volume from preferences
		player.volume = getattr(get_app().prefs, 'media_volume', 1.0)
		player.play()
		player_type = 'soundlib'
		# Auto-open audio player if setting enabled
		if getattr(get_app().prefs, 'auto_open_audio_player', False):
			try:
				from GUI import audio_player
				audio_player.auto_show_audio_player()
			except:
				pass
	except Exception as e:
		speak.speak(f"Could not play audio: {e}")

def stop():
	"""Stop media player (URL streams)."""
	global player, player_type
	if player is not None:
		try:
			player.stop()
			# VLC uses release(), sound_lib uses free()
			if player_type == 'vlc':
				player.release()
			else:
				player.free()
		except:
			pass
		player = None
		player_type = None
		# Close audio player dialog if open
		try:
			from GUI import audio_player
			audio_player.close_audio_player()
		except:
			pass

def stop_all():
	"""Stop all sounds including UI sounds and media player."""
	global handles, player
	# Stop media player
	stop()
	# Stop all UI sound handles
	for h in handles:
		try:
			h.stop()
			h.free()
		except sound_lib.main.BassError:
			pass
	handles = []
