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
			# Windows/Linux: use _MEIPASS or executable directory
			return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
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

		# Check user config path
		sounds_path = get_app().confpath+"/sounds"
		try:
			if os.path.exists(sounds_path):
				for item in os.listdir(sounds_path):
					if not item.startswith("_") and not item.startswith(".") and os.path.isdir(os.path.join(sounds_path, item)):
						all_packs.add(item)
		except:
			pass

		# Check relative path (development)
		try:
			if os.path.exists("sounds"):
				for item in os.listdir("sounds"):
					if not item.startswith("_") and not item.startswith(".") and os.path.isdir(os.path.join("sounds", item)):
						all_packs.add(item)
		except:
			pass

		# Check bundled path (frozen apps)
		if bundled_path:
			bundled_sounds = os.path.join(bundled_path, "sounds")
			try:
				if os.path.exists(bundled_sounds):
					for item in os.listdir(bundled_sounds):
						if not item.startswith("_") and not item.startswith(".") and os.path.isdir(os.path.join(bundled_sounds, item)):
							all_packs.add(item)
			except:
				pass

		# Add soundpacks to list
		for pack in sorted(all_packs):
			self.soundpackslist.Insert(pack, self.soundpackslist.GetCount())
			if account.prefs.soundpack == pack:
				self.soundpackslist.SetSelection(self.soundpackslist.GetCount()-1)
				self.sp = pack
		if not hasattr(self,"sp"):
			self.sp="default"
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
		self.footer = wx.TextCtrl(self, -1, "",style=wx.TE_MULTILINE, name="Post Footer (Optional)")
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
