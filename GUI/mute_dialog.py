"""Dialog for muting users with duration options."""

import wx
import speak

# Duration options in seconds (0 = indefinite)
DURATION_OPTIONS = [
    ("Indefinitely", 0),
    ("5 minutes", 300),
    ("30 minutes", 1800),
    ("1 hour", 3600),
    ("6 hours", 21600),
    ("1 day", 86400),
    ("3 days", 259200),
    ("7 days", 604800),
]


class MuteDialog(wx.Dialog):
    """Dialog for muting a user with duration and notification options."""

    def __init__(self, parent, account, user):
        wx.Dialog.__init__(self, parent, title=f"Mute {user.acct}", size=(350, 250))
        self.account = account
        self.user = user

        panel = wx.Panel(self)
        main_box = wx.BoxSizer(wx.VERTICAL)

        # Duration selection
        duration_label = wx.StaticText(panel, -1, "&Mute duration:")
        main_box.Add(duration_label, 0, wx.ALL, 10)

        self.duration_choice = wx.Choice(panel, -1, choices=[d[0] for d in DURATION_OPTIONS])
        self.duration_choice.SetSelection(0)  # Default to indefinite
        main_box.Add(self.duration_choice, 0, wx.ALL | wx.EXPAND, 10)

        # Mute notifications checkbox
        self.mute_notifications = wx.CheckBox(panel, -1, "Also mute &notifications from this user")
        self.mute_notifications.SetValue(True)
        main_box.Add(self.mute_notifications, 0, wx.ALL, 10)

        # Buttons
        button_box = wx.BoxSizer(wx.HORIZONTAL)

        ok_btn = wx.Button(panel, wx.ID_OK, "&Mute")
        ok_btn.Bind(wx.EVT_BUTTON, self.on_mute)
        ok_btn.SetDefault()
        button_box.Add(ok_btn, 0, wx.ALL, 5)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "&Cancel")
        button_box.Add(cancel_btn, 0, wx.ALL, 5)

        main_box.Add(button_box, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        panel.SetSizer(main_box)
        panel.Layout()

        self.duration_choice.SetFocus()

    def on_mute(self, event):
        """Perform the mute action."""
        duration_index = self.duration_choice.GetSelection()
        duration = DURATION_OPTIONS[duration_index][1]
        mute_notifications = self.mute_notifications.GetValue()

        try:
            # Use platform backend if available
            if hasattr(self.account, '_platform') and self.account._platform:
                success = self.account._platform.mute(
                    self.user.id,
                    duration=duration,
                    notifications=mute_notifications
                )
            else:
                # Direct API call
                self.account.api.account_mute(
                    id=self.user.id,
                    duration=duration if duration > 0 else None,
                    notifications=mute_notifications
                )
                success = True

            if success:
                duration_text = DURATION_OPTIONS[duration_index][0].lower()
                speak.speak(f"Muted {self.user.acct} {duration_text}")
            else:
                speak.speak("Failed to mute user")
        except Exception as e:
            self.account.app.handle_error(e, "Mute")

        self.Destroy()


def show_mute_dialog(account, user):
    """Show the mute dialog for a user."""
    from . import main as main_window
    dlg = MuteDialog(main_window.window, account, user)
    dlg.ShowModal()
