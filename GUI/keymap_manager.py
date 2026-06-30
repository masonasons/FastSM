"""Keyboard manager dialog.

Lets the user create/edit/delete keymaps that override the read-only default
keymap. Saving a keymap writes only the bindings the user actually changed
(matching how _load_keymap_with_inheritance layers a custom keymap over the
default). Unbinding an action emits an `unbind:ActionName` line that the
loader respects.
"""

import os
import re

import wx

from application import get_app


# Human-readable labels for known actions. Anything not listed gets a label
# auto-derived from the action name (camelCase / snake_case split + title case).
ACTION_LABELS = {
	"close": "Quit",
	"ToggleWindow": "Toggle window visibility",
	"Post": "New post",
	"PostUrl": "Open URL of current post",
	"prev_tl": "Previous timeline",
	"next_tl": "Next timeline",
	"prev_item": "Previous item",
	"next_item": "Next item",
	"prev_item_jump": "Jump back (20 items)",
	"next_item_jump": "Jump forward (20 items)",
	"top_item": "Top of timeline",
	"bottom_item": "Bottom of timeline",
	"PrevAccount": "Previous account",
	"NextAccount": "Next account",
	"Reply": "Reply",
	"Edit": "Edit post",
	"BoostToggle": "Boost / Unboost",
	"LikeToggle": "Like / Unlike",
	"BookmarkToggle": "Bookmark / Unbookmark",
	"BlockToggle": "Block / Unblock user",
	"FollowToggle": "Follow / Unfollow",
	"MuteToggle": "Mute / Unmute user",
	"PinToggle": "Pin / Unpin post",
	"Quote": "Quote post",
	"Message": "Send direct message",
	"Conversation": "Load conversation",
	"View": "View post",
	"Followers": "List followers",
	"Following": "List following",
	"Volup": "Volume up",
	"Voldown": "Volume down",
	"Url": "Open URL from post",
	"SpeakUser": "Speak user",
	"SpeakReply": "Speak reference post",
	"Prev": "Load older posts",
	"LoadHere": "Load posts at cursor",
	"UserTimeline": "Open user timeline",
	"UserProfile": "Open user profile",
	"AddAlias": "Add alias for user",
	"UpdateProfile": "Update own profile",
	"CloseTimeline": "Close timeline",
	"refresh": "Refresh timeline",
	"PlayExternal": "Play media",
	"StopAudio": "Stop audio",
	"AudioPlayer": "Audio player",
	"Delete": "Delete post",
	"Options": "Global options",
	"AccountOptions": "Account options",
	"previous_from_user": "Previous post from same user",
	"next_from_user": "Next post from same user",
	"previous_in_thread": "Previous post in thread",
	"next_in_thread": "Next post in thread",
	"PrevMovementUnit": "Previous movement unit",
	"NextMovementUnit": "Next movement unit",
	"MoveByUnitUp": "Move up by movement unit",
	"MoveByUnitDown": "Move down by movement unit",
	"UndoNavigation": "Undo navigation (go back)",
	"Copy": "Copy post to clipboard",
	"AddToList": "Add user to list",
	"RemoveFromList": "Remove user from list",
	"Lists": "Open lists",
	"CustomTimelines": "Add custom timeline",
	"FilterTimeline": "Client filters",
	"Search": "Search posts",
	"UserSearch": "Search users",
	"Accounts": "Open accounts dialog",
	"speak_item": "Speak current item",
	"speak_account": "Speak current account",
	"Read": "Toggle autoread",
	"Mute": "Toggle timeline mute",
	"ContextMenu": "Open post context menu",
	"ViewImage": "View image attachment",
	"ViewInstance": "View instance info",
	"KeymapManager": "Open keyboard manager",
}


_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _humanize(action):
	"""Fallback label for actions missing from ACTION_LABELS."""
	pretty = action.replace("_", " ")
	pretty = _CAMEL_SPLIT_RE.sub(" ", pretty)
	return pretty[:1].upper() + pretty[1:] if pretty else action


def action_label(action):
	return ACTION_LABELS.get(action, _humanize(action))


