import sys
import shutil
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

		threading.Thread(target=self.cfu).start()
		self.prefs = config.Config(name="FastSM", autosave=True)
		# In portable mode, userdata folder is already app-specific, don't add /FastSM
		if config.is_portable_mode():
			self.confpath = self.prefs._user_config_home
		else:
			self.confpath = self.prefs._user_config_home + "/FastSM"

		if platform.system() == "Darwin":
			try:
				f = open(self.confpath + "/errors.log", "a")
				sys.stderr = f
			except:
				pass

		# Only copy default sounds if they don't exist or app version changed
		sounds_version_file = self.confpath + "/sounds/.version"
		sounds_need_update = False
		if not os.path.exists(self.confpath + "/sounds/default"):
			sounds_need_update = True
		elif os.path.exists(sounds_version_file):
			try:
				with open(sounds_version_file, 'r') as f:
					if f.read().strip() != version:
						sounds_need_update = True
			except:
				sounds_need_update = True
		else:
			# No version file - assume needs update for safety
			sounds_need_update = True

		if sounds_need_update:
			if os.path.exists(self.confpath + "/sounds/default"):
				shutil.rmtree(self.confpath + "/sounds/default")
			if not os.path.exists(self.confpath + "/sounds"):
				os.makedirs(self.confpath + "/sounds")
			if platform.system() == "Darwin":
				shutil.copytree("/applications/fastsm.app/sounds/default", self.confpath + "/sounds/default")
			else:
				shutil.copytree("sounds/default", self.confpath + "/sounds/default")
			# Write version file
			try:
				with open(sounds_version_file, 'w') as f:
					f.write(version)
			except:
				pass

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
		self.prefs.notificationTemplate = self.prefs.get("notificationTemplate", "$account.display_name$ (@$account.acct$) $type$")
		self.prefs.messageTemplate = self.prefs.get("messageTemplate", "$account.display_name$: $text$ $created_at$")
		self.prefs.userTemplate = self.prefs.get("userTemplate", "$display_name$ (@$acct$): $followers_count$ followers, $following_count$ following, $statuses_count$ posts. Bio: $note$")
		self.prefs.accounts = self.prefs.get("accounts", 1)
		self.prefs.errors = self.prefs.get("errors", True)
		self.prefs.streaming = self.prefs.get("streaming", False)
		self.prefs.invisible = self.prefs.get("invisible", False)
		self.prefs.invisible_sync = self.prefs.get("invisible_sync", True)
		self.prefs.update_time = self.prefs.get("update_time", 2)
		self.prefs.volume = self.prefs.get("volume", 1.0)
		self.prefs.count = self.prefs.get("count", 40)
		self.prefs.repeat = self.prefs.get("repeat", False)
		self.prefs.demojify = self.prefs.get("demojify", False)
		self.prefs.demojify_post = self.prefs.get("demojify_post", False)
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
		self.prefs.load_all_previous = self.prefs.get("load_all_previous", False)  # Keep loading previous until timeline is fully loaded
		self.prefs.earcon_audio = self.prefs.get("earcon_audio", True)
		self.prefs.earcon_top = self.prefs.get("earcon_top", False)
		self.prefs.wrap = self.prefs.get("wrap", False)
		# Content warning handling: 'hide' = show CW only, 'show' = show CW + text, 'ignore' = show text only
		self.prefs.cw_mode = self.prefs.get("cw_mode", "hide")

		if self.prefs.invisible:
			main.window.register_keys()

		# User cache is now in-memory only per-account, no global cache needed
		self.users = []

		self.load_timeline_settings()

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

	def add_session(self, index=None):
		"""Add a new account session."""
		import mastodon_api as t
		if index is None:
			index = len(self.accounts)
		self.accounts.append(t.mastodon(self, index))

	def _is_account_configured(self, index):
		"""Check if an account has credentials saved (no dialogs needed)."""
		import config
		try:
			# In portable mode, don't add FastSM prefix (userdata is already app-specific)
			if config.is_portable_mode():
				prefs = config.Config(name="account"+str(index), autosave=False)
			else:
				prefs = config.Config(name="FastSM/account"+str(index), autosave=False)
			platform_type = prefs.get("platform_type", "")

			if platform_type == "bluesky":
				# Bluesky needs handle and password
				return bool(prefs.get("bluesky_handle", "")) and bool(prefs.get("bluesky_password", ""))
			else:
				# Mastodon needs instance URL and access token
				return bool(prefs.get("instance_url", "")) and bool(prefs.get("access_token", ""))
		except:
			return False

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

	def process_status(self, s, return_only_text=False, template="", ignore_cw=False):
		"""Process a Mastodon status for display"""
		if hasattr(s, 'content'):
			text = self.strip_html(s.content)
		else:
			text = ""

		if hasattr(s, 'reblog') and s.reblog:
			# For reblogs, get text from reblogged status (which includes its media descriptions)
			text = self.process_status(s.reblog, True, ignore_cw=ignore_cw)
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

			# Add media descriptions to text (only for non-reblogs to avoid duplication)
			if hasattr(s, 'media_attachments') and s.media_attachments:
				for media in s.media_attachments:
					media_type = getattr(media, 'type', 'media') or 'media'
					type_display = media_type.upper() if media_type == 'gifv' else media_type.capitalize()
					description = getattr(media, 'description', None) or getattr(media, 'alt', None)
					if description:
						text += f" ({type_display}) description: {description}"
					else:
						text += f" ({type_display}) with no description"

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

		if return_only_text:
			return text

		# Handle quotes: format as "Person: their comment. Quoting person2: quoted text. time"
		quote_formatted = ""
		if hasattr(s, 'quote') and s.quote:
			quote_text = self.process_status(s.quote, True)
			quote_wrapped = StatusWrapper(s.quote, quote_text)
			quote_formatted = self.template_to_string(quote_wrapped, self.prefs.quoteTemplate)

		wrapped = StatusWrapper(s, text)

		if quote_formatted:
			# For quotes, remove timestamp from main template and add it at the very end
			main_template = template if template else self.prefs.postTemplate
			# Remove $created_at$ from main template for quote posts
			temp_template = main_template.replace(" $created_at$", "").replace("$created_at$ ", "").replace("$created_at$", "")
			result = self.template_to_string(wrapped, temp_template)
			result += " " + quote_formatted
			# Add timestamp at the very end
			created_at = getattr(s, 'created_at', None)
			if created_at:
				result += " " + self.parse_date(created_at)
		else:
			result = self.template_to_string(wrapped, template)

		return result

	def process_notification(self, n):
		"""Process a Mastodon notification for display"""
		import speak
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
		}

		notif_type = getattr(n, 'type', 'unknown')
		account = getattr(n, 'account', None)
		status = getattr(n, 'status', None)

		label = type_labels.get(notif_type, notif_type)

		if account:
			display_name = getattr(account, 'display_name', '') or getattr(account, 'acct', '')
			acct = getattr(account, 'acct', '')
		else:
			display_name = "Unknown"
			acct = ""

		if status:
			status_text = self.strip_html(getattr(status, 'content', ''))
			if len(status_text) > 100:
				status_text = status_text[:100] + "..."
			result = f"{display_name} (@{acct}) {label}: {status_text}"
		else:
			result = f"{display_name} (@{acct}) {label}"

		created_at = getattr(n, 'created_at', None)
		if created_at:
			result += " " + self.parse_date(created_at)

		return result

	def process_conversation(self, c):
		"""Process a Mastodon conversation for display"""
		accounts = getattr(c, 'accounts', [])
		last_status = getattr(c, 'last_status', None)

		if accounts:
			participants = ", ".join([a.display_name or a.acct for a in accounts[:3]])
			if len(accounts) > 3:
				participants += f" and {len(accounts) - 3} others"
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
		"""Find URLs in a Mastodon status"""
		urls = []

		if hasattr(s, 'card') and s.card:
			if hasattr(s.card, 'url') and s.card.url:
				urls.append(s.card.url)

		if hasattr(s, 'media_attachments'):
			for media in s.media_attachments:
				if hasattr(media, 'url') and media.url:
					urls.append(media.url)

		if hasattr(s, 'content'):
			text_urls = self.find_urls_in_text(self.strip_html(s.content))
			for url in text_urls:
				if url not in urls:
					urls.append(url)

		return urls

	def template_to_string(self, s, template=""):
		"""Format a status using a template"""
		if template == "":
			template = self.prefs.postTemplate
		temp = template.split(" ")
		for i in range(len(temp)):
			if "$" in temp[i]:
				t = temp[i].split("$")
				r = t[1]
				if "." in r:
					q = r.split(".")
					# Support multi-level attribute access (e.g., reblog.account.display_name)
					try:
						obj = s
						for attr in q:
							if obj is None:
								break
							obj = getattr(obj, attr, None)
						if obj is not None:
							# Check if we need to demojify
							last_attr = q[-1]
							if (last_attr in ('name', 'display_name')) and self.prefs.demojify:
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
					except Exception as e:
						pass  # Leave placeholder if we can't resolve it
				else:
					if hasattr(s, t[1]):
						try:
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
			# Define API callback
			def api_lookup(n):
				if not use_api:
					return None
				try:
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
		result = dlg.ShowModal()
		dlg.Destroy()
		if result == wx.ID_YES:
			return 1
		else:
			return 2

	def warn(self, message, caption='Warning!', parent=None):
		dlg = wx.MessageDialog(parent, message, caption, wx.OK | wx.ICON_WARNING)
		dlg.ShowModal()
		dlg.Destroy()

	def alert(self, message, caption="", parent=None):
		dlg = wx.MessageDialog(parent, message, caption, wx.OK)
		dlg.ShowModal()
		dlg.Destroy()

	def cfu(self, silent=True):
		try:
			latest = json.loads(requests.get("https://api.github.com/repos/masonasons/FastSM/releases/latest", {"accept": "application/vnd.github.v3+json"}).content.decode())
			if version < latest['tag_name']:
				ud = self.question("Update available: " + latest['tag_name'], "There is an update available. Your version: " + version + ". Latest version: " + latest['tag_name'] + ". Description: " + latest['body'] + "\r\nDo you want to open the direct download link?")
				if ud == 1:
					for i in latest['assets']:
						if "fastsm" in i['name'].lower() and "windows" in i['name'].lower() and platform.system() == "Windows" or "fastsm" in i['name'].lower() and platform.system() == "Darwin":
							threading.Thread(target=self.download_update, args=[i['browser_download_url'],], daemon=True).start()
							return
					self.alert("A download for this version could not be found for your platform. Check back soon.", "Error")
			else:
				if not silent:
					self.alert("No updates available! The latest version of the program is " + latest['tag_name'], "No update available")
		except:
			pass

	def demojify(self, text):
		text = str(text).encode("ascii", "ignore")
		text = text.decode()
		return text

	def handle_error(self, error, name="Unknown"):
		"""Handle API errors from Mastodon or Bluesky"""
		import speak
		import sound
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
			os.system(f"open {url}")

	def download_file(self, url):
		local_filename = url.split('/')[-1]
		if platform.system() == "Darwin":
			local_filename = os.path.expanduser("~/Downloads/" + local_filename)
		with requests.get(url, stream=True) as r:
			r.raise_for_status()
			with open(local_filename, 'wb') as f:
				for chunk in r.iter_content(chunk_size=8192):
					f.write(chunk)
		return local_filename

	def download_update(self, url):
		import speak
		try:
			if platform.system() != "Darwin" and os.path.exists("FastSM.zip"):
				os.remove("FastSM.zip")
		except:
			self.alert("The current version of FastSM.zip could not be removed.", "Error")
			return
		speak.speak("Downloading.")
		filename = self.download_file(url)
		if platform.system() == "Windows":
			os.system("updater.exe")
		else:
			self.alert("FastSM has been downloaded to your Downloads directory. Due to Apple restrictions, we cannot update FastSM for you on this platform. You must do this yourself.", "Alert")


# Convenience function to get the app instance
def get_app():
	return Application.get_instance()
