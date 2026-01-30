import speak
import wx
import wx.adv
import sound
import platform
import datetime
import os
from . import poll, theme
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
		self.poll_expires_in = None
		self.poll_multiple = False
		self.poll_hide_totals = False
		self.poll_opt1 = None
		self.poll_opt2 = None
		self.poll_opt3 = None
		self.poll_opt4 = None
		self.media_attachments = []  # List of {'path': str, 'description': str}
		self.scheduled_at = None  # For scheduled posts

		# For edit mode, get the original post text with newlines and full handles preserved
		if self.type == "edit" and status is not None:
			content = getattr(status, 'content', '')
			mentions = getattr(status, 'mentions', [])
			inittext = self.account.app.html_to_text_for_edit(content, mentions)

		wx.Dialog.__init__(self, None, title=type, size=(350,200), style=wx.DEFAULT_DIALOG_STYLE | wx.TAB_TRAVERSAL)
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		# Register with main window for focus restoration
		from . import main
		if hasattr(main, 'window') and main.window:
			main.window.register_dialog(self)
		self.panel = wx.Panel(self, style=wx.TAB_TRAVERSAL)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.text_label = wx.StaticText(self.panel, -1, "Te&xt")
		self.main_box.Add(self.text_label, 0, wx.LEFT | wx.TOP, 10)
		if self.account.app.prefs.wrap:
			self.text = wx.TextCtrl(self.panel, -1, "", style=wx.TE_MULTILINE, size=text_box_size, name="Post text")
		else:
			self.text = wx.TextCtrl(self.panel, -1, "", style=wx.TE_MULTILINE|wx.TE_DONTWRAP, size=text_box_size, name="Post text")
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
			self.main_box.Add(self.text2_label, 0, wx.LEFT | wx.TOP, 10)
		if self.type == "reply" or self.type == "quote" or self.type == "message":
			if self.type == "message":
				self.text2 = wx.TextCtrl(self.panel, -1, "", style=wx.TE_DONTWRAP, size=text_box_size, name="Recipient")
			else:
				self.text2 = wx.TextCtrl(self.panel, -1, "", style=wx.TE_MULTILINE|wx.TE_DONTWRAP|wx.TE_READONLY, size=text_box_size, name="Original post")
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
				self.main_box.Add(self.visibility_label, 0, wx.LEFT | wx.TOP, 10)
				self.visibility = wx.Choice(self.panel, -1, size=(800,600), name="Visibility")
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
				self.main_box.Add(self.cw_label, 0, wx.LEFT | wx.TOP, 10)
				self.cw_text = wx.TextCtrl(self.panel, -1, "", style=wx.TE_DONTWRAP, size=(800, 30), name="Content Warning (optional)")
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
				self.main_box.Add(self.media_label, 0, wx.LEFT | wx.TOP, 10)
				self.media_list = wx.ListBox(self.panel, -1, size=(800, 100), name="Media Attachments")
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
				self.schedule_date = wx.adv.DatePickerCtrl(self.schedule_panel, style=wx.adv.DP_DROPDOWN, name="Schedule date")
				schedule_sizer.Add(self.schedule_date, 0, wx.ALL, 5)

				# Hour spinner
				schedule_sizer.Add(wx.StaticText(self.schedule_panel, -1, "Hour:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
				self.schedule_hour = wx.SpinCtrl(self.schedule_panel, -1, "12", min=0, max=23, size=(60, -1), name="Schedule hour")
				schedule_sizer.Add(self.schedule_hour, 0, wx.ALL, 5)

				# Minute spinner
				schedule_sizer.Add(wx.StaticText(self.schedule_panel, -1, "Minute:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
				self.schedule_minute = wx.SpinCtrl(self.schedule_panel, -1, "0", min=0, max=59, size=(60, -1), name="Schedule minute")
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
		self.spell_btn = wx.Button(self.panel, wx.ID_DEFAULT, "Spell Chec&k")
		self.spell_btn.Bind(wx.EVT_BUTTON, self.OnSpellCheck)
		self.main_box.Add(self.spell_btn, 0, wx.ALL, 10)
		self.send_btn = wx.Button(self.panel, wx.ID_DEFAULT, "&Send")
		self.send_btn.Bind(wx.EVT_BUTTON, self.Tweet)
		self.main_box.Add(self.send_btn, 0, wx.ALL, 10)
		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)
		self.Chars(None)
		self.text.Bind(wx.EVT_KEY_DOWN, self.onKeyPress)
		self.panel.SetSizer(self.main_box)
		self.panel.Layout()

		# On macOS, explicitly set the navigation order for VoiceOver
		if platform.system() == "Darwin":
			self._set_macos_accessibility_order()

		# Use CallAfter on Mac to ensure focus is set after dialog is fully shown
		if platform.system() == "Darwin":
			wx.CallAfter(self.text.SetFocus)
		else:
			self.text.SetFocus()
		theme.apply_theme(self)

	def _set_macos_accessibility_order(self):
		"""Set explicit navigation order for VoiceOver on macOS."""
		# Build list of controls in the order we want them read
		controls = [self.text]

		# Add text2 if it exists (reply/quote/message)
		if hasattr(self, 'text2'):
			controls.append(self.text2)

		# Visibility
		if self.visibility is not None:
			controls.append(self.visibility)

		# Content warning
		if self.cw_text is not None:
			controls.append(self.cw_text)

		# Media section
		if self.media_list is not None:
			controls.append(self.media_list)
			controls.append(self.add_media_btn)
			controls.append(self.remove_media_btn)

		# Scheduling
		if self.schedule_checkbox is not None:
			controls.append(self.schedule_checkbox)

		# Action buttons
		controls.append(self.autocomplete)
		if hasattr(self, 'poll') and self.poll is not None:
			controls.append(self.poll)
		if hasattr(self, 'thread'):
			controls.append(self.thread)
		controls.append(self.spell_btn)
		controls.append(self.send_btn)
		controls.append(self.close)

		# Set the order using MoveAfterInTabOrder
		for i in range(1, len(controls)):
			controls[i].MoveAfterInTabOrder(controls[i-1])

	def _platform_supports(self, feature):
		"""Check if the current account's platform supports a feature."""
		if hasattr(self.account, 'supports_feature'):
			return self.account.supports_feature(feature)
		# Default to True for backward compatibility (Mastodon supports most features)
		return True

	def _get_enchant_dict(self):
		"""Get the enchant dictionary, returns None if not available."""
		try:
			import enchant
			# Try to get the system language, fall back to en_US
			import locale
			lang = locale.getdefaultlocale()[0]
			if lang and enchant.dict_exists(lang):
				return enchant.Dict(lang)
			elif enchant.dict_exists('en_US'):
				return enchant.Dict('en_US')
			elif enchant.dict_exists('en'):
				return enchant.Dict('en')
			return None
		except ImportError:
			return None
		except Exception:
			return None

	def OnSpellCheck(self, event):
		"""Perform spell check on the text."""
		d = self._get_enchant_dict()
		if not d:
			speak.speak("Spell check not available. Install enchant library.")
			return

		text = self.text.GetValue()
		if not text.strip():
			speak.speak("No text to check")
			return

		# Find misspelled words
		import re

		# First, remove URLs, @mentions, and #hashtags from the text for spell checking
		# Remove URLs (http://, https://, and www.)
		text_cleaned = re.sub(r'https?://\S+', '', text)
		text_cleaned = re.sub(r'www\.\S+', '', text_cleaned)
		# Remove @mentions
		text_cleaned = re.sub(r'@\w+', '', text_cleaned)
		# Remove #hashtags
		text_cleaned = re.sub(r'#\w+', '', text_cleaned)

		# Match words from the cleaned text
		words = re.findall(r'\b[a-zA-Z\']+\b', text_cleaned)
		misspelled = []
		checked = set()

		for word in words:
			word_lower = word.lower()
			if word_lower in checked:
				continue
			checked.add(word_lower)
			# Skip short words and contractions
			if len(word) < 2:
				continue
			if not d.check(word):
				misspelled.append(word)

		if not misspelled:
			speak.speak("No spelling errors found")
			return

		# Show spell check dialog
		dlg = SpellCheckDialog(self, d, misspelled, text)
		if dlg.ShowModal() == wx.ID_OK:
			self.text.SetValue(dlg.corrected_text)
		dlg.Destroy()

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

			# Ask for alt text - cancel here cancels the entire attachment
			alt_dialog = wx.Dialog(self, title="Alt Text", size=(400, 200))
			panel = wx.Panel(alt_dialog)
			sizer = wx.BoxSizer(wx.VERTICAL)
			label = wx.StaticText(panel, label="Enter alt text description (optional):")
			sizer.Add(label, 0, wx.ALL, 5)
			alt_text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(380, 100), name="Alt text")
			sizer.Add(alt_text_ctrl, 1, wx.EXPAND | wx.ALL, 5)
			btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
			ok_btn = wx.Button(panel, wx.ID_OK, "&OK")
			cancel_btn = wx.Button(panel, wx.ID_CANCEL, "&Cancel")
			btn_sizer.Add(ok_btn, 0, wx.ALL, 5)
			btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
			sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER)
			panel.SetSizer(sizer)
			alt_text_ctrl.SetFocus()
			result = alt_dialog.ShowModal()
			if result == wx.ID_CANCEL:
				alt_dialog.Destroy()
				speak.speak("Attachment cancelled")
				return
			alt_text = alt_text_ctrl.GetValue()
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
		self.poll_expires_in = p.get_expires_in()
		self.poll_multiple = p.get_multiple()
		self.poll_hide_totals = p.get_hide_totals()
		self.poll_opt1 = p.opt1.GetValue()
		self.poll_opt2 = p.opt2.GetValue()
		self.poll_opt3 = p.opt3.GetValue()
		self.poll_opt4 = p.opt4.GetValue()
		if self.poll:
			self.poll.Enable(False)

	def onKeyPress(self, event):
		keycode = event.GetKeyCode()
		if keycode == wx.WXK_RETURN:
			# Use Cmd on Mac, Ctrl on Windows/Linux
			ctrl_down = event.ControlDown()
			if self.account.app.prefs.ctrl_enter_to_send:
				# Ctrl+Enter (Cmd+Enter on Mac) to send mode
				if ctrl_down:
					self.Tweet(None)
					return
			else:
				# Enter to send mode (default)
				if not event.HasAnyModifiers():
					self.Tweet(None)
					return
		event.Skip()

	def Autocomplete(self, event):
		# Get the text control and current content
		if self.type == "message":
			text_ctrl = self.text2
		else:
			text_ctrl = self.text

		full_text = text_ctrl.GetValue()
		cursor_pos = text_ctrl.GetInsertionPoint()

		# Find the word at or before the cursor position
		# Look backwards from cursor to find word start
		word_start = cursor_pos
		while word_start > 0 and full_text[word_start - 1] not in ' \t\n\r':
			word_start -= 1

		# Look forwards from cursor to find word end
		word_end = cursor_pos
		while word_end < len(full_text) and full_text[word_end] not in ' \t\n\r':
			word_end += 1

		# Extract the word - must start with @ for autocomplete
		word = full_text[word_start:word_end]
		if not word.startswith('@'):
			speak.speak("Place cursor on a username starting with @ to autocomplete.")
			return

		search_text = word[1:]  # Remove the @

		if not search_text:
			speak.speak("Type a username after @ to autocomplete.")
			return

		# Store for replacement later
		self._autocomplete_start = word_start
		self._autocomplete_end = word_end

		# Collect matching users from cache and API
		matches = []
		seen_accts = set()

		# First check account's user cache
		if hasattr(self.account, '_platform') and self.account._platform:
			cache = self.account._platform.user_cache
			for user in cache.get_all_users():
				acct_lower = user.acct.lower()
				display_name = getattr(user, 'display_name', '') or ''
				# Match against username (with or without domain) and display name
				username_part = acct_lower.split('@')[0] if '@' in acct_lower else acct_lower
				if (acct_lower.startswith(search_text.lower()) or
					username_part.startswith(search_text.lower()) or
					display_name.lower().startswith(search_text.lower())):
					if acct_lower not in seen_accts:
						matches.append(user)
						seen_accts.add(acct_lower)

		# Also search the API for more suggestions (limit to keep it fast)
		if len(matches) < 10:
			try:
				api_results = self.account.search_users(search_text, limit=10)
				for user in api_results:
					acct_lower = user.acct.lower()
					if acct_lower not in seen_accts:
						matches.append(user)
						seen_accts.add(acct_lower)
			except:
				pass  # API search failed, just use cache results

		if not matches:
			speak.speak("No matching users found for " + search_text)
			return

		self.menu = wx.Menu()
		for user in matches[:15]:  # Limit to 15 results
			display_name = getattr(user, 'display_name', '') or user.acct
			self.create_menu_item(self.menu, display_name + " (@" + user.acct + ")", lambda event, acct=user.acct: self.OnAutocompleteUser(event, acct))
		self.PopupMenu(self.menu)

	def OnAutocompleteUser(self, event, acct):
		"""Handle autocomplete user selection."""
		if self.type == "message":
			text_ctrl = self.text2
		else:
			text_ctrl = self.text

		full_text = text_ctrl.GetValue()

		# Build replacement: add @ for non-message posts
		if self.type == "message":
			replacement = acct
		else:
			replacement = "@" + acct

		# Check if we need to add a space after (if next char isn't whitespace)
		after_text = full_text[self._autocomplete_end:]
		if after_text and after_text[0] not in ' \t\n\r':
			replacement += " "
		elif not after_text:
			# At end of text, add space for convenience
			replacement += " "

		# Replace the word with the selected username
		new_text = full_text[:self._autocomplete_start] + replacement + full_text[self._autocomplete_end:]
		text_ctrl.SetValue(new_text)

		# Move cursor to after the inserted username (and space)
		new_cursor = self._autocomplete_start + len(replacement)
		text_ctrl.SetInsertionPoint(new_cursor)

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
							expires_in=self.poll_expires_in,
							multiple=self.poll_multiple,
							hide_totals=self.poll_hide_totals
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

		if self.type == "message":
			snd = "send_message"
		elif self.type == "reply" or self.type == "quote":
			# Check if this is a direct message reply (visibility='direct')
			if self.visibility is not None and self.visibility.GetSelection() == 3:
				snd = "send_message"
			else:
				snd = "send_reply"
		elif self.type == "post" or self.type == "edit":
			# Check if this is a direct message (visibility='direct')
			if self.visibility is not None and self.visibility.GetSelection() == 3:
				snd = "send_message"
			else:
				snd = "send_post"
		if status:
			sound.play(self.account, snd)
			# Check if this was a scheduled post (only for non-message types)
			if self.type != "message" and scheduled_at:
				# Add to scheduled timeline if it exists
				for tl in self.account.timelines:
					if tl.type == "scheduled":
						tl.load(items=[status])
						break
			else:
				# Add the posted status to the Sent timeline immediately
				# (streaming only works on Mastodon, so Bluesky needs this)
				for tl in self.account.timelines:
					if tl.type == "user" and tl.name == "Sent":
						# Use load() to properly add and deduplicate
						tl.load(items=[status])
						break
			if hasattr(self, "thread") and not self.thread.GetValue() or not hasattr(self, "thread"):
				self.Destroy()
			else:
				self.status = status
				self.next_thread()
		else:
			sound.play(self.account, "error")
			speak.speak("Failed to send post")
			# Re-enable poll button on error so user can modify poll options
			if hasattr(self, 'poll') and self.poll is not None:
				self.poll.Enable(True)

	def OnClose(self, event):
		# Unregister from main window focus tracking
		from . import main
		if hasattr(main, 'window') and main.window:
			main.window.unregister_dialog(self)
		# On Mac, explicitly reactivate main window to fix menu state
		if platform.system() == "Darwin":
			def do_raise():
				main.safe_raise_window(main.window)
			wx.CallAfter(do_raise)
		self.Destroy()


class SpellCheckDialog(wx.Dialog):
	"""Dialog for spell checking text."""

	def __init__(self, parent, dictionary, misspelled, text):
		wx.Dialog.__init__(self, parent, title="Spell Check", size=(400, 300), style=wx.DEFAULT_DIALOG_STYLE | wx.TAB_TRAVERSAL)
		self.dictionary = dictionary
		self.misspelled = misspelled
		self.corrected_text = text
		self.current_index = 0

		self.panel = wx.Panel(self, style=wx.TAB_TRAVERSAL)
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		# Current word display
		self.word_label = wx.StaticText(self.panel, -1, "Misspelled word:")
		self.main_box.Add(self.word_label, 0, wx.ALL, 10)

		self.word_text = wx.TextCtrl(self.panel, -1, "", style=wx.TE_READONLY, name="Misspelled word")
		self.main_box.Add(self.word_text, 0, wx.EXPAND | wx.ALL, 10)

		# Replacement field
		self.replace_label = wx.StaticText(self.panel, -1, "&Replace with:")
		self.main_box.Add(self.replace_label, 0, wx.ALL, 10)

		self.replace_text = wx.TextCtrl(self.panel, -1, "", name="Replace with")
		self.main_box.Add(self.replace_text, 0, wx.EXPAND | wx.ALL, 10)

		# Suggestions list
		self.suggest_label = wx.StaticText(self.panel, -1, "&Suggestions:")
		self.main_box.Add(self.suggest_label, 0, wx.ALL, 10)

		self.suggestions = wx.ListBox(self.panel, -1, size=(350, 100), name="Suggestions")
		self.suggestions.Bind(wx.EVT_LISTBOX, self.OnSuggestionSelect)
		self.suggestions.Bind(wx.EVT_LISTBOX_DCLICK, self.OnReplace)
		self.main_box.Add(self.suggestions, 0, wx.EXPAND | wx.ALL, 10)

		# Buttons
		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

		self.replace_btn = wx.Button(self.panel, -1, "&Replace")
		self.replace_btn.Bind(wx.EVT_BUTTON, self.OnReplace)
		btn_sizer.Add(self.replace_btn, 0, wx.ALL, 5)

		self.replace_all_btn = wx.Button(self.panel, -1, "Replace &All")
		self.replace_all_btn.Bind(wx.EVT_BUTTON, self.OnReplaceAll)
		btn_sizer.Add(self.replace_all_btn, 0, wx.ALL, 5)

		self.ignore_btn = wx.Button(self.panel, -1, "&Ignore")
		self.ignore_btn.Bind(wx.EVT_BUTTON, self.OnIgnore)
		btn_sizer.Add(self.ignore_btn, 0, wx.ALL, 5)

		self.ignore_all_btn = wx.Button(self.panel, -1, "Ignore A&ll")
		self.ignore_all_btn.Bind(wx.EVT_BUTTON, self.OnIgnoreAll)
		btn_sizer.Add(self.ignore_all_btn, 0, wx.ALL, 5)

		self.main_box.Add(btn_sizer, 0, wx.ALL, 5)

		# Done/Cancel buttons
		done_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.done_btn = wx.Button(self.panel, wx.ID_OK, "&Done")
		done_sizer.Add(self.done_btn, 0, wx.ALL, 5)

		self.cancel_btn = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
		done_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)

		self.main_box.Add(done_sizer, 0, wx.ALL, 5)

		self.panel.SetSizer(self.main_box)
		self.panel.Layout()

		# Show first word
		self._show_current_word()
		theme.apply_theme(self)

	def _show_current_word(self):
		"""Display the current misspelled word and its suggestions."""
		if self.current_index >= len(self.misspelled):
			speak.speak("Spell check complete")
			self.EndModal(wx.ID_OK)
			return

		word = self.misspelled[self.current_index]
		self.word_text.SetValue(word)
		self.replace_text.SetValue(word)

		# Get suggestions
		self.suggestions.Clear()
		try:
			suggestions = self.dictionary.suggest(word)[:10]  # Limit to 10 suggestions
			for s in suggestions:
				self.suggestions.Append(s)
			if suggestions:
				self.suggestions.SetSelection(0)
				self.replace_text.SetValue(suggestions[0])
		except:
			pass

		# Announce
		remaining = len(self.misspelled) - self.current_index
		speak.speak(f"{word}, {remaining} remaining")
		self.replace_text.SetFocus()

	def OnSuggestionSelect(self, event):
		"""Copy selected suggestion to replace field."""
		selection = self.suggestions.GetSelection()
		if selection != wx.NOT_FOUND:
			self.replace_text.SetValue(self.suggestions.GetString(selection))

	def OnReplace(self, event):
		"""Replace current word and move to next."""
		old_word = self.misspelled[self.current_index]
		new_word = self.replace_text.GetValue()
		if new_word:
			# Replace first occurrence only
			import re
			self.corrected_text = re.sub(r'\b' + re.escape(old_word) + r'\b', new_word, self.corrected_text, count=1)
		self.current_index += 1
		self._show_current_word()

	def OnReplaceAll(self, event):
		"""Replace all occurrences of current word."""
		old_word = self.misspelled[self.current_index]
		new_word = self.replace_text.GetValue()
		if new_word:
			import re
			self.corrected_text = re.sub(r'\b' + re.escape(old_word) + r'\b', new_word, self.corrected_text)
		self.current_index += 1
		self._show_current_word()

	def OnIgnore(self, event):
		"""Skip current word."""
		self.current_index += 1
		self._show_current_word()

	def OnIgnoreAll(self, event):
		"""Skip all occurrences of current word."""
		# Remove all instances of this word from misspelled list
		word = self.misspelled[self.current_index]
		self.misspelled = [w for w in self.misspelled if w.lower() != word.lower()]
		# Don't increment index since we removed items
		self._show_current_word()
