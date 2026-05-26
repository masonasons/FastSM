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

The backend is re-detected dynamically: if the backend raises (the screen
reader quit, the audio device went away, prism exposed a native/DBus failure,
etc.) we drop the cached backend and try again. We also periodically re-check
whether a higher-priority backend has appeared since we last picked one, so a
screen reader that starts after FastSM doesn't leave us stuck on a fallback.
"""

import importlib
import logging
import sys
import threading
import time


_main_thread_id = threading.main_thread().ident
_prism = None
_context = None
_prism_backend = None
_prism_backend_id = None
_last_recheck = 0.0
_RECHECK_INTERVAL = 5.0
_PRISM_FAILURE_BACKOFF = 30.0
_prism_backoff_until = 0.0
_lock = threading.Lock()
_shutdown_started = False
_logger = logging.getLogger("fastsm.speech")

# Legacy accessible_output2 backend, lazily imported so the dependency is only
# loaded when the user actually opts into it.
_a2_speaker = None
_a2_imported = False


class _SpeechBackendUnavailable(Exception):
	pass


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


def _prism_backoff_active():
	return time.monotonic() < _prism_backoff_until


def _log_prism_failure(action, error, backoff=False):
	try:
		extra = " Temporarily disabling prism speech." if backoff else ""
		fastsm_logger = logging.getLogger("fastsm")
		if not fastsm_logger.handlers:
			return
		_logger.warning("Prism speech %s failed: %s.%s", action, error, extra)
		_logger.debug("Prism speech %s traceback", action, exc_info=True)
	except Exception:
		pass


def _get_prism_module():
	global _prism
	if _prism_backoff_active():
		raise _SpeechBackendUnavailable("prism speech is in failure backoff")
	if _prism is None:
		_prism = importlib.import_module("prism")
	return _prism


def _get_context():
	global _context
	if _context is None:
		_context = _get_prism_module().Context()
	return _context


def _create_backend():
	"""Create the best available backend, preferring VoiceOver on macOS.

	Returns (backend, backend_id) so we can tell later whether a more-preferred
	backend has come online without rebuilding the current one to compare.
	"""
	prism = _get_prism_module()
	context = _get_context()
	if sys.platform == 'darwin':
		try:
			if context.exists(prism.BackendId.VOICE_OVER):
				return context.create(prism.BackendId.VOICE_OVER), prism.BackendId.VOICE_OVER
		except Exception as error:
			_log_prism_failure("VoiceOver detection", error)
			pass
	backend = context.create_best()
	return backend, getattr(backend, 'id', None)


def _preferred_backend_changed():
	"""Return True if a higher-priority backend than the cached one is now available."""
	prism = _get_prism_module()
	context = _get_context()
	if sys.platform == 'darwin' and _prism_backend_id != prism.BackendId.VOICE_OVER:
		try:
			if context.exists(prism.BackendId.VOICE_OVER):
				return True
		except Exception as error:
			_log_prism_failure("VoiceOver recheck", error)
			return False
	return False


def _get_prism_backend():
	global _prism_backend, _prism_backend_id, _last_recheck, _context
	with _lock:
		now = time.monotonic()
		if _prism_backend is not None and now - _last_recheck >= _RECHECK_INTERVAL:
			_last_recheck = now
			if _preferred_backend_changed():
				_prism_backend = None
				_prism_backend_id = None
		if _prism_backend is None:
			try:
				_prism_backend, _prism_backend_id = _create_backend()
				_last_recheck = time.monotonic()
			except Exception:
				_context = None
				raise
		return _prism_backend


def _invalidate_backend(reset_context=False, backoff=False, reset_backoff=False):
	global _context, _prism_backend, _prism_backend_id, _prism_backoff_until
	with _lock:
		_prism_backend = None
		_prism_backend_id = None
		if reset_context:
			_context = None
		if reset_backoff:
			_prism_backoff_until = 0.0
		if backoff:
			_prism_backoff_until = time.monotonic() + _PRISM_FAILURE_BACKOFF


def reset_backend():
	"""Force re-detection of the speech backend on the next speak() call."""
	_invalidate_backend(reset_context=True, reset_backoff=True)


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


def _shutdown_active():
	with _lock:
		return _shutdown_started


def _start_shutdown():
	global _shutdown_started
	with _lock:
		if _shutdown_started:
			return False
		_shutdown_started = True
		return True


def _do_speak(text, interrupt, retry=True, allow_shutdown=False):
	if _shutdown_active() and not allow_shutdown:
		return
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
	except _SpeechBackendUnavailable:
		pass
	except Exception as error:
		# The current backend died or prism exposed a native/DBus backend
		# failure outside PrismError (for example an unsupported Orca DBus API).
		# Drop it and retry once with a fresh pick, but never let speech output
		# abort callers such as application shutdown.
		_log_prism_failure("output", error)
		if not retry:
			_invalidate_backend(reset_context=True, backoff=True)
			return
		_invalidate_backend()
		try:
			_try_speak(text, interrupt)
		except _SpeechBackendUnavailable:
			pass
		except Exception as retry_error:
			_log_prism_failure("retry", retry_error, backoff=True)
			_invalidate_backend(reset_context=True, backoff=True)
			pass


def speak(text, interrupt=False):
	if _shutdown_active():
		return
	if sys.platform == 'darwin' and threading.current_thread().ident != _main_thread_id:
		try:
			import wx
			wx.CallAfter(_do_speak, text, interrupt)
		except Exception:
			if not _shutdown_active():
				_do_speak(text, interrupt)
	else:
		_do_speak(text, interrupt)


def speak_async(text, interrupt=False):
	"""Best-effort speech for non-critical paths that must never block callers."""
	if _shutdown_active():
		return
	try:
		threading.Thread(target=speak, args=(text, interrupt), daemon=True).start()
	except Exception as error:
		_log_prism_failure("async dispatch", error)


def speak_before_shutdown(text, interrupt=False, timeout=0.5):
	"""Speak one shutdown announcement before suppressing any later speech.

	The announcement is allowed a short grace window, but shutdown must continue
	even if a native speech backend blocks.
	"""
	if not _start_shutdown():
		return
	try:
		thread = threading.Thread(
			target=_do_speak,
			args=(text, interrupt),
			kwargs={"retry": False, "allow_shutdown": True},
			daemon=True,
		)
		thread.start()
		thread.join(timeout)
	except Exception as error:
		_log_prism_failure("shutdown dispatch", error)
