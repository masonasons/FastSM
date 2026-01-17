import requests
import platform
from application import get_app
from . import misc, theme
import wx
import sound
text_box_size=(800,600)

class ViewGui(wx.Dialog):

	def __init__(self, account, status):
		self.account = account
		self.status = status
		self.type = "post"

		# Get display name for title - handle boosts specially
		display_name = getattr(status.account, 'display_name', '') or status.account.acct

		# Check if this is a boost/reblog
		is_boost = hasattr(status, 'reblog') and status.reblog is not None
		if is_boost:
			orig_author = getattr(status.reblog, 'account', None)
			if orig_author:
				orig_display = getattr(orig_author, 'display_name', '') or getattr(orig_author, 'acct', 'Unknown')
				title = f"Boost by {display_name} of {orig_display}'s post"
			else:
				title = f"Boost by {display_name}"
		else:
			title = f"View Post from {display_name} (@{status.account.acct})"

		try:
			# Fetch full status details using platform backend
			fetched_status = None
			# For reposts, try to get the reblogged post's details
			status_id = status.id
			if hasattr(status, 'reblog') and status.reblog:
				status_id = status.reblog.id
			# Remove :repost suffix if present (Bluesky)
			if isinstance(status_id, str) and ':repost' in status_id:
				status_id = status_id.replace(':repost', '')

			if hasattr(account, '_platform') and account._platform:
				fetched_status = account._platform.get_status(status_id)
			else:
				fetched_status = account.api.status(id=status_id)

			# Use fetched status if available, otherwise use original
			if fetched_status:
				self.status = fetched_status
			# else keep self.status as the original
		except Exception:
			# Failed to fetch, use original status
			pass

		# Always show full text in view dialog, ignoring CW preference
		# Use html_to_text_for_edit for proper newline preservation
		content = getattr(self.status, 'content', '')
		mentions = getattr(self.status, 'mentions', [])
		self.post_text = self.account.app.html_to_text_for_edit(content, mentions)

		# Update display_name to match the current self.status.account (may have changed for boosts)
		display_name = getattr(self.status.account, 'display_name', '') or self.status.account.acct

		wx.Dialog.__init__(self, None, title=title, size=(350, 200))

		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		self.text_label = wx.StaticText(self.panel, -1, "Te&xt")
		self.main_box.Add(self.text_label, 0, wx.LEFT | wx.TOP, 10)
		if self.account.app.prefs.wrap:
			self.text = wx.TextCtrl(self.panel, style=wx.TE_READONLY|wx.TE_MULTILINE, size=text_box_size, name="Post text")
		else:
			self.text = wx.TextCtrl(self.panel, style=wx.TE_READONLY|wx.TE_MULTILINE|wx.TE_DONTWRAP, size=text_box_size, name="Post text")
		self.main_box.Add(self.text, 0, wx.EXPAND | wx.ALL, 10)
		self.text.SetFocus()
		self.text.SetValue(self.post_text)

		self.text2_label = wx.StaticText(self.panel, -1, "Post &Details")
		self.main_box.Add(self.text2_label, 0, wx.LEFT | wx.TOP, 10)
		self.text2 = wx.TextCtrl(self.panel, style=wx.TE_READONLY|wx.TE_MULTILINE|wx.TE_DONTWRAP, size=text_box_size, name="Post Details")
		self.main_box.Add(self.text2, 0, wx.EXPAND | wx.ALL, 10)

		extra = ""
		# Handle media attachments
		if hasattr(self.status, 'media_attachments') and self.status.media_attachments:
			for media in self.status.media_attachments:
				media_type = getattr(media, 'type', 'unknown') or 'media'
				# Capitalize media type nicely (image -> Image, gifv -> GIF, video -> Video)
				type_display = media_type.upper() if media_type == 'gifv' else media_type.capitalize()
				description = getattr(media, 'description', None) or getattr(media, 'alt', None)
				if description:
					extra += f"({type_display}) description: {description}\r\n"
				else:
					extra += f"({type_display}) with no description\r\n"

		# Content warning / spoiler text
		spoiler = getattr(self.status, 'spoiler_text', '')
		if spoiler:
			extra += "Content Warning: " + spoiler + "\r\n"

		# Visibility (Bluesky doesn't have visibility, so it may be None)
		visibility = getattr(self.status, 'visibility', None) or 'public'
		extra += "Visibility: " + str(visibility) + "\r\n"

		# Application/source
		app = getattr(self.status, 'application', None)
		source = app.get('name', 'Unknown') if app and isinstance(app, dict) else (getattr(app, 'name', 'Unknown') if app else 'Unknown')

		# Get created_at safely
		created_at = getattr(self.status, 'created_at', None)
		posted_str = self.account.app.parse_date(created_at) if created_at else 'Unknown'

		details = extra + "Posted: " + posted_str + "\r\nFrom: " + source + "\r\nFavourited " + str(getattr(self.status, 'favourites_count', 0) or 0) + " times\r\nBoosted " + str(getattr(self.status, 'boosts_count', 0) or getattr(self.status, 'reblogs_count', 0) or 0) + " times."
		self.text2.SetValue(details)

		if platform.system() == "Darwin":
			self.text2.SetValue(self.text2.GetValue().replace("\r", ""))

		self.view_orig = wx.Button(self.panel, -1, "&Original post")
		self.view_orig.Bind(wx.EVT_BUTTON, self.OnViewOrig)
		self.main_box.Add(self.view_orig, 0, wx.ALL, 10)

		self.view_boosters = wx.Button(self.panel, -1, "&View Boosters")
		self.view_boosters.Bind(wx.EVT_BUTTON, self.OnViewBoosters)
		self.main_box.Add(self.view_boosters, 0, wx.ALL, 10)

		if getattr(self.status, 'reblogs_count', 0) == 0:
			self.view_boosters.Enable(False)

		# Check if this is a boost or quote
		has_reblog = hasattr(self.status, 'reblog') and self.status.reblog
		has_quote = hasattr(self.status, 'quote') and self.status.quote
		if not has_reblog and not has_quote:
			self.view_orig.Enable(False)

		self.view_image = wx.Button(self.panel, -1, "&View Image")
		self.view_image.Bind(wx.EVT_BUTTON, self.OnViewImage)
		self.main_box.Add(self.view_image, 0, wx.ALL, 10)

		# Only enable View Image button if there are image attachments
		has_images = False
		if hasattr(self.status, 'media_attachments') and self.status.media_attachments:
			for attachment in self.status.media_attachments:
				media_type = getattr(attachment, 'type', '') or ''
				if media_type.lower() == 'image':
					has_images = True
					break
		if not has_images:
			self.view_image.Enable(False)

		self.reply = wx.Button(self.panel, -1, "&Reply")
		self.reply.Bind(wx.EVT_BUTTON, self.OnReply)
		self.main_box.Add(self.reply, 0, wx.ALL, 10)

		self.boost = wx.Button(self.panel, -1, "&Boost")
		self.boost.Bind(wx.EVT_BUTTON, self.OnBoost)
		self.main_box.Add(self.boost, 0, wx.ALL, 10)

		self.favourite = wx.Button(self.panel, -1, "&Favourite")
		self.favourite.Bind(wx.EVT_BUTTON, self.OnFavourite)
		self.main_box.Add(self.favourite, 0, wx.ALL, 10)

		users_in_status = self.account.app.get_user_objects_in_status(self.account, self.status, True, True)
		if len(users_in_status) > 0:
			self.profile = wx.Button(self.panel, -1, "View &Profile of " + display_name + " and " + str(len(users_in_status)) + " more")
		else:
			self.profile = wx.Button(self.panel, -1, "View &Profile of " + display_name)

		self.message = wx.Button(self.panel, -1, "&Message " + display_name)
		self.message.Bind(wx.EVT_BUTTON, self.OnMessage)
		self.main_box.Add(self.message, 0, wx.ALL, 10)

		self.profile.Bind(wx.EVT_BUTTON, self.OnProfile)
		self.main_box.Add(self.profile, 0, wx.ALL, 10)

		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)

		# Keyboard shortcuts
		menu = wx.Menu()
		m_like = menu.Append(-1, "Like")
		m_unlike = menu.Append(-1, "Unlike")
		self.Bind(wx.EVT_MENU, self.OnLike, m_like)
		self.Bind(wx.EVT_MENU, self.OnUnlike, m_unlike)
		accel = [
			(wx.ACCEL_CTRL, ord('K'), m_like.GetId()),
			(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('K'), m_unlike.GetId()),
		]
		accel_tbl = wx.AcceleratorTable(accel)
		self.SetAcceleratorTable(accel_tbl)

		self.panel.SetSizer(self.main_box)
		self.panel.Layout()
		theme.apply_theme(self)

	def OnLike(self, event):
		"""Like/favourite the post."""
		import speak
		try:
			status_id = misc.get_interaction_id(self.account, self.status)
			if not getattr(self.status, 'favourited', False):
				self.account.favourite(status_id)
				self.account.app.prefs.favourites_sent += 1
				self.status.favourited = True
				sound.play(self.account, "like")
			else:
				speak.speak("Already liked")
		except Exception as error:
			self.account.app.handle_error(error, "like post")

	def OnUnlike(self, event):
		"""Unlike/unfavourite the post."""
		import speak
		try:
			status_id = misc.get_interaction_id(self.account, self.status)
			if getattr(self.status, 'favourited', False):
				self.account.unfavourite(status_id)
				self.status.favourited = False
				sound.play(self.account, "unlike")
			else:
				speak.speak("Not liked")
		except Exception as error:
			self.account.app.handle_error(error, "unlike post")

	def OnViewOrig(self, event):
		if hasattr(self.status, 'reblog') and self.status.reblog:
			v = ViewGui(self.account, self.status.reblog)
			v.Show()
		elif hasattr(self.status, 'quote') and self.status.quote:
			v = ViewGui(self.account, self.status.quote)
			v.Show()

	def OnViewImage(self, event):
		v = ViewImageGui(self.status)
		v.Show()

	def OnReply(self, event):
		misc.reply(self.account, self.status)

	def OnBoost(self, event):
		misc.boost(self.account, self.status)

	def OnViewBoosters(self, event):
		users = []
		try:
			status_id = self.status.id
			if hasattr(self.status, 'reblog') and self.status.reblog:
				status_id = self.status.reblog.id
			boosters = self.account.api.status_reblogged_by(id=status_id)
			users = list(boosters)
		except Exception as error:
			self.account.app.handle_error(error)
			return
		g = UserViewGui(self.account, users, "Boosters")
		g.Show()

	def OnFavourite(self, event):
		misc.favourite(self.account, self.status)

	def OnProfile(self, event):
		u = [self.status.account]
		u2 = self.account.app.get_user_objects_in_status(self.account, self.status, True, True)
		for i in u2:
			u.append(i)
		g = UserViewGui(self.account, u)
		g.Show()

	def OnMessage(self, event):
		misc.message(self.account, self.status)

	def OnClose(self, event):
		self.Destroy()


