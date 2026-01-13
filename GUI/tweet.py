import speak
import wx
import sound
import platform
from . import poll
from application import get_app

text_box_size=(800,600)

class TweetGui(wx.Dialog):
	def __init__(self, account, inittext="", type="post", status=None):
		self.ids = []
		self.account = account
		self.inittext = inittext
		self.max_length = 0
		self.status = status
		self.type = type
		self.poll_runfor = None
		self.poll_opt1 = None
		self.poll_opt2 = None
		self.poll_opt3 = None
		self.poll_opt4 = None
		wx.Dialog.__init__(self, None, title=type, size=(350,200))
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.text_label = wx.StaticText(self.panel, -1, "Te&xt")
		if self.account.app.prefs.wrap:
			self.text = wx.TextCtrl(self.panel, -1, "", style=wx.TE_MULTILINE, size=text_box_size)
		else:
			self.text = wx.TextCtrl(self.panel, -1, "", style=wx.TE_MULTILINE|wx.TE_DONTWRAP, size=text_box_size)
		if platform.system() == "Darwin":
			self.text.MacCheckSpelling(True)
		self.main_box.Add(self.text, 0, wx.ALL, 10)
		self.text.SetFocus()
		self.text.Bind(wx.EVT_TEXT, self.Chars)
		if self.type != "message":
			self.text.AppendText(inittext)
			cursorpos = len(inittext)
		else:
			cursorpos = 0
		if self.type == "message":
			self.max_length = 10000
		else:
			# Get character limit from account
			self.max_length = getattr(self.account, 'max_chars', 500)
		if self.type == "message":
			self.text2_label = wx.StaticText(self.panel, -1, "Recipient")
		if self.type == "reply" or self.type == "quote" or self.type == "message":
			if self.type == "message":
				self.text2 = wx.TextCtrl(self.panel, -1, "", style=wx.TE_DONTWRAP, size=text_box_size)
			else:
				self.text2 = wx.TextCtrl(self.panel, -1, "", style=wx.TE_MULTILINE|wx.TE_DONTWRAP|wx.TE_READONLY, size=text_box_size)
			self.main_box.Add(self.text2, 0, wx.ALL, 10)
			if self.type == "message":
				self.text2.AppendText(inittext)
			else:
				# Use Mastodon field names
				display_name = getattr(status.account, 'display_name', '') or status.account.acct
				status_text = getattr(status, 'text', self.account.app.strip_html(getattr(status, 'content', '')))
				self.text2.AppendText(display_name + ": " + status_text)
		if self.account.prefs.footer != "":
			self.text.AppendText(" " + self.account.prefs.footer)
		self.text.SetInsertionPoint(cursorpos)
		if self.type != "message":
			# Visibility settings - only show if platform supports it
			self.visibility = None
			if self._platform_supports('visibility'):
				self.visibility_label = wx.StaticText(self.panel, -1, "Visibility")
				self.visibility = wx.Choice(self.panel, -1, size=(800,600))
				self.visibility.Insert("Public", self.visibility.GetCount())
				self.visibility.Insert("Unlisted", self.visibility.GetCount())
				self.visibility.Insert("Followers Only", self.visibility.GetCount())
				self.visibility.Insert("Direct Message", self.visibility.GetCount())
				# Set default visibility
				default_vis = getattr(self.account, 'default_visibility', 'public')
				vis_map = {'public': 0, 'unlisted': 1, 'private': 2, 'direct': 3}
				self.visibility.SetSelection(vis_map.get(default_vis, 0))
				self.main_box.Add(self.visibility, 0, wx.ALL, 10)

			# Content warning / Spoiler text - only show if platform supports it
			self.cw_text = None
			if self._platform_supports('content_warning'):
				self.cw_label = wx.StaticText(self.panel, -1, "Content &Warning (optional)")
				self.cw_text = wx.TextCtrl(self.panel, -1, "", style=wx.TE_DONTWRAP, size=(800, 30))
				self.main_box.Add(self.cw_text, 0, wx.ALL, 10)

		if platform.system() == "Darwin":
			self.autocomplete = wx.Button(self.panel, wx.ID_DEFAULT, "User A&utocomplete")
		else:
			self.autocomplete = wx.Button(self.panel, wx.ID_DEFAULT, "User &Autocomplete")
		self.autocomplete.Bind(wx.EVT_BUTTON, self.Autocomplete)
		self.main_box.Add(self.autocomplete, 0, wx.ALL, 10)
		if self.type != "reply" and self.type != "message":
			# Poll button - only show if platform supports polls
			self.poll = None
			if self._platform_supports('polls'):
				self.poll = wx.Button(self.panel, wx.ID_DEFAULT, "Poll")
				self.poll.Bind(wx.EVT_BUTTON, self.Poll)
				self.main_box.Add(self.poll, 0, wx.ALL, 10)
		if self.type == "reply" and self.status is not None and hasattr(self.status, 'mentions') and len(self.status.mentions) > 0:
			self.users = self.account.app.get_user_objects_in_status(self.account, self.status, True, True)
			self.list_label = wx.StaticText(self.panel, -1, label="&Users to include in reply")
			self.list = wx.CheckListBox(self.panel, -1)
			self.main_box.Add(self.list, 0, wx.ALL, 10)
			for i in self.users:
				display_name = getattr(i, 'display_name', '') or i.acct
				self.list.Append(display_name + " (@" + i.acct + ")")
				self.list.Check(self.list.GetCount()-1, True)
				self.list.SetSelection(0)
				self.list.Bind(wx.EVT_CHECKLISTBOX, self.OnToggle)
		if self.type == "post" or self.type == "reply":
			self.thread = wx.CheckBox(self.panel, -1, "&Thread mode")
			self.main_box.Add(self.thread, 0, wx.ALL, 10)
		self.send_btn = wx.Button(self.panel, wx.ID_DEFAULT, "&Send")
		self.send_btn.Bind(wx.EVT_BUTTON, self.Tweet)
		self.main_box.Add(self.send_btn, 0, wx.ALL, 10)
		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)
		self.Chars(None)
		self.text.Bind(wx.EVT_CHAR, self.onKeyPress)
		self.panel.Layout()

	def _platform_supports(self, feature):
		"""Check if the current account's platform supports a feature."""
		if hasattr(self.account, 'supports_feature'):
			return self.account.supports_feature(feature)
		# Default to True for backward compatibility (Mastodon supports most features)
		return True

	def Poll(self, event):
		if not self._platform_supports('polls'):
			speak.speak("Polls are not supported on this platform")
			return False
		p = poll.PollGui()
		result = p.ShowModal()
		if result == wx.ID_CANCEL:
			return False
		self.poll_runfor = p.runfor.GetValue() * 60 * 24
		self.poll_opt1 = p.opt1.GetValue()
		self.poll_opt2 = p.opt2.GetValue()
		self.poll_opt3 = p.opt3.GetValue()
		self.poll_opt4 = p.opt4.GetValue()
		if self.poll:
			self.poll.Enable(False)

	def onKeyPress(self, event):
		mods = event.HasAnyModifiers()
		keycode = event.GetKeyCode()
		if keycode == wx.WXK_RETURN:
			if not mods:
				self.Tweet(None)
		event.Skip()

	def OnToggle(self, event):
		index = event.GetInt()
		if self.list.IsChecked(index):
			speak.speak("Checked")
		else:
			speak.speak("Unchecked.")

	def Autocomplete(self, event):
		if self.type == "message":
			txt = self.text2.GetValue().split(" ")
		else:
			txt = self.text.GetValue().split(" ")
		text = ""
		for i in txt:
			if (self.type != "message" and i.startswith("@") or self.type == "message") and self.account.app.lookup_user_name(self.account, i.strip("@"), False) == -1:
				text = i.strip("@")

		if text == "":
			speak.speak("No user to autocomplete")
			return
		self.menu = wx.Menu()
		for i in get_app().users:
			display_name = getattr(i, 'display_name', '') or i.acct
			if i.acct.lower().startswith(text.lower()) or display_name.lower().startswith(text.lower()):
				self.create_menu_item(self.menu, display_name + " (@" + i.acct + ")", lambda event, orig=text, text=i.acct: self.OnUser(event, orig, text))
		self.PopupMenu(self.menu)

	def Newline(self, event):
		if platform.system() == "Darwin":
			nl = "\n"
		else:
			nl = "\r\n"
		self.text.WriteText(nl)

	def create_menu_item(self, menu, label, func):
		item = wx.MenuItem(menu, -1, label)
		self.Bind(wx.EVT_MENU, func, id=item.GetId())
		menu.Append(item)
		return item

	def OnUser(self, event, orig, text):
		if self.type != "message":
			v = self.text.GetValue().replace(orig, text)
			self.text.SetValue(v)
			self.text.SetInsertionPoint(len(v))
		else:
			v = self.text2.GetValue().replace(orig, text)
			self.text2.SetValue(v)

	def next_thread(self):
		self.text.SetValue("")
		self.text.AppendText(self.inittext)
		cursorpos = len(self.inittext)
		if self.account.prefs.footer != "":
			self.text.AppendText(" " + self.account.prefs.footer)
		self.text.SetInsertionPoint(cursorpos)

	def maximum(self):
		sound.play(self.account, "max_length")

	def Chars(self, event):
		# Simple character count for Mastodon
		length = len(self.text.GetValue())
		if length > 0 and self.max_length > 0:
			percent = str(int((length / self.max_length) * 100))
		else:
			percent = "0"
		if self.max_length > 0 and length > self.max_length:
			self.maximum()
		self.SetLabel(self.type + " - " + str(length) + " of " + str(self.max_length) + " characters (" + percent + " Percent)")

	def Tweet(self, event):
		snd = ""
		status = False
		if self.type != "message":
			# Get visibility (only if platform supports it)
			visibility = 'public'  # Default
			if self.visibility is not None:
				vis_selection = self.visibility.GetSelection()
				vis_map = {0: 'public', 1: 'unlisted', 2: 'private', 3: 'direct'}
				visibility = vis_map.get(vis_selection, 'public')

			# Get content warning if any (only if platform supports it)
			spoiler_text = None
			if self.cw_text is not None and self.cw_text.GetValue().strip():
				spoiler_text = self.cw_text.GetValue().strip()

			self.account.app.prefs.posts_sent += 1
			try:
				if self.status is not None:
					if self.type == "quote":
						self.account.app.prefs.quotes_sent += 1
						status = self.account.quote(self.status, self.text.GetValue(), visibility=visibility)
					else:
						self.account.app.prefs.replies_sent += 1
						# Build mention string for excluded users
						exclude_mentions = []
						if hasattr(self, "list"):
							index = 0
							for i in self.users:
								if not self.list.IsChecked(index):
									exclude_mentions.append(i.acct)
								index += 1
						# Use original status ID if available (for mentions timeline)
						# or resolve remote status ID (for instance timelines)
						reply_to_id = getattr(self.status, '_original_status_id', None)
						if not reply_to_id:
							# Check if this is from an instance timeline
							if hasattr(self.status, '_instance_url'):
								# Need to resolve the remote status to a local ID
								print(f"Resolving instance timeline status for reply: {self.status._instance_url}")
								print(f"Status URL: {getattr(self.status, 'url', 'N/A')}")
								print(f"Status URI: {getattr(self.status, 'uri', 'N/A')}")
								reply_to_id = self.account._platform.resolve_remote_status(self.status)
								print(f"Resolved to local ID: {reply_to_id}")
							else:
								reply_to_id = self.status.id
						status = self.account.post(
							text=self.text.GetValue(),
							id=reply_to_id,
							visibility=visibility,
							spoiler_text=spoiler_text
						)
				else:
					# Check if poll is set and platform supports it
					if self.poll_opt1 is not None and self.poll_opt1 != "" and self._platform_supports('polls'):
						opts = []
						if self.poll_opt1 != "" and self.poll_opt1 is not None:
							opts.append(self.poll_opt1)
						if self.poll_opt2 != "" and self.poll_opt2 is not None:
							opts.append(self.poll_opt2)
						if self.poll_opt3 != "" and self.poll_opt3 is not None:
							opts.append(self.poll_opt3)
						if self.poll_opt4 != "" and self.poll_opt4 is not None:
							opts.append(self.poll_opt4)
						# Post with poll (Mastodon only)
						status = self.account.api.make_poll(
							options=opts,
							expires_in=self.poll_runfor * 60
						)
						status = self.account.api.status_post(
							status=self.text.GetValue(),
							visibility=visibility,
							spoiler_text=spoiler_text,
							poll=status
						)
					else:
						status = self.account.post(
							self.text.GetValue(),
							visibility=visibility,
							spoiler_text=spoiler_text
						)
				self.account.app.prefs.chars_sent += len(self.text.GetValue())
			except Exception as error:
				sound.play(self.account, "error")
				speak.speak(str(error))
				status = False
			except Exception as error:
				# Generic exception handler for other platform errors
				sound.play(self.account, "error")
				speak.speak("Error: " + str(error))
				status = False
		else:
			# Direct message - check if platform supports it
			if not self._platform_supports('direct_messages'):
				sound.play(self.account, "error")
				speak.speak("Direct messages are not supported on this platform")
				return
			user = self.account.app.lookup_user_name(self.account, self.text2.GetValue())
			if user != -1:
				try:
					# Mention the user and use direct visibility
					text = "@" + user.acct + " " + self.text.GetValue()
					status = self.account.api.status_post(
						status=text,
						visibility='direct'
					)
				except Exception as error:
					sound.play(self.account, "error")
					speak.speak(str(error))
					status = False
				except Exception as error:
					sound.play(self.account, "error")
					speak.speak("Error: " + str(error))
					status = False

		if self.type == "reply" or self.type == "quote":
			snd = "send_reply"
		elif self.type == "post":
			snd = "send_tweet"
		elif self.type == "message":
			snd = "send_message"
		if status:
			sound.play(self.account, snd)
			if hasattr(self, "thread") and not self.thread.GetValue() or not hasattr(self, "thread"):
				self.Destroy()
			else:
				self.status = status
				self.next_thread()
		else:
			sound.play(self.account, "error")

	def OnClose(self, event):
		self.Destroy()
