"""AT-SPI based global hotkeys for Linux Wayland sessions.

This backend avoids wx.RegisterHotKey limitations on Wayland and dispatches
actions on the wx main thread for GUI safety.
"""

import threading

import wx

try:
	import pyatspi
except Exception:  # pragma: no cover - runtime availability check
	pyatspi = None


class AtspiWaylandKeyboardHandler:
	_MOD_ORDER = ("control", "win", "alt", "shift")
	_MOD_NAMES = {"control", "alt", "shift", "win"}
	_EVENT_ALIASES = {
		"page_up": "pageup",
		"prior": "pageup",
		"page_down": "pagedown",
		"next": "pagedown",
		"kp_enter": "return",
		"enter": "return",
		"kp_delete": "delete",
		"bracketleft": "[",
		"bracketright": "]",
		"slash": "/",
		"semicolon": ";",
		"apostrophe": "'",
	}
	_KEY_ALIASES = {
		"pageup": {"pageup", "page_up", "prior"},
		"pagedown": {"pagedown", "page_down", "next"},
		"return": {"return", "enter", "kp_enter"},
		"delete": {"delete", "kp_delete"},
		"[": {"[", "bracketleft"},
		"]": {"]", "bracketright"},
		"/": {"/", "slash"},
		";": {";", "semicolon"},
		"'": {"'", "apostrophe"},
	}

	def __init__(self):
		if pyatspi is None:
			raise RuntimeError("pyatspi is not available")

		self._bindings = {}
		self._lock = threading.RLock()
		self._listener_started = False
		self._listener_thread = None

		self._bit_control = 1 << int(pyatspi.MODIFIER_CONTROL)
		self._bit_alt = 1 << int(pyatspi.MODIFIER_ALT)
		self._bit_shift = 1 << int(pyatspi.MODIFIER_SHIFT)
		self._bit_win = 0
		for name in ("MODIFIER_META", "MODIFIER_META2", "MODIFIER_META3", "MODIFIER_SUPER"):
			if hasattr(pyatspi, name):
				self._bit_win |= 1 << int(getattr(pyatspi, name))

		self._start_listener()

	def _start_listener(self):
		if self._listener_started:
			return
		pyatspi.Registry.registerKeystrokeListener(
			self._on_keystroke,
			kind=(pyatspi.KEY_PRESSED_EVENT,),
			mask=pyatspi.allModifiers(),
		)
		self._listener_thread = threading.Thread(
			target=self._run_registry,
			name="FastSMAtspiHotkeys",
			daemon=True,
		)
		self._listener_thread.start()
		self._listener_started = True

	def _run_registry(self):
		try:
			pyatspi.Registry.start()
		except Exception:
			pass

	def _normalize_key_token(self, key):
		key = key.strip().lower()
		return self._EVENT_ALIASES.get(key, key)

	def _canonicalize(self, key):
		parts = [p.strip().lower() for p in str(key).split("+") if p.strip()]
		if not parts:
			raise ValueError("Empty key string")
		key_token = self._normalize_key_token(parts[-1])
		mods = []
		for mod in parts[:-1]:
			if mod not in self._MOD_NAMES:
				raise ValueError(f"Unknown modifier {mod}")
			if mod not in mods:
				mods.append(mod)
		ordered_mods = [m for m in self._MOD_ORDER if m in mods]
		return "+".join(ordered_mods + [key_token]), set(ordered_mods), key_token

	def _aliases_for_key(self, key_token):
		if key_token in self._KEY_ALIASES:
			return set(self._KEY_ALIASES[key_token])
		return {key_token}

	def register_key(self, key, function):
		if not callable(function):
			raise TypeError("Must provide a callable to be invoked upon keypress")
		canonical, mods, key_token = self._canonicalize(key)
		aliases = self._aliases_for_key(key_token)
		with self._lock:
			if canonical in self._bindings:
				raise ValueError(f"Key {canonical} is already registered")
			self._bindings[canonical] = {
				"mods": mods,
				"aliases": aliases,
				"function": function,
			}
		return True

	def unregister_key(self, key, function):
		canonical, _mods, _key_token = self._canonicalize(key)
		with self._lock:
			entry = self._bindings.get(canonical)
			if entry is None:
				raise ValueError(f"Key {canonical} not currently registered")
			if entry["function"] != function:
				raise ValueError(f"Key {canonical} is not registered to that function")
			del self._bindings[canonical]
		return True

	def _event_mods(self, event):
		modifiers = int(getattr(event, "modifiers", 0))
		mods = set()
		if modifiers & self._bit_control:
			mods.add("control")
		if modifiers & self._bit_alt:
			mods.add("alt")
		if modifiers & self._bit_shift:
			mods.add("shift")
		if self._bit_win and modifiers & self._bit_win:
			mods.add("win")
		return mods

	def _event_key_candidates(self, event):
		candidates = set()
		name = str(getattr(event, "event_string", "")).strip().lower()
		if name:
			candidates.add(name)
			candidates.add(self._EVENT_ALIASES.get(name, name))
		try:
			key_id = int(getattr(event, "id", -1))
		except Exception:
			key_id = -1
		if 32 <= key_id <= 126:
			candidates.add(chr(key_id).lower())
		if getattr(event, "is_text", False) and key_id >= 0:
			try:
				candidates.add(chr(key_id).lower())
			except Exception:
				pass
		return candidates

	def _on_keystroke(self, event):
		key_candidates = self._event_key_candidates(event)
		if not key_candidates:
			return False
		event_mods = self._event_mods(event)
		with self._lock:
			bindings = list(self._bindings.values())
		for binding in bindings:
			if event_mods != binding["mods"]:
				continue
			if binding["aliases"].isdisjoint(key_candidates):
				continue
			if wx.GetApp() is not None:
				wx.CallAfter(binding["function"])
			else:
				binding["function"]()
			return True
		return False
