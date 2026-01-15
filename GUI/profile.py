from application import get_app
import wx
import speak

class ProfileGui(wx.Dialog):

	def __init__(self, account):
		self.account = account
		# Get platform backend
		self.platform = getattr(account, '_platform', account)
		
		# Check if platform supports profile editing
		if not hasattr(self.platform, 'get_own_profile') or not hasattr(self.platform, 'update_profile'):
			wx.Dialog.__init__(self, None, title="Profile Editor", size=(350, 200))
			speak.speak("This platform does not support profile editing.")
			return
		
		# Get current profile data
		profile_data = self.platform.get_own_profile()
		if not profile_data:
			wx.Dialog.__init__(self, None, title="Profile Editor", size=(350, 200))
			speak.speak("Could not load profile data.")
			return
		
		wx.Dialog.__init__(self, None, title="Profile Editor", size=(350, 200))
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		self.name_label = wx.StaticText(self.panel, -1, "Display Name")
		self.name = wx.TextCtrl(self.panel, -1, "")
		self.main_box.Add(self.name, 0, wx.ALL, 10)
		self.name.SetFocus()
		display_name = profile_data.get('display_name', '')
		if display_name:
			self.name.SetValue(display_name)

		self.description_label = wx.StaticText(self.panel, -1, "Bio")
		self.description = wx.TextCtrl(self.panel, -1, "", style=wx.TE_MULTILINE)
		self.main_box.Add(self.description, 0, wx.ALL, 10)
		note = profile_data.get('note', '')
		if note:
			# Strip HTML from the bio
			self.description.SetValue(self.account.app.strip_html(note))

		# Profile fields (Mastodon supports up to 4 key-value pairs, Bluesky doesn't support this)
		fields = profile_data.get('fields', [])
		self.supports_fields = len(fields) > 0 or getattr(self.platform, 'platform_name', '') == 'mastodon'
		
		if self.supports_fields:
			self.fields_label = wx.StaticText(self.panel, -1, "Profile Fields (Name: Value, one per line)")
			self.fields = wx.TextCtrl(self.panel, -1, "", style=wx.TE_MULTILINE)
			self.main_box.Add(self.fields, 0, wx.ALL, 10)
			if fields:
				field_text = ""
				for field in fields:
					name = field.get('name', '')
					value = field.get('value', '')
					if name and value:
						field_text += name + ": " + self.account.app.strip_html(value) + "\n"
				self.fields.SetValue(field_text.strip())
		else:
			self.fields = None

		# Locked account option (only for platforms that support it)
		self.supports_locked = getattr(self.platform, 'platform_name', '') == 'mastodon'
		if self.supports_locked:
			self.locked = wx.CheckBox(self.panel, -1, "Lock account (manually approve followers)")
			self.main_box.Add(self.locked, 0, wx.ALL, 10)
			self.locked.SetValue(profile_data.get('locked', False))
		else:
			self.locked = None

		self.update = wx.Button(self.panel, wx.ID_DEFAULT, "&Update")
		self.update.SetDefault()
		self.update.Bind(wx.EVT_BUTTON, self.Update)
		self.main_box.Add(self.update, 0, wx.ALL, 10)

		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)
		self.panel.Layout()

	def Update(self, event):
		# Check if platform supports profile editing
		if not hasattr(self.platform, 'update_profile'):
			speak.speak("This platform does not support profile editing.")
			self.Destroy()
			return
		
		# Parse fields from text (if supported)
		fields_list = None
		if self.fields and self.supports_fields:
			fields_list = []
			fields_text = self.fields.GetValue().strip()
			if fields_text:
				for line in fields_text.split("\n"):
					if ": " in line:
						name, value = line.split(": ", 1)
						fields_list.append({"name": name.strip(), "value": value.strip()})

		# Get locked value (if supported)
		locked_value = None
		if self.locked and self.supports_locked:
			locked_value = self.locked.GetValue()

		try:
			success = self.platform.update_profile(
				display_name=self.name.GetValue(),
				note=self.description.GetValue(),
				fields=fields_list,
				locked=locked_value
			)
			if success:
				speak.speak("Profile updated.")
			else:
				speak.speak("Failed to update profile.")
		except Exception as e:
			self.account.app.handle_error(e, "Update profile")
		self.Destroy()

	def OnClose(self, event):
		self.Destroy()
