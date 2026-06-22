import types
import sys
import threading
import unittest

sys.modules["GUI.main"] = types.SimpleNamespace(
	window=types.SimpleNamespace(refreshList=lambda: None)
)

import timeline


class TimelineRefreshFocusTests(unittest.TestCase):
	def _make_timeline(self, statuses, index):
		tl = timeline.timeline.__new__(timeline.timeline)
		tl.type = "home"
		tl.statuses = list(statuses)
		tl.index = index
		tl.initial = False
		tl.read = False
		tl.mute = True
		tl.hide = False
		tl.name = "Home"
		tl._position_moved = True
		tl._status_ids = set(str(getattr(item, "id", "")) for item in statuses)
		tl._status_lock = threading.Lock()
		tl._gaps = []
		tl.update_kwargs = {}
		tl.prev_kwargs = {}
		tl.account = types.SimpleNamespace(
			me=types.SimpleNamespace(acct="user@example.com"),
			user_cache=types.SimpleNamespace(add_users_from_status=lambda item: None),
			timelines=[],
			ready=True,
		)
		tl.app = types.SimpleNamespace(
			prefs=types.SimpleNamespace(
				reversed=False,
				statuses_received=0,
				fetch_pages=1,
				single_api_on_startup=False,
			),
			currentAccount=None,
			refresh_fusion_view_soon=lambda: None,
			handle_error=lambda error, context: None,
		)
		tl._add_status_with_filter = lambda item, to_front=False: (
			tl.statuses.insert(0, item) if to_front else tl.statuses.append(item)
		) is None or True
		return tl

	def test_refresh_keeps_selected_item_when_newer_items_are_inserted(self):
		old_items = [
			types.SimpleNamespace(id="2"),
			types.SimpleNamespace(id="1"),
		]
		tl = self._make_timeline(old_items, 1)

		tl._do_load(items=[types.SimpleNamespace(id="3")])

		self.assertEqual(tl.index, 2)
		self.assertEqual(tl.statuses[tl.index].id, "1")


class FusionTimelineFocusTests(unittest.TestCase):
	def _make_fusion_timeline(self, statuses, index, refreshed_statuses):
		tl = timeline.timeline.__new__(timeline.timeline)
		tl.type = "fusion"
		tl.statuses = statuses
		tl.index = index
		tl.func = lambda: refreshed_statuses
		tl._status_ids = set(str(getattr(item, "id", "")) for item in statuses)
		tl.initial = False
		tl.account = types.SimpleNamespace()
		tl.app = types.SimpleNamespace(currentAccount=None)
		tl.name = "Fusion View"
		return tl

	def test_fusion_refresh_keeps_selected_item_when_newer_items_are_inserted(self):
		old_items = [
			types.SimpleNamespace(id="2"),
			types.SimpleNamespace(id="1"),
		]
		refreshed_items = [
			types.SimpleNamespace(id="3"),
			types.SimpleNamespace(id="2"),
			types.SimpleNamespace(id="1"),
		]
		tl = self._make_fusion_timeline(old_items, 1, refreshed_items)

		self.assertTrue(tl.load())

		self.assertEqual(tl.index, 2)
		self.assertEqual(tl.statuses[tl.index].id, "1")
		self.assertEqual(tl._previous_refresh_statuses, old_items)

	def test_fusion_refresh_clamps_index_when_selected_item_disappears(self):
		old_items = [
			types.SimpleNamespace(id="2"),
			types.SimpleNamespace(id="1"),
		]
		refreshed_items = [
			types.SimpleNamespace(id="4"),
			types.SimpleNamespace(id="3"),
		]
		tl = self._make_fusion_timeline(old_items, 1, refreshed_items)

		self.assertTrue(tl.load())

		self.assertEqual(tl.index, 1)
		self.assertEqual(tl.statuses[tl.index].id, "3")


if __name__ == "__main__":
	unittest.main()
