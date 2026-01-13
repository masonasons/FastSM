import os
import webbrowser
import platform
import pyperclip
import sys
import application
from application import get_app
import wx
from keyboard_handler.wx_handler import WXKeyboardHandler
import speak
from . import account_options, accounts, chooser, custom_timelines, invisible, lists, misc, options, profile, search, timelines, tray, tweet, view
import sound
import timeline
import threading

class MainGui(wx.Frame):
	def __init__(self, title):
		self.invisible=False
		wx.Frame.__init__(self, None, title=title,size=(800,600))
		self.Center()
		if platform.system()!="Darwin":
			self.trayicon=tray.TaskBarIcon(self)
		self.handler=WXKeyboardHandler(self)
		self.handler.register_key("control+win+shift+t",self.ToggleWindow)
		self.handler.register_key("alt+win+shift+q",self.OnClose)
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.menuBar = wx.MenuBar()
		if platform.system()!="Darwin":
			ctrl="control"
		else:
			ctrl="command"

		menu = wx.Menu()
		m_accounts = menu.Append(-1, "Accounts ("+ctrl+"+A)", "accounts")
		self.Bind(wx.EVT_MENU, self.OnAccounts, m_accounts)
		m_update_profile = menu.Append(-1, "Update profile", "profile")
		self.Bind(wx.EVT_MENU, self.OnUpdateProfile, m_update_profile)
		m_lists = menu.Append(-1, "Lists", "lists")
		self.Bind(wx.EVT_MENU, self.OnLists, m_lists)
		m_custom_timelines = menu.Append(-1, "Add Custom Timeline ("+ctrl+"+shift+T)", "custom_timelines")
		self.Bind(wx.EVT_MENU, self.OnCustomTimelines, m_custom_timelines)
		m_followers = menu.Append(-1, "List Followers ("+ctrl+"+Left Bracket)", "followers")
		self.Bind(wx.EVT_MENU, self.OnFollowers, m_followers)
		m_friends = menu.Append(-1, "List Following ("+ctrl+"+right bracket)", "following")
		self.Bind(wx.EVT_MENU, self.OnFriends, m_friends)
		if platform.system()!="Darwin":
			m_options = menu.Append(wx.ID_PREFERENCES, "Global Options", "options")
		else:
			m_options = menu.Append(wx.ID_PREFERENCES, "Preferences ("+ctrl+"+comma", "options")
		self.Bind(wx.EVT_MENU, self.OnOptions, m_options)
		m_account_options = menu.Append(-1, "Account options", "account_options")
		self.Bind(wx.EVT_MENU, self.OnAccountOptions, m_account_options)
		m_close = menu.Append(wx.ID_EXIT, "exit", "exit")
		self.Bind(wx.EVT_MENU, self.OnClose, m_close)
		self.menuBar.Append(menu, "&Application")
		menu2 = wx.Menu()
		m_tweet = menu2.Append(-1, "New post ("+ctrl+"+n)", "post")
		self.Bind(wx.EVT_MENU, self.OnTweet, m_tweet)
		m_reply = menu2.Append(-1, "Reply ("+ctrl+"+r)", "reply")
		self.Bind(wx.EVT_MENU, self.OnReply, m_reply)
		m_retweet = menu2.Append(-1, "Boost ("+ctrl+"+shift+r)", "boost")
		self.Bind(wx.EVT_MENU, self.OnRetweet, m_retweet)
		if platform.system()=="Darwin":
			m_quote = menu2.Append(-1, "Quote (option+q)", "quote")
		else:
			m_quote = menu2.Append(-1, "Quote ("+ctrl+"+q)", "quote")
		self.Bind(wx.EVT_MENU, self.OnQuote, m_quote)
		m_like=menu2.Append(-1, "Favourite ("+ctrl+"+l)", "favourite")
		self.Bind(wx.EVT_MENU, self.OnLike, m_like)
		m_url=menu2.Append(-1, "Open URL ("+ctrl+"+o)", "url")
		self.Bind(wx.EVT_MENU, self.OnUrl, m_url)
		m_tweet_url=menu2.Append(-1, "Open URL of Post ("+ctrl+"+shift+o)", "post_url")
		self.Bind(wx.EVT_MENU, self.OnTweetUrl, m_tweet_url)
		m_delete = menu2.Append(-1, "Delete Post (Delete)", "post")
		self.Bind(wx.EVT_MENU, self.OnDelete, m_delete)
		m_copy = menu2.Append(-1, "Copy post to clipboard ("+ctrl+"+c)", "copy")
		self.Bind(wx.EVT_MENU, self.onCopy, m_copy)
		m_message=menu2.Append(-1, "Send message ("+ctrl+"+d)", "message")
		self.Bind(wx.EVT_MENU, self.OnMessage, m_message)
		m_follow=menu2.Append(-1, "Follow ("+ctrl+"+f)", "follow")
		self.Bind(wx.EVT_MENU, self.OnFollow, m_follow)
		m_unfollow=menu2.Append(-1, "Unfollow ("+ctrl+"+shift+f", "follow")
		self.Bind(wx.EVT_MENU, self.OnUnfollow, m_unfollow)
		m_add_to_list=menu2.Append(-1, "Add to list ("+ctrl+"+i)", "addlist")
		self.Bind(wx.EVT_MENU, self.OnAddToList, m_add_to_list)
		m_remove_from_list=menu2.Append(-1, "Remove from list ("+ctrl+"+shift+i)", "removelist")
		self.Bind(wx.EVT_MENU, self.OnRemoveFromList, m_remove_from_list)
		m_block=menu2.Append(-1, "Block ("+ctrl+"+b)", "block")
		self.Bind(wx.EVT_MENU, self.OnBlock, m_block)
		m_unblock=menu2.Append(-1, "Unblock ("+ctrl+"+shift+b)", "unblock")
		self.Bind(wx.EVT_MENU, self.OnUnblock, m_unblock)
		m_mute_user=menu2.Append(-1, "Mute", "mute")
		self.Bind(wx.EVT_MENU, self.OnMuteUser, m_mute_user)
		m_unmute_user=menu2.Append(-1, "Unmute", "unmute")
		self.Bind(wx.EVT_MENU, self.OnUnmuteUser, m_unmute_user)
		m_view=menu2.Append(-1, "View post (Enter)", "view")
		self.Bind(wx.EVT_MENU, self.OnView, m_view)
		m_user_profile=menu2.Append(-1, "User Profile ("+ctrl+"+shift+u)", "profile")
		self.Bind(wx.EVT_MENU, self.OnUserProfile, m_user_profile)
		m_speak_user=menu2.Append(-1, "Speak user ("+ctrl+"+semicolon)", "speak")
		self.Bind(wx.EVT_MENU, self.OnSpeakUser, m_speak_user)
		m_speak_reply=menu2.Append(-1, "Speak reference post of this reply ("+ctrl+"+shift+semicolon)", "speak2")
		self.Bind(wx.EVT_MENU, self.OnSpeakReply, m_speak_reply)
		m_conversation=menu2.Append(-1, "Load conversation/related posts ("+ctrl+"+g)", "conversation")
		self.Bind(wx.EVT_MENU, self.OnConversation, m_conversation)
		self.menuBar.Append(menu2, "A&ctions")
		menu7 = wx.Menu()
		m_mutual_following=menu7.Append(-1, "View mutual follows (users who I follow that also follow me)", "conversation")
		self.Bind(wx.EVT_MENU, self.OnMutualFollowing, m_mutual_following)
		m_not_following=menu7.Append(-1, "View users who follow me that I do not follow", "conversation")
		self.Bind(wx.EVT_MENU, self.OnNotFollowing, m_not_following)
		m_not_following_me=menu7.Append(-1, "View users who I follow that do not follow me", "conversation")
		self.Bind(wx.EVT_MENU, self.OnNotFollowingMe, m_not_following_me)
		m_havent_posted=menu7.Append(-1, "View users who I follow that haven't posted in a year", "conversation")
		self.Bind(wx.EVT_MENU, self.OnHaventTweeted, m_havent_posted)
		self.menuBar.Append(menu7, "U&sers")
		menu3 = wx.Menu()
		m_refresh = menu3.Append(-1, "Refresh timeline (F5)", "refresh")
		self.Bind(wx.EVT_MENU, self.onRefresh, m_refresh)
		m_prev = menu3.Append(-1, "Load older posts (alt/option+pageup)", "prev")
		self.Bind(wx.EVT_MENU, self.onPrev, m_prev)
		m_hide = menu3.Append(-1, "Hide Timeline ("+ctrl+"+h)", "hide")
		self.Bind(wx.EVT_MENU, self.OnHide, m_hide)
		m_manage_hide = menu3.Append(-1, "Manage hidden Timelines ("+ctrl+"+shift+h)", "manage_hide")
		self.Bind(wx.EVT_MENU, self.OnManageHide, m_manage_hide)
		m_read = menu3.Append(-1, "Toggle autoread ("+ctrl+"+e)", "autoread")
		self.Bind(wx.EVT_MENU, self.OnRead, m_read)
		if platform.system()!="Darwin":
			m_mute = menu3.Append(-1, "Toggle mute ("+ctrl+"+m)", "mute")
		else:
			m_mute = menu3.Append(-1, "Toggle mute ("+ctrl+"+shift+m)", "mute")
		self.Bind(wx.EVT_MENU, self.OnMute, m_mute)
		m_user_timeline = menu3.Append(-1, "User timeline ("+ctrl+"+u)", "user")
		self.Bind(wx.EVT_MENU, self.OnUserTimeline, m_user_timeline)
		m_search = menu3.Append(-1, "Search ("+ctrl+"+slash)", "search")
		self.Bind(wx.EVT_MENU, self.OnSearch, m_search)
		m_user_search = menu3.Append(-1, "User Search ("+ctrl+"+shift+slash)", "search")
		self.Bind(wx.EVT_MENU, self.OnUserSearch, m_user_search)
		self.m_close_timeline = menu3.Append(-1, "Close timeline ("+ctrl+"+w)", "removetimeline")
		self.m_close_timeline.Enable(False)
		self.Bind(wx.EVT_MENU, self.OnCloseTimeline, self.m_close_timeline)
		self.menuBar.Append(menu3, "Time&line")
		menu4 = wx.Menu()
		m_play_external = menu4.Append(-1, "Play media ("+ctrl+"+enter)", "play_external")
		self.Bind(wx.EVT_MENU, self.OnPlayExternal, m_play_external)
		m_stop_audio = menu4.Append(-1, "Stop audio ("+ctrl+"+shift+enter)", "stop_audio")
		self.Bind(wx.EVT_MENU, self.OnStopAudio, m_stop_audio)
		m_volup = menu4.Append(-1, "Volume up (alt/option+up)", "volup")
		self.Bind(wx.EVT_MENU, self.OnVolup, m_volup)
		m_voldown = menu4.Append(-1, "Volume down (alt/option+down)", "voldown")
		self.Bind(wx.EVT_MENU, self.OnVoldown, m_voldown)
		self.menuBar.Append(menu4, "A&udio")
		menu5 = wx.Menu()
		m_previous_in_thread = menu5.Append(-1, "Previous post in thread ("+ctrl+"+up)", "prevpost")
		self.Bind(wx.EVT_MENU, self.OnPreviousInThread, m_previous_in_thread)
		m_next_in_thread = menu5.Append(-1, "Next post in thread ("+ctrl+"+down)", "nextpost")
		self.Bind(wx.EVT_MENU, self.OnNextInThread, m_next_in_thread)
		m_previous_from_user = menu5.Append(-1, "Previous post from user ("+ctrl+"+left)", "prevuser")
		self.Bind(wx.EVT_MENU, self.OnPreviousFromUser, m_previous_from_user)
		m_next_from_user = menu5.Append(-1, "Next post from user ("+ctrl+"+right)", "nextuser")
		self.Bind(wx.EVT_MENU, self.OnNextFromUser, m_next_from_user)
		m_next_timeline = menu5.Append(-1, "Next timeline (alt/option+right)", "nexttl")
		self.Bind(wx.EVT_MENU, self.OnNextTimeline, m_next_timeline)
		m_prev_timeline = menu5.Append(-1, "Previous timeline (alt/Option+left)", "prevtl")
		self.Bind(wx.EVT_MENU, self.OnPrevTimeline, m_prev_timeline)
		self.menuBar.Append(menu5, "Navigation")
		menu6 = wx.Menu()
		m_readme = menu6.Append(-1, "Readme (F1)", "readme")
		self.Bind(wx.EVT_MENU, self.OnReadme, m_readme)
		m_cfu = menu6.Append(-1, "Check for updates", "cfu")
		self.Bind(wx.EVT_MENU, self.OnCfu, m_cfu)
		m_stats = menu6.Append(-1, "Stats for nerds", "stats")
		self.Bind(wx.EVT_MENU, self.OnStats, m_stats)
		m_errors = menu6.Append(-1, "View API errors", "errors")
		self.Bind(wx.EVT_MENU, self.OnErrors, m_errors)
		m_view_user_db = menu6.Append(-1, "View user database", "viewusers")
		self.Bind(wx.EVT_MENU, self.OnViewUserDb, m_view_user_db)
		m_clean_user_db = menu6.Append(-1, "Refresh user database", "cleanusers")
		self.Bind(wx.EVT_MENU, self.OnCleanUserDb, m_clean_user_db)
		self.menuBar.Append(menu6, "&Help")
		self.SetMenuBar(self.menuBar)
		self.list_label=wx.StaticText(self.panel, -1, label="Timelines")
		self.list=wx.ListBox(self.panel, -1)
		self.main_box.Add(self.list, 0, wx.ALL, 10)
		self.list.Bind(wx.EVT_LISTBOX, self.on_list_change)
		self.list.SetFocus()
		self.list2_label=wx.StaticText(self.panel, -1, label="Contents")
		self.list2=wx.ListBox(self.panel, -1,size=(1200,800))
		self.main_box.Add(self.list2, 0, wx.ALL, 10)
		self.list2.Bind(wx.EVT_LISTBOX, self.on_list2_change)
		accel=[]
		accel.append((wx.ACCEL_ALT, ord('X'), m_close.GetId()))
		if platform.system()=="Darwin":
			accel.append((wx.ACCEL_CTRL, ord(','), m_options.GetId()))
			accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord(','), m_account_options.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('N'), m_tweet.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('R'), m_reply.GetId()))
		accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord('R'), m_retweet.GetId()))
		if platform.system()=="Darwin":
			accel.append((wx.ACCEL_ALT, ord('Q'), m_quote.GetId()))
		else:
			accel.append((wx.ACCEL_CTRL, ord('Q'), m_quote.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('O'), m_url.GetId()))
		accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord('O'), m_tweet_url.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('D'), m_message.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('f'), m_follow.GetId()))
		accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord('f'), m_unfollow.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('b'), m_block.GetId()))
		accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord('b'), m_unblock.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('a'), m_accounts.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('i'), m_add_to_list.GetId()))
		accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord('i'), m_remove_from_list.GetId()))
		accel.append((wx.ACCEL_CTRL, ord("c"), m_copy.GetId()))
		accel.append((wx.ACCEL_NORMAL, wx.WXK_RETURN, m_view.GetId()))
		accel.append((wx.ACCEL_CTRL, wx.WXK_RETURN, m_play_external.GetId()))
		accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, wx.WXK_RETURN, m_stop_audio.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('U'), m_user_timeline.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('/'), m_search.GetId()))
		accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord('/'), m_user_search.GetId()))
		accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord('U'), m_user_profile.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('W'), self.m_close_timeline.GetId()))
		accel.append((wx.ACCEL_ALT, wx.WXK_PAGEUP, m_prev.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('h'), m_hide.GetId()))
		accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord('h'), m_manage_hide.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('L'), m_like.GetId()))
		accel.append((wx.ACCEL_CTRL, ord('G'), m_conversation.GetId()))
		accel.append((wx.ACCEL_CTRL, ord(';'), m_speak_user.GetId()))
		accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord(';'), m_speak_reply.GetId()))
		accel.append((wx.ACCEL_ALT, wx.WXK_UP, m_volup.GetId()))
		accel.append((wx.ACCEL_ALT, wx.WXK_DOWN, m_voldown.GetId()))
		accel.append((wx.ACCEL_CTRL, ord("e"), m_read.GetId()))
		if platform.system()=="Darwin":
			accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord("m"), m_mute.GetId()))
		else:
			accel.append((wx.ACCEL_CTRL, ord("m"), m_mute.GetId()))
		accel.append((wx.ACCEL_CTRL, wx.WXK_UP, m_previous_in_thread.GetId()))
		accel.append((wx.ACCEL_CTRL, wx.WXK_DOWN, m_next_in_thread.GetId()))
		accel.append((wx.ACCEL_CTRL, wx.WXK_LEFT, m_previous_from_user.GetId()))
		accel.append((wx.ACCEL_CTRL, wx.WXK_RIGHT, m_next_from_user.GetId()))
		accel.append((wx.ACCEL_ALT, wx.WXK_RIGHT, m_next_timeline.GetId()))
		accel.append((wx.ACCEL_ALT, wx.WXK_LEFT, m_prev_timeline.GetId()))
		accel.append((wx.ACCEL_CTRL, ord("["), m_followers.GetId()))
		accel.append((wx.ACCEL_CTRL, ord("]"), m_friends.GetId()))
		accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord("L"), m_lists.GetId()))
		accel.append((wx.ACCEL_CTRL|wx.ACCEL_SHIFT, ord("T"), m_custom_timelines.GetId()))
		accel.append((wx.ACCEL_NORMAL, wx.WXK_F5, m_refresh.GetId()))
		accel.append((wx.ACCEL_NORMAL, wx.WXK_DELETE, m_delete.GetId()))
		accel.append((wx.ACCEL_NORMAL, wx.WXK_F1, m_readme.GetId()))
		accel_tbl=wx.AcceleratorTable(accel)
		self.SetAcceleratorTable(accel_tbl)
		self.panel.Layout()

	def register_keys(self):
		self.invisible=True
		if platform.system()=="Darwin":
			f=open("keymac.keymap","r")
		else:
			f=open("keymap.keymap","r")
		keys=f.read().split("\n")
		f.close()
		for i in keys:
			key=i.strip(" ").split("=")
			success=invisible.register_key(key[0],key[1])

	def unregister_keys(self):
		self.invisible=False
		f=open("keymap.keymap","r")
		keys=f.read().split("\n")
		f.close()
		for i in keys:
			key=i.split("=")
			success=invisible.register_key(key[0],key[1],False)

	def get_current_status(self):
		"""Get the current status, handling conversation objects properly"""
		item = get_app().currentAccount.currentTimeline.statuses[get_app().currentAccount.currentTimeline.index]
		if get_app().currentAccount.currentTimeline.type == "conversations":
			# Conversations have last_status instead of being a status directly
			if hasattr(item, 'last_status') and item.last_status:
				return item.last_status
			return None
		return item

	def ToggleWindow(self):
		if self.IsShown():
			self.Show(False)
			get_app().prefs.window_shown=False
		else:
			self.Show(True)
			self.Raise()
			get_app().prefs.window_shown=True
			if not get_app().prefs.invisible_sync:
				self.list.SetSelection(get_app().currentAccount.currentIndex)
				self.on_list_change(None)
				self.list2.SetSelection(get_app().currentAccount.currentTimeline.index)
				self.on_list2_change(None)

	def OnReadme(self,event=None):
		webbrowser.open("https://github.com/masonasons/FastSM/blob/main/README.md")

	def OnRead(self,event=None):
		get_app().currentAccount.currentTimeline.toggle_read()

	def OnMute(self,event=None):
		get_app().currentAccount.currentTimeline.toggle_mute()

	def OnStats(self, event=None):
		txt=view.ViewTextGui("You have sent a total of "+str(get_app().prefs.posts_sent)+" posts, of which "+str(get_app().prefs.replies_sent)+" are replies and "+str(get_app().prefs.quotes_sent)+" are quotes.\r\nYou have boosted "+str(get_app().prefs.boosts_sent)+" posts, and favourited "+str(get_app().prefs.favourites_sent)+" posts.\r\nYou have sent "+str(get_app().prefs.chars_sent)+" characters from FastSM!\r\nYou have received "+str(get_app().prefs.statuses_received)+" posts in total through all of your timelines.")
		txt.Show()

	def OnErrors(self, event=None):
		errors=""
		for i in get_app().errors:
			errors+=i+"\r\n"
		txt=view.ViewTextGui(errors)
		txt.Show()

	def OnManageHide(self, event=None):
		gui=timelines.HiddenTimelinesGui(get_app().currentAccount)
		gui.Show()

	def OnCfu(self, event=None):
		get_app().cfu(False)

	def onCopy(self,event=None):
		status = self.get_current_status()
		if status:
			pyperclip.copy(get_app().template_to_string(status, get_app().prefs.copyTemplate))
			speak.speak("Copied")

	def OnClose(self, event=None):
		speak.speak("Exiting.")
		if platform.system()!="Darwin":
			self.trayicon.on_exit(event,False)
		self.Destroy()
		sys.exit()
	
	def OnPlayExternal(self,event=None):
		status = self.get_current_status()
		if status:
			thread=threading.Thread(target=misc.play_external,args=(status,)).start()

	def OnStopAudio(self,event=None):
		sound.stop()
		speak.speak("Stopped")

	def OnConversation(self,event=None):
		status = self.get_current_status()
		if status:
			misc.load_conversation(get_app().currentAccount, status)

	def OnDelete(self,event=None):
		status = self.get_current_status()
		if status:
			misc.delete(get_app().currentAccount, status)

	def OnHide(self,event=None):
		get_app().currentAccount.currentTimeline.hide_tl()

	def OnNextInThread(self,event=None):
		if not get_app().prefs.reversed:
			misc.next_in_thread(get_app().currentAccount)
		else:
			misc.previous_in_thread(get_app().currentAccount)

	def OnPreviousInThread(self,event=None):
		if not get_app().prefs.reversed:
			misc.previous_in_thread(get_app().currentAccount)
		else:
			misc.next_in_thread(get_app().currentAccount)

	def OnPreviousFromUser(self,event=None):
		misc.previous_from_user(get_app().currentAccount)

	def OnNextTimeline(self,event=None):
		invisible.inv.next_tl(True)

	def OnPrevTimeline(self,event=None):
		invisible.inv.prev_tl(True)

	def OnNextFromUser(self,event=None):
		misc.next_from_user(get_app().currentAccount)

	def OnSpeakUser(self,event=None):
		users=[]
		if get_app().currentAccount.currentTimeline.type=="conversations":
			# Handle conversations
			conv=get_app().currentAccount.currentTimeline.statuses[get_app().currentAccount.currentTimeline.index]
			if hasattr(conv, 'accounts'):
				for acc in conv.accounts:
					users.append(acc.acct)
		elif get_app().currentAccount.currentTimeline.type == "notifications":
			# Handle notifications only (mentions are now statuses)
			notif=get_app().currentAccount.currentTimeline.statuses[get_app().currentAccount.currentTimeline.index]
			if hasattr(notif, 'account'):
				users.append(notif.account.acct)
			if hasattr(notif, 'status') and notif.status:
				users.append(notif.status.account.acct)
		else:
			# Mentions now treated same as home/user/etc.
			status=get_app().currentAccount.currentTimeline.statuses[get_app().currentAccount.currentTimeline.index]
			users.append(status.account.acct)
			if hasattr(status,"quote") and status.quote and status.quote.account.acct not in users:
				users.insert(0,status.quote.account.acct)
			if hasattr(status,"reblog") and status.reblog and status.reblog.account.acct not in users:
				users.insert(0,status.reblog.account.acct)
			for i in get_app().get_user_objects_in_status(get_app().currentAccount,status):
				if i.acct not in users:
					users.append(i.acct)
		get_app().speak_user(get_app().currentAccount,users)

	def OnSpeakReply(self,event=None):
		status = self.get_current_status()
		if status:
			get_app().speak_reply(get_app().currentAccount, status)

	def refreshTimelines(self):
		old_selection=self.list.GetSelection()
		self.list.Clear()
		for i in get_app().currentAccount.list_timelines():
			self.list.Insert(i.name,self.list.GetCount())
		try:
			self.list.SetSelection(old_selection)
		except:
			self.list.SetSelection(1)

	def on_list_change(self, event):
		get_app().currentAccount.currentTimeline=get_app().currentAccount.list_timelines()[self.list.GetSelection()]
		get_app().currentAccount.currentIndex=self.list.GetSelection()
		if get_app().currentAccount.currentTimeline.removable:
			self.m_close_timeline.Enable(True)
		else:
			self.m_close_timeline.Enable(False)

		self.play_earcon()
		self.refreshList()

	def play_earcon(self):
		if get_app().prefs.earcon_top and (not get_app().prefs.reversed and get_app().currentAccount.currentTimeline.index > 0 or get_app().prefs.reversed and get_app().currentAccount.currentTimeline.index < len(get_app().currentAccount.currentTimeline.statuses) - 1):
			sound.play(get_app().currentAccount,"new")

	def OnFollowers(self,event=None):
		misc.followers(get_app().currentAccount)

	def OnFriends(self,event=None):
		misc.following(get_app().currentAccount)

	def OnMutualFollowing(self,event=None):
		misc.mutual_following(get_app().currentAccount)

	def OnNotFollowing(self,event=None):
		misc.not_following(get_app().currentAccount)

	def OnNotFollowingMe(self,event=None):
		misc.not_following_me(get_app().currentAccount)

	def OnHaventTweeted(self,event=None):
		misc.havent_tweeted(get_app().currentAccount)

	def refreshList(self):
		stuffage=get_app().currentAccount.currentTimeline.get()
		self.list2.Freeze()
		self.list2.Clear()
		for i in stuffage:
			self.list2.Insert(i,self.list2.GetCount())
		try:
			self.list2.SetSelection(get_app().currentAccount.currentTimeline.index)
		except:
			self.list2.SetSelection(get_app().currentAccount.currentTimeline.index-1)
		self.list2.Thaw()

	def OnViewUserDb(self, event=None):
		u=view.UserViewGui(get_app().currentAccount,get_app().users,"User Database containing "+str(len(get_app().users))+" users.")
		u.Show()

	def OnCleanUserDb(self, event=None):
		get_app().clean_users()
		get_app().save_users()

	def on_list2_change(self, event):
		get_app().currentAccount.currentTimeline.index=self.list2.GetSelection()
		status = self.get_current_status()
		if status and get_app().prefs.earcon_audio and len(sound.get_media_urls(get_app().find_urls_in_status(status))) > 0:
			sound.play(get_app().currentAccount,"media")

	def onRefresh(self,event=None):
		threading.Thread(target=get_app().currentAccount.currentTimeline.load, daemon=True).start()

	def add_to_list(self,list):
		self.list2.Freeze()
		for i in list:
			self.list2.Insert(i,0)
		self.list2.Thaw()

	def append_to_list(self,list):
		self.list2.Freeze()
		for i in list:
			self.list2.Insert(i,self.list2.GetCount())
		self.list2.Thaw()

	def OnView(self,event=None):
		status = self.get_current_status()
		if status:
			viewer = view.ViewGui(get_app().currentAccount, status)
			viewer.Show()
		else:
			speak.speak("No messages in this conversation")

	def onPrev(self,event=None):
		threading.Thread(target=get_app().currentAccount.currentTimeline.load, args=(True,), daemon=True).start()

	def OnVolup(self, event=None):
		if get_app().prefs.volume<1.0:
			get_app().prefs.volume+=0.1
			get_app().prefs.volume=round(get_app().prefs.volume,1)
			sound.play(get_app().currentAccount,"volume_changed")

	def OnVoldown(self, event=None):
		if get_app().prefs.volume>0.0:
			get_app().prefs.volume-=0.1
			get_app().prefs.volume=round(get_app().prefs.volume,1)
			sound.play(get_app().currentAccount,"volume_changed")

	def OnOptions(self, event=None):
		Opt=options.OptionsGui()
		Opt.Show()

	def OnAccountOptions(self, event=None):
		Opt=account_options.OptionsGui(get_app().currentAccount)
		Opt.Show()

	def OnUpdateProfile(self, event=None):
		Profile=profile.ProfileGui(get_app().currentAccount)
		Profile.Show()

	def OnAccounts(self, event=None):
		acc=accounts.AccountsGui()
		acc.Show()

	def OnTweet(self, event=None):
		NewTweet=tweet.TweetGui(get_app().currentAccount)
		NewTweet.Show()

	# Alias for invisible interface
	OnPost = OnTweet

	def OnUserTimeline(self, event=None):
		status = self.get_current_status()
		if status:
			misc.user_timeline(get_app().currentAccount, status)

	def OnSearch(self, event=None):
		s=search.SearchGui(get_app().currentAccount)
		s.Show()

	def OnUserSearch(self, event=None):
		s=search.SearchGui(get_app().currentAccount,"user")
		s.Show()

	def OnLists(self, event=None):
		s=lists.ListsGui(get_app().currentAccount)
		s.Show()

	def OnCustomTimelines(self, event=None):
		s=custom_timelines.CustomTimelinesDialog(get_app().currentAccount)
		s.Show()

	def OnUserProfile(self, event=None):
		status = self.get_current_status()
		if status:
			misc.user_profile(get_app().currentAccount, status)

	def OnUrl(self, event=None):
		status = self.get_current_status()
		if status:
			misc.url_chooser(get_app().currentAccount, status)

	def OnTweetUrl(self, event=None):
		status = self.get_current_status()
		if not status:
			return
		# Get the URL from the status, or construct it
		url = getattr(status, 'url', None)
		if not url:
			# For notifications, get the status URL
			if hasattr(status, 'status') and status.status:
				url = getattr(status.status, 'url', None)
			# For reblogs, get the reblogged status URL
			if not url and hasattr(status, 'reblog') and status.reblog:
				url = getattr(status.reblog, 'url', None)
			if not url and hasattr(status, 'account'):
				# Construct URL based on platform
				platform_type = getattr(get_app().currentAccount.prefs, 'platform_type', 'mastodon')
				if platform_type == 'bluesky':
					# Bluesky URL format: https://bsky.app/profile/{handle}/post/{rkey}
					handle = getattr(status.account, 'acct', '') or getattr(status.account, 'handle', '')
					# Extract rkey from AT URI (at://did/app.bsky.feed.post/rkey)
					status_id = status.id
					if '/' in str(status_id):
						rkey = str(status_id).split('/')[-1]
						# Remove :repost suffix if present
						rkey = rkey.replace(':repost', '')
					else:
						rkey = status_id
					url = f"https://bsky.app/profile/{handle}/post/{rkey}"
				else:
					# Mastodon URL format
					url = f"{get_app().currentAccount.prefs.instance_url}/@{status.account.acct}/{status.id}"
		if url:
			if platform.system()!="Darwin":
				webbrowser.open(url)
			else:
				os.system("open "+url)

	# Alias for invisible interface
	OnPostUrl = OnTweetUrl

	def OnFollow(self, event=None):
		status = self.get_current_status()
		if status:
			misc.follow(get_app().currentAccount, status)

	def OnAddToList(self, event=None):
		status = self.get_current_status()
		if status:
			misc.add_to_list(get_app().currentAccount, status)

	def OnRemoveFromList(self, event=None):
		status = self.get_current_status()
		if status:
			misc.remove_from_list(get_app().currentAccount, status)

	def OnUnfollow(self, event=None):
		status = self.get_current_status()
		if status:
			misc.unfollow(get_app().currentAccount, status)

	def OnBlock(self, event=None):
		status = self.get_current_status()
		if status:
			misc.block(get_app().currentAccount, status)

	def OnUnblock(self, event=None):
		status = self.get_current_status()
		if status:
			misc.unblock(get_app().currentAccount, status)

	def OnMuteUser(self, event=None):
		status = self.get_current_status()
		if status:
			misc.mute(get_app().currentAccount, status)

	def OnUnmuteUser(self, event=None):
		status = self.get_current_status()
		if status:
			misc.unmute(get_app().currentAccount, status)

	def OnCloseTimeline(self, event=None):
		tl=get_app().currentAccount.currentTimeline
		if tl.removable:
			if get_app().prefs.ask_dismiss:
				dlg=wx.MessageDialog(None,"Are you sure you wish to close "+tl.name+"?","Warning",wx.YES_NO | wx.ICON_QUESTION)
				result=dlg.ShowModal()
				dlg.Destroy()
			if not get_app().prefs.ask_dismiss or get_app().prefs.ask_dismiss and result== wx.ID_YES:
				if tl.type=="user" and tl.data in get_app().currentAccount.prefs.user_timelines:
					get_app().currentAccount.prefs.user_timelines.remove(tl.data)
				if tl.type=="list":
					get_app().currentAccount.prefs.list_timelines = [
						item for item in get_app().currentAccount.prefs.list_timelines
						if item.get('id') != tl.data
					]
				if tl.type=="search" and tl.data in get_app().currentAccount.prefs.search_timelines:
					get_app().currentAccount.prefs.search_timelines.remove(tl.data)
				if tl.type in ("feed", "local", "federated"):
					# Remove from custom_timelines
					get_app().currentAccount.prefs.custom_timelines = [
						ct for ct in get_app().currentAccount.prefs.custom_timelines
						if not (ct.get('type') == tl.type and ct.get('id') == tl.data)
					]
				if tl.type == "instance":
					# Remove from instance_timelines
					get_app().currentAccount.prefs.instance_timelines = [
						inst for inst in get_app().currentAccount.prefs.instance_timelines
						if inst.get('url') != tl.data
					]
				get_app().currentAccount.timelines.remove(tl)
				sound.play(get_app().currentAccount,"close")
				self.refreshTimelines()
				self.list.SetSelection(0)
				get_app().currentAccount.currentIndex=0
				self.on_list_change(None)
				del tl

	def OnReply(self, event=None):
		if get_app().currentAccount.currentTimeline.type=="conversations":
			self.OnMessage(None)
		else:
			status = self.get_current_status()
			if status:
				misc.reply(get_app().currentAccount, status)

	def OnQuote(self, event=None):
		if get_app().currentAccount.currentTimeline.type=="conversations":
			self.OnMessage(None)
		else:
			status = self.get_current_status()
			if status:
				misc.quote(get_app().currentAccount, status)

	def OnMessage(self, event=None):
		status = self.get_current_status()
		if status:
			misc.message(get_app().currentAccount, status)

	def OnRetweet(self, event=None):
		status = self.get_current_status()
		if status:
			misc.boost(get_app().currentAccount, status)

	# Alias for invisible interface
	OnBoost = OnRetweet

	def OnLike(self, event=None):
		status = self.get_current_status()
		if status:
			misc.favourite(get_app().currentAccount, status)

global window
window=MainGui(application.name+" "+application.version)
