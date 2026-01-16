import timeline
import platform
import os, sys
import wx
from . import main, theme
from application import get_app

class general(wx.Panel, wx.Dialog):
	def __init__(self, parent):
		super(general, self).__init__(parent)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.ask_dismiss=wx.CheckBox(self, -1, "Ask before dismissing timelines")
		self.main_box.Add(self.ask_dismiss, 0, wx.ALL, 10)
		self.ask_dismiss.SetValue(get_app().prefs.ask_dismiss)
		self.earcon_audio=wx.CheckBox(self, -1, "Play a sound when a post contains media")
		self.main_box.Add(self.earcon_audio, 0, wx.ALL, 10)
		self.earcon_audio.SetValue(get_app().prefs.earcon_audio)
		self.earcon_top=wx.CheckBox(self, -1, "Play a sound when you navigate to a timeline that may have new items")
		self.main_box.Add(self.earcon_top, 0, wx.ALL, 10)
		self.earcon_top.SetValue(get_app().prefs.earcon_top)
		self.demojify=wx.CheckBox(self, -1, "Remove emojis and other unicode characters from display names")
		self.main_box.Add(self.demojify, 0, wx.ALL, 10)
		self.demojify.SetValue(get_app().prefs.demojify)
		self.demojify_post=wx.CheckBox(self, -1, "Remove emojis and other unicode characters from post text")
		self.main_box.Add(self.demojify_post, 0, wx.ALL, 10)
		self.demojify_post.SetValue(get_app().prefs.demojify_post)
		self.reversed=wx.CheckBox(self, -1, "Reverse timelines (newest on bottom)")
		self.main_box.Add(self.reversed, 0, wx.ALL, 10)
		self.reversed.SetValue(get_app().prefs.reversed)
		self.wrap=wx.CheckBox(self, -1, "Word wrap in text fields")
		self.main_box.Add(self.wrap, 0, wx.ALL, 10)
		self.wrap.SetValue(get_app().prefs.wrap)
		self.errors=wx.CheckBox(self, -1, "Play sound and speak message for errors")
		self.main_box.Add(self.errors, 0, wx.ALL, 10)
		self.errors.SetValue(get_app().prefs.errors)
		self.autoOpenSingleURL=wx.CheckBox(self, -1, "When getting URLs from a post, automatically open the first URL if it is the only one")
		self.main_box.Add(self.autoOpenSingleURL, 0, wx.ALL, 10)
		self.autoOpenSingleURL.SetValue(get_app().prefs.autoOpenSingleURL)
		self.use24HourTime=wx.CheckBox(self, -1, "Use 24-hour time for post timestamps")
		self.main_box.Add(self.use24HourTime, 0, wx.ALL, 10)
		self.use24HourTime.SetValue(get_app().prefs.use24HourTime)

		# Content warning handling
		cw_label = wx.StaticText(self, -1, "Content warnings:")
		self.main_box.Add(cw_label, 0, wx.LEFT | wx.TOP, 10)
		self.cw_mode = wx.Choice(self, -1, choices=[
			"Hide post text (show CW only)",
			"Show CW followed by post text",
			"Ignore CW (show post text only)"
		])
		cw_mode_map = {'hide': 0, 'show': 1, 'ignore': 2}
		self.cw_mode.SetSelection(cw_mode_map.get(get_app().prefs.cw_mode, 0))
		self.main_box.Add(self.cw_mode, 0, wx.ALL, 10)


