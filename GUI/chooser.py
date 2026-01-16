from mastodon import MastodonError
import sound, timeline
from application import get_app
import time
import wx
import webbrowser
import os
import platform
from . import lists, main, misc, view

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
		self.chooser=wx.ComboBox(self.panel,-1,size=(800,600))
		self.main_box.Add(self.chooser, 0, wx.ALL, 10)
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
		self.panel.Layout()

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
			else:
				import speak
				speak.speak("Could not find user")
		elif self.type==self.TYPE_USER_TIMELINE_DIRECT:
			# Use user object directly for timeline
			idx = self.chooser.GetSelection()
			if idx >= 0 and idx < len(self.user_objects):
				user = self.user_objects[idx]
				self._show_filter_dialog(user.acct)
			else:
				import speak
				speak.speak("Could not find user")
		elif self.type==self.TYPE_FOLLOW_TOGGLE:
			# Toggle follow state - check relationship first
			try:
				user = self.account.app.lookup_user_name(self.account, self.returnvalue)
				if user != -1:
					# Check if we can get relationship info
					following = False
					if hasattr(self.account, 'api') and hasattr(self.account.api, 'account_relationships'):
						try:
							relationships = self.account.api.account_relationships([user.id])
							if relationships and len(relationships) > 0:
								following = getattr(relationships[0], 'following', False)
						except:
							pass
					elif hasattr(user, 'viewer') and user.viewer:
						# Bluesky viewer info
						following = getattr(user.viewer, 'following', False)

					if following:
						self.account.unfollow(user.id)
						sound.play(self.account, "unfollow")
					else:
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
					if hasattr(self.account, 'api') and hasattr(self.account.api, 'account_relationships'):
						try:
							relationships = self.account.api.account_relationships([user.id])
							if relationships and len(relationships) > 0:
								muting = getattr(relationships[0], 'muting', False)
						except:
							pass
					elif hasattr(user, 'viewer') and user.viewer:
						# Bluesky viewer info
						muting = getattr(user.viewer, 'muted', False)

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
					if hasattr(self.account, 'api') and hasattr(self.account.api, 'account_relationships'):
						try:
							relationships = self.account.api.account_relationships([user.id])
							if relationships and len(relationships) > 0:
								blocking = getattr(relationships[0], 'blocking', False)
						except:
							pass
					elif hasattr(user, 'viewer') and user.viewer:
						# Bluesky viewer info
						blocking = getattr(user.viewer, 'blocked_by', False) or getattr(user.viewer, 'blocking', False)

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
