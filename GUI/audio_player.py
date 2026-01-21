"""Audio player dialog for controlling media playback."""

import wx
import platform
import sound
from application import get_app
from . import theme

# Global reference to the audio player dialog
_audio_player_dialog = None


class AudioPlayerDialog(wx.Dialog):
	"""Dialog for controlling audio playback with volume and seeking."""

	def __init__(self, parent=None):
		global _audio_player_dialog
		_audio_player_dialog = self

		wx.Dialog.__init__(self, parent, title="Audio Player", size=(400, 200),
			style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)

		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDown)

		self.panel = wx.Panel(self)
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		# Status label
		self.status_label = wx.StaticText(self.panel, -1, "Now Playing")
		main_sizer.Add(self.status_label, 0, wx.ALL, 10)

		# Position/duration display
		self.position_label = wx.StaticText(self.panel, -1, "0:00 / 0:00")
		main_sizer.Add(self.position_label, 0, wx.LEFT | wx.RIGHT, 10)

		# Volume display
		volume = int(get_app().prefs.media_volume * 100)
		self.volume_label = wx.StaticText(self.panel, -1, f"Volume: {volume}%")
		main_sizer.Add(self.volume_label, 0, wx.ALL, 10)

		# Instructions
		instructions = wx.StaticText(self.panel, -1,
			"Up/Down: Volume | Left/Right: Seek 5s | Space: Play/Pause | E/R/T: Elapsed/Remaining/Total | Escape: Close")
		main_sizer.Add(instructions, 0, wx.ALL, 10)

		# Close button
		self.close_btn = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
		self.close_btn.Bind(wx.EVT_BUTTON, self.OnClose)
		main_sizer.Add(self.close_btn, 0, wx.ALL, 10)

		self.panel.SetSizer(main_sizer)
		self.panel.Layout()
		theme.apply_theme(self)

		# Start timer to update position and check if still playing
		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
		self.timer.Start(500)  # Update every 500ms

		# Focus panel for keyboard input
		self.panel.SetFocus()

	def OnKeyDown(self, event):
		"""Handle keyboard input for volume and seeking."""
		keycode = event.GetKeyCode()

		if keycode == wx.WXK_UP:
			self._adjust_volume(0.05)
		elif keycode == wx.WXK_DOWN:
			self._adjust_volume(-0.05)
		elif keycode == wx.WXK_LEFT:
			self._seek(-5)
		elif keycode == wx.WXK_RIGHT:
			self._seek(5)
		elif keycode == wx.WXK_SPACE:
			self._toggle_pause()
		elif keycode == wx.WXK_ESCAPE:
			self.OnClose(None)
		elif keycode == ord('E'):
			self._speak_elapsed()
		elif keycode == ord('R'):
			self._speak_remaining()
		elif keycode == ord('T'):
			self._speak_total()
		else:
			event.Skip()

	def _get_time_info(self):
		"""Get current position and length in seconds. Returns (elapsed, total) or (None, None) on error."""
		if sound.player is None:
			return None, None
		try:
			if sound.player_type == 'vlc':
				pos_ms = sound.player.get_time()
				length_ms = sound.player.get_length()
				if pos_ms < 0:
					pos_ms = 0
				if length_ms < 0:
					length_ms = 0
				return pos_ms // 1000, length_ms // 1000
			else:
				pos = sound.player.position
				length = sound.player.length
				bytes_per_second = 176400
				return int(pos / bytes_per_second), int(length / bytes_per_second)
		except:
			return None, None

	def _format_time(self, seconds):
		"""Format seconds as readable string like '3:45'."""
		if seconds is None:
			return "unknown"
		minutes = seconds // 60
		secs = seconds % 60
		return f"{minutes}:{secs:02d}"

	def _speak_elapsed(self):
		"""Speak elapsed time."""
		import speak
		elapsed, _ = self._get_time_info()
		if elapsed is not None:
			speak.speak(f"Elapsed: {self._format_time(elapsed)}")
		else:
			speak.speak("Unknown")

	def _speak_remaining(self):
		"""Speak remaining time."""
		import speak
		elapsed, total = self._get_time_info()
		if elapsed is not None and total is not None and total > 0:
			remaining = max(0, total - elapsed)
			speak.speak(f"Remaining: {self._format_time(remaining)}")
		else:
			speak.speak("Unknown")

	def _speak_total(self):
		"""Speak total time."""
		import speak
		_, total = self._get_time_info()
		if total is not None:
			speak.speak(f"Total: {self._format_time(total)}")
		else:
			speak.speak("Unknown")

	def _adjust_volume(self, delta):
		"""Adjust media volume by delta amount."""
		import speak
		app = get_app()
		new_volume = app.prefs.media_volume + delta
		new_volume = max(0.0, min(1.0, new_volume))
		new_volume = round(new_volume, 2)
		app.prefs.media_volume = new_volume

		# Apply to current player
		if sound.player is not None:
			try:
				if sound.player_type == 'vlc':
					sound.player.audio_set_volume(int(new_volume * 100))
				else:
					sound.player.volume = new_volume
			except:
				pass

		# Update display and speak new volume
		volume_percent = int(new_volume * 100)
		self.volume_label.SetLabel(f"Volume: {volume_percent}%")
		speak.speak(f"{volume_percent}%")

	def _seek(self, seconds):
		"""Seek forward or backward by seconds."""
		if sound.player is None:
			return

		try:
			if sound.player_type == 'vlc':
				# VLC uses milliseconds for time
				current_ms = sound.player.get_time()
				if current_ms < 0:
					current_ms = 0
				new_ms = current_ms + (seconds * 1000)
				new_ms = max(0, int(new_ms))

				# Get length to cap at end
				length_ms = sound.player.get_length()
				if length_ms > 0:
					new_ms = min(new_ms, length_ms)

				sound.player.set_time(new_ms)
			else:
				# sound_lib uses bytes position
				current_pos = sound.player.position
				bytes_per_second = 176400  # Approximate for most audio
				new_pos = current_pos + (seconds * bytes_per_second)
				new_pos = max(0, int(new_pos))

				# Get length to cap at end
				try:
					length = sound.player.length
					new_pos = min(new_pos, length)
				except:
					pass

				sound.player.position = new_pos
		except Exception:
			pass

	def _toggle_pause(self):
		"""Toggle play/pause on the media player."""
		if sound.player is None:
			return

		try:
			if sound.player_type == 'vlc':
				# VLC's is_playing() returns 1 if playing, 0 otherwise
				if sound.player.is_playing():
					sound.player.pause()
					self.status_label.SetLabel("Paused")
				else:
					sound.player.play()
					self.status_label.SetLabel("Now Playing")
			else:
				# sound_lib uses is_playing property
				if sound.player.is_playing:
					sound.player.pause()
					self.status_label.SetLabel("Paused")
				else:
					sound.player.play()
					self.status_label.SetLabel("Now Playing")
		except:
			pass

	def OnTimer(self, event):
		"""Update position display and check if audio is still playing."""
		if sound.player is None:
			self._close_dialog()
			return

		# Check if playback ended
		try:
			if sound.player_type == 'vlc':
				# VLC's get_state() returns the current state
				import vlc
				state = sound.player.get_state()
				# Only close for terminal states (Ended, Error)
				# Don't close for Stopped - VLC may transition through it
				if state in (vlc.State.Ended, vlc.State.Error):
					self._close_dialog()
					return
			else:
				# sound_lib - check if stopped and near end
				if not sound.player.is_playing:
					try:
						pos = sound.player.position
						length = sound.player.length
						if pos >= length - 1000 or length == 0:
							self._close_dialog()
							return
					except:
						pass
		except:
			pass

		# Update position display
		try:
			if sound.player_type == 'vlc':
				# VLC uses milliseconds
				pos_ms = sound.player.get_time()
				length_ms = sound.player.get_length()

				if pos_ms < 0:
					pos_ms = 0
				if length_ms < 0:
					length_ms = 0

				pos_seconds = pos_ms // 1000
				length_seconds = length_ms // 1000
			else:
				# sound_lib uses bytes
				pos = sound.player.position
				length = sound.player.length
				bytes_per_second = 176400

				pos_seconds = int(pos / bytes_per_second)
				length_seconds = int(length / bytes_per_second)

			pos_str = f"{pos_seconds // 60}:{pos_seconds % 60:02d}"
			length_str = f"{length_seconds // 60}:{length_seconds % 60:02d}"

			self.position_label.SetLabel(f"{pos_str} / {length_str}")
		except:
			self.position_label.SetLabel("Playing...")

	def _close_dialog(self):
		"""Close the dialog and clean up."""
		global _audio_player_dialog
		self.timer.Stop()
		_audio_player_dialog = None
		# Stop audio if the setting is enabled
		if get_app().prefs.stop_audio_on_close:
			sound.stop()
		self.Destroy()

	def OnClose(self, event):
		"""Handle close event."""
		self._close_dialog()


