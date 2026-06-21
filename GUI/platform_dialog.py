"""Platform selection and authentication dialogs."""

import wx
import wx.adv
import sys


class PlatformSelectDialog(wx.Dialog):
    """Dialog for selecting which platform to add an account for."""

    def __init__(self, parent):
        super().__init__(parent, title="Select Platform", size=(300, 150))

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Label
        label = wx.StaticText(panel, label="Which platform would you like to add?")
        sizer.Add(label, 0, wx.ALL | wx.CENTER, 10)

        # Radio buttons
        self.mastodon_radio = wx.RadioButton(panel, label="Mastodon", style=wx.RB_GROUP)
        self.bluesky_radio = wx.RadioButton(panel, label="Bluesky")
        self.youtube_radio = wx.RadioButton(panel, label="YouTube")

        radio_sizer = wx.BoxSizer(wx.VERTICAL)
        radio_sizer.Add(self.mastodon_radio, 0, wx.ALL, 5)
        radio_sizer.Add(self.bluesky_radio, 0, wx.ALL, 5)
        radio_sizer.Add(self.youtube_radio, 0, wx.ALL, 5)
        sizer.Add(radio_sizer, 0, wx.CENTER, 5)

        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "OK")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)
        self.Centre()

        # Set focus to first radio button
        self.mastodon_radio.SetFocus()

    def get_platform(self) -> str:
        """Return the selected platform name."""
        if self.bluesky_radio.GetValue():
            return "bluesky"
        if self.youtube_radio.GetValue():
            return "youtube"
        return "mastodon"


class BlueskyAuthDialog(wx.Dialog):
    """Dialog for Bluesky authentication (handle + app password)."""

    def __init__(self, parent):
        super().__init__(parent, title="Bluesky Login", size=(400, 250))

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Instructions
        instructions = wx.StaticText(panel, label="Enter your Bluesky handle and an App Password.")
        sizer.Add(instructions, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Link to create app password
        app_password_link = wx.adv.HyperlinkCtrl(
            panel, wx.ID_ANY,
            "How do I create an App Password?",
            "https://bsky.app/settings/app-passwords"
        )
        sizer.Add(app_password_link, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Handle input
        handle_label = wx.StaticText(panel, label="Handle (e.g., username.bsky.social):")
        sizer.Add(handle_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.handle_input = wx.TextCtrl(panel)
        sizer.Add(self.handle_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # App Password input
        password_label = wx.StaticText(panel, label="App Password:")
        sizer.Add(password_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.password_input = wx.TextCtrl(panel, style=wx.TE_PASSWORD)
        sizer.Add(self.password_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Service URL (optional, for custom PDS)
        service_label = wx.StaticText(panel, label="Service URL (leave blank for default):")
        sizer.Add(service_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.service_input = wx.TextCtrl(panel)
        self.service_input.SetValue("https://bsky.social")
        sizer.Add(self.service_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, "Login")
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Cancel")
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)
        self.Centre()

        # Set focus to handle input
        self.handle_input.SetFocus()

    def get_credentials(self) -> dict:
        """Return the entered credentials."""
        return {
            'handle': self.handle_input.GetValue().strip(),
            'password': self.password_input.GetValue(),
            'service_url': self.service_input.GetValue().strip() or 'https://bsky.social',
        }


def select_platform(parent=None) -> str:
    """Show platform selection dialog and return the selected platform.

    Returns:
        'mastodon', 'bluesky', or None if cancelled
    """
    import platform
    # On Mac, use None as parent to avoid menu state issues
    if platform.system() == "Darwin":
        parent = None
    dlg = PlatformSelectDialog(parent)
    result = dlg.ShowModal()
    if result == wx.ID_OK:
        plat = dlg.get_platform()
        dlg.Destroy()
        return plat
    dlg.Destroy()
    return None


def get_bluesky_credentials(parent=None) -> dict:
    """Show Bluesky auth dialog and return credentials.

    Returns:
        dict with 'handle', 'password', 'service_url', or None if cancelled
    """
    import platform
    # On Mac, use None as parent to avoid menu state issues
    if platform.system() == "Darwin":
        parent = None
    dlg = BlueskyAuthDialog(parent)
    result = dlg.ShowModal()
    if result == wx.ID_OK:
        creds = dlg.get_credentials()
        dlg.Destroy()
        if creds['handle'] and creds['password']:
            return creds
    dlg.Destroy()
    return None
