"""Virtual Fusion View account.

This account has no login or API backend. It exists so Fusion View can appear
as its own top-level account while the real Mastodon and Bluesky accounts keep
their normal timelines unchanged.
"""

import timeline
from models import UniversalUser, UserCache


class FusionPrefs(object):
	def __init__(self):
		self.platform_type = "fusion"
		self.soundpack = "default"
		self.soundpan = 0
		self.soundpack_volume = 1.0
		self.footer = ""
		self.aliases = {}
		self.timeline_order = []
		self.mentions_in_notifications = False

	def get(self, name, default=None):
		return getattr(self, name, default)

	def save(self):
		pass


class FusionAccount(object):
	"""Non-authenticated virtual account for the Fusion View placeholder."""

	is_virtual = True
	folder_index = 999999

	def __init__(self, app):
		self.app = app
		self.ready = True
		self.timelines = []
		self.currentIndex = 0
		self.currentTimeline = None
		self.currentStatus = None
		self.confpath = ""
		self.prefs = FusionPrefs()
		self.me = UniversalUser(
			id="fusion-view",
			acct="Fusion View",
			username="fusion",
			display_name="Fusion View",
			_platform="fastsm",
		)
		self.user_cache = UserCache("", "fusion", self.me.id)

		for name, source_type in (
			("Unified Timeline", "home"),
			("Unified Mentions", "mentions"),
			("Unified Notifications", "notifications"),
		):
			self.timelines.append(timeline.timeline(
				self,
				name=name,
				type="fusion",
				data=source_type,
				silent=True,
			))
		self.currentTimeline = self.timelines[0]

	def list_timelines(self, hidden=False):
		return [tl for tl in self.timelines if tl.hide == hidden]

	def get_first_timeline(self):
		return self.timelines[0] if self.timelines else None

	def get_timeline_by_type(self, timeline_type):
		for tl in self.timelines:
			if tl.type == timeline_type:
				return tl
		return None

	def _on_timeline_initial_load_complete(self):
		pass

	def start_stream(self):
		pass

	def supports_feature(self, feature):
		return False
