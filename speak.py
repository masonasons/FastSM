"""Speech output via prism.

On macOS, prefer VoiceOver so FastSM speaks through the active screen reader
instead of firing up AV Speech as a separate TTS voice. Windows and Linux use
prism's own ranking (which picks the active screen reader when one is running).

AV Speech on macOS must be driven from the main thread, so off-thread callers
are marshalled via wx.CallAfter.
"""

import sys
import threading

import prism


_main_thread_id = threading.main_thread().ident
_context = prism.Context()
_prism_backend = None


def _get_prism_backend():
	global _prism_backend
	if _prism_backend is not None:
		return _prism_backend
	if sys.platform == 'darwin' and _context.exists(prism.BackendId.VOICE_OVER):
		try:
			_prism_backend = _context.create(prism.BackendId.VOICE_OVER)
			return _prism_backend
		except prism.PrismError:
			pass
	_prism_backend = _context.create_best()
	return _prism_backend


def _do_speak(text, interrupt):
	backend = _get_prism_backend()
	backend.speak(text, interrupt)
	try:
		backend.braille(text)
	except Exception:
		pass


def speak(text, interrupt=False):
	# Backend creation is deferred to first speak() because prism's macOS
	# VoiceOver backend needs an NSWindow to exist when create() is called —
	# warming up at import time runs before GUI.main has built the wxFrame,
	# so VOICE_OVER returns BackendNotAvailable and we'd get stuck on AV Speech.
	if sys.platform == 'darwin' and threading.current_thread().ident != _main_thread_id:
		try:
			import wx
			wx.CallAfter(_do_speak, text, interrupt)
		except Exception:
			_do_speak(text, interrupt)
	else:
		_do_speak(text, interrupt)
