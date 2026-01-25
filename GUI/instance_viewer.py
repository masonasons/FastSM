"""Instance information viewer dialog."""

import threading
import wx

from application import get_app
from . import theme
import speak


class InstanceViewerDialog(wx.Dialog):
    """Dialog for viewing instance information."""

    def __init__(self, account, instance_url=None):
        """
        Args:
            account: The account to use for API calls
            instance_url: URL of instance to view. If None, shows current instance.
        """
        self.account = account
        self.instance_url = instance_url
        self.info = None

        # Determine title
        if instance_url:
            title = f"Instance Info: {instance_url}"
        else:
            title = "Instance Info"

        wx.Dialog.__init__(self, None, title=title, size=(500, 400))

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.panel = wx.Panel(self)
        self.main_box = wx.BoxSizer(wx.VERTICAL)

        # Info text area
        self.info_label = wx.StaticText(self.panel, -1, "&Instance Information")
        self.main_box.Add(self.info_label, 0, wx.LEFT | wx.TOP, 10)

        self.info_text = wx.TextCtrl(
            self.panel,
            style=wx.TE_READONLY | wx.TE_MULTILINE,
            size=(480, 300),
            name="Instance Information"
        )
        self.info_text.SetValue("Loading...")
        self.main_box.Add(self.info_text, 1, wx.ALL | wx.EXPAND, 10)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.refresh_btn = wx.Button(self.panel, -1, "&Refresh")
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.OnRefresh)
        button_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)

        self.close_btn = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
        self.close_btn.Bind(wx.EVT_BUTTON, self.OnClose)
        button_sizer.Add(self.close_btn, 0, wx.ALL, 5)

        self.main_box.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        self.panel.SetSizer(self.main_box)

        # Apply theme
        theme.apply_theme(self)

        # Load info in background
        self.LoadInfo()

    def LoadInfo(self):
        """Load instance info in a background thread."""
        self.info_text.SetValue("Loading instance information...")

        def fetch():
            try:
                if hasattr(self.account, '_platform') and self.account._platform:
                    info = self.account._platform.get_instance_info(self.instance_url)
                else:
                    info = {'error': 'Platform backend not available'}
                wx.CallAfter(self.DisplayInfo, info)
            except Exception as e:
                wx.CallAfter(self.DisplayInfo, {'error': str(e)})

        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()

    def DisplayInfo(self, info):
        """Display the instance information."""
        self.info = info

        if 'error' in info:
            self.info_text.SetValue(f"Error: {info['error']}")
            speak.speak(f"Error loading instance info: {info['error']}")
            return

        # Build display text
        lines = []

        # Basic info
        if info.get('title'):
            lines.append(f"Name: {info['title']}")
        if info.get('domain'):
            lines.append(f"Domain: {info['domain']}")
        if info.get('version'):
            lines.append(f"Version: {info['version']}")

        # Description
        if info.get('description'):
            lines.append("")
            lines.append("Description:")
            # Strip HTML if present
            desc = info['description']
            desc = get_app().strip_html(desc)
            lines.append(desc)

        # Stats
        stats = info.get('stats', {})
        if stats:
            lines.append("")
            lines.append("Statistics:")
            if 'active_month' in stats:
                lines.append(f"  Monthly Active Users: {stats['active_month']:,}")
            if 'user_count' in stats:
                lines.append(f"  Total Users: {stats['user_count']:,}")
            if 'status_count' in stats:
                lines.append(f"  Total Posts: {stats['status_count']:,}")
            if 'domain_count' in stats:
                lines.append(f"  Known Instances: {stats['domain_count']:,}")

        # Configuration/Limits
        config = info.get('configuration', {})
        if config:
            lines.append("")
            lines.append("Limits:")
            if config.get('max_characters'):
                lines.append(f"  Max Characters: {config['max_characters']:,}")
            if config.get('max_media_attachments'):
                lines.append(f"  Max Media per Post: {config['max_media_attachments']}")
            if config.get('characters_reserved_per_url'):
                lines.append(f"  Characters per URL: {config['characters_reserved_per_url']}")
            if config.get('max_pinned_statuses'):
                lines.append(f"  Max Pinned Posts: {config['max_pinned_statuses']}")

            # Media limits
            if config.get('image_size_limit') or config.get('video_size_limit'):
                lines.append("")
                lines.append("Media Limits:")
                if config.get('image_size_limit'):
                    size_mb = config['image_size_limit'] / (1024 * 1024)
                    lines.append(f"  Max Image Size: {size_mb:.1f} MB")
                if config.get('video_size_limit'):
                    size_mb = config['video_size_limit'] / (1024 * 1024)
                    lines.append(f"  Max Video Size: {size_mb:.1f} MB")
                if config.get('video_frame_rate_limit'):
                    lines.append(f"  Max Video Frame Rate: {config['video_frame_rate_limit']} fps")

            # Poll limits
            if config.get('poll_max_options'):
                lines.append("")
                lines.append("Poll Limits:")
                lines.append(f"  Max Options: {config['poll_max_options']}")
                if config.get('poll_max_characters_per_option'):
                    lines.append(f"  Max Characters per Option: {config['poll_max_characters_per_option']}")
                if config.get('poll_min_expiration') and config.get('poll_max_expiration'):
                    min_hours = config['poll_min_expiration'] / 3600
                    max_days = config['poll_max_expiration'] / 86400
                    lines.append(f"  Duration: {min_hours:.0f} hours to {max_days:.0f} days")

            # Features
            if config.get('translation_enabled'):
                lines.append("")
                lines.append("Features:")
                lines.append("  Translation: Enabled")

        # Registration info
        registrations = info.get('registrations', {})
        if registrations:
            lines.append("")
            lines.append("Registration:")
            if registrations.get('enabled'):
                if registrations.get('approval_required'):
                    lines.append("  Open with approval required")
                else:
                    lines.append("  Open")
            else:
                lines.append("  Closed")

        # Contact info
        if info.get('contact_email') or info.get('contact_account'):
            lines.append("")
            lines.append("Contact:")
            if info.get('contact_email'):
                lines.append(f"  Email: {info['contact_email']}")
            contact_account = info.get('contact_account')
            if contact_account:
                acct = getattr(contact_account, 'acct', None)
                display_name = getattr(contact_account, 'display_name', None)
                if acct:
                    if display_name:
                        lines.append(f"  Admin: {display_name} (@{acct})")
                    else:
                        lines.append(f"  Admin: @{acct}")

        # Languages
        languages = info.get('languages', [])
        if languages:
            lines.append("")
            lines.append(f"Languages: {', '.join(languages)}")

        # Rules
        rules = info.get('rules', [])
        if rules:
            lines.append("")
            lines.append("Server Rules:")
            for i, rule in enumerate(rules, 1):
                lines.append(f"  {i}. {rule}")

        # Source URL
        if info.get('source_url'):
            lines.append("")
            lines.append(f"Source: {info['source_url']}")

        text = "\n".join(lines)
        self.info_text.SetValue(text)
        self.info_text.SetInsertionPoint(0)

        # Announce
        title = info.get('title', info.get('domain', 'Unknown'))
        speak.speak(f"Instance info loaded for {title}")

    def OnRefresh(self, event):
        """Refresh the instance info."""
        self.LoadInfo()

    def OnClose(self, event):
        """Close the dialog."""
        self.Destroy()


def view_instance(account, instance_url=None):
    """Show instance viewer dialog.

    Args:
        account: The account to use for API calls
        instance_url: URL of instance to view. If None, shows current instance.
    """
    dlg = InstanceViewerDialog(account, instance_url)
    dlg.Show()
