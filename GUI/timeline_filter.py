"""Dialog for filtering timeline posts by type."""

import wx
from application import get_app


def should_show_status(status, settings, app=None, _parent_cache=None, account=None):
    """Check if a status should be shown based on filter settings.

    This is a standalone function so it can be used by both the dialog
    and the timeline when new posts come in.

    Args:
        status: The status to check
        settings: Dict with filter settings (original, replies, threads, boosts, quotes, media, no_media, replies_to_me)
        app: Application instance for looking up parent posts (optional)
        _parent_cache: Dict cache for parent lookups (optional, for batch filtering)
        account: Account instance for checking replies to self (optional)

    Returns:
        True if the status should be shown, False otherwise
    """
    if not settings:
        return True

    if app is None:
        app = get_app()

    def get_post_for_check(s):
        """Get the actual post to check (unwrap boosts for content checks)."""
        if hasattr(s, 'reblog') and s.reblog:
            return s.reblog
        return s

    def is_boost(s):
        return hasattr(s, 'reblog') and s.reblog is not None

    def is_quote(s):
        post = get_post_for_check(s)
        return hasattr(post, 'quote') and post.quote is not None

    def has_media(s):
        post = get_post_for_check(s)
        attachments = getattr(post, 'media_attachments', None)
        return attachments is not None and len(attachments) > 0

    def is_reply_to_id(s):
        post = get_post_for_check(s)
        return hasattr(post, 'in_reply_to_id') and post.in_reply_to_id is not None

    def is_thread(s):
        """Check if status is a self-reply (thread continuation)."""
        post = get_post_for_check(s)
        if not hasattr(post, 'in_reply_to_id') or post.in_reply_to_id is None:
            return False

        # Get author of this post
        post_author = getattr(post, 'account', None)
        if not post_author:
            return False
        post_author_id = str(getattr(post_author, 'id', ''))

        # Fast path: use in_reply_to_account_id if available (no API call needed)
        if hasattr(post, 'in_reply_to_account_id') and post.in_reply_to_account_id is not None:
            return str(post.in_reply_to_account_id) == post_author_id

        # Fallback: check if we know this is a self-reply from other fields
        # Don't make API calls for filtering - too slow
        # If we can't determine, assume it's a reply to others (safer default)
        return False

    def is_reply(s):
        """Check if status is a reply to someone else (not self)."""
        if not is_reply_to_id(s):
            return False
        return not is_thread(s)

    def is_reply_to_me(s):
        """Check if status is a reply to the current user."""
        post = get_post_for_check(s)
        if not hasattr(post, 'in_reply_to_id') or post.in_reply_to_id is None:
            return False

        if not account:
            return False

        # Get current user ID
        me_id = str(getattr(account.me, 'id', '')) if hasattr(account, 'me') else ''
        if not me_id:
            return False

        # Use in_reply_to_account_id if available
        if hasattr(post, 'in_reply_to_account_id') and post.in_reply_to_account_id is not None:
            return str(post.in_reply_to_account_id) == me_id

        return False

    def is_original(s):
        """Check if status is an original post (not reply, not boost)."""
        if is_boost(s):
            return False
        return not is_reply_to_id(s)

    # Now apply filters
    _is_boost = is_boost(status)
    _is_quote = is_quote(status)
    _is_thread = is_thread(status)
    _is_reply = is_reply(status)
    _is_reply_to_me = is_reply_to_me(status)
    _is_original = is_original(status)
    _has_media = has_media(status)

    # Check boost filter
    if _is_boost and not settings.get('boosts', True):
        return False

    # Check quote filter
    if _is_quote and not settings.get('quotes', True):
        return False

    # Check thread filter (self-replies)
    if _is_thread and not settings.get('threads', True):
        return False

    # Check reply filter (replies to others)
    if _is_reply and not settings.get('replies', True):
        return False

    # Check replies to me filter
    if _is_reply_to_me and not settings.get('replies_to_me', True):
        return False

    # Check original post filter
    if _is_original and not _is_boost and not settings.get('original', True):
        return False

    # Check media filters
    if _has_media and not settings.get('media', True):
        return False
    if not _has_media and not settings.get('no_media', True):
        return False

    # Check text filter
    filter_text = settings.get('text', '').strip().lower()
    if filter_text:
        post = get_post_for_check(status)
        # Get text content - try 'text' attribute first, then strip HTML from 'content'
        post_text = getattr(post, 'text', '')
        if not post_text:
            content = getattr(post, 'content', '')
            if content and app:
                post_text = app.strip_html(content)
        post_text = post_text.lower() if post_text else ''

        # Also check display name and username
        account = getattr(post, 'account', None)
        display_name = getattr(account, 'display_name', '') if account else ''
        acct = getattr(account, 'acct', '') if account else ''

        searchable = f"{post_text} {display_name} {acct}".lower()
        if filter_text not in searchable:
            return False

    return True


