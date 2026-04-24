"""Global shortcuts for Linux via /dev/input/event* (pure Python evdev).

Drop-in substitute for keyboard_handler.wx_handler.WXKeyboardHandler. Reads raw
keyboard events from the kernel so it works on Wayland without needing Orca's
privileged AT slot, without Flatpak packaging, and without a portal approval
dialog. The user must be in the `input` group to read /dev/input/event*.

Layout note: evdev gives us hardware keycodes (QWERTY-position, not the symbol
the layout maps them to), so FastSM's ASCII key names match assuming a
Latin/QWERTY layout. This is the same tradeoff `keyboard` and `python-evdev`
have — on Dvorak/AZERTY a "t" shortcut fires on the physical T-key position,
not wherever the layout puts "t".
"""

import glob
import logging
import os
import re
import struct
import sys
import threading

import wx


logger = logging.getLogger('fastsm.linux_shortcuts')


# ---- Modifier masks (our own bits, chosen to fit in a small int) ----

_MOD_SHIFT = 1 << 0
_MOD_CTRL  = 1 << 1
_MOD_ALT   = 1 << 2
_MOD_SUPER = 1 << 3


# ---- Linux input event protocol ----

# struct input_event {
#   struct timeval time;   // on 64-bit: long sec, long usec => 16 bytes
#   __u16 type;
#   __u16 code;
#   __s32 value;
# };  // 24 bytes on 64-bit

_EVENT_FMT = 'llHHi'
_EVENT_SIZE = struct.calcsize(_EVENT_FMT)

_EV_KEY  = 0x01
_EV_REP_BIT = 0x100000  # bit in /proc/bus/input/devices EV= to indicate real keyboard


# ---- Linux keycode → FastSM key-name tables ----

_MODIFIER_KEYCODES = {
	29: _MOD_CTRL,  97: _MOD_CTRL,       # LEFTCTRL, RIGHTCTRL
	42: _MOD_SHIFT, 54: _MOD_SHIFT,      # LEFTSHIFT, RIGHTSHIFT
	56: _MOD_ALT,  100: _MOD_ALT,        # LEFTALT, RIGHTALT
	125: _MOD_SUPER, 126: _MOD_SUPER,    # LEFTMETA, RIGHTMETA
}

_KEYCODE_TO_NAME = {
	# letters (row-scan keycodes from input-event-codes.h)
	30:'a', 48:'b', 46:'c', 32:'d', 18:'e', 33:'f', 34:'g', 35:'h',
	23:'i', 36:'j', 37:'k', 38:'l', 50:'m', 49:'n', 24:'o', 25:'p',
	16:'q', 19:'r', 31:'s', 20:'t', 22:'u', 47:'v', 17:'w', 45:'x',
	21:'y', 44:'z',
	# digit row
	2:'1', 3:'2', 4:'3', 5:'4', 6:'5', 7:'6', 8:'7', 9:'8', 10:'9', 11:'0',
	# punctuation
	12:'-', 13:'=', 26:'[', 27:']', 43:'\\',
	39:';', 40:"'", 41:'`',
	51:',', 52:'.', 53:'/',
	# whitespace / control
	28:'return', 57:'space', 1:'escape', 14:'backspace', 15:'tab',
	# navigation
	103:'up', 108:'down', 105:'left', 106:'right',
	102:'home', 107:'end', 104:'pageup', 109:'pagedown',
	110:'insert', 111:'delete',
	# function keys
	**{59+i: f'f{i+1}' for i in range(10)}, 87:'f11', 88:'f12',
}

_NAME_TO_KEYCODE = {name: code for code, name in _KEYCODE_TO_NAME.items()}
# Aliases to match the default keymap naming.
_NAME_TO_KEYCODE['enter'] = 28
_NAME_TO_KEYCODE['esc'] = 1


_MOD_NAMES = {
	'ctrl': _MOD_CTRL, 'control': _MOD_CTRL,
	'shift': _MOD_SHIFT,
	'alt': _MOD_ALT,
	'win': _MOD_SUPER, 'super': _MOD_SUPER, 'meta': _MOD_SUPER,
}


