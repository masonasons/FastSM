# -*- coding: utf-8 -*-
from mastodon import StreamListener
from GUI import main
import time
import speak
import sys
import wx
from platforms.mastodon.models import mastodon_status_to_universal, mastodon_notification_to_universal

class MastodonStreamListener(StreamListener):
	"""Handles Mastodon streaming events"""

	def __init__(self, account):
		super(MastodonStreamListener, self).__init__()
		self.account = account

	def on_update(self, status):
		"""Called when a new status appears in the home timeline"""
		try:
			# Convert to universal status
			status = mastodon_status_to_universal(status)
			if not status:
				return

			# Add to home timeline
			home_tl = self.account.get_timeline_by_type("home")
			if home_tl:
				home_tl.load(items=[status])

			# Note: Mentions are handled by on_notification to avoid duplicates

			# Check if it's from us (add to Sent)
			if str(status.account.id) == str(self.account.me.id):
				for tl in self.account.timelines:
					if tl.type == "user" and tl.name == "Sent":
						tl.load(items=[status])
						break

			# Check user timelines
			for tl in self.account.timelines:
				if tl.type == "list" and str(status.account.id) in [str(m) for m in tl.members]:
					tl.load(items=[status])
				if tl.type == "user" and tl.user and str(status.account.id) == str(tl.user.id):
					tl.load(items=[status])
		except Exception as e:
			self.account.app.handle_error(e, "Stream update")

	def on_notification(self, notification):
		"""Called when a new notification arrives"""
		try:
			# Check if mentions should be included in notifications
			include_mentions = getattr(self.account.prefs, 'mentions_in_notifications', False)

			# Add to notifications timeline (mentions only if setting enabled)
			if notification.type != "mention" or include_mentions:
				uni_notif = mastodon_notification_to_universal(notification)
				if uni_notif:
					for tl in self.account.timelines:
						if tl.type == "notifications":
							tl.load(items=[uni_notif])
							break

			# Add mentions to mentions timeline as STATUS (not notification)
			if notification.type == "mention" and hasattr(notification, 'status') and notification.status:
				# Convert to universal status
				status = mastodon_status_to_universal(notification.status)
				if not status:
					return

				# Store original ID and set notification ID as primary for timeline tracking
				status._original_status_id = str(status.id)
				status.id = str(notification.id)
				status._notification_id = str(notification.id)

				for tl in self.account.timelines:
					if tl.type == "mentions":
						tl.load(items=[status])
						break
		except Exception as e:
			self.account.app.handle_error(e, "Stream notification")

	def on_conversation(self, conversation):
		"""Called when a direct message conversation is updated"""
		try:
			for tl in self.account.timelines:
				if tl.type == "conversations":
					tl.load(items=[conversation])
					break
		except Exception as e:
			self.account.app.handle_error(e, "Stream conversation")

	def on_delete(self, status_id):
		"""Called when a status is deleted"""
		try:
			status_id_str = str(status_id)
			needs_refresh = False
			for tl in self.account.timelines:
				for i, status in enumerate(tl.statuses):
					if hasattr(status, 'id') and str(status.id) == status_id_str:
						tl.statuses.pop(i)
						if tl == self.account.currentTimeline and self.account == self.account.app.currentAccount:
							needs_refresh = True
						break
			if needs_refresh:
				wx.CallAfter(main.window.refreshList)
		except Exception as e:
			self.account.app.handle_error(e, "Stream delete")

	def on_status_update(self, status):
		"""Called when a status is edited"""
		try:
			# Convert to universal status
			uni_status = mastodon_status_to_universal(status)
			if not uni_status:
				return

			needs_refresh = False
			for tl in self.account.timelines:
				for i, s in enumerate(tl.statuses):
					if hasattr(s, 'id') and str(s.id) == str(uni_status.id):
						tl.statuses[i] = uni_status
						if tl == self.account.currentTimeline and self.account == self.account.app.currentAccount:
							needs_refresh = True
						break
			if needs_refresh:
				wx.CallAfter(main.window.refreshList)
		except Exception as e:
			self.account.app.handle_error(e, "Stream status update")

	def handle_heartbeat(self):
		"""Called on heartbeat to keep connection alive"""
		pass

	def on_abort(self, err):
		"""Called when stream is aborted - reconnect handled automatically"""
		# Don't announce every disconnect since we auto-reconnect
		pass

	def on_unknown_event(self, name, data=None):
		"""Called on unknown events"""
		pass
