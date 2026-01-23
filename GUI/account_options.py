from sound_lib import stream
import platform
import os, sys
import wx
from . import main, theme
from application import get_app

def _get_bundled_path():
	"""Get the path to bundled resources (for PyInstaller frozen apps)."""
	import platform as plat
	if getattr(sys, 'frozen', False):
		if plat.system() == 'Darwin':
			# macOS .app bundle: Resources are in Contents/Resources
			# sys.executable is at Contents/MacOS/AppName
			return os.path.join(os.path.dirname(sys.executable), '..', 'Resources')
		else:
			# Windows/Linux: sounds/keymaps are in the same directory as the executable
			# (not in _MEIPASS/_internal, which is for Python modules)
			return os.path.dirname(sys.executable)
	return None

class general(wx.Panel, wx.Dialog):
	def __init__(self, account, parent):
		# Get bundled path for frozen apps
		bundled_path = _get_bundled_path()

		# Try multiple paths for the preview sound
		self.snd = None
		sound_paths = [
			get_app().confpath+"/sounds/default/boundary.ogg",
			"sounds/default/boundary.ogg",
		]
		if bundled_path:
			sound_paths.append(os.path.join(bundled_path, "sounds/default/boundary.ogg"))
		for path in sound_paths:
			if os.path.exists(path):
				try:
					self.snd = stream.FileStream(file=path)
					break
				except:
					pass
		self.account=account
		super(general, self).__init__(parent)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.soundpack_box = wx.BoxSizer(wx.VERTICAL)
		self.soundpacklist_label=wx.StaticText(self, -1, "Soundpacks")
		self.main_box.Add(self.soundpacklist_label, 0, wx.LEFT | wx.TOP, 10)
		self.soundpackslist = wx.ListBox(self, -1, name="Soundpacks")
		self.soundpack_box.Add(self.soundpackslist, 0, wx.ALL, 10)
		self.soundpackslist.Bind(wx.EVT_LISTBOX, self.on_soundpacks_list_change)

		# Collect soundpacks from all locations
		all_packs = set()
		self._soundpack_paths_checked = []  # For debugging

		# Check user config path
		sounds_path = get_app().confpath+"/sounds"
		self._soundpack_paths_checked.append(f"Config: {sounds_path} (exists={os.path.exists(sounds_path)})")
		try:
			if os.path.exists(sounds_path):
				for item in os.listdir(sounds_path):
					full_path = os.path.join(sounds_path, item)
					is_dir = os.path.isdir(full_path)
					if not item.startswith("_") and not item.startswith(".") and is_dir:
						all_packs.add(item)
		except Exception as e:
			self._soundpack_paths_checked.append(f"  Error: {e}")

		# Check relative path (development)
		rel_sounds = os.path.abspath("sounds")
		self._soundpack_paths_checked.append(f"Relative: {rel_sounds} (exists={os.path.exists('sounds')})")
		try:
			if os.path.exists("sounds"):
				for item in os.listdir("sounds"):
					full_path = os.path.join("sounds", item)
					is_dir = os.path.isdir(full_path)
					if not item.startswith("_") and not item.startswith(".") and is_dir:
						all_packs.add(item)
		except Exception as e:
			self._soundpack_paths_checked.append(f"  Error: {e}")

		# Check bundled path (frozen apps)
		if bundled_path:
			bundled_sounds = os.path.join(bundled_path, "sounds")
			self._soundpack_paths_checked.append(f"Bundled: {bundled_sounds} (exists={os.path.exists(bundled_sounds)})")
			try:
				if os.path.exists(bundled_sounds):
					for item in os.listdir(bundled_sounds):
						full_path = os.path.join(bundled_sounds, item)
						is_dir = os.path.isdir(full_path)
						if not item.startswith("_") and not item.startswith(".") and is_dir:
							all_packs.add(item)
			except Exception as e:
				self._soundpack_paths_checked.append(f"  Error: {e}")
		else:
			self._soundpack_paths_checked.append("Bundled: N/A (not frozen)")

		self._soundpack_paths_checked.append(f"Found packs: {sorted(all_packs)}")

		# Add soundpacks to list
		for pack in sorted(all_packs):
			self.soundpackslist.Insert(pack, self.soundpackslist.GetCount())
			if account.prefs.soundpack == pack:
				self.soundpackslist.SetSelection(self.soundpackslist.GetCount()-1)
				self.sp = pack
		if not hasattr(self,"sp"):
			self.sp="default"

		# If no soundpacks found, show debug info
		if len(all_packs) == 0:
			self.soundpackslist.Insert("(No soundpacks found - see debug info)", 0)
			# Log debug info
			import logging
			logging.warning("No soundpacks found. Paths checked:")
			for path_info in self._soundpack_paths_checked:
				logging.warning(f"  {path_info}")
		self.soundpan_label = wx.StaticText(self, -1, "Sound pan")
		self.main_box.Add(self.soundpan_label, 0, wx.LEFT | wx.TOP, 10)
		self.soundpan = wx.Slider(self, -1, int(self.account.prefs.soundpan*50),-50,50,name="Sound pan")
		self.soundpan.Bind(wx.EVT_SLIDER,self.OnPan)
		self.main_box.Add(self.soundpan, 0, wx.ALL, 10)
		self.soundvolume_label = wx.StaticText(self, -1, "Soundpack volume")
		self.main_box.Add(self.soundvolume_label, 0, wx.LEFT | wx.TOP, 10)
		# Get soundpack_volume with fallback for old configs
		current_volume = getattr(self.account.prefs, 'soundpack_volume', 1.0)
		self.soundvolume = wx.Slider(self, -1, int(current_volume*100), 0, 100, name="Soundpack volume")
		self.soundvolume.Bind(wx.EVT_SLIDER, self.OnVolume)
		self.main_box.Add(self.soundvolume, 0, wx.ALL, 10)
		self.footer_label = wx.StaticText(self, -1, "Post Footer (Optional)")
		self.main_box.Add(self.footer_label, 0, wx.LEFT | wx.TOP, 10)
		footer_style = wx.TE_MULTILINE if getattr(get_app().prefs, 'word_wrap', True) else wx.TE_MULTILINE | wx.TE_DONTWRAP
		self.footer = wx.TextCtrl(self, -1, "", style=footer_style, name="Post Footer (Optional)")
		self.main_box.Add(self.footer, 0, wx.ALL, 10)
		self.footer.AppendText(account.prefs.footer)
		# Get max chars from account, default to 500
		max_chars = getattr(account, 'max_chars', 500)
		self.footer.SetMaxLength(max_chars)

		# Mastodon-specific options
		platform_type = getattr(account.prefs, 'platform_type', 'mastodon')
		if platform_type == 'mastodon':
			self.mentions_in_notifications = wx.CheckBox(self, -1, "Show mentions in notifications buffer")
			self.mentions_in_notifications.SetValue(account.prefs.mentions_in_notifications)
			self.main_box.Add(self.mentions_in_notifications, 0, wx.ALL, 10)
		else:
			self.mentions_in_notifications = None

	def OnPan(self,event):
		pan=self.soundpan.GetValue()/50
		if self.snd:
			self.snd.pan=pan
			self.snd.play()

	def OnVolume(self, event):
		volume = self.soundvolume.GetValue() / 100
		if self.snd:
			self.snd.volume = volume
			self.snd.play()

	def on_soundpacks_list_change(self, event):
		self.sp=event.GetString()

