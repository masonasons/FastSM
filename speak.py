"""Speech output via prism, with an accessible_output2 fallback for users who
hit prism-specific issues on Windows/macOS.

The legacy backend is gated behind the use_legacy_speech pref (Advanced tab).
Linux builds don't ship accessible_output2 at all, so the fallback path is
prism-only there.

On macOS, prefer VoiceOver so FastSM speaks through the active screen reader
instead of firing up AV Speech as a separate TTS voice. Windows and Linux use
prism's own ranking (which picks the active screen reader when one is running).

AV Speech on macOS must be driven from the main thread, so off-thread callers
are marshalled via wx.CallAfter.

The backend is re-detected dynamically: if speak() raises PrismError (the
screen reader quit, the audio device went away, etc.) we drop the cached
backend and try again. We also periodically re-check whether a higher-priority
backend has appeared since we last picked one, so a screen reader that starts
after FastSM doesn't leave us stuck on a fallback.
"""

import sys
import threading
import time

import prism


_main_thread_id = threading.main_thread().ident
_context = prism.Context()
_prism_backend = None
_prism_backend_id = None
_last_recheck = 0.0
_RECHECK_INTERVAL = 5.0
_lock = threading.Lock()

# Legacy accessible_output2 backend, lazily imported so the dependency is only
# loaded when the user actually opts into it.
_a2_speaker = None
_a2_imported = False


def _use_legacy():
	"""Read the use_legacy_speech pref without making speak.py import-cycle on application."""
	if sys.platform.startswith('linux'):
		return False
	try:
		from application import get_app
		app = get_app()
		if app is None:
			return False
		return bool(getattr(app.prefs, 'use_legacy_speech', False))
	except Exception:
		return False


def _get_a2_speaker():
	"""Lazily import accessible_output2 and return its auto-picked speaker."""
	global _a2_speaker, _a2_imported
	if _a2_imported:
		return _a2_speaker
	_a2_imported = True
	try:
		from accessible_output2 import outputs
		_a2_speaker = outputs.auto.Auto()
	except Exception:
		_a2_speaker = None
	return _a2_speaker


def _create_backend():
	"""Create the best available backend, preferring VoiceOver on macOS.

	Returns (backend, backend_id) so we can tell later whether a more-preferred
	backend has come online without rebuilding the current one to compare.
	"""
	if sys.platform == 'darwin' and _context.exists(prism.BackendId.VOICE_OVER):
		try:
			return _context.create(prism.BackendId.VOICE_OVER), prism.BackendId.VOICE_OVER
		except prism.PrismError:
			pass
	backend = _context.create_best()
	return backend, getattr(backend, 'id', None)


def _preferred_backend_changed():
	"""Return True if a higher-priority backend than the cached one is now available."""
	if sys.platform == 'darwin' and _prism_backend_id != prism.BackendId.VOICE_OVER:
		try:
			if _context.exists(prism.BackendId.VOICE_OVER):
				return True
		except prism.PrismError:
			return False
	return False


def _get_prism_backend():
	global _prism_backend, _prism_backend_id, _last_recheck
	with _lock:
		now = time.monotonic()
		if _prism_backend is not None and now - _last_recheck >= _RECHECK_INTERVAL:
			_last_recheck = now
			if _preferred_backend_changed():
				_prism_backend = None
				_prism_backend_id = None
		if _prism_backend is None:
			_prism_backend, _prism_backend_id = _create_backend()
			_last_recheck = time.monotonic()
		return _prism_backend


def _invalidate_backend():
	global _prism_backend, _prism_backend_id
	with _lock:
		_prism_backend = None
		_prism_backend_id = None


def reset_backend():
	"""Force re-detection of the speech backend on the next speak() call."""
	_invalidate_backend()


def _try_speak(text, interrupt):
	backend = _get_prism_backend()
	backend.speak(text, interrupt)
	try:
		backend.braille(text)
	except Exception:
		pass


def _speak_via_a2(text, interrupt):
	speaker = _get_a2_speaker()
	if speaker is None:
		return False
	try:
		speaker.speak(text, interrupt=interrupt)
		try:
			speaker.braille(text)
		except Exception:
			pass
		return True
	except Exception:
		return False


def _do_speak(text, interrupt):
	# Backend creation is deferred to first speak() because prism's macOS
	# VoiceOver backend needs an NSWindow to exist when create() is called —
	# warming up at import time runs before GUI.main has built the wxFrame,
	# so VOICE_OVER returns BackendNotAvailable and we'd get stuck on AV Speech.
	if _use_legacy():
		if _speak_via_a2(text, interrupt):
			return
		# accessible_output2 import or speak failed — fall through to prism so
		# the user still hears something instead of going silent.
	try:
		_try_speak(text, interrupt)
	except prism.PrismError:
		# The current backend died (screen reader closed, audio bus dropped,
		# etc.). Drop it and retry once with a fresh pick.
		_invalidate_backend()
		try:
			_try_speak(text, interrupt)
		except prism.PrismError:
			pass


def speak(text, interrupt=False):
	if sys.platform == 'darwin' and threading.current_thread().ident != _main_thread_id:
		try:
			import wx
			wx.CallAfter(_do_speak, text, interrupt)
		except Exception:
			_do_speak(text, interrupt)
	else:
		_do_speak(text, interrupt)
