"""Speech output.

Linux: prefer Orca via its D-Bus service (org.gnome.Orca.Service.PresentMessage),
fall back to prism's best available backend (usually Speech Dispatcher). Prism's
own Orca backend reports BACKEND_NOT_AVAILABLE against Orca 50.x, so we talk to
the service directly.

Speech is dispatched on a background worker thread so callers never block on
D-Bus. Messages are sent NO_REPLY_EXPECTED so Orca never has to round-trip.

Windows/macOS: use prism's best available backend (SAPI / OneCore / JAWS / NVDA
/ VoiceOver / AV Speech) synchronously on the calling thread (or main thread on
macOS via wx.CallAfter).
"""

import sys
import threading
import queue

import prism


_main_thread_id = threading.main_thread().ident
_context = prism.Context()


def _setup_orca_worker():
	"""On Linux, spin up a background thread that fires D-Bus PresentMessage
	calls at Orca as NO_REPLY_EXPECTED. Returns a (submit, is_alive) pair or
	(None, None) if Orca can't be reached. `submit(text, interrupt)` queues a
	message; `interrupt=True` drops any pending messages first so speech
	replaces rather than queues."""
	if not sys.platform.startswith('linux'):
		return None, None
	try:
		from jeepney import DBusAddress, new_method_call
		from jeepney.io.blocking import open_dbus_connection
		from jeepney.low_level import MessageFlag
	except ImportError:
		return None, None
	try:
		conn = open_dbus_connection(bus='SESSION')
	except Exception:
		return None, None
	addr = DBusAddress('/org/gnome/Orca/Service',
	                   bus_name='org.gnome.Orca.Service',
	                   interface='org.gnome.Orca.Service')
	# Probe: if Orca isn't actually running, bail before committing to the worker.
	try:
		probe = new_method_call(addr, 'GetVersion')
		conn.send_and_get_reply(probe, timeout=1.0)
	except Exception:
		try: conn.close()
		except Exception: pass
		return None, None

	q = queue.Queue()
	connection = [conn]  # mutable cell so the worker can reconnect

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
			# Fire-and-forget: tell the bus daemon not to route a reply back.
			msg.header.flags |= MessageFlag.no_reply_expected
			try:
				connection[0].send(msg)
			except Exception:
				# Connection is probably dead — try once to reconnect and retry.
				if _reconnect():
					try: connection[0].send(msg)
					except Exception: pass

	t = threading.Thread(target=worker, daemon=True, name='orca-speak')
	t.start()

	def submit(text, interrupt):
		if interrupt:
			# Drop queued messages so the new utterance isn't at the back of the line.
			try:
				while True:
					q.get_nowait()
			except queue.Empty:
				pass
		q.put(text)

	return submit, t


_orca_submit, _orca_thread = _setup_orca_worker()
_prism_backend = None


def _get_prism_backend():
	global _prism_backend
	if _prism_backend is None:
		_prism_backend = _context.create_best()
	return _prism_backend


def _do_speak(text, interrupt):
	"""Internal function that actually speaks."""
	if _orca_submit is not None:
		try:
			_orca_submit(text, interrupt)
			return
		except Exception:
			pass  # fall through to prism
	backend = _get_prism_backend()
	backend.speak(text, interrupt)
	try:
		backend.braille(text)
	except Exception:
		pass


def speak(text, interrupt=False):
	"""Speak text, ensuring thread safety on Mac."""
	# On Mac, speech backends (AV Speech) must be called from the main thread.
	if sys.platform == 'darwin' and threading.current_thread().ident != _main_thread_id:
		try:
			import wx
			wx.CallAfter(_do_speak, text, interrupt)
		except Exception:
			_do_speak(text, interrupt)
	else:
		_do_speak(text, interrupt)


# Warm up prism at import time on non-Linux platforms so the first speak() call
# doesn't pay the init cost. Linux skips this so Orca is the preferred path.
if not sys.platform.startswith('linux'):
	_get_prism_backend()
