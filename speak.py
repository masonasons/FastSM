"""Speech output with accessible_output2 and Linux fallbacks."""

import atexit
import shutil
import subprocess
import sys
import threading

_main_thread_id = threading.main_thread().ident
_fallback_lock = threading.RLock()
_fallback_process = None
_speechd_client = None

try:
	from accessible_output2 import outputs
	_ao2_speaker = outputs.auto.Auto()
	AO2_AVAILABLE = True
except Exception:
	_ao2_speaker = None
	AO2_AVAILABLE = False


def _normalize_text(text):
	"""Normalize speech text and avoid speaking empty content."""
	if text is None:
		return ""
	return str(text).strip()


def _terminate_process(proc):
	"""Terminate a running subprocess cleanly."""
	if not proc:
		return
	try:
		if proc.poll() is None:
			proc.terminate()
			proc.wait(timeout=0.2)
	except Exception:
		try:
			proc.kill()
		except Exception:
			pass


def _speak_with_speechd(text, interrupt):
	"""Try linux speech-dispatcher Python bindings."""
	global _speechd_client
	if sys.platform != "linux":
		return False
	try:
		if _speechd_client is None:
			import speechd
			_speechd_client = speechd.SSIPClient("FastSM")
		if interrupt:
			_speechd_client.cancel()
		_speechd_client.speak(text)
		return True
	except Exception:
		_speechd_client = None
		return False


def _close_speechd_client():
	"""Close speech-dispatcher client cleanly at process exit."""
	global _speechd_client
	client = _speechd_client
	_speechd_client = None
	if client is not None:
		try:
			client.close()
		except Exception:
			pass


def _get_tts_command(text):
	"""Pick a platform command-line TTS fallback."""
	if sys.platform == "linux":
		if shutil.which("spd-say"):
			return ["spd-say", "--wait", "--", text]
		if shutil.which("espeak-ng"):
			return ["espeak-ng", text]
		if shutil.which("espeak"):
			return ["espeak", text]
	return None


def _speak_with_command(text, interrupt):
	"""Speak through a subprocess TTS command."""
	global _fallback_process
	cmd = _get_tts_command(text)
	if not cmd:
		return False
	with _fallback_lock:
		if interrupt:
			_terminate_process(_fallback_process)
			_fallback_process = None
		try:
			_fallback_process = subprocess.Popen(
				cmd,
				stdout=subprocess.DEVNULL,
				stderr=subprocess.DEVNULL,
			)
			return True
		except Exception:
			return False


def _do_speak(text, interrupt):
	"""Internal function that actually speaks."""
	text = _normalize_text(text)
	if not text:
		return

	if AO2_AVAILABLE:
		_ao2_speaker.speak(text, interrupt)
		_ao2_speaker.braille(text)
		return

	# Linux fallback chain: speech-dispatcher Python bindings -> command-line TTS.
	if _speak_with_speechd(text, interrupt):
		return
	if _speak_with_command(text, interrupt):
		return

	# Last resort fallback if no TTS engine is available.
	try:
		print(text, file=sys.stderr)
	except Exception:
		pass


def speak(text, interrupt=False):
	"""Speak text, ensuring thread safety for AO2 on macOS."""
	# On Mac, accessible_output2 must be called from the main thread.
	if AO2_AVAILABLE and sys.platform == "darwin" and threading.current_thread().ident != _main_thread_id:
		try:
			import wx
			wx.CallAfter(_do_speak, text, interrupt)
		except Exception:
			_do_speak(text, interrupt)
	else:
		_do_speak(text, interrupt)


atexit.register(_close_speechd_client)
