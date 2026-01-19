import timeline
import platform
import os, sys
import wx
from . import main, theme
from application import get_app

class general(wx.Panel, wx.Dialog):
	def __init__(self, parent):
		super(general, self).__init__(parent)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.ask_dismiss=wx.CheckBox(self, -1, "Ask before dismissing timelines")
		self.main_box.Add(self.ask_dismiss, 0, wx.ALL, 10)
		self.ask_dismiss.SetValue(get_app().prefs.ask_dismiss)
		self.earcon_audio=wx.CheckBox(self, -1, "Play a sound when a post contains media")
		self.main_box.Add(self.earcon_audio, 0, wx.ALL, 10)
		self.earcon_audio.SetValue(get_app().prefs.earcon_audio)
		self.earcon_top=wx.CheckBox(self, -1, "Play a sound when you navigate to a timeline that may have new items")
		self.main_box.Add(self.earcon_top, 0, wx.ALL, 10)
		self.earcon_top.SetValue(get_app().prefs.earcon_top)
		self.demojify=wx.CheckBox(self, -1, "Remove emojis and other unicode characters from display names")
		self.main_box.Add(self.demojify, 0, wx.ALL, 10)
		self.demojify.SetValue(get_app().prefs.demojify)
		self.demojify_post=wx.CheckBox(self, -1, "Remove emojis and other unicode characters from post text")
		self.main_box.Add(self.demojify_post, 0, wx.ALL, 10)
		self.demojify_post.SetValue(get_app().prefs.demojify_post)
		self.reversed=wx.CheckBox(self, -1, "Reverse timelines (newest on bottom)")
		self.main_box.Add(self.reversed, 0, wx.ALL, 10)
		self.reversed.SetValue(get_app().prefs.reversed)
		self.wrap=wx.CheckBox(self, -1, "Word wrap in text fields")
		self.main_box.Add(self.wrap, 0, wx.ALL, 10)
		self.wrap.SetValue(get_app().prefs.wrap)
		self.errors=wx.CheckBox(self, -1, "Play sound and speak message for errors")
		self.main_box.Add(self.errors, 0, wx.ALL, 10)
		self.errors.SetValue(get_app().prefs.errors)
		self.autoOpenSingleURL=wx.CheckBox(self, -1, "When getting URLs from a post, automatically open the first URL if it is the only one")
		self.main_box.Add(self.autoOpenSingleURL, 0, wx.ALL, 10)
		self.autoOpenSingleURL.SetValue(get_app().prefs.autoOpenSingleURL)
		self.use24HourTime=wx.CheckBox(self, -1, "Use 24-hour time for post timestamps")
		self.main_box.Add(self.use24HourTime, 0, wx.ALL, 10)
		self.use24HourTime.SetValue(get_app().prefs.use24HourTime)
		self.auto_open_audio_player=wx.CheckBox(self, -1, "Automatically open audio player when media starts playing")
		self.main_box.Add(self.auto_open_audio_player, 0, wx.ALL, 10)
		self.auto_open_audio_player.SetValue(get_app().prefs.auto_open_audio_player)
		self.stop_audio_on_close=wx.CheckBox(self, -1, "Stop audio playback when audio player closes")
		self.main_box.Add(self.stop_audio_on_close, 0, wx.ALL, 10)
		self.stop_audio_on_close.SetValue(get_app().prefs.stop_audio_on_close)

		# Content warning handling - use accessible name instead of separate label
		cw_label = wx.StaticText(self, -1, "Content warnings:")
		self.main_box.Add(cw_label, 0, wx.LEFT | wx.TOP, 10)
		self.cw_mode = wx.Choice(self, -1, choices=[
			"Hide post text (show CW only)",
			"Show CW followed by post text",
			"Ignore CW (show post text only)"
		], name="Content warnings")
		cw_mode_map = {'hide': 0, 'show': 1, 'ignore': 2}
		self.cw_mode.SetSelection(cw_mode_map.get(get_app().prefs.cw_mode, 0))
		self.main_box.Add(self.cw_mode, 0, wx.ALL, 10)
		self.SetSizer(self.main_box)


