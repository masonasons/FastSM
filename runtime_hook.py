"""PyInstaller runtime hook to redirect stderr to config directory early."""
import sys
import os
import platform

def _get_config_dir():
    """Get the config directory path."""
    # Check for portable mode (userdata folder next to executable)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        userdata_path = os.path.join(exe_dir, "userdata")
        if os.path.isdir(userdata_path):
            return userdata_path

    # Standard config locations
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "fastsm")
    elif platform.system() == "Darwin":
        return os.path.expanduser("~/Library/Application Support/fastsm")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        return os.path.join(base, "fastsm")

def _setup_error_logging():
    """Redirect stderr to config directory."""
    if not getattr(sys, 'frozen', False):
        return

    try:
        config_dir = _get_config_dir()
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        error_log_path = os.path.join(config_dir, "errors.log")
        sys.stderr = open(error_log_path, "a")
    except Exception:
        pass  # If we can't set up logging, just continue

_setup_error_logging()