class TimelineFilterDialog(wx.Dialog):
    """Dialog for filtering the current timeline by post type."""

    def __init__(self, parent, timeline):
        wx.Dialog.__init__(self, parent, title="Filter Timeline", size=(400, 380))
        self.timeline = timeline
        self.app = get_app()

        # Sync unfiltered statuses with current statuses
        # This handles new posts that came in since filter was last applied
        self._sync_unfiltered_statuses()

        panel = wx.Panel(self)
        main_box = wx.BoxSizer(wx.VERTICAL)

        # Instructions
        label = wx.StaticText(panel, -1, "Check the types of posts you want to show:")
        main_box.Add(label, 0, wx.ALL, 10)

        # Checkboxes for filter options
        self.show_original = wx.CheckBox(panel, -1, "Original posts (not replies or boosts)")
        self.show_original.SetValue(True)
        main_box.Add(self.show_original, 0, wx.ALL, 5)

        self.show_replies = wx.CheckBox(panel, -1, "Replies to others")
        self.show_replies.SetValue(True)
        main_box.Add(self.show_replies, 0, wx.ALL, 5)

        self.show_replies_to_me = wx.CheckBox(panel, -1, "Replies to me")
        self.show_replies_to_me.SetValue(True)
        main_box.Add(self.show_replies_to_me, 0, wx.ALL, 5)

        self.show_threads = wx.CheckBox(panel, -1, "Threads (self-replies)")
        self.show_threads.SetValue(True)
        main_box.Add(self.show_threads, 0, wx.ALL, 5)

        self.show_boosts = wx.CheckBox(panel, -1, "Boosts/Reposts")
        self.show_boosts.SetValue(True)
        main_box.Add(self.show_boosts, 0, wx.ALL, 5)

        self.show_quotes = wx.CheckBox(panel, -1, "Quote posts")
        self.show_quotes.SetValue(True)
        main_box.Add(self.show_quotes, 0, wx.ALL, 5)

        self.show_media = wx.CheckBox(panel, -1, "Posts with media")
        self.show_media.SetValue(True)
        main_box.Add(self.show_media, 0, wx.ALL, 5)

        self.show_no_media = wx.CheckBox(panel, -1, "Posts without media")
        self.show_no_media.SetValue(True)
        main_box.Add(self.show_no_media, 0, wx.ALL, 5)

        # Text filter
        text_box = wx.BoxSizer(wx.HORIZONTAL)
        text_label = wx.StaticText(panel, -1, "Contains &text:")
        text_box.Add(text_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.filter_text = wx.TextCtrl(panel, -1, "", size=(200, -1))
        text_box.Add(self.filter_text, 1, wx.ALL | wx.EXPAND, 5)
        main_box.Add(text_box, 0, wx.ALL | wx.EXPAND, 5)

        # Load existing filter settings if present
        if hasattr(timeline, '_filter_settings'):
            settings = timeline._filter_settings
            self.show_original.SetValue(settings.get('original', True))
            self.show_replies.SetValue(settings.get('replies', True))
            self.show_replies_to_me.SetValue(settings.get('replies_to_me', True))
            self.show_threads.SetValue(settings.get('threads', True))
            self.show_boosts.SetValue(settings.get('boosts', True))
            self.show_quotes.SetValue(settings.get('quotes', True))
            self.show_media.SetValue(settings.get('media', True))
            self.show_no_media.SetValue(settings.get('no_media', True))
            self.filter_text.SetValue(settings.get('text', ''))

        # Buttons
        button_box = wx.BoxSizer(wx.HORIZONTAL)

        self.ok_btn = wx.Button(panel, wx.ID_OK, "&Apply")
        self.ok_btn.Bind(wx.EVT_BUTTON, self.on_apply)
        button_box.Add(self.ok_btn, 0, wx.ALL, 5)

        self.clear_btn = wx.Button(panel, -1, "&Clear Filter")
        self.clear_btn.Bind(wx.EVT_BUTTON, self.on_clear)
        button_box.Add(self.clear_btn, 0, wx.ALL, 5)

        self.cancel_btn = wx.Button(panel, wx.ID_CANCEL, "&Cancel")
        button_box.Add(self.cancel_btn, 0, wx.ALL, 5)

        main_box.Add(button_box, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        panel.SetSizer(main_box)
        panel.Layout()

        # Set focus to first checkbox
        self.show_original.SetFocus()

    def _sync_unfiltered_statuses(self):
        """Sync _unfiltered_statuses with any new posts that came in."""
        if not hasattr(self.timeline, '_unfiltered_statuses'):
            # First time - store current statuses as unfiltered
            self.timeline._unfiltered_statuses = list(self.timeline.statuses)
        else:
            # Merge: add any statuses in current list that aren't in unfiltered
            unfiltered_ids = {getattr(s, 'id', None) for s in self.timeline._unfiltered_statuses}
            for status in self.timeline.statuses:
                status_id = getattr(status, 'id', None)
                if status_id and status_id not in unfiltered_ids:
                    self.timeline._unfiltered_statuses.append(status)
                    unfiltered_ids.add(status_id)

    def _get_current_status_id(self):
        """Get the ID of the currently focused status."""
        try:
            # Use timeline index directly (more reliable than GUI selection)
            index = self.timeline.index
            if index >= 0 and index < len(self.timeline.statuses):
                status = self.timeline.statuses[index]
                status_id = getattr(status, 'id', None)
                return str(status_id) if status_id is not None else None
        except:
            pass
        return None

    def _restore_selection(self, status_id):
        """Restore selection to the status with the given ID, or top if not found."""
        from . import main as main_window
        if status_id is None:
            self.timeline.index = 0
            main_window.window.list2.SetSelection(0)
            return

        # Find the status by ID (compare as strings to handle type mismatches)
        for i, status in enumerate(self.timeline.statuses):
            sid = getattr(status, 'id', None)
            if sid is not None and str(sid) == status_id:
                self.timeline.index = i
                main_window.window.list2.SetSelection(i)
                return

        # Not found, go to top
        if len(self.timeline.statuses) > 0:
            self.timeline.index = 0
            main_window.window.list2.SetSelection(0)

    def on_apply(self, event):
        """Apply the filter to the timeline."""
        from . import main as main_window

        try:
            # Remember current position
            current_id = self._get_current_status_id()

            # Save filter settings to timeline
            self.timeline._filter_settings = {
                'original': self.show_original.GetValue(),
                'replies': self.show_replies.GetValue(),
                'replies_to_me': self.show_replies_to_me.GetValue(),
                'threads': self.show_threads.GetValue(),
                'boosts': self.show_boosts.GetValue(),
                'quotes': self.show_quotes.GetValue(),
                'media': self.show_media.GetValue(),
                'no_media': self.show_no_media.GetValue(),
                'text': self.filter_text.GetValue().strip(),
            }

            # Save to account prefs for persistence
            _save_filter_settings(self.timeline.account, self.timeline)

            # Filter statuses from the unfiltered list
            filtered = []
            for status in self.timeline._unfiltered_statuses:
                if should_show_status(status, self.timeline._filter_settings, self.app, account=self.timeline.account):
                    filtered.append(status)

            self.timeline.statuses = filtered
            self.timeline._is_filtered = True

            # Refresh the list and restore position
            main_window.window.refreshList()
            self._restore_selection(current_id)
        finally:
            # Always ensure index is valid and dialog closes
            self._ensure_valid_index()
            self.EndModal(wx.ID_OK)

    def _ensure_valid_index(self):
        """Ensure timeline index is within valid bounds."""
        from . import main as main_window
        if len(self.timeline.statuses) == 0:
            self.timeline.index = 0
        elif self.timeline.index >= len(self.timeline.statuses):
            self.timeline.index = 0
            try:
                main_window.window.list2.SetSelection(0)
            except:
                pass

    def on_clear(self, event):
        """Clear the filter and restore all posts."""
        from . import main as main_window

        try:
            # Remember current position
            current_id = self._get_current_status_id()

            if hasattr(self.timeline, '_unfiltered_statuses'):
                self.timeline.statuses = list(self.timeline._unfiltered_statuses)
                del self.timeline._unfiltered_statuses

            self.timeline._is_filtered = False
            if hasattr(self.timeline, '_filter_settings'):
                del self.timeline._filter_settings

            # Remove from saved prefs
            _clear_filter_settings(self.timeline.account, self.timeline)

            # Refresh the list and restore position
            main_window.window.refreshList()
            self._restore_selection(current_id)
        finally:
            # Always ensure index is valid and dialog closes
            self._ensure_valid_index()
            self.EndModal(wx.ID_CANCEL)


def show_filter_dialog(account):
    """Show the timeline filter dialog for the current timeline."""
    from . import main as main_window
    import platform
    timeline = account.currentTimeline
    if not timeline:
        return

    # On Mac, use None as parent to avoid menu state issues
    parent = None if platform.system() == "Darwin" else main_window.window
    dlg = TimelineFilterDialog(parent, timeline)
    dlg.ShowModal()
    dlg.Destroy()


def _get_timeline_filter_key(timeline):
    """Get a unique key for storing filter settings for this timeline."""
    # Use type and data to create a unique key
    if timeline.data:
        return f"{timeline.type}:{timeline.data}"
    return timeline.type


def _save_filter_settings(account, timeline):
    """Save filter settings to account prefs."""
    if not hasattr(account.prefs, 'saved_filters'):
        account.prefs.saved_filters = {}

    key = _get_timeline_filter_key(timeline)
    account.prefs.saved_filters[key] = timeline._filter_settings


def _clear_filter_settings(account, timeline):
    """Remove saved filter settings for a timeline."""
    if not hasattr(account.prefs, 'saved_filters'):
        return

    key = _get_timeline_filter_key(timeline)
    if key in account.prefs.saved_filters:
        del account.prefs.saved_filters[key]


def get_saved_filter(account, timeline):
    """Get saved filter settings for a timeline, if any."""
    if not hasattr(account.prefs, 'saved_filters'):
        return None

    key = _get_timeline_filter_key(timeline)
    return account.prefs.saved_filters.get(key)


def apply_saved_filter(timeline):
    """Apply saved filter settings to a timeline if they exist."""
    account = timeline.account
    saved = get_saved_filter(account, timeline)
    if not saved:
        return False

    # Store unfiltered statuses
    if not hasattr(timeline, '_unfiltered_statuses'):
        timeline._unfiltered_statuses = list(timeline.statuses)

    # Apply filter settings
    timeline._filter_settings = saved

    # Filter statuses
    filtered = []
    for status in timeline._unfiltered_statuses:
        if should_show_status(status, timeline._filter_settings, timeline.app, account=timeline.account):
            filtered.append(status)

    timeline.statuses = filtered
    timeline._is_filtered = True
    return True
