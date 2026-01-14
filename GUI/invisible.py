from application import get_app
from . import main
import speak
import sound
import threading
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
			main.window.list.SetSelection(get_app().currentAccount.currentIndex)
			main.window.on_list_change(None)
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
			main.window.play_earcon()

	def focus_tl_item(self):
		if get_app().prefs.invisible_sync:
			main.window.list2.SetSelection(get_app().currentAccount.currentTimeline.index)
			main.window.on_list2_change(None)
		else:
			item = get_app().currentAccount.currentTimeline.statuses[get_app().currentAccount.currentTimeline.index]
			# Handle conversations - get last_status for URL detection
			if get_app().currentAccount.currentTimeline.type == "conversations":
				if hasattr(item, 'last_status') and item.last_status:
					item = item.last_status
				else:
					item = None
			if item and get_app().prefs.earcon_audio:
				# Check for audio attachments or audio URLs in post
				has_audio = sound.has_audio_attachment(item) or len(sound.get_media_urls(get_app().find_urls_in_status(item))) > 0
				if has_audio:
					sound.play(get_app().currentAccount,"media")
		self.speak_item()

	def speak_item(self):
		tl_type = get_app().currentAccount.currentTimeline.type
		item = get_app().currentAccount.currentTimeline.statuses[get_app().currentAccount.currentTimeline.index]
		if tl_type == "notifications":
			speak.speak(get_app().process_notification(item), True)
		elif tl_type in ("messages", "conversations"):
			speak.speak(get_app().process_conversation(item), True)
		else:
			# mentions now treated same as home/user/etc.
			speak.speak(get_app().process_status(item), True)

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

	def prev_item(self):
		if get_app().currentAccount.currentTimeline.index==0 or len(get_app().currentAccount.currentTimeline.statuses)==0:
			sound.play(get_app().currentAccount,"boundary")
			if get_app().prefs.repeat:
				self.speak_item()
			return
		get_app().currentAccount.currentTimeline.index-=1
		self.focus_tl_item()

	def prev_item_jump(self):
		if get_app().currentAccount.currentTimeline.index < 20:
			sound.play(get_app().currentAccount,"boundary")
			if get_app().prefs.repeat:
				self.speak_item()
			return
		get_app().currentAccount.currentTimeline.index -= 20
		self.focus_tl_item()
	
	def top_item(self):
		get_app().currentAccount.currentTimeline.index=0
		self.focus_tl_item()
	
	def next_item(self):
		if get_app().currentAccount.currentTimeline.index==len(get_app().currentAccount.currentTimeline.statuses)-1 or len(get_app().currentAccount.currentTimeline.statuses)==0:
			sound.play(get_app().currentAccount,"boundary")
			if get_app().prefs.repeat:
				self.speak_item()
			return
		get_app().currentAccount.currentTimeline.index+=1
		self.focus_tl_item()
	
	def next_item_jump(self):
		if get_app().currentAccount.currentTimeline.index >= len(get_app().currentAccount.currentTimeline.statuses) - 20:
			sound.play(get_app().currentAccount,"boundary")
			if get_app().prefs.repeat:
				self.speak_item()
			return
		get_app().currentAccount.currentTimeline.index += 20
		self.focus_tl_item()
	
	def bottom_item(self):
		get_app().currentAccount.currentTimeline.index=len(get_app().currentAccount.currentTimeline.statuses)-1
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
		speak.speak(get_app().currentAccount.me.acct)

	def close(self):
		main.window.OnClose()

	def StopAudio(self):
		sound.stop()
		speak.speak("Stopped")

	def CustomTimelines(self):
		main.window.OnCustomTimelines()

	def FilterTimeline(self):
		main.window.OnFilterTimeline()

	def Follow(self):
		status = main.window.get_current_status()
		if status:
			misc.follow(get_app().currentAccount, status)

	def Unfollow(self):
		status = main.window.get_current_status()
		if status:
			misc.unfollow(get_app().currentAccount, status)

	def PinToggle(self):
		status = main.window.get_current_status()
		if status:
			misc.pin_toggle(get_app().currentAccount, status)

inv=invisible_interface()