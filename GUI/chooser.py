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
	TYPE_LIST = "list"
	TYPE_LIST_R="listr"
	TYPE_MUTE="mute"
	TYPE_MUTE_TOGGLE="mute_toggle"
	TYPE_PROFILE = "profile"
	TYPE_UNBLOCK="unblock"
	TYPE_UNFOLLOW="unfollow"
	TYPE_UNMUTE="unmute"
	TYPE_URL="url"
	TYPE_USER_TIMELINE="userTimeline"

	def __init__(self,account,title="Choose",text="Choose a thing",list=[],type=""):
		self.account=account
		self.type=type
		self.returnvalue=""
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
			user=view.UserViewGui(self.account,[self.account.app.lookup_user_name(self.account,self.returnvalue)],self.returnvalue+"'s profile")
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
			user=self.account.block(self.returnvalue)
		elif self.type==self.TYPE_UNBLOCK:
			user=self.account.unblock(self.returnvalue)
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
					self.account.api.account_unmute(id=user.id)
			except MastodonError as e:
				self.account.app.handle_error(e,"Unmute")
		elif self.type==self.TYPE_USER_TIMELINE:
			# Show filter selection dialog for user timelines
			self._show_filter_dialog(self.returnvalue)
		elif self.type==self.TYPE_FOLLOW_TOGGLE:
			# Toggle follow state - check relationship first
			try:
				user = self.account.app.lookup_user_name(self.account, self.returnvalue)
				if user != -1:
					rel = misc.get_relationship(self.account, user.id)
					if rel.get('following', False):
						self.account.unfollow(self.returnvalue)
						sound.play(self.account, "unfollow")
					else:
						self.account.follow(self.returnvalue)
						sound.play(self.account, "follow")
			except MastodonError as e:
				self.account.app.handle_error(e, "Toggle follow")
		elif self.type==self.TYPE_MUTE_TOGGLE:
			# Toggle mute state - check relationship first
			try:
				user = self.account.app.lookup_user_name(self.account, self.returnvalue)
				if user != -1:
					rel = misc.get_relationship(self.account, user.id)
					if rel.get('muting', False):
						self.account.api.account_unmute(id=user.id)
						sound.play(self.account, "unmute")
					else:
						# Use mute dialog for options
						from . import mute_dialog
						mute_dialog.show_mute_dialog(self.account, user)
			except MastodonError as e:
				self.account.app.handle_error(e, "Toggle mute")
		elif self.type==self.TYPE_BLOCK_TOGGLE:
			# Toggle block state - check relationship first
			try:
				user = self.account.app.lookup_user_name(self.account, self.returnvalue)
				if user != -1:
					rel = misc.get_relationship(self.account, user.id)
					if rel.get('blocking', False):
						self.account.unblock(self.returnvalue)
						sound.play(self.account, "unblock")
					else:
						self.account.block(self.returnvalue)
						sound.play(self.account, "block")
			except MastodonError as e:
				self.account.app.handle_error(e, "Toggle block")

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

def chooser(account,title="choose",text="Choose some stuff",list=[],type=""):
	chooser=ChooseGui(account,title,text,list,type)
	chooser.Show()
	return chooser.returnvalue
