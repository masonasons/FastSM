"""Account creation dialogs for Mastodon and Bluesky."""

import wx
import webbrowser
import requests
import speak
from . import theme
from application import get_app


class PlatformSignupDialog(wx.Dialog):
	"""Dialog to select which platform to create an account on."""

	def __init__(self, parent):
		wx.Dialog.__init__(self, parent, title="Create Account", size=(400, 200))
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		info_label = wx.StaticText(self.panel, -1, "Select a platform to create an account on:")
		self.main_box.Add(info_label, 0, wx.ALL, 10)

		self.mastodon_btn = wx.Button(self.panel, -1, "&Mastodon")
		self.mastodon_btn.Bind(wx.EVT_BUTTON, self.on_mastodon)
		self.main_box.Add(self.mastodon_btn, 0, wx.ALL, 10)
		self.mastodon_btn.SetFocus()

		self.bluesky_btn = wx.Button(self.panel, -1, "&Bluesky")
		self.bluesky_btn.Bind(wx.EVT_BUTTON, self.on_bluesky)
		self.main_box.Add(self.bluesky_btn, 0, wx.ALL, 10)

		self.cancel_btn = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
		self.main_box.Add(self.cancel_btn, 0, wx.ALL, 10)

		self.panel.SetSizer(self.main_box)
		self.panel.Layout()
		theme.apply_theme(self)

		self.result = None

	def on_mastodon(self, event):
		self.result = 'mastodon'
		self.EndModal(wx.ID_OK)

	def on_bluesky(self, event):
		self.result = 'bluesky'
		self.EndModal(wx.ID_OK)


