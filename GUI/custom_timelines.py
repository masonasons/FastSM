"""Dialog for browsing and adding custom timelines (feeds, local/federated)."""

import wx
import threading
from application import get_app
from . import main
import timeline
import speak


def add_custom_timeline(account, tl_type, tl_id, tl_name, focus=True):
    """Add a custom timeline to the account."""
    # Check if already exists in preferences
    for ct in account.prefs.custom_timelines:
        if ct.get('type') == tl_type and ct.get('id') == tl_id:
            if focus:
                get_app().alert("This timeline is already open.", "Error")
            return False

    # Also check if timeline is already open (e.g., favourites, bookmarks)
    for tl in account.timelines:
        if tl.type == tl_type:
            if focus:
                get_app().alert("This timeline is already open.", "Error")
            return False

    # Add the timeline
    account.timelines.append(timeline.timeline(account, name=tl_name, type=tl_type, data=tl_id))

    # Save to preferences
    account.prefs.custom_timelines.append({
        'type': tl_type,
        'id': tl_id,
        'name': tl_name
    })

    main.window.refreshTimelines()
    if focus:
        main.window.list.SetSelection(len(account.timelines) - 1)
        account.currentIndex = len(account.timelines) - 1
        main.window.on_list_change(None)

    return True


def add_instance_timeline(account, instance_url, focus=True):
    """Add an instance timeline (local timeline from a remote instance).

    Args:
        account: The account to add the timeline to
        instance_url: The URL of the remote instance (e.g., 'mastodon.social')
        focus: Whether to focus the new timeline

    Returns:
        True if successful, False otherwise
    """
    # Normalize URL
    if not instance_url.startswith('http'):
        instance_url = 'https://' + instance_url
    instance_url = instance_url.rstrip('/')

    # Check if already exists
    for inst in account.prefs.instance_timelines:
        if inst.get('url') == instance_url:
            if focus:
                get_app().alert("This instance timeline is already open.", "Error")
            return False

    # Create timeline name from instance URL
    # Extract domain from URL
    domain = instance_url.replace('https://', '').replace('http://', '')
    tl_name = f"{domain} Local"

    # Add the timeline
    account.timelines.append(timeline.timeline(account, name=tl_name, type="instance", data=instance_url))

    # Save to preferences
    account.prefs.instance_timelines.append({
        'url': instance_url,
        'name': tl_name
    })

    main.window.refreshTimelines()
    if focus:
        main.window.list.SetSelection(len(account.timelines) - 1)
        account.currentIndex = len(account.timelines) - 1
        main.window.on_list_change(None)

    return True


def add_remote_user_timeline(account, instance_url, username, focus=True):
    """Add a remote user timeline (user timeline from a remote instance).

    Args:
        account: The account to add the timeline to
        instance_url: The URL of the remote instance (e.g., 'mastodon.social')
        username: The username on that instance
        focus: Whether to focus the new timeline

    Returns:
        True if successful, False otherwise
    """
    # Normalize URL
    if not instance_url.startswith('http'):
        instance_url = 'https://' + instance_url
    instance_url = instance_url.rstrip('/')

    # Normalize username (remove @ if present)
    username = username.lstrip('@')

    # Check if already exists
    for rut in account.prefs.remote_user_timelines:
        if rut.get('url') == instance_url and rut.get('username').lower() == username.lower():
            if focus:
                get_app().alert("This remote user timeline is already open.", "Error")
            return False

    # Create timeline name
    domain = instance_url.replace('https://', '').replace('http://', '')
    tl_name = f"@{username}@{domain}"

    # Add the timeline
    account.timelines.append(timeline.timeline(account, name=tl_name, type="remote_user", data={'url': instance_url, 'username': username}))

    # Save to preferences
    account.prefs.remote_user_timelines.append({
        'url': instance_url,
        'username': username,
        'name': tl_name
    })

    main.window.refreshTimelines()
    if focus:
        main.window.list.SetSelection(len(account.timelines) - 1)
        account.currentIndex = len(account.timelines) - 1
        main.window.on_list_change(None)

    return True