class templates(wx.Panel, wx.Dialog):
	def __init__(self, parent):
		super(templates, self).__init__(parent)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.postTemplate_label = wx.StaticText(self, -1, "Post template")
		self.postTemplate = wx.TextCtrl(self, -1, "")
		self.main_box.Add(self.postTemplate, 0, wx.ALL, 10)
		self.postTemplate.AppendText(get_app().prefs.postTemplate)
		self.quoteTemplate_label = wx.StaticText(self, -1, "Quote template")
		self.quoteTemplate = wx.TextCtrl(self, -1, "")
		self.main_box.Add(self.quoteTemplate, 0, wx.ALL, 10)
		self.quoteTemplate.AppendText(get_app().prefs.quoteTemplate)
		self.boostTemplate_label = wx.StaticText(self, -1, "Boost template")
		self.boostTemplate = wx.TextCtrl(self, -1, "")
		self.main_box.Add(self.boostTemplate, 0, wx.ALL, 10)
		self.boostTemplate.AppendText(get_app().prefs.boostTemplate)
		self.copyTemplate_label = wx.StaticText(self, -1, "Copy template")
		self.copyTemplate = wx.TextCtrl(self, -1, "")
		self.main_box.Add(self.copyTemplate, 0, wx.ALL, 10)
		self.copyTemplate.AppendText(get_app().prefs.copyTemplate)
		self.messageTemplate_label = wx.StaticText(self, -1, "Direct Message template")
		self.messageTemplate = wx.TextCtrl(self, -1, "")
		self.main_box.Add(self.messageTemplate, 0, wx.ALL, 10)
		self.messageTemplate.AppendText(get_app().prefs.messageTemplate)
		self.userTemplate_label = wx.StaticText(self, -1, "User template")
		self.userTemplate = wx.TextCtrl(self, -1, "")
		self.main_box.Add(self.userTemplate, 0, wx.ALL, 10)
		self.userTemplate.AppendText(get_app().prefs.userTemplate)
		self.notificationTemplate_label = wx.StaticText(self, -1, "Notification template")
		self.notificationTemplate = wx.TextCtrl(self, -1, "")
		self.main_box.Add(self.notificationTemplate, 0, wx.ALL, 10)
		self.notificationTemplate.AppendText(get_app().prefs.notificationTemplate)