class MastodonInstanceDialog(wx.Dialog):
	"""Dialog to enter a Mastodon instance and check registration status."""

	def __init__(self, parent):
		wx.Dialog.__init__(self, parent, title="Select Mastodon Instance", size=(500, 400))
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		info_label = wx.StaticText(self.panel, -1, "Enter a Mastodon instance URL or paste an invite link:")
		self.main_box.Add(info_label, 0, wx.ALL, 10)

		self.instance_label = wx.StaticText(self.panel, -1, "&Instance or Invite Link:")
		self.main_box.Add(self.instance_label, 0, wx.LEFT | wx.TOP, 10)
		self.instance = wx.TextCtrl(self.panel, -1, "", name="Instance or Invite Link")
		self.instance.SetHint("mastodon.social or https://instance.social/invite/CODE")
		self.main_box.Add(self.instance, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		self.instance.SetFocus()

		self.check_btn = wx.Button(self.panel, -1, "&Check Registration Status")
		self.check_btn.Bind(wx.EVT_BUTTON, self.on_check)
		self.main_box.Add(self.check_btn, 0, wx.ALL, 10)

		self.status_label = wx.StaticText(self.panel, -1, "Status:")
		self.main_box.Add(self.status_label, 0, wx.LEFT | wx.TOP, 10)
		self.status_text = wx.TextCtrl(self.panel, -1, "", style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 100), name="Registration Status")
		self.main_box.Add(self.status_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.continue_btn = wx.Button(self.panel, wx.ID_OK, "C&ontinue")
		self.continue_btn.Bind(wx.EVT_BUTTON, self.on_continue)
		self.continue_btn.Enable(False)
		btn_sizer.Add(self.continue_btn, 0, wx.ALL, 5)

		self.cancel_btn = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
		btn_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)
		self.main_box.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

		self.panel.SetSizer(self.main_box)
		self.panel.Layout()
		theme.apply_theme(self)

		self.instance_url = None
		self.registrations_open = False
		self.approval_required = False
		self.reason_required = False
		self.instance_info = None
		self.invite_code = None

	def on_check(self, event):
		"""Check the registration status of the instance."""
		instance = self.instance.GetValue().strip()
		if not instance:
			speak.speak("Please enter an instance URL or invite link")
			return

		# Check if this is an invite link and extract the code
		self.invite_code = None
		if '/invite/' in instance:
			# Parse invite link: https://instance.social/invite/CODE
			import re
			match = re.search(r'https?://([^/]+)/invite/([^/\s?]+)', instance)
			if match:
				instance = 'https://' + match.group(1)
				self.invite_code = match.group(2)
			else:
				speak.speak("Could not parse invite link")
				return
		else:
			# Normalize the URL
			if not instance.startswith('http'):
				instance = 'https://' + instance
		instance = instance.rstrip('/')

		self.status_text.SetValue("Checking...")
		speak.speak("Checking registration status")
		wx.GetApp().Yield()

		try:
			# Try v2 instance API first
			response = requests.get(f"{instance}/api/v2/instance", timeout=10)
			if response.status_code == 200:
				data = response.json()
				self.instance_info = data
				self.instance_url = instance

				registrations = data.get('registrations', {})
				self.registrations_open = registrations.get('enabled', False)
				self.approval_required = registrations.get('approval_required', False)
				self.reason_required = registrations.get('reason_required', False)

				# Get instance info
				title = data.get('title', instance)
				description = data.get('description', '')
				if description:
					description = get_app().strip_html(description)[:200]

				status_lines = [f"Instance: {title}"]
				if description:
					status_lines.append(f"Description: {description}")

				if self.invite_code:
					status_lines.append(f"Invite code: {self.invite_code}")
					status_lines.append("You can register using this invite code.")
					self.continue_btn.Enable(True)
				elif self.registrations_open:
					if self.approval_required:
						status_lines.append("Registrations: Open (requires approval)")
						if self.reason_required:
							status_lines.append("You must provide a reason for joining.")
					else:
						status_lines.append("Registrations: Open")
					self.continue_btn.Enable(True)
				else:
					status_lines.append("Registrations: Closed")
					status_lines.append("This instance is not accepting new registrations.")
					status_lines.append("You may need an invite link to register.")
					self.continue_btn.Enable(False)

				self.status_text.SetValue("\n".join(status_lines))
				if self.invite_code:
					speak.speak("Invite code found")
				elif self.registrations_open:
					speak.speak("Open, requires approval" if self.approval_required else "Registrations open")
				else:
					speak.speak("Registrations closed")
			else:
				# Try v1 instance API as fallback
				response = requests.get(f"{instance}/api/v1/instance", timeout=10)
				if response.status_code == 200:
					data = response.json()
					self.instance_info = data
					self.instance_url = instance
					# v1 API doesn't have detailed registration info
					self.status_text.SetValue(f"Instance: {data.get('title', instance)}\n\nNote: This instance uses an older API. Registration status unknown.\nYou can try to continue, but registration may fail.")
					self.registrations_open = True  # Assume open, let user try
					self.continue_btn.Enable(True)
					speak.speak("Registration status unknown")
				else:
					self.status_text.SetValue("Could not connect to this instance. Please check the URL.")
					self.continue_btn.Enable(False)
					speak.speak("Could not connect")
		except requests.exceptions.Timeout:
			self.status_text.SetValue("Connection timed out. Please check the URL and try again.")
			self.continue_btn.Enable(False)
			speak.speak("Connection timed out")
		except requests.exceptions.RequestException as e:
			self.status_text.SetValue(f"Error connecting to instance: {str(e)}")
			self.continue_btn.Enable(False)
			speak.speak("Connection error")
		except Exception as e:
			self.status_text.SetValue(f"Error: {str(e)}")
			self.continue_btn.Enable(False)
			speak.speak("Error")

	def on_continue(self, event):
		if self.instance_url and (self.registrations_open or self.invite_code):
			self.EndModal(wx.ID_OK)


