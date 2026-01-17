"""Dialog for viewing and managing followed hashtags."""

import platform
import wx
import sound
import speak
from application import get_app
from . import misc, theme

class FollowedHashtagsDialog(wx.Dialog):
    """Dialog showing followed hashtags with ability to unfollow."""

    def __init__(self, account, hashtags):
        self.account = account
        self.hashtags = hashtags  # List of dicts with 'name', 'url', 'following'

        wx.Dialog.__init__(self, None, title="Followed Hashtags", size=(400, 300))
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.panel = wx.Panel(self)
        self.main_box = wx.BoxSizer(wx.VERTICAL)

        # Hashtags list
        self.list_label = wx.StaticText(self.panel, -1, "&Hashtags")
        self.main_box.Add(self.list_label, 0, wx.LEFT | wx.TOP, 10)

        self.list = wx.ListBox(self.panel, -1, size=(380, 150), name="Hashtags")
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, self.OnOpenTimeline)
        self.main_box.Add(self.list, 1, wx.ALL | wx.EXPAND, 10)

        # Populate list
        for tag in self.hashtags:
            name = tag.get('name', '')
            if name:
                self.list.Append(f"#{name}")

        if self.list.GetCount() > 0:
            self.list.SetSelection(0)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.timeline_btn = wx.Button(self.panel, -1, "Open &Timeline")
        self.timeline_btn.Bind(wx.EVT_BUTTON, self.OnOpenTimeline)
        button_sizer.Add(self.timeline_btn, 0, wx.ALL, 5)

        self.unfollow_btn = wx.Button(self.panel, -1, "&Unfollow")
        self.unfollow_btn.Bind(wx.EVT_BUTTON, self.OnUnfollow)
        button_sizer.Add(self.unfollow_btn, 0, wx.ALL, 5)

        self.main_box.Add(button_sizer, 0, wx.ALL, 5)

        # Close button
        self.close_btn = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
        self.close_btn.Bind(wx.EVT_BUTTON, self.OnClose)
        self.main_box.Add(self.close_btn, 0, wx.ALL, 10)

        self.panel.SetSizer(self.main_box)
        self.panel.Layout()
        theme.apply_theme(self)

        self.list.SetFocus()

    def _get_selected_hashtag(self):
        """Get the selected hashtag name (without #)."""
        index = self.list.GetSelection()
        if index == wx.NOT_FOUND or index >= len(self.hashtags):
            return None
        return self.hashtags[index].get('name', '')

    def OnOpenTimeline(self, event):
        """Open a search timeline for the selected hashtag."""
        hashtag = self._get_selected_hashtag()
        if not hashtag:
            return

        misc.search(self.account, f"#{hashtag}")
        self.Destroy()

    def OnUnfollow(self, event):
        """Unfollow the selected hashtag."""
        hashtag = self._get_selected_hashtag()
        if not hashtag:
            return

        index = self.list.GetSelection()

        # Unfollow using misc function
        misc.unfollow_hashtag(self.account, hashtag)

        # Remove from list
        self.hashtags.pop(index)
        self.list.Delete(index)

        # Select next item
        if self.list.GetCount() > 0:
            new_index = min(index, self.list.GetCount() - 1)
            self.list.SetSelection(new_index)
        else:
            speak.speak("No more followed hashtags")
            self.Destroy()

    def OnClose(self, event):
        self.Destroy()
