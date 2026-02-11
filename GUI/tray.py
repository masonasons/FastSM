import wx.adv
import wx
import os
from . import main
TRAY_TOOLTIP = 'FastSM'
TRAY_ICON = 'icon.png'

def create_menu_item(menu, label, func):
	item = wx.MenuItem(menu, -1, label)
	menu.Bind(wx.EVT_MENU, func, id=item.GetId())
	menu.Append(item)
	return item

class TaskBarIcon(wx.adv.TaskBarIcon):
	def __init__(self, frame):
		self.frame = frame
		super(TaskBarIcon, self).__init__()
		self.set_icon(None)
		self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)

	def CreatePopupMenu(self):
		menu = wx.Menu()
		create_menu_item(menu, 'New post', self.frame.OnTweet)
		if self.frame.IsShown():
			create_menu_item(menu, 'Hide window', self.OnShowHide)
		else:
			create_menu_item(menu, 'Show window', self.OnShowHide)
		create_menu_item(menu, 'Exit', self.on_exit)
		return menu

	def on_left_down(self, event):
		self.OnShowHide(event)

	def OnShowHide(self, event):
		self.frame.ToggleWindow()

	def on_exit(self, event, blah=True):
		self.Destroy()
		if blah:
			self.frame.OnClose(event)

	def set_icon(self, path):
		icon = wx.Icon()

		# Try explicit icon path first.
		if path and os.path.exists(path):
			try:
				icon = wx.Icon(path)
			except Exception:
				icon = wx.Icon()

		# Fallback to a stock art icon so Linux always gets a valid bitmap.
		if not icon.IsOk():
			try:
				bmp = wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_OTHER, (16, 16))
				if bmp.IsOk():
					icon = wx.Icon(bmp)
			except Exception:
				pass

		if icon.IsOk():
			self.SetIcon(icon, TRAY_TOOLTIP)
