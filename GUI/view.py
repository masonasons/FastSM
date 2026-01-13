import requests
import platform
from application import get_app
from . import misc
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

		self.post_text = self.account.app.process_status(self.status, True)
		wx.Dialog.__init__(self, None, title=title, size=(350, 200))

		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		self.text_label = wx.StaticText(self.panel, -1, "Te&xt")
		if self.account.app.prefs.wrap:
			self.text = wx.TextCtrl(self.panel, style=wx.TE_READONLY|wx.TE_MULTILINE, size=text_box_size)
		else:
			self.text = wx.TextCtrl(self.panel, style=wx.TE_READONLY|wx.TE_MULTILINE|wx.TE_DONTWRAP, size=text_box_size)
		self.main_box.Add(self.text, 0, wx.ALL, 10)
		self.text.SetFocus()
		self.text.SetValue(self.post_text)

		self.text2_label = wx.StaticText(self.panel, -1, "Post &Details")
		self.text2 = wx.TextCtrl(self.panel, style=wx.TE_READONLY|wx.TE_MULTILINE|wx.TE_DONTWRAP, size=text_box_size)
		self.main_box.Add(self.text2, 0, wx.ALL, 10)

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

		if not hasattr(self.status, 'media_attachments') or not self.status.media_attachments:
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
		self.panel.Layout()

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
		self.list = wx.ListBox(self.panel, -1)
		self.main_box.Add(self.list, 0, wx.ALL, 10)
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
		self.text = wx.TextCtrl(self.panel, style=wx.TE_READONLY|wx.TE_MULTILINE|wx.TE_DONTWRAP, size=text_box_size)
		self.main_box.Add(self.text, 0, wx.ALL, 10)
		if len(self.users) == 1:
			self.text.SetFocus()

		self.follow = wx.Button(self.panel, -1, "&Follow")
		self.follow.Bind(wx.EVT_BUTTON, self.OnFollow)
		self.main_box.Add(self.follow, 0, wx.ALL, 10)

		self.unfollow = wx.Button(self.panel, -1, "&Unfollow")
		self.unfollow.Bind(wx.EVT_BUTTON, self.OnUnfollow)
		self.main_box.Add(self.unfollow, 0, wx.ALL, 10)

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
		self.timeline.Enable(False)
		self.message.Enable(False)

		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)

		self.on_list_change(None)

		menu = wx.Menu()
		m_speak_user = menu.Append(-1, "Speak user", "speak")
		self.Bind(wx.EVT_MENU, self.OnSpeakUser, m_speak_user)
		accel = []
		accel.append((wx.ACCEL_CTRL, ord(';'), m_speak_user.GetId()))
		accel_tbl = wx.AcceleratorTable(accel)
		self.SetAcceleratorTable(accel_tbl)
		self.panel.Layout()

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
				if following:
					self.unfollow.Enable(True)
					self.follow.Enable(False)
				else:
					self.unfollow.Enable(False)
					self.follow.Enable(True)
		except:
			self.follow.Enable(True)
			self.unfollow.Enable(True)

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
		misc.follow_user(self.account, user.acct)

	def OnUnfollow(self, event):
		user = self.users[self.index]
		misc.unfollow_user(self.account, user.acct)

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
		self.text = wx.TextCtrl(self.panel, style=wx.TE_READONLY|wx.TE_MULTILINE|wx.TE_DONTWRAP)
		self.main_box.Add(self.text, 0, wx.ALL, 10)
		self.text.SetValue(text)
		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)
		self.panel.Layout()

	def OnClose(self, event):
		self.Destroy()


class ViewImageGui(wx.Dialog):

	def __init__(self, status):
		self.url = None
		# Check if this is a user object (for profile images)
		if hasattr(status, 'avatar'):
			self.url = status.avatar
		# Check for media attachments on a status
		elif hasattr(status, 'media_attachments') and status.media_attachments:
			for media in status.media_attachments:
				self.url = getattr(media, 'url', None) or getattr(media, 'preview_url', None)
				if self.url:
					break

		if not self.url:
			wx.Dialog.__init__(self, None, title="Image", size=(400, 300))
			self.Bind(wx.EVT_CLOSE, self.OnClose)
			self.panel = wx.Panel(self)
			self.text = wx.StaticText(self.panel, -1, "No image available")
			self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
			self.close.Bind(wx.EVT_BUTTON, self.OnClose)
			self.panel.Layout()
			return

		image = requests.get(self.url)
		f = open(get_app().confpath + "/temp_image", "wb")
		f.write(image.content)
		f.close()
		self.image = wx.Image(get_app().confpath + "/temp_image", wx.BITMAP_TYPE_ANY).ConvertToBitmap()
		self.size = (self.image.GetWidth(), self.image.GetHeight())
		wx.Dialog.__init__(self, None, title="Image", size=self.size)
		self.SetClientSize(self.size)
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.text_label = wx.StaticText(self.panel, -1, "Image")
		self.text = wx.StaticBitmap(self.panel, -1, self.image, (10, 5), self.size)
		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.panel.Layout()

	def OnClose(self, event):
		self.Destroy()
