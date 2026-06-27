"""Speech output.

Windows / macOS: accessible_output2's auto-picked backend (NVDA/JAWS/SAPI/
OneCore on Windows; VoiceOver on macOS). macOS speech must be driven from the
main thread, so off-thread callers are marshalled via wx.CallAfter.

Linux: talk to Orca directly over its D-Bus service
(org.gnome.Orca.Service.PresentMessage). accessible_output2 has no Linux
backend, and routing through Speech Dispatcher / prism made the screen-reader
case worse than just speaking through Orca itself. A background worker fires
messages NO_REPLY_EXPECTED so callers never block on D-Bus.
"""

import logging
import queue
import sys
import threading


_main_thread_id = threading.main_thread().ident
_logger = logging.getLogger("fastsm.speech")
_shutdown_started = False
_shutdown_lock = threading.Lock()

_a2_speaker = None
_a2_imported = False


def _get_a2_speaker():
	"""Lazily import accessible_output2 and return its auto-picked speaker."""
	global _a2_speaker, _a2_imported
	if _a2_imported:
		return _a2_speaker
	_a2_imported = True
	try:
		from accessible_output2 import outputs
		_a2_speaker = outputs.auto.Auto()
	except Exception as error:
		_logger.warning("accessible_output2 unavailable: %s", error)
		_a2_speaker = None
	return _a2_speaker


def _setup_orca_worker():
	"""Spin up a Linux-only background worker that fires PresentMessage calls
	at Orca as NO_REPLY_EXPECTED. Returns a submit(text, interrupt) callable
	or None if Orca can't be reached.
	"""
	if not sys.platform.startswith('linux'):
		return None
	try:
		from jeepney import DBusAddress, new_method_call
		from jeepney.io.blocking import open_dbus_connection
		from jeepney.low_level import MessageFlag
	except ImportError:
		_logger.warning("jeepney not installed; no Linux speech backend available.")
		return None
	try:
		conn = open_dbus_connection(bus='SESSION')
	except Exception as error:
		_logger.warning("Could not open D-Bus session bus: %s", error)
		return None
	addr = DBusAddress('/org/gnome/Orca/Service',
	                   bus_name='org.gnome.Orca.Service',
	                   interface='org.gnome.Orca.Service')
	try:
		probe = new_method_call(addr, 'GetVersion')
		conn.send_and_get_reply(probe, timeout=1.0)
	except Exception as error:
		_logger.warning("Orca D-Bus service not reachable: %s", error)
		try: conn.close()
		except Exception: pass
		return None

	q = queue.Queue()
	connection = [conn]

	def _reconnect():
		try: connection[0].close()
		except Exception: pass
		try:
			connection[0] = open_dbus_connection(bus='SESSION')
			return True
		except Exception:
			return False

	def worker():
		while True:
			text = q.get()
			if text is None:
				return
			msg = new_method_call(addr, 'PresentMessage', 's', (text,))
			msg.header.flags |= MessageFlag.no_reply_expected
			try:
				connection[0].send(msg)
			except Exception:
				if _reconnect():
					try: connection[0].send(msg)
					except Exception: pass

	threading.Thread(target=worker, daemon=True, name='orca-speak').start()

	def submit(text, interrupt):
		if interrupt:
			try:
				while True:
					q.get_nowait()
			except queue.Empty:
				pass
		q.put(text)

	return submit


_orca_submit = _setup_orca_worker()


def _shutdown_active():
	with _shutdown_lock:
		return _shutdown_started


def _start_shutdown():
	global _shutdown_started
	with _shutdown_lock:
		if _shutdown_started:
			return False
		_shutdown_started = True
		return True


def _do_speak(text, interrupt):
	if _shutdown_active():
		return
	if _orca_submit is not None:
		try:
			_orca_submit(text, interrupt)
			return
		except Exception as error:
			_logger.warning("Orca submit failed: %s", error)
	speaker = _get_a2_speaker()
	if speaker is None:
		return
	try:
		speaker.speak(text, interrupt=interrupt)
	except Exception as error:
		_logger.warning("Speech output failed: %s", error)
		return
	try:
		speaker.braille(text)
	except Exception:
		pass


def speak(text, interrupt=False):
	if _shutdown_active():
		return
	if sys.platform == 'darwin' and threading.current_thread().ident != _main_thread_id:
		try:
			import wx
			wx.CallAfter(_do_speak, text, interrupt)
			return
		except Exception:
			pass
	_do_speak(text, interrupt)


def speak_async(text, interrupt=False):
	"""Best-effort speech for non-critical paths that must never block callers."""
	if _shutdown_active():
		return
	try:
		threading.Thread(target=speak, args=(text, interrupt), daemon=True).start()
	except Exception as error:
		_logger.warning("Async speech dispatch failed: %s", error)


def speak_before_shutdown(text, interrupt=False, timeout=0.5):
	"""Speak one shutdown announcement before suppressing later speech.

	The announcement gets a short grace window; shutdown continues even if a
	native backend blocks.
	"""
	if not _start_shutdown():
		return
	def _go():
		if _orca_submit is not None:
			try:
				_orca_submit(text, interrupt)
				return
			except Exception:
				pass
		speaker = _get_a2_speaker()
		if speaker is None:
			return
		try:
			speaker.speak(text, interrupt=interrupt)
		except Exception:
			pass
	try:
		thread = threading.Thread(target=_go, daemon=True)
		thread.start()
		thread.join(timeout)
	except Exception as error:
		_logger.warning("Shutdown speech dispatch failed: %s", error)