class MastodonSignupDialog(wx.Dialog):
	"""Dialog to create a Mastodon account."""

	def __init__(self, parent, instance_url, approval_required=False, reason_required=False, instance_info=None, invite_code=None):
		wx.Dialog.__init__(self, parent, title="Create Mastodon Account", size=(500, 500))
		self.instance_url = instance_url
		self.approval_required = approval_required
		self.reason_required = reason_required
		self.instance_info = instance_info
		self.invite_code = invite_code

		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		info_text = f"Create an account on {instance_url}"
		if invite_code:
			info_text += f"\n(Using invite code: {invite_code})"
		elif approval_required:
			info_text += "\n(This instance requires approval for new accounts)"
		info_label = wx.StaticText(self.panel, -1, info_text)
		self.main_box.Add(info_label, 0, wx.ALL, 10)

		# Username
		username_label = wx.StaticText(self.panel, -1, "&Username:")
		self.main_box.Add(username_label, 0, wx.LEFT | wx.TOP, 10)
		self.username = wx.TextCtrl(self.panel, -1, "", name="Username")
		self.main_box.Add(self.username, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		self.username.SetFocus()

		# Email
		email_label = wx.StaticText(self.panel, -1, "&Email:")
		self.main_box.Add(email_label, 0, wx.LEFT | wx.TOP, 10)
		self.email = wx.TextCtrl(self.panel, -1, "", name="Email")
		self.main_box.Add(self.email, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

		# Password
		password_label = wx.StaticText(self.panel, -1, "&Password:")
		self.main_box.Add(password_label, 0, wx.LEFT | wx.TOP, 10)
		self.password = wx.TextCtrl(self.panel, -1, "", style=wx.TE_PASSWORD, name="Password")
		self.main_box.Add(self.password, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

		# Confirm Password
		confirm_label = wx.StaticText(self.panel, -1, "Con&firm Password:")
		self.main_box.Add(confirm_label, 0, wx.LEFT | wx.TOP, 10)
		self.confirm_password = wx.TextCtrl(self.panel, -1, "", style=wx.TE_PASSWORD, name="Confirm Password")
		self.main_box.Add(self.confirm_password, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

		# Reason (if required or approval required)
		if approval_required or reason_required:
			reason_label = wx.StaticText(self.panel, -1, "&Reason for joining:" + (" (required)" if reason_required else " (optional)"))
			self.main_box.Add(reason_label, 0, wx.LEFT | wx.TOP, 10)
			reason_style = wx.TE_MULTILINE if getattr(get_app().prefs, 'word_wrap', True) else wx.TE_MULTILINE | wx.TE_DONTWRAP
			self.reason = wx.TextCtrl(self.panel, -1, "", style=reason_style, size=(-1, 60), name="Reason for joining")
			self.main_box.Add(self.reason, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		else:
			self.reason = None

		# Server rules
		rules_label = wx.StaticText(self.panel, -1, "Server &Rules:")
		self.main_box.Add(rules_label, 0, wx.LEFT | wx.TOP, 10)
		self.rules_text = wx.TextCtrl(self.panel, -1, "", style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP, size=(-1, 100), name="Server Rules")
		self.main_box.Add(self.rules_text, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

		# Fetch and display rules
		self._load_rules()

		# Agreement checkbox
		self.agreement = wx.CheckBox(self.panel, -1, "I &agree to the instance rules and terms of service")
		self.main_box.Add(self.agreement, 0, wx.ALL, 10)

		# Buttons
		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.create_btn = wx.Button(self.panel, wx.ID_OK, "&Create Account")
		self.create_btn.Bind(wx.EVT_BUTTON, self.on_create)
		btn_sizer.Add(self.create_btn, 0, wx.ALL, 5)

		self.cancel_btn = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
		btn_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)
		self.main_box.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

		self.panel.SetSizer(self.main_box)
		self.panel.Layout()
		theme.apply_theme(self)

		self.created_successfully = False

	def _load_rules(self):
		"""Fetch and display the instance rules."""
		rules_text = "Loading rules..."
		self.rules_text.SetValue(rules_text)

		try:
			# Try to get rules from instance info first
			rules = []
			if self.instance_info:
				rules = self.instance_info.get('rules', [])

			# If no rules in instance info, fetch from API
			if not rules:
				response = requests.get(f"{self.instance_url}/api/v1/instance/rules", timeout=10)
				if response.status_code == 200:
					rules = response.json()

			if rules:
				# Format rules as numbered list
				rules_lines = []
				for i, rule in enumerate(rules, 1):
					if isinstance(rule, dict):
						text = rule.get('text', str(rule))
					else:
						text = str(rule)
					rules_lines.append(f"{i}. {text}")
				rules_text = "\n".join(rules_lines)
			else:
				rules_text = "No specific rules found. Please visit the instance website for terms of service."

		except Exception as e:
			rules_text = f"Could not load rules: {str(e)}\n\nPlease visit {self.instance_url}/about for the full terms."

		self.rules_text.SetValue(rules_text)

	def on_create(self, event):
		"""Attempt to create the account."""
		username = self.username.GetValue().strip()
		email = self.email.GetValue().strip()
		password = self.password.GetValue()
		confirm = self.confirm_password.GetValue()
		reason = self.reason.GetValue().strip() if self.reason else None

		# Validation
		if not username:
			speak.speak("Please enter a username")
			self.username.SetFocus()
			return
		if not email:
			speak.speak("Please enter an email address")
			self.email.SetFocus()
			return
		if not password:
			speak.speak("Please enter a password")
			self.password.SetFocus()
			return
		if password != confirm:
			speak.speak("Passwords do not match")
			self.confirm_password.SetFocus()
			return
		if not self.agreement.GetValue():
			speak.speak("You must agree to the instance rules and terms of service")
			self.agreement.SetFocus()
			return
		if self.reason_required and not reason:
			speak.speak("Please provide a reason for joining")
			self.reason.SetFocus()
			return

		speak.speak("Creating account, please wait")
		wx.GetApp().Yield()

		try:
			from mastodon import Mastodon

			# First, create an app on the instance
			client_id, client_secret = Mastodon.create_app(
				"FastSM",
				api_base_url=self.instance_url,
				scopes=['read', 'write', 'follow', 'push']
			)

			# Create a Mastodon instance for registration
			api = Mastodon(
				client_id=client_id,
				client_secret=client_secret,
				api_base_url=self.instance_url
			)

			# If we have an invite code, we need to use direct API call
			# since Mastodon.py doesn't support invite_code parameter
			if self.invite_code:
				# Get app token for registration
				token_response = requests.post(
					f"{self.instance_url}/oauth/token",
					data={
						'client_id': client_id,
						'client_secret': client_secret,
						'grant_type': 'client_credentials',
						'scope': 'read write follow push'
					},
					timeout=30
				)

				if token_response.status_code != 200:
					# Try to get error details
					try:
						error_detail = token_response.json().get('error_description', token_response.json().get('error', ''))
					except:
						error_detail = f"Status {token_response.status_code}"
					raise Exception(f"Could not obtain app token: {error_detail}")

				app_token = token_response.json().get('access_token')
				if not app_token:
					raise Exception("No access token in response")

				# Create account with invite code
				data = {
					'username': username,
					'email': email,
					'password': password,
					'agreement': 'true',
					'locale': 'en',
					'invite_code': self.invite_code
				}
				if reason:
					data['reason'] = reason

				response = requests.post(
					f"{self.instance_url}/api/v1/accounts",
					data=data,
					headers={'Authorization': f'Bearer {app_token}'},
					timeout=30
				)

				if response.status_code not in (200, 201):
					try:
						error_data = response.json()
						error_msg = error_data.get('error', str(response.status_code))
						# Check for detailed field errors
						if 'details' in error_data:
							details = error_data['details']
							field_errors = []
							for field, errors in details.items():
								for err in errors:
									desc = err.get('description', err.get('error', str(err)))
									field_errors.append(f"{field}: {desc}")
							if field_errors:
								error_msg = "\n".join(field_errors)
					except:
						error_msg = f"Server returned status {response.status_code}"
					raise Exception(error_msg)

				result = response.json()
			else:
				# Use Mastodon.py for normal registration
				result = api.create_account(
					username=username,
					password=password,
					email=email,
					agreement=True,
					locale='en',
					reason=reason,
					return_detailed_error=True
				)

			# Success - the result is an access token (but email confirmation may be required)
			self.created_successfully = True

			if self.invite_code:
				msg = f"Account created successfully using invite code!\n\nA confirmation email has been sent to {email}.\n\nPlease click the link in the email to confirm your account, then use 'Add account' to sign in."
			elif self.approval_required:
				msg = f"Account creation request submitted!\n\nYour account on {self.instance_url} is pending approval.\n\nYou will receive an email when your account is approved. Once approved, you can add the account using 'Add account'."
			else:
				msg = f"Account created successfully!\n\nA confirmation email has been sent to {email}.\n\nPlease click the link in the email to confirm your account, then use 'Add account' to sign in."

			dlg = wx.MessageDialog(self, msg, "Account Created", wx.OK | wx.ICON_INFORMATION)
			dlg.ShowModal()
			dlg.Destroy()
			speak.speak("Account created")
			self.EndModal(wx.ID_OK)

		except Exception as e:
			error_msg = str(e)
			# Try to parse Mastodon error details
			if hasattr(e, 'args') and e.args:
				error_msg = str(e.args[0])

			# Common error translations
			if 'ERR_TAKEN' in error_msg or 'taken' in error_msg.lower():
				error_msg = "This username or email is already taken."
			elif 'ERR_RESERVED' in error_msg or 'reserved' in error_msg.lower():
				error_msg = "This username is reserved and cannot be used."
			elif 'ERR_BLOCKED' in error_msg or 'blocked' in error_msg.lower():
				error_msg = "This email provider is not allowed."
			elif 'ERR_INVALID' in error_msg or 'invalid' in error_msg.lower():
				if 'email' in error_msg.lower():
					error_msg = "Invalid email address format."
				else:
					error_msg = "Invalid input. Please check your entries."
			elif 'ERR_TOO_SHORT' in error_msg:
				error_msg = "Password is too short."
			elif 'ERR_TOO_LONG' in error_msg:
				error_msg = "One of the fields is too long."

			speak.speak("Error creating account")
			dlg = wx.MessageDialog(self, f"Error creating account:\n\n{error_msg}", "Error", wx.OK | wx.ICON_ERROR)
			dlg.ShowModal()
			dlg.Destroy()


class BlueskySignupDialog(wx.Dialog):
	"""Dialog for Bluesky account creation."""

	def __init__(self, parent):
		wx.Dialog.__init__(self, parent, title="Create Bluesky Account", size=(500, 450))
		self.panel = wx.Panel(self)
		self.main_box = wx.BoxSizer(wx.VERTICAL)

		info_label = wx.StaticText(self.panel, -1, "Create a new Bluesky account:")
		self.main_box.Add(info_label, 0, wx.ALL, 10)

		# Handle
		handle_label = wx.StaticText(self.panel, -1, "&Handle (username):")
		self.main_box.Add(handle_label, 0, wx.LEFT | wx.TOP, 10)
		handle_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.handle = wx.TextCtrl(self.panel, -1, "", name="Handle")
		handle_sizer.Add(self.handle, 1, wx.EXPAND)
		self.handle_suffix = wx.StaticText(self.panel, -1, ".bsky.social")
		handle_sizer.Add(self.handle_suffix, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
		self.main_box.Add(handle_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
		self.handle.SetFocus()

		# Email
		email_label = wx.StaticText(self.panel, -1, "&Email:")
		self.main_box.Add(email_label, 0, wx.LEFT | wx.TOP, 10)
		self.email = wx.TextCtrl(self.panel, -1, "", name="Email")
		self.main_box.Add(self.email, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

		# Password
		password_label = wx.StaticText(self.panel, -1, "&Password:")
		self.main_box.Add(password_label, 0, wx.LEFT | wx.TOP, 10)
		self.password = wx.TextCtrl(self.panel, -1, "", style=wx.TE_PASSWORD, name="Password")
		self.main_box.Add(self.password, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

		# Confirm Password
		confirm_label = wx.StaticText(self.panel, -1, "Con&firm Password:")
		self.main_box.Add(confirm_label, 0, wx.LEFT | wx.TOP, 10)
		self.confirm_password = wx.TextCtrl(self.panel, -1, "", style=wx.TE_PASSWORD, name="Confirm Password")
		self.main_box.Add(self.confirm_password, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

		# Invite code (optional)
		invite_label = wx.StaticText(self.panel, -1, "&Invite Code (optional):")
		self.main_box.Add(invite_label, 0, wx.LEFT | wx.TOP, 10)
		self.invite_code = wx.TextCtrl(self.panel, -1, "", name="Invite Code")
		self.main_box.Add(self.invite_code, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

		# Date of birth
		dob_label = wx.StaticText(self.panel, -1, "&Date of Birth (YYYY-MM-DD):")
		self.main_box.Add(dob_label, 0, wx.LEFT | wx.TOP, 10)
		self.date_of_birth = wx.TextCtrl(self.panel, -1, "", name="Date of Birth")
		self.main_box.Add(self.date_of_birth, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

		# Buttons
		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.create_btn = wx.Button(self.panel, wx.ID_OK, "&Create Account")
		self.create_btn.Bind(wx.EVT_BUTTON, self.on_create)
		self.create_btn.SetDefault()
		btn_sizer.Add(self.create_btn, 0, wx.ALL, 5)

		self.browser_btn = wx.Button(self.panel, -1, "Open &bsky.app Instead")
		self.browser_btn.Bind(wx.EVT_BUTTON, self.on_open_browser)
		btn_sizer.Add(self.browser_btn, 0, wx.ALL, 5)

		self.cancel_btn = wx.Button(self.panel, wx.ID_CANCEL, "&Cancel")
		btn_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)
		self.main_box.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

		self.panel.SetSizer(self.main_box)
		self.panel.Layout()
		theme.apply_theme(self)

	def on_open_browser(self, event):
		"""Open Bluesky signup page in browser."""
		webbrowser.open("https://bsky.app")
		speak.speak("Opened Bluesky in browser. Create your account there, then use Add account to sign in.")
		dlg = wx.MessageDialog(
			self,
			"Bluesky has been opened in your browser.\n\nAfter creating your account there, close this dialog and use 'Add account' to sign in with your new account.",
			"Bluesky Signup",
			wx.OK | wx.ICON_INFORMATION
		)
		dlg.ShowModal()
		dlg.Destroy()
		self.EndModal(wx.ID_CANCEL)

	def on_create(self, event):
		"""Try to create account via AT Protocol API."""
		handle = self.handle.GetValue().strip()
		email = self.email.GetValue().strip()
		password = self.password.GetValue()
		confirm = self.confirm_password.GetValue()
		invite_code = self.invite_code.GetValue().strip() or None
		date_of_birth = self.date_of_birth.GetValue().strip() or None

		# Validation
		if not handle:
			speak.speak("Please enter a handle")
			self.handle.SetFocus()
			return
		if not email:
			speak.speak("Please enter an email")
			self.email.SetFocus()
			return
		if not password:
			speak.speak("Please enter a password")
			self.password.SetFocus()
			return
		if password != confirm:
			speak.speak("Passwords do not match")
			self.confirm_password.SetFocus()
			return

		# Add .bsky.social if no domain specified
		if '.' not in handle:
			handle = f"{handle}.bsky.social"

		speak.speak("Creating account, please wait")
		wx.GetApp().Yield()

		try:
			# Try the AT Protocol createAccount endpoint
			pds_url = "https://bsky.social"

			data = {
				"handle": handle,
				"email": email,
				"password": password,
			}
			if invite_code:
				data["inviteCode"] = invite_code
			if date_of_birth:
				data["dateOfBirth"] = date_of_birth

			response = requests.post(
				f"{pds_url}/xrpc/com.atproto.server.createAccount",
				json=data,
				headers={"Content-Type": "application/json"},
				timeout=30
			)

			if response.status_code == 200:
				result = response.json()
				speak.speak("Account created successfully")
				dlg = wx.MessageDialog(
					self,
					f"Account created successfully!\n\nYour handle: {result.get('handle', handle)}\n\nYou may need to verify your email. Then use 'Add account' to sign in.",
					"Success",
					wx.OK | wx.ICON_INFORMATION
				)
				dlg.ShowModal()
				dlg.Destroy()
				self.EndModal(wx.ID_OK)
			else:
				try:
					error_data = response.json()
					error_msg = error_data.get('message', error_data.get('error', str(response.status_code)))
				except:
					error_msg = f"Server returned status {response.status_code}"

				# Translate common errors
				if 'InvalidHandle' in error_msg:
					error_msg = "Invalid handle. Handles must be 3-20 characters, containing only letters, numbers, and hyphens."
				elif 'HandleNotAvailable' in error_msg:
					error_msg = "This handle is already taken. Please choose a different one."
				elif 'InvalidEmail' in error_msg:
					error_msg = "Invalid email address."
				elif 'InvalidPassword' in error_msg:
					error_msg = "Invalid password. Passwords must be at least 8 characters."
				elif 'InvalidInviteCode' in error_msg:
					error_msg = "Invalid or expired invite code."
				elif 'PhoneVerification' in error_msg or 'verification' in error_msg.lower():
					error_msg = "Bluesky requires additional verification for new accounts.\n\nPlease create your account at bsky.app instead."

				speak.speak("Account creation failed")
				dlg = wx.MessageDialog(
					self,
					f"Could not create account:\n\n{error_msg}",
					"Error",
					wx.OK | wx.ICON_ERROR
				)
				dlg.ShowModal()
				dlg.Destroy()

		except requests.exceptions.RequestException as e:
			speak.speak("Connection error")
			dlg = wx.MessageDialog(
				self,
				f"Connection error:\n\n{str(e)}\n\nPlease try creating your account at bsky.app instead.",
				"Error",
				wx.OK | wx.ICON_ERROR
			)
			dlg.ShowModal()
			dlg.Destroy()
		except Exception as e:
			speak.speak("Error")
			dlg = wx.MessageDialog(
				self,
				f"Error:\n\n{str(e)}\n\nPlease try creating your account at bsky.app instead.",
				"Error",
				wx.OK | wx.ICON_ERROR
			)
			dlg.ShowModal()
			dlg.Destroy()


def show_signup_dialog(parent):
	"""Show the signup dialog flow."""
	# First, select platform
	platform_dlg = PlatformSignupDialog(parent)
	result = platform_dlg.ShowModal()
	platform = platform_dlg.result
	platform_dlg.Destroy()

	if result != wx.ID_OK or not platform:
		return

	if platform == 'mastodon':
		# Show instance selection
		instance_dlg = MastodonInstanceDialog(parent)
		result = instance_dlg.ShowModal()
		if result == wx.ID_OK and (instance_dlg.instance_url or instance_dlg.invite_code):
			# Show signup form
			signup_dlg = MastodonSignupDialog(
				parent,
				instance_dlg.instance_url,
				instance_dlg.approval_required,
				instance_dlg.reason_required,
				instance_dlg.instance_info,
				instance_dlg.invite_code
			)
			signup_dlg.ShowModal()
			signup_dlg.Destroy()
		instance_dlg.Destroy()

	elif platform == 'bluesky':
		# Show Bluesky signup dialog
		bluesky_dlg = BlueskySignupDialog(parent)
		bluesky_dlg.ShowModal()
		bluesky_dlg.Destroy()
