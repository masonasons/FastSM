from application import get_app
from . import main, misc
import speak
import sound
import threading
import wx

def register_key(key,name,reg=True):
	if hasattr(main.window,name):
		try:
			if reg:
				main.window.handler.register_key(key,getattr(main.window,name))
			else:
				main.window.handler.unregister_key(key,getattr(main.window,name))
			return True
		except:
			return False
	if hasattr(main.window,"on"+name):
		try:
			if reg:
				main.window.handler.register_key(key,getattr(main.window,"on"+name))
			else:
				main.window.handler.unregister_key(key,getattr(main.window,"on"+name))
			return True
		except:
			return False
	if hasattr(main.window,"On"+name):
		try:
			if reg:
				main.window.handler.register_key(key,getattr(main.window,"On"+name))
			else:
				main.window.handler.unregister_key(key,getattr(main.window,"On"+name))
			return True
		except:
			return False
	if hasattr(inv,name):
		try:
			if reg:
				main.window.handler.register_key(key,getattr(inv,name))
			else:
				main.window.handler.unregister_key(key,getattr(inv,name))
			return True
		except:
			return False

class invisible_interface(object):
	def focus_tl(self,sync=False):
		get_app().currentAccount.currentTimeline=get_app().currentAccount.list_timelines()[get_app().currentAccount.currentIndex]
		if not sync and get_app().prefs.invisible_sync or sync:
			# Use CallAfter for thread-safe wx operations
			# Capture values at call time to avoid race conditions
			current_index = get_app().currentAccount.currentIndex
			def update_ui(idx=current_index):
				main.window.list.SetSelection(idx)
				main.window.on_list_change(None)
			wx.CallAfter(update_ui)
		extratext=""
		if get_app().prefs.position:
			if len(get_app().currentAccount.currentTimeline.statuses)==0:
				extratext+="Empty"
			else:
				extratext+=str(get_app().currentAccount.currentTimeline.index+1)+" of "+str(len(get_app().currentAccount.currentTimeline.statuses))
		if get_app().currentAccount.currentTimeline.read:
			extratext+=", Autoread"
		if get_app().currentAccount.currentTimeline.mute:
			extratext+=", muted"
		speak.speak(get_app().currentAccount.currentTimeline.name+". "+extratext,True)
		if not get_app().prefs.invisible_sync and not sync:
			wx.CallAfter(main.window.play_earcon)

	def focus_tl_item(self):
		if get_app().prefs.invisible_sync:
			# Use CallAfter for thread-safe wx operations
			# Capture values at call time to avoid race conditions
			current_tl_index = get_app().currentAccount.currentTimeline.index
			def update_ui(idx=current_tl_index):
				main.window.list2.SetSelection(idx)
				main.window.on_list2_change(None)
			wx.CallAfter(update_ui)
		else:
			item = get_app().currentAccount.currentTimeline.statuses[get_app().currentAccount.currentTimeline.index]
			# Handle conversations - get last_status for URL detection
			if get_app().currentAccount.currentTimeline.type == "conversations":
				if hasattr(item, 'last_status') and item.last_status:
					item = item.last_status
				else:
					item = None
			# Handle notifications - get the status from the notification
			elif get_app().currentAccount.currentTimeline.type == "notifications":
				if hasattr(item, 'status') and item.status:
					item = item.status
				else:
					item = None
			if item and get_app().prefs.earcon_audio:
				# Get the actual status (unwrap boosts)
				status_to_check = item.reblog if hasattr(item, 'reblog') and item.reblog else item
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
				elif len(sound.get_media_urls(get_app().find_urls_in_status(item))) > 0:
					sound.play(get_app().currentAccount, "media")
		self.speak_item()

	def speak_item(self):
		account = get_app().currentAccount
		tl_type = account.currentTimeline.type
		item = account.currentTimeline.statuses[account.currentTimeline.index]
		if tl_type == "notifications":
			speak.speak(get_app().process_notification(item, account=account), True)
		elif tl_type in ("messages", "conversations"):
			speak.speak(get_app().process_conversation(item, account=account), True)
		else:
			# mentions now treated same as home/user/etc.
			speak.speak(get_app().process_status(item, account=account), True)

	def prev_tl(self,sync=False):
		get_app().currentAccount.currentIndex-=1
		if get_app().currentAccount.currentIndex<0:
			get_app().currentAccount.currentIndex=len(get_app().currentAccount.list_timelines())-1
		self.focus_tl(sync)

	def next_tl(self,sync=False):
		get_app().currentAccount.currentIndex+=1
		if get_app().currentAccount.currentIndex>=len(get_app().currentAccount.list_timelines()):
			get_app().currentAccount.currentIndex=0
		self.focus_tl(sync)

	def goto_tl(self, index, sync=False):
		"""Go to a specific timeline by index (0-based)."""
		timelines = get_app().currentAccount.list_timelines()
		if index < 0 or index >= len(timelines):
			sound.play(get_app().currentAccount, "boundary")
			return
		get_app().currentAccount.currentIndex = index
		self.focus_tl(sync)

	def prev_account(self):
		main.window.OnPrevAccount()

	def next_account(self):
		main.window.OnNextAccount()

	def prev_item(self):
		if get_app().currentAccount.currentTimeline.index==0 or len(get_app().currentAccount.currentTimeline.statuses)==0:
			sound.play(get_app().currentAccount,"boundary")
			if get_app().prefs.repeat:
				self.speak_item()
			return
		get_app().currentAccount.currentTimeline.index-=1
		get_app().currentAccount.currentTimeline.mark_position_moved()
		self.focus_tl_item()

	def prev_item_jump(self):
		if get_app().currentAccount.currentTimeline.index < 20:
			sound.play(get_app().currentAccount,"boundary")
			if get_app().prefs.repeat:
				self.speak_item()
			return
		get_app().currentAccount.currentTimeline.index -= 20
		get_app().currentAccount.currentTimeline.mark_position_moved()
		self.focus_tl_item()
	
	def top_item(self):
		get_app().currentAccount.currentTimeline.index=0
		get_app().currentAccount.currentTimeline.mark_position_moved()
		self.focus_tl_item()
	
	def next_item(self):
		if get_app().currentAccount.currentTimeline.index==len(get_app().currentAccount.currentTimeline.statuses)-1 or len(get_app().currentAccount.currentTimeline.statuses)==0:
			sound.play(get_app().currentAccount,"boundary")
			if get_app().prefs.repeat:
				self.speak_item()
			return
		get_app().currentAccount.currentTimeline.index+=1
		get_app().currentAccount.currentTimeline.mark_position_moved()
		self.focus_tl_item()
	
	def next_item_jump(self):
		if get_app().currentAccount.currentTimeline.index >= len(get_app().currentAccount.currentTimeline.statuses) - 20:
			sound.play(get_app().currentAccount,"boundary")
			if get_app().prefs.repeat:
				self.speak_item()
			return
		get_app().currentAccount.currentTimeline.index += 20
		get_app().currentAccount.currentTimeline.mark_position_moved()
		self.focus_tl_item()

	def bottom_item(self):
		get_app().currentAccount.currentTimeline.index=len(get_app().currentAccount.currentTimeline.statuses)-1
		get_app().currentAccount.currentTimeline.mark_position_moved()
		self.focus_tl_item()
	
	def previous_from_user(self):
		main.window.OnPreviousFromUser()
		self.speak_item()
	
	def next_from_user(self):
		main.window.OnNextFromUser()
		self.speak_item()

	def previous_in_thread(self):
		main.window.OnPreviousInThread()
		self.speak_item()

	def next_in_thread(self):
		main.window.OnNextInThread()
		self.speak_item()

	def refresh(self,event=None):
		threading.Thread(target=get_app().currentAccount.currentTimeline.load, kwargs={'speech': True}, daemon=True).start()

	def speak_account(self):
		account = get_app().currentAccount
		acct = account.me.acct
		# Add instance for Mastodon accounts
		platform_type = getattr(account.prefs, 'platform_type', 'mastodon')
		if platform_type == 'mastodon' and hasattr(account, 'api') and hasattr(account.api, 'api_base_url'):
			from urllib.parse import urlparse
			parsed = urlparse(account.api.api_base_url)
			instance = parsed.netloc or parsed.path.strip('/')
			if instance:
				acct = f"{acct} on {instance}"
		speak.speak(acct)

	def close(self):
		main.window.OnClose()

	def StopAudio(self):
		sound.stop()
		speak.speak("Stopped")

	def CustomTimelines(self):
		main.window.OnCustomTimelines()

	def FilterTimeline(self):
		main.window.OnFilterTimeline()

	def AccountOptions(self):
		"""Open account options dialog."""
		main.window.OnAccountOptions()

	def FollowToggle(self):
		"""Toggle follow state for a user."""
		main.window.OnFollowToggle()

	def MuteToggle(self):
		"""Toggle mute state for a user."""
		main.window.OnMuteToggle()

	def BlockToggle(self):
		"""Toggle block state for a user."""
		main.window.OnBlockToggle()

	def LikeToggle(self):
		"""Toggle favourite/like state for a post."""
		main.window.OnLikeToggle()

	def BoostToggle(self):
		"""Toggle boost/retweet state for a post."""
		main.window.OnBoostToggle()

	def BookmarkToggle(self):
		"""Toggle bookmark state for a post."""
		main.window.OnBookmarkToggle()

	def NextAccount(self):
		"""Switch to the next account."""
		main.window.OnNextAccount()

	def PrevAccount(self):
		"""Switch to the previous account."""
		main.window.OnPrevAccount()

	def PinToggle(self):
		status = main.window.get_current_status()
		if status:
			misc.pin_toggle(get_app().currentAccount, status)

	def UpdateProfile(self):
		"""Open the update profile dialog."""
		main.window.OnUpdateProfile()

	def ContextMenu(self):
		"""Open the context menu from invisible interface."""
		import wx
		def show_menu():
			if not main.window:
				return
			try:
				if not main.window.IsShown():
					main.window.Show(True)
					main.safe_raise_window(main.window)
				# Sync the list selection
				main.window.list.SetSelection(get_app().currentAccount.currentIndex)
				main.window.list2.SetSelection(get_app().currentAccount.currentTimeline.index)
				main.window.list2.SetFocus()
				main.window.OnPostContextMenu(None)
			except (RuntimeError, Exception):
				pass  # Window may have been destroyed
		wx.CallAfter(show_menu)

inv=invisible_interface()