class templates(wx.Panel, wx.Dialog):
	def __init__(self, parent):
		super(templates, self).__init__(parent)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.postTemplate_label = wx.StaticText(self, -1, "Post template")
		self.main_box.Add(self.postTemplate_label, 0, wx.LEFT | wx.TOP, 10)
		self.postTemplate = wx.TextCtrl(self, -1, "", name="Post template")
		self.main_box.Add(self.postTemplate, 0, wx.EXPAND | wx.ALL, 10)
		self.postTemplate.AppendText(get_app().prefs.postTemplate)
		self.quoteTemplate_label = wx.StaticText(self, -1, "Quote template")
		self.main_box.Add(self.quoteTemplate_label, 0, wx.LEFT | wx.TOP, 10)
		self.quoteTemplate = wx.TextCtrl(self, -1, "", name="Quote template")
		self.main_box.Add(self.quoteTemplate, 0, wx.EXPAND | wx.ALL, 10)
		self.quoteTemplate.AppendText(get_app().prefs.quoteTemplate)
		self.boostTemplate_label = wx.StaticText(self, -1, "Boost template")
		self.main_box.Add(self.boostTemplate_label, 0, wx.LEFT | wx.TOP, 10)
		self.boostTemplate = wx.TextCtrl(self, -1, "", name="Boost template")
		self.main_box.Add(self.boostTemplate, 0, wx.EXPAND | wx.ALL, 10)
		self.boostTemplate.AppendText(get_app().prefs.boostTemplate)
		self.copyTemplate_label = wx.StaticText(self, -1, "Copy template")
		self.main_box.Add(self.copyTemplate_label, 0, wx.LEFT | wx.TOP, 10)
		self.copyTemplate = wx.TextCtrl(self, -1, "", name="Copy template")
		self.main_box.Add(self.copyTemplate, 0, wx.EXPAND | wx.ALL, 10)
		self.copyTemplate.AppendText(get_app().prefs.copyTemplate)
		self.messageTemplate_label = wx.StaticText(self, -1, "Direct Message template")
		self.main_box.Add(self.messageTemplate_label, 0, wx.LEFT | wx.TOP, 10)
		self.messageTemplate = wx.TextCtrl(self, -1, "", name="Direct Message template")
		self.main_box.Add(self.messageTemplate, 0, wx.EXPAND | wx.ALL, 10)
		self.messageTemplate.AppendText(get_app().prefs.messageTemplate)
		self.userTemplate_label = wx.StaticText(self, -1, "User template")
		self.main_box.Add(self.userTemplate_label, 0, wx.LEFT | wx.TOP, 10)
		self.userTemplate = wx.TextCtrl(self, -1, "", name="User template")
		self.main_box.Add(self.userTemplate, 0, wx.EXPAND | wx.ALL, 10)
		self.userTemplate.AppendText(get_app().prefs.userTemplate)
		self.notificationTemplate_label = wx.StaticText(self, -1, "Notification template")
		self.main_box.Add(self.notificationTemplate_label, 0, wx.LEFT | wx.TOP, 10)
		self.notificationTemplate = wx.TextCtrl(self, -1, "", name="Notification template")
		self.main_box.Add(self.notificationTemplate, 0, wx.EXPAND | wx.ALL, 10)
		self.notificationTemplate.AppendText(get_app().prefs.notificationTemplate)
		self.SetSizer(self.main_box)

