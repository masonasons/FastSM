"""Speech output using accessible_output2."""

import sys
import threading

from accessible_output2 import outputs

speaker = outputs.auto.Auto()
_main_thread_id = threading.main_thread().ident

def _do_speak(text, interrupt):
	"""Internal function that actually speaks."""
	speaker.speak(text, interrupt)
	speaker.braille(text)

def speak(text, interrupt=False):
	"""Speak text, ensuring thread safety on Mac."""
	# On Mac, accessible_output2 must be called from main thread
	if sys.platform == 'darwin' and threading.current_thread().ident != _main_thread_id:
		try:
			import wx
			wx.CallAfter(_do_speak, text, interrupt)
		except:
			# If wx not available, try anyway
			_do_speak(text, interrupt)
	else:
		_do_speak(text, interrupt)
