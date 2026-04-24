"""Speech output via prism.

Routes speech through the active screen reader where possible, so FastSM
sounds like the rest of the user's desktop instead of a separate TTS voice:
  - Windows: UIA (speaks through whatever AT is focused) -> SAPI/OneCore/JAWS/NVDA
  - macOS:   VoiceOver -> AV Speech
  - Linux:   Orca -> Speech Dispatcher (handled entirely by prism's ranking)

On macOS, AV Speech must be driven from the main thread, so off-thread callers
are marshalled via wx.CallAfter.
"""

import sys
import threading

import prism


_main_thread_id = threading.main_thread().ident
_context = prism.Context()
_prism_backend = None


# Backends to try before prism's own ranking, in preference order per platform.
# The intent is "route through the active assistive tech if it's running,
# otherwise let prism pick."
_PREFERRED_BACKENDS = {
	'win32': (prism.BackendId.UIA,),
	'darwin': (prism.BackendId.VOICE_OVER,),
}


def _get_prism_backend():
	global _prism_backend
	if _prism_backend is not None:
		return _prism_backend
	for backend_id in _PREFERRED_BACKENDS.get(sys.platform, ()):
		if _context.exists(backend_id):
			try:
				_prism_backend = _context.create(backend_id)
				return _prism_backend
			except prism.PrismError:
				continue
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