def format_key(key):
	"""Render a keymap key string for display (control+shift+k -> Ctrl+Shift+K)."""
	if not key:
		return ""
	parts = []
	for chunk in key.split("+"):
		chunk = chunk.strip()
		if not chunk:
			continue
		low = chunk.lower()
		if low == "control":
			parts.append("Ctrl")
		elif low == "win":
			parts.append("Win")
		elif low == "alt":
			parts.append("Alt")
		elif low == "shift":
			parts.append("Shift")
		elif len(chunk) == 1:
			parts.append(chunk.upper())
		else:
			parts.append(chunk[:1].upper() + chunk[1:].lower())
	return "+".join(parts)


# --- key name validation ------------------------------------------------

# Canonical key tokens accepted by the keyboard_handler library. Imported lazily
# so unit tests can stub the library.
def _named_keys():
	try:
		from keyboard_handler import key_constants
	except Exception:
		return set()
	out = set()
	for name in key_constants.keys:
		out.add(name.lower())
	return out


_MODIFIER_TOKENS = {"control", "alt", "shift", "win", "ctrl", "windows", "cmd", "command"}


def validate_key_name(key):
	"""Return (canonical_token, None) if the base key name is valid, else (None, error_string)."""
	if key is None:
		return None, "Key field is empty."
	stripped = key.strip()
	if not stripped:
		return None, "Key field is empty."
	if "+" in stripped:
		return None, "Don't include modifiers in the key field — use the checkboxes."
	low = stripped.lower()
	if low in _MODIFIER_TOKENS:
		return None, f"'{stripped}' is a modifier, not a key. Pick a base key like 't', 'up', 'f5', 'delete'."
	if low in _named_keys():
		return low, None
	if len(stripped) == 1 and (stripped.isalnum() or stripped in "/;[]\\'=,-"):
		return low, None
	return None, (
		f"'{stripped}' isn't a recognised key. Use a single character (a, 1, /, ;) "
		"or a name like up, down, return, escape, delete, space, f1-f24."
	)


def build_binding(control, alt, shift, win, key):
	"""Compose a keymap string from individual modifier flags + a base key.

	Returns (binding_or_None, error_string_or_None).
	"""
	canonical, err = validate_key_name(key)
	if err:
		return None, err
	parts = []
	if control:
		parts.append("control")
	if alt:
		parts.append("alt")
	if shift:
		parts.append("shift")
	if win:
		parts.append("win")
	parts.append(canonical)
	return "+".join(parts), None


# --- keymap I/O ----------------------------------------------------------

def _user_keymaps_dir():
	d = os.path.join(get_app().confpath, "keymaps")
	os.makedirs(d, exist_ok=True)
	return d


def _bundled_keymap_path(name):
	return os.path.join("keymaps", f"{name}.keymap")


def _user_keymap_path(name):
	return os.path.join(_user_keymaps_dir(), f"{name}.keymap")


def _list_keymap_names_in(root):
	if not os.path.isdir(root):
		return set()
	out = set()
	for f in os.listdir(root):
		if f.endswith(".keymap") and not f.startswith("."):
			out.add(f[:-7])
	return out


def list_user_keymaps():
	"""Return sorted list of user-config keymap names (always editable)."""
	return sorted(n for n in _list_keymap_names_in(_user_keymaps_dir()) if n != "default")


def list_bundled_keymaps():
	"""Return sorted list of bundled (read-only) keymap names that are NOT shadowed by a user copy.

	Excludes 'default', which is special-cased everywhere.
	"""
	user = _list_keymap_names_in(_user_keymaps_dir())
	bundled = _list_keymap_names_in("keymaps")
	return sorted(n for n in bundled if n != "default" and n not in user)


def list_custom_keymaps():
	"""Back-compat helper — returns everything that's selectable (user + bundled)."""
	return sorted(set(list_user_keymaps()) | set(list_bundled_keymaps()))


def is_editable_keymap(name):
	"""True iff `name` is a user-config keymap (not default, not bundled)."""
	if not name or name == "default":
		return False
	return os.path.exists(_user_keymap_path(name))


