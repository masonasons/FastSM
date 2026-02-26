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
		# Set of status IDs for O(1) duplicate checking
		self._status_ids = set()
		# Lock for thread-safe duplicate checking and status addition
		self._status_lock = threading.RLock()
		# Gap tracking for cache - when API refresh doesn't fully connect to cached items
		# List of gaps, each gap is a dict with 'max_id' (where to load from)
		self._gaps = []
		self._last_load_time = None  # Timestamp of last successful load (for gap detection)
		self._gap_idle_threshold = 600  # Seconds of idle time before gap detection triggers (10 minutes)
		# Per-timeline streaming support
		self._stream_thread = None
		self._stream_started = False
		self._stream_lock = threading.Lock()

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
			# Check if we should load from cache first
			if self._should_use_cache() and self._load_from_cache():
				# Cache loaded successfully - spawn background refresh thread
				threading.Thread(target=self._refresh_after_cache, daemon=True).start()
			else:
				# No cache or cache disabled - normal load
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

	@property
	def supports_streaming(self):
		"""Check if this timeline type supports streaming."""
		# Only Mastodon supports streaming
		if getattr(self.account.prefs, 'platform_type', '') == 'bluesky':
			return False
		# Streamable timeline types
		# Note: instance (remote) timelines can't stream - most instances require auth
		if self.type in ('list', 'local', 'federated'):
			return True
		# Search timelines with hashtag queries can stream
		if self.type == 'search' and self.data and str(self.data).startswith('#'):
			return True
		return False

	@property
	def stream_endpoint(self):
		"""Get the streaming endpoint URL for this timeline."""
		if not self.supports_streaming:
			return None
		base_url = self.account.prefs.instance_url
		if self.type == 'list':
			return f"{base_url}/api/v1/streaming/list?list={self.data}"
		elif self.type == 'local':
			return f"{base_url}/api/v1/streaming/public/local"
		elif self.type == 'federated':
			return f"{base_url}/api/v1/streaming/public"
		elif self.type == 'search' and self.data and str(self.data).startswith('#'):
			# Hashtag search - stream the hashtag
			tag = str(self.data).lstrip('#')
			return f"{base_url}/api/v1/streaming/hashtag?tag={tag}"
		return None

	def start_stream(self):
		"""Start streaming for this timeline if supported."""
		if not self.supports_streaming:
			return
		if not self.app.prefs.streaming:
			return

		with self._stream_lock:
			if self._stream_started:
				return
			if self._stream_thread is not None and self._stream_thread.is_alive():
				return

			self._stream_started = True
			self._stream_thread = threading.Thread(
				target=self._run_stream,
				daemon=True
			)
			self._stream_thread.start()

	def stop_stream(self):
		"""Stop streaming for this timeline."""
		with self._stream_lock:
			self._stream_started = False
			# Thread will exit on next iteration when it checks _stream_started

	def _run_stream(self):
		"""Run the streaming connection for this timeline."""
		import requests
		import json
		from mastodon import AttribAccessDict
		from platforms.mastodon.models import mastodon_status_to_universal

		thread_id = threading.current_thread().ident
		consecutive_errors = 0
		base_delay = 5
		max_delay = 300

		def convert_to_attrib_dict(obj):
			"""Recursively convert dicts to AttribAccessDict for attribute access."""
			if isinstance(obj, dict):
				converted = {k: convert_to_attrib_dict(v) for k, v in obj.items()}
				return AttribAccessDict(**converted)
			elif isinstance(obj, list):
				return [convert_to_attrib_dict(item) for item in obj]
			return obj

		while self._stream_started:
			try:
				# Check if we're still the active stream thread
				if self._stream_thread is None or self._stream_thread.ident != thread_id:
					return

				stream_url = self.stream_endpoint
				if not stream_url:
					return

				# Only list timelines require authentication
				# Public streams (local, federated, hashtag, instance) don't need auth
				from version import APP_NAME, APP_VERSION
				headers = {
					"Accept": "text/event-stream",
					"User-Agent": f"{APP_NAME}/{APP_VERSION}",
				}
				if self.type == 'list':
					headers["Authorization"] = f"Bearer {self.account.prefs.access_token}"

				with requests.get(stream_url, headers=headers, stream=True, timeout=300) as response:
					response.raise_for_status()
					consecutive_errors = 0

					event_type = None
					data_lines = []

					for line in response.iter_lines():
						if not self._stream_started:
							return
						if self._stream_thread is None or self._stream_thread.ident != thread_id:
							return

						if line:
							line = line.decode('utf-8')
							if line.startswith('event:'):
								event_type = line[6:].strip()
							elif line.startswith('data:'):
								data_lines.append(line[5:].strip())
						else:
							# Empty line = end of event
							if event_type and data_lines:
								data_str = '\n'.join(data_lines)
								try:
									data = json.loads(data_str)
									self._handle_stream_event(event_type, data, convert_to_attrib_dict)
								except json.JSONDecodeError:
									pass
							event_type = None
							data_lines = []

			except requests.exceptions.Timeout:
				time.sleep(2)
				continue
			except Exception:
				consecutive_errors += 1
				if consecutive_errors >= 10:
					# Too many errors, give up
					self._stream_started = False
					return
				delay = min(base_delay * (2 ** (consecutive_errors - 1)), max_delay)
				time.sleep(delay)

	def _handle_stream_event(self, event_type, data, convert_func):
		"""Handle a streaming event for this timeline."""
		import wx
		from platforms.mastodon.models import mastodon_status_to_universal

		try:
			if event_type == 'update':
				status = convert_func(data)
				uni_status = mastodon_status_to_universal(status)
				if uni_status:
					wx.CallAfter(lambda s=uni_status: self.load(items=[s]))
			elif event_type == 'delete':
				status_id = str(data)
				def do_delete():
					for i, s in enumerate(self.statuses):
						if hasattr(s, 'id') and str(s.id) == status_id:
							if i < self.index:
								self.index = max(0, self.index - 1)
							elif i == self.index and self.index >= len(self.statuses) - 1:
								self.index = max(0, len(self.statuses) - 2)
							self.statuses.pop(i)
							self._status_ids.discard(status_id)
							self.invalidate_display_cache()
							if self == self.account.currentTimeline and self.account == self.app.currentAccount:
								main.window.refreshList()
							break
				wx.CallAfter(do_delete)
			elif event_type == 'status.update':
				status = convert_func(data)
				uni_status = mastodon_status_to_universal(status)
				if uni_status:
					def do_update():
						for i, s in enumerate(self.statuses):
							if hasattr(s, 'id') and str(s.id) == str(uni_status.id):
								self.statuses[i] = uni_status
								self.invalidate_display_cache()
								if self == self.account.currentTimeline and self.account == self.app.currentAccount:
									main.window.refreshList()
								break
					wx.CallAfter(do_update)
		except Exception:
			pass  # Silently ignore stream handler errors

	def read_items(self, items):
		pref = ""
		if len(self.app.accounts) > 1:
			pref = self.account.me.acct + ": "
		if len(items) >= 4:
			speak.speak(pref + str(len(items)) + " new in " + self.name)
			return
		speak.speak(pref + ", ".join(self.prepare(items)))

	def _status_passes_server_filter(self, status):
		"""Check if a status should be shown based on server-side filters.

		Returns True if the status should be shown, False if it should be hidden.
		Checks the 'filtered' attribute for any filters with filter_action='hide'.
		"""
		filtered = getattr(status, 'filtered', None)
		if not filtered:
			return True

		# Check each filter result - if any has action="hide", hide the post
		for result in filtered:
			filter_obj = getattr(result, 'filter', None)
			if filter_obj:
				action = getattr(filter_obj, 'filter_action', 'warn')
				if action == 'hide':
					return False

		return True

	def _add_status_with_filter(self, status, to_front=False, skip_cache_invalidation=False):
		"""Add a status to the timeline, respecting any active filter.

		Args:
			status: The status to add
			to_front: If True, insert at front of list; if False, append to end
			skip_cache_invalidation: If True, don't invalidate display cache (for incremental updates)

		Returns:
			True if the status was added to the visible list, False if filtered out
		"""
		from GUI.timeline_filter import should_show_status

		with self._status_lock:
			# Always track ID for duplicate checking, even if filtered
			if hasattr(status, 'id'):
				self._status_ids.add(str(status.id))

			# Check server-side filter action - hide posts completely if filter_action="hide"
			if not self._status_passes_server_filter(status):
				return False

			# Always add to unfiltered list if it exists
			if hasattr(self, '_unfiltered_statuses'):
				if to_front:
					self._unfiltered_statuses.insert(0, status)
				else:
					self._unfiltered_statuses.append(status)

			# Check if we should show this status based on filter
			if hasattr(self, '_filter_settings') and self._filter_settings:
				if not should_show_status(status, self._filter_settings, self.app, account=self.account):
					return False

			# Add to visible statuses
			if to_front:
				self.statuses.insert(0, status)
			else:
				self.statuses.append(status)
			if not skip_cache_invalidation:
				self.invalidate_display_cache()
			return True

	def has_status(self, status_id):
		"""Check if a status ID is already in this timeline (O(1) lookup)."""
		with self._status_lock:
			return str(status_id) in self._status_ids

	def try_add_status_id(self, status_id):
		"""Atomically check if status ID exists and add it if not.

		Returns True if the ID was added (not a duplicate), False if already exists.
		"""
		with self._status_lock:
			status_id_str = str(status_id)
			if status_id_str in self._status_ids:
				return False
			self._status_ids.add(status_id_str)
			return True

	def has_gap(self):
		"""Check if there's a gap in the timeline that needs to be filled."""
		return len(self._gaps) > 0

	def gap_count(self):
		"""Return the number of gaps in the timeline."""
		return len(self._gaps)

	def _should_detect_gaps(self):
		"""Check if gap detection should apply to this timeline type.

		Gap detection is currently disabled due to false positives
		(e.g., network outages causing huge idle times that trigger
		false gap detection on any full page refresh).
		"""
		# Disabled for now - the heuristic-based approach causes too many false positives
		return False

	# ============ Cache Methods ============

	def _get_cache(self):
		"""Get the timeline cache from the platform backend, if available."""
		if hasattr(self.account, '_platform') and self.account._platform:
			return getattr(self.account._platform, 'timeline_cache', None)
		return None

	def _should_use_cache(self):
		"""Check if this timeline should use caching."""
		# Check global cache enabled
		if not self.app.prefs.timeline_cache_enabled:
			return False

		# Check if cache is available
		cache = self._get_cache()
		if not cache or not cache.is_available():
			return False

		# Cacheable timeline types
		cacheable_types = {
			'home', 'mentions', 'notifications', 'favourites', 'bookmarks',
			'user', 'list', 'search', 'feed',
			'local', 'federated', 'instance', 'remote_user', 'pinned'
		}
		# Sent is a special user timeline we should cache
		if self.type == 'user' and self.name == 'Sent':
			return True

		return self.type in cacheable_types

	def _get_timeline_data_key(self):
		"""Get the data key for this timeline for caching."""
		if self.type in ('user', 'list', 'search', 'feed', 'instance', 'remote_user'):
			return self.data
		return None

	def _get_item_type(self):
		"""Get the item type for this timeline (status or notification)."""
		if self.type == 'notifications':
			return 'notification'
		return 'status'

	def get_cache_key(self):
		"""Get the cache key tuple for this timeline (for cleanup purposes)."""
		cache = self._get_cache()
		if cache:
			data_key = cache._get_timeline_key(self.type, self.name, self._get_timeline_data_key())
			return (self.type, self.name, data_key)
		return None

	def clear_cache(self):
		"""Clear the cache for this timeline."""
		cache = self._get_cache()
		if cache and cache.is_available():
			cache.clear_timeline(self.type, self.name, self._get_timeline_data_key())

	def _load_from_cache(self):
		"""Load timeline items from cache (synchronous).

		Returns True if cache was loaded, False otherwise.
		"""
		cache = self._get_cache()
		if not cache:
			return False

		try:
			items, metadata = cache.load_timeline(
				self.type,
				self.name,
				self._get_timeline_data_key(),
				self._get_item_type()
			)

			if not items:
				return False

			# Check if filter is active
			filter_active = hasattr(self, '_filter_settings') and self._filter_settings
			if filter_active:
				from GUI.timeline_filter import should_show_status

			# For notifications, check if we should filter out mentions from cache
			filter_mentions_from_notifications = False
			if self.type == "notifications":
				include_mentions = getattr(self.account.prefs, 'mentions_in_notifications', False)
				filter_mentions_from_notifications = not include_mentions

			# Load items into timeline
			for item in items:
				if item is None:
					continue
				# Filter mentions from notifications cache if setting is disabled
				if filter_mentions_from_notifications:
					notif_type = getattr(item, 'type', None)
					if notif_type == 'mention':
						continue
				# Check server-side filter action - hide posts completely if filter_action="hide"
				if not self._status_passes_server_filter(item):
					continue
				# Track ID for O(1) duplicate checking
				if hasattr(item, 'id'):
					self._status_ids.add(str(item.id))
				# If filter is active, add to unfiltered list and only add to visible if it passes filter
				if filter_active:
					self._unfiltered_statuses.append(item)
					if should_show_status(item, self._filter_settings, self.app, account=self.account):
						self.statuses.append(item)
				else:
					self.statuses.append(item)

			# Set up since_id for next refresh
			# Don't use since_id for timelines that use internal pagination IDs
			# (favourites, bookmarks, scheduled use internal IDs, not status IDs)
			if metadata.get('since_id') and items and self.type not in ('favourites', 'bookmarks', 'scheduled'):
				self.update_kwargs['since_id'] = metadata['since_id']

			# Clear any stale gaps from cache (gap detection is currently disabled)
			self._gaps = []

			# Set last load time to now
			import time
			self._last_load_time = time.time()

			# Store position ID for restore after API refresh
			# ID-based restore is more robust than index when new items arrive
			self._cached_position_id = metadata.get('last_position_id')

			# Set initial position (will be corrected after API refresh using ID)
			saved_index = metadata.get('last_index', 0)
			if self.statuses and saved_index >= 0 and saved_index < len(self.statuses):
				self.index = saved_index
			elif not self.statuses:
				# All items filtered out or empty cache - keep index at 0
				self.index = 0
			elif not self.app.prefs.reversed:
				self.index = 0
			else:
				self.index = len(self.statuses) - 1

			# Invalidate display cache
			self.invalidate_display_cache()

			# Mark initial load as complete (so API refresh is treated as update, not initial)
			self.initial = False

			# Notify account that this timeline's initial load is complete
			if hasattr(self.account, '_on_timeline_initial_load_complete'):
				self.account._on_timeline_initial_load_complete()

			# Start streaming for this timeline if supported
			self.start_stream()

			# Play ready sound if this is the last timeline
			if self.account.timelines and self == self.account.timelines[-1] and not self.account.ready:
				self.account.ready = True
				sound.play(self.account, "ready")

			# Update UI
			if self.account == self.app.currentAccount and self.account.currentTimeline == self:
				wx.CallAfter(main.window.refreshList)

			return True

		except Exception as e:
			import traceback
			print(f"Cache load error for {self.name}: {e}")
			traceback.print_exc()
			return False

	def _refresh_after_cache(self):
		"""Background refresh after loading from cache."""
		# Do a normal load (will fetch new items from API)
		# Since initial=False after cache load, this will be treated as an update
		self.load()

		# Restore position by saved ID after refresh
		# This is more robust than index-based restore since new items shift positions
		position_restored = False

		# For notifications/mentions, use the account prefs saved ID
		if self.type in ("notifications", "mentions"):
			position_restored = self.sync_local_position()
		# For other timelines, use the cached position ID
		elif hasattr(self, '_cached_position_id') and self._cached_position_id:
			# Find the item with this ID and set index
			for i, status in enumerate(self.statuses):
				if str(status.id) == str(self._cached_position_id):
					self.index = i
					position_restored = True
					break
			if not position_restored:
				# Position ID not found - item may have been deleted or aged out
				print(f"Position restore: ID {self._cached_position_id} not found in {self.name} ({len(self.statuses)} items)")
			# Clean up
			del self._cached_position_id

		if position_restored and self.app.currentAccount == self.account and self.account.currentTimeline == self:
			wx.CallAfter(main.window.list2.SetSelection, self.index)

	def _cache_timeline(self):
		"""Save current timeline items to cache (called after API load)."""
		if not self._should_use_cache():
			return

		cache = self._get_cache()
		if not cache:
			return

		# Use unfiltered statuses if filter is active, otherwise use visible statuses
		# This ensures filtered-out items are still cached for when filter is changed/removed
		source_statuses = getattr(self, '_unfiltered_statuses', None) or self.statuses

		# Don't cache if no items
		if not source_statuses:
			return

		try:
			# Get cache limit
			cache_limit = self.app.prefs.timeline_cache_limit

			# Get items to cache - always cache newest items regardless of reversed setting
			# When reversed=False: newest at start, so take [:limit]
			# When reversed=True: newest at end, so take [-limit:]
			if self.app.prefs.reversed:
				items_to_cache = source_statuses[-cache_limit:] if len(source_statuses) > cache_limit else source_statuses[:]
			else:
				items_to_cache = source_statuses[:cache_limit]

			# Get the ID at current position for robust restore (use visible statuses for position)
			position_id = None
			if self.index >= 0 and self.index < len(self.statuses):
				position_id = str(self.statuses[self.index].id)

			# Save to cache with gap info and current position
			cache.save_timeline(
				self.type,
				self.name,
				self._get_timeline_data_key(),
				items_to_cache,
				self._get_item_type(),
				limit=cache_limit,
				gaps=self._gaps if self._gaps else None,
				last_index=self.index,
				last_position_id=position_id
			)
		except Exception as e:
			print(f"Cache save error for {self.name}: {e}")

	def load_conversation(self):
		status = self.status

		# For boosted posts, use the reblogged status for conversation context
		# This ensures we get replies to the original post, not the boost wrapper
		actual_status = status
		if hasattr(status, 'reblog') and status.reblog:
			actual_status = status.reblog

		# Get the actual status ID (for mentions, id is notification_id, real id is in _original_status_id)
		status_id = getattr(actual_status, '_original_status_id', None) or actual_status.id
		source_status_id = str(status_id)  # Track source post to focus on it

		# Track position of source status in the stored list
		source_position = 0

		# Try to use get_status_context for full thread (works better for Bluesky)
		if hasattr(self.account, '_platform') and self.account._platform:
			try:
				context = self.account._platform.get_status_context(status_id)
				ancestors = context.get('ancestors', [])
				descendants = context.get('descendants', [])

				# Build thread: ancestors -> current status -> descendants
				for ancestor in ancestors:
					self.statuses.append(ancestor)
					if hasattr(ancestor, 'id'):
						self._status_ids.add(str(ancestor.id))
				# Source position is after all ancestors
				source_position = len(ancestors)
				self.statuses.append(actual_status)
				if hasattr(actual_status, 'id'):
					self._status_ids.add(str(actual_status.id))
				for descendant in descendants:
					self.statuses.append(descendant)
					if hasattr(descendant, 'id'):
						self._status_ids.add(str(descendant.id))
				self.invalidate_display_cache()
			except Exception:
				# Fall back to recursive method
				self.process_status(actual_status)
				self.invalidate_display_cache()
				# Find source position after recursive loading
				for i, s in enumerate(self.statuses):
					if str(getattr(s, 'id', '')) == source_status_id:
						source_position = i
						break
		else:
			# Fall back to recursive method for Mastodon API
			self.process_status(actual_status)
			self.invalidate_display_cache()
			# Find source position after recursive loading
			for i, s in enumerate(self.statuses):
				if str(getattr(s, 'id', '')) == source_status_id:
					source_position = i
					break

		# Conversation threads are always displayed in chronological order (oldest first)
		# regardless of the global reversed setting, since they represent a chat-like thread
		# Index directly matches the source position in the stored list
		self.index = source_position

		# Ensure index is valid
		if len(self.statuses) > 0:
			self.index = max(0, min(self.index, len(self.statuses) - 1))
		if self.account.currentTimeline == self:
			wx.CallAfter(main.window.refreshList)
		sound.play(self.account, "search")
		# Notify initial load complete
		if self.initial:
			self.initial = False
			if hasattr(self.account, '_on_timeline_initial_load_complete'):
				self.account._on_timeline_initial_load_complete()
			# Start streaming for this timeline if supported
			self.start_stream()

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
		# Process parents FIRST to maintain chronological order (oldest first)
		try:
			if hasattr(status, "in_reply_to_id") and status.in_reply_to_id is not None:
				# Check if this is a remote status
				if hasattr(status, '_instance_url') and status._instance_url:
					parent = self._lookup_remote_status(status._instance_url, status.in_reply_to_id)
				else:
					parent = self.app.lookup_status(self.account, status.in_reply_to_id)
				if parent:
					self.process_status(parent)
		except:
			pass

		# Then append current status
		self.statuses.append(status)
		if hasattr(status, 'id'):
			self._status_ids.add(str(status.id))

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
				# Start streaming for this timeline if supported (even if hidden, stream may be useful)
				self.start_stream()
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

	def load_here(self, speech=True):
		"""Load posts starting from the current position, filling in gaps.

		This loads posts using the current post's ID as max_id, inserting
		new posts below the current position. Stops when it finds posts
		that already exist in the timeline.

		Returns: (new_count, found_existing) tuple
		"""
		if self.hide:
			return (0, False)
		if self._loading:
			return (0, False)
		self._loading = True
		try:
			result = self._do_load_here(speech)
			# Clear the anchor after single load (load_all_here manages its own cleanup)
			if not self._loading_all_active:
				self._move_to_oldest_loaded()
				self._clear_load_here_anchor()
			return result
		finally:
			self._loading = False

	def _clear_load_here_anchor(self):
		"""Clear the load_here anchor point."""
		self._load_here_anchor_id = None
		self._load_here_anchor_index = None
		self._load_here_items_inserted = 0
		self._load_here_oldest_index = None

	def _move_to_oldest_loaded(self):
		"""Move timeline position to the oldest post loaded by load_here."""
		if hasattr(self, '_load_here_oldest_index') and self._load_here_oldest_index is not None:
			if 0 <= self._load_here_oldest_index < len(self.statuses):
				self.index = self._load_here_oldest_index
				speak.speak("Nothing more to load")
				# Update UI if this timeline is active
				if self.app.currentAccount == self.account and self.account.currentTimeline == self:
					wx.CallAfter(main.window.refreshList)
					wx.CallAfter(main.window.list.SetSelection, self.index)

	def _do_load_here(self, speech=True):
		"""Internal implementation of load_here."""
		# Get the current status - but only set the anchor on first call
		if not self.statuses or self.index >= len(self.statuses):
			if speech:
				speak.speak("No current post")
			return (0, False)

		# Store the starting position and ID on first call (anchor point)
		# This ensures subsequent calls in load_all_here use the same reference point
		if not hasattr(self, '_load_here_anchor_id') or self._load_here_anchor_id is None:
			self._load_here_anchor_id = self.statuses[self.index].id
			self._load_here_anchor_index = self.index
			self._load_here_items_inserted = 0

		current_id = self._load_here_anchor_id
		# Calculate the actual insertion position based on items already inserted
		base_insert_index = self._load_here_anchor_index + self._load_here_items_inserted

		# Build the set of existing IDs for quick lookup
		existing_ids = set(self._status_ids)

		# Determine the ID of the next post (if any) - posts after the insertion point
		# Use the anchor index, not the user's current position
		# For normal order: items at higher indices are older (lower IDs)
		# For reversed order: items at lower indices are older (lower IDs)
		next_existing_id = None
		if not self.app.prefs.reversed:
			# Normal mode: insertion point is after anchor, check next post (older)
			check_index = base_insert_index + 1
			if check_index < len(self.statuses):
				next_existing_id = self.statuses[check_index].id
		else:
			# Reversed mode: insertion point is at anchor, check post before anchor (older)
			check_index = self._load_here_anchor_index - 1
			if check_index >= 0:
				next_existing_id = self.statuses[check_index].id

		# Fetch posts using current post's ID as max_id
		load_kwargs = dict(self.prev_kwargs)
		load_kwargs['max_id'] = current_id

		try:
			# Determine how many pages to fetch
			fetch_pages = getattr(self.app.prefs, 'fetch_pages', 1)
			if fetch_pages < 1:
				fetch_pages = 1

			if fetch_pages > 1:
				tl = self._fetch_multiple_pages(load_kwargs, fetch_pages)
			else:
				tl = self.func(**load_kwargs)
		except Exception as error:
			self.app.handle_error(error, self.account.me.acct + "'s " + self.name)
			return (0, False)

		if tl is None or len(tl) == 0:
			return (0, True)

		# Process the fetched items
		new_items = []
		found_existing = False

		for item in tl:
			# Skip the current item itself (API returns max_id inclusive)
			if item.id == current_id:
				continue

			# Check if this item already exists
			if item.id in existing_ids:
				found_existing = True
				break

			# Check if we've reached the next existing post
			# This handles the case where IDs might not be contiguous
			if next_existing_id is not None:
				# For Mastodon-style numeric IDs or Bluesky string IDs
				# We can compare if the fetched item is "between" current and next
				try:
					# Try numeric comparison first (Mastodon uses numeric-string IDs)
					item_num = int(item.id) if isinstance(item.id, str) else item.id
					next_num = int(next_existing_id) if isinstance(next_existing_id, str) else next_existing_id
					current_num = int(current_id) if isinstance(current_id, str) else current_id

					if not self.app.prefs.reversed:
						# Normal order: older posts have lower IDs
						# If item ID is <= next existing, we've reached existing territory
						if item_num <= next_num:
							found_existing = True
							break
					else:
						# Reversed order: we're going towards older (lower IDs)
						if item_num <= next_num:
							found_existing = True
							break
				except (ValueError, TypeError):
					# Non-numeric IDs (Bluesky), just rely on the set lookup
					pass

			# Add to user cache
			if self.type == "notifications":
				self.account.user_cache.add_users_from_notification(item)
			elif self.type == "mentions":
				self.account.user_cache.add_users_from_status(item)
			elif self.type != "conversations":
				self.account.user_cache.add_users_from_status(item)

			# Try to add (checks for duplicates)
			# For scheduled posts, use _scheduled_id if available
			status_id = getattr(item, '_scheduled_id', None) or item.id
			if self.try_add_status_id(status_id):
				new_items.append(item)

		if len(new_items) == 0:
			if speech:
				if found_existing:
					speak.speak("Gap filled, no new posts")
				else:
					speak.speak("No new posts")
			return (0, found_existing)

		# Insert the new items at the correct position
		# API returns items newest-to-oldest (item 0 is newest of the older posts)
		# Use anchor-based position, NOT the user's current position
		#
		# Normal mode (newest at top, oldest at bottom):
		#   - Older posts go at higher indices (after anchor position)
		#   - Insert at anchor+1+items_already_inserted, anchor+2+items_already_inserted, etc.
		#
		# Reversed mode (oldest at top, newest at bottom):
		#   - Older posts go at lower indices (before anchor position)
		#   - Insert repeatedly at anchor index, which pushes items down
		#   - This naturally reverses the order: [A, B, C] inserted at pos 5
		#     becomes [..., C, B, A, anchor, ...] with C at 5, B at 6, A at 7

		items_added = 0
		if not self.app.prefs.reversed:
			# Normal mode: insert after anchor position
			insert_pos = base_insert_index + 1
			for i, item in enumerate(new_items):
				shown = self._add_status_at_position(item, insert_pos + i)
				if shown:
					items_added += 1
			# In normal mode, oldest loaded is at the last inserted position
			if items_added > 0:
				self._load_here_oldest_index = insert_pos + items_added - 1
		else:
			# Reversed mode: insert at anchor position repeatedly
			# Each insert pushes anchor and subsequent items down
			insert_pos = self._load_here_anchor_index
			for item in new_items:
				shown = self._add_status_at_position(item, insert_pos)
				if shown:
					items_added += 1
			# In reversed mode, oldest loaded is at the insert position (first one inserted ends up there)
			if items_added > 0:
				self._load_here_oldest_index = insert_pos

		# Track total items inserted for subsequent calls
		self._load_here_items_inserted += items_added

		# Refresh the UI
		if self.app.currentAccount == self.account and self.account.currentTimeline == self:
			wx.CallAfter(main.window.refreshList)

		# Play sounds for new items
		if not self.mute and not self.hide and len(new_items) > 0:
			self.play(new_items)

		if speech:
			if found_existing:
				speak.speak(f"Gap filled, {len(new_items)} posts loaded")
			else:
				speak.speak(f"{len(new_items)} posts loaded")

		return (len(new_items), found_existing)

	def _status_passes_filter(self, status):
		"""Check if a status passes the current filter settings.

		Returns True if the status should be shown, False if it should be filtered out.
		"""
		if not hasattr(self, '_filter_settings') or not self._filter_settings:
			return True
		from GUI.timeline_filter import should_show_status
		return should_show_status(status, self._filter_settings, self.app, account=self.account)

	def _add_status_at_position(self, status, position):
		"""Add a status at a specific position in the statuses list.

		Returns True if the status was shown (passed filter), False otherwise.
		"""
		# Check server-side filter action - hide posts completely if filter_action="hide"
		if not self._status_passes_server_filter(status):
			return False

		# Apply client-side filter if one is set
		if hasattr(self, '_filter_settings') and self._filter_settings:
			if not self._status_passes_filter(status):
				# Still track in unfiltered list
				if hasattr(self, '_unfiltered_statuses'):
					self._unfiltered_statuses.insert(position, status)
				return False

		# Insert at the specified position
		if position >= len(self.statuses):
			self.statuses.append(status)
		else:
			self.statuses.insert(position, status)

		# Also update unfiltered list if we have one
		if hasattr(self, '_unfiltered_statuses') and self._unfiltered_statuses is not None:
			if position >= len(self._unfiltered_statuses):
				self._unfiltered_statuses.append(status)
			else:
				self._unfiltered_statuses.insert(position, status)

		return True

	def load_all_here(self):
		"""Load all posts from the current position until gap is filled or an error occurs."""
		self._stop_loading_all = False
		self._loading_all_active = True
		total_loaded = 0

		speak.speak("Loading posts from here...")

		while not self._stop_loading_all:
			try:
				new_count, found_existing = self.load_here(speech=False)
			except Exception as e:
				speak.speak(f"Stopped loading: {e}")
				break

			total_loaded += new_count

			if found_existing or new_count == 0:
				# Gap is filled or no more posts
				speak.speak(f"Gap filled. {total_loaded} posts loaded in total.")
				break

			# Small delay to avoid hammering the API
			import time
			time.sleep(0.5)

		if self._stop_loading_all:
			speak.speak(f"Loading stopped. {total_loaded} posts loaded.")

		# Move to the oldest loaded post and clear the anchor
		self._move_to_oldest_loaded()
		self._clear_load_here_anchor()
		self._loading_all_active = False

	def _do_load(self, back=False, speech=False, items=[]):
		# Conversation timelines use load_conversation() instead of func
		if self.type == "conversation":
			if back:
				# Conversation threads don't support loading previous
				return False
			# Refresh the conversation thread - preserve position
			old_index = self.index
			old_count = len(self.statuses)
			self.statuses = []
			self._status_ids = set()
			self.load_conversation()
			# Restore position (clamped to new length)
			if self.statuses:
				self.index = min(old_index, len(self.statuses) - 1)
			if speech:
				speak.speak("Refreshed")
			return True
		if items == []:
			if back:
				# Check if we should fill a gap first
				if self._gaps:
					# Fill the first gap in the list
					self.prev_kwargs['max_id'] = self._gaps[0]['max_id']
				else:
					# Normal load previous: use unfiltered statuses for pagination if filter is applied
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

				# Ensure since_id is never used for timelines with internal pagination
				# (favourites, bookmarks, scheduled use internal IDs, not status IDs)
				if self.type in ('favourites', 'bookmarks', 'scheduled'):
					self.update_kwargs.pop('since_id', None)
					self.prev_kwargs.pop('since_id', None)

				if not back:
					if self.initial and single_on_startup:
						# Single API call on initial load when single_api_on_startup is enabled
						tl = self.func(**self.update_kwargs)
					elif fetch_pages > 1:
						# Multi-page fetch for initial load or refresh
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
					# Start streaming for this timeline if supported
					self.start_stream()
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
					# Stop streaming before removing timeline
					self.stop_stream()
					self.account.timelines.remove(self)
					if self.account == self.app.currentAccount:
						# Use wx.CallAfter for thread safety (this runs in background thread)
						def update_ui_after_remove():
							main.window.refreshTimelines()
							if self.account.currentTimeline == self:
								main.window.list.SetSelection(0)
								self.account.currentIndex = 0
								main.window.on_list_change(None)
						wx.CallAfter(update_ui_after_remove)
				return
		else:
			tl = items
		if tl is not None:
			# Sort scheduled posts by scheduled date (soonest first)
			if self.type == "scheduled" and tl:
				tl = sorted(tl, key=lambda x: getattr(x, '_scheduled_at', None) or getattr(x, 'scheduled_at', None) or '')

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

				# Check for duplicates using atomic check-and-add to prevent race conditions
				# between streaming and REST API refresh threads
				# For scheduled posts, use _scheduled_id if available for consistent deduplication
				status_id = getattr(i, '_scheduled_id', None) or i.id
				if self.try_add_status_id(status_id):
					newitems += 1
					# For initial/back load: add directly to statuses
					# For refresh: collect first, add after processing all items
					if self.initial or back:
						# Insert at front for reversed (oldest at top), append for normal (newest at top)
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

					# Check if we can use incremental update (single streaming item, is current timeline)
					use_incremental = (
						items != [] and
						len(objs) == 1 and
						self.app.currentAccount == self.account and
						self.account.currentTimeline == self and
						hasattr(self, '_display_list_cache') and
						self._display_list_cache is not None
					)

					# Filter objs2 to only include items that pass the filter
					filtered_objs2 = []
					for i in objs:
						# Skip cache invalidation if using incremental update
						shown = self._add_status_with_filter(i, to_front=not self.app.prefs.reversed, skip_cache_invalidation=use_incremental)
						if shown:
							filtered_objs2.append(i)
					objs2 = filtered_objs2

				if self.app.currentAccount == self.account and self.account.currentTimeline == self:
					# For single streaming items, use incremental update for better performance
					# This avoids O(n) list rebuild for each streaming item
					if items != [] and len(filtered_objs2) == 1:
						# Single streaming item - try incremental update
						status = filtered_objs2[0]
						to_front = not self.app.prefs.reversed
						display = self.add_display_item(status, to_front=to_front)
						if display is not None:
							# Incremental update successful
							# Position is 0 for front, len(statuses)-1 for back
							position = 0 if to_front else len(self.statuses) - 1
							wx.CallAfter(main.window.insertListItem, display, position)
						else:
							# Cache out of sync, fall back to full refresh
							wx.CallAfter(main.window.refreshList)
					else:
						# Bulk items or API load - use full refresh
						wx.CallAfter(main.window.refreshList)

				if items == []:
					# Don't set since_id for timelines that use internal pagination IDs
					# (favourites, bookmarks, scheduled use internal IDs, not status IDs)
					if self.type not in ('favourites', 'bookmarks', 'scheduled'):
						# Find the newest non-pinned post for since_id
						# Pinned posts can be very old and would cause fetching tons of "new" posts
						since_id_post = None
						if not self.app.prefs.reversed:
							# First item is newest - find first non-pinned
							for post in tl:
								if not getattr(post, 'pinned', False) and not getattr(post, '_pinned', False):
									since_id_post = post
									break
							if not since_id_post and tl:
								since_id_post = tl[0]  # Fallback if all pinned
						else:
							# Last item is newest - find last non-pinned
							for post in reversed(tl):
								if not getattr(post, 'pinned', False) and not getattr(post, '_pinned', False):
									since_id_post = post
									break
							if not since_id_post and tl:
								since_id_post = tl[-1]  # Fallback if all pinned
						if since_id_post:
							self.update_kwargs['since_id'] = since_id_post.id

					# Update last load time
					import time
					self._last_load_time = time.time()

				# Adjust index when items are added before current position
				if not back and not self.initial:
					if not self.app.prefs.reversed:
						# New items added at front, shift index to stay on same item
						self.index += len(objs2)
				if back and self.app.prefs.reversed:
					# Previous items added at front, shift index to stay on same item
					self.index += len(objs2)

				if self.initial:
					if not self.app.prefs.reversed:
						self.index = 0
					else:
						self.index = len(self.statuses) - 1
				if not self.mute and not self.hide and len(objs2) > 0:
					self.play(objs2)
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

				# Set last load time
				import time
				self._last_load_time = time.time()

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
				# Cache timeline for fast startup (in background to not block)
				threading.Thread(target=self._cache_timeline, daemon=True).start()
				# Notify account that this timeline's initial load is complete
				if hasattr(self.account, '_on_timeline_initial_load_complete'):
					self.account._on_timeline_initial_load_complete()
				# Start streaming for this timeline if supported
				self.start_stream()
			else:
				# On refresh: if user hasn't moved, check if server marker changed
				# This handles the case where another client updated the position
				if not self._position_moved:
					synced = self.sync_position_from_server()
					if synced and self.app.currentAccount == self.account and self.account.currentTimeline == self:
						wx.CallAfter(main.window.list2.SetSelection, self.index)
				# Update cache after load previous and check if gap is filled
				if back:
					# Check if gap is now filled
					if self._gaps and tl is not None:
						fetch_limit = self.prev_kwargs.get('limit', 40)
						if len(tl) < fetch_limit:
							# Got partial page - this gap is filled, remove it
							self._gaps.pop(0)
							if self._gaps:
								speak.speak(f"Gap filled, {len(self._gaps)} remaining")
							else:
								speak.speak("All gaps filled")
						else:
							# Still more items in this gap - update position for next load
							if not self.app.prefs.reversed:
								self._gaps[0]['max_id'] = str(tl[-1].id)
							else:
								self._gaps[0]['max_id'] = str(tl[0].id)
					threading.Thread(target=self._cache_timeline, daemon=True).start()
		if self.account.timelines and self == self.account.timelines[-1] and not self.account.ready:
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
		# Return cached display list if available and valid
		if hasattr(self, '_display_list_cache') and self._display_list_cache is not None:
			if len(self._display_list_cache) == len(self.statuses):
				return self._display_list_cache

		# Build display list (cache individual items for future use)
		items = []
		# Conversation threads are always displayed in chronological order (oldest first)
		# regardless of global reversed setting, since they represent a chat-like thread
		statuses_to_display = self.statuses
		for i in statuses_to_display:
			# Use cached display string if available
			cache_attr = '_display_cache'
			cached = getattr(i, cache_attr, None)
			if cached is not None:
				items.append(cached)
			else:
				if self.type == "notifications":
					display = self.app.process_notification(i, account=self.account)
				elif self.type == "conversations":
					display = self.app.process_conversation(i, account=self.account)
				else:
					display = self.app.process_status(i, account=self.account)
				# Try to cache, but don't fail if object doesn't support it
				try:
					setattr(i, cache_attr, display)
				except (AttributeError, TypeError):
					pass
				items.append(display)

		# Cache the full display list
		self._display_list_cache = items
		return items

	def invalidate_display_cache(self):
		"""Invalidate the cached display list (call when statuses change)."""
		self._display_list_cache = None

	def _get_display_string(self, status):
		"""Get display string for a single status (using cache if available)."""
		cached = getattr(status, '_display_cache', None)
		if cached is not None:
			return cached

		if self.type == "notifications":
			display = self.app.process_notification(status, account=self.account)
		elif self.type == "conversations":
			display = self.app.process_conversation(status, account=self.account)
		else:
			display = self.app.process_status(status, account=self.account)

		# Try to cache
		try:
			status._display_cache = display
		except (AttributeError, TypeError):
			pass
		return display

	def add_display_item(self, status, to_front=True):
		"""Add a single item to display list incrementally (for streaming).

		Returns the display string if successful, None if full refresh needed.
		"""
		# If no cache exists, need full rebuild
		if not hasattr(self, '_display_list_cache') or self._display_list_cache is None:
			return None

		# Check if cache is out of sync (shouldn't happen, but be safe)
		if len(self._display_list_cache) != len(self.statuses) - 1:
			self._display_list_cache = None
			return None

		display = self._get_display_string(status)

		# Update cache incrementally
		if to_front:
			self._display_list_cache.insert(0, display)
		else:
			self._display_list_cache.append(display)

		return display

	def prepare(self, items):
		"""Convert status objects to display strings, preserving order.

		The items should already be in the correct order for display.
		This function only converts them to strings, it does not reorder.
		"""
		items2 = []
		for i in items:
			if self.type == "notifications":
				processed = self.app.process_notification(i, account=self.account)
			elif self.type == "conversations":
				processed = self.app.process_conversation(i, account=self.account)
			else:
				# mentions now treated same as home/user/etc.
				processed = self.app.process_status(i, account=self.account)
			# Cache the display string on the item (if supported)
			try:
				i._display_cache = processed
			except (AttributeError, TypeError):
				pass
			items2.append(processed)
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
	"""Reverse all timelines when the reversed setting is toggled."""
	for account in app.accounts:
		for tl in account.timelines:
			# Reverse visible statuses
			tl.statuses.reverse()
			# Also reverse unfiltered statuses if filter is active
			if hasattr(tl, '_unfiltered_statuses') and tl._unfiltered_statuses:
				tl._unfiltered_statuses.reverse()
			# Invert the index to maintain relative position
			if tl.statuses:
				tl.index = (len(tl.statuses) - 1) - tl.index
				# Clamp index to valid range
				tl.index = max(0, min(tl.index, len(tl.statuses) - 1))
			# Invalidate display cache
			tl.invalidate_display_cache()
	main.window.on_list_change(None)
