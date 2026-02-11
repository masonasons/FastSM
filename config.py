"""Simple JSON-based configuration module."""

import os
import json
import atexit
import platform
import shutil
from collections.abc import MutableMapping

# Cache for portable mode detection
_portable_path = None
_portable_checked = False
_migration_checked = False

APP_CONFIG_DIRNAME = "fastsm"
LEGACY_APP_CONFIG_DIRNAMES = ("FastSM",)


def get_app_config_dirname():
	"""Get the canonical app config directory name."""
	return APP_CONFIG_DIRNAME


def get_legacy_config_dirnames():
	"""Get legacy app config directory names used by older versions."""
	return LEGACY_APP_CONFIG_DIRNAMES


def is_portable_mode():
	"""Check if running in portable mode (userdata folder exists in current directory)."""
	global _portable_path, _portable_checked
	if _portable_checked:
		return _portable_path is not None

	_portable_checked = True
	# Only check for portable mode on Windows and Linux, not macOS
	if platform.system() == "Darwin":
		return False

	# Check for userdata folder in current directory
	userdata_path = os.path.join(os.getcwd(), "userdata")
	if os.path.isdir(userdata_path):
		_portable_path = userdata_path
		return True

	return False


def get_portable_path():
	"""Get the portable userdata path, or None if not in portable mode."""
	is_portable_mode()  # Ensure check has been done
	return _portable_path


def get_config_home():
	"""Get the user config directory based on platform.

	On Windows/Linux, if a 'userdata' folder exists in the current directory,
	that folder will be used instead (portable mode).
	"""
	# Check for portable mode first (Windows/Linux only)
	portable = get_portable_path()
	if portable:
		return portable

	if platform.system() == "Windows":
		return os.environ.get("APPDATA", os.path.expanduser("~"))
	elif platform.system() == "Darwin":
		return os.path.expanduser("~/Library/Application Support")
	else:
		return os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))


def _normalize_config_name(name, portable_mode):
	"""Normalize config names to the canonical app directory."""
	if name is None:
		name = ""
	name = str(name)

	known_roots = (APP_CONFIG_DIRNAME,) + LEGACY_APP_CONFIG_DIRNAMES
	known_prefixes = tuple(f"{root}/" for root in known_roots)

	if portable_mode:
		# In portable mode, userdata is already app-specific.
		if name in known_roots:
			return ""
		for prefix in known_prefixes:
			if name.startswith(prefix):
				return name[len(prefix):]
		return name

	if name in known_roots:
		return APP_CONFIG_DIRNAME
	for prefix in known_prefixes:
		if name.startswith(prefix):
			rest = name[len(prefix):]
			return f"{APP_CONFIG_DIRNAME}/{rest}" if rest else APP_CONFIG_DIRNAME
	# Be tolerant of bare account names in non-portable mode.
	if name.startswith("account"):
		return f"{APP_CONFIG_DIRNAME}/{name}"
	if name == "":
		return APP_CONFIG_DIRNAME
	return name


def ensure_config_migrated():
	"""Migrate legacy config directory to canonical one (non-portable only)."""
	global _migration_checked
	if _migration_checked:
		return
	_migration_checked = True

	if is_portable_mode():
		return

	config_home = get_config_home()
	new_dir = os.path.join(config_home, APP_CONFIG_DIRNAME)
	if os.path.isdir(new_dir):
		return

	for legacy_name in LEGACY_APP_CONFIG_DIRNAMES:
		legacy_dir = os.path.join(config_home, legacy_name)
		if os.path.isdir(legacy_dir):
			try:
				shutil.copytree(legacy_dir, new_dir)
			except Exception:
				pass
			return