class advanced(wx.Panel, wx.Dialog):
	def _get_available_keymaps(self):
		"""Get list of available keymaps from bundled and user config folders."""
		keymaps = ['default']  # Always have default

		# Check bundled keymaps folder
		if os.path.exists("keymaps"):
			for f in os.listdir("keymaps"):
				if f.endswith(".keymap") and not f.startswith("."):
					name = f[:-7]  # Remove .keymap extension
					if name != "default" and name not in keymaps:
						keymaps.append(name)

		# Check user config keymaps folder
		user_keymaps_path = os.path.join(get_app().confpath, "keymaps")
		if os.path.exists(user_keymaps_path):
			for f in os.listdir(user_keymaps_path):
				if f.endswith(".keymap") and not f.startswith("."):
					name = f[:-7]  # Remove .keymap extension
					if name != "default" and name not in keymaps:
						keymaps.append(name)

		return keymaps

	def __init__(self, parent):
		super(advanced, self).__init__(parent)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		if platform.system()!="Darwin":
			self.invisible=wx.CheckBox(self, -1, "Enable invisible interface")
			self.main_box.Add(self.invisible, 0, wx.ALL, 10)
			self.invisible.SetValue(get_app().prefs.invisible)
			self.invisible_sync=wx.CheckBox(self, -1, "Sync invisible interface with UI (uncheck for reduced lag in invisible interface)")
			self.main_box.Add(self.invisible_sync, 0, wx.ALL, 10)
			self.invisible_sync.SetValue(get_app().prefs.invisible_sync)
			self.repeat=wx.CheckBox(self, -1, "Repeat items at edges of invisible interface")
			self.main_box.Add(self.repeat, 0, wx.ALL, 10)
			self.repeat.SetValue(get_app().prefs.repeat)

			# Keymap selection
			keymap_label = wx.StaticText(self, -1, "Keymap:")
			self.main_box.Add(keymap_label, 0, wx.LEFT | wx.TOP, 10)
			self.keymaps = self._get_available_keymaps()
			self.keymap_choice = wx.Choice(self, -1, choices=self.keymaps, name="Keymap")
			current_keymap = get_app().prefs.keymap
			if current_keymap in self.keymaps:
				self.keymap_choice.SetSelection(self.keymaps.index(current_keymap))
			else:
				self.keymap_choice.SetSelection(0)
			self.main_box.Add(self.keymap_choice, 0, wx.ALL, 10)
		self.position=wx.CheckBox(self, -1, "Speak position information when navigating between timelines of invisible interface and switching timelines")
		self.main_box.Add(self.position, 0, wx.ALL, 10)
		self.position.SetValue(get_app().prefs.position)
		self.update_time_label = wx.StaticText(self, -1, "Update time, in minutes")
		self.main_box.Add(self.update_time_label, 0, wx.LEFT | wx.TOP, 10)
		self.update_time = wx.TextCtrl(self, -1, "", name="Update time, in minutes")
		self.main_box.Add(self.update_time, 0, wx.EXPAND | wx.ALL, 10)
		self.update_time.AppendText(str(get_app().prefs.update_time))
		self.user_limit_label = wx.StaticText(self, -1, "Max API calls when fetching users in user viewer")
		self.main_box.Add(self.user_limit_label, 0, wx.LEFT | wx.TOP, 10)
		self.user_limit = wx.TextCtrl(self, -1, "", name="Max API calls when fetching users in user viewer")
		self.main_box.Add(self.user_limit, 0, wx.EXPAND | wx.ALL, 10)
		self.user_limit.AppendText(str(get_app().prefs.user_limit))
		self.count_label = wx.StaticText(self, -1, "Number of posts to fetch per call (Maximum is 40)")
		self.main_box.Add(self.count_label, 0, wx.LEFT | wx.TOP, 10)
		self.count = wx.TextCtrl(self, -1, "", name="Number of posts to fetch per call (Maximum is 40)")
		self.main_box.Add(self.count, 0, wx.EXPAND | wx.ALL, 10)
		self.count.AppendText(str(get_app().prefs.count))
		self.fetch_pages_label = wx.StaticText(self, -1, "Number of API calls to make when loading timelines (1-10)")
		self.main_box.Add(self.fetch_pages_label, 0, wx.LEFT | wx.TOP, 10)
		self.fetch_pages = wx.TextCtrl(self, -1, "", name="Number of API calls to make when loading timelines (1-10)")
		self.main_box.Add(self.fetch_pages, 0, wx.EXPAND | wx.ALL, 10)
		self.fetch_pages.AppendText(str(get_app().prefs.fetch_pages))
		self.single_api_on_startup=wx.CheckBox(self, -1, "Use only one API call on initial timeline loads (faster startup)")
		self.main_box.Add(self.single_api_on_startup, 0, wx.ALL, 10)
		self.single_api_on_startup.SetValue(get_app().prefs.single_api_on_startup)
		self.streaming=wx.CheckBox(self, -1, "Enable streaming for home and notifications (Requires restart to disable)")
		self.main_box.Add(self.streaming, 0, wx.ALL, 10)
		self.streaming.SetValue(get_app().prefs.streaming)
		self.load_all_previous=wx.CheckBox(self, -1, "Load all previous posts until timeline is fully loaded")
		self.main_box.Add(self.load_all_previous, 0, wx.ALL, 10)
		self.load_all_previous.SetValue(get_app().prefs.load_all_previous)
		self.sync_timeline_position=wx.CheckBox(self, -1, "Sync home timeline position with Mastodon (Mastodon only)")
		self.main_box.Add(self.sync_timeline_position, 0, wx.ALL, 10)
		self.sync_timeline_position.SetValue(get_app().prefs.sync_timeline_position)
		self.check_for_updates=wx.CheckBox(self, -1, "Check for updates on startup")
		self.main_box.Add(self.check_for_updates, 0, wx.ALL, 10)
		self.check_for_updates.SetValue(get_app().prefs.check_for_updates)

		# Dark mode setting
		dark_mode_label = wx.StaticText(self, -1, "Dark mode:")
		self.main_box.Add(dark_mode_label, 0, wx.LEFT | wx.TOP, 10)
		self.dark_mode = wx.Choice(self, -1, choices=[
			"Off",
			"On",
			"Auto (follow system)"
		], name="Dark mode")
		dark_mode_map = {'off': 0, 'on': 1, 'auto': 2}
		self.dark_mode.SetSelection(dark_mode_map.get(get_app().prefs.dark_mode, 0))
		self.main_box.Add(self.dark_mode, 0, wx.ALL, 10)

		# yt-dlp path
		ytdlp_label = wx.StaticText(self, -1, "yt-dlp path (for YouTube/Twitter audio, leave blank to use bundled):")
		self.main_box.Add(ytdlp_label, 0, wx.LEFT | wx.TOP, 10)
		ytdlp_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.ytdlp_path = wx.TextCtrl(self, -1, get_app().prefs.ytdlp_path, name="yt-dlp path")
		ytdlp_sizer.Add(self.ytdlp_path, 1, wx.EXPAND | wx.RIGHT, 5)
		self.ytdlp_browse = wx.Button(self, -1, "Browse...")
		self.ytdlp_browse.Bind(wx.EVT_BUTTON, self.on_ytdlp_browse)
		ytdlp_sizer.Add(self.ytdlp_browse, 0, wx.RIGHT, 5)
		self.ytdlp_download = wx.Button(self, -1, "Download/Update")
		self.ytdlp_download.Bind(wx.EVT_BUTTON, self.on_ytdlp_download)
		ytdlp_sizer.Add(self.ytdlp_download, 0)
		self.main_box.Add(ytdlp_sizer, 0, wx.EXPAND | wx.ALL, 10)

		# VLC download button
		vlc_sizer = wx.BoxSizer(wx.HORIZONTAL)
		vlc_label = wx.StaticText(self, -1, "VLC libraries (required for media playback):")
		self.main_box.Add(vlc_label, 0, wx.LEFT | wx.TOP, 10)
		self.vlc_download = wx.Button(self, -1, "Download VLC")
		self.vlc_download.Bind(wx.EVT_BUTTON, self.on_vlc_download)
		vlc_sizer.Add(self.vlc_download, 0)
		self.main_box.Add(vlc_sizer, 0, wx.ALL, 10)

		self.SetSizer(self.main_box)

	def on_ytdlp_browse(self, event):
		"""Browse for yt-dlp executable."""
		with wx.FileDialog(self, "Select yt-dlp executable",
			wildcard="Executable files (*.exe)|*.exe|All files (*.*)|*.*",
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
			if dlg.ShowModal() == wx.ID_OK:
				self.ytdlp_path.SetValue(dlg.GetPath())

	def on_ytdlp_download(self, event):
		"""Download or update yt-dlp."""
		import threading
		import subprocess
		import requests
		import os
		import sys
		import stat
		import speak

		# Determine asset name and local filename based on platform
		if sys.platform == 'win32':
			asset_name = 'yt-dlp.exe'
			local_name = 'yt-dlp.exe'
		elif sys.platform == 'darwin':
			asset_name = 'yt-dlp_macos'  # GitHub release name
			local_name = 'yt-dlp'  # Save as just yt-dlp
		else:
			asset_name = 'yt-dlp'
			local_name = 'yt-dlp'

		# Determine target path - use config directory
		custom_path = self.ytdlp_path.GetValue().strip()
		if custom_path and os.path.isfile(custom_path):
			# Update existing custom path
			ytdlp_path = custom_path
		else:
			# Download to config directory (sound.py checks this location)
			ytdlp_path = os.path.join(get_app().confpath, local_name)

		def do_download_or_update():
			try:
				if os.path.isfile(ytdlp_path):
					# Update existing yt-dlp
					speak.speak("Updating yt-dlp...")
					result = subprocess.run(
						[ytdlp_path, '-U'],
						capture_output=True,
						text=True,
						timeout=60,
						creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
					)
					if result.returncode == 0:
						speak.speak("yt-dlp updated successfully")
					else:
						# If update fails, might need to download fresh
						speak.speak("Update failed, downloading fresh copy...")
						download_ytdlp(ytdlp_path)
				else:
					# Download new yt-dlp
					download_ytdlp(ytdlp_path)
			except Exception as e:
				wx.CallAfter(wx.MessageBox, f"Error: {e}", "yt-dlp Download", wx.OK | wx.ICON_ERROR)

		def download_ytdlp(dest_path):
			speak.speak("Downloading yt-dlp...")
			try:
				# Get latest release URL from GitHub API
				api_url = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
				response = requests.get(api_url, timeout=30)
				response.raise_for_status()
				release = response.json()

				# Find the appropriate asset for this platform
				exe_url = None
				for asset in release.get('assets', []):
					if asset['name'] == asset_name:
						exe_url = asset['browser_download_url']
						break

				if not exe_url:
					speak.speak(f"Could not find {asset_name} in latest release")
					return

				# Download the executable
				exe_response = requests.get(exe_url, timeout=120, stream=True)
				exe_response.raise_for_status()

				# Ensure config directory exists
				os.makedirs(os.path.dirname(dest_path), exist_ok=True)

				with open(dest_path, 'wb') as f:
					for chunk in exe_response.iter_content(chunk_size=8192):
						f.write(chunk)

				# Make executable on Unix systems
				if sys.platform != 'win32':
					os.chmod(dest_path, os.stat(dest_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

				speak.speak("yt-dlp downloaded successfully")
			except Exception as e:
				speak.speak(f"Download failed: {e}")

		# Run in background thread
		threading.Thread(target=do_download_or_update, daemon=True).start()

	def on_vlc_download(self, event):
		"""Download VLC libraries if not found."""
		import threading
		import requests
		import zipfile
		import io
		import os
		import sys
		import speak

		def find_existing_vlc():
			"""Check all locations where VLC could be installed."""
			# Check bundled location (app folder)
			if getattr(sys, 'frozen', False):
				if sys.platform == 'darwin':
					bundled = os.path.join(os.path.dirname(sys.executable), '..', 'Resources', 'vlc')
				else:
					bundled = os.path.join(os.path.dirname(sys.executable), 'vlc')
			else:
				bundled = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'vlc')

			if sys.platform == 'win32':
				if os.path.exists(bundled) and os.path.isfile(os.path.join(bundled, 'libvlc.dll')):
					return bundled
			elif os.path.exists(bundled):
				return bundled

			# Check system VLC installation paths
			if sys.platform == 'win32':
				system_paths = [
					os.path.join(os.environ.get('PROGRAMFILES', ''), 'VideoLAN', 'VLC'),
					os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'VideoLAN', 'VLC'),
					'C:\\Program Files\\VideoLAN\\VLC',
					'C:\\Program Files (x86)\\VideoLAN\\VLC',
				]
				for path in system_paths:
					if path and os.path.exists(path) and os.path.isfile(os.path.join(path, 'libvlc.dll')):
						return path
			elif sys.platform == 'darwin':
				system_paths = [
					'/Applications/VLC.app/Contents/MacOS',
					os.path.expanduser('~/Applications/VLC.app/Contents/MacOS'),
				]
				for path in system_paths:
					if os.path.exists(path):
						return path

			return None

		# Determine VLC target path for download
		if getattr(sys, 'frozen', False):
			vlc_path = os.path.join(os.path.dirname(sys.executable), 'vlc')
		else:
			vlc_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'vlc')

		def do_download():
			try:
				# Check if VLC already exists anywhere
				existing = find_existing_vlc()
				if existing:
					speak.speak(f"VLC is already available at {existing}")
					return

				speak.speak("Downloading VLC libraries...")

				# Download the zip file
				vlc_url = "https://masonasons.me/vlc.zip"
				response = requests.get(vlc_url, timeout=120, stream=True)
				response.raise_for_status()

				# Extract to app folder
				speak.speak("Extracting VLC libraries...")
				zip_data = io.BytesIO(response.content)
				with zipfile.ZipFile(zip_data, 'r') as zip_ref:
					zip_ref.extractall(os.path.dirname(vlc_path))

				speak.speak("VLC libraries downloaded and installed successfully")

			except Exception as e:
				speak.speak(f"VLC download failed: {e}")
				wx.CallAfter(wx.MessageBox, f"Error downloading VLC: {e}", "VLC Download", wx.OK | wx.ICON_ERROR)

		# Run in background thread
		threading.Thread(target=do_download, daemon=True).start()

