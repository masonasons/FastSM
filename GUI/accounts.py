import application
import wx
import shutil
import os
from application import get_app
from . import main, misc
import speak
import mastodon_api

class AccountsGui(wx.Dialog):
	def __init__(self):
		wx.Dialog.__init__(self, None, title="Accounts", size=(350,200))
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)
		self.list_label=wx.StaticText(self.panel, -1, label="&Accounts")
		self.list=wx.ListBox(self.panel, -1)
		self.main_box.Add(self.list, 0, wx.ALL, 10)
		self.list.SetFocus()
		self.list.Bind(wx.EVT_LISTBOX, self.on_list_change)
		self.add_items()
		self.load = wx.Button(self.panel, wx.ID_DEFAULT, "&Switch")
		self.load.SetDefault()
		self.load.Bind(wx.EVT_BUTTON, self.Load)
		self.main_box.Add(self.load, 0, wx.ALL, 10)
		self.new = wx.Button(self.panel, wx.ID_DEFAULT, "&Add account")
		self.new.Bind(wx.EVT_BUTTON, self.New)
		self.main_box.Add(self.new, 0, wx.ALL, 10)
		self.remove = wx.Button(self.panel, -1, "&Remove account")
		self.remove.Bind(wx.EVT_BUTTON, self.Remove)
		self.main_box.Add(self.remove, 0, wx.ALL, 10)
		self.close = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
		self.close.Bind(wx.EVT_BUTTON, self.OnClose)
		self.main_box.Add(self.close, 0, wx.ALL, 10)
		self.panel.Layout()

	def add_items(self):
		app = get_app()
		index=0
		for i in app.accounts:
			acct = i.me.acct
			# Add instance for Mastodon accounts
			platform_type = getattr(i.prefs, 'platform_type', 'mastodon')
			if platform_type == 'mastodon' and hasattr(i, 'api') and hasattr(i.api, 'api_base_url'):
				from urllib.parse import urlparse
				parsed = urlparse(i.api.api_base_url)
				instance = parsed.netloc or parsed.path.strip('/')
				if instance:
					acct = f"{acct} on {instance}"
			self.list.Insert(acct, self.list.GetCount())
			if i==app.currentAccount:
				self.list.SetSelection(index)
			index+=1

	def on_list_change(self,event):
		pass

	def New(self, event):
		app = get_app()
		try:
			app.add_session()
			app.prefs.accounts+=1
			app.currentAccount=app.accounts[len(app.accounts)-1]
			main.window.refreshTimelines()
			main.window.on_list_change(None)
			main.window.SetLabel(app.currentAccount.me.acct+" - "+application.name+" "+application.version)
			self.Destroy()
		except mastodon_api.AccountSetupCancelled:
			# User cancelled - just close the dialog without adding account
			speak.speak("Account setup cancelled.")
			return

	def Load(self, event):
		app = get_app()
		app.currentAccount=app.accounts[self.list.GetSelection()]
		main.window.refreshTimelines()
		main.window.list.SetSelection(app.currentAccount.currentIndex)
		main.window.on_list_change(None)
		main.window.SetLabel(app.currentAccount.me.acct+" - "+application.name+" "+application.version)
		self.Destroy()

	def Remove(self, event):
		app = get_app()
		selection = self.list.GetSelection()
		if selection < 0:
			speak.speak("No account selected")
			return

		# Don't allow removing the last account
		if len(app.accounts) <= 1:
			speak.speak("Cannot remove the only account")
			return

		account_to_remove = app.accounts[selection]
		account_name = account_to_remove.me.acct

		# Confirm removal
		dlg = wx.MessageDialog(self,
			f"Are you sure you want to remove the account {account_name}? This will delete all local data for this account.",
			"Confirm Removal",
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
		result = dlg.ShowModal()
		dlg.Destroy()

		if result != wx.ID_YES:
			return

		# Stop streaming if active
		if hasattr(account_to_remove, 'stream') and account_to_remove.stream:
			try:
				account_to_remove.stream.close()
			except:
				pass

		# Get the config path before removing
		confpath = account_to_remove.confpath

		# Remove from accounts list
		app.accounts.remove(account_to_remove)
		app.prefs.accounts -= 1

		# Delete the account's config folder
		if confpath and os.path.exists(confpath):
			try:
				shutil.rmtree(confpath)
			except Exception as e:
				speak.speak(f"Warning: Could not delete account data: {e}")

		# If we removed the current account, switch to first account
		if app.currentAccount == account_to_remove:
			app.currentAccount = app.accounts[0]
			main.window.refreshTimelines()
			main.window.list.SetSelection(0)
			main.window.on_list_change(None)
			main.window.SetLabel(app.currentAccount.me.acct+" - "+application.name+" "+application.version)

		# Refresh the list
		self.list.Clear()
		self.add_items()
		speak.speak(f"Account {account_name} removed")

	def OnClose(self, event):
		self.Destroy()
