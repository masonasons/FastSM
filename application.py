import sys
import platform
import os
import pickle
import threading
import zipfile
import html
import json
import datetime
import time
import re
import requests
import webbrowser
import config
import wx
from version import APP_NAME, APP_SHORTNAME, APP_VERSION, APP_AUTHOR

shortname = APP_SHORTNAME
name = APP_NAME
version = APP_VERSION
author = APP_AUTHOR

# Regex patterns
url_re = re.compile(r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?]))")
url_re2 = re.compile(r"(?:\w+://|www\.)[^ ,.?!#%=+][^ ]*")
bad_chars = "'\\.,[](){}:;\""
html_tag_re = re.compile(r'<[^>]+>')


class StatusWrapper:
	"""Wrapper class to add text attribute to immutable Mastodon status objects"""
	def __init__(self, status, text=""):
		self._status = status
		self.text = text

	def __getattr__(self, name):
		if name in ('_status', 'text'):
			return object.__getattribute__(self, name)
		return getattr(self._status, name)

	def __hasattr__(self, name):
		if name in ('_status', 'text'):
			return True
		return hasattr(self._status, name)


class NotificationWrapper:
	"""Wrapper class to add type label and text to notification objects for templating"""
	def __init__(self, notification, type_label="", text=""):
		self._notification = notification
		self.type = type_label  # Human-readable type label like "followed you"
		self.text = text  # Status text if notification has associated status

	def __getattr__(self, name):
		if name in ('_notification', 'type', 'text'):
			return object.__getattribute__(self, name)
		return getattr(self._notification, name)

	def __hasattr__(self, name):
		if name in ('_notification', 'type', 'text'):
			return True
		return hasattr(self._notification, name)


class dict_obj:
	def __init__(self, dict1):
		self.__dict__.update(dict1)