class confirmation(wx.Panel, wx.Dialog):
	def __init__(self, parent):
		super(confirmation, self).__init__(parent)
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		info_label = wx.StaticText(self, -1, "Show confirmation dialogs for the following actions (menu/hotkeys only):")
		self.main_box.Add(info_label, 0, wx.ALL, 10)

		self.confirm_boost=wx.CheckBox(self, -1, "Boosting")
		self.main_box.Add(self.confirm_boost, 0, wx.ALL, 10)
		self.confirm_boost.SetValue(get_app().prefs.confirm_boost)

		self.confirm_unboost=wx.CheckBox(self, -1, "Unboosting")
		self.main_box.Add(self.confirm_unboost, 0, wx.ALL, 10)
		self.confirm_unboost.SetValue(get_app().prefs.confirm_unboost)

		self.confirm_favorite=wx.CheckBox(self, -1, "Favoriting")
		self.main_box.Add(self.confirm_favorite, 0, wx.ALL, 10)
		self.confirm_favorite.SetValue(get_app().prefs.confirm_favorite)

		self.confirm_unfavorite=wx.CheckBox(self, -1, "Unfavoriting")
		self.main_box.Add(self.confirm_unfavorite, 0, wx.ALL, 10)
		self.confirm_unfavorite.SetValue(get_app().prefs.confirm_unfavorite)

		self.confirm_follow=wx.CheckBox(self, -1, "Following")
		self.main_box.Add(self.confirm_follow, 0, wx.ALL, 10)
		self.confirm_follow.SetValue(get_app().prefs.confirm_follow)

		self.confirm_unfollow=wx.CheckBox(self, -1, "Unfollowing")
		self.main_box.Add(self.confirm_unfollow, 0, wx.ALL, 10)
		self.confirm_unfollow.SetValue(get_app().prefs.confirm_unfollow)

		self.confirm_block=wx.CheckBox(self, -1, "Blocking")
		self.main_box.Add(self.confirm_block, 0, wx.ALL, 10)
		self.confirm_block.SetValue(get_app().prefs.confirm_block)

		self.confirm_unblock=wx.CheckBox(self, -1, "Unblocking")
		self.main_box.Add(self.confirm_unblock, 0, wx.ALL, 10)
		self.confirm_unblock.SetValue(get_app().prefs.confirm_unblock)

		self.confirm_mute=wx.CheckBox(self, -1, "Muting")
		self.main_box.Add(self.confirm_mute, 0, wx.ALL, 10)
		self.confirm_mute.SetValue(get_app().prefs.confirm_mute)

		self.confirm_unmute=wx.CheckBox(self, -1, "Unmuting")
		self.main_box.Add(self.confirm_unmute, 0, wx.ALL, 10)
		self.confirm_unmute.SetValue(get_app().prefs.confirm_unmute)

		self.confirm_delete=wx.CheckBox(self, -1, "Deleting posts")
		self.main_box.Add(self.confirm_delete, 0, wx.ALL, 10)
		self.confirm_delete.SetValue(get_app().prefs.confirm_delete)

		self.confirm_bookmark=wx.CheckBox(self, -1, "Bookmarking")
		self.main_box.Add(self.confirm_bookmark, 0, wx.ALL, 10)
		self.confirm_bookmark.SetValue(get_app().prefs.confirm_bookmark)

		self.confirm_unbookmark=wx.CheckBox(self, -1, "Unbookmarking")
		self.main_box.Add(self.confirm_unbookmark, 0, wx.ALL, 10)
		self.confirm_unbookmark.SetValue(get_app().prefs.confirm_unbookmark)
		self.SetSizer(self.main_box)


