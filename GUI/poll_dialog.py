"""Dialog for viewing and voting in polls."""

import platform as sys_platform
import wx
import speak
import sound

class PollDialog(wx.Dialog):
    """Dialog for viewing poll options and voting."""

    def __init__(self, parent, account, status, poll=None):
        self.account = account
        self.status = status
        self.poll = poll if poll else status.poll

        # Get poll info
        is_expired = getattr(self.poll, 'expired', False)
        has_voted = getattr(self.poll, 'voted', False)
        is_multiple = getattr(self.poll, 'multiple', False)

        if is_expired:
            title = "Poll Results (Expired)"
        elif has_voted:
            title = "Poll Results (You voted)"
        else:
            title = "Vote in Poll"

        wx.Dialog.__init__(self, parent, title=title, size=(500, 450))

        self.panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        can_vote = not is_expired and not has_voted

        if can_vote:
            # Voting mode - use radio buttons/checkboxes
            self._build_voting_ui(main_sizer, is_multiple)
        else:
            # Results mode - use read-only text field
            self._build_results_ui(main_sizer)

        self.panel.SetSizer(main_sizer)
        self.panel.Layout()

    def _build_voting_ui(self, main_sizer, is_multiple):
        """Build UI for voting in a poll."""
        # Poll question (from status content)
        content = getattr(self.status, 'content', '')
        if hasattr(self.account, 'app'):
            content = self.account.app.strip_html(content)
        if content:
            question_label = wx.StaticText(self.panel, label=content[:200])
            question_label.Wrap(450)
            main_sizer.Add(question_label, 0, wx.ALL, 10)

        if is_multiple:
            multi_label = wx.StaticText(self.panel, label="Multiple choices allowed")
            main_sizer.Add(multi_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Options
        options = getattr(self.poll, 'options', [])

        self.option_controls = []

        options_label = wx.StaticText(self.panel, label="&Options:")
        main_sizer.Add(options_label, 0, wx.LEFT | wx.TOP, 10)

        for i, option in enumerate(options):
            option_title = getattr(option, 'title', str(option))

            if is_multiple:
                ctrl = wx.CheckBox(self.panel, label=option_title)
            else:
                if i == 0:
                    ctrl = wx.RadioButton(self.panel, label=option_title, style=wx.RB_GROUP)
                else:
                    ctrl = wx.RadioButton(self.panel, label=option_title)
            self.option_controls.append((i, ctrl))
            main_sizer.Add(ctrl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        main_sizer.AddSpacer(10)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        vote_btn = wx.Button(self.panel, wx.ID_OK, "&Vote")
        vote_btn.Bind(wx.EVT_BUTTON, self.on_vote)
        vote_btn.SetDefault()
        btn_sizer.Add(vote_btn, 0, wx.ALL, 5)

        close_btn = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
        btn_sizer.Add(close_btn, 0, wx.ALL, 5)

        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        # Set focus to first option
        if self.option_controls:
            self.option_controls[0][1].SetFocus()

    def _build_results_ui(self, main_sizer):
        """Build UI for viewing poll results using read-only text field."""
        # Build text content for the results
        lines = []

        # Poll question
        content = getattr(self.status, 'content', '')
        if hasattr(self.account, 'app'):
            content = self.account.app.strip_html(content)
        if content:
            lines.append(f"Question: {content[:500]}")
            lines.append("")

        # Poll info
        is_expired = getattr(self.poll, 'expired', False)
        votes_count = getattr(self.poll, 'votes_count', 0)
        voters_count = getattr(self.poll, 'voters_count', None)

        info_text = f"Total votes: {votes_count}"
        if voters_count is not None:
            info_text += f" from {voters_count} voters"
        if is_expired:
            info_text += " (Poll ended)"
        lines.append(info_text)
        lines.append("")

        # Options with results
        options = getattr(self.poll, 'options', [])
        own_votes = getattr(self.poll, 'own_votes', []) or []

        lines.append("Results:")
        for i, option in enumerate(options):
            option_title = getattr(option, 'title', str(option))
            option_votes = getattr(option, 'votes_count', 0)

            # Calculate percentage
            if votes_count > 0:
                percentage = (option_votes / votes_count) * 100
                line = f"  {option_title}: {percentage:.1f}% ({option_votes} votes)"
            else:
                line = f"  {option_title}: 0% (0 votes)"

            # Mark if user voted for this option
            if i in own_votes:
                line += " (Your vote)"

            lines.append(line)

        # Create read-only text field
        results_label = wx.StaticText(self.panel, label="Poll &Results:")
        main_sizer.Add(results_label, 0, wx.LEFT | wx.TOP, 10)

        self.results_text = wx.TextCtrl(
            self.panel,
            value="\n".join(lines),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
            name="Poll Results"
        )
        main_sizer.Add(self.results_text, 1, wx.EXPAND | wx.ALL, 10)

        # Close button
        close_btn = wx.Button(self.panel, wx.ID_CANCEL, "&Close")
        close_btn.SetDefault()
        main_sizer.Add(close_btn, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        # Set focus to text field
        self.results_text.SetFocus()

    def on_vote(self, event):
        """Submit the vote."""
        is_multiple = getattr(self.poll, 'multiple', False)

        # Get selected options
        choices = []
        for idx, ctrl in self.option_controls:
            if ctrl.GetValue():
                choices.append(idx)

        if not choices:
            speak.speak("Please select an option")
            return

        if not is_multiple and len(choices) > 1:
            speak.speak("Please select only one option")
            return

        try:
            poll_id = self.poll.id
            self.account.api.poll_vote(poll_id, choices)
            sound.play(self.account, "like")
            speak.speak("Vote submitted")
            self.EndModal(wx.ID_OK)
        except Exception as e:
            self.account.app.handle_error(e, "Vote")


def show_poll_dialog(account, status):
    """Show the poll dialog for a status, refreshing poll data from server first."""
    import platform
    from . import main as main_window

    poll = None

    # Check if this is a remote instance status
    is_remote = hasattr(status, '_instance_url') and status._instance_url

    if is_remote:
        # For remote statuses, try to resolve and get fresh poll data
        try:
            # Try to resolve the status to get it on our instance
            resolved_id = account._platform.resolve_remote_status(status)
            if resolved_id and resolved_id != status.id:
                # Fetch the resolved status to get fresh poll data
                fresh_status = account.api.status(id=resolved_id)
                if fresh_status and hasattr(fresh_status, 'poll') and fresh_status.poll:
                    poll = fresh_status.poll
        except Exception as e:
            print(f"Could not resolve remote poll: {e}")

        # If we couldn't resolve, use the poll from the status as-is
        if not poll:
            poll = status.poll
    else:
        # For local statuses, fetch fresh poll data from server
        try:
            poll_id = status.poll.id
            poll = account.api.poll(id=poll_id)
        except Exception as e:
            print(f"Could not refresh poll: {e}")
            poll = status.poll

    parent = None if platform.system() == "Darwin" else main_window.window
    dlg = PollDialog(parent, account, status, poll)
    dlg.ShowModal()
    dlg.Destroy()
