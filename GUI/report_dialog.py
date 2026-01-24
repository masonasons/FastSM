"""Report dialog for reporting users and posts."""

import wx
import speak
import sound
from application import get_app


# Report categories that work for both Mastodon and Bluesky
REPORT_CATEGORIES = [
    ("spam", "Spam", "Unwanted commercial content, misleading links, or repetitive posts"),
    ("violation", "Rule Violation", "Violates server or platform rules"),
    ("other", "Other", "Other reason not listed above"),
]

# Mastodon-specific category
MASTODON_CATEGORIES = [
    ("legal", "Legal Issue", "Content that may be illegal in your jurisdiction"),
]


class ReportDialog(wx.Dialog):
    """Dialog for reporting a user or post."""

    def __init__(self, account, user=None, status=None, parent=None):
        """Initialize report dialog.

        Args:
            account: The current account
            user: The user being reported (required)
            status: Optional status providing context (for post reports)
            parent: Parent window
        """
        self.account = account
        self.user = user
        self.status = status

        # Determine what we're reporting
        if status:
            title = f"Report Post by @{user.acct}"
        else:
            title = f"Report @{user.acct}"

        wx.Dialog.__init__(self, parent, title=title, size=(450, 400))
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.panel = wx.Panel(self)
        self.main_box = wx.BoxSizer(wx.VERTICAL)

        # Category selection
        cat_label = wx.StaticText(self.panel, -1, "&Category:")
        self.main_box.Add(cat_label, 0, wx.LEFT | wx.TOP, 10)

        # Build category list based on platform
        platform_type = getattr(account.prefs, 'platform_type', 'mastodon')
        self.categories = list(REPORT_CATEGORIES)
        if platform_type == 'mastodon':
            # Insert legal before other
            self.categories.insert(2, MASTODON_CATEGORIES[0])

        category_choices = [f"{cat[1]} - {cat[2]}" for cat in self.categories]
        self.category = wx.Choice(self.panel, -1, choices=category_choices)
        self.category.SetSelection(0)
        self.main_box.Add(self.category, 0, wx.EXPAND | wx.ALL, 10)

        # Comment/reason
        comment_label = wx.StaticText(self.panel, -1, "&Additional details (optional):")
        self.main_box.Add(comment_label, 0, wx.LEFT | wx.TOP, 10)

        self.comment = wx.TextCtrl(self.panel, -1, style=wx.TE_MULTILINE, size=(400, 100))
        self.main_box.Add(self.comment, 0, wx.EXPAND | wx.ALL, 10)

        # Forward to remote server option (Mastodon only)
        if platform_type == 'mastodon':
            # Check if user is from a remote server
            user_domain = user.acct.split('@')[-1] if '@' in user.acct else None
            if user_domain:
                self.forward = wx.CheckBox(self.panel, -1, f"&Forward report to {user_domain}")
                self.forward.SetValue(True)
                self.main_box.Add(self.forward, 0, wx.LEFT | wx.TOP, 10)
            else:
                self.forward = None
        else:
            self.forward = None

        # Info text
        if status:
            info = "This will report the post and its author to the moderation team."
        else:
            info = "This will report the user to the moderation team."

        info_text = wx.StaticText(self.panel, -1, info)
        self.main_box.Add(info_text, 0, wx.ALL, 10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.submit_btn = wx.Button(self.panel, -1, "&Submit Report")
        self.submit_btn.Bind(wx.EVT_BUTTON, self.OnSubmit)
        btn_sizer.Add(self.submit_btn, 0, wx.ALL, 5)

        self.cancel_btn = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
        self.cancel_btn.Bind(wx.EVT_BUTTON, self.OnClose)
        btn_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)

        self.main_box.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.panel.SetSizer(self.main_box)
        self.category.SetFocus()

    def OnSubmit(self, event):
        """Submit the report."""
        category_index = self.category.GetSelection()
        category = self.categories[category_index][0]
        comment = self.comment.GetValue().strip()
        forward = self.forward.GetValue() if self.forward else False

        try:
            platform_type = getattr(self.account.prefs, 'platform_type', 'mastodon')

            if platform_type == 'bluesky':
                # Bluesky reporting
                if hasattr(self.account, '_platform') and self.account._platform:
                    self.account._platform.report(
                        user_id=self.user.id,
                        status_id=self.status.id if self.status else None,
                        category=category,
                        comment=comment
                    )
            else:
                # Mastodon reporting
                status_ids = [self.status.id] if self.status else None
                self.account.api.report(
                    account_id=self.user.id,
                    status_ids=status_ids,
                    comment=comment,
                    forward=forward,
                    category=category
                )

            sound.play(self.account, "send")
            speak.speak("Report submitted")
            self.EndModal(wx.ID_OK)

        except Exception as e:
            self.account.app.handle_error(e, "Submit report")

    def OnClose(self, event):
        """Close the dialog."""
        self.EndModal(wx.ID_CANCEL)


def report_user(account, user, parent=None):
    """Show report dialog for a user.

    Args:
        account: The current account
        user: The user to report
        parent: Parent window
    """
    dlg = ReportDialog(account, user=user, parent=parent)
    dlg.ShowModal()
    dlg.Destroy()


def report_status(account, status, parent=None):
    """Show report dialog for a status/post.

    Args:
        account: The current account
        status: The status to report
        parent: Parent window
    """
    # Get the user from the status
    user = status.account if hasattr(status, 'account') else None
    if not user:
        speak.speak("Cannot report: no user information available")
        return

    dlg = ReportDialog(account, user=user, status=status, parent=parent)
    dlg.ShowModal()
    dlg.Destroy()