class ai(wx.Panel, wx.Dialog):
	def __init__(self, parent):
		super(ai, self).__init__(parent)
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		# AI Service selection
		service_label = wx.StaticText(self, -1, "AI Service for image descriptions:")
		self.main_box.Add(service_label, 0, wx.LEFT | wx.TOP, 10)
		self.ai_service = wx.Choice(self, -1, choices=[
			"None (disabled)",
			"OpenAI",
			"Google Gemini"
		], name="AI Service")
		service_map = {'none': 0, 'openai': 1, 'gemini': 2}
		self.ai_service.SetSelection(service_map.get(get_app().prefs.ai_service, 0))
		self.main_box.Add(self.ai_service, 0, wx.ALL, 10)

		# OpenAI API Key
		openai_label = wx.StaticText(self, -1, "OpenAI API Key:")
		self.main_box.Add(openai_label, 0, wx.LEFT | wx.TOP, 10)
		self.openai_api_key = wx.TextCtrl(self, -1, "", style=wx.TE_PASSWORD, name="OpenAI API Key")
		self.openai_api_key.SetValue(get_app().prefs.openai_api_key)
		self.main_box.Add(self.openai_api_key, 0, wx.EXPAND | wx.ALL, 10)

		# OpenAI Model selection
		openai_model_label = wx.StaticText(self, -1, "OpenAI Model:")
		self.main_box.Add(openai_model_label, 0, wx.LEFT | wx.TOP, 10)
		self.openai_models = ["gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"]
		self.openai_model = wx.Choice(self, -1, choices=self.openai_models, name="OpenAI Model")
		current_openai_model = get_app().prefs.openai_model
		if current_openai_model in self.openai_models:
			self.openai_model.SetSelection(self.openai_models.index(current_openai_model))
		else:
			self.openai_model.SetSelection(0)
		self.main_box.Add(self.openai_model, 0, wx.ALL, 10)

		# Gemini API Key
		gemini_label = wx.StaticText(self, -1, "Google Gemini API Key:")
		self.main_box.Add(gemini_label, 0, wx.LEFT | wx.TOP, 10)
		self.gemini_api_key = wx.TextCtrl(self, -1, "", style=wx.TE_PASSWORD, name="Gemini API Key")
		self.gemini_api_key.SetValue(get_app().prefs.gemini_api_key)
		self.main_box.Add(self.gemini_api_key, 0, wx.EXPAND | wx.ALL, 10)

		# Gemini Model selection
		gemini_model_label = wx.StaticText(self, -1, "Gemini Model:")
		self.main_box.Add(gemini_model_label, 0, wx.LEFT | wx.TOP, 10)
		self.gemini_models = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro", "gemini-3-flash-preview", "gemini-3-pro-preview"]
		self.gemini_model = wx.Choice(self, -1, choices=self.gemini_models, name="Gemini Model")
		current_gemini_model = get_app().prefs.gemini_model
		if current_gemini_model in self.gemini_models:
			self.gemini_model.SetSelection(self.gemini_models.index(current_gemini_model))
		else:
			self.gemini_model.SetSelection(0)
		self.main_box.Add(self.gemini_model, 0, wx.ALL, 10)

		# Custom prompt
		prompt_label = wx.StaticText(self, -1, "Image description prompt:")
		self.main_box.Add(prompt_label, 0, wx.LEFT | wx.TOP, 10)
		ai_prompt_style = wx.TE_MULTILINE if getattr(get_app().prefs, 'word_wrap', True) else wx.TE_MULTILINE | wx.TE_DONTWRAP
		self.ai_image_prompt = wx.TextCtrl(self, -1, "", style=ai_prompt_style, size=(-1, 80), name="Image description prompt")
		self.ai_image_prompt.SetValue(get_app().prefs.ai_image_prompt)
		self.main_box.Add(self.ai_image_prompt, 0, wx.EXPAND | wx.ALL, 10)

		self.SetSizer(self.main_box)


