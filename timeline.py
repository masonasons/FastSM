from mastodon import MastodonError
import time
import speak
import sound
import threading
import os
from GUI import main


class TimelineSettings(object):
	def __init__(self, account, tl):
		self.account_id = account
		self.tl = tl
		self.mute = False
		self.read = False
		self.hide = False


class timeline(object):
	def __init__(self, account, name, type, data=None, user=None, status=None, silent=False):
		self.members = []
		self.account = account
		self.app = account.app
		self.status = status
		self.name = name
		self.removable = False
		self.initial = True
		self.statuses = []
		self.type = type
		self.data = data
		self.user = user
		self.index = 0
		self.page = 0
		self.mute = False
		self.read = False
		self.hide = False
		self._loading = False  # Flag to prevent concurrent load operations
		self._stop_loading_all = False  # Flag to stop load_all_previous
		self._loading_all_active = False  # Flag to track if load_all_previous is running

		for i in self.app.timeline_settings:
			if i.account_id == self.account.me.id and i.tl == self.name:
				self.mute = i.mute
				self.read = i.read
				self.hide = i.hide

		if self.type == "user" and self.name != "Sent" or self.type == "conversation" or self.type == "search" or self.type == "list":
			if not silent:
				sound.play(self.account, "open")
			self.removable = True

		# Set up the API function and kwargs based on timeline type
		# Use maximum limit (100) for Bluesky, otherwise use user preference
		if getattr(self.account.prefs, 'platform_type', '') == 'bluesky':
			fetch_limit = 100  # Bluesky max
		else:
			fetch_limit = self.app.prefs.count
		self.update_kwargs = {"limit": fetch_limit}
		self.prev_kwargs = {"limit": fetch_limit}

		# Use platform backend methods where available
		if self.type == "home":
			if hasattr(self.account, '_platform') and self.account._platform:
				self.func = self.account._platform.get_home_timeline
			else:
				self.func = self.account.api.timeline_home
		elif self.type == "mentions":
			# Use platform backend - returns statuses extracted from notifications
			self.func = self.account.get_mentions
		elif self.type == "notifications":
			if hasattr(self.account, '_platform') and self.account._platform:
				self.func = self.account._platform.get_notifications
			else:
				self.func = self.account.api.notifications
		elif self.type == "conversations":
			# Check if platform supports DMs
			if hasattr(self.account, 'supports_feature') and not self.account.supports_feature('direct_messages'):
				# Platform doesn't support DMs - hide this timeline
				self.hide = True
				self.func = lambda **kwargs: []
			else:
				self.func = self.account.api.conversations
		elif self.type == "favourites":
			if hasattr(self.account, '_platform') and self.account._platform:
				self.func = self.account._platform.get_favourites
			else:
				self.func = self.account.api.favourites
			self.removable = True
		elif self.type == "bookmarks":
			if hasattr(self.account, '_platform') and self.account._platform:
				self.func = self.account._platform.get_bookmarks
			else:
				self.func = self.account.api.bookmarks
			self.removable = True
		elif self.type == "user":
			if hasattr(self.account, '_platform') and self.account._platform:
				user_id = self.user.id if self.user else self.data
				self.func = lambda **kwargs: self.account._platform.get_user_statuses(user_id, **kwargs)
			else:
				self.func = lambda **kwargs: self.account.api.account_statuses(id=self.user.id if self.user else self.data, **kwargs)
		elif self.type == "list":
			# Check if platform supports lists
			if hasattr(self.account, 'supports_feature') and not self.account.supports_feature('lists'):
				self.hide = True
				self.func = lambda **kwargs: []
			elif hasattr(self.account, '_platform') and self.account._platform:
				self.func = lambda **kwargs: self.account._platform.get_list_timeline(self.data, **kwargs)
			else:
				self.func = lambda **kwargs: self.account.api.timeline_list(id=self.data, **kwargs)
		elif self.type == "search":
			self.func = lambda **kwargs: self._search_statuses(**kwargs)
		elif self.type == "feed":
			# Bluesky custom feed
			if hasattr(self.account, '_platform') and self.account._platform:
				self.func = lambda **kwargs: self.account._platform.get_feed_timeline(self.data, **kwargs)
			else:
				self.func = lambda **kwargs: []
			self.removable = True
		elif self.type == "local":
			# Mastodon local timeline
			if hasattr(self.account, '_platform') and self.account._platform:
				self.func = self.account._platform.get_local_timeline
			else:
				self.func = self.account.api.timeline_local
			self.removable = True
		elif self.type == "federated":
			# Mastodon federated/public timeline
			if hasattr(self.account, '_platform') and self.account._platform:
				self.func = self.account._platform.get_public_timeline
			else:
				self.func = self.account.api.timeline_public
			self.removable = True
		elif self.type == "instance":
			# Remote instance local timeline
			if hasattr(self.account, '_platform') and self.account._platform:
				self.func = lambda **kwargs: self.account._platform.get_instance_timeline(self.data, **kwargs)
			else:
				self.func = lambda **kwargs: []
			self.removable = True
			if not silent:
				sound.play(self.account, "open")
		elif self.type == "remote_user":
			# Remote user timeline from another instance
			if hasattr(self.account, '_platform') and self.account._platform:
				# Store in instance variables to avoid closure issues
				self._remote_url = self.data.get('url', '') if isinstance(self.data, dict) else ''
				self._remote_username = self.data.get('username', '') if isinstance(self.data, dict) else ''
				self.func = self._load_remote_user
			else:
				self.func = lambda **kwargs: []
			self.removable = True
			if not silent:
				sound.play(self.account, "open")

		if self.type != "conversation":
			threading.Thread(target=self.load, daemon=True).start()
		else:
			self.load_conversation()

		if self.type == "conversations" and not self.hide:
			# Only load message cache if platform supports DMs
			m = self.app.load_messages(self.account)
			if m is not None:
				self.statuses = m
				self.initial = False

	def _load_remote_user(self, **kwargs):
		"""Helper to load remote user timeline"""
		if hasattr(self.account, '_platform') and self.account._platform:
			return self.account._platform.get_remote_user_timeline(self._remote_url, self._remote_username, **kwargs)
		return []

	def _search_statuses(self, **kwargs):
		"""Helper to search and return only statuses"""
		# Use platform backend if available
		if hasattr(self.account, '_platform') and self.account._platform:
			return self.account._platform.search_statuses(self.data, **kwargs)
		# Fallback to Mastodon API
		result = self.account.api.search_v2(q=self.data, result_type='statuses', **kwargs)
		if hasattr(result, 'statuses'):
			return result.statuses
		return result.get('statuses', [])

	def read_items(self, items):
		pref = ""
		if len(self.app.accounts) > 1:
			pref = self.account.me.acct + ": "
		if len(items) >= 4:
			speak.speak(pref + str(len(items)) + " new in " + self.name)
			return
		speak.speak(pref + ", ".join(self.prepare(items)))

	def load_conversation(self):
		status = self.status
		self.process_status(status)
		if self.app.prefs.reversed:
			self.statuses.reverse()
		if self.account.currentTimeline == self:
			main.window.refreshList()
		sound.play(self.account, "search")
		# Notify initial load complete
		if self.initial:
			self.initial = False
			if hasattr(self.account, '_on_timeline_initial_load_complete'):
				self.account._on_timeline_initial_load_complete()

	def play(self):
		if self.type == "user":
			if not os.path.exists("sounds/" + self.account.prefs.soundpack + "/" + self.user.acct + ".ogg"):
				sound.play(self.account, "user")
			else:
				sound.play(self.account, self.user.acct)
		else:
			if self.type == "search":
				sound.play(self.account, "search")
			elif self.type == "list":
				sound.play(self.account, "list")
			else:
				sound.play(self.account, self.name)

	def process_status(self, status):
		self.statuses.append(status)
		try:
			if hasattr(status, "in_reply_to_id") and status.in_reply_to_id is not None:
				# Check if this is a remote status
				if hasattr(status, '_instance_url') and status._instance_url:
					parent = self._lookup_remote_status(status._instance_url, status.in_reply_to_id)
				else:
					parent = self.app.lookup_status(self.account, status.in_reply_to_id)
				if parent:
					self.process_status(parent)
			if hasattr(status, "reblog") and status.reblog:
				self.process_status(status.reblog)
			if hasattr(status, "quote") and status.quote:
				self.process_status(status.quote)
		except:
			pass

	def _lookup_remote_status(self, instance_url, status_id):
		"""Look up a status from a remote instance."""
		if not hasattr(self.account, '_platform') or not self.account._platform:
			return None
		try:
			remote_api = self.account._platform.get_or_create_remote_api(instance_url)
			status = remote_api.status(id=status_id)
			if status:
				from platforms.mastodon.models import mastodon_status_to_universal
				from urllib.parse import urlparse
				uni_status = mastodon_status_to_universal(status)
				if uni_status:
					# Mark as remote
					uni_status._instance_url = instance_url
					parsed = urlparse(instance_url)
					instance_domain = parsed.netloc or parsed.path.strip('/')
					if hasattr(uni_status, 'account') and uni_status.account:
						if '@' not in uni_status.account.acct:
							uni_status.account.acct = f"{uni_status.account.acct}@{instance_domain}"
						uni_status.account._instance_url = instance_url
				return uni_status
		except:
			pass
		return None

	def hide_tl(self):
		if self.type == "user" and self.name != "Sent" or self.type == "list" or self.type == "search" or self.type == "conversation" or self.type == "instance" or self.type == "remote_user" or self.type == "favourites" or self.type == "bookmarks":
			self.app.alert("You can't hide this timeline. Try closing it instead.", "Error")
			return
		self.hide = True
		self.app.get_timeline_settings(self.account.me.id, self.name).hide = self.hide
		self.app.save_timeline_settings()
		if self.account.currentTimeline == self:
			self.account.currentTimeline = self.account.timelines[0]
			main.window.refreshTimelines()

	def unhide_tl(self):
		self.hide = False
		self.app.get_timeline_settings(self.account.me.id, self.name).hide = self.hide
		self.app.save_timeline_settings()
		main.window.refreshTimelines()

	def _fetch_multiple_pages(self, kwargs, num_pages):
		"""Fetch multiple pages of results and combine them."""
		all_results = []
		current_kwargs = kwargs.copy()
		requested_limit = kwargs.get('limit', 40)

		for page in range(num_pages):
			try:
				page_results = self.func(**current_kwargs)
				if not page_results:
					break  # No more results

				all_results.extend(page_results)

				# Check if we got fewer results than requested - means no more pages
				if len(page_results) < requested_limit:
					break  # Reached the end, no more pages available

				# For Bluesky, the cursor is handled internally by the platform backend
				# For Mastodon, we need to pass max_id of last item
				last_item = page_results[-1]
				if hasattr(last_item, 'id'):
					current_kwargs['max_id'] = last_item.id
				else:
					break  # Can't paginate without ID

			except Exception as e:
				# On error, return what we have so far
				if page == 0:
					raise  # Re-raise if first page fails
				break

		return all_results

	def load(self, back=False, speech=False, items=[]):
		if self.hide:
			# Still notify if this was an initial load that got skipped
			if self.initial:
				self.initial = False
				if hasattr(self.account, '_on_timeline_initial_load_complete'):
					self.account._on_timeline_initial_load_complete()
			return False
		# Prevent concurrent load operations (but allow streaming items to pass through)
		if items == [] and self._loading:
			return False
		if items == []:
			self._loading = True
		try:
			return self._do_load(back, speech, items)
		finally:
			if items == []:
				self._loading = False

	def load_all_previous(self):
		"""Load all previous posts in a loop until the timeline is fully loaded or an error occurs."""
		self._stop_loading_all = False
		self._loading_all_active = True
		total_loaded = 0

		speak.speak("Loading all previous posts...")

		while not self._stop_loading_all:
			# Get current count before loading
			count_before = len(self.statuses)

			# Try to load previous
			try:
				result = self.load(back=True, speech=False)
			except Exception as e:
				speak.speak(f"Stopped loading: {e}")
				break

			# Check if we got any new items
			count_after = len(self.statuses)
			new_items = count_after - count_before

			if new_items == 0:
				# No more items to load - timeline fully loaded
				speak.speak(f"Timeline fully loaded. {total_loaded} posts loaded in total.")
				break

			total_loaded += new_items

			# Small delay to avoid hammering the API
			import time
			time.sleep(0.5)

		if self._stop_loading_all:
			speak.speak(f"Loading stopped. {total_loaded} posts loaded.")

		self._loading_all_active = False

	def stop_loading_all(self):
		"""Stop the load_all_previous operation."""
		self._stop_loading_all = True

	def _do_load(self, back=False, speech=False, items=[]):
		if items == []:
			if back:
				if not self.app.prefs.reversed:
					self.prev_kwargs['max_id'] = self.statuses[len(self.statuses)-1].id
				else:
					self.prev_kwargs['max_id'] = self.statuses[0].id
			tl = None
			try:
				# Determine how many pages to fetch
				fetch_pages = getattr(self.app.prefs, 'fetch_pages', 1)
				if fetch_pages < 1:
					fetch_pages = 1

				if not back:
					if fetch_pages > 1 and self.initial:
						# Multi-page fetch for initial load
						tl = self._fetch_multiple_pages(self.update_kwargs, fetch_pages)
					else:
						tl = self.func(**self.update_kwargs)
				else:
					if fetch_pages > 1:
						# Multi-page fetch for load previous
						tl = self._fetch_multiple_pages(self.prev_kwargs, fetch_pages)
					else:
						tl = self.func(**self.prev_kwargs)
			except MastodonError as error:
				self.app.handle_error(error, self.account.me.acct + "'s " + self.name)
				# Still notify initial load complete even on error
				if self.initial:
					self.initial = False
					if hasattr(self.account, '_on_timeline_initial_load_complete'):
						self.account._on_timeline_initial_load_complete()
				if self.removable:
					if self.type == "user" and self.data in self.account.prefs.user_timelines:
						self.account.prefs.user_timelines.remove(self.data)
					if self.type == "list":
						self.account.prefs.list_timelines = [
							item for item in self.account.prefs.list_timelines
							if item.get('id') != self.data
						]
					if self.type == "search" and self.data in self.account.prefs.search_timelines:
						self.account.prefs.search_timelines.remove(self.data)
					if self.type == "instance":
						self.account.prefs.instance_timelines = [
							item for item in self.account.prefs.instance_timelines
							if item.get('url') != self.data
						]
					if self.type == "remote_user":
						inst_url = self.data.get('url', '') if isinstance(self.data, dict) else ''
						username = self.data.get('username', '') if isinstance(self.data, dict) else ''
						self.account.prefs.remote_user_timelines = [
							item for item in self.account.prefs.remote_user_timelines
							if not (item.get('url') == inst_url and item.get('username') == username)
						]
					self.account.timelines.remove(self)
					if self.account == self.app.currentAccount:
						main.window.refreshTimelines()
						if self.account.currentTimeline == self:
							main.window.list.SetSelection(0)
							self.account.currentIndex = 0
							main.window.on_list_change(None)
				return
		else:
			tl = items
		if tl is not None:
			newitems = 0
			objs = []
			objs2 = []
			for i in tl:
				# Handle notifications and conversations differently
				# Use per-account user cache
				if self.type == "notifications":
					self.account.user_cache.add_users_from_notification(i)
				elif self.type == "mentions":
					# Mentions now come as statuses from platform backend
					self.account.user_cache.add_users_from_status(i)
				elif self.type == "conversations":
					pass  # Conversations have different structure
				else:
					self.account.user_cache.add_users_from_status(i)

				if not self.app.isDuplicate(i, self.statuses):
					newitems += 1
					if self.initial or back:
						if not self.app.prefs.reversed:
							self.statuses.append(i)
							objs2.append(i)
						else:
							self.statuses.insert(0, i)
							objs2.insert(0, i)
					else:
						if not self.app.prefs.reversed:
							objs.append(i)
							objs2.append(i)
						else:
							objs.insert(0, i)
							objs2.insert(0, i)

			if newitems == 0 and speech:
				speak.speak("Nothing new.")
			if newitems > 0:
				if self.read:
					self.read_items(objs2)
				if len(objs) > 0:
					if not self.app.prefs.reversed:
						objs.reverse()
						objs2.reverse()
					for i in objs:
						if not self.app.prefs.reversed:
							self.statuses.insert(0, i)
						else:
							self.statuses.append(i)

				if self.app.currentAccount == self.account and self.account.currentTimeline == self:
					if not back and not self.initial:
						if not self.app.prefs.reversed:
							main.window.add_to_list(self.prepare(objs2))
						else:
							objs2.reverse()
							main.window.append_to_list(self.prepare(objs2))
					else:
						if not self.app.prefs.reversed:
							main.window.append_to_list(self.prepare(objs2))
						else:
							main.window.add_to_list(self.prepare(objs2))

				if items == []:
					if not self.app.prefs.reversed:
						self.update_kwargs['since_id'] = tl[0].id
					else:
						self.update_kwargs['since_id'] = tl[len(tl)-1].id

				if not back and not self.initial:
					if not self.app.prefs.reversed:
						self.index += newitems
						if self.app.currentAccount == self.account and self.account.currentTimeline == self and len(self.statuses) > 0:
							try:
								main.window.list2.SetSelection(self.index)
							except:
								pass
				if back and self.app.prefs.reversed:
					self.index += newitems
					if self.app.currentAccount == self.account and self.account.currentTimeline == self and len(self.statuses) > 0:
						main.window.list2.SetSelection(self.index)

				if self.initial:
					if not self.app.prefs.reversed:
						self.index = 0
					else:
						self.index = len(self.statuses) - 1
				if not self.mute and not self.hide:
					self.play()
				self.app.prefs.statuses_received += newitems
				if speech:
					announcement = f"{newitems} new item"
					if newitems != 1:
						announcement += "s"
					speak.speak(announcement)
			if self.initial:
				self.initial = False
				# Notify account that this timeline's initial load is complete
				if hasattr(self.account, '_on_timeline_initial_load_complete'):
					self.account._on_timeline_initial_load_complete()
		if self.type == "conversations":
			self.app.save_messages(self.account, self.statuses)
		if self == self.account.timelines[len(self.account.timelines) - 1] and not self.account.ready:
			self.account.ready = True
			sound.play(self.account, "ready")

	def toggle_read(self):
		if self.read:
			self.read = False
			speak.speak("Autoread off")
		else:
			self.read = True
			speak.speak("Autoread on")
		self.app.get_timeline_settings(self.account.me.id, self.name).read = self.read
		self.app.save_timeline_settings()

	def toggle_mute(self):
		if self.mute:
			self.mute = False
			speak.speak("Unmuted")
		else:
			self.mute = True
			speak.speak("Muted")
		self.app.get_timeline_settings(self.account.me.id, self.name).mute = self.mute
		self.app.save_timeline_settings()

	def get(self):
		items = []
		for i in self.statuses:
			if self.type == "notifications":
				items.append(self.app.process_notification(i))
			elif self.type == "conversations":
				items.append(self.app.process_conversation(i))
			else:
				# mentions now treated same as home/user/etc.
				items.append(self.app.process_status(i))
		return items

	def prepare(self, items):
		items2 = []
		for i in items:
			if self.type == "notifications":
				processed = self.app.process_notification(i)
			elif self.type == "conversations":
				processed = self.app.process_conversation(i)
			else:
				# mentions now treated same as home/user/etc.
				processed = self.app.process_status(i)

			if not self.app.prefs.reversed:
				items2.append(processed)
			else:
				items2.insert(0, processed)
		return items2


