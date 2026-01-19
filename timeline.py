from mastodon import MastodonError
import time
import speak
import sound
import threading
import os
import wx
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
		# Timeline position sync (for home timeline with Mastodon)
		self._position_moved = False  # Track if user navigated since last load
		self._last_synced_id = None  # Last position synced with server

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
			# Extract username and filter from data (data can be string or dict with username/filter)
			if isinstance(self.data, dict):
				username = self.data.get('username')
				user_filter = self.data.get('filter')
			else:
				username = self.data
				user_filter = None

			# If we don't have a user object, look it up by username
			if not self.user and username:
				looked_up = self.account.app.lookup_user_name(self.account, username)
				if looked_up and looked_up != -1:
					self.user = looked_up

			# Now get the user_id - prefer user object, fall back to username (may fail)
			user_id = self.user.id if self.user else username

			if hasattr(self.account, '_platform') and self.account._platform:
				# Use default args to capture values at definition time
				if user_filter:
					self.func = lambda uid=user_id, uf=user_filter, **kwargs: self.account._platform.get_user_statuses(uid, filter=uf, **kwargs)
				else:
					self.func = lambda uid=user_id, **kwargs: self.account._platform.get_user_statuses(uid, **kwargs)
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
			# Fetch list members for streaming (in background to not block startup)
			def fetch_members():
				try:
					members = self.account.api.list_accounts(id=self.data)
					self.members = [m.id for m in members]
				except:
					pass
			threading.Thread(target=fetch_members, daemon=True).start()
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
				self._remote_filter = self.data.get('filter') if isinstance(self.data, dict) else None
				self.func = self._load_remote_user
			else:
				self.func = lambda **kwargs: []
			self.removable = True
			if not silent:
				sound.play(self.account, "open")
		elif self.type == "pinned":
			# User's pinned posts
			if hasattr(self.account, '_platform') and self.account._platform:
				self.func = lambda **kwargs: self.account._platform.get_pinned_statuses(**kwargs)
			else:
				self.func = lambda **kwargs: self.account.api.account_statuses(id=self.account.me.id, pinned=True, **kwargs)
			self.removable = True
		elif self.type == "scheduled":
			# User's scheduled posts
			if hasattr(self.account, '_platform') and self.account._platform:
				self.func = lambda **kwargs: self.account._platform.get_scheduled_statuses(**kwargs)
			else:
				self.func = lambda **kwargs: self.account.api.scheduled_statuses(**kwargs)
			self.removable = True
		elif self.type == "quotes":
			# Quotes of a specific status (Mastodon 4.5+)
			status_id = self.data
			self.func = lambda sid=status_id, **kwargs: self.account.api._Mastodon__api_request('GET', f'/api/v1/statuses/{sid}/quotes')
			self.removable = True

		# Load saved filter settings if any
		from GUI.timeline_filter import get_saved_filter
		saved_filter = get_saved_filter(self.account, self)
		if saved_filter:
			self._filter_settings = saved_filter
			self._unfiltered_statuses = []
			self._is_filtered = True

		if self.type != "conversation":
			threading.Thread(target=self.load, daemon=True).start()
		else:
			self.load_conversation()

	def _load_remote_user(self, **kwargs):
		"""Helper to load remote user timeline"""
		if hasattr(self.account, '_platform') and self.account._platform:
			if self._remote_filter:
				return self.account._platform.get_remote_user_timeline(self._remote_url, self._remote_username, filter=self._remote_filter, **kwargs)
			return self.account._platform.get_remote_user_timeline(self._remote_url, self._remote_username, **kwargs)
		return []

	def _search_statuses(self, **kwargs):
		"""Helper to search and return only statuses"""
		# Extract only valid search parameters (avoid passing unsupported kwargs)
		limit = kwargs.get('limit', 40)
		max_id = kwargs.get('max_id')

		# Use platform backend if available
		if hasattr(self.account, '_platform') and self.account._platform:
			# Only pass max_id if it's actually set (not None)
			if max_id:
				return self.account._platform.search_statuses(self.data, limit=limit, max_id=max_id)
			return self.account._platform.search_statuses(self.data, limit=limit)

		# Fallback to Mastodon API - handle versions that don't support limit
		search_kwargs = {'q': self.data, 'result_type': 'statuses'}
		if max_id:
			search_kwargs['max_id'] = max_id
		try:
			# Try with limit first (Mastodon.py 2.8.0+)
			result = self.account.api.search_v2(limit=limit, **search_kwargs)
		except TypeError:
			# Fall back without limit for older Mastodon.py versions
			result = self.account.api.search_v2(**search_kwargs)
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

	def _add_status_with_filter(self, status, to_front=False):
		"""Add a status to the timeline, respecting any active filter.

		Args:
			status: The status to add
			to_front: If True, insert at front of list; if False, append to end

		Returns:
			True if the status was added to the visible list, False if filtered out
		"""
		from GUI.timeline_filter import should_show_status

		# Always add to unfiltered list if it exists
		if hasattr(self, '_unfiltered_statuses'):
			if to_front:
				self._unfiltered_statuses.insert(0, status)
			else:
				self._unfiltered_statuses.append(status)

		# Check if we should show this status based on filter
		if hasattr(self, '_filter_settings') and self._filter_settings:
			if not should_show_status(status, self._filter_settings, self.app):
				return False

		# Add to visible statuses
		if to_front:
			self.statuses.insert(0, status)
		else:
			self.statuses.append(status)
		return True

	def load_conversation(self):
		status = self.status

		# For boosted posts, use the reblogged status for conversation context
		# This ensures we get replies to the original post, not the boost wrapper
		actual_status = status
		if hasattr(status, 'reblog') and status.reblog:
			actual_status = status.reblog

		# Get the actual status ID (for mentions, id is notification_id, real id is in _original_status_id)
		status_id = getattr(actual_status, '_original_status_id', None) or actual_status.id

		# Try to use get_status_context for full thread (works better for Bluesky)
		if hasattr(self.account, '_platform') and self.account._platform:
			try:
				context = self.account._platform.get_status_context(status_id)
				ancestors = context.get('ancestors', [])
				descendants = context.get('descendants', [])

				# Build thread: ancestors -> current status -> descendants
				for ancestor in ancestors:
					self.statuses.append(ancestor)
				self.statuses.append(actual_status)
				for descendant in descendants:
					self.statuses.append(descendant)
			except Exception:
				# Fall back to recursive method
				self.process_status(actual_status)
		else:
			# Fall back to recursive method for Mastodon API
			self.process_status(actual_status)

		# Conversation threads should always be in chronological order (oldest first)
		# regardless of the global reversed setting, since they represent a chat-like thread
		if self.account.currentTimeline == self:
			wx.CallAfter(main.window.refreshList)
		sound.play(self.account, "search")
		# Notify initial load complete
		if self.initial:
			self.initial = False
			if hasattr(self.account, '_on_timeline_initial_load_complete'):
				self.account._on_timeline_initial_load_complete()

	def play(self, items=None):
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
			elif self.type == "notifications":
				# Check if any of the items are mentions (when mentions are hidden)
				if items:
					has_mention = False
					has_direct_mention = False
					# Check if mentions timeline is hidden
					mentions_hidden = False
					for tl in self.account.timelines:
						if tl.type == "mentions" and tl.hide:
							mentions_hidden = True
							break

					if mentions_hidden:
						for item in items:
							# Check if this is a mention notification
							notif_type = getattr(item, 'type', None)
							if notif_type == 'mention':
								has_mention = True
								# Check if it's a direct message
								status = getattr(item, 'status', None)
								if status:
									visibility = getattr(status, 'visibility', None)
									if visibility == 'direct':
										has_direct_mention = True
										break

					if has_direct_mention:
						sound.play(self.account, "messages")
						return
					elif has_mention:
						sound.play(self.account, "mentions")
						return

				sound.play(self.account, "notification")
			elif self.type == "mentions":
				# Check if any items are direct messages
				if items:
					for item in items:
						visibility = getattr(item, 'visibility', None)
						if visibility == 'direct':
							sound.play(self.account, "messages")
							return
				sound.play(self.account, self.name)
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
			self.account.currentTimeline = self.account.get_first_timeline()
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
		total_shown = 0

		speak.speak("Loading all previous posts...")

		while not self._stop_loading_all:
			# Get current count before loading - use unfiltered list if filter applied
			status_list = getattr(self, '_unfiltered_statuses', None) or self.statuses
			count_before = len(status_list)
			shown_before = len(self.statuses)

			# Try to load previous
			try:
				result = self.load(back=True, speech=False)
			except Exception as e:
				speak.speak(f"Stopped loading: {e}")
				break

			# Check if we got any new items (from unfiltered list)
			status_list = getattr(self, '_unfiltered_statuses', None) or self.statuses
			count_after = len(status_list)
			new_items = count_after - count_before

			# Also track shown items
			shown_after = len(self.statuses)
			new_shown = shown_after - shown_before

			if new_items == 0:
				# No more items to load - timeline fully loaded
				if hasattr(self, '_filter_settings') and self._filter_settings:
					speak.speak(f"Timeline fully loaded. {total_loaded} posts loaded, {total_shown} shown.")
				else:
					speak.speak(f"Timeline fully loaded. {total_loaded} posts loaded in total.")
				break

			total_loaded += new_items
			total_shown += new_shown

			# Small delay to avoid hammering the API
			import time
			time.sleep(0.5)

		if self._stop_loading_all:
			if hasattr(self, '_filter_settings') and self._filter_settings:
				speak.speak(f"Loading stopped. {total_loaded} posts loaded, {total_shown} shown.")
			else:
				speak.speak(f"Loading stopped. {total_loaded} posts loaded.")

		self._loading_all_active = False

	def stop_loading_all(self):
		"""Stop the load_all_previous operation."""
		self._stop_loading_all = True

	def _do_load(self, back=False, speech=False, items=[]):
		if items == []:
			if back:
				# Use unfiltered statuses for pagination if filter is applied
				status_list = getattr(self, '_unfiltered_statuses', None) or self.statuses
				if not self.app.prefs.reversed:
					self.prev_kwargs['max_id'] = status_list[len(status_list)-1].id
				else:
					self.prev_kwargs['max_id'] = status_list[0].id
			tl = None
			try:
				# Determine how many pages to fetch
				fetch_pages = getattr(self.app.prefs, 'fetch_pages', 1)
				if fetch_pages < 1:
					fetch_pages = 1

				# Check if we should use single API call on startup
				single_on_startup = getattr(self.app.prefs, 'single_api_on_startup', False)

				if not back:
					if fetch_pages > 1 and self.initial and not single_on_startup:
						# Multi-page fetch for initial load (unless single_api_on_startup is enabled)
						tl = self._fetch_multiple_pages(self.update_kwargs, fetch_pages)
					else:
						tl = self.func(**self.update_kwargs)
				else:
					if fetch_pages > 1:
						# Multi-page fetch for load previous
						tl = self._fetch_multiple_pages(self.prev_kwargs, fetch_pages)
					else:
						tl = self.func(**self.prev_kwargs)
			except Exception as error:
				self.app.handle_error(error, self.account.me.acct + "'s " + self.name)
				# Still notify initial load complete even on error
				if self.initial:
					self.initial = False
					if hasattr(self.account, '_on_timeline_initial_load_complete'):
						self.account._on_timeline_initial_load_complete()
				if self.removable:
					if self.type == "user":
						# Handle both string and dict data for user timelines
						if isinstance(self.data, dict):
							self.account.prefs.user_timelines = [
								ut for ut in self.account.prefs.user_timelines
								if not (isinstance(ut, dict) and ut.get('username') == self.data.get('username') and ut.get('filter') == self.data.get('filter'))
							]
						elif self.data in self.account.prefs.user_timelines:
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
						tl_filter = self.data.get('filter') if isinstance(self.data, dict) else None
						self.account.prefs.remote_user_timelines = [
							item for item in self.account.prefs.remote_user_timelines
							if not (item.get('url') == inst_url and item.get('username') == username and item.get('filter') == tl_filter)
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

				# Check for duplicates in both visible and unfiltered statuses
				all_statuses = self.statuses
				if hasattr(self, '_unfiltered_statuses'):
					all_statuses = self._unfiltered_statuses
				if not self.app.isDuplicate(i, all_statuses):
					newitems += 1
					# Use filter-aware method to add status
					to_front = self.app.prefs.reversed if (self.initial or back) else not self.app.prefs.reversed
					if self.initial or back:
						shown = self._add_status_with_filter(i, to_front=self.app.prefs.reversed)
						if shown:
							if not self.app.prefs.reversed:
								objs2.append(i)
							else:
								objs2.insert(0, i)
					else:
						# For new items, collect first, then add
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
					# Filter objs2 to only include items that pass the filter
					filtered_objs2 = []
					for i in objs:
						shown = self._add_status_with_filter(i, to_front=not self.app.prefs.reversed)
						if shown:
							filtered_objs2.append(i)
					objs2 = filtered_objs2

				if self.app.currentAccount == self.account and self.account.currentTimeline == self:
					if not back and not self.initial:
						if not self.app.prefs.reversed:
							wx.CallAfter(main.window.add_to_list, self.prepare(objs2))
						else:
							objs2.reverse()
							wx.CallAfter(main.window.append_to_list, self.prepare(objs2))
					else:
						if not self.app.prefs.reversed:
							wx.CallAfter(main.window.append_to_list, self.prepare(objs2))
						else:
							wx.CallAfter(main.window.add_to_list, self.prepare(objs2))

				if items == []:
					if not self.app.prefs.reversed:
						self.update_kwargs['since_id'] = tl[0].id
					else:
						self.update_kwargs['since_id'] = tl[len(tl)-1].id

				if not back and not self.initial:
					if not self.app.prefs.reversed:
						# Use filtered count (len(objs2)) for index adjustment, not total newitems
						self.index += len(objs2)
						if self.app.currentAccount == self.account and self.account.currentTimeline == self and len(self.statuses) > 0:
							try:
								wx.CallAfter(main.window.list2.SetSelection, self.index)
							except:
								pass
				if back and self.app.prefs.reversed:
					# Use filtered count (len(objs2)) for index adjustment, not total newitems
					self.index += len(objs2)
					if self.app.currentAccount == self.account and self.account.currentTimeline == self and len(self.statuses) > 0:
						wx.CallAfter(main.window.list2.SetSelection, self.index)

				if self.initial:
					if not self.app.prefs.reversed:
						self.index = 0
					else:
						self.index = len(self.statuses) - 1
				if not self.mute and not self.hide:
					self.play(tl)
				self.app.prefs.statuses_received += newitems
				if speech:
					# Count how many passed the filter
					filtered_count = len(objs2)
					if hasattr(self, '_filter_settings') and self._filter_settings:
						# Filter is applied - show both counts
						announcement = f"{newitems} new item"
						if newitems != 1:
							announcement += "s"
						announcement += f", {filtered_count} shown"
					else:
						announcement = f"{newitems} new item"
						if newitems != 1:
							announcement += "s"
					speak.speak(announcement)
			if self.initial:
				self.initial = False
				# Sync position from server after initial load (if enabled)
				# Only sync if user hasn't already moved (position_moved is False on initial load)
				if not self._position_moved:
					synced = self.sync_position_from_server()
					if synced and self.app.currentAccount == self.account and self.account.currentTimeline == self:
						# Update UI to reflect synced position
						wx.CallAfter(main.window.list2.SetSelection, self.index)
				# Sync local position for notifications/mentions
				if self.type in ("notifications", "mentions"):
					synced = self.sync_local_position()
					if synced and self.app.currentAccount == self.account and self.account.currentTimeline == self:
						wx.CallAfter(main.window.list2.SetSelection, self.index)
				# Notify account that this timeline's initial load is complete
				if hasattr(self.account, '_on_timeline_initial_load_complete'):
					self.account._on_timeline_initial_load_complete()
			else:
				# On refresh: if user hasn't moved, check if server marker changed
				# This handles the case where another client updated the position
				if not self._position_moved:
					synced = self.sync_position_from_server()
					if synced and self.app.currentAccount == self.account and self.account.currentTimeline == self:
						wx.CallAfter(main.window.list2.SetSelection, self.index)
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
			# Use cached display string if available
			cache_attr = '_display_cache'
			cached = getattr(i, cache_attr, None)
			if cached is not None:
				items.append(cached)
			else:
				if self.type == "notifications":
					display = self.app.process_notification(i)
				elif self.type == "conversations":
					display = self.app.process_conversation(i)
				else:
					display = self.app.process_status(i)
				# Try to cache, but don't fail if object doesn't support it
				try:
					setattr(i, cache_attr, display)
				except (AttributeError, TypeError):
					pass
				items.append(display)
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
			# Cache the display string on the item (if supported)
			try:
				i._display_cache = processed
			except (AttributeError, TypeError):
				pass

			if not self.app.prefs.reversed:
				items2.append(processed)
			else:
				items2.insert(0, processed)
		return items2

	# ============ Position Sync Methods ============

	def mark_position_moved(self):
		"""Mark that the user has manually moved position in this timeline."""
		self._position_moved = True

	def _can_sync_position(self):
		"""Check if position sync is available for this timeline."""
		# Only sync home timeline for now
		if self.type != "home":
			return False
		# Check if sync is enabled
		if not self.app.prefs.sync_timeline_position:
			return False
		# Check if platform supports markers (Mastodon only)
		platform_type = getattr(self.account.prefs, 'platform_type', 'mastodon')
		if platform_type != 'mastodon':
			return False
		# Check if platform backend has marker methods
		if not hasattr(self.account, '_platform') or not self.account._platform:
			return False
		if not hasattr(self.account._platform, 'get_timeline_marker'):
			return False
		return True

	def sync_position_from_server(self):
		"""Fetch position marker from server and set index accordingly.

		Should be called after initial load when sync is enabled.
		Returns True if position was synced, False otherwise.
		"""
		if not self._can_sync_position():
			return False

		try:
			marker_id = self.account._platform.get_timeline_marker('home')
			if not marker_id:
				return False

			# Find the status with this ID
			for i, status in enumerate(self.statuses):
				if str(status.id) == str(marker_id):
					self.index = i
					self._last_synced_id = marker_id
					self._position_moved = False
					return True

			# Marker ID not found in current statuses - might be older
			# Just track it for later sync decisions
			self._last_synced_id = marker_id
			return False

		except Exception:
			return False

	def sync_position_to_server(self):
		"""Push current position to server.

		Should be called when position was moved and we want to sync.
		Returns True if position was synced, False otherwise.
		"""
		if not self._can_sync_position():
			return False

		if not self._position_moved:
			return False  # No change to sync

		if len(self.statuses) == 0:
			return False

		try:
			current_status = self.statuses[self.index]
			current_id = str(current_status.id)

			# Don't sync if it's the same as last synced
			if current_id == self._last_synced_id:
				return False

			success = self.account._platform.set_timeline_marker('home', current_id)
			if success:
				self._last_synced_id = current_id
				self._position_moved = False
				return True
			return False

		except Exception:
			return False

	def sync_local_position(self):
		"""Restore position from locally saved ID for notifications/mentions.

		Should be called after initial load.
		Returns True if position was restored, False otherwise.
		"""
		if self.type not in ("notifications", "mentions"):
			return False

		if len(self.statuses) == 0:
			return False

		try:
			# Get saved ID from account prefs
			if self.type == "notifications":
				saved_id = getattr(self.account.prefs, 'last_notifications_id', None)
			else:  # mentions
				saved_id = getattr(self.account.prefs, 'last_mentions_id', None)

			if not saved_id:
				return False

			# Find the status with this ID
			for i, status in enumerate(self.statuses):
				if str(status.id) == str(saved_id):
					self.index = i
					return True

			# ID not found in current statuses
			return False

		except Exception:
			return False


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

		# Sync timeline positions to server if changed
		if app.prefs.sync_timeline_position:
			for i in account.timelines:
				try:
					i.sync_position_to_server()
				except:
					pass

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
