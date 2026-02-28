import sys
sys.dont_write_bytecode = True

def _clear_requests_pycache():
	"""Clear corrupted pycache for requests library."""
	import shutil
	import os
	try:
		import requests
		requests_path = os.path.dirname(requests.__file__)
	except:
		# requests not importable, find it manually
		for path in sys.path:
			requests_path = os.path.join(path, 'requests')
			if os.path.isdir(requests_path):
				break
		else:
			return False

	pycache = os.path.join(requests_path, '__pycache__')
	if os.path.exists(pycache):
		try:
			shutil.rmtree(pycache)
			return True
		except:
			pass
	return False

# Try to import requests, clear pycache if it fails (only when running from source)
if not getattr(sys, 'frozen', False):
	try:
		import requests
	except Exception:
		if _clear_requests_pycache():
			# Retry after clearing cache
			import importlib
			import requests

import threading
import platform

def _has_bluesky_accounts():
	"""Check if any Bluesky accounts are configured (without loading full config module)."""
	import os
	import json
	# Check for portable mode (userdata folder in current directory)
	userdata_path = os.path.join(os.getcwd(), "userdata")
	if os.path.isdir(userdata_path):
		config_base = userdata_path
		prefix = ""
	else:
		# Normal mode - use APPDATA on Windows
		config_base = os.environ.get("APPDATA", os.path.expanduser("~"))
		prefix = "FastSM/"

	# Check account0, account1, etc. for bluesky platform_type
	for i in range(10):  # Check up to 10 accounts
		config_path = os.path.join(config_base, f"{prefix}account{i}", "config.json")
		if not os.path.exists(config_path):
			continue
		try:
			with open(config_path, 'r') as f:
				data = json.load(f)
				if data.get("platform_type") == "bluesky":
					return True
		except:
			pass
	return False

# Only pre-import atproto if there are Bluesky accounts (takes ~35s)
# Skip on macOS - can cause startup crashes due to thread/GUI conflicts
_should_preimport_atproto = False
if platform.system() != "Darwin" and _has_bluesky_accounts():
	_should_preimport_atproto = True

import application
from application import get_app
import os

def _get_config_dir():
	"""Get the config directory for logging."""
	# Check for portable mode (userdata folder next to executable or in cwd)
	if getattr(sys, 'frozen', False):
		exe_dir = os.path.dirname(sys.executable)
		userdata_path = os.path.join(exe_dir, "userdata")
		if os.path.isdir(userdata_path):
			return userdata_path
	else:
		# Running from source - check cwd
		userdata_path = os.path.join(os.getcwd(), "userdata")
		if os.path.isdir(userdata_path):
			return userdata_path
	# Standard config location
	if platform.system() == "Windows":
		return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "FastSM")
	elif platform.system() == "Darwin":
		return os.path.expanduser("~/Library/Application Support/FastSM")
	else:
		return os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "FastSM")

# Initialize logging
_config_dir = _get_config_dir()
try:
	from logging_config import setup_logging, get_logger
	# Debug mode will be set later after prefs are loaded
	setup_logging(_config_dir, debug=False)
	_logger = get_logger()
except Exception:
	_logger = None
import shutil
if os.path.exists(os.path.expandvars(r"%temp%\gen_py")):
	shutil.rmtree(os.path.expandvars(r"%temp%\gen_py"))
import wx
wx_app = wx.App(redirect=False)

# Start atproto pre-import AFTER wx.App() is created to avoid thread/GUI conflicts
if _should_preimport_atproto:
	def _preimport_atproto():
		try:
			import atproto
		except:
			pass
	threading.Thread(target=_preimport_atproto, daemon=True).start()

# Prevent multiple instances of the app (not needed on Mac - macOS handles this)
if platform.system() != "Darwin":
	instance_checker = wx.SingleInstanceChecker("FastSM-" + wx.GetUserId())
	if instance_checker.IsAnotherRunning():
		wx.MessageBox("Another instance of FastSM is already running.", "FastSM", wx.OK | wx.ICON_WARNING)
		sys.exit(1)

try:
	import speak
	from GUI import main, theme
	fastsm_app = get_app()
	fastsm_app.load()
	# Apply debug logging preference after prefs are loaded
	if _logger and hasattr(fastsm_app.prefs, 'debug_logging') and fastsm_app.prefs.debug_logging:
		from logging_config import set_debug_mode
		set_debug_mode(True)
	# Apply theme after prefs are loaded
	theme.apply_theme(main.window)
	if _logger:
		_logger.info("FastSM started successfully")
	if fastsm_app.prefs.window_shown:
		main.window.Show()
	else:
		speak.speak("Welcome to FastSM! Main window hidden.")
	wx_app.MainLoop()
except Exception as e:
	import traceback
	error_msg = f"FastSM failed to start:\n\n{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
	if _logger:
		_logger.critical(error_msg)
	else:
		print(error_msg, file=sys.stderr)
	try:
		wx.MessageBox(error_msg, "FastSM Startup Error", wx.OK | wx.ICON_ERROR)
	except:
		pass
	sys.exit(1)
