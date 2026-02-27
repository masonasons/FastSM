from application import get_app
from . import main, misc
import speak
import sound
import threading
import wx

def register_key(key,name,reg=True):
	def _run(target):
		try:
			if reg:
				result = main.window.handler.register_key(key, target)
			else:
				result = main.window.handler.unregister_key(key, target)
			return True if result is None else bool(result)
		except:
			return False
	if hasattr(main.window,name):
		return _run(getattr(main.window,name))
	if hasattr(main.window,"on"+name):
		return _run(getattr(main.window,"on"+name))
	if hasattr(main.window,"On"+name):
		return _run(getattr(main.window,"On"+name))
	if hasattr(inv,name):
		return _run(getattr(inv,name))
	return False

class invisible_interface(object):
	def _ensure_current_timeline(self):
		"""Ensure currentAccount/currentTimeline pointers are usable."""
		app = get_app()
		account = getattr(app, "currentAccount", None)
		if account is None:
			return None
		timelines = account.list_timelines()
		if not timelines:
			return None
		if account.currentIndex is None or account.currentIndex < 0 or account.currentIndex >= len(timelines):
			account.currentIndex = 0
		if account.currentTimeline is None or account.currentTimeline not in timelines:
			account.currentTimeline = timelines[account.currentIndex]
		return account.currentTimeline

	def _require_current_timeline(self):
		tl = self._ensure_current_timeline()
		if tl is None:
			speak.speak("No timeline selected")
			return None
		return tl

	def focus_tl(self,sync=False):
		tl = self._require_current_timeline()
		if tl is None:
			return
		account = get_app().currentAccount
		account.currentTimeline = account.list_timelines()[account.currentIndex]
		if not sync and get_app().prefs.invisible_sync or sync:
			# Use CallAfter for thread-safe wx operations
			# Capture values at call time to avoid race conditions
			current_index = account.currentIndex
			def update_ui(idx=current_index):
				main.window.list.SetSelection(idx)
				main.window.on_list_change(None)
			wx.CallAfter(update_ui)
		extratext=""
		if get_app().prefs.position:
			if len(account.currentTimeline.statuses)==0:
				extratext+="Empty"
			else:
				extratext+=str(account.currentTimeline.index+1)+" of "+str(len(account.currentTimeline.statuses))
		if account.currentTimeline.read:
			extratext+=", Autoread"
		if account.currentTimeline.mute:
			extratext+=", muted"
		speak.speak(account.currentTimeline.name+". "+extratext,True)
		if not get_app().prefs.invisible_sync and not sync:
			wx.CallAfter(main.window.play_earcon)

	def focus_tl_item(self):
		tl = self._require_current_timeline()
		if tl is None:
			return
		if get_app().prefs.invisible_sync:
			# Use CallAfter for thread-safe wx operations
			# Capture values at call time to avoid race conditions
			current_tl_index = tl.index
			def update_ui(idx=current_tl_index):
				main.window.list2.SetSelection(idx)
				main.window.on_list2_change(None)
			wx.CallAfter(update_ui)
		else:
			item = tl.statuses[tl.index]
			# Handle conversations - get last_status for URL detection
			if tl.type == "conversations":
				if hasattr(item, 'last_status') and item.last_status:
					item = item.last_status
				else:
					item = None
			# Handle notifications - get the status from the notification
			elif tl.type == "notifications":
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
			# Check if post mentions the current user (skip in mentions timeline - redundant)
			if item and get_app().prefs.earcon_mention and tl.type != "mentions":
				status_to_check = item.reblog if hasattr(item, 'reblog') and item.reblog else item
				mentions = getattr(status_to_check, 'mentions', []) or []
				my_id = str(get_app().currentAccount.me.id)
				for mention in mentions:
					mention_id = str(getattr(mention, 'id', ''))
					if mention_id == my_id:
						sound.play(get_app().currentAccount, "mention")
						break
		self.speak_item()

	def speak_item(self):
		tl = self._require_current_timeline()
		if tl is None:
			return
		account = get_app().currentAccount
		tl_type = tl.type
		item = tl.statuses[tl.index]
		cached = getattr(item, "_display_cache", None)
		if cached:
			speak.speak(cached, True)
			return
		if tl_type == "notifications":
			text = get_app().process_notification(item, account=account)
		elif tl_type in ("messages", "conversations"):
			text = get_app().process_conversation(item, account=account)
		else:
			# mentions now treated same as home/user/etc.
			text = get_app().process_status(item, account=account)
		try:
			item._display_cache = text
		except Exception:
			pass
		speak.speak(text, True)

	def prev_tl(self,sync=False):
		tl = self._require_current_timeline()
		if tl is None:
			return
		account = get_app().currentAccount
		account.currentIndex-=1
		if account.currentIndex<0:
			account.currentIndex=len(account.list_timelines())-1
		self.focus_tl(sync)

	def next_tl(self,sync=False):
		tl = self._require_current_timeline()
		if tl is None:
			return
		account = get_app().currentAccount
		account.currentIndex+=1
		if account.currentIndex>=len(account.list_timelines()):
			account.currentIndex=0
		self.focus_tl(sync)

	def goto_tl(self, index, sync=False):
		"""Go to a specific timeline by index (0-based)."""
		account = get_app().currentAccount
		timelines = account.list_timelines()
		if index < 0 or index >= len(timelines):
			sound.play(get_app().currentAccount, "boundary")
			return
		account.currentIndex = index
		self.focus_tl(sync)

	def prev_account(self):
		main.window.OnPrevAccount()

	def next_account(self):
		main.window.OnNextAccount()

	def prev_item(self):
		tl = self._require_current_timeline()
		if tl is None:
			return
		if tl.index==0 or len(tl.statuses)==0:
			sound.play(get_app().currentAccount,"boundary")
			if get_app().prefs.repeat:
				self.speak_item()
			return
		tl.index-=1
		tl.mark_position_moved()
		self.focus_tl_item()

	def prev_item_jump(self):
		tl = self._require_current_timeline()
		if tl is None:
			return
		if tl.index < 20:
			sound.play(get_app().currentAccount,"boundary")
			if get_app().prefs.repeat:
				self.speak_item()
			return
		tl.index -= 20
		tl.mark_position_moved()
		self.focus_tl_item()
	
	def top_item(self):
		tl = self._require_current_timeline()
		if tl is None:
			return
		tl.index=0
		tl.mark_position_moved()
		self.focus_tl_item()
	
	def next_item(self):
		tl = self._require_current_timeline()
		if tl is None:
			return
		if tl.index==len(tl.statuses)-1 or len(tl.statuses)==0:
			sound.play(get_app().currentAccount,"boundary")
			if get_app().prefs.repeat:
				self.speak_item()
			return
		tl.index+=1
		tl.mark_position_moved()
		self.focus_tl_item()
	
	def next_item_jump(self):
		tl = self._require_current_timeline()
		if tl is None:
			return
		if tl.index >= len(tl.statuses) - 20:
			sound.play(get_app().currentAccount,"boundary")
			if get_app().prefs.repeat:
				self.speak_item()
			return
		tl.index += 20
		tl.mark_position_moved()
		self.focus_tl_item()

	def bottom_item(self):
		tl = self._require_current_timeline()
		if tl is None:
			return
		tl.index=len(tl.statuses)-1
		tl.mark_position_moved()
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
		tl = self._require_current_timeline()
		if tl is None:
			return
		threading.Thread(target=tl.load, kwargs={'speech': True}, daemon=True).start()

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
