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
from . import account_options, accounts, chooser, custom_timelines, invisible, lists, misc, options, profile, search, timeline_filter, timelines, tray, tweet, view
import sound
import timeline
import threading

class MainGui(wx.Frame):
	def __init__(self, title):
		self.invisible=False
		self._find_text = ""  # Current search text for find in timeline
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

		menu = wx.Menu()
		m_accounts = menu.Append(-1, "Accounts\tCtrl+A", "accounts")
		self.Bind(wx.EVT_MENU, self.OnAccounts, m_accounts)
		m_update_profile = menu.Append(-1, "Update profile", "profile")
		self.Bind(wx.EVT_MENU, self.OnUpdateProfile, m_update_profile)
		m_lists = menu.Append(-1, "Lists\tCtrl+Shift+L", "lists")
		self.Bind(wx.EVT_MENU, self.OnLists, m_lists)
		m_custom_timelines = menu.Append(-1, "Add Custom Timeline\tCtrl+Shift+T", "custom_timelines")
		self.Bind(wx.EVT_MENU, self.OnCustomTimelines, m_custom_timelines)
		m_filter_timeline = menu.Append(-1, "Client Filters\tCtrl+Shift+F", "filter_timeline")
		self.Bind(wx.EVT_MENU, self.OnFilterTimeline, m_filter_timeline)
		m_server_filters = menu.Append(-1, "Server Filters", "server_filters")
		self.Bind(wx.EVT_MENU, self.OnServerFilters, m_server_filters)
		m_followers = menu.Append(-1, "List Followers\tCtrl+[", "followers")
		self.Bind(wx.EVT_MENU, self.OnFollowers, m_followers)
		m_friends = menu.Append(-1, "List Following\tCtrl+]", "following")
		self.Bind(wx.EVT_MENU, self.OnFriends, m_friends)
		m_options = menu.Append(wx.ID_PREFERENCES, "Global Options\tCtrl+,", "options")
		self.Bind(wx.EVT_MENU, self.OnOptions, m_options)
		m_account_options = menu.Append(-1, "Account options\tCtrl+Shift+,", "account_options")
		self.Bind(wx.EVT_MENU, self.OnAccountOptions, m_account_options)
		m_close = menu.Append(wx.ID_EXIT, "Exit\tAlt+X", "exit")
		self.Bind(wx.EVT_MENU, self.OnClose, m_close)
		self.menuBar.Append(menu, "&Application")
		menu2 = wx.Menu()
		m_tweet = menu2.Append(-1, "New post\tCtrl+N", "post")
		self.Bind(wx.EVT_MENU, self.OnTweet, m_tweet)
		m_reply = menu2.Append(-1, "Reply\tCtrl+R", "reply")
		self.Bind(wx.EVT_MENU, self.OnReply, m_reply)
		m_edit = menu2.Append(-1, "Edit\tCtrl+E", "edit")
		self.Bind(wx.EVT_MENU, self.OnEdit, m_edit)
		m_retweet = menu2.Append(-1, "Boost\tCtrl+Shift+R", "boost")
		self.Bind(wx.EVT_MENU, self.OnRetweet, m_retweet)
		if platform.system()=="Darwin":
			m_quote = menu2.Append(-1, "Quote\tAlt+Q", "quote")
		else:
			m_quote = menu2.Append(-1, "Quote\tCtrl+Q", "quote")
		self.Bind(wx.EVT_MENU, self.OnQuote, m_quote)
		m_like=menu2.Append(-1, "Like\tCtrl+K", "favourite")
		self.Bind(wx.EVT_MENU, self.OnLike, m_like)
		m_unlike=menu2.Append(-1, "Unlike\tCtrl+Shift+K", "unfavourite")
		self.Bind(wx.EVT_MENU, self.OnUnlike, m_unlike)
		m_url=menu2.Append(-1, "Open URL\tCtrl+O", "url")
		self.Bind(wx.EVT_MENU, self.OnUrl, m_url)
		m_tweet_url=menu2.Append(-1, "Open URL of Post\tCtrl+Shift+O", "post_url")
		self.Bind(wx.EVT_MENU, self.OnTweetUrl, m_tweet_url)
		m_delete = menu2.Append(-1, "Delete Post" if platform.system() == "Darwin" else "Delete Post\tDelete", "post")
		self.Bind(wx.EVT_MENU, self.OnDelete, m_delete)
		m_copy = menu2.Append(-1, "Copy post to clipboard\tCtrl+C", "copy")
		self.Bind(wx.EVT_MENU, self.onCopy, m_copy)
		m_message=menu2.Append(-1, "Send message\tCtrl+D", "message")
		self.Bind(wx.EVT_MENU, self.OnMessage, m_message)
		m_follow=menu2.Append(-1, "Follow\tCtrl+L", "follow")
		self.Bind(wx.EVT_MENU, self.OnFollow, m_follow)
		m_unfollow=menu2.Append(-1, "Unfollow\tCtrl+Shift+L", "follow")
		self.Bind(wx.EVT_MENU, self.OnUnfollow, m_unfollow)
		m_add_to_list=menu2.Append(-1, "Add to list\tCtrl+I", "addlist")
		self.Bind(wx.EVT_MENU, self.OnAddToList, m_add_to_list)
		m_remove_from_list=menu2.Append(-1, "Remove from list\tCtrl+Shift+I", "removelist")
		self.Bind(wx.EVT_MENU, self.OnRemoveFromList, m_remove_from_list)
		m_block=menu2.Append(-1, "Block\tCtrl+B", "block")
		self.Bind(wx.EVT_MENU, self.OnBlock, m_block)
		m_unblock=menu2.Append(-1, "Unblock\tCtrl+Shift+B", "unblock")
		self.Bind(wx.EVT_MENU, self.OnUnblock, m_unblock)
		m_mute_user=menu2.Append(-1, "Mute", "mute")
		self.Bind(wx.EVT_MENU, self.OnMuteUser, m_mute_user)
		m_unmute_user=menu2.Append(-1, "Unmute", "unmute")
		self.Bind(wx.EVT_MENU, self.OnUnmuteUser, m_unmute_user)
		m_view=menu2.Append(-1, "View post" if platform.system() == "Darwin" else "View post\tReturn", "view")
		self.Bind(wx.EVT_MENU, self.OnView, m_view)
		m_user_profile=menu2.Append(-1, "User Profile\tCtrl+Shift+U", "profile")
		self.Bind(wx.EVT_MENU, self.OnUserProfile, m_user_profile)
		m_speak_user=menu2.Append(-1, "Speak user\tCtrl+;", "speak")
		self.Bind(wx.EVT_MENU, self.OnSpeakUser, m_speak_user)
		m_speak_reply=menu2.Append(-1, "Speak reference post of this reply\tCtrl+Shift+;", "speak2")
		self.Bind(wx.EVT_MENU, self.OnSpeakReply, m_speak_reply)
		m_conversation=menu2.Append(-1, "Load conversation/related posts\tCtrl+G", "conversation")
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
		m_refresh = menu3.Append(-1, "Refresh timeline\tF5", "refresh")
		self.Bind(wx.EVT_MENU, self.onRefresh, m_refresh)
		m_prev = menu3.Append(-1, "Load older posts\tAlt+PgUp", "prev")
		self.Bind(wx.EVT_MENU, self.onPrev, m_prev)
		m_hide = menu3.Append(-1, "Hide Timeline\tCtrl+H", "hide")
		self.Bind(wx.EVT_MENU, self.OnHide, m_hide)
		m_manage_hide = menu3.Append(-1, "Manage hidden Timelines\tCtrl+Shift+H", "manage_hide")
		self.Bind(wx.EVT_MENU, self.OnManageHide, m_manage_hide)
		m_read = menu3.Append(-1, "Toggle autoread\tCtrl+Shift+E", "autoread")
		self.Bind(wx.EVT_MENU, self.OnRead, m_read)
		if platform.system()!="Darwin":
			m_mute = menu3.Append(-1, "Toggle mute\tCtrl+M", "mute")
		else:
			m_mute = menu3.Append(-1, "Toggle mute\tCtrl+Shift+M", "mute")
		self.Bind(wx.EVT_MENU, self.OnMute, m_mute)
		m_user_timeline = menu3.Append(-1, "User timeline\tCtrl+U", "user")
		self.Bind(wx.EVT_MENU, self.OnUserTimeline, m_user_timeline)
		m_search = menu3.Append(-1, "Search\tCtrl+/", "search")
		self.Bind(wx.EVT_MENU, self.OnSearch, m_search)
		m_user_search = menu3.Append(-1, "User Search\tCtrl+Shift+/", "search")
		self.Bind(wx.EVT_MENU, self.OnUserSearch, m_user_search)
		m_find = menu3.Append(-1, "Find in timeline\tF3", "find")
		self.Bind(wx.EVT_MENU, self.OnFind, m_find)
		self.m_close_timeline = menu3.Append(-1, "Close timeline\tCtrl+W", "removetimeline")
		self.m_close_timeline.Enable(False)
		self.Bind(wx.EVT_MENU, self.OnCloseTimeline, self.m_close_timeline)
		self.menuBar.Append(menu3, "Time&line")
		menu4 = wx.Menu()
		m_play_external = menu4.Append(-1, "Play media" if platform.system() == "Darwin" else "Play media\tCtrl+Return", "play_external")
		self.Bind(wx.EVT_MENU, self.OnPlayExternal, m_play_external)
		m_stop_audio = menu4.Append(-1, "Stop audio" if platform.system() == "Darwin" else "Stop audio\tCtrl+Shift+Return", "stop_audio")
		self.Bind(wx.EVT_MENU, self.OnStopAudio, m_stop_audio)
		m_volup = menu4.Append(-1, "Volume up\tAlt+Up", "volup")
		self.Bind(wx.EVT_MENU, self.OnVolup, m_volup)
		m_voldown = menu4.Append(-1, "Volume down\tAlt+Down", "voldown")
		self.Bind(wx.EVT_MENU, self.OnVoldown, m_voldown)
		self.menuBar.Append(menu4, "A&udio")
		menu5 = wx.Menu()
		m_previous_in_thread = menu5.Append(-1, "Previous post in thread\tCtrl+Up", "prevpost")
		self.Bind(wx.EVT_MENU, self.OnPreviousInThread, m_previous_in_thread)
		m_next_in_thread = menu5.Append(-1, "Next post in thread\tCtrl+Down", "nextpost")
		self.Bind(wx.EVT_MENU, self.OnNextInThread, m_next_in_thread)
		m_previous_from_user = menu5.Append(-1, "Previous post from user\tCtrl+Left", "prevuser")
		self.Bind(wx.EVT_MENU, self.OnPreviousFromUser, m_previous_from_user)
		m_next_from_user = menu5.Append(-1, "Next post from user\tCtrl+Right", "nextuser")
		self.Bind(wx.EVT_MENU, self.OnNextFromUser, m_next_from_user)
		m_next_timeline = menu5.Append(-1, "Next timeline\tAlt+Right", "nexttl")
		self.Bind(wx.EVT_MENU, self.OnNextTimeline, m_next_timeline)
		m_prev_timeline = menu5.Append(-1, "Previous timeline\tAlt+Left", "prevtl")
		self.Bind(wx.EVT_MENU, self.OnPrevTimeline, m_prev_timeline)
		self.menuBar.Append(menu5, "Navigation")
		menu6 = wx.Menu()
		m_readme = menu6.Append(-1, "Readme\tF1", "readme")
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

		# Add accelerator for context menu (Alt+M) - not on Mac due to focus issues
		if platform.system() != "Darwin":
			self.context_menu_id = wx.NewIdRef()
			self.Bind(wx.EVT_MENU, self.OnPostContextMenu, id=self.context_menu_id)
			accel = wx.AcceleratorTable([
				(wx.ACCEL_ALT, ord('M'), self.context_menu_id),
			])
			self.SetAcceleratorTable(accel)

		self.list_label=wx.StaticText(self.panel, -1, label="Timelines")
		self.list=wx.ListBox(self.panel, -1)
		self.main_box.Add(self.list, 0, wx.ALL, 10)
		self.list.Bind(wx.EVT_LISTBOX, self.on_list_change)
		self.list.SetFocus()
		self.list2_label=wx.StaticText(self.panel, -1, label="Contents")
		self.list2=wx.ListBox(self.panel, -1,size=(1200,800))
		self.main_box.Add(self.list2, 0, wx.ALL, 10)
		self.list2.Bind(wx.EVT_LISTBOX, self.on_list2_change)
		self.list2.Bind(wx.EVT_CONTEXT_MENU, self.OnPostContextMenu)
		# On Mac, bind key events directly to list controls for shortcuts
		# (menu accelerators are disabled on Mac to prevent firing in dialogs)
		if platform.system() == "Darwin":
			self.list2.Bind(wx.EVT_KEY_DOWN, self.OnListKeyDown)
			self.list.Bind(wx.EVT_KEY_DOWN, self.OnListKeyDown)
			# Use CHAR_HOOK for Option+M since it produces special characters
			self.list2.Bind(wx.EVT_CHAR_HOOK, self.OnListCharHook)
			self.list.Bind(wx.EVT_CHAR_HOOK, self.OnListCharHook)
		self.panel.Layout()

	def register_keys(self):
		# Invisible hotkeys not supported on Mac
		if platform.system() == "Darwin":
			self.invisible = False
			return
		self.invisible=True
		f=open("keymap.keymap","r")
		keys=f.read().split("\n")
		f.close()
		for i in keys:
			key=i.strip(" ").split("=")
			success=invisible.register_key(key[0],key[1])

	def unregister_keys(self):
		# Invisible hotkeys not supported on Mac
		if platform.system() == "Darwin":
			return
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
		# Window hiding not supported on Mac
		if platform.system() == "Darwin":
			self.Raise()
			return
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

	def OnListCharHook(self, event):
		"""Handle char hook for Option+M on Mac (context menu)."""
		key = event.GetKeyCode()
		# Use Option+M for context menu on Mac
		if event.AltDown() and not event.RawControlDown() and not event.ShiftDown():
			if key == ord('M') or key == ord('m'):
				self.OnPostContextMenu(None)
				return  # Don't skip - consume the event
		event.Skip()

	def OnListKeyDown(self, event):
		"""Handle key events for list controls on Mac."""
		key = event.GetKeyCode()
		mods = event.GetModifiers()

		if key == wx.WXK_RETURN:
			if mods == wx.MOD_CONTROL | wx.MOD_SHIFT:
				self.OnStopAudio()
			elif mods == wx.MOD_CONTROL:
				self.OnPlayExternal()
			elif mods == 0:
				self.OnView()
			else:
				event.Skip()
		elif key == wx.WXK_DELETE or key == wx.WXK_BACK:
			if mods == 0:
				self.OnDelete()
			else:
				event.Skip()
		else:
			event.Skip()

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
			# Use appropriate template based on status type
			if hasattr(status, 'reblog') and status.reblog:
				# For boosts, use boost template (without timestamp for copy)
				template = get_app().prefs.boostTemplate.replace(" $created_at$", "").replace("$created_at$ ", "").replace("$created_at$", "")
			else:
				template = get_app().prefs.copyTemplate
			pyperclip.copy(get_app().template_to_string(status, template))
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
			self.list2.Append(i)
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

	def OnPostContextMenu(self, event=None):
		"""Show context menu for posts list - context-aware based on timeline type."""
		# Make sure we have a valid selection
		if self.list2.GetSelection() < 0:
			return

		menu = wx.Menu()
		tl_type = get_app().currentAccount.currentTimeline.type
		item = get_app().currentAccount.currentTimeline.statuses[get_app().currentAccount.currentTimeline.index]

		if tl_type == "conversations":
			# Conversations menu - focused on opening/replying to DMs
			m_open = menu.Append(-1, "Open conversation")
			self.Bind(wx.EVT_MENU, self.OnConversation, m_open)

			m_reply = menu.Append(-1, "Reply")
			self.Bind(wx.EVT_MENU, self.OnMessage, m_reply)

			menu.AppendSeparator()

			m_copy = menu.Append(-1, "Copy to clipboard")
			self.Bind(wx.EVT_MENU, self.onCopy, m_copy)

			menu.AppendSeparator()

			# User options for conversation participants
			m_user_profile = menu.Append(-1, "User profile")
			self.Bind(wx.EVT_MENU, self.OnUserProfile, m_user_profile)

			m_user_tl = menu.Append(-1, "User timeline")
			self.Bind(wx.EVT_MENU, self.OnUserTimeline, m_user_tl)

			menu.AppendSeparator()

			m_follow = menu.Append(-1, "Follow")
			self.Bind(wx.EVT_MENU, self.OnFollow, m_follow)

			m_unfollow = menu.Append(-1, "Unfollow")
			self.Bind(wx.EVT_MENU, self.OnUnfollow, m_unfollow)

			m_mute = menu.Append(-1, "Mute user")
			self.Bind(wx.EVT_MENU, self.OnMuteUser, m_mute)

			m_unmute = menu.Append(-1, "Unmute user")
			self.Bind(wx.EVT_MENU, self.OnUnmuteUser, m_unmute)

		elif tl_type == "notifications":
			# Check notification type
			notif_type = getattr(item, 'type', '')

			if notif_type == 'follow_request':
				# Follow request - show accept/reject first
				m_accept = menu.Append(-1, "Accept follow request")
				self.Bind(wx.EVT_MENU, self.OnAcceptFollowRequest, m_accept)

				m_reject = menu.Append(-1, "Reject follow request")
				self.Bind(wx.EVT_MENU, self.OnRejectFollowRequest, m_reject)

				menu.AppendSeparator()

				m_user_profile = menu.Append(-1, "User profile")
				self.Bind(wx.EVT_MENU, self.OnUserProfile, m_user_profile)

				m_user_tl = menu.Append(-1, "User timeline")
				self.Bind(wx.EVT_MENU, self.OnUserTimeline, m_user_tl)

				menu.AppendSeparator()

				m_block = menu.Append(-1, "Block user")
				self.Bind(wx.EVT_MENU, self.OnBlockUser, m_block)

			elif notif_type == 'follow':
				# Follow notifications - user-focused options only
				m_user_profile = menu.Append(-1, "User profile")
				self.Bind(wx.EVT_MENU, self.OnUserProfile, m_user_profile)

				m_user_tl = menu.Append(-1, "User timeline")
				self.Bind(wx.EVT_MENU, self.OnUserTimeline, m_user_tl)

				menu.AppendSeparator()

				m_follow = menu.Append(-1, "Follow back")
				self.Bind(wx.EVT_MENU, self.OnFollow, m_follow)

				m_unfollow = menu.Append(-1, "Unfollow")
				self.Bind(wx.EVT_MENU, self.OnUnfollow, m_unfollow)

				menu.AppendSeparator()

				m_mute = menu.Append(-1, "Mute user")
				self.Bind(wx.EVT_MENU, self.OnMuteUser, m_mute)

				m_unmute = menu.Append(-1, "Unmute user")
				self.Bind(wx.EVT_MENU, self.OnUnmuteUser, m_unmute)

				m_block = menu.Append(-1, "Block user")
				self.Bind(wx.EVT_MENU, self.OnBlockUser, m_block)

				m_unblock = menu.Append(-1, "Unblock user")
				self.Bind(wx.EVT_MENU, self.OnUnblockUser, m_unblock)
			else:
				# Notifications with posts (favourite, reblog, mention, etc.)
				m_view = menu.Append(-1, "View post")
				self.Bind(wx.EVT_MENU, self.OnView, m_view)

				m_reply = menu.Append(-1, "Reply")
				self.Bind(wx.EVT_MENU, self.OnReply, m_reply)

				m_boost = menu.Append(-1, "Boost")
				self.Bind(wx.EVT_MENU, self.OnRetweet, m_boost)

				m_fav = menu.Append(-1, "Favourite")
				self.Bind(wx.EVT_MENU, self.OnLike, m_fav)

				menu.AppendSeparator()

				m_copy = menu.Append(-1, "Copy to clipboard")
				self.Bind(wx.EVT_MENU, self.onCopy, m_copy)

				m_url = menu.Append(-1, "Open URL in post")
				self.Bind(wx.EVT_MENU, self.OnUrl, m_url)

				m_post_url = menu.Append(-1, "Open post URL")
				self.Bind(wx.EVT_MENU, self.OnTweetUrl, m_post_url)

				menu.AppendSeparator()

				m_user_tl = menu.Append(-1, "User timeline")
				self.Bind(wx.EVT_MENU, self.OnUserTimeline, m_user_tl)

				m_user_profile = menu.Append(-1, "User profile")
				self.Bind(wx.EVT_MENU, self.OnUserProfile, m_user_profile)

				m_conversation = menu.Append(-1, "Load conversation")
				self.Bind(wx.EVT_MENU, self.OnConversation, m_conversation)

				menu.AppendSeparator()

				m_follow = menu.Append(-1, "Follow")
				self.Bind(wx.EVT_MENU, self.OnFollow, m_follow)

				m_unfollow = menu.Append(-1, "Unfollow")
				self.Bind(wx.EVT_MENU, self.OnUnfollow, m_unfollow)

		else:
			# Standard post menu for all other timelines
			m_view = menu.Append(-1, "View post")
			self.Bind(wx.EVT_MENU, self.OnView, m_view)

			m_reply = menu.Append(-1, "Reply")
			self.Bind(wx.EVT_MENU, self.OnReply, m_reply)

			m_boost = menu.Append(-1, "Boost")
			self.Bind(wx.EVT_MENU, self.OnRetweet, m_boost)

			m_quote = menu.Append(-1, "Quote")
			self.Bind(wx.EVT_MENU, self.OnQuote, m_quote)

			m_fav = menu.Append(-1, "Favourite")
			self.Bind(wx.EVT_MENU, self.OnLike, m_fav)

			menu.AppendSeparator()

			m_copy = menu.Append(-1, "Copy to clipboard")
			self.Bind(wx.EVT_MENU, self.onCopy, m_copy)

			m_url = menu.Append(-1, "Open URL in post")
			self.Bind(wx.EVT_MENU, self.OnUrl, m_url)

			m_post_url = menu.Append(-1, "Open post URL")
			self.Bind(wx.EVT_MENU, self.OnTweetUrl, m_post_url)

			menu.AppendSeparator()

			m_user_tl = menu.Append(-1, "User timeline")
			self.Bind(wx.EVT_MENU, self.OnUserTimeline, m_user_tl)

			m_user_profile = menu.Append(-1, "User profile")
			self.Bind(wx.EVT_MENU, self.OnUserProfile, m_user_profile)

			m_conversation = menu.Append(-1, "Load conversation")
			self.Bind(wx.EVT_MENU, self.OnConversation, m_conversation)

			menu.AppendSeparator()

			m_follow = menu.Append(-1, "Follow")
			self.Bind(wx.EVT_MENU, self.OnFollow, m_follow)

			m_unfollow = menu.Append(-1, "Unfollow")
			self.Bind(wx.EVT_MENU, self.OnUnfollow, m_unfollow)

			m_mute = menu.Append(-1, "Mute user")
			self.Bind(wx.EVT_MENU, self.OnMuteUser, m_mute)

			m_unmute = menu.Append(-1, "Unmute user")
			self.Bind(wx.EVT_MENU, self.OnUnmuteUser, m_unmute)

			menu.AppendSeparator()

			m_delete = menu.Append(-1, "Delete")
			self.Bind(wx.EVT_MENU, self.OnDelete, m_delete)

		self.PopupMenu(menu)
		menu.Destroy()

	def onPrev(self,event=None):
		tl = get_app().currentAccount.currentTimeline
		if tl._loading_all_active:
			tl.stop_loading_all()
		elif get_app().prefs.load_all_previous:
			threading.Thread(target=tl.load_all_previous, daemon=True).start()
		else:
			threading.Thread(target=tl.load, args=(True,), daemon=True).start()

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

	def OnFind(self, event=None):
		"""Find text in the current timeline."""
		tl = get_app().currentAccount.currentTimeline
		if not tl.statuses:
			speak.speak("No posts to search")
			return

		# Show dialog to get search text
		# On Mac, use None as parent to avoid menu state issues
		parent = None if platform.system() == "Darwin" else self
		dlg = wx.TextEntryDialog(parent, "Enter text to find:", "Find in Timeline", self._find_text)
		if dlg.ShowModal() != wx.ID_OK:
			dlg.Destroy()
			return

		search_text = dlg.GetValue().strip().lower()
		dlg.Destroy()

		if not search_text:
			speak.speak("No search text entered")
			return

		# If search text changed, start from beginning; otherwise continue from current position
		if search_text != self._find_text:
			start_index = 0
		else:
			start_index = tl.index + 1

		self._find_text = search_text

		# Get displayed text for each post
		displayed = tl.get()

		# Search from start_index, wrapping around
		found = False
		for offset in range(len(displayed)):
			idx = (start_index + offset) % len(displayed)
			if search_text in displayed[idx].lower():
				# Found a match
				tl.index = idx
				self.list2.SetSelection(idx)
				self.on_list2_change(None)
				speak.speak(displayed[idx])
				found = True
				break

		if not found:
			speak.speak(f"Not found: {self._find_text}")

	def OnLists(self, event=None):
		s=lists.ListsGui(get_app().currentAccount)
		s.Show()

	def OnCustomTimelines(self, event=None):
		s=custom_timelines.CustomTimelinesDialog(get_app().currentAccount)
		s.Show()

	def OnFilterTimeline(self, event=None):
		timeline_filter.show_filter_dialog(get_app().currentAccount)

	def OnServerFilters(self, event=None):
		from . import server_filters
		server_filters.show_server_filters_dialog(get_app().currentAccount)

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

	def OnBlockUser(self, event=None):
		status = self.get_current_status()
		if status:
			misc.block(get_app().currentAccount, status)

	def OnUnblockUser(self, event=None):
		status = self.get_current_status()
		if status:
			misc.unblock(get_app().currentAccount, status)

	def OnAcceptFollowRequest(self, event=None):
		"""Accept a follow request from the notifications timeline."""
		account = get_app().currentAccount
		if account.currentTimeline.type != "notifications":
			return
		item = account.currentTimeline.statuses[account.currentTimeline.index]
		if getattr(item, 'type', '') != 'follow_request':
			return
		user = getattr(item, 'account', None)
		if not user:
			return
		try:
			if hasattr(account, 'accept_follow_request'):
				account.accept_follow_request(user.id)
				speak.speak(f"Accepted follow request from {user.acct}")
				sound.play(account, "like")
			else:
				speak.speak("This platform does not support follow requests")
		except Exception as error:
			account.app.handle_error(error, "accept follow request")

	def OnRejectFollowRequest(self, event=None):
		"""Reject a follow request from the notifications timeline."""
		account = get_app().currentAccount
		if account.currentTimeline.type != "notifications":
			return
		item = account.currentTimeline.statuses[account.currentTimeline.index]
		if getattr(item, 'type', '') != 'follow_request':
			return
		user = getattr(item, 'account', None)
		if not user:
			return
		try:
			if hasattr(account, 'reject_follow_request'):
				account.reject_follow_request(user.id)
				speak.speak(f"Rejected follow request from {user.acct}")
			else:
				speak.speak("This platform does not support follow requests")
		except Exception as error:
			account.app.handle_error(error, "reject follow request")

	def OnCloseTimeline(self, event=None):
		tl=get_app().currentAccount.currentTimeline
		if tl.removable:
			if get_app().prefs.ask_dismiss:
				dlg=wx.MessageDialog(None,"Are you sure you wish to close "+tl.name+"?","Warning",wx.YES_NO | wx.ICON_QUESTION)
				result=dlg.ShowModal()
				dlg.Destroy()
			if not get_app().prefs.ask_dismiss or get_app().prefs.ask_dismiss and result== wx.ID_YES:
				if tl.type=="user":
					# Handle both string and dict data for user timelines
					if isinstance(tl.data, dict):
						# Remove matching dict entry
						get_app().currentAccount.prefs.user_timelines = [
							ut for ut in get_app().currentAccount.prefs.user_timelines
							if not (isinstance(ut, dict) and ut.get('username') == tl.data.get('username') and ut.get('filter') == tl.data.get('filter'))
						]
					elif tl.data in get_app().currentAccount.prefs.user_timelines:
						get_app().currentAccount.prefs.user_timelines.remove(tl.data)
				if tl.type=="list":
					get_app().currentAccount.prefs.list_timelines = [
						item for item in get_app().currentAccount.prefs.list_timelines
						if item.get('id') != tl.data
					]
				if tl.type=="search" and tl.data in get_app().currentAccount.prefs.search_timelines:
					get_app().currentAccount.prefs.search_timelines.remove(tl.data)
				if tl.type in ("feed", "local", "federated", "favourites", "bookmarks"):
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
				if tl.type == "remote_user":
					# Remove from remote_user_timelines (match url, username, and filter)
					inst_url = tl.data.get('url', '') if isinstance(tl.data, dict) else ''
					username = tl.data.get('username', '') if isinstance(tl.data, dict) else ''
					tl_filter = tl.data.get('filter') if isinstance(tl.data, dict) else None
					get_app().currentAccount.prefs.remote_user_timelines = [
						rut for rut in get_app().currentAccount.prefs.remote_user_timelines
						if not (rut.get('url') == inst_url and rut.get('username') == username and rut.get('filter') == tl_filter)
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

	def OnEdit(self, event=None):
		status = self.get_current_status()
		if status:
			# Check if this is our own post
			if hasattr(status, 'account') and hasattr(get_app().currentAccount, 'me'):
				if str(status.account.id) != str(get_app().currentAccount.me.id):
					speak.speak("You can only edit your own posts")
					return
			misc.edit(get_app().currentAccount, status)

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
			account = get_app().currentAccount
			try:
				status_id = misc.get_interaction_id(account, status)
				if not getattr(status, 'favourited', False):
					account.favourite(status_id)
					account.app.prefs.favourites_sent += 1
					status.favourited = True
					sound.play(account, "like")
				else:
					speak.speak("Already liked")
			except Exception as error:
				account.app.handle_error(error, "like post")

	def OnUnlike(self, event=None):
		status = self.get_current_status()
		if status:
			account = get_app().currentAccount
			try:
				status_id = misc.get_interaction_id(account, status)
				if getattr(status, 'favourited', False):
					account.unfavourite(status_id)
					status.favourited = False
					sound.play(account, "unlike")
				else:
					speak.speak("Not liked")
			except Exception as error:
				account.app.handle_error(error, "unlike post")

global window
window=MainGui(application.name+" "+application.version)