def _parse_spec(spec):
	"""'control+win+shift+t' → (mod_mask, keycode) or raises ValueError."""
	parts = [p.strip().lower() for p in spec.split('+') if p.strip()]
	mods = 0
	key_name = None
	for p in parts:
		if p in _MOD_NAMES:
			mods |= _MOD_NAMES[p]
		else:
			key_name = p
	if key_name is None:
		raise ValueError(f"no key in shortcut {spec!r}")
	code = _NAME_TO_KEYCODE.get(key_name)
	if code is None:
		raise ValueError(f"unknown key {key_name!r} in shortcut {spec!r}")
	return mods, code


def _find_keyboard_devices():
	"""Return /dev/input/eventN paths for real keyboards.

	Filters /proc/bus/input/devices by EV_REP capability — button-style devices
	(Power Button, headphone jack) appear with `kbd` handler but no autorepeat
	bit, so this keeps us from reading from them."""
	try:
		with open('/proc/bus/input/devices') as f:
			data = f.read()
	except OSError:
		return []
	paths = []
	for block in data.split('\n\n'):
		if 'kbd' not in block:
			continue
		m = re.search(r'EV=([0-9a-f]+)', block)
		if not m or (int(m.group(1), 16) & _EV_REP_BIT) == 0:
			continue
		m = re.search(r'event(\d+)', block)
		if m:
			paths.append(f'/dev/input/event{m.group(1)}')
	return paths


class LinuxGlobalShortcuts:
	"""WXKeyboardHandler-shaped handler backed by /dev/input/event* readers."""

	def __init__(self, parent):
		self.parent = parent
		self._bindings = {}  # (mod_mask, keycode) -> callback
		self._modifier_state = 0
		self._stop = threading.Event()
		self._readers = []
		self._start_readers()

	# ---- Public API (matches WXKeyboardHandler) ----

	def register_key(self, key, function):
		mods, code = _parse_spec(key)
		self._bindings[(mods, code)] = function

	def unregister_key(self, key, function):
		try:
			mods, code = _parse_spec(key)
		except ValueError:
			return
		self._bindings.pop((mods, code), None)

	# ---- Internals ----

	def _start_readers(self):
		devices = _find_keyboard_devices()
		if not devices:
			logger.warning("No keyboard devices found under /dev/input/ — "
			               "global shortcuts disabled")
			return
		opened = 0
		for path in devices:
			try:
				# O_NONBLOCK so a reader thread shutdown isn't stuck in read()
				fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
			except PermissionError:
				logger.warning("No read access to %s (add user to 'input' group, "
				               "then log out/in)", path)
				continue
			except OSError as e:
				logger.warning("Could not open %s: %s", path, e)
				continue
			t = threading.Thread(target=self._reader, args=(fd, path),
			                     daemon=True, name=f'evdev-{os.path.basename(path)}')
			t.start()
			self._readers.append((fd, t))
			opened += 1
		logger.info("Reading keys from %d keyboard device(s)", opened)

	def _reader(self, fd, path):
		"""Read events from one device. Each event is a 24-byte struct."""
		buf = b''
		while not self._stop.is_set():
			try:
				data = os.read(fd, _EVENT_SIZE * 64)
			except BlockingIOError:
				# No data available; wait a moment and retry.
				self._stop.wait(0.02)
				continue
			except OSError:
				break
			if not data:
				break
			buf += data
			while len(buf) >= _EVENT_SIZE:
				chunk, buf = buf[:_EVENT_SIZE], buf[_EVENT_SIZE:]
				_sec, _usec, etype, code, value = struct.unpack(_EVENT_FMT, chunk)
				if etype != _EV_KEY:
					continue
				self._on_key(code, value)
		try:
			os.close(fd)
		except OSError:
			pass

	def _on_key(self, keycode, value):
		# value: 0 = release, 1 = press, 2 = autorepeat
		mod_bit = _MODIFIER_KEYCODES.get(keycode)
		if mod_bit is not None:
			if value == 0:
				self._modifier_state &= ~mod_bit
			else:
				self._modifier_state |= mod_bit
			return
		if value == 0:
			return  # only fire on press/autorepeat
		callback = self._bindings.get((self._modifier_state, keycode))
		if callback is not None:
			wx.CallAfter(callback)

	def shutdown(self):
		self._stop.set()