def load_default_keymap():
	"""Return {action: key} for the default keymap (reversed from the file format)."""
	from GUI import main as _main  # avoid cycle at module load
	# Reuse main's loader so we follow the same search-path logic.
	parsed = _main.window._load_keymap_file("keymaps/default.keymap") if hasattr(_main.window, "_load_keymap_file") else {}
	if not parsed:
		# Fall back to direct parse if main.window isn't reachable yet.
		parsed = _parse_keymap_file("keymaps/default.keymap")[0]
	out = {}
	for key, action in parsed.items():
		out.setdefault(action, key)
	return out


def _parse_keymap_file(path):
	"""Returns ({key: action}, set_of_unbound_actions)."""
	keymap = {}
	unbinds = set()
	if not os.path.exists(path):
		return keymap, unbinds
	try:
		with open(path, "r", encoding="utf-8") as f:
			for line in f:
				line = line.strip()
				if not line or line.startswith("#"):
					continue
				if line.startswith("unbind:"):
					action = line[len("unbind:"):].strip()
					if action:
						unbinds.add(action)
					continue
				if "=" in line:
					k, _, a = line.partition("=")
					k, a = k.strip(), a.strip()
					if k and a:
						keymap[k] = a
	except OSError:
		pass
	return keymap, unbinds


def load_custom_keymap(name):
	"""Return ({action: key}, set_of_unbound_actions) for a named custom keymap."""
	for path in (_user_keymap_path(name), _bundled_keymap_path(name)):
		if os.path.exists(path):
			km, ub = _parse_keymap_file(path)
			out = {}
			for key, action in km.items():
				out.setdefault(action, key)
			return out, ub
	return {}, set()


def save_custom_keymap(name, action_to_key, unbinds):
	"""Write a custom keymap to the user's confpath. Bundled keymaps are not touched."""
	path = _user_keymap_path(name)
	lines = []
	for action, key in sorted(action_to_key.items()):
		if key:
			lines.append(f"{key}={action}")
	for action in sorted(unbinds):
		lines.append(f"unbind:{action}")
	with open(path, "w", encoding="utf-8") as f:
		f.write("\n".join(lines))
		if lines:
			f.write("\n")
	return path


def delete_custom_keymap(name):
	path = _user_keymap_path(name)
	if os.path.exists(path):
		os.remove(path)
		return True
	return False


# --- binding dialog ------------------------------------------------------

def _split_binding(binding):
	"""Decompose a keymap string into (control, alt, shift, win, key)."""
	control = alt = shift = win = False
	key = ""
	if not binding:
		return control, alt, shift, win, key
	for chunk in binding.split("+"):
		low = chunk.strip().lower()
		if low == "control":
			control = True
		elif low == "alt":
			alt = True
		elif low == "shift":
			shift = True
		elif low == "win":
			win = True
		elif low:
			key = low
	return control, alt, shift, win, key