class advanced(wx.Panel, wx.Dialog):
	def _get_available_keymaps(self):
		"""Get list of available keymaps from bundled and user config folders."""
		keymaps = ['default']  # Always have default

		# Check bundled keymaps folder
		if os.path.exists("keymaps"):
			for f in os.listdir("keymaps"):
				if f.endswith(".keymap") and not f.startswith("."):
					name = f[:-7]  # Remove .keymap extension
					if name != "default" and name not in keymaps:
						keymaps.append(name)

		# Check user config keymaps folder
		user_keymaps_path = os.path.join(get_app().confpath, "keymaps")
		if os.path.exists(user_keymaps_path):
			for f in os.listdir(user_keymaps_path):
				if f.endswith(".keymap") and not f.startswith("."):
					name = f[:-7]  # Remove .keymap extension
					if name != "default" and name not in keymaps:
						keymaps.append(name)

		return keymaps

	def __init__(self, parent):
		super(advanced, self).__init__(parent)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		if platform.system()!="Darwin":
			self.invisible=wx.CheckBox(self, -1, "Enable invisible interface")
			self.main_box.Add(self.invisible, 0, wx.ALL, 10)
			self.invisible.SetValue(get_app().prefs.invisible)
			self.invisible_sync=wx.CheckBox(self, -1, "Sync invisible interface with UI (uncheck for reduced lag in invisible interface)")
			self.main_box.Add(self.invisible_sync, 0, wx.ALL, 10)
			self.invisible_sync.SetValue(get_app().prefs.invisible_sync)
			self.repeat=wx.CheckBox(self, -1, "Repeat items at edges of invisible interface")
			self.main_box.Add(self.repeat, 0, wx.ALL, 10)
			self.repeat.SetValue(get_app().prefs.repeat)

			# Keymap selection
			keymap_label = wx.StaticText(self, -1, "Keymap:")
			self.main_box.Add(keymap_label, 0, wx.LEFT | wx.TOP, 10)
			self.keymaps = self._get_available_keymaps()
			self.keymap_choice = wx.Choice(self, -1, choices=self.keymaps)
			current_keymap = get_app().prefs.keymap
			if current_keymap in self.keymaps:
				self.keymap_choice.SetSelection(self.keymaps.index(current_keymap))
			else:
				self.keymap_choice.SetSelection(0)
			self.main_box.Add(self.keymap_choice, 0, wx.ALL, 10)
		self.position=wx.CheckBox(self, -1, "Speak position information when navigating between timelines of invisible interface and switching timelines")
		self.main_box.Add(self.position, 0, wx.ALL, 10)
		self.position.SetValue(get_app().prefs.position)
		self.update_time_label = wx.StaticText(self, -1, "Update time, in minutes")
		self.update_time = wx.TextCtrl(self, -1, "")
		self.main_box.Add(self.update_time, 0, wx.ALL, 10)
		self.update_time.AppendText(str(get_app().prefs.update_time))
		self.user_limit_label = wx.StaticText(self, -1, "Max API calls when fetching users in user viewer")
		self.user_limit = wx.TextCtrl(self, -1, "")
		self.main_box.Add(self.user_limit, 0, wx.ALL, 10)
		self.user_limit.AppendText(str(get_app().prefs.user_limit))
		self.count_label = wx.StaticText(self, -1, "Number of posts to fetch per call (Maximum is 40)")
		self.count = wx.TextCtrl(self, -1, "")
		self.main_box.Add(self.count, 0, wx.ALL, 10)
		self.count.AppendText(str(get_app().prefs.count))
		self.fetch_pages_label = wx.StaticText(self, -1, "Number of API calls to make when loading timelines (1-10)")
		self.fetch_pages = wx.TextCtrl(self, -1, "")
		self.main_box.Add(self.fetch_pages, 0, wx.ALL, 10)
		self.fetch_pages.AppendText(str(get_app().prefs.fetch_pages))
		self.single_api_on_startup=wx.CheckBox(self, -1, "Use only one API call on initial timeline loads (faster startup)")
		self.main_box.Add(self.single_api_on_startup, 0, wx.ALL, 10)
		self.single_api_on_startup.SetValue(get_app().prefs.single_api_on_startup)
		self.streaming=wx.CheckBox(self, -1, "Enable streaming for home and notifications (Requires restart to disable)")
		self.main_box.Add(self.streaming, 0, wx.ALL, 10)
		self.streaming.SetValue(get_app().prefs.streaming)
		self.load_all_previous=wx.CheckBox(self, -1, "Load all previous posts until timeline is fully loaded")
		self.main_box.Add(self.load_all_previous, 0, wx.ALL, 10)
		self.load_all_previous.SetValue(get_app().prefs.load_all_previous)
		self.sync_timeline_position=wx.CheckBox(self, -1, "Sync home timeline position with Mastodon (Mastodon only)")
		self.main_box.Add(self.sync_timeline_position, 0, wx.ALL, 10)
		self.sync_timeline_position.SetValue(get_app().prefs.sync_timeline_position)

		# Dark mode setting
		dark_mode_label = wx.StaticText(self, -1, "Dark mode:")
		self.main_box.Add(dark_mode_label, 0, wx.LEFT | wx.TOP, 10)
		self.dark_mode = wx.Choice(self, -1, choices=[
			"Off",
			"On",
			"Auto (follow system)"
		])
		dark_mode_map = {'off': 0, 'on': 1, 'auto': 2}
		self.dark_mode.SetSelection(dark_mode_map.get(get_app().prefs.dark_mode, 0))
		self.main_box.Add(self.dark_mode, 0, wx.ALL, 10)

