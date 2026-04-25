import wx
from . import misc, theme

# Each entry: (label, internal-key). Keys map to misc.* dispatch below.
_SEARCH_TYPES = [
	("Posts", "posts"),
	("Users", "users"),
]


class SearchGui(wx.Dialog):
	def __init__(self, account, type="search"):
		self.account = account
		self.type = type
		wx.Dialog.__init__(self, None, title="Search", size=(350, 200))
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.text_label = wx.StaticText(self.panel, -1, "Search text")
		self.main_box.Add(self.text_label, 0, wx.LEFT | wx.TOP, 10)
		self.text = wx.TextCtrl(self.panel, -1, "", style=wx.TE_PROCESS_ENTER | wx.TE_DONTWRAP)
		self.main_box.Add(self.text, 0, wx.EXPAND | wx.ALL, 10)
		self.text.Bind(wx.EVT_TEXT_ENTER, self.Search)

		self.kind_label = wx.StaticText(self.panel, -1, "Search &for")
		self.main_box.Add(self.kind_label, 0, wx.LEFT | wx.TOP, 10)
		self.kind = wx.Choice(self.panel, -1, choices=[label for label, _ in _SEARCH_TYPES])
		# Default to "Users" when the dialog was opened from the User Search
		# menu entry; otherwise default to "Posts".
		default_key = "users" if type == "user" else "posts"
		for i, (_, key) in enumerate(_SEARCH_TYPES):
			if key == default_key:
				self.kind.SetSelection(i)
				break
		self.main_box.Add(self.kind, 0, wx.ALL, 10)

		self.search = wx.Button(self.panel, wx.ID_DEFAULT, "&Search")
		self.search.SetDefault()
		self.search.Bind(wx.EVT_BUTTON, self.Search)
		self.main_box.Add(self.search, 0, wx.ALL, 10)
		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)
		self.panel.SetSizer(self.main_box)
		self.panel.Layout()
		self.text.SetFocus()
		theme.apply_theme(self)

	def Search(self, event):
		query = self.text.GetValue().strip()
		if not query:
			return
		key = _SEARCH_TYPES[self.kind.GetSelection()][1]
		if key == "users":
			misc.user_search(self.account, query)
		else:
			misc.search(self.account, query)
		self.Destroy()

	def OnClose(self, event):
		self.Destroy()