class BindingDialog(wx.Dialog):
	"""Modal dialog for assigning a key combination to an action.

	The user toggles modifier checkboxes and types a base key name (single
	character or named key like 'up', 'delete', 'f5'). OK validates the binding
	before returning it; on invalid input a message dialog explains the issue
	and the BindingDialog stays open.
	"""

	def __init__(self, parent, action_label_str, current_binding=None):
		super().__init__(parent,
			title=f"Set binding for: {action_label_str}",
			style=wx.DEFAULT_DIALOG_STYLE)
		self._binding = None
		self._build_ui(action_label_str, current_binding)
		self.CenterOnParent()

	def _build_ui(self, action_label_str, current_binding):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		sizer.Add(
			wx.StaticText(panel, -1, f"Action: {action_label_str}"),
			0, wx.ALL, 10)

		sizer.Add(
			wx.StaticText(panel, -1, f"Current binding: {format_key(current_binding) or '(unbound)'}"),
			0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

		mods_box = wx.StaticBox(panel, -1, "Modifiers")
		mods_sizer = wx.StaticBoxSizer(mods_box, wx.HORIZONTAL)
		self.cb_control = wx.CheckBox(panel, -1, "&Control")
		self.cb_alt = wx.CheckBox(panel, -1, "&Alt")
		self.cb_shift = wx.CheckBox(panel, -1, "&Shift")
		self.cb_win = wx.CheckBox(panel, -1, "&Win")
		for cb in (self.cb_control, self.cb_alt, self.cb_shift, self.cb_win):
			mods_sizer.Add(cb, 0, wx.ALL, 5)
		sizer.Add(mods_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

		key_row = wx.BoxSizer(wx.HORIZONTAL)
		key_row.Add(
			wx.StaticText(panel, -1, "&Key (e.g. t, /, up, return, delete, f5):"),
			0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
		self.key_field = wx.TextCtrl(panel, -1, "", name="Key")
		key_row.Add(self.key_field, 1, wx.ALL | wx.EXPAND, 5)
		sizer.Add(key_row, 0, wx.EXPAND | wx.TOP, 10)

		# Prefill from the current binding so users can tweak instead of retyping.
		c, a, s, w, k = _split_binding(current_binding)
		self.cb_control.SetValue(c)
		self.cb_alt.SetValue(a)
		self.cb_shift.SetValue(s)
		self.cb_win.SetValue(w)
		self.key_field.SetValue(k)

		btn_row = wx.BoxSizer(wx.HORIZONTAL)
		btn_row.AddStretchSpacer(1)
		ok = wx.Button(panel, wx.ID_OK, "&OK")
		ok.SetDefault()
		ok.Bind(wx.EVT_BUTTON, self._on_ok)
		btn_row.Add(ok, 0, wx.ALL, 10)
		cancel = wx.Button(panel, wx.ID_CANCEL, "Cancel")
		btn_row.Add(cancel, 0, wx.ALL, 10)
		sizer.Add(btn_row, 0, wx.EXPAND)

		panel.SetSizer(sizer)
		sizer.Fit(self)

	def _on_ok(self, event):
		binding, err = build_binding(
			self.cb_control.GetValue(),
			self.cb_alt.GetValue(),
			self.cb_shift.GetValue(),
			self.cb_win.GetValue(),
			self.key_field.GetValue(),
		)
		if err:
			wx.MessageBox(err, "Invalid binding", wx.OK | wx.ICON_ERROR, self)
			self.key_field.SetFocus()
			return
		self._binding = binding
		self.EndModal(wx.ID_OK)

	def get_binding(self):
		return self._binding


# --- main dialog ---------------------------------------------------------

class KeymapManagerGui(wx.Dialog):
	def __init__(self, parent=None):
		super().__init__(parent, title="Keyboard Manager", size=(720, 560),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._dirty = False
		self._default_keymap = load_default_keymap()
		self._actions = sorted(self._default_keymap.keys(), key=lambda a: action_label(a).lower())
		# Include actions that exist in custom keymaps but not in default.
		self._custom_overrides = {}  # {action: key}
		self._custom_unbinds = set()
		self._current_keymap_name = ""  # "" means default (read-only)

		self._build_ui()
		self._populate_keymap_choice()
		self._refresh_list()

	def _build_ui(self):
		panel = wx.Panel(self)
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		# Keymap chooser row
		top = wx.BoxSizer(wx.HORIZONTAL)
		top.Add(wx.StaticText(panel, -1, "Active &keymap:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
		self.keymap_choice = wx.Choice(panel, -1, name="Keymap")
		self.keymap_choice.Bind(wx.EVT_CHOICE, self._on_keymap_changed)
		top.Add(self.keymap_choice, 1, wx.ALL | wx.EXPAND, 5)
		self.new_btn = wx.Button(panel, -1, "&New keymap...")
		self.new_btn.Bind(wx.EVT_BUTTON, self._on_new_keymap)
		top.Add(self.new_btn, 0, wx.ALL, 5)
		self.delete_btn = wx.Button(panel, -1, "&Delete keymap")
		self.delete_btn.Bind(wx.EVT_BUTTON, self._on_delete_keymap)
		top.Add(self.delete_btn, 0, wx.ALL, 5)
		main_sizer.Add(top, 0, wx.EXPAND | wx.TOP, 5)

		self.status_label = wx.StaticText(panel, -1, "")
		main_sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

		# Action list
		main_sizer.Add(wx.StaticText(panel, -1, "&Actions:"), 0, wx.LEFT, 10)
		self.list = wx.ListCtrl(panel, -1, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, name="Actions")
		self.list.InsertColumn(0, "Action", width=260)
		self.list.InsertColumn(1, "Current key", width=200)
		self.list.InsertColumn(2, "Source", width=140)
		self.list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_set_binding)
		main_sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, 10)

		# Action buttons
		cap = wx.BoxSizer(wx.HORIZONTAL)
		self.set_btn = wx.Button(panel, -1, "&Set binding...")
		self.set_btn.Bind(wx.EVT_BUTTON, self._on_set_binding)
		cap.Add(self.set_btn, 0, wx.ALL, 5)
		self.unbind_btn = wx.Button(panel, -1, "&Unbind")
		self.unbind_btn.Bind(wx.EVT_BUTTON, self._on_unbind)
		cap.Add(self.unbind_btn, 0, wx.ALL, 5)
		self.reset_btn = wx.Button(panel, -1, "&Reset to default")
		self.reset_btn.Bind(wx.EVT_BUTTON, self._on_reset_row)
		cap.Add(self.reset_btn, 0, wx.ALL, 5)
		main_sizer.Add(cap, 0, wx.LEFT, 5)

		# Bottom buttons
		bottom = wx.BoxSizer(wx.HORIZONTAL)
		bottom.AddStretchSpacer(1)
		self.save_btn = wx.Button(panel, -1, "Sa&ve")
		self.save_btn.Bind(wx.EVT_BUTTON, self._on_save)
		bottom.Add(self.save_btn, 0, wx.ALL, 10)
		self.close_btn = wx.Button(panel, wx.ID_CANCEL, "&Close")
		self.close_btn.Bind(wx.EVT_BUTTON, self._on_close)
		bottom.Add(self.close_btn, 0, wx.ALL, 10)
		main_sizer.Add(bottom, 0, wx.EXPAND)

		panel.SetSizer(main_sizer)
		self.Bind(wx.EVT_CLOSE, self._on_close)

	# --- keymap chooser handling ---

	def _populate_keymap_choice(self):
		"""Build the dropdown. Entries store the raw keymap name in self._choice_names,
		parallel to the displayed labels (which include built-in markers).
		"""
		self.keymap_choice.Clear()
		self._choice_names = []
		self.keymap_choice.Append("default (built-in)")
		self._choice_names.append("default")
		for name in list_bundled_keymaps():
			self.keymap_choice.Append(f"{name} (built-in)")
			self._choice_names.append(name)
		for name in list_user_keymaps():
			self.keymap_choice.Append(name)
			self._choice_names.append(name)
		current = getattr(get_app().prefs, "keymap", "default") or "default"
		if current in self._choice_names:
			self.keymap_choice.SetSelection(self._choice_names.index(current))
			self._select_keymap(current)
		else:
			self.keymap_choice.SetSelection(0)
			self._select_keymap("default")

	def _select_keymap(self, name, activate=False):
		"""Switch the keymap displayed in the editor.

		When activate=True, also set this as the running app's active keymap and
		re-register hotkeys. The first call (during dialog construction) passes
		activate=False so we don't side-effect on open.
		"""
		self._current_keymap_name = name
		if name and name != "default":
			self._custom_overrides, self._custom_unbinds = load_custom_keymap(name)
		else:
			self._custom_overrides, self._custom_unbinds = {}, set()
		extra = [a for a in self._custom_overrides if a not in self._default_keymap]
		if extra:
			self._actions = sorted(
				set(self._default_keymap) | set(self._custom_overrides),
				key=lambda a: action_label(a).lower(),
			)
		else:
			self._actions = sorted(self._default_keymap.keys(), key=lambda a: action_label(a).lower())
		self._dirty = False
		self._update_edit_enable()
		self._refresh_list()
		self._update_status()
		if activate:
			prefs = get_app().prefs
			if getattr(prefs, "keymap", "default") != (name or "default"):
				prefs.keymap = name or "default"
				self._reapply_keymap_to_running_app()

	def _on_keymap_changed(self, event):
		idx = self.keymap_choice.GetSelection()
		target_name = self._choice_names[idx] if 0 <= idx < len(self._choice_names) else "default"
		prev = self._current_keymap_name

		def _switch():
			# Activate-on-pick: switching keymaps in the dropdown makes that
			# keymap the running app's active keymap.
			self._select_keymap(target_name, activate=True)

		if self._dirty:
			confirmed = [False]
			def _accept():
				confirmed[0] = True
				_switch()
			self._maybe_warn_unsaved(_accept)
			if not confirmed[0] and prev in self._choice_names:
				self.keymap_choice.SetSelection(self._choice_names.index(prev))
		else:
			_switch()

	def _maybe_warn_unsaved(self, then):
		if not self._dirty:
			then()
			return
		dlg = wx.MessageDialog(self,
			"You have unsaved changes. Discard them?",
			"Unsaved changes",
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
		try:
			if dlg.ShowModal() == wx.ID_YES:
				then()
		finally:
			dlg.Destroy()

	def _update_edit_enable(self):
		editable = is_editable_keymap(self._current_keymap_name)
		for btn in (self.set_btn, self.unbind_btn, self.reset_btn, self.save_btn):
			btn.Enable(editable)
		self.delete_btn.Enable(editable)

	def _update_status(self):
		name = self._current_keymap_name
		if not name or name == "default":
			self.status_label.SetLabel(
				"This keymap is built-in and read-only. Create a new keymap to make changes."
			)
		elif not is_editable_keymap(name):
			self.status_label.SetLabel(
				f"'{name}' is a built-in keymap and is read-only."
			)
		else:
			suffix = " (unsaved)" if self._dirty else ""
			self.status_label.SetLabel(
				f"Editing '{name}'{suffix}. Only modified bindings are saved. "
				f"File: {_user_keymap_path(name)}"
			)

	# --- new / delete ---

	def _on_new_keymap(self, event):
		dlg = wx.TextEntryDialog(self,
			"Name for new keymap (no spaces, letters/digits/dash/underscore):",
			"New keymap")
		try:
			if dlg.ShowModal() != wx.ID_OK:
				return
			name = dlg.GetValue().strip()
		finally:
			dlg.Destroy()
		if not name:
			return
		if not re.match(r"^[A-Za-z0-9_\-]+$", name):
			wx.MessageBox("Invalid name. Use letters, digits, dashes, underscores only.",
				"Invalid name", wx.OK | wx.ICON_ERROR, self)
			return
		if name.lower() == "default":
			wx.MessageBox("'default' is reserved.", "Invalid name", wx.OK | wx.ICON_ERROR, self)
			return
		if name in list_user_keymaps() or name in list_bundled_keymaps():
			wx.MessageBox(f"A keymap named '{name}' already exists.",
				"Already exists", wx.OK | wx.ICON_ERROR, self)
			return
		# Create an empty user-config keymap so it shows up in the chooser.
		save_custom_keymap(name, {}, set())
		self._populate_keymap_choice()
		if name in self._choice_names:
			self.keymap_choice.SetSelection(self._choice_names.index(name))
		self._select_keymap(name, activate=True)

	def _on_delete_keymap(self, event):
		name = self._current_keymap_name
		if not is_editable_keymap(name):
			return
		dlg = wx.MessageDialog(self,
			f"Delete keymap '{name}'? This cannot be undone.",
			"Delete keymap",
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
		try:
			if dlg.ShowModal() != wx.ID_YES:
				return
		finally:
			dlg.Destroy()
		delete_custom_keymap(name)
		self._populate_keymap_choice()
		self.keymap_choice.SetSelection(0)
		# Falls back to default; activate=True flips prefs + reapplies if needed.
		self._select_keymap("default", activate=True)

	# --- list rendering ---

	def _effective_binding(self, action):
		"""Return (key_or_None, source) where source is 'default', 'custom', or 'unbound'."""
		if action in self._custom_overrides:
			return self._custom_overrides[action], "custom"
		if action in self._custom_unbinds:
			return None, "unbound"
		default_key = self._default_keymap.get(action)
		if default_key:
			return default_key, "default"
		return None, "unbound"

	def _refresh_list(self):
		self.list.DeleteAllItems()
		for i, action in enumerate(self._actions):
			self.list.InsertItem(i, action_label(action))
			key, source = self._effective_binding(action)
			self.list.SetItem(i, 1, format_key(key) if key else "(unbound)")
			self.list.SetItem(i, 2, source)
		if self._actions:
			self.list.Select(0)

	def _selected_action(self):
		idx = self.list.GetFirstSelected()
		if idx < 0:
			return None
		return self._actions[idx]

	# --- edit operations ---

	def _on_set_binding(self, event):
		if not is_editable_keymap(self._current_keymap_name):
			return
		action = self._selected_action()
		if action is None:
			wx.MessageBox("Select an action in the list first.",
				"No action selected", wx.OK | wx.ICON_INFORMATION, self)
			return
		current_key, _ = self._effective_binding(action)
		dlg = BindingDialog(self, action_label(action), current_key)
		try:
			if dlg.ShowModal() != wx.ID_OK:
				return
			key = dlg.get_binding()
		finally:
			dlg.Destroy()
		if not key:
			return
		# Detect collisions with other actions in this keymap's effective view.
		for other in self._actions:
			if other == action:
				continue
			other_key, _ = self._effective_binding(other)
			if other_key == key:
				dlg = wx.MessageDialog(self,
					f"'{format_key(key)}' is already bound to '{action_label(other)}'. "
					"Reassign it to this action?",
					"Key in use",
					wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
				try:
					if dlg.ShowModal() != wx.ID_YES:
						return
				finally:
					dlg.Destroy()
				# Reassigning: drop the old action's binding. If the override was
				# only in this custom keymap, removing it is enough; otherwise
				# write an explicit unbind so the default's binding doesn't leak
				# back in.
				if other in self._custom_overrides:
					del self._custom_overrides[other]
				else:
					self._custom_unbinds.add(other)
				break
		self._custom_overrides[action] = key
		self._custom_unbinds.discard(action)
		self._mark_dirty_and_refresh()

	def _on_unbind(self, event):
		if not is_editable_keymap(self._current_keymap_name):
			return
		action = self._selected_action()
		if action is None:
			return
		self._custom_overrides.pop(action, None)
		if action in self._default_keymap:
			self._custom_unbinds.add(action)
		self._mark_dirty_and_refresh()

	def _on_reset_row(self, event):
		if not is_editable_keymap(self._current_keymap_name):
			return
		action = self._selected_action()
		if action is None:
			return
		removed = False
		if action in self._custom_overrides:
			del self._custom_overrides[action]
			removed = True
		if action in self._custom_unbinds:
			self._custom_unbinds.discard(action)
			removed = True
		if removed:
			self._mark_dirty_and_refresh()

	def _mark_dirty_and_refresh(self):
		self._dirty = True
		selected = self._selected_action()
		self._refresh_list()
		if selected is not None and selected in self._actions:
			i = self._actions.index(selected)
			self.list.Select(i)
			self.list.EnsureVisible(i)
		self._update_status()

	# --- save / close ---

	def _on_save(self, event):
		name = self._current_keymap_name
		if not is_editable_keymap(name):
			return
		try:
			save_custom_keymap(name, self._custom_overrides, self._custom_unbinds)
		except OSError as e:
			wx.MessageBox(f"Could not save keymap: {e}",
				"Save failed", wx.OK | wx.ICON_ERROR, self)
			return
		self._dirty = False
		# Activate the keymap immediately. Without this, the file is on disk but
		# the running app keeps using whatever prefs.keymap pointed at.
		prefs = get_app().prefs
		was_active = getattr(prefs, "keymap", "default") == name
		prefs.keymap = name
		self._reapply_keymap_to_running_app()
		try:
			import speak
			speak.speak(
				"Saved." if was_active else f"Saved and switched to keymap {name}.",
				interrupt=True,
			)
		except Exception:
			pass
		self.Destroy()

	def _reapply_keymap_to_running_app(self):
		"""Unregister and re-register invisible hotkeys with the freshly-saved keymap."""
		try:
			from GUI import main as _main
			if _main.window and getattr(_main.window, "invisible", False):
				_main.window.unregister_keys()
				_main.window.register_keys()
		except Exception:
			pass

	def _on_close(self, event):
		if self._dirty:
			dlg = wx.MessageDialog(self,
				"You have unsaved changes. Discard them and close?",
				"Unsaved changes",
				wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
			try:
				if dlg.ShowModal() != wx.ID_YES:
					if event is not None and hasattr(event, "Veto"):
						event.Veto()
					return
			finally:
				dlg.Destroy()
		if event is not None and hasattr(event, "Skip"):
			event.Skip()
		self.Destroy()
