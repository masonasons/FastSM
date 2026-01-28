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
from . import account_options, accounts, chooser, custom_timelines, explore_dialog, hashtag_dialog, invisible, lists, misc, options, profile, search, theme, timeline_filter, timelines, tray, tweet, view
import sound
import timeline
import threading

class MainGui(wx.Frame):
	def __init__(self, title):
		self.invisible=False
		self._find_text = ""  # Current search text for find in timeline
		self._open_dialogs = []  # Track open dialogs for focus restoration
		wx.Frame.__init__(self, None, title=title,size=(800,600))
		self.Center()
		if platform.system()!="Darwin":
			self.trayicon=tray.TaskBarIcon(self)
		self.handler=WXKeyboardHandler(self)
		self.handler.register_key("control+win+shift+t",self.ToggleWindow)
		self.handler.register_key("alt+win+shift+q",self.OnClose)
		self.handler.register_key("control+win+shift+a",self.OnAudioPlayer)
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.Bind(wx.EVT_ACTIVATE, self.OnActivate)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.menuBar = wx.MenuBar()

		menu = wx.Menu()
		if platform.system() == "Darwin":
			m_accounts = menu.Append(-1, "Accounts (Ctrl+A)", "accounts")
		else:
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
		m_following = menu.Append(-1, "List Following\tCtrl+]", "following")
		self.Bind(wx.EVT_MENU, self.OnFollowing, m_following)
		m_blocked = menu.Append(-1, "List Blocked Users", "blocked")
		self.Bind(wx.EVT_MENU, self.OnBlockedUsers, m_blocked)
		m_muted = menu.Append(-1, "List Muted Users", "muted")
		self.Bind(wx.EVT_MENU, self.OnMutedUsers, m_muted)
		m_followed_hashtags = menu.Append(-1, "Followed Hashtags", "followed_hashtags")
		self.Bind(wx.EVT_MENU, self.OnFollowedHashtags, m_followed_hashtags)
		m_options = menu.Append(wx.ID_PREFERENCES, "Global Options\tCtrl+,", "options")
		self.Bind(wx.EVT_MENU, self.OnOptions, m_options)
		m_account_options = menu.Append(-1, "Account options\tCtrl+Shift+,", "account_options")
		self.Bind(wx.EVT_MENU, self.OnAccountOptions, m_account_options)
		m_hide_window = menu.Append(-1, "Hide Window\tCtrl+Shift+W", "hide_window")
		self.Bind(wx.EVT_MENU, self.OnHideWindow, m_hide_window)
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
		m_retweet = menu2.Append(-1, "Boost/Unboost\tCtrl+Shift+R", "boost")
		self.Bind(wx.EVT_MENU, self.OnBoostToggle, m_retweet)
		if platform.system()=="Darwin":
			m_quote = menu2.Append(-1, "Quote\tAlt+Q", "quote")
		else:
			m_quote = menu2.Append(-1, "Quote\tCtrl+Q", "quote")
		self.Bind(wx.EVT_MENU, self.OnQuote, m_quote)
		m_like=menu2.Append(-1, "Like/Unlike\tCtrl+K", "favourite")
		self.Bind(wx.EVT_MENU, self.OnLikeToggle, m_like)
		m_url=menu2.Append(-1, "Open URL\tCtrl+O", "url")
		self.Bind(wx.EVT_MENU, self.OnUrl, m_url)
		m_tweet_url=menu2.Append(-1, "Open URL of Post\tCtrl+Shift+O", "post_url")
		self.Bind(wx.EVT_MENU, self.OnTweetUrl, m_tweet_url)
		m_delete = menu2.Append(-1, "Delete Post" if platform.system() == "Darwin" else "Delete Post\tDelete", "post")
		self.Bind(wx.EVT_MENU, self.OnDelete, m_delete)
		if platform.system() == "Darwin":
			m_copy = menu2.Append(-1, "Copy post to clipboard (Ctrl+C)", "copy")
		else:
			m_copy = menu2.Append(-1, "Copy post to clipboard\tCtrl+C", "copy")
		self.Bind(wx.EVT_MENU, self.onCopy, m_copy)
		m_message=menu2.Append(-1, "Send message\tCtrl+D", "message")
		self.Bind(wx.EVT_MENU, self.OnMessage, m_message)
		m_follow=menu2.Append(-1, "Follow/Unfollow\tCtrl+L", "follow")
		self.Bind(wx.EVT_MENU, self.OnFollowToggle, m_follow)
		m_add_to_list=menu2.Append(-1, "Add to list\tCtrl+I", "addlist")
		self.Bind(wx.EVT_MENU, self.OnAddToList, m_add_to_list)
		m_remove_from_list=menu2.Append(-1, "Remove from list\tCtrl+Shift+I", "removelist")
		self.Bind(wx.EVT_MENU, self.OnRemoveFromList, m_remove_from_list)
		m_bookmark=menu2.Append(-1, "Bookmark/Unbookmark\tCtrl+B", "bookmark")
		self.Bind(wx.EVT_MENU, self.OnBookmarkToggle, m_bookmark)
		m_block=menu2.Append(-1, "Block/Unblock\tCtrl+Shift+B", "block")
		self.Bind(wx.EVT_MENU, self.OnBlockToggle, m_block)
		m_mute_user=menu2.Append(-1, "Mute/Unmute user", "mute")
		self.Bind(wx.EVT_MENU, self.OnMuteToggle, m_mute_user)
		m_report_post=menu2.Append(-1, "Report post", "report_post")
		self.Bind(wx.EVT_MENU, self.OnReportPost, m_report_post)
		m_report_user=menu2.Append(-1, "Report user", "report_user")
		self.Bind(wx.EVT_MENU, self.OnReportUser, m_report_user)
		m_view=menu2.Append(-1, "View post" if platform.system() == "Darwin" else "View post\tReturn", "view")
		self.Bind(wx.EVT_MENU, self.OnView, m_view)
		m_user_profile=menu2.Append(-1, "User Profile\tCtrl+Shift+U", "profile")
		self.Bind(wx.EVT_MENU, self.OnUserProfile, m_user_profile)
		m_add_alias=menu2.Append(-1, "Add Alias\tCtrl+Shift+N", "alias")
		self.Bind(wx.EVT_MENU, self.OnAddAlias, m_add_alias)
		if platform.system() == "Darwin":
			m_speak_user=menu2.Append(-1, "Speak user (Ctrl+;)", "speak")
			m_speak_reply=menu2.Append(-1, "Speak reference post of this reply (Ctrl+Shift+;)", "speak2")
		else:
			m_speak_user=menu2.Append(-1, "Speak user\tCtrl+;", "speak")
			m_speak_reply=menu2.Append(-1, "Speak reference post of this reply\tCtrl+Shift+;", "speak2")
		self.Bind(wx.EVT_MENU, self.OnSpeakUser, m_speak_user)
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
		self.Bind(wx.EVT_MENU, self.OnHaventPosted, m_havent_posted)
		self.menuBar.Append(menu7, "U&sers")
		menu3 = wx.Menu()
		m_refresh = menu3.Append(-1, "Refresh timeline\tF5", "refresh")
		self.Bind(wx.EVT_MENU, self.onRefresh, m_refresh)
		m_prev = menu3.Append(-1, "Load older posts\tAlt+PgUp", "prev")
		self.Bind(wx.EVT_MENU, self.onPrev, m_prev)
		m_load_here = menu3.Append(-1, "Load posts here\tAlt+PgDn", "loadhere")
		self.Bind(wx.EVT_MENU, self.onLoadHere, m_load_here)
		if platform.system() != "Darwin":
			m_hide = menu3.Append(-1, "Hide Timeline\tCtrl+H", "hide")
		else:
			m_hide = menu3.Append(-1, "Hide Timeline\tRawCtrl+H", "hide")
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
		m_explore = menu3.Append(-1, "E&xplore\tCtrl+Shift+X", "explore")
		self.Bind(wx.EVT_MENU, self.OnExplore, m_explore)
		m_instance = menu3.Append(-1, "View &Instance\tAlt+I", "instance")
		self.Bind(wx.EVT_MENU, self.OnViewInstance, m_instance)
		m_find = menu3.Append(-1, "Find in timeline\tCtrl+F", "find")
		self.Bind(wx.EVT_MENU, self.OnFind, m_find)
		m_find_next = menu3.Append(-1, "Find next\tF3", "find_next")
		self.Bind(wx.EVT_MENU, self.OnFindNext, m_find_next)
		m_find_prev = menu3.Append(-1, "Find previous\tShift+F3", "find_prev")
		self.Bind(wx.EVT_MENU, self.OnFindPrevious, m_find_prev)
		self.m_close_timeline = menu3.Append(-1, "Close timeline\tCtrl+W", "removetimeline")
		self.m_close_timeline.Enable(False)
		self.Bind(wx.EVT_MENU, self.OnCloseTimeline, self.m_close_timeline)
		self.menuBar.Append(menu3, "Time&line")
		menu4 = wx.Menu()
		m_play_external = menu4.Append(-1, "Play media" if platform.system() == "Darwin" else "Play media\tCtrl+Return", "play_external")
		self.Bind(wx.EVT_MENU, self.OnPlayExternal, m_play_external)
		m_stop_audio = menu4.Append(-1, "Stop audio" if platform.system() == "Darwin" else "Stop audio\tCtrl+Shift+Return", "stop_audio")
		self.Bind(wx.EVT_MENU, self.OnStopAudio, m_stop_audio)
		m_audio_player = menu4.Append(-1, "Audio player\tCtrl+Shift+A", "audio_player")
		self.Bind(wx.EVT_MENU, self.OnAudioPlayer, m_audio_player)
		# On macOS, don't use menu accelerators for arrow key combos - they fire in other windows
		# Use accelerator table instead (only fires when main window has focus)
		if platform.system() == "Darwin":
			m_volup = menu4.Append(-1, "Volume up (Option+Up)", "volup")
			m_voldown = menu4.Append(-1, "Volume down (Option+Down)", "voldown")
		else:
			m_volup = menu4.Append(-1, "Volume up\tAlt+Up", "volup")
			m_voldown = menu4.Append(-1, "Volume down\tAlt+Down", "voldown")
		self.Bind(wx.EVT_MENU, self.OnVolup, m_volup)
		self.Bind(wx.EVT_MENU, self.OnVoldown, m_voldown)
		self.menuBar.Append(menu4, "A&udio")
		menu5 = wx.Menu()
		if platform.system() == "Darwin":
			m_previous_in_thread = menu5.Append(-1, "Previous post in thread (Ctrl+Up)", "prevpost")
			m_next_in_thread = menu5.Append(-1, "Next post in thread (Ctrl+Down)", "nextpost")
			m_previous_from_user = menu5.Append(-1, "Previous post from user (Ctrl+Left)", "prevuser")
			m_next_from_user = menu5.Append(-1, "Next post from user (Ctrl+Right)", "nextuser")
			m_next_timeline = menu5.Append(-1, "Next timeline (Option+Right)", "nexttl")
			m_prev_timeline = menu5.Append(-1, "Previous timeline (Option+Left)", "prevtl")
			m_next_account = menu5.Append(-1, "Next account (Ctrl+Shift+Right)", "nextacc")
			m_prev_account = menu5.Append(-1, "Previous account (Ctrl+Shift+Left)", "prevacc")
		else:
			m_previous_in_thread = menu5.Append(-1, "Previous post in thread\tCtrl+Up", "prevpost")
			m_next_in_thread = menu5.Append(-1, "Next post in thread\tCtrl+Down", "nextpost")
			m_previous_from_user = menu5.Append(-1, "Previous post from user\tCtrl+Left", "prevuser")
			m_next_from_user = menu5.Append(-1, "Next post from user\tCtrl+Right", "nextuser")
			m_next_timeline = menu5.Append(-1, "Next timeline\tAlt+Right", "nexttl")
			m_prev_timeline = menu5.Append(-1, "Previous timeline\tAlt+Left", "prevtl")
			m_next_account = menu5.Append(-1, "Next account\tCtrl+Shift+Right", "nextacc")
			m_prev_account = menu5.Append(-1, "Previous account\tCtrl+Shift+Left", "prevacc")
		self.Bind(wx.EVT_MENU, self.OnPreviousInThread, m_previous_in_thread)
		self.Bind(wx.EVT_MENU, self.OnNextInThread, m_next_in_thread)
		self.Bind(wx.EVT_MENU, self.OnPreviousFromUser, m_previous_from_user)
		self.Bind(wx.EVT_MENU, self.OnNextFromUser, m_next_from_user)
		self.Bind(wx.EVT_MENU, self.OnNextTimeline, m_next_timeline)
		self.Bind(wx.EVT_MENU, self.OnPrevTimeline, m_prev_timeline)
		self.Bind(wx.EVT_MENU, self.OnNextAccount, m_next_account)
		self.Bind(wx.EVT_MENU, self.OnPrevAccount, m_prev_account)
		# Timeline jump shortcuts (Ctrl/Cmd + number)
		menu5.AppendSeparator()
		if platform.system() == "Darwin":
			m_goto_tl1 = menu5.Append(-1, "Go to timeline 1 (Cmd+1)")
			m_goto_tl2 = menu5.Append(-1, "Go to timeline 2 (Cmd+2)")
			m_goto_tl3 = menu5.Append(-1, "Go to timeline 3 (Cmd+3)")
			m_goto_tl4 = menu5.Append(-1, "Go to timeline 4 (Cmd+4)")
			m_goto_tl5 = menu5.Append(-1, "Go to timeline 5 (Cmd+5)")
			m_goto_tl6 = menu5.Append(-1, "Go to timeline 6 (Cmd+6)")
			m_goto_tl7 = menu5.Append(-1, "Go to timeline 7 (Cmd+7)")
			m_goto_tl8 = menu5.Append(-1, "Go to timeline 8 (Cmd+8)")
			m_goto_tl9 = menu5.Append(-1, "Go to timeline 9 (Cmd+9)")
			m_goto_tl0 = menu5.Append(-1, "Go to timeline 10 (Cmd+0)")
		else:
			m_goto_tl1 = menu5.Append(-1, "Go to timeline 1\tCtrl+1")
			m_goto_tl2 = menu5.Append(-1, "Go to timeline 2\tCtrl+2")
			m_goto_tl3 = menu5.Append(-1, "Go to timeline 3\tCtrl+3")
			m_goto_tl4 = menu5.Append(-1, "Go to timeline 4\tCtrl+4")
			m_goto_tl5 = menu5.Append(-1, "Go to timeline 5\tCtrl+5")
			m_goto_tl6 = menu5.Append(-1, "Go to timeline 6\tCtrl+6")
			m_goto_tl7 = menu5.Append(-1, "Go to timeline 7\tCtrl+7")
			m_goto_tl8 = menu5.Append(-1, "Go to timeline 8\tCtrl+8")
			m_goto_tl9 = menu5.Append(-1, "Go to timeline 9\tCtrl+9")
			m_goto_tl0 = menu5.Append(-1, "Go to timeline 10\tCtrl+0")
		self.Bind(wx.EVT_MENU, self.OnGotoTimeline1, m_goto_tl1)
		self.Bind(wx.EVT_MENU, self.OnGotoTimeline2, m_goto_tl2)
		self.Bind(wx.EVT_MENU, self.OnGotoTimeline3, m_goto_tl3)
		self.Bind(wx.EVT_MENU, self.OnGotoTimeline4, m_goto_tl4)
		self.Bind(wx.EVT_MENU, self.OnGotoTimeline5, m_goto_tl5)
		self.Bind(wx.EVT_MENU, self.OnGotoTimeline6, m_goto_tl6)
		self.Bind(wx.EVT_MENU, self.OnGotoTimeline7, m_goto_tl7)
		self.Bind(wx.EVT_MENU, self.OnGotoTimeline8, m_goto_tl8)
		self.Bind(wx.EVT_MENU, self.OnGotoTimeline9, m_goto_tl9)
		self.Bind(wx.EVT_MENU, self.OnGotoTimeline0, m_goto_tl0)
		# Store menu item references for accelerator table on macOS
		self._m_volup = m_volup
		self._m_voldown = m_voldown
		self._m_previous_in_thread = m_previous_in_thread
		self._m_next_in_thread = m_next_in_thread
		self._m_previous_from_user = m_previous_from_user
		self._m_next_from_user = m_next_from_user
		self._m_next_timeline = m_next_timeline
		self._m_prev_timeline = m_prev_timeline
		self._m_next_account = m_next_account
		self._m_prev_account = m_prev_account
		self._m_speak_user = m_speak_user
		self._m_speak_reply = m_speak_reply
		self._m_accounts = m_accounts
		self._m_copy = m_copy
		self._m_goto_tl1 = m_goto_tl1
		self._m_goto_tl2 = m_goto_tl2
		self._m_goto_tl3 = m_goto_tl3
		self._m_goto_tl4 = m_goto_tl4
		self._m_goto_tl5 = m_goto_tl5
		self._m_goto_tl6 = m_goto_tl6
		self._m_goto_tl7 = m_goto_tl7
		self._m_goto_tl8 = m_goto_tl8
		self._m_goto_tl9 = m_goto_tl9
		self._m_goto_tl0 = m_goto_tl0
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

		# Add accelerator table for keyboard shortcuts
		if platform.system() != "Darwin":
			# Windows/Linux: Add Alt+M for context menu
			self.context_menu_id = wx.NewIdRef()
			self.Bind(wx.EVT_MENU, self.OnPostContextMenu, id=self.context_menu_id)
			accel = wx.AcceleratorTable([
				(wx.ACCEL_ALT, ord('M'), self.context_menu_id),
			])
			self.SetAcceleratorTable(accel)
		else:
			# macOS: Add arrow key combos to accelerator table (only fires when main window focused)
			# This prevents these shortcuts from firing in dialogs like New Post
			accel = wx.AcceleratorTable([
				# Alt (Option) + Arrow keys
				(wx.ACCEL_ALT, wx.WXK_UP, self._m_volup.GetId()),
				(wx.ACCEL_ALT, wx.WXK_DOWN, self._m_voldown.GetId()),
				(wx.ACCEL_ALT, wx.WXK_LEFT, self._m_prev_timeline.GetId()),
				(wx.ACCEL_ALT, wx.WXK_RIGHT, self._m_next_timeline.GetId()),
				# Ctrl (Control) + Arrow keys
				(wx.ACCEL_CTRL, wx.WXK_UP, self._m_previous_in_thread.GetId()),
				(wx.ACCEL_CTRL, wx.WXK_DOWN, self._m_next_in_thread.GetId()),
				(wx.ACCEL_CTRL, wx.WXK_LEFT, self._m_previous_from_user.GetId()),
				(wx.ACCEL_CTRL, wx.WXK_RIGHT, self._m_next_from_user.GetId()),
				# Ctrl+Shift + Arrow keys
				(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_LEFT, self._m_prev_account.GetId()),
				(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_RIGHT, self._m_next_account.GetId()),
				# Ctrl + semicolon shortcuts
				(wx.ACCEL_CTRL, ord(';'), self._m_speak_user.GetId()),
				(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord(';'), self._m_speak_reply.GetId()),
				# Ctrl+A for Accounts (conflicts with Select All on Mac)
				(wx.ACCEL_CTRL, ord('A'), self._m_accounts.GetId()),
				# Ctrl+C for Copy post (conflicts with system Copy on Mac)
				(wx.ACCEL_CTRL, ord('C'), self._m_copy.GetId()),
				# Cmd + number for timeline jump
				(wx.ACCEL_CMD, ord('1'), self._m_goto_tl1.GetId()),
				(wx.ACCEL_CMD, ord('2'), self._m_goto_tl2.GetId()),
				(wx.ACCEL_CMD, ord('3'), self._m_goto_tl3.GetId()),
				(wx.ACCEL_CMD, ord('4'), self._m_goto_tl4.GetId()),
				(wx.ACCEL_CMD, ord('5'), self._m_goto_tl5.GetId()),
				(wx.ACCEL_CMD, ord('6'), self._m_goto_tl6.GetId()),
				(wx.ACCEL_CMD, ord('7'), self._m_goto_tl7.GetId()),
				(wx.ACCEL_CMD, ord('8'), self._m_goto_tl8.GetId()),
				(wx.ACCEL_CMD, ord('9'), self._m_goto_tl9.GetId()),
				(wx.ACCEL_CMD, ord('0'), self._m_goto_tl0.GetId()),
			])
			self.SetAcceleratorTable(accel)

		self.list_label=wx.StaticText(self.panel, -1, label="Timelines")
		self.main_box.Add(self.list_label, 0, wx.LEFT | wx.TOP, 10)
		self.list=wx.ListBox(self.panel, -1)
		self.main_box.Add(self.list, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
		self.list.Bind(wx.EVT_LISTBOX, self.on_list_change)
		self.list.SetFocus()
		self.list2_label=wx.StaticText(self.panel, -1, label="Contents")
		self.main_box.Add(self.list2_label, 0, wx.LEFT | wx.TOP, 10)
		self.list2=wx.ListBox(self.panel, -1,size=(1200,800))
		self.main_box.Add(self.list2, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
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
		self.panel.SetSizer(self.main_box)
		self.panel.Layout()
		# Note: theme is applied in FastSM.pyw after prefs are loaded

	def _load_keymap_file(self, path):
		"""Load a keymap file and return dict of key -> action mappings."""
		keymap = {}
		if os.path.exists(path):
			try:
				with open(path, "r") as f:
					for line in f:
						line = line.strip()
						if "=" in line and not line.startswith("#"):
							parts = line.split("=", 1)
							if len(parts) == 2:
								keymap[parts[0].strip()] = parts[1].strip()
			except:
				pass
		return keymap

	def _load_keymap_with_inheritance(self):
		"""Load keymap with inheritance from default.

		Returns dict of key -> action mappings.
		First loads default keymap, then custom keymap replaces actions
		(removing default keys for any actions redefined in custom keymap).
		"""
		default_keymap = {}

		# Load default keymap first
		default_paths = [
			"keymaps/default.keymap",  # Local dev or bundled
			os.path.join(get_app().confpath, "keymaps/default.keymap"),  # User config
			"keymap.keymap",  # Fallback to legacy
		]

		for path in default_paths:
			default_keymap = self._load_keymap_file(path)
			if default_keymap:
				break

		# Load custom keymap if selected
		custom_keymap_name = getattr(get_app().prefs, 'keymap', 'default')
		if not custom_keymap_name or custom_keymap_name == 'default':
			return default_keymap

		# Load custom keymap
		custom_keymap = {}
		custom_paths = [
			os.path.join(get_app().confpath, f"keymaps/{custom_keymap_name}.keymap"),
			f"keymaps/{custom_keymap_name}.keymap",  # Bundled custom keymaps
		]

		for path in custom_paths:
			custom_keymap = self._load_keymap_file(path)
			if custom_keymap:
				break

		if not custom_keymap:
			return default_keymap

		# Get set of actions defined in custom keymap
		custom_actions = set(custom_keymap.values())

		# Build final keymap: start with defaults, but remove any keys
		# whose action is redefined in custom keymap
		final_keymap = {}
		for key, action in default_keymap.items():
			if action not in custom_actions:
				final_keymap[key] = action

		# Add all custom keymap entries
		final_keymap.update(custom_keymap)

		return final_keymap

	def register_keys(self):
		# Invisible hotkeys not supported on Mac
		if platform.system() == "Darwin":
			self.invisible = False
			return
		self.invisible=True
		keymap = self._load_keymap_with_inheritance()
		# Store registered keys so we can unregister them later
		self._registered_keymap = keymap.copy()
		for key, action in keymap.items():
			success=invisible.register_key(key, action)

	def unregister_keys(self):
		# Invisible hotkeys not supported on Mac
		if platform.system() == "Darwin":
			return
		self.invisible=False
		# Unregister the keys that were actually registered, not the current keymap
		keymap = getattr(self, '_registered_keymap', None)
		if keymap is None:
			# Fallback to loading keymap if we don't have stored keys
			keymap = self._load_keymap_with_inheritance()
		for key, action in keymap.items():
			success=invisible.register_key(key, action, False)
		self._registered_keymap = None

	def get_current_status(self):
		"""Get the current status, handling conversation and notification objects properly"""
		tl = get_app().currentAccount.currentTimeline
		if not tl.statuses or tl.index >= len(tl.statuses):
			return None
		item = tl.statuses[tl.index]
		if get_app().currentAccount.currentTimeline.type == "conversations":
			# Conversations have last_status instead of being a status directly
			if hasattr(item, 'last_status') and item.last_status:
				return item.last_status
			return None
		if get_app().currentAccount.currentTimeline.type == "notifications":
			# Notifications have status attribute for the associated post
			if hasattr(item, 'status') and item.status:
				return item.status
			# For follow notifications etc. without a status, return None
			return None
		return item

	def _sync_status_state_across_buffers(self, account, status_id, **state_updates):
		"""Sync status state (favourited, reblogged, etc.) across all buffers.

		Args:
			account: The account whose timelines to update
			status_id: The ID of the status to update
			**state_updates: Key-value pairs of state to update (e.g., favourited=True)
		"""
		status_id_str = str(status_id)
		for tl in account.timelines:
			for status in tl.statuses:
				# Check the status itself
				matched = False
				if str(getattr(status, 'id', '')) == status_id_str:
					matched = True
					target = status
				# Check if it's a reblog containing the status
				elif hasattr(status, 'reblog') and status.reblog:
					reblog_id = getattr(status.reblog, 'id', '')
					# Also check _original_status_id for mentions
					orig_id = getattr(status.reblog, '_original_status_id', reblog_id)
					if str(reblog_id) == status_id_str or str(orig_id) == status_id_str:
						matched = True
						target = status.reblog
				# Check _original_status_id for mentions (status could be notification-wrapped)
				elif hasattr(status, '_original_status_id'):
					if str(status._original_status_id) == status_id_str:
						matched = True
						target = status

				if matched:
					for key, value in state_updates.items():
						setattr(target, key, value)
					# Clear display cache so it gets re-rendered
					if hasattr(status, '_display_cache'):
						try:
							delattr(status, '_display_cache')
						except (AttributeError, TypeError):
							pass

				# Also check notification statuses
				if tl.type == "notifications" and hasattr(status, 'status') and status.status:
					notif_status = status.status
					notif_id = getattr(notif_status, 'id', '')
					orig_id = getattr(notif_status, '_original_status_id', notif_id)
					if str(notif_id) == status_id_str or str(orig_id) == status_id_str:
						for key, value in state_updates.items():
							setattr(notif_status, key, value)
						if hasattr(status, '_display_cache'):
							try:
								delattr(status, '_display_cache')
							except (AttributeError, TypeError):
								pass

	def OnHideWindow(self, event=None):
		"""Hide the window (menu handler)."""
		self.ToggleWindow()

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

	def OnActivate(self, event):
		"""Handle main window activation - restore focus to open dialogs."""
		if event.GetActive():
			# When main window is activated, check for open dialogs and raise them
			# Clean up any closed dialogs first
			self._open_dialogs = [d for d in self._open_dialogs if d and d.IsShown()]
			# Raise any open dialogs
			for dialog in self._open_dialogs:
				try:
					dialog.Raise()
				except:
					pass
		event.Skip()

	def register_dialog(self, dialog):
		"""Register a dialog to be tracked for focus restoration."""
		if dialog not in self._open_dialogs:
			self._open_dialogs.append(dialog)

	def unregister_dialog(self, dialog):
		"""Unregister a dialog from focus tracking."""
		if dialog in self._open_dialogs:
			self._open_dialogs.remove(dialog)

	def OnReadme(self,event=None):
		webbrowser.open("https://github.com/masonasons/FastSM/blob/master/docs/FastSM.md")

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
		import threading
		threading.Thread(target=lambda: get_app().cfu(False), daemon=True).start()

	def onCopy(self,event=None):
		tl_type = get_app().currentAccount.currentTimeline.type
		# Handle conversations specially - copy the conversation info
		if tl_type == "conversations":
			item = get_app().currentAccount.currentTimeline.statuses[get_app().currentAccount.currentTimeline.index]
			text = get_app().process_conversation(item)
			pyperclip.copy(text)
			speak.speak("Copied")
			return
		# Handle scheduled posts - use the processed scheduled status text
		if tl_type == "scheduled":
			item = get_app().currentAccount.currentTimeline.statuses[get_app().currentAccount.currentTimeline.index]
			text = get_app()._process_scheduled_status(item)
			pyperclip.copy(text)
			speak.speak("Copied")
			return
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
		# Sync timeline positions to server before exiting
		if get_app().prefs.sync_timeline_position:
			for account in get_app().accounts:
				for tl in account.timelines:
					try:
						tl.sync_position_to_server()
					except Exception as e:
						print(f"Error syncing {tl.name} position to server: {e}")
		# Save local position for notifications and mentions timelines
		for account in get_app().accounts:
			for tl in account.timelines:
				try:
					if tl.type == "notifications" and tl.statuses and tl.index < len(tl.statuses):
						status = tl.statuses[tl.index]
						account.prefs.last_notifications_id = str(status.id)
					elif tl.type == "mentions" and tl.statuses and tl.index < len(tl.statuses):
						status = tl.statuses[tl.index]
						account.prefs.last_mentions_id = str(status.id)
				except Exception as e:
					print(f"Error saving {tl.name} position to prefs: {e}")
			# Explicitly save account prefs to ensure position IDs are persisted
			try:
				account.prefs.save()
			except Exception as e:
				print(f"Error saving account prefs: {e}")
		# Save all timeline caches (positions, gaps, etc.) before exit
		for account in get_app().accounts:
			for tl in account.timelines:
				try:
					if hasattr(tl, '_cache_timeline'):
						tl._cache_timeline()
				except Exception as e:
					print(f"Error caching {tl.name}: {e}")
		# Clean up orphaned cache data (timelines that were dismissed)
		for account in get_app().accounts:
			if hasattr(account, '_platform') and account._platform:
				cache = getattr(account._platform, 'timeline_cache', None)
				if cache and cache.is_available():
					try:
						# Get active timeline keys
						active_keys = []
						for tl in account.timelines:
							key = tl.get_cache_key()
							if key:
								active_keys.append(key)
						cache.cleanup_orphaned_data(active_keys)
					except Exception as e:
						print(f"Error cleaning up cache: {e}")
		if platform.system()!="Darwin":
			self.trayicon.on_exit(event,False)
		# Clean up account resources (close timeline caches)
		for account in get_app().accounts:
			if hasattr(account, 'cleanup'):
				try:
					account.cleanup()
				except:
					pass
		self.Destroy()
		# On Mac, we need to explicitly exit the main loop
		if platform.system() == "Darwin":
			wx.GetApp().ExitMainLoop()
		sys.exit()
	
	def OnPlayExternal(self,event=None):
		status = self.get_current_status()
		if status:
			thread=threading.Thread(target=misc.play_external,args=(status,)).start()

	def OnStopAudio(self,event=None):
		sound.stop()
		speak.speak("Stopped")

	def OnAudioPlayer(self,event=None):
		from . import audio_player
		audio_player.show_audio_player(self)

	def OnConversation(self,event=None):
		status = self.get_current_status()
		if status:
			misc.load_conversation(get_app().currentAccount, status)

	def OnDelete(self,event=None):
		status = self.get_current_status()
		if status:
			# Check if confirmation is required
			if get_app().prefs.confirm_delete:
				dlg = wx.MessageDialog(self, "Are you sure you want to delete this post?", "Confirm Delete", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
				if dlg.ShowModal() != wx.ID_YES:
					dlg.Destroy()
					return
				dlg.Destroy()
			misc.delete(get_app().currentAccount, status)

	def OnReportPost(self, event=None):
		"""Report the current post."""
		status = self.get_current_status()
		if status:
			misc.report_status(get_app().currentAccount, status, self)

	def OnReportUser(self, event=None):
		"""Report the user of the current post."""
		account = get_app().currentAccount
		# Get users from current item (handles both statuses and notifications)
		u = self._get_users_from_current_item(account)
		if not u:
			speak.speak("No user found")
			return
		if len(u) > 1:
			# Multiple users - use chooser with user objects
			u2 = [i.acct for i in u]
			chooser.chooser(account, "Report User", "Select user to report", u2, "report_user", user_objects=u)
		else:
			# Single user - report directly
			misc.report_user(account, u[0], self)

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

	def OnGotoTimeline1(self, event=None):
		invisible.inv.goto_tl(0, True)

	def OnGotoTimeline2(self, event=None):
		invisible.inv.goto_tl(1, True)

	def OnGotoTimeline3(self, event=None):
		invisible.inv.goto_tl(2, True)

	def OnGotoTimeline4(self, event=None):
		invisible.inv.goto_tl(3, True)

	def OnGotoTimeline5(self, event=None):
		invisible.inv.goto_tl(4, True)

	def OnGotoTimeline6(self, event=None):
		invisible.inv.goto_tl(5, True)

	def OnGotoTimeline7(self, event=None):
		invisible.inv.goto_tl(6, True)

	def OnGotoTimeline8(self, event=None):
		invisible.inv.goto_tl(7, True)

	def OnGotoTimeline9(self, event=None):
		invisible.inv.goto_tl(8, True)

	def OnGotoTimeline0(self, event=None):
		invisible.inv.goto_tl(9, True)

	def _get_account_display_name(self, account):
		"""Get display name for an account, including instance for Mastodon."""
		acct = getattr(account.me, 'acct', 'Unknown')
		platform_type = getattr(account.prefs, 'platform_type', 'mastodon')
		if platform_type == 'mastodon' and hasattr(account, 'api') and hasattr(account.api, 'api_base_url'):
			from urllib.parse import urlparse
			parsed = urlparse(account.api.api_base_url)
			instance = parsed.netloc or parsed.path.strip('/')
			if instance:
				acct = f"{acct} on {instance}"
		return acct

	def OnNextAccount(self, event=None):
		"""Switch to the next account."""
		app = get_app()
		if len(app.accounts) <= 1:
			speak.speak("Only one account")
			return
		current_index = app.accounts.index(app.currentAccount)
		next_index = (current_index + 1) % len(app.accounts)
		app.currentAccount = app.accounts[next_index]
		self._switch_to_account(app.currentAccount)
		speak.speak(self._get_account_display_name(app.currentAccount))

	def OnPrevAccount(self, event=None):
		"""Switch to the previous account."""
		app = get_app()
		if len(app.accounts) <= 1:
			speak.speak("Only one account")
			return
		current_index = app.accounts.index(app.currentAccount)
		prev_index = (current_index - 1) % len(app.accounts)
		app.currentAccount = app.accounts[prev_index]
		self._switch_to_account(app.currentAccount)
		speak.speak(self._get_account_display_name(app.currentAccount))

	def _switch_to_account(self, account):
		"""Switch UI to display the given account's timelines."""
		# Refresh the timeline list for this account - use Set() for batch update
		timelines = account.list_timelines()
		self.list.Set([tl.name for tl in timelines])

		# Restore the account's last selected timeline, or default to first
		if account.currentIndex is not None and account.currentIndex < len(timelines):
			self.list.SetSelection(account.currentIndex)
		else:
			self.list.SetSelection(0)
			account.currentIndex = 0

		# Update currentTimeline to match selection
		selected_idx = self.list.GetSelection()
		if selected_idx >= 0 and selected_idx < len(timelines):
			account.currentTimeline = timelines[selected_idx]
			account.currentIndex = selected_idx

		# Update close timeline menu state
		if account.currentTimeline and account.currentTimeline.removable:
			self.m_close_timeline.Enable(True)
		else:
			self.m_close_timeline.Enable(False)

		# Refresh the posts list
		self.refreshList()

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
		# Use Set() for batch update - faster than Clear() + individual Insert()
		timeline_names = [tl.name for tl in get_app().currentAccount.list_timelines()]
		self.list.Set(timeline_names)
		try:
			self.list.SetSelection(old_selection)
		except:
			if self.list.GetCount() > 0:
				self.list.SetSelection(min(1, self.list.GetCount() - 1))

	def on_list_change(self, event):
		get_app().currentAccount.currentTimeline=get_app().currentAccount.list_timelines()[self.list.GetSelection()]
		get_app().currentAccount.currentIndex=self.list.GetSelection()
		if get_app().currentAccount.currentTimeline.removable:
			self.m_close_timeline.Enable(True)
		else:
			self.m_close_timeline.Enable(False)

		self.play_earcon()
		# Announce if timeline has gaps to fill
		tl = get_app().currentAccount.currentTimeline
		if hasattr(tl, '_gaps') and tl._gaps:
			speak.speak(f"{len(tl._gaps)} gap{'s' if len(tl._gaps) > 1 else ''} to fill")
		self.refreshList()

	def play_earcon(self):
		if get_app().prefs.earcon_top and (not get_app().prefs.reversed and get_app().currentAccount.currentTimeline.index > 0 or get_app().prefs.reversed and get_app().currentAccount.currentTimeline.index < len(get_app().currentAccount.currentTimeline.statuses) - 1):
			sound.play(get_app().currentAccount,"new")

	def OnFollowers(self,event=None):
		misc.followers(get_app().currentAccount)

	def OnFollowing(self,event=None):
		misc.following(get_app().currentAccount)

	def OnBlockedUsers(self,event=None):
		misc.blocked_users(get_app().currentAccount)

	def OnMutedUsers(self,event=None):
		misc.muted_users(get_app().currentAccount)

	def OnFollowedHashtags(self, event=None):
		misc.show_followed_hashtags(get_app().currentAccount)

	def OnMutualFollowing(self,event=None):
		misc.mutual_following(get_app().currentAccount)

	def OnNotFollowing(self,event=None):
		misc.not_following(get_app().currentAccount)

	def OnNotFollowingMe(self,event=None):
		misc.not_following_me(get_app().currentAccount)

	def OnHaventPosted(self,event=None):
		misc.havent_posted(get_app().currentAccount)

	def refreshList(self):
		stuffage=get_app().currentAccount.currentTimeline.get()
		self.list2.Freeze()
		# Use Set() for batch update - much faster than Clear() + individual Append()
		self.list2.Set(stuffage)
		tl = get_app().currentAccount.currentTimeline
		count = self.list2.GetCount()
		if count == 0:
			# Empty list - ensure index is 0
			tl.index = 0
		else:
			# Clamp index to valid range and set selection
			tl.index = max(0, min(tl.index, count - 1))
			self.list2.SetSelection(tl.index)
		self.list2.Thaw()

	def OnViewUserDb(self, event=None):
		u=view.UserViewGui(get_app().currentAccount,get_app().users,"User Database containing "+str(len(get_app().users))+" users.")
		u.Show()

	def OnCleanUserDb(self, event=None):
		get_app().clean_users()
		get_app().save_users()

	def on_list2_change(self, event):
		get_app().currentAccount.currentTimeline.index=self.list2.GetSelection()
		# Track position change for timeline sync
		get_app().currentAccount.currentTimeline.mark_position_moved()
		status = self.get_current_status()
		if status and get_app().prefs.earcon_audio:
			# Get the actual status (unwrap boosts)
			status_to_check = status.reblog if hasattr(status, 'reblog') and status.reblog else status
			# Check for pinned post (check both pinned and _pinned attributes)
			if getattr(status_to_check, 'pinned', False) or getattr(status_to_check, '_pinned', False):
				sound.play(get_app().currentAccount, "pinned")
			# Check for poll
			if getattr(status_to_check, 'poll', None):
				sound.play(get_app().currentAccount, "poll")
			# Check for media attachments (image vs other media)
			earcon_type = sound.get_media_type_for_earcon(status_to_check)
			if earcon_type:
				sound.play(get_app().currentAccount, earcon_type)
			# Fall back to URL-based media detection
			elif len(sound.get_media_urls(get_app().find_urls_in_status(status))) > 0:
				sound.play(get_app().currentAccount, "media")

	def onRefresh(self,event=None):
		threading.Thread(target=get_app().currentAccount.currentTimeline.load, daemon=True).start()

	def add_to_list(self, items):
		if not items:
			return
		self.list2.Freeze()
		# InsertItems is faster than individual Insert calls
		self.list2.InsertItems(items, 0)
		self.list2.Thaw()

	def append_to_list(self, items):
		if not items:
			return
		self.list2.Freeze()
		# AppendItems would be ideal but wx doesn't have it - use InsertItems at end
		self.list2.InsertItems(items, self.list2.GetCount())
		self.list2.Thaw()

	def OnView(self,event=None):
		tl_type = get_app().currentAccount.currentTimeline.type
		# For notifications, show the notification-specific viewer
		if tl_type == "notifications":
			item = get_app().currentAccount.currentTimeline.statuses[get_app().currentAccount.currentTimeline.index]
			viewer = view.NotificationViewGui(get_app().currentAccount, item)
			viewer.Show()
			return
		# For other timelines, show the post viewer
		status = self.get_current_status()
		if status:
			viewer = view.ViewGui(get_app().currentAccount, status)
			viewer.Show()
		else:
			speak.speak("No messages in this conversation")

	def OnViewImage(self, event=None):
		status = self.get_current_status()
		if status:
			viewer = view.ViewImageGui(status)
			viewer.Show()
		else:
			speak.speak("No post selected")

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

			m_reply = menu.Append(-1, "Reply to message")
			self.Bind(wx.EVT_MENU, self.OnReply, m_reply)

			m_new_dm = menu.Append(-1, "Send new message")
			self.Bind(wx.EVT_MENU, self.OnMessage, m_new_dm)

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

			# Get relationship state for conversation participants
			is_following = False
			is_muting = False
			is_blocking = False
			try:
				# Get first participant that isn't us
				conv_user = None
				if hasattr(item, 'accounts') and item.accounts:
					for acc in item.accounts:
						if str(acc.id) != str(get_app().currentAccount.me.id):
							conv_user = acc
							break
					if conv_user:
						account = get_app().currentAccount
						platform_type = getattr(account.prefs, 'platform_type', 'mastodon')
						if platform_type == 'mastodon' and hasattr(account, 'api') and hasattr(account.api, 'account_relationships'):
							relationships = account.api.account_relationships([conv_user.id])
							if relationships and len(relationships) > 0:
								rel = relationships[0]
								is_following = getattr(rel, 'following', False)
								is_muting = getattr(rel, 'muting', False)
								is_blocking = getattr(rel, 'blocking', False)
						elif platform_type == 'bluesky':
							viewer = getattr(conv_user, 'viewer', None)
							if viewer:
								is_following = bool(getattr(viewer, 'following', None))
								is_muting = bool(getattr(viewer, 'muted', False))
								is_blocking = bool(getattr(viewer, 'blocking', None))
			except:
				pass

			m_follow = menu.Append(-1, "Unfollow" if is_following else "Follow")
			self.Bind(wx.EVT_MENU, self.OnFollowToggle, m_follow)

			m_mute = menu.Append(-1, "Unmute user" if is_muting else "Mute user")
			self.Bind(wx.EVT_MENU, self.OnMuteToggle, m_mute)

			m_block = menu.Append(-1, "Unblock user" if is_blocking else "Block user")
			self.Bind(wx.EVT_MENU, self.OnBlockToggle, m_block)

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

				# Get relationship state
				is_blocking = False
				try:
					if hasattr(item, 'account'):
						account = get_app().currentAccount
						relationships = account.api.account_relationships([item.account.id])
						if relationships and len(relationships) > 0:
							is_blocking = getattr(relationships[0], 'blocking', False)
				except:
					pass

				m_block = menu.Append(-1, "Unblock user" if is_blocking else "Block user")
				self.Bind(wx.EVT_MENU, self.OnBlockToggle, m_block)

			elif notif_type == 'follow':
				# Follow notifications - user-focused options only
				m_user_profile = menu.Append(-1, "User profile")
				self.Bind(wx.EVT_MENU, self.OnUserProfile, m_user_profile)

				m_user_tl = menu.Append(-1, "User timeline")
				self.Bind(wx.EVT_MENU, self.OnUserTimeline, m_user_tl)

				menu.AppendSeparator()

				# Get relationship state
				is_following = False
				is_muting = False
				is_blocking = False
				is_showing_reblogs = True
				platform_type = getattr(get_app().currentAccount.prefs, 'platform_type', 'mastodon')
				try:
					if hasattr(item, 'account'):
						account = get_app().currentAccount
						relationships = account.api.account_relationships([item.account.id])
						if relationships and len(relationships) > 0:
							rel = relationships[0]
							is_following = getattr(rel, 'following', False)
							is_muting = getattr(rel, 'muting', False)
							is_blocking = getattr(rel, 'blocking', False)
							is_showing_reblogs = getattr(rel, 'showing_reblogs', True)
				except:
					pass

				m_follow = menu.Append(-1, "Unfollow" if is_following else "Follow")
				self.Bind(wx.EVT_MENU, self.OnFollowToggle, m_follow)

				# Hide boosts option - only for Mastodon and if following
				if platform_type == 'mastodon' and is_following:
					m_hide_boosts = menu.Append(-1, "Show boosts" if not is_showing_reblogs else "Hide boosts")
					self.Bind(wx.EVT_MENU, self.OnHideBoostsToggle, m_hide_boosts)

				m_mute = menu.Append(-1, "Unmute user" if is_muting else "Mute user")
				self.Bind(wx.EVT_MENU, self.OnMuteToggle, m_mute)

				m_block = menu.Append(-1, "Unblock user" if is_blocking else "Block user")
				self.Bind(wx.EVT_MENU, self.OnBlockToggle, m_block)

			elif notif_type == 'poll':
				# Poll ended notification - always show View poll results first
				m_poll = menu.Append(-1, "View poll results")
				self.Bind(wx.EVT_MENU, self.OnViewPollResults, m_poll)

				notif_status = getattr(item, 'status', None)
				if notif_status:
					menu.AppendSeparator()

					m_view = menu.Append(-1, "View post")
					self.Bind(wx.EVT_MENU, self.OnView, m_view)

					# User options for the poll author
					m_user_profile = menu.Append(-1, "User profile")
					self.Bind(wx.EVT_MENU, self.OnUserProfile, m_user_profile)

					m_user_tl = menu.Append(-1, "User timeline")
					self.Bind(wx.EVT_MENU, self.OnUserTimeline, m_user_tl)

			else:
				# Notifications with posts (favourite, reblog, mention, etc.)
				notif_status = getattr(item, 'status', None)
				is_favourited = getattr(notif_status, 'favourited', False) if notif_status else False
				is_reblogged = getattr(notif_status, 'reblogged', False) if notif_status else False
				is_bookmarked = getattr(notif_status, 'bookmarked', False) if notif_status else False
				platform_type = getattr(get_app().currentAccount.prefs, 'platform_type', 'mastodon')

				# View Image - only show if notification post has image attachments (at top of menu)
				has_images = False
				if notif_status and hasattr(notif_status, 'media_attachments') and notif_status.media_attachments:
					for media in notif_status.media_attachments:
						if getattr(media, 'type', '').lower() == 'image':
							has_images = True
							break
				if has_images:
					m_view_image = menu.Append(-1, "View image")
					self.Bind(wx.EVT_MENU, self.OnViewImage, m_view_image)
					menu.AppendSeparator()

				# Check for poll in notification status
				if notif_status:
					poll = getattr(notif_status, 'poll', None)
					if poll:
						is_expired = getattr(poll, 'expired', False)
						has_voted = getattr(poll, 'voted', False)
						if is_expired or has_voted:
							m_poll = menu.Append(-1, "View poll results")
						else:
							m_poll = menu.Append(-1, "Vote in poll")
						self.Bind(wx.EVT_MENU, self.OnVotePoll, m_poll)
						menu.AppendSeparator()

				m_view = menu.Append(-1, "View post")
				self.Bind(wx.EVT_MENU, self.OnView, m_view)

				m_reply = menu.Append(-1, "Reply")
				self.Bind(wx.EVT_MENU, self.OnReply, m_reply)

				m_boost = menu.Append(-1, "Unboost" if is_reblogged else "Boost")
				self.Bind(wx.EVT_MENU, self.OnBoostToggle, m_boost)

				m_fav = menu.Append(-1, "Unfavourite" if is_favourited else "Favourite")
				self.Bind(wx.EVT_MENU, self.OnLikeToggle, m_fav)

				if platform_type == 'mastodon':
					m_bookmark = menu.Append(-1, "Remove bookmark" if is_bookmarked else "Bookmark")
					self.Bind(wx.EVT_MENU, self.OnBookmarkToggle, m_bookmark)

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

				# Get relationship state for the notification actor
				is_following = False
				is_muting = False
				is_blocking = False
				is_showing_reblogs = True
				try:
					notif_user = item.account if hasattr(item, 'account') else (notif_status.account if notif_status else None)
					if notif_user:
						account = get_app().currentAccount
						if platform_type == 'mastodon' and hasattr(account, 'api') and hasattr(account.api, 'account_relationships'):
							relationships = account.api.account_relationships([notif_user.id])
							if relationships and len(relationships) > 0:
								rel = relationships[0]
								is_following = getattr(rel, 'following', False)
								is_muting = getattr(rel, 'muting', False)
								is_blocking = getattr(rel, 'blocking', False)
								is_showing_reblogs = getattr(rel, 'showing_reblogs', True)
						elif platform_type == 'bluesky':
							# For Bluesky, check viewer info on the user object
							viewer = getattr(notif_user, 'viewer', None)
							if viewer:
								# viewer.following is a URI string if following, None/empty if not
								is_following = bool(getattr(viewer, 'following', None))
								is_muting = bool(getattr(viewer, 'muted', False))
								is_blocking = bool(getattr(viewer, 'blocking', None))
				except:
					pass

				m_follow = menu.Append(-1, "Unfollow" if is_following else "Follow")
				self.Bind(wx.EVT_MENU, self.OnFollowToggle, m_follow)

				# Hide boosts option - only for Mastodon and if following
				if platform_type == 'mastodon' and is_following:
					m_hide_boosts = menu.Append(-1, "Show boosts" if not is_showing_reblogs else "Hide boosts")
					self.Bind(wx.EVT_MENU, self.OnHideBoostsToggle, m_hide_boosts)

				m_mute = menu.Append(-1, "Unmute user" if is_muting else "Mute user")
				self.Bind(wx.EVT_MENU, self.OnMuteToggle, m_mute)

				m_block = menu.Append(-1, "Unblock user" if is_blocking else "Block user")
				self.Bind(wx.EVT_MENU, self.OnBlockToggle, m_block)

				m_report_user = menu.Append(-1, "Report user")
				self.Bind(wx.EVT_MENU, self.OnReportUser, m_report_user)

				# Check for hashtags in notification status - only for Mastodon
				if platform_type == 'mastodon' and notif_status:
					hashtags = misc.get_hashtags_from_status(notif_status)
					if hashtags:
						menu.AppendSeparator()

						m_follow_hashtag = menu.Append(-1, "Follow hashtag")
						self.Bind(wx.EVT_MENU, self.OnFollowHashtag, m_follow_hashtag)

						m_unfollow_hashtag = menu.Append(-1, "Unfollow hashtag")
						self.Bind(wx.EVT_MENU, self.OnUnfollowHashtag, m_unfollow_hashtag)

				# Mute conversation option - only for Mastodon
				if platform_type == 'mastodon' and notif_status:
					menu.AppendSeparator()
					is_muted_conv = getattr(notif_status, 'muted', False)
					m_mute_conv = menu.Append(-1, "Unmute conversation" if is_muted_conv else "Mute conversation")
					self.Bind(wx.EVT_MENU, self.OnMuteConversationToggle, m_mute_conv)

		elif tl_type == "scheduled":
			# Scheduled posts menu - limited options since these aren't posted yet
			m_delete = menu.Append(-1, "Delete scheduled post")
			self.Bind(wx.EVT_MENU, self.OnDelete, m_delete)

			menu.AppendSeparator()

			m_copy = menu.Append(-1, "Copy to clipboard")
			self.Bind(wx.EVT_MENU, self.onCopy, m_copy)

		else:
			# Standard post menu for all other timelines
			status_to_check = item.reblog if hasattr(item, 'reblog') and item.reblog else item
			is_favourited = getattr(status_to_check, 'favourited', False)
			is_reblogged = getattr(status_to_check, 'reblogged', False)
			is_bookmarked = getattr(status_to_check, 'bookmarked', False)
			platform_type = getattr(get_app().currentAccount.prefs, 'platform_type', 'mastodon')

			# View Image - only show if post has image attachments (at top of menu)
			has_images = False
			if hasattr(status_to_check, 'media_attachments') and status_to_check.media_attachments:
				for media in status_to_check.media_attachments:
					if getattr(media, 'type', '').lower() == 'image':
						has_images = True
						break
			if has_images:
				m_view_image = menu.Append(-1, "View image")
				self.Bind(wx.EVT_MENU, self.OnViewImage, m_view_image)
				menu.AppendSeparator()

			# Check for poll - show at top of menu
			poll = getattr(status_to_check, 'poll', None)
			if poll:
				is_expired = getattr(poll, 'expired', False)
				has_voted = getattr(poll, 'voted', False)
				if is_expired or has_voted:
					m_poll = menu.Append(-1, "View poll results")
				else:
					m_poll = menu.Append(-1, "Vote in poll")
				self.Bind(wx.EVT_MENU, self.OnVotePoll, m_poll)
				menu.AppendSeparator()

			m_view = menu.Append(-1, "View post")
			self.Bind(wx.EVT_MENU, self.OnView, m_view)

			m_reply = menu.Append(-1, "Reply")
			self.Bind(wx.EVT_MENU, self.OnReply, m_reply)

			m_boost = menu.Append(-1, "Unboost" if is_reblogged else "Boost")
			self.Bind(wx.EVT_MENU, self.OnBoostToggle, m_boost)

			m_quote = menu.Append(-1, "Quote")
			self.Bind(wx.EVT_MENU, self.OnQuote, m_quote)

			m_fav = menu.Append(-1, "Unfavourite" if is_favourited else "Favourite")
			self.Bind(wx.EVT_MENU, self.OnLikeToggle, m_fav)

			if platform_type == 'mastodon':
				m_bookmark = menu.Append(-1, "Remove bookmark" if is_bookmarked else "Bookmark")
				self.Bind(wx.EVT_MENU, self.OnBookmarkToggle, m_bookmark)

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

			# Get relationship state for the post author
			is_following = False
			is_muting = False
			is_blocking = False
			is_showing_reblogs = True
			try:
				post_user = status_to_check.account
				account = get_app().currentAccount
				if platform_type == 'mastodon' and hasattr(account, 'api') and hasattr(account.api, 'account_relationships'):
					relationships = account.api.account_relationships([post_user.id])
					if relationships and len(relationships) > 0:
						rel = relationships[0]
						is_following = getattr(rel, 'following', False)
						is_muting = getattr(rel, 'muting', False)
						is_blocking = getattr(rel, 'blocking', False)
						is_showing_reblogs = getattr(rel, 'showing_reblogs', True)
				elif platform_type == 'bluesky':
					# For Bluesky, check viewer info on the user object
					viewer = getattr(post_user, 'viewer', None)
					if viewer:
						is_following = bool(getattr(viewer, 'following', None))
						is_muting = bool(getattr(viewer, 'muted', False))
						is_blocking = bool(getattr(viewer, 'blocking', None))
			except:
				pass

			m_follow = menu.Append(-1, "Unfollow" if is_following else "Follow")
			self.Bind(wx.EVT_MENU, self.OnFollowToggle, m_follow)

			# Hide boosts option - only for Mastodon and if following
			if platform_type == 'mastodon' and is_following:
				m_hide_boosts = menu.Append(-1, "Show boosts" if not is_showing_reblogs else "Hide boosts")
				self.Bind(wx.EVT_MENU, self.OnHideBoostsToggle, m_hide_boosts)

			m_mute = menu.Append(-1, "Unmute user" if is_muting else "Mute user")
			self.Bind(wx.EVT_MENU, self.OnMuteToggle, m_mute)

			m_block = menu.Append(-1, "Unblock user" if is_blocking else "Block user")
			self.Bind(wx.EVT_MENU, self.OnBlockToggle, m_block)

			m_report_user = menu.Append(-1, "Report user")
			self.Bind(wx.EVT_MENU, self.OnReportUser, m_report_user)

			# Check for hashtags in post - only show hashtag options if post has hashtags
			# Only for Mastodon - Bluesky doesn't support hashtag following
			if platform_type == 'mastodon':
				hashtags = misc.get_hashtags_from_status(status_to_check)
				if hashtags:
					menu.AppendSeparator()

					m_follow_hashtag = menu.Append(-1, "Follow hashtag")
					self.Bind(wx.EVT_MENU, self.OnFollowHashtag, m_follow_hashtag)

					m_unfollow_hashtag = menu.Append(-1, "Unfollow hashtag")
					self.Bind(wx.EVT_MENU, self.OnUnfollowHashtag, m_unfollow_hashtag)

			# Mute conversation option - only for Mastodon
			if platform_type == 'mastodon':
				menu.AppendSeparator()
				is_muted_conv = getattr(status_to_check, 'muted', False)
				m_mute_conv = menu.Append(-1, "Unmute conversation" if is_muted_conv else "Mute conversation")
				self.Bind(wx.EVT_MENU, self.OnMuteConversationToggle, m_mute_conv)

			menu.AppendSeparator()

			m_delete = menu.Append(-1, "Delete")
			self.Bind(wx.EVT_MENU, self.OnDelete, m_delete)

			m_report = menu.Append(-1, "Report post")
			self.Bind(wx.EVT_MENU, self.OnReportPost, m_report)

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

	def onLoadHere(self, event=None):
		"""Load posts starting from the current position to fill gaps."""
		tl = get_app().currentAccount.currentTimeline
		if tl._loading_all_active:
			tl.stop_loading_all()
		elif get_app().prefs.load_all_previous:
			threading.Thread(target=tl.load_all_here, daemon=True).start()
		else:
			threading.Thread(target=tl.load_here, daemon=True).start()

	def OnVolup(self, event=None):
		# Use per-account soundpack volume
		account = get_app().currentAccount
		if account.prefs.soundpack_volume < 1.0:
			account.prefs.soundpack_volume += 0.1
			account.prefs.soundpack_volume = round(account.prefs.soundpack_volume, 1)
			sound.play(account, "volume_changed")

	def OnVoldown(self, event=None):
		# Use per-account soundpack volume
		account = get_app().currentAccount
		if account.prefs.soundpack_volume > 0.0:
			account.prefs.soundpack_volume -= 0.1
			account.prefs.soundpack_volume = round(account.prefs.soundpack_volume, 1)
			sound.play(account, "volume_changed")

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
		account = get_app().currentAccount
		# Get users from current item (handles both statuses and notifications)
		u = self._get_users_from_current_item(account)
		u2 = [i.acct for i in u] if u else []
		# Use direct type to pass user objects, avoiding lookup issues
		# If no users in current item, user can still type a username
		chooser.chooser(account, "User Timeline", "Enter or choose a username", u2, "userTimeline_direct", user_objects=u or [])

	def OnSearch(self, event=None):
		s=search.SearchGui(get_app().currentAccount)
		s.Show()

	def OnUserSearch(self, event=None):
		s=search.SearchGui(get_app().currentAccount,"user")
		s.Show()

	def OnExplore(self, event=None):
		"""Open the Explore/Discover dialog."""
		e = explore_dialog.ExploreDialog(get_app().currentAccount)
		e.Show()

	def OnViewInstance(self, event=None):
		"""View instance information.

		If currently viewing a remote instance or remote user timeline,
		shows info for that remote instance. Otherwise shows current instance.
		"""
		account = get_app().currentAccount
		tl = account.currentTimeline

		# Check if we're in a remote instance/user timeline
		instance_url = None
		if tl.type == 'instance':
			# Instance timeline - the data contains the instance URL
			instance_url = tl.data
		elif tl.type == 'remote_user':
			# Remote user timeline - extract instance from data
			if isinstance(tl.data, dict):
				instance_url = tl.data.get('url')

		from . import instance_viewer
		instance_viewer.view_instance(account, instance_url)

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

	def OnFindNext(self, event=None):
		"""Find next occurrence of the search text."""
		if not self._find_text:
			# No previous search, open dialog
			self.OnFind(event)
			return

		tl = get_app().currentAccount.currentTimeline
		if not tl.statuses:
			speak.speak("No posts to search")
			return

		# Get displayed text for each post
		displayed = tl.get()

		# Search forward from current position (no wrapping)
		for idx in range(tl.index + 1, len(displayed)):
			if self._find_text in displayed[idx].lower():
				tl.index = idx
				self.list2.SetSelection(idx)
				self.on_list2_change(None)
				speak.speak(displayed[idx])
				return

		speak.speak("No more items found")

	def OnFindPrevious(self, event=None):
		"""Find previous occurrence of the search text."""
		if not self._find_text:
			# No previous search, open dialog
			self.OnFind(event)
			return

		tl = get_app().currentAccount.currentTimeline
		if not tl.statuses:
			speak.speak("No posts to search")
			return

		# Get displayed text for each post
		displayed = tl.get()

		# Search backward from current position (no wrapping)
		for idx in range(tl.index - 1, -1, -1):
			if self._find_text in displayed[idx].lower():
				tl.index = idx
				self.list2.SetSelection(idx)
				self.on_list2_change(None)
				speak.speak(displayed[idx])
				return

		speak.speak("No more items found")

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
		account = get_app().currentAccount
		# Get users from current item (handles both statuses and notifications)
		u = self._get_users_from_current_item(account)
		u2 = [i.acct for i in u] if u else []
		# Use direct type to pass user objects, avoiding lookup issues
		# If no users found, user can still type a username manually
		chooser.chooser(account, "User Profile", "Enter or choose a username", u2, "profile_direct", user_objects=u or [])

	def OnAddAlias(self, event=None):
		"""Add an alias for a user."""
		account = get_app().currentAccount
		# Get users from current item (handles both statuses and notifications)
		u = self._get_users_from_current_item(account)
		u2 = [i.acct for i in u] if u else []
		# Use alias type to pass user objects
		chooser.chooser(account, "Add Alias", "Enter or choose a username to alias", u2, "alias", user_objects=u or [])

	def AddAlias(self, event=None):
		"""Alias for OnAddAlias (for keymap compatibility)."""
		self.OnAddAlias(event)

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

	def OnAddToList(self, event=None):
		status = self.get_current_status()
		if status:
			misc.add_to_list(get_app().currentAccount, status)

	def OnRemoveFromList(self, event=None):
		status = self.get_current_status()
		if status:
			misc.remove_from_list(get_app().currentAccount, status)

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
				# Stop streaming for this timeline
				tl.stop_stream()
				# Clear cached data for this timeline
				try:
					tl.clear_cache()
				except Exception as e:
					print(f"Error clearing cache for {tl.name}: {e}")
				get_app().currentAccount.timelines.remove(tl)
				sound.play(get_app().currentAccount,"close")
				self.refreshTimelines()
				self.list.SetSelection(0)
				get_app().currentAccount.currentIndex=0
				self.on_list_change(None)
				del tl

	def OnReply(self, event=None):
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
		status = self.get_current_status()
		if status:
			misc.quote(get_app().currentAccount, status)

	def OnMessage(self, event=None):
		status = self.get_current_status()
		if status:
			misc.message(get_app().currentAccount, status)

	def OnLikeToggle(self, event=None):
		"""Toggle favourite/like state for a status."""
		status = self.get_current_status()
		if status:
			account = get_app().currentAccount
			try:
				# Get the actual status (unwrap boosts) - need to interact with the original post
				status_to_check = status.reblog if hasattr(status, 'reblog') and status.reblog else status
				status_id = misc.get_interaction_id(account, status_to_check)
				if getattr(status_to_check, 'favourited', False):
					# Check if confirmation is required
					if get_app().prefs.confirm_unfavorite:
						dlg = wx.MessageDialog(self, "Are you sure you want to unfavorite this post?", "Confirm Unfavorite", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
						if dlg.ShowModal() != wx.ID_YES:
							dlg.Destroy()
							return
						dlg.Destroy()
					account.unfavourite(status_id)
					new_state = False
					sound.play(account, "unlike")
				else:
					# Check if confirmation is required
					if get_app().prefs.confirm_favorite:
						dlg = wx.MessageDialog(self, "Are you sure you want to favorite this post?", "Confirm Favorite", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
						if dlg.ShowModal() != wx.ID_YES:
							dlg.Destroy()
							return
						dlg.Destroy()
					account.favourite(status_id)
					account.app.prefs.favourites_sent += 1
					new_state = True
					sound.play(account, "like")
				# Sync state across all buffers
				self._sync_status_state_across_buffers(account, status_id, favourited=new_state)
			except Exception as error:
				account.app.handle_error(error, "toggle favourite")

	def OnBoostToggle(self, event=None):
		"""Toggle boost/retweet state for a status."""
		status = self.get_current_status()
		if status:
			account = get_app().currentAccount
			try:
				# Get the actual status (unwrap boosts) - need to interact with the original post
				status_to_check = status.reblog if hasattr(status, 'reblog') and status.reblog else status
				status_id = misc.get_interaction_id(account, status_to_check)
				if getattr(status_to_check, 'reblogged', False):
					# Check if confirmation is required
					if get_app().prefs.confirm_unboost:
						dlg = wx.MessageDialog(self, "Are you sure you want to unboost this post?", "Confirm Unboost", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
						if dlg.ShowModal() != wx.ID_YES:
							dlg.Destroy()
							return
						dlg.Destroy()
					account.unboost(status_id)
					new_state = False
					sound.play(account, "delete")
				else:
					# Check if confirmation is required
					if get_app().prefs.confirm_boost:
						dlg = wx.MessageDialog(self, "Are you sure you want to boost this post?", "Confirm Boost", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
						if dlg.ShowModal() != wx.ID_YES:
							dlg.Destroy()
							return
						dlg.Destroy()
					account.boost(status_id)
					account.app.prefs.boosts_sent += 1
					new_state = True
					sound.play(account, "send_repost")
				# Sync state across all buffers
				self._sync_status_state_across_buffers(account, status_id, reblogged=new_state)
			except Exception as error:
				account.app.handle_error(error, "toggle boost")

	def OnBlockToggle(self, event=None):
		"""Toggle block state for a user."""
		account = get_app().currentAccount
		# Get users from current item (handles both statuses and notifications)
		u = self._get_users_from_current_item(account)
		if not u:
			speak.speak("No user found")
			return
		if len(u) > 1:
			u2 = [i.acct for i in u]
			chooser.chooser(account, "Block/Unblock User", "Select user", u2, "block_toggle")
		else:
			self._toggle_block_user(account, u[0])

	def _toggle_block_user(self, account, user):
		"""Toggle block state for a specific user."""
		try:
			# Check current relationship - platform agnostic
			blocking = False
			platform_type = getattr(account.prefs, 'platform_type', 'mastodon')

			if platform_type == 'mastodon' and hasattr(account, 'api') and hasattr(account.api, 'account_relationships'):
				try:
					relationships = account.api.account_relationships([user.id])
					if relationships and len(relationships) > 0:
						blocking = getattr(relationships[0], 'blocking', False)
				except:
					pass
			elif platform_type == 'bluesky' and hasattr(account, '_platform') and account._platform:
				# Bluesky - fetch fresh profile to get current relationship state
				try:
					profile = account._platform.client.get_profile(user.id)
					if profile and hasattr(profile, 'viewer') and profile.viewer:
						blocking = bool(getattr(profile.viewer, 'blocking', None))
				except:
					pass

			if blocking:
				# Check if confirmation is required
				if get_app().prefs.confirm_unblock:
					dlg = wx.MessageDialog(self, f"Are you sure you want to unblock {user.acct}?", "Confirm Unblock", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
					if dlg.ShowModal() != wx.ID_YES:
						dlg.Destroy()
						return
					dlg.Destroy()
				account.unblock(user.id)
				sound.play(account, "unblock")
				speak.speak(f"Unblocked {user.acct}")
			else:
				# Check if confirmation is required
				if get_app().prefs.confirm_block:
					dlg = wx.MessageDialog(self, f"Are you sure you want to block {user.acct}?", "Confirm Block", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
					if dlg.ShowModal() != wx.ID_YES:
						dlg.Destroy()
						return
					dlg.Destroy()
				account.block(user.id)
				sound.play(account, "block")
				speak.speak(f"Blocked {user.acct}")
		except Exception as error:
			account.app.handle_error(error, "toggle block")

	def OnBookmarkToggle(self, event=None):
		"""Toggle bookmark state for a status."""
		status = self.get_current_status()
		if status:
			account = get_app().currentAccount
			platform_type = getattr(account.prefs, 'platform_type', 'mastodon')
			if platform_type == 'bluesky':
				speak.speak("Bookmarks are not supported on Bluesky")
				return
			try:
				# Get the actual status (unwrap boosts) - need to interact with the original post
				status_to_check = status.reblog if hasattr(status, 'reblog') and status.reblog else status
				status_id = misc.get_interaction_id(account, status_to_check)
				if getattr(status_to_check, 'bookmarked', False):
					account.api.status_unbookmark(status_id)
					status_to_check.bookmarked = False
					sound.play(account, "unlike")
					speak.speak("Bookmark removed")
					# Remove from bookmarks timeline if we're in it
					if account.currentTimeline.type == "bookmarks":
						tl = account.currentTimeline
						idx = tl.index
						if 0 <= idx < len(tl.statuses):
							tl.statuses.pop(idx)
							# Adjust index if needed
							if tl.index >= len(tl.statuses) and len(tl.statuses) > 0:
								tl.index = len(tl.statuses) - 1
							self.on_list_change(None)
				else:
					account.api.status_bookmark(status_id)
					status_to_check.bookmarked = True
					sound.play(account, "like")
					speak.speak("Bookmarked")
			except Exception as error:
				account.app.handle_error(error, "toggle bookmark")

	def _get_users_from_current_item(self, account):
		"""Get users from the current item (status or notification)."""
		tl_type = account.currentTimeline.type
		item = account.currentTimeline.statuses[account.currentTimeline.index]
		users = []

		if tl_type == "notifications":
			# For notifications, include the notification's account (who triggered it)
			if hasattr(item, 'account') and item.account:
				users.append(item.account)
			# Also include users from the status if there is one
			if hasattr(item, 'status') and item.status:
				status_users = account.app.get_user_objects_in_status(account, item.status)
				for u in status_users:
					if u not in users and u.id != account.me.id:
						users.append(u)
		else:
			# For regular statuses
			status = self.get_current_status()
			if status:
				users = account.app.get_user_objects_in_status(account, status)

		# Filter out self
		users = [u for u in users if u.id != account.me.id]
		return users

	def OnFollowToggle(self, event=None):
		"""Toggle follow state for a user - checks relationship and follows/unfollows accordingly."""
		account = get_app().currentAccount
		# Get users from current item (handles both statuses and notifications)
		u = self._get_users_from_current_item(account)
		if not u:
			speak.speak("No user found")
			return
		# If multiple users, use the chooser
		if len(u) > 1:
			u2 = [i.acct for i in u]
			chooser.chooser(account, "Follow/Unfollow User", "Select user", u2, "follow_toggle")
		else:
			# Single user - check relationship and toggle
			self._toggle_follow_user(account, u[0])

	def _toggle_follow_user(self, account, user):
		"""Toggle follow state for a specific user."""
		try:
			# Check current relationship - platform agnostic
			following = False
			platform_type = getattr(account.prefs, 'platform_type', 'mastodon')

			if platform_type == 'mastodon' and hasattr(account, 'api') and hasattr(account.api, 'account_relationships'):
				try:
					relationships = account.api.account_relationships([user.id])
					if relationships and len(relationships) > 0:
						following = getattr(relationships[0], 'following', False)
				except:
					pass
			elif platform_type == 'bluesky' and hasattr(account, '_platform') and account._platform:
				# Bluesky - fetch fresh profile to get current relationship state
				try:
					profile = account._platform.client.get_profile(user.id)
					if profile and hasattr(profile, 'viewer') and profile.viewer:
						following = bool(getattr(profile.viewer, 'following', None))
				except:
					pass

			if following:
				# Check if confirmation is required
				if get_app().prefs.confirm_unfollow:
					dlg = wx.MessageDialog(self, f"Are you sure you want to unfollow {user.acct}?", "Confirm Unfollow", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
					if dlg.ShowModal() != wx.ID_YES:
						dlg.Destroy()
						return
					dlg.Destroy()
				account.unfollow(user.id)
				# Update user's viewer info to reflect new state
				if hasattr(user, 'viewer') and user.viewer:
					user.viewer.following = None
				sound.play(account, "unfollow")
				speak.speak(f"Unfollowed {user.acct}")
			else:
				# Check if confirmation is required
				if get_app().prefs.confirm_follow:
					dlg = wx.MessageDialog(self, f"Are you sure you want to follow {user.acct}?", "Confirm Follow", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
					if dlg.ShowModal() != wx.ID_YES:
						dlg.Destroy()
						return
					dlg.Destroy()
				account.follow(user.id)
				# Update user's viewer info to reflect new state
				if hasattr(user, 'viewer') and user.viewer:
					user.viewer.following = True  # Set truthy value
				sound.play(account, "follow")
				speak.speak(f"Followed {user.acct}")
		except Exception as error:
			account.app.handle_error(error, "toggle follow")

	def OnHideBoostsToggle(self, event=None):
		"""Toggle whether to show/hide boosts from a user (Mastodon only)."""
		status = self.get_current_status()
		if not status:
			return
		account = get_app().currentAccount
		# Get user
		u = account.app.get_user_objects_in_status(account, status)
		if not u:
			speak.speak("No user found")
			return
		# If multiple users, use first one (the author)
		user = u[0]
		try:
			# Check current relationship
			relationships = account.api.account_relationships([user.id])
			if relationships and len(relationships) > 0:
				rel = relationships[0]
				is_showing_reblogs = getattr(rel, 'showing_reblogs', True)
				# Toggle reblogs visibility - use account_follow with reblogs parameter
				account.api.account_follow(id=user.id, reblogs=not is_showing_reblogs)
				if is_showing_reblogs:
					speak.speak(f"Hiding boosts from {user.acct}")
					sound.play(account, "mute")
				else:
					speak.speak(f"Showing boosts from {user.acct}")
					sound.play(account, "unmute")
		except Exception as error:
			account.app.handle_error(error, "toggle boosts visibility")

	def OnMuteToggle(self, event=None):
		"""Toggle mute state for a user - checks relationship and mutes/unmutes accordingly."""
		account = get_app().currentAccount
		# Get users from current item (handles both statuses and notifications)
		u = self._get_users_from_current_item(account)
		if not u:
			speak.speak("No user found")
			return
		# If multiple users, use the chooser
		if len(u) > 1:
			u2 = [i.acct for i in u]
			chooser.chooser(account, "Mute/Unmute User", "Select user", u2, "mute_toggle")
		else:
			# Single user - check relationship and toggle
			self._toggle_mute_user(account, u[0])

	def _toggle_mute_user(self, account, user):
		"""Toggle mute state for a specific user."""
		try:
			# Check current relationship - platform agnostic
			muting = False
			platform_type = getattr(account.prefs, 'platform_type', 'mastodon')

			if platform_type == 'mastodon' and hasattr(account, 'api') and hasattr(account.api, 'account_relationships'):
				try:
					relationships = account.api.account_relationships([user.id])
					if relationships and len(relationships) > 0:
						muting = getattr(relationships[0], 'muting', False)
				except:
					pass
			elif platform_type == 'bluesky' and hasattr(account, '_platform') and account._platform:
				# Bluesky - fetch fresh profile to get current relationship state
				try:
					profile = account._platform.client.get_profile(user.id)
					if profile and hasattr(profile, 'viewer') and profile.viewer:
						muting = bool(getattr(profile.viewer, 'muted', False))
				except:
					pass

			if muting:
				# Check if confirmation is required
				if get_app().prefs.confirm_unmute:
					dlg = wx.MessageDialog(self, f"Are you sure you want to unmute {user.acct}?", "Confirm Unmute", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
					if dlg.ShowModal() != wx.ID_YES:
						dlg.Destroy()
						return
					dlg.Destroy()
				account.unmute(user.id)
				sound.play(account, "unmute")
				speak.speak(f"Unmuted {user.acct}")
			else:
				# Check if confirmation is required
				if get_app().prefs.confirm_mute:
					dlg = wx.MessageDialog(self, f"Are you sure you want to mute {user.acct}?", "Confirm Mute", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
					if dlg.ShowModal() != wx.ID_YES:
						dlg.Destroy()
						return
					dlg.Destroy()
				# For Mastodon, use mute dialog for options; for Bluesky, mute directly
				if platform_type == 'mastodon':
					from . import mute_dialog
					mute_dialog.show_mute_dialog(account, user)
				else:
					account.mute(user.id)
					sound.play(account, "mute")
					speak.speak(f"Muted {user.acct}")
		except Exception as error:
			account.app.handle_error(error, "toggle mute")

	def OnMuteConversationToggle(self, event=None):
		"""Toggle mute state for a conversation/thread."""
		status = self.get_current_status()
		if not status:
			return
		account = get_app().currentAccount
		# Get the actual status (unwrap boosts)
		status_to_check = status.reblog if hasattr(status, 'reblog') and status.reblog else status
		# Use _original_status_id if available (for mentions timeline where id is notification id)
		status_id = getattr(status_to_check, '_original_status_id', None) or status_to_check.id
		is_muted = getattr(status_to_check, 'muted', False)
		try:
			if is_muted:
				if account.unmute_conversation(status_id):
					speak.speak("Conversation unmuted")
				else:
					speak.speak("Failed to unmute conversation")
			else:
				if account.mute_conversation(status_id):
					speak.speak("Conversation muted")
				else:
					speak.speak("Failed to mute conversation")
		except Exception as error:
			account.app.handle_error(error, "mute conversation")

	def OnVotePoll(self, event=None):
		"""Open the poll dialog for voting or viewing results."""
		status = self.get_current_status()
		if not status:
			return
		# Get the actual status (unwrap boosts, get notification status)
		if hasattr(status, 'status') and status.status:
			# Notification with a status
			status_to_check = status.status
		elif hasattr(status, 'reblog') and status.reblog:
			status_to_check = status.reblog
		else:
			status_to_check = status
		if hasattr(status_to_check, 'poll') and status_to_check.poll:
			# Refresh status from API to ensure poll data is up to date
			# (cached polls may have missing options or stale vote counts)
			account = get_app().currentAccount
			try:
				if hasattr(account, '_platform') and account._platform:
					fresh_status = account._platform.get_status(status_to_check.id)
				else:
					fresh_status = account.api.status(status_to_check.id)
					# Convert to universal if needed
					if hasattr(fresh_status, 'poll'):
						from platforms.mastodon.models import mastodon_status_to_universal
						fresh_status = mastodon_status_to_universal(fresh_status)
				if fresh_status and hasattr(fresh_status, 'poll') and fresh_status.poll:
					status_to_check = fresh_status
			except Exception as e:
				# If refresh fails, continue with cached version
				print(f"Failed to refresh poll status: {e}")
			from . import poll_dialog
			poll_dialog.show_poll_dialog(account, status_to_check)

	def OnViewPollResults(self, event=None):
		"""View poll results from a poll ended notification."""
		# Get the notification item directly (not through get_current_status which unwraps)
		tl = get_app().currentAccount.currentTimeline
		if tl.type != "notifications" or not tl.statuses:
			return
		item = tl.statuses[tl.index]
		# Get the status from the notification
		status = getattr(item, 'status', None)
		if not status:
			speak.speak("No poll data available")
			return
		# Show poll dialog - it will fetch fresh results from the server
		from . import poll_dialog
		poll_dialog.show_poll_dialog(get_app().currentAccount, status)

	def OnFollowHashtag(self, event=None):
		"""Show dialog to follow a hashtag from the current post."""
		status = self.get_current_status()
		if not status:
			return
		# Get the actual status (unwrap boosts)
		status_to_check = status.reblog if hasattr(status, 'reblog') and status.reblog else status
		misc.hashtag_chooser(get_app().currentAccount, status_to_check, "follow")

	def OnUnfollowHashtag(self, event=None):
		"""Show dialog to unfollow a hashtag from the current post."""
		status = self.get_current_status()
		if not status:
			return
		# Get the actual status (unwrap boosts)
		status_to_check = status.reblog if hasattr(status, 'reblog') and status.reblog else status
		misc.hashtag_chooser(get_app().currentAccount, status_to_check, "unfollow")

global window
window=MainGui(application.name+" "+application.version)