def show_audio_player(parent=None, silent=False):
	"""Show the audio player dialog if audio is playing.

	Args:
		parent: Parent window
		silent: If True, don't speak "No audio playing" message
	"""
	global _audio_player_dialog

	# Check if audio is actually playing
	if sound.player is None:
		if not silent:
			import speak
			speak.speak("No audio playing")
		return None

	# Check if player is active (playing, buffering, opening, paused, or stopped but not ended)
	try:
		if sound.player_type == 'vlc':
			import vlc
			state = sound.player.get_state()
			# Consider active if not in terminal states
			# Stopped is OK - VLC transitions through it
			is_active = state not in (vlc.State.NothingSpecial, vlc.State.Ended, vlc.State.Error)
		else:
			# sound_lib uses is_playing property
			is_active = sound.player.is_playing
	except:
		is_active = False

	if not is_active and not silent:
		import speak
		speak.speak("No audio playing")
		return None

	# If dialog already open, just focus it
	if _audio_player_dialog is not None:
		try:
			_audio_player_dialog.Raise()
			_audio_player_dialog.SetFocus()
			return _audio_player_dialog
		except:
			_audio_player_dialog = None

	# Create and show new dialog
	dlg = AudioPlayerDialog(parent)
	dlg.Show()
	return dlg


def close_audio_player():
	"""Close the audio player dialog if open."""
	global _audio_player_dialog
	if _audio_player_dialog is not None:
		try:
			wx.CallAfter(_audio_player_dialog._close_dialog)
		except:
			_audio_player_dialog = None


def is_audio_player_open():
	"""Check if audio player dialog is open."""
	return _audio_player_dialog is not None


def auto_show_audio_player(parent=None):
	"""Show audio player if auto-open setting is enabled."""
	if get_app().prefs.auto_open_audio_player:
		# Use a small delay to ensure the player has started
		def delayed_show():
			import time
			time.sleep(0.3)  # Wait for audio to start
			wx.CallAfter(show_audio_player, parent, silent=True)
		import threading
		threading.Thread(target=delayed_show, daemon=True).start()