class OptionsGui(wx.Dialog):
	def __init__(self,account):
		self.account=account
		# Use acct for Mastodon instead of screen_name
		acct = getattr(self.account.me, 'acct', 'Unknown')
		wx.Dialog.__init__(self, None, title="Account Options for @" + acct, size=(350,200))
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.notebook = wx.Notebook(self.panel)
		self.general=general(self.account, self.notebook)
		self.notebook.AddPage(self.general, "General")
		self.timelines_panel = TimelinesPanel(self.account, self.notebook)
		self.notebook.AddPage(self.timelines_panel, "Timelines")
		self.alias_panel = AliasPanel(self.account, self.notebook)
		self.notebook.AddPage(self.alias_panel, "Aliases")
		self.main_box.Add(self.notebook, 0, wx.ALL, 10)
		self.ok = wx.Button(self.panel, wx.ID_OK, "&OK")
		self.ok.SetDefault()
		self.ok.Bind(wx.EVT_BUTTON, self.OnOK)
		self.main_box.Add(self.ok, 0, wx.ALL, 10)
		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)
		self.panel.Layout()
		theme.apply_theme(self)
		self.general.soundpackslist.SetFocus()

	def OnOK(self, event):
		self.account.prefs.soundpack=self.general.sp
		self.account.prefs.soundpan=self.general.soundpan.GetValue()/50
		self.account.prefs.soundpack_volume=self.general.soundvolume.GetValue()/100
		self.account.prefs.footer=self.general.footer.GetValue()

		# Save timeline order
		self.account.prefs.timeline_order = self.timelines_panel.get_order()

		# Handle mentions_in_notifications setting change
		if self.general.mentions_in_notifications is not None:
			old_value = self.account.prefs.mentions_in_notifications
			new_value = self.general.mentions_in_notifications.GetValue()
			if old_value != new_value:
				self.account.prefs.mentions_in_notifications = new_value
				# Clear and reload the notifications timeline
				import threading
				for tl in self.account.timelines:
					if tl.type == "notifications":
						tl.statuses = []
						tl.update_kwargs = {}
						tl.index = 0
						tl.initial = True
						if hasattr(tl, '_unfiltered_statuses'):
							tl._unfiltered_statuses = []
						# Reload in background
						threading.Thread(target=tl.load, daemon=True).start()
						break

		# Explicitly save preferences to ensure persistence
		self.account.prefs.save()

		if self.general.snd:
			self.general.snd.free()
		self.Destroy()

	def OnClose(self, event):
		if self.general.snd:
			self.general.snd.free()
		self.Destroy()