class CustomTimelinesDialog(wx.Dialog):
    """Dialog for browsing and adding custom timelines."""

    def __init__(self, account):
        wx.Dialog.__init__(self, None, title="Add Custom Timeline", size=(500, 400))
        self.account = account
        self.timelines = []

        self.panel = wx.Panel(self)
        self.main_box = wx.BoxSizer(wx.VERTICAL)

        # Platform type determines what's available
        platform_type = getattr(account.prefs, 'platform_type', 'mastodon')

        if platform_type == 'bluesky':
            self._setup_bluesky_ui()
        else:
            self._setup_mastodon_ui()

        # Buttons
        button_box = wx.BoxSizer(wx.HORIZONTAL)
        self.add_btn = wx.Button(self.panel, wx.ID_OK, "&Add")
        self.add_btn.Bind(wx.EVT_BUTTON, self.OnAdd)
        button_box.Add(self.add_btn, 0, wx.ALL, 5)

        self.cancel_btn = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
        self.cancel_btn.Bind(wx.EVT_BUTTON, self.OnCancel)
        button_box.Add(self.cancel_btn, 0, wx.ALL, 5)

        self.main_box.Add(button_box, 0, wx.ALL, 10)

        self.panel.SetSizer(self.main_box)
        self.panel.Layout()

    def _setup_mastodon_ui(self):
        """Set up UI for Mastodon timelines."""
        label = wx.StaticText(self.panel, -1, "Available Timelines:")
        self.main_box.Add(label, 0, wx.ALL, 10)

        self.list = wx.ListBox(self.panel, -1, size=(450, 200))
        self.main_box.Add(self.list, 1, wx.EXPAND | wx.ALL, 10)

        # Get available timelines from platform
        if hasattr(self.account, '_platform') and self.account._platform:
            self.timelines = self.account._platform.get_available_timelines()
        else:
            self.timelines = [
                {'type': 'local', 'id': 'local', 'name': 'Local Timeline', 'description': 'Posts from users on this instance'},
                {'type': 'federated', 'id': 'federated', 'name': 'Federated Timeline', 'description': 'Posts from all known instances'},
            ]

        for tl in self.timelines:
            self.list.Append(f"{tl['name']} - {tl.get('description', '')}")

        if self.list.GetCount() > 0:
            self.list.SetSelection(0)

    def _setup_bluesky_ui(self):
        """Set up UI for Bluesky feeds."""
        # Search box
        search_label = wx.StaticText(self.panel, -1, "Search feeds (leave empty for your saved feeds):")
        self.main_box.Add(search_label, 0, wx.ALL, 5)

        search_box = wx.BoxSizer(wx.HORIZONTAL)
        self.search_text = wx.TextCtrl(self.panel, -1, "")
        search_box.Add(self.search_text, 1, wx.EXPAND | wx.ALL, 5)

        self.search_btn = wx.Button(self.panel, -1, "&Search")
        self.search_btn.Bind(wx.EVT_BUTTON, self.OnSearch)
        search_box.Add(self.search_btn, 0, wx.ALL, 5)

        self.main_box.Add(search_box, 0, wx.EXPAND | wx.ALL, 5)

        # Results list
        list_label = wx.StaticText(self.panel, -1, "Available Feeds:")
        self.main_box.Add(list_label, 0, wx.ALL, 5)

        self.list = wx.ListBox(self.panel, -1, size=(450, 200))
        self.main_box.Add(self.list, 1, wx.EXPAND | wx.ALL, 10)

        # Load saved feeds by default
        self._load_saved_feeds()

    def _load_saved_feeds(self):
        """Load user's saved Bluesky feeds."""
        self.list.Clear()
        self.timelines = []
        speak.speak("Loading saved feeds...")

        def load():
            # Always include Likes as an option
            self.timelines = [
                {'type': 'favourites', 'id': 'favourites', 'name': 'Likes', 'description': 'Posts you have liked'},
            ]
            if hasattr(self.account, '_platform') and self.account._platform:
                self.timelines.extend(self.account._platform.get_saved_feeds())
            wx.CallAfter(self._update_list)

        threading.Thread(target=load, daemon=True).start()

    def _search_feeds(self, query):
        """Search for Bluesky feeds."""
        self.list.Clear()
        self.timelines = []
        speak.speak("Searching...")

        def search():
            if hasattr(self.account, '_platform') and self.account._platform:
                self.timelines = self.account._platform.search_feeds(query)
            wx.CallAfter(self._update_list)

        threading.Thread(target=search, daemon=True).start()

    def _update_list(self):
        """Update the list with loaded timelines."""
        self.list.Clear()
        for tl in self.timelines:
            creator = tl.get('creator', '')
            creator_str = f" by @{creator}" if creator else ""
            self.list.Append(f"{tl['name']}{creator_str}")

        if self.list.GetCount() > 0:
            self.list.SetSelection(0)
            speak.speak(f"{len(self.timelines)} feeds found.")
        else:
            speak.speak("No feeds found.")

    def OnSearch(self, event):
        """Handle search button click."""
        query = self.search_text.GetValue().strip()
        if query:
            self._search_feeds(query)
        else:
            self._load_saved_feeds()

    def OnAdd(self, event):
        """Handle add button click."""
        selection = self.list.GetSelection()
        if selection == wx.NOT_FOUND or selection >= len(self.timelines):
            get_app().alert("Please select a timeline to add.", "Error")
            return

        tl = self.timelines[selection]
        tl_type = tl.get('type', 'feed')

        # Handle instance timeline specially - prompt for instance URL
        if tl_type == 'instance':
            dlg = wx.TextEntryDialog(
                self,
                "Enter the instance URL (e.g., mastodon.social, fosstodon.org):",
                "Instance Timeline"
            )
            if dlg.ShowModal() == wx.ID_OK:
                instance_url = dlg.GetValue().strip()
                dlg.Destroy()
                if instance_url:
                    success = add_instance_timeline(self.account, instance_url)
                    if success:
                        self.Destroy()
                else:
                    get_app().alert("Please enter an instance URL.", "Error")
            else:
                dlg.Destroy()
            return

        # Handle remote user timeline - prompt for instance URL and username
        if tl_type == 'remote_user':
            dlg = wx.TextEntryDialog(
                self,
                "Enter the instance URL (e.g., mastodon.social, fosstodon.org):",
                "Remote User Timeline"
            )
            if dlg.ShowModal() == wx.ID_OK:
                instance_url = dlg.GetValue().strip()
                dlg.Destroy()
                if instance_url:
                    # Now prompt for username
                    dlg2 = wx.TextEntryDialog(
                        self,
                        "Enter the username (e.g., user or @user):",
                        "Remote User Timeline"
                    )
                    if dlg2.ShowModal() == wx.ID_OK:
                        username = dlg2.GetValue().strip()
                        dlg2.Destroy()
                        if username:
                            success = add_remote_user_timeline(self.account, instance_url, username)
                            if success:
                                self.Destroy()
                        else:
                            get_app().alert("Please enter a username.", "Error")
                    else:
                        dlg2.Destroy()
                else:
                    get_app().alert("Please enter an instance URL.", "Error")
            else:
                dlg.Destroy()
            return

        success = add_custom_timeline(
            self.account,
            tl_type,
            tl['id'],
            tl['name']
        )

        if success:
            self.Destroy()

    def OnCancel(self, event):
        """Handle cancel button click."""
        self.Destroy()
