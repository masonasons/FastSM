"""Speech output via prism.

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


def _do_speak(text, interrupt):
	# Backend creation is deferred to first speak() because prism's macOS
	# VoiceOver backend needs an NSWindow to exist when create() is called —
	# warming up at import time runs before GUI.main has built the wxFrame,
	# so VOICE_OVER returns BackendNotAvailable and we'd get stuck on AV Speech.
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