class confirmation(wx.Panel, wx.Dialog):
	def __init__(self, parent):
		super(confirmation, self).__init__(parent)
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		info_label = wx.StaticText(self, -1, "Show confirmation dialogs for the following actions (menu/hotkeys only):")
		self.main_box.Add(info_label, 0, wx.ALL, 10)

		self.confirm_boost=wx.CheckBox(self, -1, "Boosting")
		self.main_box.Add(self.confirm_boost, 0, wx.ALL, 10)
		self.confirm_boost.SetValue(get_app().prefs.confirm_boost)

		self.confirm_unboost=wx.CheckBox(self, -1, "Unboosting")
		self.main_box.Add(self.confirm_unboost, 0, wx.ALL, 10)
		self.confirm_unboost.SetValue(get_app().prefs.confirm_unboost)

		self.confirm_favorite=wx.CheckBox(self, -1, "Favoriting")
		self.main_box.Add(self.confirm_favorite, 0, wx.ALL, 10)
		self.confirm_favorite.SetValue(get_app().prefs.confirm_favorite)

		self.confirm_unfavorite=wx.CheckBox(self, -1, "Unfavoriting")
		self.main_box.Add(self.confirm_unfavorite, 0, wx.ALL, 10)
		self.confirm_unfavorite.SetValue(get_app().prefs.confirm_unfavorite)

		self.confirm_follow=wx.CheckBox(self, -1, "Following")
		self.main_box.Add(self.confirm_follow, 0, wx.ALL, 10)
		self.confirm_follow.SetValue(get_app().prefs.confirm_follow)

		self.confirm_unfollow=wx.CheckBox(self, -1, "Unfollowing")
		self.main_box.Add(self.confirm_unfollow, 0, wx.ALL, 10)
		self.confirm_unfollow.SetValue(get_app().prefs.confirm_unfollow)