class UserViewGui(wx.Dialog):

	def __init__(self, account, users=[], title="User Viewer"):
		self.account = account
		self.index = 0
		self.users = users
		wx.Dialog.__init__(self, None, title=title, size=(350, 200))
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.list_label = wx.StaticText(self.panel, -1, label="&Users")
		self.main_box.Add(self.list_label, 0, wx.LEFT | wx.TOP, 10)
		self.list = wx.ListBox(self.panel, -1, name="Users")
		self.main_box.Add(self.list, 0, wx.EXPAND | wx.ALL, 10)
		self.list.Bind(wx.EVT_LISTBOX, self.on_list_change)

		for i in self.users:
			extra = ""
			if getattr(i, 'locked', False):
				extra += ", Protected"
			# Note: Mastodon doesn't provide 'following' in basic account objects
			# We'll need to check relationship separately if needed
			note = getattr(i, 'note', '')
			if note:
				# Strip HTML from bio
				note = self.account.app.strip_html(note)
				if note:
					extra += ", " + note[:100]  # Truncate long bios
			display_name = getattr(i, 'display_name', '') or i.acct
			self.list.Insert(display_name + " (@" + i.acct + ")" + extra, self.list.GetCount())

		self.index = 0
		self.list.SetSelection(self.index)
		if len(self.users) == 1:
			self.list.Show(False)
		else:
			self.list.SetFocus()

		self.text_label = wx.StaticText(self.panel, -1, "Info")
		self.main_box.Add(self.text_label, 0, wx.LEFT | wx.TOP, 10)
		self.text = wx.TextCtrl(self.panel, style=wx.TE_READONLY|wx.TE_MULTILINE|wx.TE_DONTWRAP, size=text_box_size, name="User Info")
		self.main_box.Add(self.text, 0, wx.EXPAND | wx.ALL, 10)
		if len(self.users) == 1:
			self.text.SetFocus()

		self.follow = wx.Button(self.panel, -1, "&Follow")
		self.follow.Bind(wx.EVT_BUTTON, self.OnFollow)
		self.main_box.Add(self.follow, 0, wx.ALL, 10)

		self.unfollow = wx.Button(self.panel, -1, "&Unfollow")
		self.unfollow.Bind(wx.EVT_BUTTON, self.OnUnfollow)
		self.main_box.Add(self.unfollow, 0, wx.ALL, 10)

		self.mute = wx.Button(self.panel, -1, "M&ute")
		self.mute.Bind(wx.EVT_BUTTON, self.OnMute)
		self.main_box.Add(self.mute, 0, wx.ALL, 10)

		self.unmute = wx.Button(self.panel, -1, "Un&mute")
		self.unmute.Bind(wx.EVT_BUTTON, self.OnUnmute)
		self.main_box.Add(self.unmute, 0, wx.ALL, 10)

		self.block = wx.Button(self.panel, -1, "&Block")
		self.block.Bind(wx.EVT_BUTTON, self.OnBlock)
		self.main_box.Add(self.block, 0, wx.ALL, 10)

		self.unblock = wx.Button(self.panel, -1, "Unbloc&k")
		self.unblock.Bind(wx.EVT_BUTTON, self.OnUnblock)
		self.main_box.Add(self.unblock, 0, wx.ALL, 10)

		# Show/Hide boosts buttons (Mastodon only)
		platform_type = getattr(account.prefs, 'platform_type', 'mastodon')
		if platform_type == 'mastodon':
			self.show_boosts = wx.Button(self.panel, -1, "Show B&oosts")
			self.show_boosts.Bind(wx.EVT_BUTTON, self.OnShowBoosts)
			self.main_box.Add(self.show_boosts, 0, wx.ALL, 10)

			self.hide_boosts = wx.Button(self.panel, -1, "&Hide Boosts")
			self.hide_boosts.Bind(wx.EVT_BUTTON, self.OnHideBoosts)
			self.main_box.Add(self.hide_boosts, 0, wx.ALL, 10)

			self.enable_notifs = wx.Button(self.panel, -1, "Enable &Notifications")
			self.enable_notifs.Bind(wx.EVT_BUTTON, self.OnEnableNotifications)
			self.main_box.Add(self.enable_notifs, 0, wx.ALL, 10)

			self.disable_notifs = wx.Button(self.panel, -1, "&Disable Notifications")
			self.disable_notifs.Bind(wx.EVT_BUTTON, self.OnDisableNotifications)
			self.main_box.Add(self.disable_notifs, 0, wx.ALL, 10)

			self.show_boosts.Enable(False)
			self.hide_boosts.Enable(False)
			self.enable_notifs.Enable(False)
			self.disable_notifs.Enable(False)
		else:
			self.show_boosts = None
			self.hide_boosts = None
			self.enable_notifs = None
			self.disable_notifs = None

		self.message = wx.Button(self.panel, -1, "&Message")
		self.message.Bind(wx.EVT_BUTTON, self.OnMessage)
		self.main_box.Add(self.message, 0, wx.ALL, 10)

		self.timeline = wx.Button(self.panel, -1, "&Timeline")
		self.timeline.Bind(wx.EVT_BUTTON, self.OnTimeline)
		self.main_box.Add(self.timeline, 0, wx.ALL, 10)

		self.image = wx.Button(self.panel, -1, "View Profile Ima&ge")
		self.image.Bind(wx.EVT_BUTTON, self.OnImage)
		self.main_box.Add(self.image, 0, wx.ALL, 10)

		self.followers = wx.Button(self.panel, -1, "View Fo&llowers")
		self.followers.Bind(wx.EVT_BUTTON, self.OnFollowers)
		self.main_box.Add(self.followers, 0, wx.ALL, 10)

		self.following_btn = wx.Button(self.panel, -1, "View F&ollowing")
		self.following_btn.Bind(wx.EVT_BUTTON, self.OnFollowing)
		self.main_box.Add(self.following_btn, 0, wx.ALL, 10)

		self.follow.Enable(False)
		self.unfollow.Enable(False)
		self.mute.Enable(False)
		self.unmute.Enable(False)
		self.block.Enable(False)
		self.unblock.Enable(False)
		self.timeline.Enable(False)
		self.message.Enable(False)

		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)

		self.on_list_change(None)

		menu = wx.Menu()
		m_speak_user = menu.Append(-1, "Speak user", "speak")
		m_follow = menu.Append(-1, "Follow")
		m_unfollow = menu.Append(-1, "Unfollow")
		self.Bind(wx.EVT_MENU, self.OnSpeakUser, m_speak_user)
		self.Bind(wx.EVT_MENU, self.OnFollowKey, m_follow)
		self.Bind(wx.EVT_MENU, self.OnUnfollowKey, m_unfollow)
		accel = [
			(wx.ACCEL_CTRL, ord(';'), m_speak_user.GetId()),
			(wx.ACCEL_CTRL, ord('L'), m_follow.GetId()),
			(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('L'), m_unfollow.GetId()),
		]
		accel_tbl = wx.AcceleratorTable(accel)
		self.SetAcceleratorTable(accel_tbl)
		self.panel.SetSizer(self.main_box)
		self.panel.Layout()
		theme.apply_theme(self)

	def OnSpeakUser(self, event):
		self.index = self.list.GetSelection()
		user = self.users[self.index].acct
		self.account.app.speak_user(self.account, [user])

	def on_list_change(self, event):
		self.index = self.list.GetSelection()
		user = self.users[self.index]

		# Check relationship with this user
		try:
			relationships = self.account.api.account_relationships(id=user.id)
			if relationships and len(relationships) > 0:
				rel = relationships[0]
				following = getattr(rel, 'following', False)
				muting = getattr(rel, 'muting', False)
				blocking = getattr(rel, 'blocking', False)
				showing_reblogs = getattr(rel, 'showing_reblogs', True)

				if following:
					self.unfollow.Enable(True)
					self.follow.Enable(False)
					# Show/hide boosts only available when following
					if self.show_boosts is not None:
						if showing_reblogs:
							self.hide_boosts.Enable(True)
							self.show_boosts.Enable(False)
						else:
							self.hide_boosts.Enable(False)
							self.show_boosts.Enable(True)
					# Enable/disable notifications only available when following
					if self.enable_notifs is not None:
						notifying = getattr(rel, 'notifying', False)
						if notifying:
							self.disable_notifs.Enable(True)
							self.enable_notifs.Enable(False)
						else:
							self.disable_notifs.Enable(False)
							self.enable_notifs.Enable(True)
				else:
					self.unfollow.Enable(False)
					self.follow.Enable(True)
					# Disable boosts buttons when not following
					if self.show_boosts is not None:
						self.show_boosts.Enable(False)
						self.hide_boosts.Enable(False)
					# Disable notification buttons when not following
					if self.enable_notifs is not None:
						self.enable_notifs.Enable(False)
						self.disable_notifs.Enable(False)

				if muting:
					self.unmute.Enable(True)
					self.mute.Enable(False)
				else:
					self.unmute.Enable(False)
					self.mute.Enable(True)

				if blocking:
					self.unblock.Enable(True)
					self.block.Enable(False)
				else:
					self.unblock.Enable(False)
					self.block.Enable(True)
		except:
			self.follow.Enable(True)
			self.unfollow.Enable(True)
			self.mute.Enable(True)
			self.unmute.Enable(True)
			self.block.Enable(True)
			self.unblock.Enable(True)
			if self.show_boosts is not None:
				self.show_boosts.Enable(True)
				self.hide_boosts.Enable(True)
			if self.enable_notifs is not None:
				self.enable_notifs.Enable(True)
				self.disable_notifs.Enable(True)

		self.message.Enable(True)
		self.timeline.Enable(True)

		display_name = getattr(user, 'display_name', '') or user.acct
		location = ""  # Mastodon doesn't have location field
		bio = self.account.app.strip_html(getattr(user, 'note', '') or '')
		followers_count = getattr(user, 'followers_count', 0)
		following_count = getattr(user, 'following_count', 0)
		statuses_count = getattr(user, 'statuses_count', 0)
		created_at = getattr(user, 'created_at', None)
		locked = getattr(user, 'locked', False)

		# Build extra info from fields
		extra = ""
		fields = getattr(user, 'fields', None)
		# Also try to get from _platform_data directly
		if not fields and hasattr(user, '_platform_data') and user._platform_data:
			fields = getattr(user._platform_data, 'fields', None)
			if not fields and isinstance(user._platform_data, dict):
				fields = user._platform_data.get('fields', [])
		if fields:
			for field in fields:
				if isinstance(field, dict):
					name = field.get('name', '')
					value = field.get('value', '')
				else:
					name = getattr(field, 'name', '')
					value = getattr(field, 'value', '')
				if name and value:
					extra += "\r\n" + name + ": " + self.account.app.strip_html(value)

		# Last status date
		last_status = getattr(user, 'last_status_at', None)
		if last_status:
			extra += "\r\nLast posted: " + str(last_status)

		info = "Name: " + display_name + "\r\nUsername: @" + user.acct + "\r\nBio: " + bio + extra + "\r\nFollowers: " + str(followers_count) + "\r\nFollowing: " + str(following_count) + "\r\nPosts: " + str(statuses_count) + "\r\nCreated: " + (self.account.app.parse_date(created_at) if created_at else "Unknown") + "\r\nLocked: " + str(locked)
		self.text.SetValue(info)

		if platform.system() == "Darwin":
			self.text.SetValue(self.text.GetValue().replace("\r", ""))

	def OnFollow(self, event):
		user = self.users[self.index]
		try:
			self.account.follow(user.id)
			sound.play(self.account, "follow")
		except Exception as error:
			self.account.app.handle_error(error, "Follow " + user.acct)

	def OnUnfollow(self, event):
		user = self.users[self.index]
		try:
			self.account.unfollow(user.id)
			sound.play(self.account, "unfollow")
		except Exception as error:
			self.account.app.handle_error(error, "Unfollow " + user.acct)

	def OnMute(self, event):
		user = self.users[self.index]
		misc.mute_user(self.account, user.id)
		self.on_list_change(None)

	def OnUnmute(self, event):
		user = self.users[self.index]
		misc.unmute_user(self.account, user.id)
		self.on_list_change(None)

	def OnBlock(self, event):
		user = self.users[self.index]
		misc.block_user(self.account, user.id)
		self.on_list_change(None)

	def OnUnblock(self, event):
		user = self.users[self.index]
		misc.unblock_user(self.account, user.id)
		self.on_list_change(None)

	def OnShowBoosts(self, event):
		"""Show boosts from this user (Mastodon only)."""
		import speak
		user = self.users[self.index]
		try:
			self.account.api.account_follow(id=user.id, reblogs=True)
			sound.play(self.account, "unmute")
			speak.speak(f"Showing boosts from {user.acct}")
			self.on_list_change(None)
		except Exception as error:
			self.account.app.handle_error(error, "show boosts")

	def OnHideBoosts(self, event):
		"""Hide boosts from this user (Mastodon only)."""
		import speak
		user = self.users[self.index]
		try:
			self.account.api.account_follow(id=user.id, reblogs=False)
			sound.play(self.account, "mute")
			speak.speak(f"Hiding boosts from {user.acct}")
			self.on_list_change(None)
		except Exception as error:
			self.account.app.handle_error(error, "hide boosts")

	def OnEnableNotifications(self, event):
		"""Enable notifications when this user posts (Mastodon only)."""
		import speak
		user = self.users[self.index]
		try:
			self.account.api.account_follow(id=user.id, notify=True)
			sound.play(self.account, "unmute")
			speak.speak(f"Notifications enabled for {user.acct}")
			self.on_list_change(None)
		except Exception as error:
			self.account.app.handle_error(error, "enable notifications")

	def OnDisableNotifications(self, event):
		"""Disable notifications when this user posts (Mastodon only)."""
		import speak
		user = self.users[self.index]
		try:
			self.account.api.account_follow(id=user.id, notify=False)
			sound.play(self.account, "mute")
			speak.speak(f"Notifications disabled for {user.acct}")
			self.on_list_change(None)
		except Exception as error:
			self.account.app.handle_error(error, "disable notifications")

	def OnFollowKey(self, event):
		"""Follow user via keyboard shortcut."""
		import speak
		if self.follow.IsEnabled():
			self.OnFollow(event)
		else:
			speak.speak("Already following")

	def OnUnfollowKey(self, event):
		"""Unfollow user via keyboard shortcut."""
		import speak
		if self.unfollow.IsEnabled():
			self.OnUnfollow(event)
		else:
			speak.speak("Not following")

	def OnFollowers(self, event):
		user = self.users[self.index]
		user_id = self._get_local_user_id(user)
		if user_id:
			misc.followers(self.account, user_id)

	def OnFollowing(self, event):
		user = self.users[self.index]
		user_id = self._get_local_user_id(user)
		if user_id:
			misc.following(self.account, user_id)

	def _get_local_user_id(self, user):
		"""Get the local user ID, resolving remote users if needed."""
		import speak
		# If user is from a remote instance, look them up locally first
		if hasattr(user, '_instance_url'):
			speak.speak("Looking up user...")
			try:
				# Search for user by their acct (username@domain)
				results = self.account.api.account_search(q=user.acct, limit=1)
				if results and len(results) > 0:
					return results[0].id
				else:
					speak.speak("User not found on your instance")
					return None
			except Exception as e:
				self.account.app.handle_error(e, "Look up user")
				return None
		return user.id

	def OnMessage(self, event):
		user = self.users[self.index]
		misc.message_user(self.account, user.acct)

	def OnTimeline(self, event):
		user = self.users[self.index]
		misc.user_timeline_user(self.account, user.acct)

	def OnImage(self, event):
		user = self.users[self.index]
		v = ViewImageGui(user)
		v.Show()

	def OnClose(self, event):
		"""App close event handler"""
		self.Destroy()


