import speak
import wx
import wx.adv
import sound
import platform
import datetime
import os
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
		self.media_attachments = []  # List of {'path': str, 'description': str}
		self.scheduled_at = None  # For scheduled posts

		# For edit mode, get the original post text
		if self.type == "edit" and status is not None:
			inittext = getattr(status, 'text', self.account.app.strip_html(getattr(status, 'content', '')))

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
				# For replies/edits, use the original post's visibility; otherwise use default
				if (self.type == "reply" or self.type == "edit") and status is not None:
					orig_vis = getattr(status, 'visibility', None)
					if orig_vis:
						vis_map = {'public': 0, 'unlisted': 1, 'private': 2, 'direct': 3}
						self.visibility.SetSelection(vis_map.get(orig_vis, 0))
					else:
						default_vis = getattr(self.account, 'default_visibility', 'public')
						vis_map = {'public': 0, 'unlisted': 1, 'private': 2, 'direct': 3}
						self.visibility.SetSelection(vis_map.get(default_vis, 0))
				else:
					default_vis = getattr(self.account, 'default_visibility', 'public')
					vis_map = {'public': 0, 'unlisted': 1, 'private': 2, 'direct': 3}
					self.visibility.SetSelection(vis_map.get(default_vis, 0))
				self.main_box.Add(self.visibility, 0, wx.ALL, 10)

			# Content warning / Spoiler text - only show if platform supports it
			self.cw_text = None
			if self._platform_supports('content_warning'):
				self.cw_label = wx.StaticText(self.panel, -1, "Content &Warning (optional)")
				self.cw_text = wx.TextCtrl(self.panel, -1, "", style=wx.TE_DONTWRAP, size=(800, 30))
				# For replies/edits, copy the original post's content warning if present
				if (self.type == "reply" or self.type == "edit") and status is not None:
					orig_cw = getattr(status, 'spoiler_text', None)
					if orig_cw:
						self.cw_text.SetValue(orig_cw)
				self.main_box.Add(self.cw_text, 0, wx.ALL, 10)

			# Media attachments - only show if platform supports it
			self.media_list = None
			if self._platform_supports('media_attachments'):
				self.media_label = wx.StaticText(self.panel, -1, "&Media Attachments")
				self.media_list = wx.ListBox(self.panel, -1, size=(800, 100))
				self.main_box.Add(self.media_list, 0, wx.ALL, 10)

				media_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
				self.add_media_btn = wx.Button(self.panel, -1, "Add &Media")
				self.add_media_btn.Bind(wx.EVT_BUTTON, self.OnAddMedia)
				media_btn_sizer.Add(self.add_media_btn, 0, wx.ALL, 5)

				self.remove_media_btn = wx.Button(self.panel, -1, "Remove Media")
				self.remove_media_btn.Bind(wx.EVT_BUTTON, self.OnRemoveMedia)
				self.remove_media_btn.Enable(False)
				media_btn_sizer.Add(self.remove_media_btn, 0, wx.ALL, 5)
				self.main_box.Add(media_btn_sizer, 0, wx.ALL, 5)

				self.media_list.Bind(wx.EVT_LISTBOX, self.OnMediaSelect)

			# Scheduling - only show if platform supports it
			self.schedule_checkbox = None
			if self._platform_supports('scheduling'):
				self.schedule_checkbox = wx.CheckBox(self.panel, -1, "Sc&hedule post")
				self.schedule_checkbox.Bind(wx.EVT_CHECKBOX, self.OnScheduleToggle)
				self.main_box.Add(self.schedule_checkbox, 0, wx.ALL, 10)

				# Date and time controls (initially hidden)
				self.schedule_panel = wx.Panel(self.panel)
				schedule_sizer = wx.BoxSizer(wx.HORIZONTAL)

				# Date picker - label must be created before control for accessibility
				schedule_sizer.Add(wx.StaticText(self.schedule_panel, -1, "Date:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
				self.schedule_date = wx.adv.DatePickerCtrl(self.schedule_panel, style=wx.adv.DP_DROPDOWN)
				schedule_sizer.Add(self.schedule_date, 0, wx.ALL, 5)

				# Hour spinner
				schedule_sizer.Add(wx.StaticText(self.schedule_panel, -1, "Hour:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
				self.schedule_hour = wx.SpinCtrl(self.schedule_panel, -1, "12", min=0, max=23, size=(60, -1))
				schedule_sizer.Add(self.schedule_hour, 0, wx.ALL, 5)

				# Minute spinner
				schedule_sizer.Add(wx.StaticText(self.schedule_panel, -1, "Minute:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
				self.schedule_minute = wx.SpinCtrl(self.schedule_panel, -1, "0", min=0, max=59, size=(60, -1))
				schedule_sizer.Add(self.schedule_minute, 0, wx.ALL, 5)

				self.schedule_panel.SetSizer(schedule_sizer)
				self.schedule_panel.Hide()
				self.main_box.Add(self.schedule_panel, 0, wx.ALL, 5)

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
		self.text.SetFocus()

	def _platform_supports(self, feature):
		"""Check if the current account's platform supports a feature."""
		if hasattr(self.account, 'supports_feature'):
			return self.account.supports_feature(feature)
		# Default to True for backward compatibility (Mastodon supports most features)
		return True

	def OnAddMedia(self, event):
		"""Add a media attachment with alt text."""
		# Get max attachments from account, default to 4
		max_attachments = getattr(self.account, 'max_media_attachments', 4)
		if len(self.media_attachments) >= max_attachments:
			speak.speak(f"Maximum of {max_attachments} attachments allowed")
			return

		# Open file picker
		wildcard = "Image files (*.jpg;*.jpeg;*.png;*.gif;*.webp)|*.jpg;*.jpeg;*.png;*.gif;*.webp|Video files (*.mp4;*.webm;*.mov)|*.mp4;*.webm;*.mov|Audio files (*.mp3;*.ogg;*.wav;*.flac)|*.mp3;*.ogg;*.wav;*.flac|All files (*.*)|*.*"
		dialog = wx.FileDialog(self, "Select media file", wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)

		if dialog.ShowModal() == wx.ID_OK:
			file_path = dialog.GetPath()
			dialog.Destroy()

			# Ask for alt text
			alt_dialog = wx.TextEntryDialog(self, "Enter alt text description (optional):", "Alt Text", "")
			alt_text = ""
			if alt_dialog.ShowModal() == wx.ID_OK:
				alt_text = alt_dialog.GetValue()
			alt_dialog.Destroy()

			# Add to list
			filename = os.path.basename(file_path)
			display_text = filename
			if alt_text:
				display_text = f"{filename} - {alt_text[:30]}..."
			self.media_attachments.append({'path': file_path, 'description': alt_text})
			self.media_list.Append(display_text)
			speak.speak(f"Added {filename}")
		else:
			dialog.Destroy()

	def OnRemoveMedia(self, event):
		"""Remove the selected media attachment."""
		selection = self.media_list.GetSelection()
		if selection != wx.NOT_FOUND:
			removed = self.media_attachments.pop(selection)
			self.media_list.Delete(selection)
			speak.speak(f"Removed {os.path.basename(removed['path'])}")
			self.remove_media_btn.Enable(False)

	def OnMediaSelect(self, event):
		"""Enable/disable remove button based on selection."""
		self.remove_media_btn.Enable(self.media_list.GetSelection() != wx.NOT_FOUND)

	def OnScheduleToggle(self, event):
		"""Show/hide scheduling controls."""
		if self.schedule_checkbox.GetValue():
			self.schedule_panel.Show()
			# Set default time to 1 hour from now
			now = datetime.datetime.now()
			future = now + datetime.timedelta(hours=1)
			self.schedule_hour.SetValue(future.hour)
			self.schedule_minute.SetValue(future.minute)
		else:
			self.schedule_panel.Hide()
		self.panel.Layout()
		self.Fit()

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

	def _upload_media(self):
		"""Upload media attachments and return list of media IDs."""
		import time
		media_ids = []
		if not self.media_attachments:
			return media_ids

		for attachment in self.media_attachments:
			try:
				filename = os.path.basename(attachment['path'])
				speak.speak(f"Uploading {filename}...")
				media = self.account.api.media_post(
					media_file=attachment['path'],
					description=attachment['description'] if attachment['description'] else None
				)

				# Wait for media processing to complete
				# Media is processed async - url is None until ready
				max_wait = 60  # Maximum 60 seconds wait
				waited = 0
				while media.get('url') is None and waited < max_wait:
					time.sleep(1)
					waited += 1
					# Refresh media status
					try:
						media = self.account.api.media(media['id'])
					except:
						pass  # Keep using existing media dict
					if waited % 5 == 0:
						speak.speak(f"Processing {filename}...")

				if media.get('url') is None and waited >= max_wait:
					speak.speak(f"Timed out waiting for {filename} to process")
					return None

				media_ids.append(media['id'])
			except Exception as e:
				speak.speak(f"Failed to upload {os.path.basename(attachment['path'])}: {str(e)}")
				return None  # Return None to indicate failure
		return media_ids

	def _get_scheduled_time(self):
		"""Get the scheduled datetime if scheduling is enabled."""
		if self.schedule_checkbox is None or not self.schedule_checkbox.GetValue():
			return None

		# Get date from date picker
		wx_date = self.schedule_date.GetValue()
		year = wx_date.GetYear()
		month = wx_date.GetMonth() + 1  # wx months are 0-indexed
		day = wx_date.GetDay()

		# Get time from spinners
		hour = self.schedule_hour.GetValue()
		minute = self.schedule_minute.GetValue()

		# Create local datetime
		scheduled_local = datetime.datetime(year, month, day, hour, minute)

		# Check if scheduled time is in the future (with some buffer for processing)
		if scheduled_local <= datetime.datetime.now() + datetime.timedelta(minutes=5):
			speak.speak("Scheduled time must be at least 5 minutes in the future")
			return False  # Return False to indicate invalid time

		# Convert to UTC for the API
		# Get local timezone offset and convert to UTC
		local_tz = datetime.datetime.now().astimezone().tzinfo
		scheduled_aware = scheduled_local.replace(tzinfo=local_tz)
		scheduled_utc = scheduled_aware.astimezone(datetime.timezone.utc)

		return scheduled_utc

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

			# Upload media attachments if any
			media_ids = None
			if self.media_list is not None and self.media_attachments:
				media_ids = self._upload_media()
				if media_ids is None:
					# Upload failed
					sound.play(self.account, "error")
					return

			# Get scheduled time if enabled
			scheduled_at = self._get_scheduled_time()
			if scheduled_at is False:
				# Invalid scheduled time
				return

			self.account.app.prefs.posts_sent += 1
			try:
				if self.status is not None:
					if self.type == "edit":
						# Edit existing post
						status = self.account.edit(
							status_id=self.status.id,
							text=self.text.GetValue(),
							visibility=visibility,
							spoiler_text=spoiler_text,
							media_ids=media_ids
						)
					elif self.type == "quote":
						self.account.app.prefs.quotes_sent += 1
						status = self.account.quote(self.status, self.text.GetValue(), visibility=visibility)
					else:
						self.account.app.prefs.replies_sent += 1
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
							spoiler_text=spoiler_text,
							media_ids=media_ids,
							scheduled_at=scheduled_at
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
						poll_obj = self.account.api.make_poll(
							options=opts,
							expires_in=self.poll_runfor * 60
						)
						status = self.account.api.status_post(
							status=self.text.GetValue(),
							visibility=visibility,
							spoiler_text=spoiler_text,
							poll=poll_obj,
							media_ids=media_ids,
							scheduled_at=scheduled_at
						)
					else:
						status = self.account.post(
							self.text.GetValue(),
							visibility=visibility,
							spoiler_text=spoiler_text,
							media_ids=media_ids,
							scheduled_at=scheduled_at
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
		elif self.type == "post" or self.type == "edit":
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
			speak.speak("Failed to send post")

	def OnClose(self, event):
		# On Mac, explicitly reactivate main window to fix menu state
		if platform.system() == "Darwin":
			from . import main
			wx.CallAfter(main.window.Raise)
		self.Destroy()
