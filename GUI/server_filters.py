"""Dialog for managing Mastodon server-side filters."""

import wx
import speak
from application import get_app


# Context options for filters
CONTEXT_OPTIONS = [
    ("Home timeline", "home"),
    ("Notifications", "notifications"),
    ("Public timelines", "public"),
    ("Conversations", "thread"),
    ("Profiles", "account"),
]

# Filter action options
ACTION_OPTIONS = [
    ("Hide completely", "hide"),
    ("Show with warning", "warn"),
]

# Expiration options (in seconds, 0 = never)
EXPIRATION_OPTIONS = [
    ("Never", 0),
    ("30 minutes", 1800),
    ("1 hour", 3600),
    ("6 hours", 21600),
    ("12 hours", 43200),
    ("1 day", 86400),
    ("1 week", 604800),
]


class ServerFiltersDialog(wx.Dialog):
    """Dialog for viewing and managing server-side filters."""

    def __init__(self, parent, account):
        wx.Dialog.__init__(self, parent, title="Server Filters", size=(500, 400))
        self.account = account
        self.filters = []

        panel = wx.Panel(self)
        main_box = wx.BoxSizer(wx.VERTICAL)

        # Check if this is a Mastodon account
        platform_type = getattr(account.prefs, 'platform_type', 'mastodon')
        if platform_type != 'mastodon':
            label = wx.StaticText(panel, -1, "Server filters are only available for Mastodon accounts.")
            main_box.Add(label, 0, wx.ALL, 10)
            close_btn = wx.Button(panel, wx.ID_CANCEL, "&Close")
            main_box.Add(close_btn, 0, wx.ALL, 10)
            panel.SetSizer(main_box)
            return

        # Filter list
        list_label = wx.StaticText(panel, -1, "&Filters:")
        main_box.Add(list_label, 0, wx.ALL, 5)

        self.filter_list = wx.ListBox(panel, -1, size=(450, 200))
        main_box.Add(self.filter_list, 1, wx.ALL | wx.EXPAND, 5)

        # Buttons
        button_box = wx.BoxSizer(wx.HORIZONTAL)

        add_btn = wx.Button(panel, -1, "&Add")
        add_btn.Bind(wx.EVT_BUTTON, self.on_add)
        button_box.Add(add_btn, 0, wx.ALL, 5)

        edit_btn = wx.Button(panel, -1, "&Edit")
        edit_btn.Bind(wx.EVT_BUTTON, self.on_edit)
        button_box.Add(edit_btn, 0, wx.ALL, 5)

        delete_btn = wx.Button(panel, -1, "&Delete")
        delete_btn.Bind(wx.EVT_BUTTON, self.on_delete)
        button_box.Add(delete_btn, 0, wx.ALL, 5)

        refresh_btn = wx.Button(panel, -1, "&Refresh")
        refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        button_box.Add(refresh_btn, 0, wx.ALL, 5)

        close_btn = wx.Button(panel, wx.ID_CANCEL, "&Close")
        button_box.Add(close_btn, 0, wx.ALL, 5)

        main_box.Add(button_box, 0, wx.ALL | wx.ALIGN_CENTER, 5)

        panel.SetSizer(main_box)

        # Load filters
        self.load_filters()

    def load_filters(self):
        """Load filters from the server."""
        self.filter_list.Clear()
        try:
            self.filters = self.account.api.filters_v2()
            for f in self.filters:
                # Build display string
                keywords = [kw.keyword for kw in getattr(f, 'keywords', [])]
                keyword_str = ", ".join(keywords[:3])
                if len(keywords) > 3:
                    keyword_str += f" (+{len(keywords) - 3} more)"

                contexts = getattr(f, 'context', [])
                action = getattr(f, 'filter_action', 'warn')

                display = f"{f.title}: {keyword_str} [{action}]"
                self.filter_list.Append(display)

            if self.filters:
                self.filter_list.SetSelection(0)
                speak.speak(f"Loaded {len(self.filters)} filters")
            else:
                speak.speak("No filters")
        except Exception as e:
            speak.speak(f"Error loading filters: {e}")
            self.account.app.handle_error(e, "Load Filters")

    def on_add(self, event):
        """Add a new filter."""
        dlg = EditFilterDialog(self, self.account, None)
        if dlg.ShowModal() == wx.ID_OK:
            self.load_filters()
        dlg.Destroy()

    def on_edit(self, event):
        """Edit the selected filter."""
        selection = self.filter_list.GetSelection()
        if selection < 0 or selection >= len(self.filters):
            speak.speak("No filter selected")
            return

        dlg = EditFilterDialog(self, self.account, self.filters[selection])
        if dlg.ShowModal() == wx.ID_OK:
            self.load_filters()
        dlg.Destroy()

    def on_delete(self, event):
        """Delete the selected filter."""
        selection = self.filter_list.GetSelection()
        if selection < 0 or selection >= len(self.filters):
            speak.speak("No filter selected")
            return

        filter_obj = self.filters[selection]
        dlg = wx.MessageDialog(
            self,
            f"Are you sure you want to delete the filter '{filter_obj.title}'?",
            "Confirm Delete",
            wx.YES_NO | wx.ICON_QUESTION
        )
        if dlg.ShowModal() == wx.ID_YES:
            try:
                self.account.api.delete_filter_v2(filter_obj.id)
                speak.speak("Filter deleted")
                self.load_filters()
            except Exception as e:
                speak.speak(f"Error deleting filter: {e}")
                self.account.app.handle_error(e, "Delete Filter")
        dlg.Destroy()

    def on_refresh(self, event):
        """Refresh the filter list."""
        self.load_filters()


