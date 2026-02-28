import datetime
from mastodon import Mastodon, MastodonError
import streaming
import application
from version import APP_NAME, APP_VERSION
import threading
from GUI import main, misc
import config
import timeline
import speak
from GUI.ask import *
from GUI.platform_dialog import select_platform, get_bluesky_credentials
import webbrowser
import platform
import os
import sys
import wx

from models import UserCache
from platforms.mastodon import MastodonAccount

# Get logger for API operations
try:
	from logging_config import get_logger
	_logger = get_logger('api')
except ImportError:
	_logger = None


class AccountSetupCancelled(Exception):
	"""Raised when user cancels account setup."""
	pass


def _exit_app():
	"""Safely exit the application from within wxPython context."""
	# Raise exception to stop current code execution, then schedule exit
	raise AccountSetupCancelled()


class mastodon(object):
	"""Multi-platform account wrapper. Despite the name, supports both Mastodon and Bluesky."""

	def __init__(self, app, index):
		self.app = app
		self.ready = False
		self.timelines = []
		self.currentTimeline = None
		self.currentIndex = 0
		self.currentStatus = None
		self.confpath = ""
		# Initialize streaming-related attributes early
		self._pending_initial_loads = 0
		self._initial_loads_lock = threading.Lock()
		self._stream_lock = threading.Lock()  # Prevents multiple stream connections
		self.stream_listener = None
		self.stream_thread = None
		self.stream = None
		self._stream_started = False
		# In portable mode, don't add FastSM prefix (userdata is already app-specific)
		if config.is_portable_mode():
			self.prefs = config.Config(name="account"+str(index), autosave=True)
			self.confpath = self.prefs._user_config_home+"/account"+str(index)
		else:
			self.prefs = config.Config(name="FastSM/account"+str(index), autosave=True)
			self.confpath = self.prefs._user_config_home+"/FastSM/account"+str(index)

		# Platform backend (initialized after authentication)
		self._platform = None

		# Check platform type - this determines which auth flow to use
		self.prefs.platform_type = self.prefs.get("platform_type", "")

		# Timeline preferences (shared across platforms)
		self.prefs.user_timelines = self.prefs.get("user_timelines", [])
		self.prefs.list_timelines = self.prefs.get("list_timelines", [])
		self.prefs.search_timelines = self.prefs.get("search_timelines", [])
		self.prefs.custom_timelines = self.prefs.get("custom_timelines", [])
		self.prefs.instance_timelines = self.prefs.get("instance_timelines", [])
		self.prefs.remote_user_timelines = self.prefs.get("remote_user_timelines", [])
		# Built-in timeline order (list of timeline types in desired order)
		self.prefs.timeline_order = self.prefs.get("timeline_order", [])

		# Remote API instances for instance timelines (unauthenticated)
		self.remote_apis = {}
		self.prefs.footer = self.prefs.get("footer", "")
		self.prefs.soundpack = self.prefs.get("soundpack", "default")
		self.prefs.soundpan = self.prefs.get("soundpan", 0)
		self.prefs.soundpack_volume = self.prefs.get("soundpack_volume", 1.0)  # Per-account soundpack volume
		self.prefs.mentions_in_notifications = self.prefs.get("mentions_in_notifications", False)
		# Local position sync for notifications/mentions timelines
		self.prefs.last_notifications_id = self.prefs.get("last_notifications_id", None)
		self.prefs.last_mentions_id = self.prefs.get("last_mentions_id", None)
		# User aliases - maps user ID to custom display name
		self.prefs.aliases = self.prefs.get("aliases", {})

		# Determine platform type if not set
		if self.prefs.platform_type == "":
			# New account - ask user which platform
			selected = select_platform(main.window)
			if selected is None:
				_exit_app()
			self.prefs.platform_type = selected

		# Initialize based on platform type
		if self.prefs.platform_type == "bluesky":
			self._init_bluesky(index)
		else:
			self.prefs.platform_type = "mastodon"
			self._init_mastodon(index)

	def _init_mastodon(self, index):
		"""Initialize Mastodon account."""
		# Mastodon-specific config
		self.prefs.instance_url = self.prefs.get("instance_url", "")
		self.prefs.access_token = self.prefs.get("access_token", "")
		is_new_signin = self.prefs.access_token == ""  # Track if this is a new sign-in
		self.prefs.client_id = self.prefs.get("client_id", "")
		self.prefs.client_secret = self.prefs.get("client_secret", "")

		# Get instance URL if not set or invalid
		def is_valid_instance_url(url):
			"""Check if URL is a valid instance URL with a host."""
			if not url or not url.strip():
				return False
			# Must have a host after the protocol
			if url.startswith("https://"):
				host = url[8:]
			elif url.startswith("http://"):
				host = url[7:]
			else:
				host = url
			# Host must have at least one dot or be localhost
			return bool(host) and ('.' in host or host.startswith('localhost'))

		if not is_valid_instance_url(self.prefs.instance_url):
			# Clear credentials if instance URL is invalid (they're tied to the instance)
			self.prefs.client_id = ""
			self.prefs.client_secret = ""
			self.prefs.access_token = ""

			self.prefs.instance_url = ask(caption="Mastodon Instance",
				message="Enter your Mastodon instance URL (e.g., mastodon.social, fosstodon.org):")
			if self.prefs.instance_url is None or not self.prefs.instance_url.strip():
				_exit_app()
			self.prefs.instance_url = self.prefs.instance_url.strip()
			# Ensure https://
			if not self.prefs.instance_url.startswith("https://") and not self.prefs.instance_url.startswith("http://"):
				self.prefs.instance_url = "https://" + self.prefs.instance_url

		# Register app if needed
		if self.prefs.client_id == "" or self.prefs.client_secret == "":
			try:
				client_id, client_secret = Mastodon.create_app(
					"FastSM",
					scopes=['read', 'write', 'follow', 'push'],
					redirect_uris='urn:ietf:wg:oauth:2.0:oob',
					api_base_url=self.prefs.instance_url,
					user_agent=f"{APP_NAME}/{APP_VERSION}"
				)
				self.prefs.client_id = client_id
				self.prefs.client_secret = client_secret
			except MastodonError as e:
				speak.speak("Error registering app: " + str(e))
				_exit_app()

		# Authenticate if needed
		if self.prefs.access_token == "":
			try:
				temp_api = Mastodon(
					client_id=self.prefs.client_id,
					client_secret=self.prefs.client_secret,
					api_base_url=self.prefs.instance_url,
					user_agent=f"{APP_NAME}/{APP_VERSION}"
				)
				auth_url = temp_api.auth_request_url(
					scopes=['read', 'write', 'follow', 'push'],
					redirect_uris='urn:ietf:wg:oauth:2.0:oob'
				)
				webbrowser.open(auth_url)

				auth_code = ask(caption="Authorization Code",
					message="Enter the authorization code from your browser:")
				if auth_code is None:
					_exit_app()

				access_token = temp_api.log_in(code=auth_code, scopes=['read', 'write', 'follow', 'push'])
				self.prefs.access_token = access_token
			except MastodonError as e:
				speak.speak("Error during authentication: " + str(e))
				_exit_app()

		# Initialize the API
		self.api = Mastodon(
			client_id=self.prefs.client_id,
			client_secret=self.prefs.client_secret,
			access_token=self.prefs.access_token,
			api_base_url=self.prefs.instance_url,
			user_agent=f"{APP_NAME}/{APP_VERSION}"
		)

		# Verify credentials and get user info
		try:
			self.me = self.api.account_verify_credentials()
		except MastodonError as e:
			# Don't clear credentials on transient failures (server offline, network issues)
			# Only exit - credentials will be preserved for next startup
			speak.speak("Error connecting to server: " + str(e))
			_exit_app()

		# Prompt to follow FastSM account on new sign-in
		if is_new_signin:
			self._prompt_follow_fastsm()

		# Get instance info for character limit (use cached if available)
		cached_max_chars = self.prefs.get("cached_max_chars", 0)
		if cached_max_chars > 0:
			self.max_chars = cached_max_chars
		else:
			try:
				instance_info = self.api.instance()
				if hasattr(instance_info, 'configuration') and hasattr(instance_info.configuration, 'statuses'):
					self.max_chars = instance_info.configuration.statuses.max_characters
				else:
					self.max_chars = 500
				# Cache it for next time
				self.prefs.cached_max_chars = self.max_chars
			except:
				self.max_chars = 500
		# Get default visibility from user info (already fetched)
		self.default_visibility = getattr(self.me, 'source', {}).get('privacy', 'public')

		# Initialize platform backend with user cache
		self._platform = MastodonAccount(self.app, index, self.api, self.me, self.confpath, self.max_chars, self.prefs)

		# Migrate global user cache to per-account if this is the first run
		self._migrate_user_cache()

		self._finish_init(index)

		# Create built-in timelines in user's preferred order
		self._create_builtin_timelines()

		# Restore saved timelines (avoid API calls during startup for speed)
		for ut_entry in list(self.prefs.user_timelines):
			try:
				# Handle both string and dict entries (dict has username and optional filter)
				if isinstance(ut_entry, dict):
					username = ut_entry.get('username', '')
					user_filter = ut_entry.get('filter')
					filter_labels = {
						'posts_no_replies': 'Posts Only',
						'posts_with_media': 'Media',
						'posts_and_author_threads': 'Threads',
						'posts_with_video': 'Videos',
						'posts_no_boosts': 'No Boosts',
					}
					tl_name = username + "'s Timeline"
					if user_filter and user_filter in filter_labels:
						tl_name = f"{username}'s {filter_labels[user_filter]}"
					self.timelines.append(timeline.timeline(self, name=tl_name, type="user", data=ut_entry, user=None, silent=True))
				else:
					username = ut_entry
					self.timelines.append(timeline.timeline(self, name=username + "'s Timeline", type="user", data=username, user=None, silent=True))
			except:
				self.prefs.user_timelines.remove(ut_entry)
		for list_data in list(self.prefs.list_timelines):
			try:
				if not isinstance(list_data, dict):
					self.prefs.list_timelines.remove(list_data)
					continue
				list_id = list_data.get('id')
				list_name = list_data.get('name', 'List')
				self.timelines.append(timeline.timeline(self, name=list_name + " List", type="list", data=list_id, silent=True))
			except:
				self.prefs.list_timelines.remove(list_data)
		for q in list(self.prefs.search_timelines):
			try:
				self.timelines.append(timeline.timeline(self, name=q + " Search", type="search", data=q, silent=True))
			except:
				self.prefs.search_timelines.remove(q)

		# Restore custom timelines (local, federated, favourites, bookmarks)
		for ct in list(self.prefs.custom_timelines):
			try:
				tl_type = ct.get('type', '')
				tl_id = ct.get('id', '')
				tl_name = ct.get('name', tl_type.title())
				if tl_type in ('local', 'federated', 'favourites', 'bookmarks'):
					self.timelines.append(timeline.timeline(self, name=tl_name, type=tl_type, data=tl_id, silent=True))
			except:
				self.prefs.custom_timelines.remove(ct)

		# Restore instance timelines (remote instance local timelines)
		for inst in list(self.prefs.instance_timelines):
			try:
				inst_url = inst.get('url', '')
				inst_name = inst.get('name', inst_url + ' Local')
				if inst_url:
					self.timelines.append(timeline.timeline(self, name=inst_name, type="instance", data=inst_url, silent=True))
			except:
				self.prefs.instance_timelines.remove(inst)

		# Restore remote user timelines
		for rut in list(self.prefs.remote_user_timelines):
			try:
				inst_url = rut.get('url', '')
				username = rut.get('username', '')
				rut_filter = rut.get('filter')
				# Build timeline name based on filter
				filter_labels = {
					'posts_no_replies': 'Posts Only',
					'posts_with_media': 'Media',
					'posts_no_boosts': 'No Boosts',
				}
				instance_domain = inst_url.replace('https://', '')
				rut_name = f"@{username}@{instance_domain}"
				if rut_filter and rut_filter in filter_labels:
					rut_name = f"@{username}@{instance_domain}'s {filter_labels[rut_filter]}"
				# Use saved name if available
				if rut.get('name'):
					rut_name = rut.get('name')
				if inst_url and username:
					data = {'url': inst_url, 'username': username}
					if rut_filter:
						data['filter'] = rut_filter
					self.timelines.append(timeline.timeline(self, name=rut_name, type="remote_user", data=data, silent=True))
			except:
				self.prefs.remote_user_timelines.remove(rut)

		# Only reset stream state if not already streaming
		# (this can be called during re-init while stream is running)
		if not (self.stream_thread is not None and self.stream_thread.is_alive()):
			self.stream_listener = None
			self.stream = None
			self._stream_started = False
		# Don't start streaming yet - wait for initial timeline loads to complete
		# Streaming will be started by _check_initial_loads_complete()

		self._finish_timeline_init()

	def _prompt_follow_fastsm(self):
		"""Prompt user to follow MewProjects account after new Mastodon sign-in."""
		result = wx.MessageBox(
			"Would you like to follow MewProjects@fwoof.space to get updates about the app?",
			"Follow MewProjects",
			wx.YES_NO | wx.ICON_QUESTION
		)
		if result == wx.YES:
			try:
				# Look up the MewProjects account via search
				results = self.api.account_search(q="MewProjects@fwoof.space", limit=1)
				if results and len(results) > 0:
					self.api.account_follow(id=results[0].id)
					speak.speak("Now following MewProjects")
				else:
					speak.speak("Could not find MewProjects account")
			except Exception as e:
				speak.speak(f"Could not follow: {e}")

	def _init_bluesky(self, index):
		"""Initialize Bluesky account."""
		from atproto import Client
		from atproto.exceptions import AtProtocolError
		from platforms.bluesky import BlueskyAccount, bluesky_profile_to_universal

		# Bluesky-specific config
		self.prefs.bluesky_handle = self.prefs.get("bluesky_handle", "")
		self.prefs.bluesky_password = self.prefs.get("bluesky_password", "")
		self.prefs.bluesky_service = self.prefs.get("bluesky_service", "https://bsky.social")

		# Get credentials if not set
		if self.prefs.bluesky_handle == "" or self.prefs.bluesky_password == "":
			creds = get_bluesky_credentials(main.window)
			if creds is None:
				_exit_app()
			self.prefs.bluesky_handle = creds['handle']
			self.prefs.bluesky_password = creds['password']
			self.prefs.bluesky_service = creds['service_url']

		# Initialize the client and login
		try:
			self.api = Client(base_url=self.prefs.bluesky_service)
			raw_profile = self.api.login(self.prefs.bluesky_handle, self.prefs.bluesky_password)
			self.me = bluesky_profile_to_universal(raw_profile)
		except AtProtocolError as e:
			speak.speak("Error logging into Bluesky: " + str(e))
			# Clear credentials
			self.prefs.bluesky_handle = ""
			self.prefs.bluesky_password = ""
			_exit_app()
		except Exception as e:
			speak.speak("Error connecting to Bluesky: " + str(e))
			_exit_app()

		# Set platform properties
		self.max_chars = 300  # Bluesky character limit
		self.default_visibility = 'public'  # Bluesky only has public posts

		# Initialize platform backend (pass raw profile, it converts internally)
		self._platform = BlueskyAccount(self.app, index, self.api, raw_profile, self.confpath, self.prefs)

		self._finish_init(index)

		# Create built-in timelines in user's preferred order
		self._create_builtin_timelines()

		# Restore saved user timelines and searches (no lists for Bluesky)
		# Avoid API calls during startup for speed
		for ut_entry in list(self.prefs.user_timelines):
			try:
				# Handle both string and dict entries (dict has username and optional filter)
				if isinstance(ut_entry, dict):
					username = ut_entry.get('username', '')
					user_filter = ut_entry.get('filter')
					filter_labels = {
						'posts_no_replies': 'Posts Only',
						'posts_with_media': 'Media',
						'posts_and_author_threads': 'Threads',
						'posts_with_video': 'Videos',
						'posts_no_boosts': 'No Boosts',
					}
					tl_name = username + "'s Timeline"
					if user_filter and user_filter in filter_labels:
						tl_name = f"{username}'s {filter_labels[user_filter]}"
					self.timelines.append(timeline.timeline(self, name=tl_name, type="user", data=ut_entry, user=None, silent=True))
				else:
					username = ut_entry
					self.timelines.append(timeline.timeline(self, name=username + "'s Timeline", type="user", data=username, user=None, silent=True))
			except:
				self.prefs.user_timelines.remove(ut_entry)
		for q in list(self.prefs.search_timelines):
			try:
				self.timelines.append(timeline.timeline(self, name=q + " Search", type="search", data=q, silent=True))
			except:
				self.prefs.search_timelines.remove(q)

		# Restore custom timelines (feeds for Bluesky)
		for ct in list(self.prefs.custom_timelines):
			try:
				tl_type = ct.get('type', '')
				tl_id = ct.get('id', '')
				tl_name = ct.get('name', 'Feed')
				if tl_type in ('feed', 'favourites', 'bookmarks'):
					self.timelines.append(timeline.timeline(self, name=tl_name, type=tl_type, data=tl_id, silent=True))
			except:
				self.prefs.custom_timelines.remove(ct)

		# No streaming for Bluesky
		self.stream_listener = None
		self.stream = None
		self._stream_started = False

		self._finish_timeline_init()

	def _finish_init(self, index):
		"""Common initialization after platform-specific setup."""
		import wx
		if self.app.currentAccount is None:
			self.app.currentAccount = self
			# Get display name - both platforms now use UniversalUser with acct
			acct = getattr(self.me, 'acct', str(self.me))
			# Use CallAfter for thread safety
			wx.CallAfter(main.window.SetLabel, acct + " - " + application.name + " " + application.version)

	def _finish_timeline_init(self):
		"""Finish timeline initialization (common to all platforms)."""
		import wx
		if self.app.currentAccount == self:
			# Use CallAfter for thread safety - must refresh timeline list before selecting
			wx.CallAfter(main.window.refreshTimelines)
			wx.CallAfter(main.window.list.SetSelection, 0)
			wx.CallAfter(main.window.on_list_change, None)
		# Track pending initial loads - streaming starts after all complete
		self._pending_initial_loads = len([t for t in self.timelines if t.initial and not t.hide])
		self._initial_loads_lock = threading.Lock()
		threading.Thread(target=timeline.timelineThread, args=[self,], daemon=True).start()

	def _on_timeline_initial_load_complete(self):
		"""Called when a timeline finishes its initial load. Starts streaming when all are done."""
		with self._initial_loads_lock:
			self._pending_initial_loads -= 1
			if self._pending_initial_loads <= 0 and self.app.prefs.streaming:
				# All timelines loaded, start streaming
				self.start_stream()

	def get_timeline_by_type(self, timeline_type):
		"""Find a timeline by its type (e.g., 'home', 'notifications', 'mentions').

		Returns the first matching timeline, or None if not found.
		"""
		for tl in self.timelines:
			if tl.type == timeline_type:
				return tl
		return None

	def get_first_timeline(self):
		"""Get the first timeline (fallback when current timeline is removed).

		Returns the first timeline in the list, or None if no timelines exist.
		"""
		return self.timelines[0] if self.timelines else None

	def _create_builtin_timelines(self):
		"""Create built-in timelines in the user's preferred order.

		Respects the timeline_order preference if set, otherwise uses default order.
		"""
		# Define available built-in timelines for each platform
		if self.prefs.platform_type == "bluesky":
			available = {
				"home": ("Home", "home", None, None),
				"notifications": ("Notifications", "notifications", None, None),
				"mentions": ("Mentions", "mentions", None, None),
				"sent": ("Sent", "user", self.me.acct, self.me),
			}
			default_order = ["home", "notifications", "mentions", "sent"]
		else:
			# Mastodon
			available = {
				"home": ("Home", "home", None, None),
				"notifications": ("Notifications", "notifications", None, None),
				"mentions": ("Mentions", "mentions", None, None),
				"conversations": ("Conversations", "conversations", None, None),
				"sent": ("Sent", "user", self.me.acct, self.me),
			}
			default_order = ["home", "notifications", "mentions", "conversations", "sent"]

		# Use saved order if available, otherwise use default
		order = self.prefs.timeline_order if self.prefs.timeline_order else default_order

		# Ensure all available timelines are included (in case new ones were added)
		for tl_key in default_order:
			if tl_key not in order:
				order.append(tl_key)

		# Create timelines in the specified order
		for tl_key in order:
			if tl_key in available:
				name, tl_type, data, user = available[tl_key]
				timeline.add(self, name, tl_type, data, user)

	def start_stream(self):
		# Bluesky doesn't support streaming
		if self.prefs.platform_type == "bluesky":
			return

		# Use lock to prevent race condition where multiple threads try to start stream
		with self._stream_lock:
			# Check if stream is already running or starting
			if hasattr(self, '_stream_started') and self._stream_started:
				return

			if self.stream_thread is not None and self.stream_thread.is_alive():
				return  # Stream already running

			# Mark as started before creating thread
			self._stream_started = True

			self.stream_thread = threading.Thread(
				target=self._run_stream,
				daemon=True
			)
			self.stream_thread.start()

	def _run_stream(self):
		# Bluesky doesn't support streaming
		if self.prefs.platform_type == "bluesky":
			return

		import time
		import threading
		import requests
		import json
		thread_id = threading.current_thread().ident
		consecutive_errors = 0
		base_delay = 5  # seconds
		max_delay = 300  # 5 minutes max

		# Create listener once
		self.stream_listener = streaming.MastodonStreamListener(self)

		while True:
			try:
				# Ensure API is available before attempting stream
				if not hasattr(self, 'api') or self.api is None:
					time.sleep(5)
					continue

				# Check if we're still the active stream thread
				if self.stream_thread is None or self.stream_thread.ident != thread_id:
					return

				# Use our own SSE implementation instead of Mastodon.py's buggy one
				stream_url = f"{self.prefs.instance_url}/api/v1/streaming/user"
				headers = {
					"Authorization": f"Bearer {self.prefs.access_token}",
					"Accept": "text/event-stream",
				}

				with requests.get(stream_url, headers=headers, stream=True, timeout=300) as response:
					response.raise_for_status()
					consecutive_errors = 0  # Reset on successful connect

					event_type = None
					data_lines = []

					for line in response.iter_lines():
						# Check if we should stop
						if self.stream_thread is None or self.stream_thread.ident != thread_id:
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
									self._handle_stream_event(event_type, data)
								except json.JSONDecodeError:
									pass  # Ignore malformed JSON
							event_type = None
							data_lines = []

			except requests.exceptions.Timeout:
				time.sleep(2)
				continue
			except Exception as e:
				error_str = str(e).lower()

				transient_errors = [
					"connection", "timeout", "reset", "refused", "unreachable",
					"network", "socket", "eof", "broken pipe", "ssl", "certificate"
				]
				if any(err in error_str for err in transient_errors):
					time.sleep(2)
					continue

				consecutive_errors += 1
				if consecutive_errors >= 5:
					speak.speak("Stream connection lost")
					consecutive_errors = 0

				delay = min(base_delay * (2 ** (consecutive_errors - 1)), max_delay)
				time.sleep(delay)

	def _handle_stream_event(self, event_type, data):
		"""Handle a streaming event by dispatching to the listener."""
		# Guard: check listener exists
		if self.stream_listener is None:
			return

		from mastodon import AttribAccessDict

		def convert_to_attrib_dict(obj):
			"""Recursively convert dicts to AttribAccessDict for attribute access."""
			if isinstance(obj, dict):
				converted = {k: convert_to_attrib_dict(v) for k, v in obj.items()}
				return AttribAccessDict(**converted)
			elif isinstance(obj, list):
				return [convert_to_attrib_dict(item) for item in obj]
			return obj

		try:
			if event_type == 'update':
				status = convert_to_attrib_dict(data)
				self.stream_listener.on_update(status)
			elif event_type == 'notification':
				notification = convert_to_attrib_dict(data)
				self.stream_listener.on_notification(notification)
			elif event_type == 'delete':
				self.stream_listener.on_delete(data)
			elif event_type == 'status.update':
				status = convert_to_attrib_dict(data)
				self.stream_listener.on_status_update(status)
			elif event_type == 'conversation':
				conversation = convert_to_attrib_dict(data)
				self.stream_listener.on_conversation(conversation)
		except Exception:
			pass  # Silently ignore stream handler errors

	def followers(self, id):
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.get_followers(id, limit=80, max_pages=self.app.prefs.user_limit)

		count = 0
		followers = []
		try:
			page = self.api.account_followers(id=id, limit=80)
		except MastodonError as err:
			self.app.handle_error(err, "followers")
			return []

		followers.extend(page)
		count += 1

		while page and count < self.app.prefs.user_limit:
			try:
				page = self.api.fetch_next(page)
				if page:
					followers.extend(page)
					count += 1
			except MastodonError as err:
				self.app.handle_error(err, "followers")
				break

		return followers

	def following(self, id):
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.get_following(id, limit=80, max_pages=self.app.prefs.user_limit)

		count = 0
		following = []
		try:
			page = self.api.account_following(id=id, limit=80)
		except MastodonError as err:
			self.app.handle_error(err, "following")
			return []

		following.extend(page)
		count += 1

		while page and count < self.app.prefs.user_limit:
			try:
				page = self.api.fetch_next(page)
				if page:
					following.extend(page)
					count += 1
			except MastodonError as err:
				self.app.handle_error(err, "following")
				break

		return following


	def mutual_following(self):
		followers = self.followers(self.me.id)
		following = self.following(self.me.id)
		users = []
		follower_ids = {f.id for f in followers}
		for i in following:
			if i.id in follower_ids:
				users.append(i)
		return users

	def not_following(self):
		followers = self.followers(self.me.id)
		following = self.following(self.me.id)
		following_ids = {f.id for f in following}
		users = []
		for i in followers:
			if i.id not in following_ids:
				users.append(i)
		return users

	def not_following_me(self):
		followers = self.followers(self.me.id)
		following = self.following(self.me.id)
		follower_ids = {f.id for f in followers}
		users = []
		for i in following:
			if i.id not in follower_ids:
				users.append(i)
		return users

	def havent_posted(self):
		following = self.following(self.me.id)
		users = []
		for i in following:
			if hasattr(i, "last_status_at") and i.last_status_at:
				if i.last_status_at.year < datetime.datetime.now().year - 1:
					users.append(i)
		return users


	def list_timelines(self, hidden=False):
		tl = []
		for i in self.timelines:
			if i.hide == hidden:
				tl.append(i)
		return tl

	def post(self, text, id=None, visibility=None, spoiler_text=None, **kwargs):
		"""Post a new status or reply"""
		try:
			# Use platform backend if available
			if hasattr(self, '_platform') and self._platform:
				return self._platform.post(
					text=text,
					reply_to_id=id,
					visibility=visibility,
					spoiler_text=spoiler_text,
					**kwargs
				)

			if visibility is None:
				visibility = self.default_visibility

			post_kwargs = {
				'status': text,
				'visibility': visibility
			}

			if spoiler_text:
				post_kwargs['spoiler_text'] = spoiler_text

			if id is not None:
				post_kwargs['in_reply_to_id'] = id

			# Merge any additional kwargs
			post_kwargs.update(kwargs)

			return self.api.status_post(**post_kwargs)
		except Exception as e:
			speak.speak(str(e))
			return False


	def boost(self, id):
		"""Boost (reblog) a status"""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.boost(id)
		self.api.status_reblog(id=id)

	def unboost(self, id):
		"""Unboost (unreblog) a status"""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.unboost(id)
		self.api.status_unreblog(id=id)

	def quote(self, status, text, visibility=None, language=None):
		"""Quote a status - try native quote, fallback to URL"""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.quote(status, text, visibility=visibility, language=language)

		if visibility is None:
			visibility = self.default_visibility

		status_id = str(status.id)
		result = None
		quote_succeeded = False

		# Method 1: Try native Mastodon 4.5+ quoting via direct API call
		try:
			params = {
				'status': text,
				'visibility': visibility,
				'quoted_status_id': status_id
			}
			if language:
				params['language'] = language
			result = self.api._Mastodon__api_request('POST', '/api/v1/statuses', params)
			# Verify the quote was actually attached
			if result and ('quote' in result or 'quote_id' in result):
				quote_succeeded = True
		except:
			pass

		# Method 2: Try Mastodon.py's quote_id (for Fedibird/compatible servers)
		if not quote_succeeded:
			result = None
			try:
				result = self.api.status_post(status=text, quote_id=status_id, visibility=visibility, language=language)
				if result and (hasattr(result, 'quote') and result.quote):
					quote_succeeded = True
			except:
				pass

		# Method 3: Fallback - include link to original post
		if not quote_succeeded:
			original_url = getattr(status, 'url', None)
			if not original_url:
				original_url = f"{self.prefs.instance_url}/@{status.account.acct}/{status_id}"
			result = self.api.status_post(status=f"{text}\n\n{original_url}", visibility=visibility, language=language)

		return result

	def edit(self, status_id, text, visibility=None, spoiler_text=None, media_ids=None, language=None, **kwargs):
		"""Edit an existing status"""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.edit(
				status_id=status_id,
				text=text,
				visibility=visibility,
				spoiler_text=spoiler_text,
				media_ids=media_ids,
				language=language,
				**kwargs
			)

		edit_kwargs = {
			'id': status_id,
			'status': text,
		}
		if spoiler_text:
			edit_kwargs['spoiler_text'] = spoiler_text
		if media_ids:
			edit_kwargs['media_ids'] = media_ids
		# Note: language is not supported by Mastodon's status_update API

		return self.api.status_update(**edit_kwargs)

	def favourite(self, id):
		"""Favourite a status"""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.favourite(id)
		self.api.status_favourite(id=id)

	def unfavourite(self, id):
		"""Unfavourite a status"""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.unfavourite(id)
		self.api.status_unfavourite(id=id)

	def follow(self, user_id):
		"""Follow a user by ID or acct"""
		if isinstance(user_id, str) and not user_id.isdigit():
			# It's an acct/username, look up the user
			user = self.app.lookup_user_name(self, user_id.lstrip('@'))
			if user and user != -1:
				user_id = user.id
			else:
				speak.speak("User not found")
				return
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.follow(user_id)
		self.api.account_follow(id=user_id)

	def unfollow(self, user_id):
		"""Unfollow a user by ID or acct"""
		if isinstance(user_id, str) and not user_id.isdigit():
			user = self.app.lookup_user_name(self, user_id.lstrip('@'))
			if user and user != -1:
				user_id = user.id
			else:
				speak.speak("User not found")
				return
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.unfollow(user_id)
		self.api.account_unfollow(id=user_id)

	def block(self, user_id):
		"""Block a user by ID or acct"""
		if isinstance(user_id, str) and not user_id.isdigit():
			user = self.app.lookup_user_name(self, user_id.lstrip('@'))
			if user and user != -1:
				user_id = user.id
			else:
				speak.speak("User not found")
				return
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.block(user_id)
		self.api.account_block(id=user_id)

	def unblock(self, user_id):
		"""Unblock a user by ID or acct"""
		if isinstance(user_id, str) and not user_id.isdigit():
			user = self.app.lookup_user_name(self, user_id.lstrip('@'))
			if user and user != -1:
				user_id = user.id
			else:
				speak.speak("User not found")
				return
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.unblock(user_id)
		self.api.account_unblock(id=user_id)

	def mute(self, user_id):
		"""Mute a user by ID or acct"""
		if isinstance(user_id, str) and not user_id.isdigit():
			user = self.app.lookup_user_name(self, user_id.lstrip('@'))
			if user and user != -1:
				user_id = user.id
			else:
				speak.speak("User not found")
				return
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.mute(user_id)
		self.api.account_mute(id=user_id)

	def unmute(self, user_id):
		"""Unmute a user by ID or acct"""
		if isinstance(user_id, str) and not user_id.isdigit():
			user = self.app.lookup_user_name(self, user_id.lstrip('@'))
			if user and user != -1:
				user_id = user.id
			else:
				speak.speak("User not found")
				return
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.unmute(user_id)
		self.api.account_unmute(id=user_id)

	def get_user(self, user_id):
		"""Get user by ID."""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.get_user(user_id)
		return self.api.account(id=user_id)

	def search_users(self, query, limit=40):
		"""Search for users."""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.search_users(query, limit=limit)
		return self.api.account_search(q=query, limit=limit)

	def accept_follow_request(self, user_id):
		"""Accept a follow request from a user."""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.accept_follow_request(user_id)
		self.api.follow_request_authorize(id=user_id)

	def reject_follow_request(self, user_id):
		"""Reject a follow request from a user."""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.reject_follow_request(user_id)
		self.api.follow_request_reject(id=user_id)

	def mute_conversation(self, status_id):
		"""Mute a conversation (stop notifications for replies)."""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.mute_conversation(status_id)
		self.api.status_mute(id=status_id)
		return True

	def unmute_conversation(self, status_id):
		"""Unmute a conversation (resume notifications for replies)."""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.unmute_conversation(status_id)
		self.api.status_unmute(id=status_id)
		return True

	def UpdateProfile(self, display_name, note, fields=None):
		"""Update profile information"""
		kwargs = {}
		if display_name:
			kwargs['display_name'] = display_name
		if note:
			kwargs['note'] = note
		if fields:
			kwargs['fields'] = fields
		self.api.account_update_credentials(**kwargs)

	@property
	def user_cache(self) -> UserCache:
		"""Get the per-account user cache."""
		return self._platform.user_cache

	def _migrate_user_cache(self):
		"""Migrate global user cache to per-account cache on first run."""
		# Check if we've already migrated
		if self.prefs.get("user_cache_migrated", False):
			return

		# If there are global users, copy them to this account's cache
		if hasattr(self.app, 'users') and self.app.users:
			from platforms.mastodon.models import mastodon_user_to_universal
			for user in self.app.users:
				try:
					universal_user = mastodon_user_to_universal(user)
					if universal_user:
						self._platform.user_cache.add_user(universal_user)
				except:
					pass
			self._platform.user_cache.save()

		self.prefs.user_cache_migrated = True

	def get_mentions(self, limit=40, **kwargs):
		"""Get mentions as statuses (delegates to platform backend)."""
		return self._platform.get_mentions(limit=limit, **kwargs)

	def get_home_timeline(self, limit=40, **kwargs):
		"""Get home timeline (delegates to platform backend)."""
		return self._platform.get_home_timeline(limit=limit, **kwargs)

	def get_notifications(self, limit=40, **kwargs):
		"""Get notifications (delegates to platform backend)."""
		return self._platform.get_notifications(limit=limit, **kwargs)

	def supports_feature(self, feature: str) -> bool:
		"""Check if this platform supports a feature."""
		return self._platform.supports_feature(feature)

	def cleanup(self):
		"""Clean up resources when account is removed or app is closing."""
		if self._platform:
			self._platform.close()
