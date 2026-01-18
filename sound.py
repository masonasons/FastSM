import os
import sys
import sound_lib
from sound_lib import stream
from sound_lib import output as o
import speak
import re

def _setup_vlc_path():
	"""Set up VLC library path for bundled or system VLC."""
	# Check for bundled VLC libraries first
	if getattr(sys, 'frozen', False):
		# Running as frozen app (PyInstaller)
		if sys.platform == 'darwin':
			# macOS: check in Resources/vlc
			base = os.path.join(os.path.dirname(sys.executable), '..', 'Resources')
		else:
			# Windows: check in vlc subfolder next to executable
			base = os.path.dirname(sys.executable)

		vlc_path = os.path.join(base, 'vlc')
		if os.path.exists(vlc_path):
			# Set environment variables for python-vlc to find bundled libraries
			os.environ['PYTHON_VLC_MODULE_PATH'] = vlc_path
			os.environ['PYTHON_VLC_LIB_PATH'] = os.path.join(vlc_path, 'libvlc.dll') if sys.platform == 'win32' else vlc_path
			# Also add to PATH for DLL loading on Windows
			if sys.platform == 'win32':
				os.environ['PATH'] = vlc_path + os.pathsep + os.environ.get('PATH', '')
			return vlc_path
	else:
		# Development mode - check for vlc folder in project
		vlc_path = os.path.join(os.path.dirname(__file__), 'vlc')
		if os.path.exists(vlc_path):
			os.environ['PYTHON_VLC_MODULE_PATH'] = vlc_path
			os.environ['PYTHON_VLC_LIB_PATH'] = os.path.join(vlc_path, 'libvlc.dll') if sys.platform == 'win32' else vlc_path
			if sys.platform == 'win32':
				os.environ['PATH'] = vlc_path + os.pathsep + os.environ.get('PATH', '')
			return vlc_path
	return None

# Set up VLC path before importing
_vlc_path = _setup_vlc_path()

try:
	import vlc
	# Test that VLC libraries are actually available
	_test_instance = vlc.Instance('--no-video')
	if _test_instance:
		_test_instance.release()
		VLC_AVAILABLE = True
	else:
		VLC_AVAILABLE = False
except (ImportError, OSError, FileNotFoundError, AttributeError):
	VLC_AVAILABLE = False
	vlc = None

out = o.Output()
handles = []  # List of active sound handles for concurrent playback
player = None  # Media player for URL streams (VLC or sound_lib)
player_type = None  # 'vlc' or 'soundlib' to track which player is active
vlc_instance = None  # VLC instance (reused for efficiency)

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

# URLs that require VLC (not supported by sound_lib)
vlc_only_matchlist = [
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
			# Check VLC-only URLs if VLC is available
			if VLC_AVAILABLE:
				for service in vlc_only_matchlist:
					if re.match(service['match'], u.lower()) != None:
						result.append({"url":u, "func":service['func'], "vlc_only": True})
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
			# Windows/Linux: use _MEIPASS or executable directory
			return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
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
				vlc_args = ['--no-video']
				# If using bundled VLC, set paths
				if _vlc_path:
					vlc_args.append(f'--data-path={_vlc_path}')
				vlc_instance = vlc.Instance(' '.join(vlc_args))
			# Create media player
			player = vlc_instance.media_player_new()
			media = vlc_instance.media_new(url)
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
	try:
		player = stream.URLStream(url=url)
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
