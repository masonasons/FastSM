import os
import sound_lib
from sound_lib import stream
from sound_lib import output as o
import speak
import re

out = o.Output()
handles = []  # List of active sound handles for concurrent playback
player = None

def return_url(url):
	return url

media_matchlist = [
	{"match": r"https://sndup.net/[a-zA-Z0-9]+/[ad]$", "func":return_url},
	{"match": r"^http:\/\/\S+(\/\S+)*(\/)?\.(mp3|m4a|ogg|opus|flac)$", "func":return_url},
	{"match": r"^https:\/\/\S+(\/\S+)*(\/)?\.(mp3|m4a|ogg|opus|flac)$", "func":return_url},
	{"match": r"^http:\/\/\S+:[+-]?[1-9]\d*|0(\/\S+)*(\/)?$", "func":return_url},
	{"match": r"^https:\/\/\S+:[+-]?[1-9]\d*|0(\/\S+)*(\/)?$", "func":return_url},
	{"match": r"https?://twitter.com/.+/status/.+/video/.+", "func":return_url},
	{"match": r"https?://twitch.tv/.", "func":return_url},
	{"match": r"http?://twitch.tv/.", "func":return_url},
	{"match": r"https?://vm.tiktok.com/.+", "func":return_url},
	{"match": r"https?://soundcloud.com/.+", "func":return_url},
	{"match": r"https?://t.co/.", "func":return_url},
	{"match": r"^(?:https?:\/\/)?(?:m\.|www\.)?(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))((\w|-){11})(?:\S+)?$", "func":return_url}
]

audio_matchlist = [
	{"match": r"https://sndup.net/[a-zA-Z0-9]+/[ad]$", "func":return_url},
	{"match": r"^http:\/\/\S+(\/\S+)*(\/)?\.(mp3|m4a|ogg|opus|flac)$", "func":return_url},
	{"match": r"^https:\/\/\S+(\/\S+)*(\/)?\.(mp3|m4a|ogg|opus|flac)$", "func":return_url},
]

def get_media_urls(urls):
	result = []
	for u in urls:
		for service in media_matchlist:
			if re.match(service['match'], u.lower()) != None:
				result.append({"url":u, "func":service['func']})
	return result

def get_audio_urls(urls):
	result = []
	for u in urls:
		for service in audio_matchlist:
			if re.match(service['match'], u.lower()) != None:
				result.append({"url":u, "func":service['func']})
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

def play_url(url):
	global player
	try:
		from application import get_app
		player = stream.URLStream(url=url)
		# Apply media volume from preferences
		player.volume = getattr(get_app().prefs, 'media_volume', 1.0)
		player.play()
		# Auto-open audio player if setting enabled
		if getattr(get_app().prefs, 'auto_open_audio_player', False):
			try:
				from GUI import audio_player
				audio_player.auto_show_audio_player()
			except:
				pass
	except:
		speak.speak("Could not play audio.")

def stop():
	"""Stop media player (URL streams)."""
	global player
	if player is not None:
		try:
			player.stop()
			player.free()
		except:
			pass
		player = None
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
