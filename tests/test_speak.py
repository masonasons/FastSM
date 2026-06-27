import importlib
import sys
import threading
import time
import types
import unittest


def _load_speak_with_speaker(speaker, *, orca_submit=None, platform="win32"):
	"""Import speak with a stub accessible_output2 and a forced Orca submit.

	The fake accessible_output2 module provides an outputs.auto.Auto factory
	that returns the supplied speaker (or raises if speaker is None).
	"""
	sys.modules.pop("speak", None)

	class _Auto:
		def __init__(self_inner):
			if speaker is None:
				raise RuntimeError("no speaker configured")
		# Proxy method lookups onto the supplied speaker so the actual call
		# sites (speaker.speak, speaker.braille) work without rebinding.
		def __getattr__(self_inner, name):
			return getattr(speaker, name)

	fake_outputs = types.SimpleNamespace(auto=types.SimpleNamespace(Auto=_Auto))
	sys.modules["accessible_output2"] = types.SimpleNamespace(outputs=fake_outputs)
	sys.modules["accessible_output2.outputs"] = fake_outputs
	sys.modules["accessible_output2.outputs.auto"] = fake_outputs.auto

	original_platform = sys.platform
	sys.platform = platform
	try:
		speak = importlib.import_module("speak")
	finally:
		sys.platform = original_platform
	speak._logger.disabled = True
	# Override the Linux-only Orca submit (None unless the test wants one).
	speak._orca_submit = orca_submit
	return speak


class SpeakTests(unittest.TestCase):
	def tearDown(self):
		sys.modules.pop("speak", None)
		for name in (
			"accessible_output2",
			"accessible_output2.outputs",
			"accessible_output2.outputs.auto",
		):
			sys.modules.pop(name, None)

	def test_speak_uses_accessible_output2(self):
		calls = []

		class Speaker:
			def speak(self, text, interrupt=False):
				calls.append((text, interrupt))
			def braille(self, text):
				pass

		speak = _load_speak_with_speaker(Speaker())
		speak.speak("hello", True)
		self.assertEqual(calls, [("hello", True)])

	def test_orca_path_short_circuits_accessible_output2(self):
		a2_calls = []
		orca_calls = []

		class Speaker:
			def speak(self, text, interrupt=False):
				a2_calls.append((text, interrupt))
			def braille(self, text):
				pass

		def orca_submit(text, interrupt):
			orca_calls.append((text, interrupt))

		speak = _load_speak_with_speaker(Speaker(), orca_submit=orca_submit)
		speak.speak("hello")
		self.assertEqual(orca_calls, [("hello", False)])
		self.assertEqual(a2_calls, [])

	def test_orca_failure_falls_back_to_a2(self):
		a2_calls = []

		class Speaker:
			def speak(self, text, interrupt=False):
				a2_calls.append((text, interrupt))
			def braille(self, text):
				pass

		def orca_submit(text, interrupt):
			raise RuntimeError("D-Bus exploded")

		speak = _load_speak_with_speaker(Speaker(), orca_submit=orca_submit)
		speak.speak("hello", True)
		self.assertEqual(a2_calls, [("hello", True)])

	def test_speaker_error_is_swallowed(self):
		class Speaker:
			def speak(self, text, interrupt=False):
				raise RuntimeError("backend went away")
			def braille(self, text):
				pass

		speak = _load_speak_with_speaker(Speaker())
		speak.speak("hello")  # must not raise

	def test_no_speaker_available_is_silent(self):
		speak = _load_speak_with_speaker(None)
		speak.speak("hello")  # must not raise

	def test_speak_async_start_failure_is_swallowed(self):
		class Speaker:
			def speak(self, text, interrupt=False):
				raise AssertionError("speech should not be attempted")
			def braille(self, text):
				pass

		class FailingThread:
			def __init__(self, *args, **kwargs):
				pass
			def start(self):
				raise RuntimeError("cannot start thread")

		speak = _load_speak_with_speaker(Speaker())
		original_thread = threading.Thread
		threading.Thread = FailingThread
		try:
			speak.speak_async("non-critical")
		finally:
			threading.Thread = original_thread

	def test_shutdown_announcement_blocks_later_speech(self):
		calls = []

		class Speaker:
			def speak(self, text, interrupt=False):
				calls.append((text, interrupt))
			def braille(self, text):
				pass

		speak = _load_speak_with_speaker(Speaker())

		speak.speak_before_shutdown("Exiting.", interrupt=True)
		speak.speak("late speech")
		speak.speak_async("late async speech")
		speak._do_speak("queued before shutdown", False)

		self.assertEqual(calls, [("Exiting.", True)])

	def test_shutdown_announcement_has_bounded_wait(self):
		started = threading.Event()
		release = threading.Event()

		class Speaker:
			def speak(self, text, interrupt=False):
				started.set()
				release.wait(1.0)
			def braille(self, text):
				pass

		speak = _load_speak_with_speaker(Speaker())

		start = time.monotonic()
		try:
			speak.speak_before_shutdown("Exiting.", timeout=0.01)
			elapsed = time.monotonic() - start
			self.assertLess(elapsed, 0.2)
			self.assertTrue(started.wait(0.2))
		finally:
			release.set()

	def test_shutdown_announcement_has_bounded_wait_on_darwin(self):
		started = threading.Event()
		release = threading.Event()

		class Speaker:
			def speak(self, text, interrupt=False):
				started.set()
				release.wait(1.0)
			def braille(self, text):
				pass

		speak = _load_speak_with_speaker(Speaker(), platform="darwin")

		start = time.monotonic()
		try:
			speak.speak_before_shutdown("Exiting.", timeout=0.01)
			elapsed = time.monotonic() - start
			self.assertLess(elapsed, 0.2)
			self.assertTrue(started.wait(0.2))
		finally:
			release.set()

	def test_shutdown_announcement_start_failure_is_swallowed(self):
		class Speaker:
			def speak(self, text, interrupt=False):
				raise AssertionError("speech should not be attempted")
			def braille(self, text):
				pass

		class FailingThread:
			def __init__(self, *args, **kwargs):
				pass
			def start(self):
				raise RuntimeError("cannot start thread")
			def join(self, timeout=None):
				raise AssertionError("join should not run after start failure")

		speak = _load_speak_with_speaker(Speaker())
		original_thread = threading.Thread
		threading.Thread = FailingThread
		try:
			speak.speak_before_shutdown("Exiting.")
		finally:
			threading.Thread = original_thread


if __name__ == "__main__":
	unittest.main()