class Application:
	"""Main application class that holds all global state and utility methods."""

	_instance = None

	def __init__(self):
		self.accounts = []
		self.prefs = None
		self.users = []
		self.unknown_users = []
		self.confpath = ""
		self.errors = []
		self.currentAccount = None
		self.timeline_settings = []
		self._initialized = False

	@classmethod
	def get_instance(cls):
		"""Get the singleton application instance."""
		if cls._instance is None:
			cls._instance = cls()
		return cls._instance

	def load(self):
		"""Initialize the application - load preferences and accounts."""
		if self._initialized:
			return

		import sound
		from GUI import main
		import mastodon_api as t
		import timeline

		self.prefs = config.Config(name="FastSM", autosave=True)
		# In portable mode, userdata folder is already app-specific, don't add /FastSM
		if config.is_portable_mode():
			self.confpath = self.prefs._user_config_home
		else:
			self.confpath = self.prefs._user_config_home + "/FastSM"

		# Redirect stderr to errors.log in config directory (not app directory)
		# This is especially important for installed versions where the app directory
		# (Program Files) is write-protected
		if getattr(sys, 'frozen', False):
			try:
				# Ensure config directory exists before writing errors.log
				if not os.path.exists(self.confpath):
					os.makedirs(self.confpath)
				f = open(self.confpath + "/errors.log", "a")
				sys.stderr = f
			except Exception as e:
				# Log to console if we can't set up error logging
				print(f"Warning: Could not set up error logging: {e}", file=sys.__stderr__)

		# Load preferences with defaults
		self.prefs.timelinecache_version = self.prefs.get("timelinecache_version", 1)
		if self.prefs.timelinecache_version == 1:
			if os.path.exists(self.confpath + "/timelinecache"):
				os.remove(self.confpath + "/timelinecache")
			self.prefs.timelinecache_version = 2

		self.prefs.user_reversed = self.prefs.get("user_reversed", False)
		self.prefs.user_limit = self.prefs.get("user_limit", 4)
		self.prefs.postTemplate = self.prefs.get("postTemplate", "$account.display_name$ (@$account.acct$): $text$ $created_at$")
		self.prefs.conversationTemplate = self.prefs.get("conversationTemplate", "$account.display_name$: $text$ $created_at$")
		self.prefs.copyTemplate = self.prefs.get("copyTemplate", "$account.display_name$ (@$account.acct$): $text$")
		self.prefs.boostTemplate = self.prefs.get("boostTemplate", "$account.display_name$ boosted $reblog.account.display_name$: $text$ $created_at$")
		self.prefs.quoteTemplate = self.prefs.get("quoteTemplate", "Quoting $account.display_name$ (@$account.acct$): $text$")
		self.prefs.notificationTemplate = self.prefs.get("notificationTemplate", "$account.display_name$ (@$account.acct$) $type$: $text$ $created_at$")
		self.prefs.messageTemplate = self.prefs.get("messageTemplate", "$account.display_name$: $text$ $created_at$")
		self.prefs.userTemplate = self.prefs.get("userTemplate", "$display_name$ (@$acct$): $followers_count$ followers, $following_count$ following, $statuses_count$ posts. Bio: $note$")
		self.prefs.accounts = self.prefs.get("accounts", 1)
		self.prefs.errors = self.prefs.get("errors", True)
		self.prefs.streaming = self.prefs.get("streaming", False)
		self.prefs.invisible = self.prefs.get("invisible", False)
		self.prefs.invisible_sync = self.prefs.get("invisible_sync", True)
		self.prefs.update_time = self.prefs.get("update_time", 2)
		self.prefs.media_volume = self.prefs.get("media_volume", self.prefs.get("volume", 1.0))  # Media player volume (migrates from old volume setting)
		self.prefs.auto_open_audio_player = self.prefs.get("auto_open_audio_player", False)  # Auto-open audio player when media starts
		self.prefs.stop_audio_on_close = self.prefs.get("stop_audio_on_close", False)  # Stop audio when audio player closes
		self.prefs.ctrl_enter_to_send = self.prefs.get("ctrl_enter_to_send", False)  # Use Ctrl+Enter to send posts instead of Enter
		self.prefs.count = self.prefs.get("count", 40)
		self.prefs.repeat = self.prefs.get("repeat", False)
		self.prefs.demojify = self.prefs.get("demojify", False)
		self.prefs.demojify_post = self.prefs.get("demojify_post", False)
		self.prefs.include_media_descriptions = self.prefs.get("include_media_descriptions", True)
		self.prefs.include_link_preview = self.prefs.get("include_link_preview", True)
		self.prefs.max_usernames_display = self.prefs.get("max_usernames_display", 0)  # 0 = show all
		self.prefs.position = self.prefs.get("position", True)
		self.prefs.chars_sent = self.prefs.get("chars_sent", 0)
		self.prefs.posts_sent = self.prefs.get("posts_sent", 0)
		self.prefs.replies_sent = self.prefs.get("replies_sent", 0)
		self.prefs.quotes_sent = self.prefs.get("quotes_sent", 0)
		self.prefs.boosts_sent = self.prefs.get("boosts_sent", 0)
		self.prefs.favourites_sent = self.prefs.get("favourites_sent", 0)
		self.prefs.statuses_received = self.prefs.get("statuses_received", 0)
		self.prefs.ask_dismiss = self.prefs.get("ask_dismiss", True)
		self.prefs.reversed = self.prefs.get("reversed", False)
		self.prefs.window_shown = self.prefs.get("window_shown", True)
		self.prefs.autoOpenSingleURL = self.prefs.get("autoOpenSingleURL", False)
		self.prefs.use24HourTime = self.prefs.get("use24HourTime", False)
		self.prefs.fetch_pages = self.prefs.get("fetch_pages", 1)  # Number of API calls to make when loading timelines
		self.prefs.single_api_on_startup = self.prefs.get("single_api_on_startup", False)  # Use only one API call on initial timeline loads
		self.prefs.check_for_updates = self.prefs.get("check_for_updates", True)  # Check for updates on startup
		self.prefs.load_all_previous = self.prefs.get("load_all_previous", False)  # Keep loading previous until timeline is fully loaded
		self.prefs.earcon_audio = self.prefs.get("earcon_audio", True)
		self.prefs.earcon_top = self.prefs.get("earcon_top", False)
		self.prefs.earcon_mention = self.prefs.get("earcon_mention", True)
		self.prefs.wrap = self.prefs.get("wrap", False)
		# Content warning handling: 'hide' = show CW only, 'show' = show CW + text, 'ignore' = show text only
		self.prefs.cw_mode = self.prefs.get("cw_mode", "hide")
		# Keymap for invisible interface (default inherits from default.keymap)
		self.prefs.keymap = self.prefs.get("keymap", "default")
		# Sync home timeline position with Mastodon marker API
		self.prefs.sync_timeline_position = self.prefs.get("sync_timeline_position", False)
		# Dark mode: 'off', 'on', or 'auto' (follow system)
		self.prefs.dark_mode = self.prefs.get("dark_mode", "off")
		# Debug logging: write verbose logs to fastsm.log
		self.prefs.debug_logging = self.prefs.get("debug_logging", False)
		# Confirmation settings for menu/hotkey actions
		self.prefs.confirm_boost = self.prefs.get("confirm_boost", False)
		self.prefs.confirm_unboost = self.prefs.get("confirm_unboost", False)
		self.prefs.confirm_favorite = self.prefs.get("confirm_favorite", False)
		self.prefs.confirm_unfavorite = self.prefs.get("confirm_unfavorite", False)
		self.prefs.confirm_follow = self.prefs.get("confirm_follow", False)
		self.prefs.confirm_unfollow = self.prefs.get("confirm_unfollow", False)
		self.prefs.confirm_block = self.prefs.get("confirm_block", True)
		self.prefs.confirm_unblock = self.prefs.get("confirm_unblock", True)
		self.prefs.confirm_mute = self.prefs.get("confirm_mute", False)
		self.prefs.confirm_unmute = self.prefs.get("confirm_unmute", False)
		self.prefs.confirm_delete = self.prefs.get("confirm_delete", False)
		self.prefs.confirm_bookmark = self.prefs.get("confirm_bookmark", False)
		self.prefs.confirm_unbookmark = self.prefs.get("confirm_unbookmark", False)
		# AI image description settings
		self.prefs.ai_service = self.prefs.get("ai_service", "none")  # 'none', 'openai', or 'gemini'
		self.prefs.openai_api_key = self.prefs.get("openai_api_key", "")
		self.prefs.openai_model = self.prefs.get("openai_model", "gpt-4o-mini")
		self.prefs.gemini_api_key = self.prefs.get("gemini_api_key", "")
		self.prefs.gemini_model = self.prefs.get("gemini_model", "gemini-2.0-flash")
		self.prefs.ai_image_prompt = self.prefs.get("ai_image_prompt", "Describe this image in detail for someone who cannot see it. Include information about the subjects, setting, colors, and any text visible in the image.")

		# yt-dlp path for YouTube/etc URL extraction (empty = use bundled or system)
		self.prefs.ytdlp_path = self.prefs.get("ytdlp_path", "")
		# yt-dlp cookies file for age-restricted/private videos
		self.prefs.ytdlp_cookies = self.prefs.get("ytdlp_cookies", "")
		# Deno path for yt-dlp extractors that need it
		self.prefs.deno_path = self.prefs.get("deno_path", "")
		# Whether we've already asked about Windows 11 keymap
		self.prefs.win11_keymap_asked = self.prefs.get("win11_keymap_asked", False)
		# Audio output device index (1 = default device in BASS)
		self.prefs.audio_output_device = self.prefs.get("audio_output_device", 1)

		# Timeline caching settings
		self.prefs.timeline_cache_enabled = self.prefs.get("timeline_cache_enabled", True)  # Enable timeline caching for fast startup
		self.prefs.timeline_cache_limit = self.prefs.get("timeline_cache_limit", 1000)  # Max items to cache per timeline

		# Initialize audio output with selected device
		import sound
		try:
			sound.init_audio_output(self.prefs.audio_output_device)
		except Exception as e:
			# Audio init failure shouldn't crash the app
			print(f"Warning: Audio initialization failed: {e}", file=sys.stderr)

		if self.prefs.invisible:
			main.window.register_keys()

		# User cache is now in-memory only per-account, no global cache needed
		self.users = []

		self.load_timeline_settings()

		# Check for and handle any partially configured accounts
		self._handle_unfinished_accounts()

		# If all accounts were removed, ensure at least one will be created
		if self.prefs.accounts <= 0:
			self.prefs.accounts = 1

		# Load accounts - first one on main thread, rest in parallel if already configured
		if self.prefs.accounts > 0:
			# First account must be on main thread (handles auth dialogs, sets currentAccount)
			self.add_session()

			# Load remaining accounts in parallel if more than one
			if self.prefs.accounts > 1:
				import concurrent.futures
				# Check which accounts are already configured (have credentials)
				parallelizable = []
				sequential = []
				for i in range(1, self.prefs.accounts):
					if self._is_account_configured(i):
						parallelizable.append(i)
					else:
						sequential.append(i)

				# Load configured accounts in parallel
				if parallelizable:
					with concurrent.futures.ThreadPoolExecutor(max_workers=len(parallelizable)) as executor:
						futures = [executor.submit(self._add_session_threaded, i) for i in parallelizable]
						concurrent.futures.wait(futures)

				# Load unconfigured accounts sequentially on main thread (need dialogs)
				for i in sequential:
					self.add_session(i)

		self._initialized = True

		# Check for updates on startup if enabled
		# Delay slightly to ensure main window is fully initialized on macOS
		if self.prefs.check_for_updates:
			def delayed_cfu():
				import time
				time.sleep(2)  # Wait for window to be fully ready
				self.cfu()
			threading.Thread(target=delayed_cfu, daemon=True).start()

	def add_session(self, index=None):
		"""Add a new account session."""
		import mastodon_api as t
		import wx
		if index is None:
			index = len(self.accounts)
		try:
			self.accounts.append(t.mastodon(self, index))
		except t.AccountSetupCancelled:
			# User cancelled account setup - exit gracefully if no accounts
			if len(self.accounts) == 0:
				wx.CallAfter(wx.Exit)
				return
			# Otherwise just skip this account

	def _is_account_configured(self, index):
		"""Check if an account has credentials saved (no dialogs needed)."""
		import config
		try:
			# In portable mode, don't add FastSM prefix (userdata is already app-specific)
			# Use save_on_exit=False to avoid overwriting real account prefs on exit
			if config.is_portable_mode():
				prefs = config.Config(name="account"+str(index), autosave=False, save_on_exit=False)
			else:
				prefs = config.Config(name="FastSM/account"+str(index), autosave=False, save_on_exit=False)
			platform_type = prefs.get("platform_type", "")

			if platform_type == "bluesky":
				# Bluesky needs handle and password
				return bool(prefs.get("bluesky_handle", "")) and bool(prefs.get("bluesky_password", ""))
			else:
				# Mastodon needs instance URL and access token
				return bool(prefs.get("instance_url", "")) and bool(prefs.get("access_token", ""))
		except:
			return False

	def _is_account_partially_configured(self, index):
		"""Check if an account has been started but not completed.
		Returns (is_partial, platform_type, details) tuple."""
		import config
		try:
			if config.is_portable_mode():
				prefs = config.Config(name="account"+str(index), autosave=False, save_on_exit=False)
			else:
				prefs = config.Config(name="FastSM/account"+str(index), autosave=False, save_on_exit=False)

			platform_type = prefs.get("platform_type", "")
			if not platform_type:
				return (False, None, None)

			if platform_type == "bluesky":
				handle = prefs.get("bluesky_handle", "")
				password = prefs.get("bluesky_password", "")
				if handle and password:
					return (False, None, None)  # Fully configured
				if handle or password:
					return (True, "bluesky", handle or "incomplete")
				# Just platform_type set, nothing else
				return (True, "bluesky", "setup not started")
			else:
				# Mastodon
				instance_url = prefs.get("instance_url", "")
				access_token = prefs.get("access_token", "")
				if instance_url and access_token:
					return (False, None, None)  # Fully configured
				if instance_url:
					return (True, "mastodon", instance_url)
				# Just platform_type set, nothing else
				return (True, "mastodon", "setup not started")
		except:
			return (False, None, None)

	def _handle_unfinished_accounts(self):
		"""Check for and handle any partially configured accounts on startup."""
		import wx
		import config
		import shutil
		import os

		unfinished = []
		for i in range(self.prefs.accounts):
			is_partial, platform_type, details = self._is_account_partially_configured(i)
			if is_partial:
				unfinished.append((i, platform_type, details))

		if not unfinished:
			return

		# Build message for user
		accounts_to_remove = []
		for index, platform_type, details in unfinished:
			msg = f"Account {index + 1} ({platform_type}) has incomplete setup"
			if details and details != "setup not started":
				msg += f": {details}"

			result = wx.MessageBox(
				f"{msg}\n\nWould you like to continue setup for this account?\n\n"
				"Yes = Continue setup\n"
				"No = Remove this account",
				"Incomplete Account Found",
				wx.YES_NO | wx.ICON_QUESTION
			)

			if result == wx.NO:
				accounts_to_remove.append(index)

		# Remove accounts (in reverse order to maintain indices)
		if accounts_to_remove:
			for index in sorted(accounts_to_remove, reverse=True):
				try:
					# Delete config folder
					if config.is_portable_mode():
						config_path = os.path.join(self.confpath, f"account{index}")
					else:
						config_path = os.path.join(self.confpath, f"account{index}")

					if os.path.exists(config_path):
						shutil.rmtree(config_path)

					# Shift remaining account folders down
					for j in range(index + 1, self.prefs.accounts):
						old_path = os.path.join(self.confpath, f"account{j}")
						new_path = os.path.join(self.confpath, f"account{j-1}")
						if os.path.exists(old_path):
							shutil.move(old_path, new_path)

					self.prefs.accounts -= 1
				except Exception as e:
					print(f"Error removing account {index}: {e}")

	def _add_session_threaded(self, index):
		"""Add account session from a background thread."""
		import mastodon_api as t
		try:
			account = t.mastodon(self, index)
			# Store directly - account is fully initialized
			self.accounts.append(account)
		except Exception as e:
			print(f"Error loading account {index}: {e}")

	def save_users(self):
		"""No-op - user cache is in-memory only now."""
		pass

	def save_timeline_settings(self):
		"""Save timeline settings to disk."""
		f = open(self.confpath + "/timelinecache", "wb")
		f.write(pickle.dumps(self.timeline_settings))
		f.close()

	def load_timeline_settings(self):
		"""Load timeline settings from disk."""
		try:
			f = open(self.confpath + "/timelinecache", "rb")
			self.timeline_settings = pickle.loads(f.read())
			f.close()
		except:
			return False

	def get_timeline_settings(self, account_id, name):
		"""Get or create timeline settings for an account/timeline."""
		import timeline
		for i in self.timeline_settings:
			if i.tl == name and i.account_id == account_id:
				return i
		self.timeline_settings.append(timeline.TimelineSettings(account_id, name))
		return self.timeline_settings[len(self.timeline_settings) - 1]

	def clean_users(self):
		"""Clear the user cache."""
		self.users = []

	# ============ Utility Methods (moved from utils.py) ============

	def strip_html(self, text):
		"""Strip HTML tags and decode entities"""
		# Add spaces for block elements and line breaks to prevent text concatenation
		# Note: Don't add spaces for inline elements like <span> - Mastodon uses spans
		# within URLs (e.g., <span class="invisible">https://</span>) and adding spaces
		# would break the URL (causing "https:// example.com" instead of "https://example.com")
		text = re.sub(r'</(p|div)>', ' ', text, flags=re.IGNORECASE)
		text = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
		text = html_tag_re.sub('', text)
		text = html.unescape(text)
		text = re.sub(r'\s+', ' ', text).strip()
		return text

	def html_to_text_for_edit(self, content, mentions=None):
		"""Convert HTML content to plain text for editing, preserving newlines and full handles.

		Args:
			content: The HTML content from the status
			mentions: List of mention objects from the status (for resolving full handles)
		"""
		if not content:
			return ""

		text = content

		# Replace mentions with full handles if we have mention data
		# Mastodon HTML: <span class="h-card"><a href="https://instance/@user" ...>@<span>user</span></a></span>
		if mentions:
			for mention in mentions:
				acct = getattr(mention, 'acct', '')
				url = getattr(mention, 'url', '')
				if acct and url:
					# Match the mention link and replace with @acct
					# Pattern matches <a href="URL">@anything</a> or similar structures
					pattern = rf'<a[^>]*href=["\']?{re.escape(url)}["\']?[^>]*>.*?</a>'
					text = re.sub(pattern, f'@{acct}', text, flags=re.IGNORECASE | re.DOTALL)

		# Convert line breaks and paragraphs to newlines
		text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
		text = re.sub(r'</p>\s*<p[^>]*>', '\n\n', text, flags=re.IGNORECASE)
		text = re.sub(r'</?p[^>]*>', '\n', text, flags=re.IGNORECASE)

		# Remove all remaining HTML tags
		text = html_tag_re.sub('', text)

		# Decode HTML entities
		text = html.unescape(text)

		# Clean up excessive newlines but preserve intentional ones
		text = re.sub(r'\n{3,}', '\n\n', text)
		text = text.strip()

		return text

	def process_status(self, s, return_only_text=False, template="", ignore_cw=False, account=None):
		"""Process a Mastodon status for display"""
		# Handle scheduled statuses - check for _scheduled flag (set by platform backend)
		# or raw ScheduledStatus (has params and scheduled_at)
		is_scheduled = getattr(s, '_scheduled', False)
		if not is_scheduled and hasattr(s, 'params') and hasattr(s, 'scheduled_at'):
			is_scheduled = True

		if is_scheduled:
			return self._process_scheduled_status(s)

		if hasattr(s, 'content'):
			text = self.strip_html(s.content)
		else:
			text = ""

		if hasattr(s, 'reblog') and s.reblog:
			# For reblogs, get text from reblogged status (which includes its media descriptions)
			text = self.process_status(s.reblog, True, ignore_cw=ignore_cw, account=account)
			if template == "":
				template = self.prefs.boostTemplate
		else:
			# Handle content warning based on preference
			spoiler = getattr(s, 'spoiler_text', None)
			if spoiler and not ignore_cw:
				cw_mode = getattr(self.prefs, 'cw_mode', 'hide')
				if cw_mode == 'hide':
					# Show only the content warning
					text = f"CW: {spoiler}"
				elif cw_mode == 'show':
					# Show CW followed by text
					text = f"CW: {spoiler}. {text}"
				# 'ignore' mode: just use the text as-is

			# Handle server-side filter warnings (action="warn")
			# Uses the same cw_mode setting as content warnings
			filtered = getattr(s, 'filtered', None)
			if filtered and not ignore_cw:
				# Get filter titles from the matched filters
				filter_titles = []
				for result in filtered:
					filter_obj = getattr(result, 'filter', None)
					if filter_obj:
						title = getattr(filter_obj, 'title', None)
						if title:
							filter_titles.append(title)
				if filter_titles:
					filter_warning = "Filtered: " + ", ".join(filter_titles)
					cw_mode = getattr(self.prefs, 'cw_mode', 'hide')
					if cw_mode == 'hide':
						text = filter_warning
					elif cw_mode == 'show':
						text = f"{filter_warning}. {text}"
					# 'ignore' mode: just use the text as-is

			# Add media descriptions to text (only for non-reblogs to avoid duplication)
			if self.prefs.include_media_descriptions and hasattr(s, 'media_attachments') and s.media_attachments:
				for media in s.media_attachments:
					# Handle both objects (from API) and dicts (from cache)
					if isinstance(media, dict):
						media_type = media.get('type', 'media') or 'media'
						description = media.get('description') or media.get('alt')
					else:
						media_type = getattr(media, 'type', 'media') or 'media'
						description = getattr(media, 'description', None) or getattr(media, 'alt', None)
					type_display = media_type.upper() if media_type == 'gifv' else media_type.capitalize()
					if description:
						text += f" ({type_display}) description: {description}"
					else:
						text += f" ({type_display}) with no description"

			# Add card (external link embed) information - especially useful for Bluesky
			# posts that only contain a link with no text
			if self.prefs.include_link_preview:
				card = getattr(s, 'card', None)
				if card:
					card_title = getattr(card, 'title', None) if not isinstance(card, dict) else card.get('title')
					card_description = getattr(card, 'description', None) if not isinstance(card, dict) else card.get('description')
					card_url = getattr(card, 'url', None) if not isinstance(card, dict) else card.get('url')
					# Show card if we have title, description, or at least the URL
					if card_title or card_description or card_url:
						card_parts = []
						if card_title:
							card_parts.append(card_title)
						if card_description:
							card_parts.append(card_description)
						# If no title/description but we have URL, show the URL
						if not card_parts and card_url:
							card_parts.append(card_url)
						card_text = " - ".join(card_parts)
						# If text is empty, use card as main text; otherwise append
						if not text.strip():
							text = f"(Link) {card_text}"
						else:
							text += f" (Link) {card_text}"

			# Add poll information
			if hasattr(s, 'poll') and s.poll:
				poll = s.poll
				# Handle both object and dict (from cache)
				def get_poll_attr(obj, name, default=None):
					if isinstance(obj, dict):
						return obj.get(name, default)
					return getattr(obj, name, default)

				is_expired = get_poll_attr(poll, 'expired', False)
				has_voted = get_poll_attr(poll, 'voted', False)
				options = get_poll_attr(poll, 'options', [])
				own_votes = get_poll_attr(poll, 'own_votes', []) or []
				votes_count = get_poll_attr(poll, 'votes_count', 0)

				# Build poll status
				if is_expired:
					poll_status = "Poll ended"
				elif has_voted:
					poll_status = "Poll (voted)"
				else:
					poll_status = "Poll"

				# Build options list with vote info
				option_texts = []
				for i, opt in enumerate(options):
					opt_title = get_poll_attr(opt, 'title', str(opt))
					opt_votes = get_poll_attr(opt, 'votes_count', 0)
					if is_expired or has_voted:
						# Show results
						if votes_count > 0 and opt_votes:
							pct = (opt_votes / votes_count) * 100
							opt_text = f"{opt_title}: {pct:.0f}%"
						else:
							opt_text = f"{opt_title}: 0%"
						if i in own_votes:
							opt_text += " (your vote)"
					else:
						opt_text = opt_title
					option_texts.append(opt_text)

				text += f" ({poll_status}: {', '.join(option_texts)})"

		# Strip quote-related URLs from text when there's a quote
		if hasattr(s, 'quote') and s.quote:
			import re
			# Remove RE:/QT: followed by a URL at the start
			text = re.sub(r'^(RE|QT|re|qt):\s*https?://\S+\s*', '', text, flags=re.IGNORECASE).strip()
			# Get the quoted post's URL to strip it from the text
			quote_url = getattr(s.quote, 'url', None)
			if quote_url:
				# Strip the exact URL if it appears at the end
				text = text.rstrip()
				if text.endswith(quote_url):
					text = text[:-len(quote_url)].rstrip()
			# Also strip any trailing Mastodon-style status URLs (https://instance/@user/id)
			text = re.sub(r'\s*https?://[^\s]+/@[^\s]+/\d+\s*$', '', text).strip()

		# Collapse consecutive usernames at start of text if max_usernames_display is set
		# Setting controls threshold - when exceeded, show only first username + "and X more"
		max_usernames = getattr(self.prefs, 'max_usernames_display', 0)
		if max_usernames > 0:
			import re
			# Match consecutive @username patterns at the start (with optional whitespace between)
			username_pattern = r'^((?:@[\w.-]+(?:@[\w.-]+)?(?:\s+|$))+)'
			match = re.match(username_pattern, text)
			if match:
				# Extract all usernames from the matched portion
				username_portion = match.group(1)
				usernames = re.findall(r'@[\w.-]+(?:@[\w.-]+)?', username_portion)
				if len(usernames) > max_usernames:
					# Show only the first username and "X more"
					first_username = usernames[0]
					remaining_count = len(usernames) - 1
					rest_of_text = text[len(username_portion):].lstrip()
					text = f"{first_username} and {remaining_count} more"
					if rest_of_text:
						text += f" {rest_of_text}"

		if return_only_text:
			return text

		# Handle quotes: format as "Person: their comment. Quoting person2: quoted text. time"
		quote_formatted = ""
		if hasattr(s, 'quote') and s.quote:
			quote_text = self.process_status(s.quote, True, account=account)
			quote_wrapped = StatusWrapper(s.quote, quote_text)
			quote_formatted = self.template_to_string(quote_wrapped, self.prefs.quoteTemplate, account=account)

		wrapped = StatusWrapper(s, text)

		if quote_formatted:
			# For quotes, remove timestamp from main template and add it at the very end
			main_template = template if template else self.prefs.postTemplate
			# Remove $created_at$ from main template for quote posts
			temp_template = main_template.replace(" $created_at$", "").replace("$created_at$ ", "").replace("$created_at$", "")
			result = self.template_to_string(wrapped, temp_template, account=account)
			result += " " + quote_formatted
			# Add timestamp at the very end
			created_at = getattr(s, 'created_at', None)
			if created_at:
				result += " " + self.parse_date(created_at)
		else:
			result = self.template_to_string(wrapped, template, account=account)

		return result

	def _process_scheduled_status(self, s):
		"""Process a scheduled status for display."""
		# Check both _scheduled_at (UniversalStatus) and scheduled_at (raw ScheduledStatus)
		scheduled_at = getattr(s, '_scheduled_at', None) or getattr(s, 'scheduled_at', None)

		# Handle both raw ScheduledStatus (has params dict) and UniversalStatus (content from params)
		params = getattr(s, 'params', None)
		if params:
			# Raw ScheduledStatus - get from params
			if isinstance(params, dict):
				text = params.get('text', '')
				visibility = params.get('visibility', 'public')
				spoiler = params.get('spoiler_text', '')
			else:
				text = getattr(params, 'text', '')
				visibility = getattr(params, 'visibility', 'public')
				spoiler = getattr(params, 'spoiler_text', '')
		else:
			# UniversalStatus - content may be empty since params.text doesn't map to content
			# Check content first, then fall back to text attribute
			content = getattr(s, 'content', '')
			if content:
				text = self.strip_html(content)
			else:
				text = getattr(s, 'text', '')
			visibility = getattr(s, 'visibility', 'public')
			spoiler = getattr(s, 'spoiler_text', '')

		# Format scheduled time
		if scheduled_at:
			time_str = self.parse_date(scheduled_at)
		else:
			time_str = "unknown time"

		# Build the display string
		result = f"Scheduled for {time_str}"
		if visibility and visibility != 'public':
			result += f" ({visibility})"
		if spoiler:
			result += f" CW: {spoiler}."
		result += f": {text}"

		# Add media attachment count if any
		media = getattr(s, 'media_attachments', None)
		if media:
			result += f" ({len(media)} attachment{'s' if len(media) > 1 else ''})"

		return result

	def process_notification(self, n, account=None):
		"""Process a Mastodon notification for display using notification template"""
		type_labels = {
			'follow': 'followed you',
			'favourite': 'favourited your post',
			'reblog': 'boosted your post',
			'mention': 'mentioned you',
			'poll': 'poll ended',
			'update': 'edited a post',
			'status': 'posted',
			'follow_request': 'requested to follow you',
			'admin.sign_up': 'signed up',
			'admin.report': 'new report',
			'quote': 'quoted your post',
		}

		notif_type = getattr(n, 'type', 'unknown')
		status = getattr(n, 'status', None)

		# Get human-readable type label
		label = type_labels.get(notif_type, notif_type)

		# Build status text if notification has an associated status
		status_text = ""
		if status:
			# Use text field if available, otherwise strip HTML from content
			status_text = getattr(status, 'text', '') or self.strip_html(getattr(status, 'content', ''))

			# Collapse consecutive usernames at start of text if max_usernames_display is set
			max_usernames = getattr(self.prefs, 'max_usernames_display', 0)
			if max_usernames > 0:
				import re
				username_pattern = r'^((?:@[\w.-]+(?:@[\w.-]+)?(?:\s+|$))+)'
				match = re.match(username_pattern, status_text)
				if match:
					username_portion = match.group(1)
					usernames = re.findall(r'@[\w.-]+(?:@[\w.-]+)?', username_portion)
					if len(usernames) > max_usernames:
						first_username = usernames[0]
						remaining_count = len(usernames) - 1
						rest_of_text = status_text[len(username_portion):].lstrip()
						status_text = f"{first_username} and {remaining_count} more"
						if rest_of_text:
							status_text += f" {rest_of_text}"

			# Handle quote notifications - format similar to how quotes are shown in timelines
			if hasattr(status, 'quote') and status.quote:
				import re
				# Strip quote-related URLs from status_text (same as process_status)
				# Remove RE:/QT: followed by a URL at the start
				status_text = re.sub(r'^(RE|QT|re|qt):\s*https?://\S+\s*', '', status_text, flags=re.IGNORECASE).strip()
				# Get the quoted post's URL to strip it from the text
				quote_url = getattr(status.quote, 'url', None)
				if quote_url:
					# Strip the exact URL if it appears at the end
					status_text = status_text.rstrip()
					if status_text.endswith(quote_url):
						status_text = status_text[:-len(quote_url)].rstrip()
				# Also strip any trailing Mastodon-style status URLs (https://instance/@user/id)
				status_text = re.sub(r'\s*https?://[^\s]+/@[^\s]+/\d+\s*$', '', status_text).strip()

				quote = status.quote
				quote_text = getattr(quote, 'text', '') or self.strip_html(getattr(quote, 'content', ''))
				quote_account = getattr(quote, 'account', None)
				if quote_account:
					# Check for alias
					quote_user_id = str(getattr(quote_account, 'id', ''))
					if account and quote_user_id and quote_user_id in account.prefs.aliases:
						quote_name = account.prefs.aliases[quote_user_id]
					else:
						quote_name = getattr(quote_account, 'display_name', '') or getattr(quote_account, 'acct', '')
					quote_acct = getattr(quote_account, 'acct', '')
					status_text += f" Quoting {quote_name} (@{quote_acct}): {quote_text}"
				else:
					status_text += f" Quoting: {quote_text}"

			# Add poll info for notifications with polls
			if hasattr(status, 'poll') and status.poll:
				poll = status.poll
				# Handle both object and dict (from cache)
				def get_poll_attr(obj, name, default=None):
					if isinstance(obj, dict):
						return obj.get(name, default)
					return getattr(obj, name, default)

				is_expired = get_poll_attr(poll, 'expired', False)
				options = get_poll_attr(poll, 'options', [])
				votes_count = get_poll_attr(poll, 'votes_count', 0)
				option_texts = []
				for opt in options:
					opt_title = get_poll_attr(opt, 'title', str(opt))
					opt_votes = get_poll_attr(opt, 'votes_count', 0)
					if is_expired and votes_count > 0:
						pct = (opt_votes / votes_count) * 100
						option_texts.append(f"{opt_title}: {pct:.0f}%")
					else:
						option_texts.append(opt_title)
				poll_label = "Poll ended" if is_expired else "Poll"
				status_text += f" ({poll_label}: {', '.join(option_texts)})"

		# Wrap notification with type label and text for templating
		wrapped = NotificationWrapper(n, type_label=label, text=status_text)

		# Use notification template
		result = self.template_to_string(wrapped, self.prefs.notificationTemplate, account=account)

		return result

	def process_conversation(self, c, account=None):
		"""Process a Mastodon conversation for display"""
		conv_accounts = getattr(c, 'accounts', [])
		last_status = getattr(c, 'last_status', None)

		if conv_accounts:
			# Get display names with alias and demojify support
			names = []
			for a in conv_accounts[:3]:
				user_id = str(getattr(a, 'id', ''))
				if account and user_id and user_id in account.prefs.aliases:
					names.append(account.prefs.aliases[user_id])
				else:
					display_name = a.display_name or a.acct
					# Apply demojify setting
					if self.prefs.demojify:
						demojied = self.demojify(display_name)
						if demojied == "":
							display_name = a.acct
						else:
							display_name = demojied
					names.append(display_name)
			participants = ", ".join(names)
			if len(conv_accounts) > 3:
				participants += f" and {len(conv_accounts) - 3} others"
		else:
			participants = "Unknown"

		if last_status:
			text = self.strip_html(getattr(last_status, 'content', ''))
			created_at = self.parse_date(getattr(last_status, 'created_at', None))
			return f"{participants}: {text} {created_at}"
		else:
			return f"Conversation with {participants}"

	def process_message(self, s, return_text=False):
		"""Process a direct message/conversation"""
		if hasattr(s, 'last_status'):
			return self.process_conversation(s)
		elif hasattr(s, 'content'):
			text = self.strip_html(s.content)
			if return_text:
				return text
			return self.template_to_string(s, self.prefs.conversationTemplate)
		return ""

	def find_urls_in_text(self, text):
		return [s.strip(bad_chars) for s in url_re2.findall(text)]

	def find_urls_in_status(self, s):
		"""Find URLs in a status (Mastodon or Bluesky)

		Returns URLs in order: text/link URLs first, then media URLs
		"""
		urls = []
		media_urls = []

		# For reblogged/boosted posts, also check the inner post
		post_to_check = s
		if hasattr(s, 'reblog') and s.reblog:
			post_to_check = s.reblog

		# Get card URL (external link embed)
		if hasattr(post_to_check, 'card') and post_to_check.card:
			if hasattr(post_to_check.card, 'url') and post_to_check.card.url:
				urls.append(post_to_check.card.url)

		# Get Bluesky facet links (URLs embedded in post text)
		if hasattr(post_to_check, '_facet_links') and post_to_check._facet_links:
			for link in post_to_check._facet_links:
				if link not in urls:
					urls.append(link)

		# Get URLs from HTML content (Mastodon)
		if hasattr(post_to_check, 'content') and post_to_check.content:
			text_urls = self.find_urls_in_text(self.strip_html(post_to_check.content))
			for url in text_urls:
				if url not in urls:
					urls.append(url)

		# Get URLs from plain text (Bluesky) - only if no facet links found
		if hasattr(post_to_check, 'text') and post_to_check.text and not hasattr(post_to_check, '_facet_links'):
			text_urls = self.find_urls_in_text(post_to_check.text)
			for url in text_urls:
				if url not in urls:
					urls.append(url)

		# Get media attachment URLs (added last so they appear after text URLs)
		if hasattr(post_to_check, 'media_attachments'):
			for media in post_to_check.media_attachments:
				if hasattr(media, 'url') and media.url:
					if media.url not in urls:
						media_urls.append(media.url)

		# Combine: text URLs first, then media URLs
		urls.extend(media_urls)

		# Also check quoted posts for media
		if hasattr(post_to_check, 'quote') and post_to_check.quote:
			quote = post_to_check.quote
			if hasattr(quote, 'media_attachments'):
				for media in quote.media_attachments:
					if hasattr(media, 'url') and media.url and media.url not in urls:
						urls.append(media.url)

		return urls

	def template_to_string(self, s, template="", account=None):
		"""Format a status using a template"""
		if template == "":
			template = self.prefs.postTemplate

		# Prepare text content now, but replace AFTER other substitutions
		# to prevent $..$ patterns in post text from being interpreted as template vars
		text_content = None
		if "$text$" in template:
			# First check if we have a pre-processed text attribute (from StatusWrapper)
			# This includes media descriptions and other processed content from process_status()
			text_content = getattr(s, 'text', '')
			needs_media_descriptions = False
			if not text_content:
				# Fall back to stripping HTML from content
				# Media descriptions need to be added since we're not using pre-processed text
				if hasattr(s, 'reblog') and s.reblog:
					text_content = self.strip_html(getattr(s.reblog, 'content', ''))
				else:
					text_content = self.strip_html(getattr(s, 'content', ''))
				needs_media_descriptions = True
			if self.prefs.demojify_post:
				text_content = self.demojify(text_content)

			# Add media descriptions only if we used the fallback path (not pre-processed text)
			if needs_media_descriptions and self.prefs.include_media_descriptions:
				# Get media from reblog if this is a boost, otherwise from status
				status_for_media = s.reblog if hasattr(s, 'reblog') and s.reblog else s
				media_attachments = getattr(status_for_media, 'media_attachments', []) or []
				for media in media_attachments:
					# Handle both objects (from API) and dicts (from cache)
					if isinstance(media, dict):
						media_type = media.get('type', 'media') or 'media'
						description = media.get('description') or media.get('alt')
					else:
						media_type = getattr(media, 'type', 'media') or 'media'
						description = getattr(media, 'description', None) or getattr(media, 'alt', None)
					type_display = media_type.upper() if media_type == 'gifv' else media_type.capitalize()
					if description:
						text_content += f" ({type_display}) description: {description}"
					else:
						text_content += f" ({type_display}) with no description"

		temp = template.split(" ")
		for i in range(len(temp)):
			if "$" in temp[i]:
				t = temp[i].split("$")
				r = t[1]
				if r == "text":
					continue  # Already handled above
				if "." in r:
					q = r.split(".")
					# Support multi-level attribute access (e.g., reblog.account.display_name)
					try:
						obj = s
						parent_obj = None
						for attr in q:
							if obj is None:
								break
							parent_obj = obj
							obj = getattr(obj, attr, None)
						if obj is not None:
							# Check if we need to demojify
							last_attr = q[-1]
							# Check for alias if this is display_name and we have an account
							if last_attr in ('name', 'display_name') and account and parent_obj:
								user_id = str(getattr(parent_obj, 'id', ''))
								if user_id and user_id in account.prefs.aliases:
									obj = account.prefs.aliases[user_id]
								elif self.prefs.demojify:
									demojied = self.demojify(str(obj))
									if demojied == "":
										obj = getattr(parent_obj, "acct", obj)
									else:
										obj = demojied
							elif (last_attr in ('name', 'display_name')) and self.prefs.demojify:
								demojied = self.demojify(str(obj))
								if demojied == "":
									# Try to get acct as fallback
									fallback_obj = s
									for attr in q[:-1]:
										fallback_obj = getattr(fallback_obj, attr, None)
										if fallback_obj is None:
											break
									if fallback_obj:
										obj = getattr(fallback_obj, "acct", obj)
								else:
									obj = demojied
							elif last_attr == 'note':
								# Strip HTML from bio/note field
								obj = self.strip_html(str(obj))
							template = template.replace("$" + t[1] + "$", str(obj))
						else:
							# Value is None - replace with empty string to avoid showing raw template
							template = template.replace("$" + t[1] + "$", "")
					except Exception as e:
						pass  # Leave placeholder if we can't resolve it
				else:
					if hasattr(s, t[1]):
						try:
							# Check for alias if this is display_name and we have an account
							if t[1] in ('name', 'display_name') and account:
								user_id = str(getattr(s, 'id', ''))
								if user_id and user_id in account.prefs.aliases:
									template = template.replace("$" + t[1] + "$", account.prefs.aliases[user_id])
									continue
							if t[1] == "name" or t[1] == "display_name" and self.prefs.demojify or t[1] == "text" and self.prefs.demojify_post:
								deEmojify = True
							else:
								deEmojify = False
							if deEmojify:
								demojied = self.demojify(str(getattr(s, t[1])))
								if demojied == "" and (t[1] == "name" or t[1] == "display_name"):
									template = template.replace("$" + t[1] + "$", getattr(s, "acct", ""))
								else:
									template = template.replace("$" + t[1] + "$", demojied)
							else:
								if t[1] == "created_at":
									template = template.replace("$" + t[1] + "$", self.parse_date(getattr(s, t[1])))
								elif t[1] == "note":
									# Strip HTML from bio/note field
									template = template.replace("$" + t[1] + "$", self.strip_html(str(getattr(s, t[1]))))
								else:
									template = template.replace("$" + t[1] + "$", str(getattr(s, t[1])))
						except:
							try:
								template = template.replace("$" + t[1] + "$", str(getattr(s, t[1])))
							except Exception as e:
								print(e)
		# Replace $text$ last to prevent post content with $..$ from being interpreted as template vars
		if text_content is not None:
			template = template.replace("$text$", text_content)
		return template

	def get_users_in_status(self, account, s):
		"""Get usernames mentioned in a status for reply"""
		users = []

		if hasattr(s, 'account') and s.account.acct != account.me.acct:
			users.append(s.account.acct)

		if hasattr(s, 'mentions'):
			for mention in s.mentions:
				if mention.acct != account.me.acct and mention.acct not in users:
					users.append(mention.acct)

		if hasattr(s, 'reblog') and s.reblog:
			if s.reblog.account.acct != account.me.acct and s.reblog.account.acct not in users:
				users.append(s.reblog.account.acct)

		if hasattr(s, 'quote') and s.quote and hasattr(s.quote, 'account') and s.quote.account:
			if s.quote.account.acct != account.me.acct and s.quote.account.acct not in users:
				users.append(s.quote.account.acct)

		return " ".join(["@" + u if not u.startswith("@") else u for u in users])

	def user(self, s):
		"""Get username from status"""
		if hasattr(s, 'account'):
			return s.account.acct
		return ""

	def parse_date(self, date, convert=True):
		"""Parse a date for display"""
		if date is None:
			return ""
		ti = datetime.datetime.now()
		dst = time.localtime().tm_isdst
		if dst == 1:
			tz = time.altzone
		else:
			tz = time.timezone
		if convert:
			try:
				if hasattr(date, 'tzinfo') and date.tzinfo is not None:
					date = date.replace(tzinfo=None)
				date += datetime.timedelta(seconds=0 - tz)
			except:
				pass
		returnstring = ""

		try:
			dateFormatString = "%m/%d/%Y"
			timeFormatString = "%I:%M:%S %p"
			if self.prefs.use24HourTime:
				timeFormatString = "%H:%M:%S"
			if date.year == ti.year:
				if date.day == ti.day and date.month == ti.month:
					returnstring = ""
				else:
					returnstring = date.strftime(f"{dateFormatString}, ")
			else:
				returnstring = date.strftime(f"{dateFormatString}, ")

			returnstring += date.strftime(timeFormatString)
		except:
			pass
		return returnstring

	def isDuplicate(self, status, statuses):
		for i in statuses:
			if i.id == status.id:
				return True
		return False

	def _remove_user_by_id(self, user_id):
		"""Remove a user from the cache by ID"""
		for i, u in enumerate(self.users):
			if u.id == user_id:
				self.users.pop(i)
				return True
		return False

	def _add_user_to_cache(self, user):
		"""Add a user to the cache, removing any existing entry with same ID"""
		if user is None:
			return
		self._remove_user_by_id(user.id)
		self.users.insert(0, user)

	def add_users(self, status, account=None):
		"""Add users from a status to the cache"""
		# Use per-account cache if available
		if account is None:
			account = self.currentAccount
		if account and hasattr(account, 'user_cache') and account.user_cache:
			account.user_cache.add_users_from_status(status)
			return

		# Fallback to global cache
		if hasattr(status, 'account') and status.account:
			self._add_user_to_cache(status.account)

		if hasattr(status, 'reblog') and status.reblog and hasattr(status.reblog, 'account'):
			self._add_user_to_cache(status.reblog.account)

		if hasattr(status, 'quote') and status.quote and hasattr(status.quote, 'account') and status.quote.account:
			self._add_user_to_cache(status.quote.account)

	def add_users_from_notification(self, notification, account=None):
		"""Add users from a notification to the cache"""
		# Use per-account cache if available
		if account is None:
			account = self.currentAccount
		if account and hasattr(account, 'user_cache') and account.user_cache:
			account.user_cache.add_users_from_notification(notification)
			return

		# Fallback to global cache
		if hasattr(notification, 'account') and notification.account:
			self._add_user_to_cache(notification.account)

		if hasattr(notification, 'status') and notification.status:
			self.add_users(notification.status)

	def lookup_user(self, id, account=None):
		"""Look up user by ID from cache"""
		# Use per-account cache if available
		if account is None:
			account = self.currentAccount
		if account and hasattr(account, 'user_cache') and account.user_cache:
			user = account.user_cache.lookup_by_id(str(id))
			if user:
				return user

		# Fallback to global cache
		for i in self.users:
			try:
				if int(i.id) == int(id):
					return i
			except:
				pass
		if account and hasattr(account, 'user_cache') and account.user_cache:
			account.user_cache.unknown_users.append(str(id))
		else:
			self.unknown_users.append(id)
		print(str(id) + " not found. Added to queue.")
		return None

	def lookup_user_name(self, account, name, use_api=True):
		"""Look up user by acct/username"""
		name = name.lstrip('@')

		# Use per-account cache if available
		if account and hasattr(account, 'user_cache') and account.user_cache:
			# Define API callback based on platform
			def api_lookup(n):
				if not use_api:
					return None
				try:
					# Use platform backend if available
					if hasattr(account, '_platform') and account._platform:
						if hasattr(account._platform, 'lookup_user_by_name'):
							return account._platform.lookup_user_by_name(n)
						elif hasattr(account._platform, 'search_users'):
							results = account._platform.search_users(n, limit=1)
							if results:
								return results[0]
					else:
						# Fallback to Mastodon API
						from platforms.mastodon.models import mastodon_user_to_universal
						results = account.api.account_search(q=n, limit=1)
						if results:
							return mastodon_user_to_universal(results[0])
				except:
					pass
				return None

			user = account.user_cache.lookup_by_name(name, api_lookup if use_api else None)
			if user:
				return user
			return -1 if not use_api else -1

		# Fallback to global cache
		for i in self.users:
			if i.acct.lower() == name.lower() or i.acct.split('@')[0].lower() == name.lower():
				return i
		if not use_api:
			return -1
		try:
			# Use platform backend if available
			if hasattr(account, '_platform') and account._platform:
				if hasattr(account._platform, 'lookup_user_by_name'):
					user = account._platform.lookup_user_by_name(name)
					if user:
						return user
				elif hasattr(account._platform, 'search_users'):
					results = account._platform.search_users(name, limit=1)
					if results:
						return results[0]
			else:
				# Fallback to Mastodon API
				results = account.api.account_search(q=name, limit=1)
				if results:
					user = results[0]
					self._add_user_to_cache(user)
					return user
		except:
			pass
		return -1

	def get_user_objects_in_status(self, account, status, exclude_self=False, exclude_orig=False):
		"""Get user objects mentioned in a status"""
		users = []

		if hasattr(status, 'account') and not exclude_orig:
			if status.account not in users:
				users.append(status.account)

		if hasattr(status, 'reblog') and status.reblog:
			if status.reblog.account not in users:
				users.append(status.reblog.account)

		if hasattr(status, 'quote') and status.quote and hasattr(status.quote, 'account') and status.quote.account:
			if status.quote.account not in users:
				users.append(status.quote.account)

		if hasattr(status, 'mentions'):
			for mention in status.mentions:
				if account.me.acct != mention.acct or not exclude_self:
					un = self.lookup_user_name(account, mention.acct)
					if un != -1 and un not in users:
						users.append(un)

		if exclude_self:
			users = [u for u in users if u.id != account.me.id]

		return users

	def speak_user(self, account, users):
		import speak
		text = ""
		for i in users:
			user = self.lookup_user_name(account, i)
			if user is not None and user != -1:
				# Fetch detailed profile if this looks like a basic profile view
				# Basic profiles lack created_at and counts (or have all zeros)
				is_basic_profile = (
					getattr(user, 'created_at', None) is None or
					(getattr(user, 'followers_count', 0) == 0 and
					 getattr(user, 'following_count', 0) == 0 and
					 getattr(user, 'statuses_count', 0) == 0)
				)
				if is_basic_profile:
					try:
						detailed_user = account.get_user(user.id)
						if detailed_user:
							user = detailed_user
					except:
						pass  # Fall back to basic profile if fetch fails
				text += ". " + self.template_to_string(user, self.prefs.userTemplate)
			text = text.rstrip(".")
		text = text.lstrip(".")
		speak.speak(str(len(users)) + " users: " + text)

	def lookup_status(self, account, id):
		"""Look up a status by ID"""
		for i in account.timelines:
			for i2 in i.statuses:
				if i2.id == id:
					return i2
		try:
			# Use platform-specific status lookup
			if hasattr(account, '_platform') and account._platform:
				s = account._platform.get_status(id)
			else:
				s = account.api.status(id=id)
			return s
		except:
			return None

	def find_status(self, tl, id):
		index = 0
		for i in tl.statuses:
			if i.id == id:
				return index
			index += 1
		return -1

	def find_reply(self, tl, id):
		index = 0
		for i in tl.statuses:
			if hasattr(i, "in_reply_to_id") and i.in_reply_to_id == id:
				return index
			index += 1
		return -1

	def speak_reply(self, account, status):
		import speak
		if hasattr(status, "in_reply_to_id") and status.in_reply_to_id is not None:
			status = self.lookup_status(account, status.in_reply_to_id)
			if status:
				status = self.process_status(status)
				speak.speak(status)
			else:
				speak.speak("Could not find the original post.")
		else:
			speak.speak("Not a reply.")

	def question(self, title, text, parent=None):
		dlg = wx.MessageDialog(parent, text, title, wx.YES_NO | wx.ICON_QUESTION)
		# Skip Raise() on macOS - it can cause segfaults and ShowModal brings dialog to front anyway
		if platform.system() != "Darwin":
			try:
				dlg.Raise()
				dlg.RequestUserAttention()
			except (RuntimeError, Exception):
				pass
		result = dlg.ShowModal()
		dlg.Destroy()
		if result == wx.ID_YES:
			return 1
		else:
			return 2

	def question_from_thread(self, title, text):
		"""Show a question dialog from a background thread. Returns 1 for Yes, 2 for No."""
		result = [None]
		event = threading.Event()
		def show_dialog():
			result[0] = self.question(title, text)
			event.set()
		wx.CallAfter(show_dialog)
		event.wait()
		return result[0]

	def warn(self, message, caption='Warning!', parent=None):
		dlg = wx.MessageDialog(parent, message, caption, wx.OK | wx.ICON_WARNING)
		# Skip Raise() on macOS - it can cause segfaults and ShowModal brings dialog to front anyway
		if platform.system() != "Darwin":
			try:
				dlg.Raise()
				dlg.RequestUserAttention()
			except (RuntimeError, Exception):
				pass
		dlg.ShowModal()
		dlg.Destroy()

	def alert(self, message, caption="", parent=None):
		dlg = wx.MessageDialog(parent, message, caption, wx.OK)
		# Skip Raise() on macOS - it can cause segfaults and ShowModal brings dialog to front anyway
		if platform.system() != "Darwin":
			try:
				dlg.Raise()
				dlg.RequestUserAttention()
			except (RuntimeError, Exception):
				pass
		dlg.ShowModal()
		dlg.Destroy()

	def alert_from_thread(self, message, caption=""):
		"""Show an alert dialog from a background thread."""
		if platform.system() == "Darwin":
			# On Mac, don't block - just schedule the dialog
			wx.CallAfter(self.alert, message, caption)
		else:
			event = threading.Event()
			def show_dialog():
				self.alert(message, caption)
				event.set()
			wx.CallAfter(show_dialog)
			event.wait()

	def _get_local_build_commit(self):
		"""Get the commit SHA from the build_info.txt file."""
		# Check various locations for build_info.txt
		possible_paths = []

		# Frozen app (PyInstaller) - check _MEIPASS first (internal folder)
		if getattr(sys, 'frozen', False):
			# PyInstaller bundles data files in sys._MEIPASS
			meipass = getattr(sys, '_MEIPASS', None)
			if meipass:
				possible_paths.append(os.path.join(meipass, 'build_info.txt'))

			# Fallback: same folder as exe (Windows)
			app_dir = os.path.dirname(sys.executable)
			possible_paths.append(os.path.join(app_dir, 'build_info.txt'))

			# Fallback: macOS Resources folder
			if platform.system() == 'Darwin':
				resources_dir = os.path.join(os.path.dirname(app_dir), 'Resources')
				possible_paths.append(os.path.join(resources_dir, 'build_info.txt'))
		else:
			# Running from source - check script directory
			script_dir = os.path.dirname(os.path.abspath(__file__))
			possible_paths.append(os.path.join(script_dir, 'build_info.txt'))

		for path in possible_paths:
			if os.path.isfile(path):
				try:
					with open(path, 'r') as f:
						return f.read().strip()
				except:
					pass
		return None

	def _is_installed(self):
		"""Check if the app was installed via installer (vs portable/zip).

		Returns True if installed via Inno Setup installer, False if portable.
		Detection is based on whether the app is running from typical install locations:
		- Program Files (admin install)
		- User's AppData/Local/Programs (per-user install)
		"""
		if platform.system() != "Windows":
			return False

		if not getattr(sys, 'frozen', False):
			return False

		try:
			# Get the directory where the executable is running from
			app_dir = os.path.dirname(sys.executable).lower()

			# Check for typical install locations
			program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files').lower()
			program_files_x86 = os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)').lower()
			local_appdata = os.environ.get('LOCALAPPDATA', '').lower()

			# Admin install: Program Files\FastSM
			if app_dir.startswith(program_files) or app_dir.startswith(program_files_x86):
				return True

			# Per-user install: AppData\Local\Programs\FastSM
			if local_appdata and app_dir.startswith(os.path.join(local_appdata, 'programs')):
				return True

		except Exception:
			pass

		return False

	def cfu(self, silent=True):
		# Don't run auto-updater when running from source
		if not getattr(sys, 'frozen', False):
			if not silent:
				self.alert("Auto-updater is only available in compiled builds.\n\nWhen running from source, use git pull to update.", "Update Check")
			return

		try:
			# Use /releases endpoint since /releases/latest doesn't include prereleases
			releases = json.loads(requests.get("https://api.github.com/repos/masonasons/FastSM/releases", headers={"accept": "application/vnd.github.v3+json", "User-Agent": f"{name}/{version}"}).content.decode())
			if not releases:
				if not silent:
					self.alert("No releases found.", "Update Check")
				return
			# Get the first release (most recent)
			latest = releases[0]
			body = latest.get('body', '')

			# Parse commit SHA from release body (format: "Automated build from commit XXXX")
			commit_match = re.search(r'Automated build from commit\s+([a-f0-9]+)', body)
			release_commit = commit_match.group(1) if commit_match else None

			# Parse version from release body (format: **Version:** X.Y.Z)
			version_match = re.search(r'\*\*Version:\*\*\s*(\d+\.\d+\.\d+)', body)
			latest_version = version_match.group(1) if version_match else version

			# Get local build commit
			local_commit = self._get_local_build_commit()

			# Determine if update is available
			update_available = False

			if release_commit and local_commit:
				# Compare by commit SHA (most reliable)
				update_available = release_commit != local_commit
			else:
				# Fallback to version comparison if no commit info
				def parse_version(v):
					return tuple(int(x) for x in v.split('.'))
				try:
					current_ver = parse_version(version)
					latest_ver = parse_version(latest_version)
					update_available = latest_ver > current_ver
				except:
					pass

			if update_available:
				# Build message showing commit info if available
				message = "There is an update available.\n\n"
				message += f"Your version: {version}"
				if local_commit:
					message += f" (commit {local_commit[:8]})"
				message += f"\nLatest version: {latest_version}"
				if release_commit:
					message += f" (commit {release_commit[:8]})"
				message += "\n\nDo you want to download and install the update?"

				# Use thread-safe dialog since cfu runs in background thread
				ud = self.question_from_thread("Update available: " + latest_version, message)
				if ud == 1:
					# Check if app is installed (vs portable) to choose update method
					is_installed = self._is_installed()

					for asset in latest['assets']:
						asset_name = asset['name'].lower()
						if platform.system() == "Windows":
							# If installed, prefer the installer; if portable, prefer the zip
							if is_installed and 'installer' in asset_name and asset_name.endswith('.exe'):
								threading.Thread(target=self.download_update, args=[asset['browser_download_url'], True], daemon=True).start()
								return
							elif not is_installed and 'portable' in asset_name and asset_name.endswith('.zip'):
								threading.Thread(target=self.download_update, args=[asset['browser_download_url'], False], daemon=True).start()
								return
						elif platform.system() == "Darwin" and asset_name.endswith('.dmg'):
							threading.Thread(target=self.download_update, args=[asset['browser_download_url'], False], daemon=True).start()
							return

					# Fallback: if preferred format not found, try the other one
					for asset in latest['assets']:
						asset_name = asset['name'].lower()
						if platform.system() == "Windows":
							if 'installer' in asset_name and asset_name.endswith('.exe'):
								threading.Thread(target=self.download_update, args=[asset['browser_download_url'], True], daemon=True).start()
								return
							elif 'portable' in asset_name and asset_name.endswith('.zip'):
								threading.Thread(target=self.download_update, args=[asset['browser_download_url'], False], daemon=True).start()
								return

					self.alert_from_thread("A download for this version could not be found for your platform. Check back soon.", "Error")
			else:
				if not silent:
					message = f"You are running the latest version: {version}"
					if local_commit:
						message += f" (commit {local_commit[:8]})"
					self.alert_from_thread("No updates available!\n\n" + message, "No Update Available")
		except Exception as e:
			if not silent:
				self.alert_from_thread(f"Error checking for updates: {e}", "Update Check Error")

	def demojify(self, text):
		"""Remove emoji from text while preserving accented characters."""
		import re
		text = str(text)

		# First remove Mastodon-style custom emoji shortcodes like :emoji_name:
		# These are in format :shortcode: where shortcode is alphanumeric with underscores
		shortcode_pattern = re.compile(r':[a-zA-Z0-9_]+:', flags=re.UNICODE)
		text = shortcode_pattern.sub('', text)

		# Pattern to match most Unicode emoji ranges
		emoji_pattern = re.compile(
			"["
			"\U0001F300-\U0001F9FF"  # Miscellaneous Symbols and Pictographs, Emoticons, etc.
			"\U0001FA00-\U0001FAFF"  # Chess, symbols, etc.
			"\U00002600-\U000027BF"  # Misc symbols, Dingbats
			"\U0001F600-\U0001F64F"  # Emoticons
			"\U0001F680-\U0001F6FF"  # Transport and Map
			"\U0001F1E0-\U0001F1FF"  # Flags
			"\U00002300-\U000023FF"  # Misc Technical
			"\U00002B50-\U00002B55"  # Stars
			"\U0000FE00-\U0000FE0F"  # Variation Selectors
			"\U0000200D"             # Zero Width Joiner
			"\U00003030\U000025AA\U000025AB\U000025B6\U000025C0\U000025FB-\U000025FE"
			"]+",
			flags=re.UNICODE
		)
		return emoji_pattern.sub('', text)

	def handle_error(self, error, name="Unknown"):
		"""Handle API errors from Mastodon or Bluesky"""
		import speak
		import sound
		# Log the error
		try:
			from logging_config import get_logger
			logger = get_logger('api')
			logger.error(f"API error in {name}: {error}", exc_info=True)
		except ImportError:
			pass
		# Try to extract a meaningful error message
		error_msg = str(error)
		# If empty or unhelpful, try other sources
		if not error_msg or error_msg == "None" or error_msg == str(type(error)):
			# Handle atproto errors which may have response attribute
			if hasattr(error, 'response') and error.response:
				try:
					if hasattr(error.response, 'content'):
						error_msg = str(error.response.content)
					elif hasattr(error.response, 'text'):
						error_msg = error.response.text
				except:
					pass
			# Try other attributes
			if not error_msg or error_msg == "None":
				if hasattr(error, 'message'):
					error_msg = error.message
				elif hasattr(error, 'args') and error.args:
					error_msg = str(error.args[0])
				else:
					error_msg = type(error).__name__
		if "429" in error_msg:
			self.errors.append("Error in " + name + ": Rate limited")
			return
		if self.prefs.errors:
			speak.speak("Error in " + name + ": " + error_msg)
			sound.play(self.currentAccount, "error")
		self.errors.append("Error in " + name + ": " + error_msg)

	def get_account(self, id):
		for i in self.accounts:
			if i.me.id == id:
				return i
		return -1

	def openURL(self, url):
		if platform.system() != "Darwin":
			webbrowser.open(url)
		else:
			# Use subprocess with list args to avoid shell escaping issues
			import subprocess
			subprocess.run(['open', url])

	def download_file(self, url):
		local_filename = url.split('/')[-1]
		if platform.system() == "Darwin":
			local_filename = os.path.expanduser("~/Downloads/" + local_filename)
		with requests.get(url, stream=True, headers={"User-Agent": f"{name}/{version}"}) as r:
			r.raise_for_status()
			with open(local_filename, 'wb') as f:
				for chunk in r.iter_content(chunk_size=8192):
					f.write(chunk)
		return local_filename

	def download_update(self, url, use_installer=False):
		import speak
		import shutil

		# Use a temp directory for download to avoid I/O contention with app directory
		import tempfile
		temp_dir = tempfile.gettempdir()

		if platform.system() == "Windows" and use_installer:
			# Installer-based update (for installed versions)
			self._download_installer_update(url, temp_dir)
			return

		if platform.system() == "Windows":
			# Get app directory
			if getattr(sys, 'frozen', False):
				app_dir = os.path.dirname(sys.executable)
			else:
				app_dir = os.path.dirname(os.path.abspath(__file__))

			# Download to temp, then move
			zip_path = os.path.join(temp_dir, "FastSM-update.zip")
			final_zip_path = os.path.join(app_dir, "FastSM-update.zip")
			extract_dir = os.path.join(app_dir, "FastSM-update")

			# Create and show progress dialog from main thread
			progress_data = {'dialog': None, 'cancelled': False}

			def create_progress_dialog():
				progress_data['dialog'] = wx.ProgressDialog(
					"Downloading Update",
					"Downloading FastSM update...",
					maximum=100,
					style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME
				)
				# Skip Raise() on macOS - can cause segfaults
				if platform.system() != "Darwin":
					progress_data['dialog'].Raise()

			def update_progress(downloaded, total):
				if progress_data['dialog'] and total > 0:
					percent = int((downloaded / total) * 100)
					mb_downloaded = downloaded / (1024 * 1024)
					mb_total = total / (1024 * 1024)
					def do_update():
						if progress_data['dialog']:
							cont, _ = progress_data['dialog'].Update(
								percent,
								f"Downloading: {mb_downloaded:.1f} MB / {mb_total:.1f} MB"
							)
							if not cont:
								progress_data['cancelled'] = True
					wx.CallAfter(do_update)

			def close_progress_dialog():
				if progress_data['dialog']:
					progress_data['dialog'].Destroy()
					progress_data['dialog'] = None

			# Create dialog on main thread and wait
			event = threading.Event()
			def create_and_signal():
				create_progress_dialog()
				event.set()
			wx.CallAfter(create_and_signal)
			event.wait()

			try:
				# Remove old update files if they exist
				if os.path.exists(zip_path):
					os.remove(zip_path)
				if os.path.exists(final_zip_path):
					os.remove(final_zip_path)
				if os.path.exists(extract_dir):
					shutil.rmtree(extract_dir)

				# Download the zip file to temp with progress
				self.download_file_to(url, zip_path, progress_callback=update_progress)

				if progress_data['cancelled']:
					wx.CallAfter(close_progress_dialog)
					speak.speak("Download cancelled.")
					if os.path.exists(zip_path):
						os.remove(zip_path)
					return

				wx.CallAfter(close_progress_dialog)

				# Move from temp to app directory
				shutil.move(zip_path, final_zip_path)
				speak.speak("Download complete. Preparing update...")

				# Create updater batch script
				batch_path = os.path.join(app_dir, "updater.bat")
				exe_name = "FastSM.exe" if getattr(sys, 'frozen', False) else "python.exe"

				# Escape apostrophes in paths for PowerShell single-quoted strings (double them)
				ps_zip_path = final_zip_path.replace("'", "''")
				ps_extract_dir = extract_dir.replace("'", "''")

				batch_content = f'''@echo off
echo Waiting for FastSM to close...
timeout /t 2 /nobreak >nul

echo Extracting update...
powershell -Command "Expand-Archive -Path '{ps_zip_path}' -DestinationPath '{ps_extract_dir}' -Force"

echo Installing update...
rem The zip contains a FastSM folder inside, so copy from there
xcopy /s /y /q "{extract_dir}\\FastSM\\*" "{app_dir}\\"

echo Cleaning up...
rmdir /s /q "{extract_dir}"
del "{final_zip_path}"

echo Starting FastSM...
start "" "{os.path.join(app_dir, exe_name)}"

echo Update complete!
del "%~f0"
'''
				with open(batch_path, 'w') as f:
					f.write(batch_content)

				speak.speak("Update ready. FastSM will now restart.")
				# Run the updater and exit cleanly (OnClose handles cleanup like saving positions)
				os.startfile(batch_path)
				from GUI import main
				wx.CallAfter(main.window.OnClose)

			except Exception as e:
				wx.CallAfter(close_progress_dialog)
				speak.speak(f"Update failed: {e}")
				self.alert_from_thread(f"Failed to download or apply update: {e}", "Update Error")

		else:
			# macOS - download to Downloads folder with progress
			progress_data = {'dialog': None, 'cancelled': False}

			def create_progress_dialog():
				progress_data['dialog'] = wx.ProgressDialog(
					"Downloading Update",
					"Downloading FastSM update...",
					maximum=100,
					style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME
				)
				# Skip Raise() on macOS - can cause segfaults

			def update_progress(downloaded, total):
				if progress_data['dialog'] and total > 0:
					percent = int((downloaded / total) * 100)
					mb_downloaded = downloaded / (1024 * 1024)
					mb_total = total / (1024 * 1024)
					def do_update():
						if progress_data['dialog']:
							cont, _ = progress_data['dialog'].Update(
								percent,
								f"Downloading: {mb_downloaded:.1f} MB / {mb_total:.1f} MB"
							)
							if not cont:
								progress_data['cancelled'] = True
					wx.CallAfter(do_update)

			def close_progress_dialog():
				if progress_data['dialog']:
					progress_data['dialog'].Destroy()
					progress_data['dialog'] = None

			event = threading.Event()
			def create_and_signal():
				create_progress_dialog()
				event.set()
			wx.CallAfter(create_and_signal)
			event.wait()

			try:
				local_filename = url.split('/')[-1]
				local_filename = os.path.expanduser("~/Downloads/" + local_filename)
				self.download_file_to(url, local_filename, progress_callback=update_progress)

				if progress_data['cancelled']:
					wx.CallAfter(close_progress_dialog)
					speak.speak("Download cancelled.")
					if os.path.exists(local_filename):
						os.remove(local_filename)
					return

				wx.CallAfter(close_progress_dialog)
				speak.speak("Download complete.")
				self.alert_from_thread(f"FastSM has been downloaded to:\n{local_filename}\n\nPlease open the DMG file and drag FastSM to your Applications folder to complete the update.", "Update Downloaded")
			except Exception as e:
				wx.CallAfter(close_progress_dialog)
				speak.speak(f"Download failed: {e}")
				self.alert_from_thread(f"Failed to download update: {e}", "Download Error")

	def _download_installer_update(self, url, temp_dir):
		"""Download and run installer for installed versions of the app."""
		import speak

		installer_path = os.path.join(temp_dir, "FastSM-Setup.exe")

		# Create and show progress dialog from main thread
		progress_data = {'dialog': None, 'cancelled': False}

		def create_progress_dialog():
			progress_data['dialog'] = wx.ProgressDialog(
				"Downloading Update",
				"Downloading FastSM installer...",
				maximum=100,
				style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME
			)
			progress_data['dialog'].Raise()

		def update_progress(downloaded, total):
			if progress_data['dialog'] and total > 0:
				percent = int((downloaded / total) * 100)
				mb_downloaded = downloaded / (1024 * 1024)
				mb_total = total / (1024 * 1024)
				def do_update():
					if progress_data['dialog']:
						cont, _ = progress_data['dialog'].Update(
							percent,
							f"Downloading: {mb_downloaded:.1f} MB / {mb_total:.1f} MB"
						)
						if not cont:
							progress_data['cancelled'] = True
				wx.CallAfter(do_update)

		def close_progress_dialog():
			if progress_data['dialog']:
				progress_data['dialog'].Destroy()
				progress_data['dialog'] = None

		# Create dialog on main thread and wait
		event = threading.Event()
		def create_and_signal():
			create_progress_dialog()
			event.set()
		wx.CallAfter(create_and_signal)
		event.wait()

		try:
			# Remove old installer if it exists
			if os.path.exists(installer_path):
				os.remove(installer_path)

			# Download the installer
			self.download_file_to(url, installer_path, progress_callback=update_progress)

			if progress_data['cancelled']:
				wx.CallAfter(close_progress_dialog)
				speak.speak("Download cancelled.")
				if os.path.exists(installer_path):
					os.remove(installer_path)
				return

			wx.CallAfter(close_progress_dialog)
			speak.speak("Download complete. Running installer...")

			# Run the installer silently and close the app
			# /SILENT shows progress but no user interaction
			# /VERYSILENT shows nothing at all
			# /CLOSEAPPLICATIONS closes the running app automatically
			# /RESTARTAPPLICATIONS restarts after install
			import subprocess
			subprocess.Popen([
				installer_path,
				'/SILENT',
				'/CLOSEAPPLICATIONS',
				'/RESTARTAPPLICATIONS'
			], creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)

			# Close the app to allow installer to update files
			from GUI import main
			wx.CallAfter(main.window.OnClose)

		except Exception as e:
			wx.CallAfter(close_progress_dialog)
			speak.speak(f"Update failed: {e}")
			self.alert_from_thread(f"Failed to download or run installer: {e}", "Update Error")

	def download_file_to(self, url, dest_path, progress_callback=None):
		"""Download a file to a specific path with optional progress callback.

		Args:
			url: URL to download from
			dest_path: Local path to save file
			progress_callback: Optional function(downloaded, total) called periodically
		"""
		with requests.get(url, stream=True, timeout=30, headers={"User-Agent": f"{name}/{version}"}) as r:
			r.raise_for_status()
			total_size = int(r.headers.get('content-length', 0))
			downloaded = 0
			# Use 1MB chunks to reduce I/O overhead and improve performance
			chunk_size = 1024 * 1024
			with open(dest_path, 'wb') as f:
				for chunk in r.iter_content(chunk_size=chunk_size):
					if chunk:
						f.write(chunk)
						downloaded += len(chunk)
						if progress_callback:
							progress_callback(downloaded, total_size)


# Convenience function to get the app instance
def get_app():
	return Application.get_instance()
