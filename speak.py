"""Speech output using accessible_output2."""

import sys
import threading
import contextlib
import io
import queue
import time

from accessible_output2 import outputs

_main_thread_id = threading.main_thread().ident
_orca_lock = threading.RLock()
_orca_proxy = None
_orca_glib = None
_orca_gio = None
_orca_checked = False
_orca_detected = False
_speaker = None
_speech_queue = queue.Queue(maxsize=128)
_speech_worker = None
_speech_worker_lock = threading.RLock()
_last_enqueued_text = ""
_last_enqueued_ts = 0.0
_last_spoken_text = ""
_last_spoken_ts = 0.0
_DEDUP_WINDOW = 0.25


def _reset_orca_proxy():
	global _orca_proxy, _orca_checked
	_orca_proxy = None
	_orca_checked = False


def _get_speaker():
	"""Lazy-init fallback speech backend for non-Orca output."""
	global _speaker
	if _speaker is None:
		with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
			_speaker = outputs.auto.Auto()
	return _speaker


def _queue_clear():
	"""Drop any queued speech items."""
	try:
		while True:
			_speech_queue.get_nowait()
	except queue.Empty:
		pass


def _should_dedup(text, last_text, last_ts):
	if text != last_text:
		return False
	return (time.monotonic() - last_ts) < _DEDUP_WINDOW


def _get_orca_proxy():
	"""Return Orca DBus proxy if Orca service is available."""
	global _orca_proxy, _orca_checked, _orca_glib, _orca_gio, _orca_detected
	if not sys.platform.startswith("linux"):
		return None
	with _orca_lock:
		if _orca_checked:
			return _orca_proxy
		_orca_checked = True
		try:
			import gi
			gi.require_version("Gio", "2.0")
			from gi.repository import Gio, GLib
			bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
			has_owner = bus.call_sync(
				"org.freedesktop.DBus",
				"/org/freedesktop/DBus",
				"org.freedesktop.DBus",
				"NameHasOwner",
				GLib.Variant("(s)", ("org.gnome.Orca.Service",)),
				GLib.VariantType("(b)"),
				Gio.DBusCallFlags.NONE,
				1000,
				None,
			).unpack()[0]
			if not has_owner:
				return None
			_orca_detected = True
			_orca_proxy = Gio.DBusProxy.new_sync(
				bus,
				Gio.DBusProxyFlags.DO_NOT_AUTO_START,
				None,
				"org.gnome.Orca.Service",
				"/org/gnome/Orca/Service",
				"org.gnome.Orca.Service",
				None,
			)
			_orca_glib = GLib
			_orca_gio = Gio
		except Exception:
			_orca_proxy = None
		return _orca_proxy


def _speak_via_orca(text):
	"""Try speaking via Orca DBus service; return True on success."""
	proxy = _get_orca_proxy()
	if proxy is None:
		return False
	try:
		result = proxy.call_sync(
			"PresentMessage",
			_orca_glib.Variant("(s)", (text,)),
			_orca_gio.DBusCallFlags.NO_AUTO_START,
			1000,
			None,
		)
		if result is None:
			return True
		payload = result.unpack()
		return bool(payload[0]) if payload else True
	except Exception:
		_reset_orca_proxy()
		return False

def _do_speak(text, interrupt):
	"""Internal function that actually speaks."""
	global _last_spoken_text, _last_spoken_ts
	text = str(text).strip()
	if not text:
		return
	if _should_dedup(text, _last_spoken_text, _last_spoken_ts):
		return
	_last_spoken_text = text
	_last_spoken_ts = time.monotonic()
	proxy = _get_orca_proxy()
	# If Orca is available, use Orca only (no duplicate fallback voice).
	if proxy is not None:
		_speak_via_orca(text)
		return
	# If Orca was detected earlier in this session but is temporarily unavailable,
	# avoid falling back to a second speech engine which causes duplicate output.
	if _orca_detected:
		return
	speaker = _get_speaker()
	speaker.speak(text, interrupt)
	speaker.braille(text)


def _speech_worker_loop():
	"""Serialize Linux speech output to avoid thread contention and bursts."""
	while True:
		try:
			text, interrupt = _speech_queue.get()
		except Exception:
			return
		if text is None:
			return
		try:
			_do_speak(text, interrupt)
		except Exception:
			# Never let speech failures kill the worker loop.
			pass


def _ensure_speech_worker():
	global _speech_worker
	with _speech_worker_lock:
		if _speech_worker is not None and _speech_worker.is_alive():
			return
		_speech_worker = threading.Thread(
			target=_speech_worker_loop,
			name="FastSMSpeechWorker",
			daemon=True,
		)
		_speech_worker.start()


def _enqueue_speech(text, interrupt):
	global _last_enqueued_text, _last_enqueued_ts
	text = str(text).strip()
	if not text:
		return
	if _should_dedup(text, _last_enqueued_text, _last_enqueued_ts):
		return
	_last_enqueued_text = text
	_last_enqueued_ts = time.monotonic()
	if interrupt:
		_queue_clear()
	try:
		_speech_queue.put_nowait((text, interrupt))
	except queue.Full:
		try:
			_speech_queue.get_nowait()
		except queue.Empty:
			pass
		try:
			_speech_queue.put_nowait((text, interrupt))
		except queue.Full:
			pass


def speak(text, interrupt=False):
	"""Speak text, ensuring thread safety on Mac."""
	text = str(text)
	if not text.strip():
		return
	# On Linux, queue speech so rapid events don't hammer Orca/CPU.
	if sys.platform.startswith("linux"):
		_ensure_speech_worker()
		_enqueue_speech(text, interrupt)
		return
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