class OptionsGui(wx.Dialog):
	def __init__(self):
		wx.Dialog.__init__(self, None, title="Options", size=(350,200), style=wx.DEFAULT_DIALOG_STYLE | wx.TAB_TRAVERSAL)
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self, style=wx.TAB_TRAVERSAL)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.notebook = wx.Notebook(self.panel, name="Options tabs")
		self.general=general(self.notebook)
		self.notebook.AddPage(self.general, "General")
		self.templates=templates(self.notebook)
		self.notebook.AddPage(self.templates, "Templates")
		self.advanced=advanced(self.notebook)
		self.notebook.AddPage(self.advanced, "Advanced")
		self.confirmation=confirmation(self.notebook)
		self.notebook.AddPage(self.confirmation, "Confirmation")
		self.ai_tab=ai(self.notebook)
		self.notebook.AddPage(self.ai_tab, "AI")
		self.main_box.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)
		self.ok = wx.Button(self.panel, wx.ID_OK, "&OK")
		self.ok.SetDefault()
		self.ok.Bind(wx.EVT_BUTTON, self.OnOK)
		self.main_box.Add(self.ok, 0, wx.ALL, 10)
		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)
		self.panel.SetSizer(self.main_box)
		self.panel.Layout()
		theme.apply_theme(self)
		# On macOS, focus the notebook first so user can tab through tabs
		if platform.system() == "Darwin":
			self.notebook.SetFocus()
		else:
			self.general.ask_dismiss.SetFocus()

	def OnOK(self, event):
		refresh=False
		get_app().prefs.use24HourTime = self.general.use24HourTime.GetValue()
		get_app().prefs.ask_dismiss=self.general.ask_dismiss.GetValue()
		if platform.system()!="Darwin":
			get_app().prefs.invisible=self.advanced.invisible.GetValue()
			get_app().prefs.invisible_sync=self.advanced.invisible_sync.GetValue()
			get_app().prefs.repeat=self.advanced.repeat.GetValue()
			get_app().prefs.invisible_sync=self.advanced.invisible_sync.GetValue()

			# Handle keymap change - re-register if keymap changed while invisible interface is enabled
			new_keymap = self.advanced.keymaps[self.advanced.keymap_choice.GetSelection()]
			keymap_changed = get_app().prefs.keymap != new_keymap
			get_app().prefs.keymap = new_keymap

			if get_app().prefs.invisible and not main.window.invisible:
				main.window.register_keys()
			elif not get_app().prefs.invisible and main.window.invisible:
				main.window.unregister_keys()
			elif keymap_changed and main.window.invisible:
				# Re-register with new keymap
				main.window.unregister_keys()
				main.window.register_keys()
		get_app().prefs.streaming=self.advanced.streaming.GetValue()
		get_app().prefs.load_all_previous=self.advanced.load_all_previous.GetValue()
		get_app().prefs.sync_timeline_position=self.advanced.sync_timeline_position.GetValue()
		get_app().prefs.check_for_updates=self.advanced.check_for_updates.GetValue()
		# Dark mode setting
		dark_mode_values = ['off', 'on', 'auto']
		get_app().prefs.dark_mode = dark_mode_values[self.advanced.dark_mode.GetSelection()]
		get_app().prefs.position=self.advanced.position.GetValue()
		get_app().prefs.earcon_audio=self.general.earcon_audio.GetValue()
		get_app().prefs.earcon_top=self.general.earcon_top.GetValue()
		get_app().prefs.wrap=self.general.wrap.GetValue()
		get_app().prefs.update_time=int(self.advanced.update_time.GetValue())
		if get_app().prefs.update_time<1:
			get_app().prefs.update_time=1
		get_app().prefs.user_limit=int(self.advanced.user_limit.GetValue())
		if get_app().prefs.user_limit<1:
			get_app().prefs.user_limit=1
		if get_app().prefs.user_limit>15:
			get_app().prefs.user_limit=15
		get_app().prefs.count=int(self.advanced.count.GetValue())
		if get_app().prefs.count>40:
			get_app().prefs.count=40
		get_app().prefs.fetch_pages=int(self.advanced.fetch_pages.GetValue())
		if get_app().prefs.fetch_pages<1:
			get_app().prefs.fetch_pages=1
		if get_app().prefs.fetch_pages>10:
			get_app().prefs.fetch_pages=10
		get_app().prefs.single_api_on_startup=self.advanced.single_api_on_startup.GetValue()
		get_app().prefs.ytdlp_path=self.advanced.ytdlp_path.GetValue()
		# Confirmation settings
		get_app().prefs.confirm_boost=self.confirmation.confirm_boost.GetValue()
		get_app().prefs.confirm_unboost=self.confirmation.confirm_unboost.GetValue()
		get_app().prefs.confirm_favorite=self.confirmation.confirm_favorite.GetValue()
		get_app().prefs.confirm_unfavorite=self.confirmation.confirm_unfavorite.GetValue()
		get_app().prefs.confirm_follow=self.confirmation.confirm_follow.GetValue()
		get_app().prefs.confirm_unfollow=self.confirmation.confirm_unfollow.GetValue()
		get_app().prefs.confirm_block=self.confirmation.confirm_block.GetValue()
		get_app().prefs.confirm_unblock=self.confirmation.confirm_unblock.GetValue()
		get_app().prefs.confirm_mute=self.confirmation.confirm_mute.GetValue()
		get_app().prefs.confirm_unmute=self.confirmation.confirm_unmute.GetValue()
		get_app().prefs.confirm_delete=self.confirmation.confirm_delete.GetValue()
		get_app().prefs.confirm_bookmark=self.confirmation.confirm_bookmark.GetValue()
		get_app().prefs.confirm_unbookmark=self.confirmation.confirm_unbookmark.GetValue()
		# AI settings
		ai_service_values = ['none', 'openai', 'gemini']
		get_app().prefs.ai_service = ai_service_values[self.ai_tab.ai_service.GetSelection()]
		get_app().prefs.openai_api_key = self.ai_tab.openai_api_key.GetValue()
		get_app().prefs.openai_model = self.ai_tab.openai_models[self.ai_tab.openai_model.GetSelection()]
		get_app().prefs.gemini_api_key = self.ai_tab.gemini_api_key.GetValue()
		get_app().prefs.gemini_model = self.ai_tab.gemini_models[self.ai_tab.gemini_model.GetSelection()]
		get_app().prefs.ai_image_prompt = self.ai_tab.ai_image_prompt.GetValue()
		if get_app().prefs.reversed!=self.general.reversed.GetValue():
			reverse=True
		else:
			reverse=False
		get_app().prefs.reversed=self.general.reversed.GetValue()
		# Check if any display-affecting settings changed
		cw_mode_values = ['hide', 'show', 'ignore']
		new_cw_mode = cw_mode_values[self.general.cw_mode.GetSelection()]
		if (get_app().prefs.demojify_post != self.general.demojify_post.GetValue() or
			get_app().prefs.demojify != self.general.demojify.GetValue() or
			get_app().prefs.postTemplate != self.templates.postTemplate.GetValue() or
			get_app().prefs.boostTemplate != self.templates.boostTemplate.GetValue() or
			get_app().prefs.quoteTemplate != self.templates.quoteTemplate.GetValue() or
			get_app().prefs.messageTemplate != self.templates.messageTemplate.GetValue() or
			get_app().prefs.notificationTemplate != self.templates.notificationTemplate.GetValue() or
			get_app().prefs.use24HourTime != self.general.use24HourTime.GetValue() or
			get_app().prefs.cw_mode != new_cw_mode):
			refresh=True
		get_app().prefs.demojify=self.general.demojify.GetValue()
		get_app().prefs.demojify_post=self.general.demojify_post.GetValue()
		get_app().prefs.errors=self.general.errors.GetValue()
		get_app().prefs.postTemplate=self.templates.postTemplate.GetValue()
		get_app().prefs.quoteTemplate=self.templates.quoteTemplate.GetValue()
		get_app().prefs.boostTemplate=self.templates.boostTemplate.GetValue()
		get_app().prefs.messageTemplate=self.templates.messageTemplate.GetValue()
		get_app().prefs.copyTemplate=self.templates.copyTemplate.GetValue()
		get_app().prefs.userTemplate=self.templates.userTemplate.GetValue()
		get_app().prefs.notificationTemplate=self.templates.notificationTemplate.GetValue()
		get_app().prefs.autoOpenSingleURL=self.general.autoOpenSingleURL.GetValue()
		get_app().prefs.auto_open_audio_player=self.general.auto_open_audio_player.GetValue()
		get_app().prefs.stop_audio_on_close=self.general.stop_audio_on_close.GetValue()
		# Content warning mode
		get_app().prefs.cw_mode = new_cw_mode
		self.Destroy()
		if reverse:
			timeline.reverse()
		if refresh:
			# Clear display caches on all statuses when templates/display settings change
			for account in get_app().accounts:
				for tl in account.timelines:
					for status in tl.statuses:
						if hasattr(status, '_display_cache'):
							delattr(status, '_display_cache')
			main.window.refreshList()

	def OnClose(self, event):
		self.Destroy()