class OptionsGui(wx.Dialog):
	def __init__(self):
		wx.Dialog.__init__(self, None, title="Options", size=(350,200))
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.notebook = wx.Notebook(self.panel)
		self.general=general(self.notebook)
		self.notebook.AddPage(self.general, "General")
		self.templates=templates(self.notebook)
		self.notebook.AddPage(self.templates, "Templates")
		self.advanced=advanced(self.notebook)
		self.notebook.AddPage(self.advanced, "Advanced")
		self.confirmation=confirmation(self.notebook)
		self.notebook.AddPage(self.confirmation, "Confirmation")
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
		self.general.ask_dismiss.SetFocus()

	def OnOK(self, event):
		refresh=False
		get_app().prefs.use24HourTime = self.general.use24HourTime.GetValue()
		get_app().prefs.ask_dismiss=self.general.ask_dismiss.GetValue()
		if platform.system()!="Darwin":
			get_app().prefs.invisible=self.advanced.invisible.GetValue()
			get_app().prefs.invisible_sync=self.advanced.invisible_sync.GetValue()
			get_app().prefs.repeat=self.advanced.repeat.GetValue()
			get_app().prefs.invisible_sync=self.advanced.invisible_sync.GetValue()

			# Handle keymap change - re-register if keymap changed while invisible interface is enabled
			new_keymap = self.advanced.keymaps[self.advanced.keymap_choice.GetSelection()]
			keymap_changed = get_app().prefs.keymap != new_keymap
			get_app().prefs.keymap = new_keymap

			if get_app().prefs.invisible and not main.window.invisible:
				main.window.register_keys()
			elif not get_app().prefs.invisible and main.window.invisible:
				main.window.unregister_keys()
			elif keymap_changed and main.window.invisible:
				# Re-register with new keymap
				main.window.unregister_keys()
				main.window.register_keys()
		get_app().prefs.streaming=self.advanced.streaming.GetValue()
		get_app().prefs.load_all_previous=self.advanced.load_all_previous.GetValue()
		get_app().prefs.sync_timeline_position=self.advanced.sync_timeline_position.GetValue()
		# Dark mode setting
		dark_mode_values = ['off', 'on', 'auto']
		get_app().prefs.dark_mode = dark_mode_values[self.advanced.dark_mode.GetSelection()]
		get_app().prefs.position=self.advanced.position.GetValue()
		get_app().prefs.earcon_audio=self.general.earcon_audio.GetValue()
		get_app().prefs.earcon_top=self.general.earcon_top.GetValue()
		get_app().prefs.wrap=self.general.wrap.GetValue()
		get_app().prefs.update_time=int(self.advanced.update_time.GetValue())
		if get_app().prefs.update_time<1:
			get_app().prefs.update_time=1
		get_app().prefs.user_limit=int(self.advanced.user_limit.GetValue())
		if get_app().prefs.user_limit<1:
			get_app().prefs.user_limit=1
		if get_app().prefs.user_limit>15:
			get_app().prefs.user_limit=15
		get_app().prefs.count=int(self.advanced.count.GetValue())
		if get_app().prefs.count>40:
			get_app().prefs.count=40
		get_app().prefs.fetch_pages=int(self.advanced.fetch_pages.GetValue())
		if get_app().prefs.fetch_pages<1:
			get_app().prefs.fetch_pages=1
		if get_app().prefs.fetch_pages>10:
			get_app().prefs.fetch_pages=10
		get_app().prefs.single_api_on_startup=self.advanced.single_api_on_startup.GetValue()
		# Confirmation settings
		get_app().prefs.confirm_boost=self.confirmation.confirm_boost.GetValue()
		get_app().prefs.confirm_unboost=self.confirmation.confirm_unboost.GetValue()
		get_app().prefs.confirm_favorite=self.confirmation.confirm_favorite.GetValue()
		get_app().prefs.confirm_unfavorite=self.confirmation.confirm_unfavorite.GetValue()
		get_app().prefs.confirm_follow=self.confirmation.confirm_follow.GetValue()
		get_app().prefs.confirm_unfollow=self.confirmation.confirm_unfollow.GetValue()
		if get_app().prefs.reversed!=self.general.reversed.GetValue():
			reverse=True
		else:
			reverse=False
		get_app().prefs.reversed=self.general.reversed.GetValue()
		# Check if any display-affecting settings changed
		cw_mode_values = ['hide', 'show', 'ignore']
		new_cw_mode = cw_mode_values[self.general.cw_mode.GetSelection()]
		if (get_app().prefs.demojify_post != self.general.demojify_post.GetValue() or
			get_app().prefs.demojify != self.general.demojify.GetValue() or
			get_app().prefs.postTemplate != self.templates.postTemplate.GetValue() or
			get_app().prefs.boostTemplate != self.templates.boostTemplate.GetValue() or
			get_app().prefs.quoteTemplate != self.templates.quoteTemplate.GetValue() or
			get_app().prefs.messageTemplate != self.templates.messageTemplate.GetValue() or
			get_app().prefs.notificationTemplate != self.templates.notificationTemplate.GetValue() or
			get_app().prefs.use24HourTime != self.general.use24HourTime.GetValue() or
			get_app().prefs.cw_mode != new_cw_mode):
			refresh=True
		get_app().prefs.demojify=self.general.demojify.GetValue()
		get_app().prefs.demojify_post=self.general.demojify_post.GetValue()
		get_app().prefs.errors=self.general.errors.GetValue()
		get_app().prefs.postTemplate=self.templates.postTemplate.GetValue()
		get_app().prefs.quoteTemplate=self.templates.quoteTemplate.GetValue()
		get_app().prefs.boostTemplate=self.templates.boostTemplate.GetValue()
		get_app().prefs.messageTemplate=self.templates.messageTemplate.GetValue()
		get_app().prefs.copyTemplate=self.templates.copyTemplate.GetValue()
		get_app().prefs.userTemplate=self.templates.userTemplate.GetValue()
		get_app().prefs.notificationTemplate=self.templates.notificationTemplate.GetValue()
		get_app().prefs.autoOpenSingleURL=self.general.autoOpenSingleURL.GetValue()
		# Content warning mode
		get_app().prefs.cw_mode = new_cw_mode
		self.Destroy()
		if reverse:
			timeline.reverse()
		if refresh:
			# Clear display caches on all statuses when templates/display settings change
			for account in get_app().accounts:
				for tl in account.timelines:
					for status in tl.statuses:
						if hasattr(status, '_display_cache'):
							delattr(status, '_display_cache')
			main.window.refreshList()

	def OnClose(self, event):
		self.Destroy()
