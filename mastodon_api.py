import datetime
from mastodon import Mastodon, MastodonError
import streaming
import application
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

from models import UserCache
from platforms.mastodon import MastodonAccount


class mastodon(object):
	"""Multi-platform account wrapper. Despite the name, supports both Mastodon and Bluesky."""

	def __init__(self, app, index):
		self.app = app
		self.stream_thread = None
		self.ready = False
		self.timelines = []
		self.currentTimeline = None
		self.currentIndex = 0
		self.currentStatus = None
		self.confpath = ""
		# Initialize streaming-related attributes early
		self._pending_initial_loads = 0
		self._initial_loads_lock = threading.Lock()
		self.stream_listener = None
		self.stream = None
		self.prefs = config.Config(name="FastSM/account"+str(index), autosave=True)
		self.confpath = self.prefs._user_config_home+"/FastSM/account"+str(index)

		# Platform backend (initialized after authentication)
		self._platform = None

		# Check platform type - this determines which auth flow to use
		self.prefs.platform_type = self.prefs.get("platform_type", "")

		# Legacy prefs (shared across platforms)
		self.prefs.user_timelines = self.prefs.get("user_timelines", [])
		self.prefs.list_timelines = self.prefs.get("list_timelines", [])
		self.prefs.search_timelines = self.prefs.get("search_timelines", [])
		self.prefs.custom_timelines = self.prefs.get("custom_timelines", [])  # [{type, id, name}, ...]
		self.prefs.instance_timelines = self.prefs.get("instance_timelines", [])  # [{url, name}, ...]

		# Remote API instances for instance timelines (unauthenticated)
		self.remote_apis = {}
		self.prefs.footer = self.prefs.get("footer", "")
		self.prefs.soundpack = self.prefs.get("soundpack", "default")
		self.prefs.soundpan = self.prefs.get("soundpan", 0)

		# If no platform type set, check if this is a legacy Mastodon account
		if self.prefs.platform_type == "":
			# Check for existing Mastodon credentials (legacy account migration)
			existing_instance = self.prefs.get("instance_url", "")
			existing_token = self.prefs.get("access_token", "")
			if existing_instance != "" or existing_token != "":
				# This is an existing Mastodon account - set type automatically
				self.prefs.platform_type = "mastodon"
			else:
				# Truly new account - ask user which platform
				selected = select_platform(main.window)
				if selected is None:
					sys.exit()
				self.prefs.platform_type = selected

		# Initialize based on platform type
		if self.prefs.platform_type == "bluesky":
			self._init_bluesky(index)
		else:
			# Default to Mastodon (including legacy accounts)
			self.prefs.platform_type = "mastodon"
			self._init_mastodon(index)

	def _init_mastodon(self, index):
		"""Initialize Mastodon account."""
		# Mastodon-specific config
		self.prefs.instance_url = self.prefs.get("instance_url", "")
		self.prefs.access_token = self.prefs.get("access_token", "")
		self.prefs.client_id = self.prefs.get("client_id", "")
		self.prefs.client_secret = self.prefs.get("client_secret", "")

		# Get instance URL if not set
		if self.prefs.instance_url == "":
			self.prefs.instance_url = ask(caption="Mastodon Instance",
				message="Enter your Mastodon instance URL (e.g., mastodon.social, fosstodon.org):")
			if self.prefs.instance_url is None:
				sys.exit()
			# Ensure https://
			if not self.prefs.instance_url.startswith("https://") and not self.prefs.instance_url.startswith("http://"):
				self.prefs.instance_url = "https://" + self.prefs.instance_url

		# Register app if needed
		if self.prefs.client_id == "" or self.prefs.client_secret == "":
			try:
				client_id, client_secret = Mastodon.create_app(
					"FastSM",
					scopes=['read', 'write', 'follow', 'push'],
					api_base_url=self.prefs.instance_url
				)
				self.prefs.client_id = client_id
				self.prefs.client_secret = client_secret
			except MastodonError as e:
				speak.speak("Error registering app: " + str(e))
				sys.exit()

		# Authenticate if needed
		if self.prefs.access_token == "":
			try:
				temp_api = Mastodon(
					client_id=self.prefs.client_id,
					client_secret=self.prefs.client_secret,
					api_base_url=self.prefs.instance_url
				)
				auth_url = temp_api.auth_request_url(scopes=['read', 'write', 'follow', 'push'])
				if platform.system() != "Darwin":
					webbrowser.open(auth_url)
				else:
					os.system("open " + auth_url)

				auth_code = ask(caption="Authorization Code",
					message="Enter the authorization code from your browser:")
				if auth_code is None:
					sys.exit()

				access_token = temp_api.log_in(code=auth_code, scopes=['read', 'write', 'follow', 'push'])
				self.prefs.access_token = access_token
			except MastodonError as e:
				speak.speak("Error during authentication: " + str(e))
				sys.exit()

		# Initialize the API
		self.api = Mastodon(
			client_id=self.prefs.client_id,
			client_secret=self.prefs.client_secret,
			access_token=self.prefs.access_token,
			api_base_url=self.prefs.instance_url
		)

		# Verify credentials and get user info
		try:
			self.me = self.api.account_verify_credentials()
		except MastodonError as e:
			speak.speak("Error verifying credentials: " + str(e))
			# Clear tokens and try again
			self.prefs.access_token = ""
			sys.exit()

		# Get instance info for character limit
		try:
			instance_info = self.api.instance()
			if hasattr(instance_info, 'configuration') and hasattr(instance_info.configuration, 'statuses'):
				self.max_chars = instance_info.configuration.statuses.max_characters
			else:
				self.max_chars = 500
			# Get default visibility
			self.default_visibility = getattr(self.me, 'source', {}).get('privacy', 'public')
		except:
			self.max_chars = 500
			self.default_visibility = 'public'

		# Initialize platform backend with user cache
		self._platform = MastodonAccount(self.app, index, self.api, self.me, self.confpath)

		# Migrate global user cache to per-account if this is the first run
		self._migrate_user_cache()

		self._finish_init(index)

		# Create default timelines for Mastodon
		timeline.add(self, "Home", "home")
		timeline.add(self, "Notifications", "notifications")
		timeline.add(self, "Mentions", "mentions")
		timeline.add(self, "Conversations", "conversations")
		timeline.add(self, "Favourites", "favourites")
		timeline.add(self, "Sent", "user", self.me.acct, self.me)

		# Restore saved timelines (avoid API calls during startup for speed)
		for username in list(self.prefs.user_timelines):
			try:
				# Create timeline without API lookup - user info will be fetched when timeline loads
				self.timelines.append(timeline.timeline(self, name=username + "'s Timeline", type="user", data=username, user=None, silent=True))
			except:
				self.prefs.user_timelines.remove(username)
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

		# Restore custom timelines (local, federated)
		for ct in list(self.prefs.custom_timelines):
			try:
				tl_type = ct.get('type', '')
				tl_id = ct.get('id', '')
				tl_name = ct.get('name', tl_type.title())
				if tl_type in ('local', 'federated'):
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

		self.stream_listener = None
		self.stream = None
		# Don't start streaming yet - wait for initial timeline loads to complete
		# Streaming will be started by _check_initial_loads_complete()

		self._finish_timeline_init()

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
				sys.exit()
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
			sys.exit()
		except Exception as e:
			speak.speak("Error connecting to Bluesky: " + str(e))
			sys.exit()

		# Set platform properties
		self.max_chars = 300  # Bluesky character limit
		self.default_visibility = 'public'  # Bluesky only has public posts

		# Initialize platform backend (pass raw profile, it converts internally)
		self._platform = BlueskyAccount(self.app, index, self.api, raw_profile, self.confpath)

		self._finish_init(index)

		# Create default timelines for Bluesky (no conversations, lists)
		timeline.add(self, "Home", "home")
		timeline.add(self, "Notifications", "notifications")
		timeline.add(self, "Mentions", "mentions")
		# No conversations - Bluesky doesn't support DMs
		timeline.add(self, "Favourites", "favourites")
		timeline.add(self, "Sent", "user", self.me.acct, self.me)

		# Restore saved user timelines and searches (no lists for Bluesky)
		# Avoid API calls during startup for speed
		for username in list(self.prefs.user_timelines):
			try:
				self.timelines.append(timeline.timeline(self, name=username + "'s Timeline", type="user", data=username, user=None, silent=True))
			except:
				self.prefs.user_timelines.remove(username)
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
				if tl_type == 'feed':
					self.timelines.append(timeline.timeline(self, name=tl_name, type=tl_type, data=tl_id, silent=True))
			except:
				self.prefs.custom_timelines.remove(ct)

		# No streaming for Bluesky
		self.stream_listener = None
		self.stream = None

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
			# Use CallAfter for thread safety
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

	def start_stream(self):
		# Bluesky doesn't support streaming
		if self.prefs.platform_type == "bluesky":
			return

		if self.stream_listener is None:
			self.stream_listener = streaming.MastodonStreamListener(self)
			self.stream_thread = threading.Thread(
				target=self._run_stream,
				daemon=True
			)
			self.stream_thread.start()

	def _run_stream(self):
		# Bluesky doesn't support streaming
		if self.prefs.platform_type == "bluesky":
			return

		try:
			self.stream = self.api.stream_user(self.stream_listener, run_async=False, reconnect_async=True)
		except Exception as e:
			speak.speak("Stream error: " + str(e))

	def followers(self, id):
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.get_followers(id, limit=80)

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
			return self._platform.get_following(id, limit=80)

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

	# Alias for backwards compatibility
	def friends(self, id):
		return self.following(id)

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

	# Alias for backwards compatibility
	def havent_tweeted(self):
		return self.havent_posted()

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

	# Alias for backwards compatibility
	def tweet(self, text, id=None, **kwargs):
		return self.post(text, id, **kwargs)

	def boost(self, id):
		"""Boost (reblog) a status"""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.boost(id)
		self.api.status_reblog(id=id)

	# Alias for backwards compatibility
	def retweet(self, id):
		self.boost(id)

	def quote(self, status, text, visibility=None):
		"""Quote a status - try native quote, fallback to URL"""
		try:
			# Use platform backend if available
			if hasattr(self, '_platform') and self._platform:
				return self._platform.quote(status, text, visibility=visibility)

			if visibility is None:
				visibility = self.default_visibility
			# Try native quote (Mastodon 4.0+)
			return self.api.status_post(status=text, quote_id=status.id, visibility=visibility)
		except:
			# Fallback: include link to original post
			original_url = getattr(status, 'url', None)
			if not original_url:
				original_url = f"{self.prefs.instance_url}/@{status.account.acct}/{status.id}"
			return self.api.status_post(status=f"{text}\n\n{original_url}", visibility=visibility)

	def edit(self, status_id, text, visibility=None, spoiler_text=None, media_ids=None, **kwargs):
		"""Edit an existing status"""
		# Use platform backend if available
		if hasattr(self, '_platform') and self._platform:
			return self._platform.edit(
				status_id=status_id,
				text=text,
				visibility=visibility,
				spoiler_text=spoiler_text,
				media_ids=media_ids,
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

	# Aliases for backwards compatibility
	def like(self, id):
		self.favourite(id)

	def unlike(self, id):
		self.unfavourite(id)

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
