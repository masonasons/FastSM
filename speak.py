"""Speech output via prism's best available backend.

Picks per platform: SAPI / OneCore / JAWS / NVDA on Windows, VoiceOver / AV
Speech on macOS, Orca / Speech Dispatcher on Linux. On macOS, AV Speech must be
driven from the main thread, so off-thread callers are marshalled via wx.
"""

import sys
import threading

import prism


_main_thread_id = threading.main_thread().ident
_context = prism.Context()
_prism_backend = None


def _get_prism_backend():
	global _prism_backend
	if _prism_backend is None:
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
	if sys.platform == 'darwin' and threading.current_thread().ident != _main_thread_id:
		try:
			import wx
			wx.CallAfter(_do_speak, text, interrupt)
		except Exception:
			_do_speak(text, interrupt)
	else:
		_do_speak(text, interrupt)


# Warm up prism at import time so the first speak() call doesn't pay init cost.
_get_prism_backend()