class ViewTextGui(wx.Dialog):

	def __init__(self, text):
		wx.Dialog.__init__(self, None, title="Text", size=(350, 200))
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.text_label = wx.StaticText(self.panel, -1, "Te&xt")
		self.main_box.Add(self.text_label, 0, wx.LEFT | wx.TOP, 10)
		self.text = wx.TextCtrl(self.panel, style=wx.TE_READONLY|wx.TE_MULTILINE|wx.TE_DONTWRAP, name="Text")
		self.main_box.Add(self.text, 0, wx.EXPAND | wx.ALL, 10)
		self.text.SetValue(text)
		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)
		self.panel.SetSizer(self.main_box)
		self.panel.Layout()
		self.text.SetFocus()

	def OnClose(self, event):
		self.Destroy()


class NotificationViewGui(wx.Dialog):
	"""Dialog for viewing notification details."""

	# Human-readable notification type labels
	NOTIFICATION_TYPES = {
		'follow': 'Follow',
		'follow_request': 'Follow Request',
		'favourite': 'Favourited your post',
		'reblog': 'Boosted your post',
		'mention': 'Mentioned you',
		'poll': 'Poll ended',
		'status': 'Posted',
		'update': 'Edited a post',
		'admin.sign_up': 'New user signed up',
		'admin.report': 'New report',
		'like': 'Liked your post',  # Bluesky
		'repost': 'Reposted your post',  # Bluesky
		'reply': 'Replied to your post',  # Bluesky
		'quote': 'Quoted your post',  # Bluesky
	}

	def __init__(self, account, notification):
		self.account = account
		self.notification = notification

		# Get notification details
		notif_type = getattr(notification, 'type', 'unknown')
		type_label = self.NOTIFICATION_TYPES.get(notif_type, notif_type.replace('_', ' ').title())

		# Get the user who triggered the notification
		notif_account = getattr(notification, 'account', None)
		if notif_account:
			display_name = getattr(notif_account, 'display_name', '') or getattr(notif_account, 'acct', 'Unknown')
			acct = getattr(notif_account, 'acct', '')
		else:
			display_name = 'Unknown'
			acct = ''

		title = f"Notification: {type_label}"
		wx.Dialog.__init__(self, None, title=title, size=(350, 200))

		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		# Notification details text
		self.details_label = wx.StaticText(self.panel, -1, "Notification &Details")
		self.main_box.Add(self.details_label, 0, wx.LEFT | wx.TOP, 10)
		self.details = wx.TextCtrl(self.panel, style=wx.TE_READONLY|wx.TE_MULTILINE|wx.TE_DONTWRAP, size=text_box_size, name="Notification Details")
		self.main_box.Add(self.details, 0, wx.EXPAND | wx.ALL, 10)
		self.details.SetFocus()

		# Build details text
		created_at = getattr(notification, 'created_at', None)
		time_str = self.account.app.parse_date(created_at) if created_at else 'Unknown'

		details_text = f"Type: {type_label}\r\n"
		details_text += f"From: {display_name}"
		if acct:
			details_text += f" (@{acct})"
		details_text += f"\r\nTime: {time_str}"

		# Add notification-specific details
		if notif_type == 'follow':
			details_text += "\r\n\r\nThis user is now following you."
		elif notif_type == 'follow_request':
			details_text += "\r\n\r\nThis user has requested to follow you."
		elif notif_type in ('favourite', 'like'):
			details_text += "\r\n\r\nThey liked your post."
		elif notif_type in ('reblog', 'repost'):
			details_text += "\r\n\r\nThey boosted/reposted your post."
		elif notif_type == 'mention':
			details_text += "\r\n\r\nYou were mentioned in a post."
		elif notif_type == 'poll':
			details_text += "\r\n\r\nA poll you voted in or created has ended."

		self.details.SetValue(details_text)

		# Related post text (if any)
		self.status = getattr(notification, 'status', None)
		if self.status:
			self.post_label = wx.StaticText(self.panel, -1, "&Post Content")
			self.main_box.Add(self.post_label, 0, wx.LEFT | wx.TOP, 10)
			if self.account.app.prefs.wrap:
				self.post_text = wx.TextCtrl(self.panel, style=wx.TE_READONLY|wx.TE_MULTILINE, size=text_box_size, name="Post Content")
			else:
				self.post_text = wx.TextCtrl(self.panel, style=wx.TE_READONLY|wx.TE_MULTILINE|wx.TE_DONTWRAP, size=text_box_size, name="Post Content")
			self.main_box.Add(self.post_text, 0, wx.EXPAND | wx.ALL, 10)

			# Get post content
			content = getattr(self.status, 'content', '')
			mentions = getattr(self.status, 'mentions', [])
			post_content = self.account.app.html_to_text_for_edit(content, mentions)
			self.post_text.SetValue(post_content)

			# Show spoiler if present
			spoiler = getattr(self.status, 'spoiler_text', '')
			if spoiler:
				self.post_text.SetValue(f"[CW: {spoiler}]\r\n\r\n{post_content}")

		# Action buttons
		if notif_account:
			self.view_profile = wx.Button(self.panel, -1, "View &Profile")
			self.view_profile.Bind(wx.EVT_BUTTON, self.OnViewProfile)
			self.main_box.Add(self.view_profile, 0, wx.ALL, 10)

		if self.status:
			self.view_post = wx.Button(self.panel, -1, "&View Full Post")
			self.view_post.Bind(wx.EVT_BUTTON, self.OnViewPost)
			self.main_box.Add(self.view_post, 0, wx.ALL, 10)

			self.reply = wx.Button(self.panel, -1, "&Reply")
			self.reply.Bind(wx.EVT_BUTTON, self.OnReply)
			self.main_box.Add(self.reply, 0, wx.ALL, 10)

		# Follow request actions
		if notif_type == 'follow_request':
			self.accept = wx.Button(self.panel, -1, "&Accept Request")
			self.accept.Bind(wx.EVT_BUTTON, self.OnAcceptFollowRequest)
			self.main_box.Add(self.accept, 0, wx.ALL, 10)

			self.reject = wx.Button(self.panel, -1, "Re&ject Request")
			self.reject.Bind(wx.EVT_BUTTON, self.OnRejectFollowRequest)
			self.main_box.Add(self.reject, 0, wx.ALL, 10)

		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)

		if platform.system() == "Darwin":
			self.details.SetValue(self.details.GetValue().replace("\r", ""))
			if self.status:
				self.post_text.SetValue(self.post_text.GetValue().replace("\r", ""))

		self.panel.SetSizer(self.main_box)
		self.panel.Layout()

	def OnViewProfile(self, event):
		notif_account = getattr(self.notification, 'account', None)
		if notif_account:
			g = UserViewGui(self.account, [notif_account], "User Profile")
			g.Show()

	def OnViewPost(self, event):
		if self.status:
			v = ViewGui(self.account, self.status)
			v.Show()

	def OnReply(self, event):
		if self.status:
			misc.reply(self.account, self.status)

	def OnAcceptFollowRequest(self, event):
		import speak
		notif_account = getattr(self.notification, 'account', None)
		if notif_account:
			try:
				self.account.api.follow_request_authorize(id=notif_account.id)
				sound.play(self.account, "follow")
				speak.speak("Follow request accepted")
			except Exception as error:
				self.account.app.handle_error(error, "accept follow request")

	def OnRejectFollowRequest(self, event):
		import speak
		notif_account = getattr(self.notification, 'account', None)
		if notif_account:
			try:
				self.account.api.follow_request_reject(id=notif_account.id)
				speak.speak("Follow request rejected")
			except Exception as error:
				self.account.app.handle_error(error, "reject follow request")

	def OnClose(self, event):
		self.Destroy()


