"""PyInstaller runtime hook for early initialization."""
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
        return os.path.join(base, "FastSM")
    elif platform.system() == "Darwin":
        return os.path.expanduser("~/Library/Application Support/FastSM")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        return os.path.join(base, "FastSM")

def _setup_early_logging():
    """Initialize logging early for frozen builds."""
    if not getattr(sys, 'frozen', False):
        return

    try:
        from logging_config import setup_logging
        config_dir = _get_config_dir()
        setup_logging(config_dir, debug=False)
    except Exception:
        pass  # Logging will be set up later in FastSM.pyw

_setup_early_logging()
