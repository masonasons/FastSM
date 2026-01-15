import wx
import platform
import sys
import os

# Colors
DARK_BG = "#191919"
DARK_FG = "#F0F0F0"
CONTROL_BG = "#2D2D2D"
CONTROL_FG = "#FFFFFF"
BORDER_COLOR = "#404040"

_is_dark = None

def is_os_dark_mode():
    """Detect if the OS is in dark mode."""
    global _is_dark
    if _is_dark is not None:
        return _is_dark

    sys_platform = platform.system()

    if sys_platform == "Windows":
        try:
            import winreg
            registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            _is_dark = (value == 0)
        except Exception:
            _is_dark = False
    
    elif sys_platform == "Darwin":
        try:
            import subprocess
            cmd = "defaults read -g AppleInterfaceStyle"
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            output = p.communicate()[0]
            _is_dark = b"Dark" in output
        except Exception:
            _is_dark = False
            
    else:
        # Linux/Other - rudimentary check
        try:
            import subprocess
            # Try checking GTK theme settings via gsettings
            cmd = ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"]
            output = subprocess.check_output(cmd).decode().lower()
            _is_dark = 'dark' in output
        except Exception:
            _is_dark = False

    return _is_dark

def apply_windows_titlebar_hack(window):
    """Force Windows 10/11 title bar to be dark."""
    if platform.system() != "Windows":
        return
    
    try:
        import ctypes
        from ctypes import wintypes
        
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 11, and Win 10 2004+)
        # For older Win 10 builds, it was 19, but 20 is the standard now.
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        
        hwnd = window.GetHandle()
        attribute = ctypes.c_int(1) # 1 = True
        
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            ctypes.c_int(DWMWA_USE_IMMERSIVE_DARK_MODE),
            ctypes.byref(attribute),
            ctypes.sizeof(attribute)
        )
    except Exception:
        pass

def style_window(window):
    """Recursively apply dark theme to a window and its children."""
    if not is_os_dark_mode():
        return

    # Apply Windows specific Title Bar hack
    apply_windows_titlebar_hack(window)

    # Set Main Window Colors
    window.SetBackgroundColour(DARK_BG)
    window.SetForegroundColour(DARK_FG)

    # Helper to style children
    def _style_child(child):
        try:
            # Defaults
            bg = DARK_BG
            fg = DARK_FG
            
            # Specific Widgets
            if isinstance(child, (wx.TextCtrl, wx.ListBox, wx.ComboBox, wx.Choice, wx.ListCtrl, wx.TreeCtrl)):
                bg = CONTROL_BG
                fg = CONTROL_FG
            elif isinstance(child, wx.Panel):
                bg = DARK_BG
                fg = DARK_FG
            elif isinstance(child, wx.Button):
                # Buttons on Windows often resist coloring without custom drawing, 
                # but we try anyway.
                bg = CONTROL_BG
                fg = CONTROL_FG
            
            child.SetBackgroundColour(bg)
            child.SetForegroundColour(fg)
            
            # Recurse if the child has children (like a Panel)
            for grandchild in child.GetChildren():
                _style_child(grandchild)
                
        except Exception:
            pass

    for child in window.GetChildren():
        _style_child(child)
        
    window.Refresh()

# Monkey Patching
# We wrap the __init__ methods of Dialog and Frame to automatically apply styles
# when they are initialized.

_original_dialog_init = wx.Dialog.__init__
_original_frame_init = wx.Frame.__init__

def _patched_dialog_init(self, *args, **kwargs):
    _original_dialog_init(self, *args, **kwargs)
    # We use CallAfter to ensure children are created before we style them
    if is_os_dark_mode():
        wx.CallAfter(style_window, self)

def _patched_frame_init(self, *args, **kwargs):
    _original_frame_init(self, *args, **kwargs)
    if is_os_dark_mode():
        wx.CallAfter(style_window, self)

def install_theme_handler():
    """Install the hooks to automatically theme windows."""
    if is_os_dark_mode():
        wx.Dialog.__init__ = _patched_dialog_init
        wx.Frame.__init__ = _patched_frame_init