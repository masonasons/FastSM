import importlib
import sys
import threading
import time
import types
import unittest


class _BackendId:
	VOICE_OVER = "voice_over"


class _PrismError(Exception):
	pass


def _load_speak_with_context(context_cls):
	fake_prism = types.SimpleNamespace(
		BackendId=_BackendId,
		Context=context_cls,
		PrismError=_PrismError,
	)
	sys.modules.pop("speak", None)
	sys.modules["prism"] = fake_prism
	speak = importlib.import_module("speak")
	speak._logger.disabled = True
	return speak


class SpeakPrismFailureTests(unittest.TestCase):
	def tearDown(self):
		sys.modules.pop("speak", None)
		sys.modules.pop("prism", None)

	def test_non_prism_backend_errors_are_swallowed_after_retry(self):
		speak_calls = []

		class Backend:
			id = "orca"

			def speak(self, text, interrupt):
				speak_calls.append((text, interrupt))
				raise RuntimeError("unsupported Orca DBus API")

			def braille(self, text):
				pass

		class Context:
			create_count = 0

			def create_best(self):
				type(self).create_count += 1
				return Backend()

		speak = _load_speak_with_context(Context)

		speak.speak("Exiting.", interrupt=True)

		self.assertEqual(Context.create_count, 2)
		self.assertEqual(len(speak_calls), 2)
		self.assertIsNone(speak._prism_backend)

	def test_non_prism_backend_creation_errors_are_swallowed(self):
		class Context:
			create_count = 0

			def create_best(self):
				type(self).create_count += 1
				raise RuntimeError("unsupported Orca DBus API")

		speak = _load_speak_with_context(Context)

		speak.speak("Exiting.")

		self.assertEqual(Context.create_count, 2)
		self.assertIsNone(speak._prism_backend)

	def test_retry_success_keeps_new_backend_cached(self):
		class BrokenBackend:
			id = "orca"

			def speak(self, text, interrupt):
				raise RuntimeError("unsupported Orca DBus API")

			def braille(self, text):
				pass

		class WorkingBackend:
			id = "speech_dispatcher"
			speak_calls = 0

			def speak(self, text, interrupt):
				type(self).speak_calls += 1

			def braille(self, text):
				pass

		class Context:
			create_count = 0

			def create_best(self):
				type(self).create_count += 1
				if type(self).create_count == 1:
					return BrokenBackend()
				return WorkingBackend()

		speak = _load_speak_with_context(Context)

		speak.speak("Hello")

		self.assertEqual(Context.create_count, 2)
		self.assertEqual(WorkingBackend.speak_calls, 1)
		self.assertIsInstance(speak._prism_backend, WorkingBackend)

	def test_import_time_does_not_require_prism(self):
		sys.modules.pop("speak", None)
		sys.modules.pop("prism", None)

		speak = importlib.import_module("speak")
		speak._logger.disabled = True
		original_import_module = importlib.import_module
		def fail_import(name):
			raise RuntimeError(f"cannot import {name}")
		importlib.import_module = fail_import

		try:
			speak.speak("Exiting.")
		finally:
			importlib.import_module = original_import_module

		self.assertIsNone(speak._prism_backend)

	def test_backoff_skips_repeated_prism_creation_attempts(self):
		class Context:
			create_count = 0

			def create_best(self):
				type(self).create_count += 1
				raise RuntimeError("unsupported Orca DBus API")

		speak = _load_speak_with_context(Context)

		speak.speak("first failure")
		speak.speak("during backoff")

		self.assertEqual(Context.create_count, 2)

	def test_prism_failure_does_not_show_dialogs(self):
		class DialogSentinel:
			def __getattr__(self, name):
				if name in ("MessageBox", "MessageDialog"):
					raise AssertionError(f"unexpected dialog: {name}")
				raise AttributeError(name)

		class Context:
			def create_best(self):
				raise RuntimeError("unsupported Orca DBus API")

		sys.modules["wx"] = DialogSentinel()
		try:
			speak = _load_speak_with_context(Context)

			speak.speak("Exiting.")
		finally:
			sys.modules.pop("wx", None)

	def test_speak_async_start_failure_is_swallowed(self):
		class FailingThread:
			def __init__(self, *args, **kwargs):
				pass

			def start(self):
				raise RuntimeError("cannot start thread")

		class Context:
			def create_best(self):
				raise AssertionError("speech should not be attempted")

		speak = _load_speak_with_context(Context)
		original_thread = threading.Thread
		threading.Thread = FailingThread
		try:
			speak.speak_async("non-critical")
		finally:
			threading.Thread = original_thread

	def test_shutdown_announcement_blocks_later_speech(self):
		speak_calls = []

		class Backend:
			id = "speech_dispatcher"

			def speak(self, text, interrupt):
				speak_calls.append((text, interrupt))

			def braille(self, text):
				pass

		class Context:
			def create_best(self):
				return Backend()

		speak = _load_speak_with_context(Context)

		speak.speak_before_shutdown("Exiting.", interrupt=True)
		speak.speak("late speech")
		speak.speak_async("late async speech")
		speak._do_speak("queued before shutdown", False)

		self.assertEqual(speak_calls, [("Exiting.", True)])

	def test_shutdown_announcement_does_not_retry_broken_backend(self):
		class Context:
			create_count = 0

			def create_best(self):
				type(self).create_count += 1
				raise RuntimeError("unsupported Orca DBus API")

		speak = _load_speak_with_context(Context)

		speak.speak_before_shutdown("Exiting.")

		self.assertEqual(Context.create_count, 1)
		self.assertIsNone(speak._prism_backend)

	def test_shutdown_announcement_has_bounded_wait(self):
		started = threading.Event()
		release = threading.Event()

		class Backend:
			id = "speech_dispatcher"

			def speak(self, text, interrupt):
				started.set()
				release.wait(1.0)

			def braille(self, text):
				pass

		class Context:
			def create_best(self):
				return Backend()

		speak = _load_speak_with_context(Context)

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

		class Backend:
			id = "voice_over"

			def speak(self, text, interrupt):
				started.set()
				release.wait(1.0)

			def braille(self, text):
				pass

		class Context:
			def exists(self, backend_id):
				return False

			def create_best(self):
				return Backend()

		speak = _load_speak_with_context(Context)
		original_platform = sys.platform
		sys.platform = "darwin"

		start = time.monotonic()
		try:
			speak.speak_before_shutdown("Exiting.", timeout=0.01)
			elapsed = time.monotonic() - start
			self.assertLess(elapsed, 0.2)
			self.assertTrue(started.wait(0.2))
		finally:
			sys.platform = original_platform
			release.set()

	def test_shutdown_announcement_start_failure_is_swallowed(self):
		class FailingThread:
			def __init__(self, *args, **kwargs):
				pass

			def start(self):
				raise RuntimeError("cannot start thread")

			def join(self, timeout=None):
				raise AssertionError("join should not run after start failure")

		class Context:
			def create_best(self):
				raise AssertionError("speech should not be attempted")

		speak = _load_speak_with_context(Context)
		original_thread = threading.Thread
		threading.Thread = FailingThread
		try:
			speak.speak_before_shutdown("Exiting.")
		finally:
			threading.Thread = original_thread


if __name__ == "__main__":
	unittest.main()