class TimelinesPanel(wx.Panel):
	"""Panel for reordering built-in timelines."""

	def __init__(self, account, parent):
		super().__init__(parent)
		self.account = account
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		# Define built-in timelines based on platform
		platform_type = getattr(account.prefs, 'platform_type', 'mastodon')
		if platform_type == "bluesky":
			self.available_timelines = {
				"home": "Home",
				"notifications": "Notifications",
				"mentions": "Mentions",
				"sent": "Sent",
			}
			self.default_order = ["home", "notifications", "mentions", "sent"]
		else:
			self.available_timelines = {
				"home": "Home",
				"notifications": "Notifications",
				"mentions": "Mentions",
				"conversations": "Conversations",
				"sent": "Sent",
			}
			self.default_order = ["home", "notifications", "mentions", "conversations", "sent"]

		# Get current order or use default
		self.current_order = list(account.prefs.timeline_order) if account.prefs.timeline_order else list(self.default_order)
		# Ensure all available timelines are in the order
		for tl_key in self.default_order:
			if tl_key not in self.current_order:
				self.current_order.append(tl_key)
		# Remove any timelines that are no longer available
		self.current_order = [tl for tl in self.current_order if tl in self.available_timelines]

		# Label
		label = wx.StaticText(self, -1, "Built-in timeline order (changes apply on restart):")
		self.main_box.Add(label, 0, wx.LEFT | wx.TOP, 10)

		# Horizontal box for list and buttons
		h_box = wx.BoxSizer(wx.HORIZONTAL)

		# Timeline list
		self.timeline_list = wx.ListBox(self, -1, size=(200, 150), name="Timeline order")
		self._populate_list()
		h_box.Add(self.timeline_list, 1, wx.ALL | wx.EXPAND, 10)

		# Buttons box
		btn_box = wx.BoxSizer(wx.VERTICAL)

		self.move_up_btn = wx.Button(self, -1, "Move &Up")
		self.move_up_btn.Bind(wx.EVT_BUTTON, self.on_move_up)
		btn_box.Add(self.move_up_btn, 0, wx.ALL, 5)

		self.move_down_btn = wx.Button(self, -1, "Move &Down")
		self.move_down_btn.Bind(wx.EVT_BUTTON, self.on_move_down)
		btn_box.Add(self.move_down_btn, 0, wx.ALL, 5)

		self.reset_btn = wx.Button(self, -1, "&Reset to Default")
		self.reset_btn.Bind(wx.EVT_BUTTON, self.on_reset)
		btn_box.Add(self.reset_btn, 0, wx.ALL, 5)

		h_box.Add(btn_box, 0, wx.ALIGN_CENTER_VERTICAL)

		self.main_box.Add(h_box, 1, wx.EXPAND)
		self.SetSizer(self.main_box)

	def _populate_list(self):
		"""Populate the list with current timeline order."""
		self.timeline_list.Clear()
		for tl_key in self.current_order:
			if tl_key in self.available_timelines:
				self.timeline_list.Append(self.available_timelines[tl_key])
		if self.timeline_list.GetCount() > 0:
			self.timeline_list.SetSelection(0)

	def on_move_up(self, event):
		"""Move selected timeline up in the order."""
		idx = self.timeline_list.GetSelection()
		if idx > 0:
			# Swap in order
			self.current_order[idx], self.current_order[idx - 1] = self.current_order[idx - 1], self.current_order[idx]
			self._populate_list()
			self.timeline_list.SetSelection(idx - 1)

	def on_move_down(self, event):
		"""Move selected timeline down in the order."""
		idx = self.timeline_list.GetSelection()
		if idx < len(self.current_order) - 1 and idx >= 0:
			# Swap in order
			self.current_order[idx], self.current_order[idx + 1] = self.current_order[idx + 1], self.current_order[idx]
			self._populate_list()
			self.timeline_list.SetSelection(idx + 1)

	def on_reset(self, event):
		"""Reset to default order."""
		self.current_order = list(self.default_order)
		self._populate_list()

	def get_order(self):
		"""Return the current timeline order."""
		return self.current_order