class EditFilterDialog(wx.Dialog):
    """Dialog for adding or editing a filter."""

    def __init__(self, parent, account, filter_obj=None):
        title = "Edit Filter" if filter_obj else "Add Filter"
        wx.Dialog.__init__(self, parent, title=title, size=(450, 500))
        self.account = account
        self.filter_obj = filter_obj
        self.is_new = filter_obj is None

        panel = wx.Panel(self)
        main_box = wx.BoxSizer(wx.VERTICAL)

        # Title
        title_box = wx.BoxSizer(wx.HORIZONTAL)
        title_label = wx.StaticText(panel, -1, "&Title:")
        title_box.Add(title_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.title_text = wx.TextCtrl(panel, -1, size=(300, -1))
        title_box.Add(self.title_text, 1, wx.ALL | wx.EXPAND, 5)
        main_box.Add(title_box, 0, wx.EXPAND)

        # Keywords
        keywords_label = wx.StaticText(panel, -1, "&Keywords (one per line):")
        main_box.Add(keywords_label, 0, wx.ALL, 5)
        self.keywords_text = wx.TextCtrl(panel, -1, style=wx.TE_MULTILINE, size=(400, 100))
        main_box.Add(self.keywords_text, 0, wx.ALL | wx.EXPAND, 5)

        # Whole word checkbox
        self.whole_word = wx.CheckBox(panel, -1, "Match &whole word only")
        self.whole_word.SetValue(True)
        main_box.Add(self.whole_word, 0, wx.ALL, 5)

        # Context checkboxes
        context_label = wx.StaticText(panel, -1, "Filter &contexts:")
        main_box.Add(context_label, 0, wx.ALL, 5)

        self.context_checks = {}
        for label, value in CONTEXT_OPTIONS:
            cb = wx.CheckBox(panel, -1, label)
            cb.SetValue(True)  # Default all checked
            self.context_checks[value] = cb
            main_box.Add(cb, 0, wx.LEFT, 20)

        # Action
        action_box = wx.BoxSizer(wx.HORIZONTAL)
        action_label = wx.StaticText(panel, -1, "&Action:")
        action_box.Add(action_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.action_choice = wx.Choice(panel, -1, choices=[a[0] for a in ACTION_OPTIONS])
        self.action_choice.SetSelection(0)
        action_box.Add(self.action_choice, 0, wx.ALL, 5)
        main_box.Add(action_box, 0)

        # Expiration
        expire_box = wx.BoxSizer(wx.HORIZONTAL)
        expire_label = wx.StaticText(panel, -1, "E&xpires:")
        expire_box.Add(expire_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.expire_choice = wx.Choice(panel, -1, choices=[e[0] for e in EXPIRATION_OPTIONS])
        self.expire_choice.SetSelection(0)
        expire_box.Add(self.expire_choice, 0, wx.ALL, 5)
        main_box.Add(expire_box, 0)

        # Buttons
        button_box = wx.BoxSizer(wx.HORIZONTAL)
        save_btn = wx.Button(panel, wx.ID_OK, "&Save")
        save_btn.Bind(wx.EVT_BUTTON, self.on_save)
        save_btn.SetDefault()
        button_box.Add(save_btn, 0, wx.ALL, 5)
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, "&Cancel")
        button_box.Add(cancel_btn, 0, wx.ALL, 5)
        main_box.Add(button_box, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        panel.SetSizer(main_box)

        # Load existing filter data if editing
        if filter_obj:
            self.load_filter_data()

        self.title_text.SetFocus()

    def load_filter_data(self):
        """Load data from existing filter."""
        self.title_text.SetValue(self.filter_obj.title or "")

        # Keywords
        keywords = [kw.keyword for kw in getattr(self.filter_obj, 'keywords', [])]
        self.keywords_text.SetValue("\n".join(keywords))

        # Whole word - use first keyword's setting if available
        if getattr(self.filter_obj, 'keywords', []):
            self.whole_word.SetValue(getattr(self.filter_obj.keywords[0], 'whole_word', True))

        # Context
        contexts = getattr(self.filter_obj, 'context', [])
        for value, cb in self.context_checks.items():
            cb.SetValue(value in contexts)

        # Action
        action = getattr(self.filter_obj, 'filter_action', 'warn')
        for i, (_, val) in enumerate(ACTION_OPTIONS):
            if val == action:
                self.action_choice.SetSelection(i)
                break

    def on_save(self, event):
        """Save the filter."""
        title = self.title_text.GetValue().strip()
        if not title:
            speak.speak("Title is required")
            return

        keywords_raw = self.keywords_text.GetValue().strip()
        keywords = [k.strip() for k in keywords_raw.split("\n") if k.strip()]
        if not keywords:
            speak.speak("At least one keyword is required")
            return

        # Get contexts
        contexts = [val for val, cb in self.context_checks.items() if cb.GetValue()]
        if not contexts:
            speak.speak("At least one context is required")
            return

        # Get action
        action_idx = self.action_choice.GetSelection()
        action = ACTION_OPTIONS[action_idx][1]

        # Get expiration
        expire_idx = self.expire_choice.GetSelection()
        expires_in = EXPIRATION_OPTIONS[expire_idx][1] or None

        # Build keywords attributes
        whole_word = self.whole_word.GetValue()
        keywords_attributes = [{"keyword": k, "whole_word": whole_word} for k in keywords]

        try:
            if self.is_new:
                self.account.api.create_filter_v2(
                    title=title,
                    context=contexts,
                    filter_action=action,
                    expires_in=expires_in,
                    keywords_attributes=keywords_attributes
                )
                speak.speak("Filter created")
            else:
                self.account.api.update_filter_v2(
                    self.filter_obj.id,
                    title=title,
                    context=contexts,
                    filter_action=action,
                    expires_in=expires_in,
                    keywords_attributes=keywords_attributes
                )
                speak.speak("Filter updated")

            self.EndModal(wx.ID_OK)
        except Exception as e:
            speak.speak(f"Error saving filter: {e}")
            self.account.app.handle_error(e, "Save Filter")


def show_server_filters_dialog(account):
    """Show the server filters dialog."""
    from . import main as main_window
    dlg = ServerFiltersDialog(main_window.window, account)
    dlg.ShowModal()
    dlg.Destroy()