def add(account, name, type, data=None, user=None):
	account.timelines.append(timeline(account, name, type, data, user))
	if account == account.app.currentAccount:
		main.window.refreshTimelines()


def timelineThread(account):
	app = account.app
	while 1:
		time.sleep(app.prefs.update_time * 60)
		for i in account.timelines:
			try:
				if i.type == "list":
					try:
						members = account.api.list_accounts(id=i.data)
						i.members = []
						for i2 in members:
							i.members.append(i2.id)
					except:
						pass
				if i.type != "conversation":
					i.load()
			except MastodonError as error:
				sound.play(account, "error")
				speak.speak(str(error))
		if app.prefs.streaming and (account.stream is not None and not account.stream_thread.is_alive() or account.stream is None):
			account.start_stream()

		# Resolve unknown users using per-account cache
		if len(account.user_cache.unknown_users) > 0:
			try:
				from platforms.mastodon.models import mastodon_user_to_universal
				new_users = account.api.accounts(ids=account.user_cache.unknown_users)
				for i in new_users:
					universal_user = mastodon_user_to_universal(i)
					if universal_user:
						account.user_cache.add_user(universal_user)
				account.user_cache.unknown_users = []
			except:
				account.user_cache.unknown_users = []

		# Save per-account user cache
		account.user_cache.save()


def reverse(app):
	for i in app.accounts:
		for i2 in i.timelines:
			i2.statuses.reverse()
			i2.index = (len(i2.statuses) - 1) - i2.index
	main.window.on_list_change(None)