class AliasPanel(wx.Panel):
	"""Panel for managing user aliases."""

	def __init__(self, account, parent):
		super().__init__(parent)
		self.account = account
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		# Instructions
		info = wx.StaticText(self, -1, "Set custom display names for users. These will replace their actual display names throughout the app.")
		self.main_box.Add(info, 0, wx.ALL, 10)

		# List of current aliases
		self.list_label = wx.StaticText(self, -1, "&Aliases")
		self.main_box.Add(self.list_label, 0, wx.LEFT | wx.TOP, 10)
		self.alias_list = wx.ListBox(self, -1, size=(300, 150), name="Aliases")
		self.main_box.Add(self.alias_list, 0, wx.EXPAND | wx.ALL, 10)
		self.alias_list.Bind(wx.EVT_LISTBOX, self.on_selection_change)

		# Store user info for each alias
		self._alias_data = {}  # Maps list index to (user_id, acct, alias)

		# Buttons
		btn_box = wx.BoxSizer(wx.HORIZONTAL)
		self.edit_btn = wx.Button(self, -1, "&Edit")
		self.edit_btn.Bind(wx.EVT_BUTTON, self.on_edit)
		self.edit_btn.Enable(False)
		btn_box.Add(self.edit_btn, 0, wx.ALL, 5)

		self.remove_btn = wx.Button(self, -1, "&Remove")
		self.remove_btn.Bind(wx.EVT_BUTTON, self.on_remove)
		self.remove_btn.Enable(False)
		btn_box.Add(self.remove_btn, 0, wx.ALL, 5)

		self.main_box.Add(btn_box, 0, wx.ALL, 5)
		self.SetSizer(self.main_box)

		# Populate after buttons exist
		self._populate_list()

	def _populate_list(self):
		"""Populate the list with current aliases."""
		self.alias_list.Clear()
		self._alias_data = {}
		try:
			aliases = getattr(self.account.prefs, 'aliases', None)
			if aliases:
				# Convert to dict if it's a Config object
				if hasattr(aliases, 'items'):
					alias_items = list(aliases.items())
				elif hasattr(aliases, 'keys'):
					alias_items = [(k, aliases[k]) for k in aliases.keys()]
				else:
					alias_items = []
				idx = 0
				for user_id, alias in alias_items:
					# Try to get user info from cache if available
					acct = self._get_user_acct(user_id) or f"ID: {user_id}"
					display_text = f"{alias} ({acct})"
					self.alias_list.Append(display_text)
					self._alias_data[idx] = (user_id, acct, alias)
					idx += 1
		except Exception:
			pass
		self._update_buttons()

	def _get_user_acct(self, user_id):
		"""Try to get user acct from cache."""
		# Check timeline statuses for this user
		try:
			for tl in getattr(self.account, 'timelines', []):
				for status in getattr(tl, 'statuses', []):
					status_account = getattr(status, 'account', None)
					if status_account and str(getattr(status_account, 'id', '')) == str(user_id):
						return getattr(status_account, 'acct', None)
		except:
			pass
		return None

	def _update_buttons(self):
		"""Enable/disable buttons based on selection."""
		has_selection = self.alias_list.GetSelection() != wx.NOT_FOUND
		self.edit_btn.Enable(has_selection)
		self.remove_btn.Enable(has_selection)

	def on_selection_change(self, event):
		self._update_buttons()

	def _invalidate_display_caches(self):
		"""Clear display caches so aliases are refreshed."""
		for tl in getattr(self.account, 'timelines', []):
			tl.invalidate_display_cache()
			for status in getattr(tl, 'statuses', []):
				if hasattr(status, '_display_cache'):
					delattr(status, '_display_cache')

	def on_edit(self, event):
		"""Edit the selected alias."""
		idx = self.alias_list.GetSelection()
		if idx == wx.NOT_FOUND or idx not in self._alias_data:
			return
		user_id, acct, current_alias = self._alias_data[idx]
		dlg = wx.TextEntryDialog(self, f"Enter alias for {acct}:", "Edit Alias", current_alias)
		if dlg.ShowModal() == wx.ID_OK:
			new_alias = dlg.GetValue().strip()
			if new_alias:
				self.account.prefs.aliases[user_id] = new_alias
				self._invalidate_display_caches()
				self._populate_list()
				self.alias_list.SetSelection(idx)
		dlg.Destroy()

	def on_remove(self, event):
		"""Remove the selected alias."""
		idx = self.alias_list.GetSelection()
		if idx == wx.NOT_FOUND or idx not in self._alias_data:
			return
		user_id, acct, alias = self._alias_data[idx]
		if user_id in self.account.prefs.aliases:
			del self.account.prefs.aliases[user_id]
			self._invalidate_display_caches()
			self._populate_list()
			# Select nearest item
			if self.alias_list.GetCount() > 0:
				new_idx = min(idx, self.alias_list.GetCount() - 1)
				self.alias_list.SetSelection(new_idx)
		self._update_buttons()
