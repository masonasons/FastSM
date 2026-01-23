from mastodon import MastodonError
import sound, timeline
from application import get_app
import time
import wx
import webbrowser
import os
import platform
from . import lists, main, misc, theme, view

class ChooseGui(wx.Dialog):

	#constants for the types we might need to handle
	TYPE_BLOCK="block"
	TYPE_BLOCK_TOGGLE="block_toggle"
	TYPE_FOLLOW="follow"
	TYPE_FOLLOW_TOGGLE="follow_toggle"
	TYPE_FOLLOW_HASHTAG="followHashtag"
	TYPE_LIST = "list"
	TYPE_LIST_R="listr"
	TYPE_MUTE="mute"
	TYPE_MUTE_TOGGLE="mute_toggle"
	TYPE_PROFILE = "profile"
	TYPE_UNBLOCK="unblock"
	TYPE_UNFOLLOW="unfollow"
	TYPE_UNFOLLOW_HASHTAG="unfollowHashtag"
	TYPE_UNMUTE="unmute"
	TYPE_URL="url"
	TYPE_USER_TIMELINE="userTimeline"
	# Types that work with user objects directly (no lookup needed)
	TYPE_PROFILE_DIRECT="profile_direct"
	TYPE_USER_TIMELINE_DIRECT="userTimeline_direct"
	TYPE_ALIAS="alias"

	def __init__(self,account,title="Choose",text="Choose a thing",list=[],type="",user_objects=None):
		self.account=account
		self.type=type
		self.returnvalue=""
		self.user_objects = user_objects or []  # Store user objects for direct use
		wx.Dialog.__init__(self, None, title=title, size=(350,200))
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.chooser_label=wx.StaticText(self.panel, -1, title)
		self.main_box.Add(self.chooser_label, 0, wx.LEFT | wx.TOP, 10)
		self.chooser=wx.ComboBox(self.panel,-1,size=(800,600))
		self.main_box.Add(self.chooser, 0, wx.EXPAND | wx.ALL, 10)
		self.chooser.SetFocus()
		for i in list:
			self.chooser.Insert(i,self.chooser.GetCount())
		self.chooser.SetSelection(0)
		self.ok = wx.Button(self.panel, wx.ID_DEFAULT, "OK")
		self.ok.SetDefault()
		self.ok.Bind(wx.EVT_BUTTON, self.OK)
		self.main_box.Add(self.ok, 0, wx.ALL, 10)
		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)
		self.panel.SetSizer(self.main_box)
		self.panel.Layout()
		theme.apply_theme(self)

	def OK(self, event):
		self.returnvalue=self.chooser.GetValue().strip("@")
		self.Destroy()
		if self.type==self.TYPE_PROFILE:
			looked_up = self.account.app.lookup_user_name(self.account, self.returnvalue)
			if looked_up == -1 or looked_up is None:
				import speak
				speak.speak(f"Could not find user {self.returnvalue}")
				return
			user=view.UserViewGui(self.account,[looked_up],self.returnvalue+"'s profile")
			user.Show()
		elif self.type==self.TYPE_URL:
			self.account.app.openURL(self.returnvalue)
		elif self.type==self.TYPE_LIST:
			l=lists.ListsGui(self.account,self.account.app.lookup_user_name(self.account,self.returnvalue))
			l.Show()
		elif self.type==self.TYPE_LIST_R:
			l=lists.ListsGui(self.account,self.account.app.lookup_user_name(self.account,self.returnvalue),False)
			l.Show()
		elif self.type==self.TYPE_FOLLOW:
			misc.follow_user(self.account,self.returnvalue)
		elif self.type==self.TYPE_UNFOLLOW:
			misc.unfollow_user(self.account,self.returnvalue)
		elif self.type==self.TYPE_BLOCK:
			try:
				user = self.account.app.lookup_user_name(self.account, self.returnvalue)
				if user != -1:
					self.account.block(user.id)
					sound.play(self.account, "block")
			except Exception as e:
				self.account.app.handle_error(e, "Block")
		elif self.type==self.TYPE_UNBLOCK:
			try:
				user = self.account.app.lookup_user_name(self.account, self.returnvalue)
				if user != -1:
					self.account.unblock(user.id)
					sound.play(self.account, "unblock")
			except Exception as e:
				self.account.app.handle_error(e, "Unblock")
		elif self.type==self.TYPE_MUTE:
			try:
				user = self.account.app.lookup_user_name(self.account, self.returnvalue)
				if user != -1:
					from . import mute_dialog
					mute_dialog.show_mute_dialog(self.account, user)
			except MastodonError as e:
				self.account.app.handle_error(e,"Mute")
		elif self.type==self.TYPE_UNMUTE:
			try:
				user = self.account.app.lookup_user_name(self.account, self.returnvalue)
				if user != -1:
					# Use platform backend if available
					if hasattr(self.account, '_platform') and self.account._platform:
						self.account._platform.unmute(user.id)
					else:
						self.account.api.account_unmute(id=user.id)
			except Exception as e:
				self.account.app.handle_error(e,"Unmute")
		elif self.type==self.TYPE_USER_TIMELINE:
			# Show filter selection dialog for user timelines
			self._show_filter_dialog(self.returnvalue)
		elif self.type==self.TYPE_PROFILE_DIRECT:
			# Use user object directly (no lookup needed)
			idx = self.chooser.GetSelection()
			if idx >= 0 and idx < len(self.user_objects):
				user = self.user_objects[idx]
				viewer = view.UserViewGui(self.account, [user], user.acct + "'s profile")
				viewer.Show()
			elif self.returnvalue:
				# User typed a username manually - fall back to lookup
				user = self.account.app.lookup_user_name(self.account, self.returnvalue)
				if user and user != -1:
					viewer = view.UserViewGui(self.account, [user], user.acct + "'s profile")
					viewer.Show()
				else:
					import speak
					speak.speak("Could not find user")
			else:
				import speak
				speak.speak("Could not find user")
		elif self.type==self.TYPE_USER_TIMELINE_DIRECT:
			# Use user object directly for timeline, or look up if typed manually
			idx = self.chooser.GetSelection()
			if idx >= 0 and idx < len(self.user_objects):
				user = self.user_objects[idx]
				self._show_filter_dialog(user.acct)
			elif self.returnvalue:
				# User typed a username manually - fall back to lookup
				self._show_filter_dialog(self.returnvalue)
		elif self.type==self.TYPE_ALIAS:
			# Add alias for a user
			import speak
			idx = self.chooser.GetSelection()
			user = None
			if idx >= 0 and idx < len(self.user_objects):
				user = self.user_objects[idx]
			elif self.returnvalue:
				# User typed a username manually - look up
				user = self.account.app.lookup_user_name(self.account, self.returnvalue)
				if user == -1:
					user = None
			if user:
				user_id = str(getattr(user, 'id', ''))
				acct = getattr(user, 'acct', self.returnvalue)
				current_display = getattr(user, 'display_name', '') or acct
				# Check for existing alias
				current_alias = self.account.prefs.aliases.get(user_id, current_display)
				dlg = wx.TextEntryDialog(None, f"Enter alias for @{acct}:", "Add Alias", current_alias)
				if dlg.ShowModal() == wx.ID_OK:
					new_alias = dlg.GetValue().strip()
					if new_alias:
						self.account.prefs.aliases[user_id] = new_alias
						self.account.prefs.save()
						speak.speak(f"Alias set for {acct}")
						# Clear display caches to refresh with new alias
						for tl in self.account.timelines:
							tl.invalidate_display_cache()
							for status in getattr(tl, 'statuses', []):
								if hasattr(status, '_display_cache'):
									delattr(status, '_display_cache')
					else:
						# Remove alias if empty
						if user_id in self.account.prefs.aliases:
							del self.account.prefs.aliases[user_id]
							self.account.prefs.save()
							speak.speak(f"Alias removed for {acct}")
							# Clear display caches
							for tl in self.account.timelines:
								tl.invalidate_display_cache()
								for status in getattr(tl, 'statuses', []):
									if hasattr(status, '_display_cache'):
										delattr(status, '_display_cache')
				dlg.Destroy()
			else:
				speak.speak("Could not find user")
		elif self.type==self.TYPE_FOLLOW_TOGGLE:
			# Toggle follow state - check relationship first
			try:
				user = self.account.app.lookup_user_name(self.account, self.returnvalue)
				if user != -1:
					# Check if we can get relationship info
					following = False
					platform_type = getattr(self.account.prefs, 'platform_type', 'mastodon')
					if platform_type == 'mastodon' and hasattr(self.account, 'api') and hasattr(self.account.api, 'account_relationships'):
						try:
							relationships = self.account.api.account_relationships([user.id])
							if relationships and len(relationships) > 0:
								following = getattr(relationships[0], 'following', False)
						except:
							pass
					elif platform_type == 'bluesky' and hasattr(self.account, '_platform') and self.account._platform:
						# Bluesky - fetch fresh profile to get current relationship state
						try:
							profile = self.account._platform.client.get_profile(user.id)
							if profile and hasattr(profile, 'viewer') and profile.viewer:
								following = bool(getattr(profile.viewer, 'following', None))
						except:
							pass

					if following:
						# Check if confirmation is required
						if self.account.app.prefs.confirm_unfollow:
							dlg = wx.MessageDialog(self, f"Are you sure you want to unfollow {user.acct}?", "Confirm Unfollow", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
							if dlg.ShowModal() != wx.ID_YES:
								dlg.Destroy()
								return
							dlg.Destroy()
						self.account.unfollow(user.id)
						sound.play(self.account, "unfollow")
					else:
						# Check if confirmation is required
						if self.account.app.prefs.confirm_follow:
							dlg = wx.MessageDialog(self, f"Are you sure you want to follow {user.acct}?", "Confirm Follow", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
							if dlg.ShowModal() != wx.ID_YES:
								dlg.Destroy()
								return
							dlg.Destroy()
						self.account.follow(user.id)
						sound.play(self.account, "follow")
			except Exception as e:
				self.account.app.handle_error(e, "Toggle follow")
		elif self.type==self.TYPE_MUTE_TOGGLE:
			# Toggle mute state - check relationship first
			try:
				user = self.account.app.lookup_user_name(self.account, self.returnvalue)
				if user != -1:
					# Check if we can get relationship info
					muting = False
					platform_type = getattr(self.account.prefs, 'platform_type', 'mastodon')
					if platform_type == 'mastodon' and hasattr(self.account, 'api') and hasattr(self.account.api, 'account_relationships'):
						try:
							relationships = self.account.api.account_relationships([user.id])
							if relationships and len(relationships) > 0:
								muting = getattr(relationships[0], 'muting', False)
						except:
							pass
					elif platform_type == 'bluesky' and hasattr(self.account, '_platform') and self.account._platform:
						# Bluesky - fetch fresh profile to get current relationship state
						try:
							profile = self.account._platform.client.get_profile(user.id)
							if profile and hasattr(profile, 'viewer') and profile.viewer:
								muting = bool(getattr(profile.viewer, 'muted', False))
						except:
							pass

					if muting:
						# Unmute
						if hasattr(self.account, '_platform') and self.account._platform:
							self.account._platform.unmute(user.id)
						else:
							self.account.api.account_unmute(id=user.id)
						sound.play(self.account, "unmute")
					else:
						# Mute - use dialog for Mastodon, direct mute for Bluesky
						platform_type = getattr(self.account.prefs, 'platform_type', 'mastodon')
						if platform_type == 'mastodon':
							from . import mute_dialog
							mute_dialog.show_mute_dialog(self.account, user)
						else:
							if hasattr(self.account, '_platform') and self.account._platform:
								self.account._platform.mute(user.id)
							sound.play(self.account, "mute")
			except Exception as e:
				self.account.app.handle_error(e, "Toggle mute")
		elif self.type==self.TYPE_BLOCK_TOGGLE:
			# Toggle block state - check relationship first
			try:
				user = self.account.app.lookup_user_name(self.account, self.returnvalue)
				if user != -1:
					# Check if we can get relationship info
					blocking = False
					platform_type = getattr(self.account.prefs, 'platform_type', 'mastodon')
					if platform_type == 'mastodon' and hasattr(self.account, 'api') and hasattr(self.account.api, 'account_relationships'):
						try:
							relationships = self.account.api.account_relationships([user.id])
							if relationships and len(relationships) > 0:
								blocking = getattr(relationships[0], 'blocking', False)
						except:
							pass
					elif platform_type == 'bluesky' and hasattr(self.account, '_platform') and self.account._platform:
						# Bluesky - fetch fresh profile to get current relationship state
						try:
							profile = self.account._platform.client.get_profile(user.id)
							if profile and hasattr(profile, 'viewer') and profile.viewer:
								blocking = bool(getattr(profile.viewer, 'blocking', None))
						except:
							pass

					if blocking:
						self.account.unblock(user.id)
						sound.play(self.account, "unblock")
					else:
						self.account.block(user.id)
						sound.play(self.account, "block")
			except Exception as e:
				self.account.app.handle_error(e, "Toggle block")
		elif self.type==self.TYPE_FOLLOW_HASHTAG:
			# Follow a hashtag - strip # prefix if present
			hashtag = self.returnvalue.lstrip('#')
			misc.follow_hashtag(self.account, hashtag)
		elif self.type==self.TYPE_UNFOLLOW_HASHTAG:
			# Unfollow a hashtag - strip # prefix if present
			hashtag = self.returnvalue.lstrip('#')
			misc.unfollow_hashtag(self.account, hashtag)

	def _show_filter_dialog(self, username):
		"""Show a dialog to select filter type for user timelines."""
		platform_type = getattr(self.account.prefs, 'platform_type', 'mastodon')

		if platform_type == 'bluesky':
			choices = [
				"Posts and Replies (default)",
				"Posts Only",
				"Media Only",
				"Threads Only",
			]
			filter_values = [
				None,  # default (posts_with_replies)
				'posts_no_replies',
				'posts_with_media',
				'posts_and_author_threads',
			]
		else:
			# Mastodon filter options
			choices = [
				"Posts and Replies (default)",
				"Posts Only (no replies)",
				"Media Only",
				"No Boosts",
			]
			filter_values = [
				None,  # default (posts_with_replies)
				'posts_no_replies',
				'posts_with_media',
				'posts_no_boosts',
			]

		dlg = wx.SingleChoiceDialog(
			None,
			f"Select what to load for {username}'s timeline:",
			"Timeline Filter",
			choices
		)
		dlg.SetSelection(0)

		if dlg.ShowModal() == wx.ID_OK:
			selection = dlg.GetSelection()
			filter_value = filter_values[selection]
			misc.user_timeline_user(self.account, username, filter=filter_value)

		dlg.Destroy()

	def OnClose(self, event):
		self.Destroy()

def chooser(account,title="choose",text="Choose some stuff",list=[],type="",user_objects=None):
	chooser=ChooseGui(account,title,text,list,type,user_objects=user_objects)
	chooser.Show()
	return chooser.returnvalue