class ViewImageGui(wx.Dialog):

	def __init__(self, status):
		self.urls = []
		self.current_index = 0
		self.descriptions = []

		# Check if this is a user object (for profile images)
		if hasattr(status, 'avatar'):
			self.urls.append(status.avatar)
			self.descriptions.append("Profile image")
		# Check for media attachments on a status
		elif hasattr(status, 'media_attachments') and status.media_attachments:
			for media in status.media_attachments:
				media_type = getattr(media, 'type', '') or ''
				if media_type.lower() == 'image':
					url = getattr(media, 'url', None) or getattr(media, 'preview_url', None)
					if url:
						self.urls.append(url)
						desc = getattr(media, 'description', None) or "No description"
						self.descriptions.append(desc)

		wx.Dialog.__init__(self, None, title="Image Viewer", size=(800, 600))
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDown)

		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		if not self.urls:
			self.text = wx.StaticText(self.panel, -1, "No image available")
			self.main_box.Add(self.text, 0, wx.ALL, 10)
		else:
			# Image counter label
			self.counter_label = wx.StaticText(self.panel, -1, "")
			self.main_box.Add(self.counter_label, 0, wx.ALL, 5)

			# Description (read-only text field for accessibility)
			self.desc_label = wx.StaticText(self.panel, -1, "&Description:")
			self.main_box.Add(self.desc_label, 0, wx.LEFT | wx.TOP, 10)
			self.description = wx.TextCtrl(self.panel, -1, "", style=wx.TE_MULTILINE | wx.TE_READONLY, size=(780, 60), name="Image description")
			self.main_box.Add(self.description, 0, wx.ALL, 5)

			# Image display area
			self.image_panel = wx.Panel(self.panel, size=(780, 400))
			self.main_box.Add(self.image_panel, 1, wx.EXPAND | wx.ALL, 5)
			self.bitmap_ctrl = None

			# Navigation buttons (if multiple images)
			if len(self.urls) > 1:
				nav_sizer = wx.BoxSizer(wx.HORIZONTAL)
				self.prev_btn = wx.Button(self.panel, -1, "&Previous")
				self.prev_btn.Bind(wx.EVT_BUTTON, self.OnPrevious)
				nav_sizer.Add(self.prev_btn, 0, wx.ALL, 5)
				self.next_btn = wx.Button(self.panel, -1, "&Next")
				self.next_btn.Bind(wx.EVT_BUTTON, self.OnNext)
				nav_sizer.Add(self.next_btn, 0, wx.ALL, 5)
				self.main_box.Add(nav_sizer, 0, wx.ALIGN_CENTER, 5)

		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)

		self.panel.SetSizer(self.main_box)
		self.panel.Layout()

		if self.urls:
			self._load_current_image()
			self.description.SetFocus()
		else:
			self.close.SetFocus()

	def _load_current_image(self):
		"""Load and display the current image."""
		import io
		try:
			from PIL import Image as PILImage
		except ImportError:
			# Fallback if PIL not available
			self.description.SetValue("Error: PIL/Pillow library not installed")
			return

		url = self.urls[self.current_index]
		desc = self.descriptions[self.current_index]

		# Update counter and description
		self.counter_label.SetLabel(f"Image {self.current_index + 1} of {len(self.urls)}")
		self.description.SetValue(desc)

		try:
			# Download image
			response = requests.get(url, timeout=30)
			response.raise_for_status()

			# Load with PIL (supports many formats including WebP)
			pil_image = PILImage.open(io.BytesIO(response.content))

			# Convert to RGB if necessary (for formats like RGBA, P, etc.)
			if pil_image.mode not in ('RGB', 'L'):
				pil_image = pil_image.convert('RGB')

			# Scale to fit the panel while maintaining aspect ratio
			panel_size = self.image_panel.GetSize()
			max_width = panel_size[0] - 20
			max_height = panel_size[1] - 20

			# Calculate scaling factor
			img_width, img_height = pil_image.size
			scale = min(max_width / img_width, max_height / img_height, 1.0)

			if scale < 1.0:
				new_width = int(img_width * scale)
				new_height = int(img_height * scale)
				pil_image = pil_image.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

			# Convert PIL image to wx.Bitmap
			wx_image = wx.Image(pil_image.size[0], pil_image.size[1])
			wx_image.SetData(pil_image.tobytes())
			bitmap = wx_image.ConvertToBitmap()

			# Remove old bitmap control if exists
			if self.bitmap_ctrl:
				self.bitmap_ctrl.Destroy()

			# Create new bitmap control
			self.bitmap_ctrl = wx.StaticBitmap(self.image_panel, -1, bitmap)

		except Exception as e:
			self.description.SetValue(f"Error loading image: {str(e)}\n\nURL: {url}")

		# Update navigation buttons
		if len(self.urls) > 1:
			self.prev_btn.Enable(self.current_index > 0)
			self.next_btn.Enable(self.current_index < len(self.urls) - 1)

	def OnKeyDown(self, event):
		"""Handle keyboard navigation."""
		keycode = event.GetKeyCode()
		if keycode == wx.WXK_LEFT and len(self.urls) > 1:
			self.OnPrevious(None)
		elif keycode == wx.WXK_RIGHT and len(self.urls) > 1:
			self.OnNext(None)
		elif keycode == wx.WXK_ESCAPE:
			self.OnClose(None)
		else:
			event.Skip()

	def OnPrevious(self, event):
		"""Show previous image."""
		if self.current_index > 0:
			self.current_index -= 1
			self._load_current_image()

	def OnNext(self, event):
		"""Show next image."""
		if self.current_index < len(self.urls) - 1:
			self.current_index += 1
			self._load_current_image()

	def OnClose(self, event):
		self.Destroy()