class Config(MutableMapping):
	"""A simple JSON-based configuration class with attribute access and autosave."""

	def __init__(self, name, autosave=False, save_on_exit=True, _parent=None, _data=None):
		self._name = name
		self._autosave = autosave
		self._parent = _parent
		self._closed = False
		self._user_config_home = get_config_home()
		self._portable_mode = is_portable_mode()
		if not self._portable_mode:
			ensure_config_migrated()
		self._normalized_name = _normalize_config_name(name, self._portable_mode)

		if _data is None:
			self._data = {}
			if _parent is None:
				self._load()
				self._data = self._convert_nested(self._data)
				if save_on_exit:
					atexit.register(self.save)
		else:
			self._data = _data

	@property
	def config_file(self):
		"""Get the path to the config file."""
		# In portable mode, don't add app name prefix (userdata is already app-specific)
		# but keep subdirectories for account configs etc.
		if self._portable_mode:
			if self._normalized_name:
				return os.path.join(self._user_config_home, self._normalized_name, "config.json")
			return os.path.join(self._user_config_home, "config.json")
		return os.path.join(self._user_config_home, self._normalized_name, "config.json")

	def _convert_nested(self, data):
		"""Convert nested dicts to Config objects."""
		if isinstance(data, dict):
			result = {}
			for key, value in data.items():
				result[key] = self._convert_nested(value)
			return result
		return data

	def _load(self):
		"""Load configuration from file."""
		try:
			with open(self.config_file, 'r') as f:
				self._data = json.load(f)
		except FileNotFoundError:
			# Fallback: read from legacy locations if migration was not possible.
			for legacy_file in self._legacy_config_files():
				try:
					with open(legacy_file, 'r') as f:
						self._data = json.load(f)
						return
				except FileNotFoundError:
					continue
				except Exception:
					continue
		except Exception as e:
			print(f"Error loading config: {e}")

	def _legacy_config_files(self):
		"""Get possible legacy config file paths for backward compatibility."""
		if self._portable_mode:
			return []
		if not self._normalized_name:
			return []
		if self._normalized_name == APP_CONFIG_DIRNAME:
			suffix = ""
		elif self._normalized_name.startswith(APP_CONFIG_DIRNAME + "/"):
			suffix = self._normalized_name[len(APP_CONFIG_DIRNAME) + 1:]
		else:
			return []

		paths = []
		for legacy_root in LEGACY_APP_CONFIG_DIRNAMES:
			if suffix:
				paths.append(os.path.join(self._user_config_home, legacy_root, suffix, "config.json"))
			else:
				paths.append(os.path.join(self._user_config_home, legacy_root, "config.json"))
		return paths

	def save(self):
		"""Save configuration to file."""
		if self._parent:
			return self._parent.save()

		config_file = self.config_file
		os.makedirs(os.path.dirname(config_file), exist_ok=True)

		try:
			with open(config_file, 'w') as f:
				json.dump(self._data, f, indent=1, default=self._serialize)
		except Exception as e:
			print(f"Error saving config: {e}")

	def _serialize(self, obj):
		"""Custom serializer for Config objects."""
		if hasattr(obj, '_data'):
			return obj._data
		return str(obj)

	def get(self, key, default=None):
		"""Get a value with a default."""
		return self._data.get(key, default)

	def __getitem__(self, key):
		return self._data[key]

	def __setitem__(self, key, value):
		if isinstance(value, dict):
			value = Config(name=self._name, autosave=self._autosave, _parent=self, _data=value)
		self._data[key] = value
		if self._autosave:
			self.save()

	def __delitem__(self, key):
		del self._data[key]
		if self._autosave:
			self.save()

	def __iter__(self):
		return iter(self._data)

	def __len__(self):
		return len(self._data)

	def __repr__(self):
		return repr(self._data)

	def __getattr__(self, name):
		if name.startswith('_'):
			raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
		try:
			return self[name]
		except KeyError:
			raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

	def __setattr__(self, name, value):
		if name.startswith('_'):
			super().__setattr__(name, value)
		else:
			self[name] = value

	def __delattr__(self, name):
		if name.startswith('_'):
			super().__delattr__(name)
		else:
			del self[name]

	def close(self):
		"""Save and close the config."""
		if not self._closed:
			self._closed = True
			self.save()
			atexit.unregister(self.save)
			return True
		return False
