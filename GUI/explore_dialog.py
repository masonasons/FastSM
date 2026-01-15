"""Explore/Discover dialog for finding users, trending content, and feeds."""

import threading
import webbrowser
import wx

from application import get_app
from . import misc, view, custom_timelines


class ExploreDialog(wx.Dialog):
    """Dialog for exploring and discovering content on Mastodon/Bluesky."""

    # Category constants
    MASTODON_CATEGORIES = [
        ('users', 'Discover Users'),
        ('trending_posts', 'Trending Posts'),
        ('trending_tags', 'Trending Tags'),
        ('trending_links', 'Trending Links'),
    ]

    BLUESKY_CATEGORIES = [
        ('suggested_users', 'Suggested Users'),
        ('suggested_feeds', 'Suggested Feeds'),
        ('popular_feeds', 'Popular Feeds'),
    ]

    def __init__(self, account):
        self.account = account
        self.items = []  # Current items in the list
        self.current_category = None
        self.loading = False

        # Determine platform
        self.platform_type = getattr(account.prefs, 'platform_type', 'mastodon')
        if self.platform_type == 'bluesky':
            self.categories = self.BLUESKY_CATEGORIES
        else:
            self.categories = self.MASTODON_CATEGORIES

        title = "Explore" if self.platform_type == 'mastodon' else "Discover"
        wx.Dialog.__init__(self, None, title=title, size=(500, 400))

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.panel = wx.Panel(self)
        self.main_box = wx.BoxSizer(wx.VERTICAL)

        # Category selector
        self.category_label = wx.StaticText(self.panel, -1, "&Category")
        self.main_box.Add(self.category_label, 0, wx.LEFT | wx.TOP, 10)

        category_names = [c[1] for c in self.categories]
        self.category_choice = wx.Choice(self.panel, -1, choices=category_names)
        self.category_choice.SetSelection(0)
        self.category_choice.Bind(wx.EVT_CHOICE, self.OnCategoryChange)
        self.main_box.Add(self.category_choice, 0, wx.ALL | wx.EXPAND, 10)

        # Results list
        self.list_label = wx.StaticText(self.panel, -1, "&Results")
        self.main_box.Add(self.list_label, 0, wx.LEFT, 10)

        self.list = wx.ListBox(self.panel, -1, size=(480, 200))
        self.list.Bind(wx.EVT_LISTBOX, self.OnListChange)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, self.OnView)
        self.main_box.Add(self.list, 1, wx.ALL | wx.EXPAND, 10)

        # Action buttons (will be shown/hidden based on category)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.view_btn = wx.Button(self.panel, -1, "&View")
        self.view_btn.Bind(wx.EVT_BUTTON, self.OnView)
        button_sizer.Add(self.view_btn, 0, wx.ALL, 5)

        self.follow_btn = wx.Button(self.panel, -1, "&Follow")
        self.follow_btn.Bind(wx.EVT_BUTTON, self.OnFollow)
        button_sizer.Add(self.follow_btn, 0, wx.ALL, 5)

        self.timeline_btn = wx.Button(self.panel, -1, "Open &Timeline")
        self.timeline_btn.Bind(wx.EVT_BUTTON, self.OnOpenTimeline)
        button_sizer.Add(self.timeline_btn, 0, wx.ALL, 5)

        self.open_btn = wx.Button(self.panel, -1, "Open in &Browser")
        self.open_btn.Bind(wx.EVT_BUTTON, self.OnOpenBrowser)
        button_sizer.Add(self.open_btn, 0, wx.ALL, 5)

        self.main_box.Add(button_sizer, 0, wx.ALL, 5)

        # Refresh and Close buttons
        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.refresh_btn = wx.Button(self.panel, -1, "&Refresh")
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.OnRefresh)
        bottom_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)

        self.close_btn = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
        self.close_btn.Bind(wx.EVT_BUTTON, self.OnClose)
        bottom_sizer.Add(self.close_btn, 0, wx.ALL, 5)

        self.main_box.Add(bottom_sizer, 0, wx.ALL, 5)

        self.panel.SetSizer(self.main_box)
        self.panel.Layout()

        # Disable buttons initially
        self._update_buttons()

        # Load initial category
        self.LoadCategory(0)
        self.category_choice.SetFocus()

    def _update_buttons(self):
        """Enable/disable buttons based on current category and selection."""
        has_selection = self.list.GetSelection() != wx.NOT_FOUND
        category = self.current_category

        # Default all disabled
        self.view_btn.Enable(False)
        self.follow_btn.Enable(False)
        self.timeline_btn.Enable(False)
        self.open_btn.Enable(False)

        if not has_selection:
            return

        if category in ('users', 'suggested_users'):
            self.view_btn.Enable(True)
            self.follow_btn.Enable(True)
            self.timeline_btn.Enable(True)
        elif category == 'trending_posts':
            self.view_btn.Enable(True)
        elif category in ('trending_tags',):
            self.timeline_btn.Enable(True)
        elif category in ('trending_links',):
            self.open_btn.Enable(True)
        elif category in ('suggested_feeds', 'popular_feeds'):
            self.timeline_btn.Enable(True)

    def OnCategoryChange(self, event):
        """Handle category selection change."""
        index = self.category_choice.GetSelection()
        self.LoadCategory(index)

    def LoadCategory(self, index):
        """Load data for the selected category."""
        if self.loading:
            return

        self.current_category = self.categories[index][0]
        self.loading = True
        self.list.Clear()
        self.list.Append("Loading...")
        self.items = []
        self._update_buttons()

        def load():
            items = []
            try:
                platform = getattr(self.account, '_platform', None)
                if not platform:
                    wx.CallAfter(self._on_load_error, "Platform not available")
                    return

                if self.current_category == 'users':
                    items = platform.get_directory(limit=40)
                elif self.current_category == 'trending_posts':
                    items = platform.get_trending_statuses(limit=20)
                elif self.current_category == 'trending_tags':
                    items = platform.get_trending_tags(limit=20)
                elif self.current_category == 'trending_links':
                    items = platform.get_trending_links(limit=20)
                elif self.current_category == 'suggested_users':
                    items = platform.get_suggested_users(limit=50)
                elif self.current_category == 'suggested_feeds':
                    items = platform.get_suggested_feeds(limit=50)
                elif self.current_category == 'popular_feeds':
                    items = platform.get_popular_feeds(limit=50)

                wx.CallAfter(self._on_load_complete, items)
            except Exception as e:
                wx.CallAfter(self._on_load_error, str(e))

        threading.Thread(target=load, daemon=True).start()

    def _on_load_complete(self, items):
        """Handle load completion on main thread."""
        self.loading = False
        self.items = items
        self.list.Clear()

        if not items:
            self.list.Append("No items found")
            return

        for item in items:
            display = self._format_item(item)
            self.list.Append(display)

        if self.list.GetCount() > 0:
            self.list.SetSelection(0)
            self._update_buttons()

    def _on_load_error(self, error):
        """Handle load error."""
        self.loading = False
        self.list.Clear()
        self.list.Append(f"Error: {error}")

    def _format_item(self, item):
        """Format an item for display in the list."""
        if self.current_category in ('users', 'suggested_users'):
            # User object
            display_name = getattr(item, 'display_name', '') or getattr(item, 'acct', 'Unknown')
            acct = getattr(item, 'acct', '')
            followers = getattr(item, 'followers_count', 0)
            return f"{display_name} (@{acct}) - {followers} followers"

        elif self.current_category == 'trending_posts':
            # Status object
            author = getattr(item.account, 'display_name', '') or item.account.acct
            content = self.account.app.strip_html(getattr(item, 'content', ''))[:80]
            boosts = getattr(item, 'reblogs_count', 0) or getattr(item, 'boosts_count', 0)
            return f"{author}: {content}... ({boosts} boosts)"

        elif self.current_category == 'trending_tags':
            # Dict with name, url, history
            name = item.get('name', '')
            return f"#{name}"

        elif self.current_category == 'trending_links':
            # Dict with title, url, description
            title = item.get('title', 'Untitled')
            provider = item.get('provider_name', '')
            if provider:
                return f"{title} ({provider})"
            return title

        elif self.current_category in ('suggested_feeds', 'popular_feeds'):
            # Dict with name, description, creator
            name = item.get('name', 'Unnamed')
            creator = item.get('creator', '')
            likes = item.get('likes', 0)
            if creator:
                return f"{name} by @{creator} ({likes} likes)"
            return f"{name} ({likes} likes)"

        return str(item)

    def OnListChange(self, event):
        """Handle list selection change."""
        self._update_buttons()

    def OnView(self, event):
        """View the selected item."""
        index = self.list.GetSelection()
        if index == wx.NOT_FOUND or index >= len(self.items):
            return

        item = self.items[index]

        if self.current_category in ('users', 'suggested_users'):
            # Open user viewer
            g = view.UserViewGui(self.account, [item], "User Profile")
            g.Show()
        elif self.current_category == 'trending_posts':
            # Open post viewer
            v = view.ViewGui(self.account, item)
            v.Show()

    def OnFollow(self, event):
        """Follow the selected user."""
        import sound
        import speak
        index = self.list.GetSelection()
        if index == wx.NOT_FOUND or index >= len(self.items):
            return

        item = self.items[index]
        if self.current_category in ('users', 'suggested_users'):
            user_id = getattr(item, 'id', None)
            if user_id:
                try:
                    self.account.follow(user_id)
                    sound.play(self.account, "follow")
                except Exception as error:
                    self.account.app.handle_error(error, "Follow user")

    def OnOpenTimeline(self, event):
        """Open a timeline for the selected item."""
        index = self.list.GetSelection()
        if index == wx.NOT_FOUND or index >= len(self.items):
            return

        item = self.items[index]

        if self.current_category in ('users', 'suggested_users'):
            # Open user timeline
            acct = getattr(item, 'acct', '')
            if acct:
                misc.user_timeline_user(self.account, acct)
                self.Destroy()

        elif self.current_category == 'trending_tags':
            # Open hashtag search timeline
            tag = item.get('name', '')
            if tag:
                misc.search(self.account, f"#{tag}")
                self.Destroy()

        elif self.current_category in ('suggested_feeds', 'popular_feeds'):
            # Open feed timeline
            uri = item.get('uri', '')
            name = item.get('name', 'Feed')
            if uri:
                custom_timelines.add_custom_timeline(self.account, 'feed', uri, name)
                self.Destroy()

    def OnOpenBrowser(self, event):
        """Open the selected link in browser."""
        index = self.list.GetSelection()
        if index == wx.NOT_FOUND or index >= len(self.items):
            return

        item = self.items[index]

        if self.current_category == 'trending_links':
            url = item.get('url', '')
            if url:
                webbrowser.open(url)

    def OnRefresh(self, event):
        """Refresh the current category."""
        index = self.category_choice.GetSelection()
        self.LoadCategory(index)

    def OnClose(self, event):
        """Close the dialog."""
        self.Destroy()
