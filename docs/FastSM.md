# FastSM

Welcome to FastSM!

## What is FastSM?

FastSM is a fully accessible, easy-to-use, lightweight social media client that supports both Mastodon and Bluesky. Based on the Quinter App created back in 2021, it works on both Windows and Mac, and is open source, allowing anyone to contribute!

## Supported Platforms

- **Mastodon**: Full support including streaming, lists, bookmarks, and conversations
- **Bluesky**: Full support including quotes, mentions, and notifications

## Interfaces

FastSM has two interfaces:

### GUI Interface
Control FastSM like any other application with buttons, lists, menus, and standard keyboard shortcuts.

### Invisible Interface (Windows only)
Control FastSM from anywhere on your computer using global hotkeys. This is disabled by default but can be enabled in the Advanced settings. Multiple keymaps are available, including a Windows 11-optimized keymap.

## Main Window

The main window contains two list boxes:
1. **Timelines list**: Shows all your timelines (Home, Notifications, Mentions, Sent, etc.)
2. **Posts list**: Shows all posts in the currently selected timeline

FastSM also has a menu bar for accessing all functions without memorizing keyboard shortcuts.

### Menus

* **Application**: Application settings, update profile, manage accounts, and exit
* **Actions**: Post, reply, boost, favorite, bookmark, send direct message, and more
* **Users**: View followers, following, mutual follows, and user management
* **Timeline**: Refresh, load older posts, filter, hide/show timelines
* **Audio**: Play audio, open audio player, adjust volume, stop playback
* **Navigation**: Jump to next/previous post from same user, thread navigation
* **Help**: View documentation, check for updates, about dialog

## Keyboard Shortcuts

### GUI Shortcuts

All menu items show their keyboard shortcuts. Common shortcuts include:
- **Ctrl+N** (Cmd+N on Mac): New post
- **Ctrl+R** (Cmd+R on Mac): Reply
- **Ctrl+E**: Edit post
- **Ctrl+Shift+R**: Boost/Repost
- **Ctrl+K**: Favorite/Like
- **Ctrl+L**: Follow/Unfollow
- **Ctrl+B**: Block/Unblock
- **Ctrl+D**: Send direct message
- **Ctrl+O**: Open URL from post
- **Ctrl+C**: Copy post to clipboard
- **Ctrl+G**: Load conversation
- **Ctrl+U**: User timeline
- **Ctrl+W**: Close timeline
- **Ctrl+Shift+W**: Hide window
- **Ctrl+Shift+A**: Audio player
- **Ctrl+Enter**: Play media
- **Ctrl+Shift+Enter**: Stop audio

### Invisible Interface Keys (Windows only)

Default keymap (can be customized via keymap files):

| Action | Shortcut |
|--------|----------|
| Show/hide window | Ctrl+Win+W |
| New post | Alt+Win+N |
| Previous timeline | Alt+Win+Left |
| Next timeline | Alt+Win+Right |
| Previous post | Alt+Win+Up |
| Next post | Alt+Win+Down |
| Move up 20 | Ctrl+Win+Page Up |
| Move down 20 | Ctrl+Win+Page Down |
| Go to top | Alt+Win+Home |
| Go to bottom | Alt+Win+End |
| Reply | Ctrl+Win+R |
| Edit post | Alt+Win+E |
| Boost/Repost | Ctrl+Win+Shift+R |
| Favorite/Like | Alt+Win+K |
| Bookmark | Alt+Ctrl+Win+B |
| Quote | Alt+Win+Q |
| Direct message | Alt+Win+Ctrl+D |
| Follow/Unfollow | Alt+Win+L |
| Block/Unblock | Alt+Win+Shift+B |
| Mute/Unmute user | Alt+Win+Shift+L |
| Pin/Unpin | Alt+Win+P |
| Delete post | Alt+Win+Delete |
| Open conversation | Alt+Win+C |
| Open post viewer | Alt+Win+V |
| View image | Ctrl+Alt+Win+V |
| Volume up | Alt+Win+Ctrl+Up |
| Volume down | Alt+Win+Ctrl+Down |
| Open URL | Alt+Win+Enter |
| Play audio | Alt+Win+Shift+Enter |
| Stop audio | Ctrl+Win+Shift+Enter |
| Audio player | Ctrl+Win+Shift+A |
| Profile overview | Alt+Win+; |
| Speak reply info | Alt+Win+Shift+; |
| Load older posts | Alt+Win+Page Up |
| Refresh | Alt+Win+Ctrl+U |
| User timeline | Alt+Win+U |
| User profile | Alt+Win+Shift+U |
| Update profile | Ctrl+Win+Shift+U |
| Close timeline | Alt+Win+' |
| View followers | Alt+Win+[ |
| View following | Alt+Win+] |
| Global options | Alt+Win+O |
| Account options | Ctrl+Alt+Win+O |
| Previous post same user | Alt+Win+Shift+Left |
| Next post same user | Alt+Win+Shift+Right |
| Previous in thread | Alt+Win+Shift+Up |
| Next in thread | Alt+Win+Shift+Down |
| Copy post | Ctrl+Win+Shift+C |
| Add to list | Alt+Win+A |
| Remove from list | Alt+Win+Shift+A |
| View lists | Alt+Win+Ctrl+L |
| Custom timelines | Alt+Win+Ctrl+T |
| Filter timeline | Ctrl+Alt+Win+F |
| Search | Alt+Win+/ |
| User search | Alt+Win+Shift+/ |
| Account manager | Ctrl+Win+A |
| Previous account | Ctrl+Shift+Win+Page Up |
| Next account | Ctrl+Shift+Win+Page Down |
| Repeat item | Alt+Win+Space |
| Speak account | Alt+Win+Ctrl+A |
| Open post URL | Ctrl+Alt+Shift+Win+Enter |
| Toggle autoread | Alt+Win+Shift+E |
| Toggle timeline mute | Alt+Win+Shift+M |
| Context menu | Ctrl+Win+Alt+M |
| Exit | Alt+Win+Shift+Q |

## Templates

FastSM uses a template system to customize how posts are displayed. Template variables are enclosed in dollar signs ($).

### Post Templates

| Variable | Description |
|----------|-------------|
| $account.acct$ | The @handle of the user |
| $account.display_name$ | The display name of the user |
| $text$ | The post text |
| $created_at$ | Timestamp when posted |
| $reblogs_count$ | Number of boosts/reposts |
| $favourites_count$ | Number of favorites/likes |

### Boost Templates

| Variable | Description |
|----------|-------------|
| $account.display_name$ | Display name of who boosted |
| $reblog.account.display_name$ | Display name of original poster |
| $text$ | The boosted post text |
| $created_at$ | Timestamp |

### Quote Templates

| Variable | Description |
|----------|-------------|
| $account.acct$ | The @handle of the quoter |
| $account.display_name$ | Display name of the quoter |
| $text$ | The quote post text |

### Direct Message Templates

| Variable | Description |
|----------|-------------|
| $account.display_name$ | Sender's display name |
| $text$ | Message text |
| $created_at$ | Timestamp |

### User Templates

| Variable | Description |
|----------|-------------|
| $display_name$ | Display name |
| $acct$ | @handle |
| $followers_count$ | Number of followers |
| $following_count$ | Number following |
| $statuses_count$ | Number of posts |
| $note$ | User bio |

### Notification Templates

| Variable | Description |
|----------|-------------|
| $type$ | Notification type (follow, favourite, reblog, mention, etc.) |
| $account.display_name$ | Display name of the user |
| $account.acct$ | @handle of the user |

## Options

FastSM has two options dialogs: Global Options (for app-wide settings) and Account Options (for per-account settings).

### Global Options

#### General Tab

- **Ask before dismissing timelines**: Show confirmation when closing timelines
- **Play a sound when a post contains media**: Audio notification for posts with media
- **Play a sound when you navigate to a timeline that may have new items**: Notification sound for timelines with new content
- **Remove emojis and other unicode characters from display names**: Clean up emoji-heavy display names (includes Mastodon custom emoji shortcodes)
- **Remove emojis and other unicode characters from post text**: Clean up post text
- **Reverse timelines (newest on bottom)**: Put newest posts at the bottom
- **Word wrap in text fields**: Enable word wrap in all text fields
- **Play sound and speak message for errors**: Audio and speech feedback for errors
- **When getting URLs from a post, automatically open the first URL if it is the only one**: Quick URL opening
- **Use 24-hour time for post timestamps**: Display times in 24-hour format
- **Automatically open audio player when media starts playing**: Show player controls automatically
- **Stop audio playback when audio player closes**: Stop media when closing the player
- **Use Ctrl+Enter to send posts (instead of Enter)**: Prevent accidental sends
- **Content warnings**: Choose how to handle CWs:
  - Hide post text (show CW only)
  - Show CW followed by post text
  - Ignore CW (show post text only)

#### Templates Tab

Customize display templates for:
- Post template
- Quote template
- Boost template
- Copy template (for copying posts to clipboard)
- Direct message template
- User template
- Notification template
- **Include image/media descriptions in post text**: Add alt text to post display

#### Advanced Tab

- **Enable invisible interface**: Enable global hotkeys (Windows only)
- **Sync invisible interface with UI**: Keep invisible interface in sync (disable for better performance)
- **Repeat items at edges of invisible interface**: Repeat when reaching timeline boundaries
- **Keymap**: Select keyboard layout (default, win11, or custom)
- **Speak position information**: Announce position when switching timelines
- **Update time (in minutes)**: How often to check for new posts
- **Max API calls when fetching users**: Limit for follower/following lists (1 call = 200 users)
- **Number of posts to fetch per call**: Posts per API request (max 40)
- **Number of API calls to make when loading timelines**: Initial load depth (1-10)
- **Use only one API call on initial timeline loads**: Faster startup
- **Enable streaming for home and notifications**: Real-time updates (Mastodon only)
- **Load all previous posts until timeline is fully loaded**: Complete history loading
- **Sync home timeline position with Mastodon**: Remember position across sessions
- **Check for updates on startup**: Automatic update checking
- **Dark mode**: Off, On, or Auto (follow system)
- **yt-dlp path**: Path to yt-dlp for YouTube/Twitter audio extraction
- Download buttons for yt-dlp

#### Confirmation Tab

Enable confirmation dialogs for:
- Boosting/Unboosting
- Favoriting/Unfavoriting
- Following/Unfollowing
- Blocking/Unblocking
- Muting/Unmuting
- Deleting posts
- Bookmarking/Unbookmarking

#### AI Tab

Configure AI-powered image descriptions:
- **AI Service**: None, OpenAI, or Google Gemini
- **API Keys**: Enter your API keys
- **Model selection**: Choose which AI model to use
- **Image description prompt**: Customize the prompt for descriptions

#### Audio Tab

- **Audio output device**: Select which audio device to use for soundpacks and media playback

### Account Options

#### General Tab

- **Soundpacks**: Choose your soundpack
- **Sound pan**: Pan sounds left/right for multi-account differentiation
- **Soundpack volume**: Adjust soundpack volume
- **Post Footer**: Automatically append text to your posts
- **Show mentions in notifications buffer**: Include mentions in notifications (Mastodon only)

#### Timelines Tab

- **Timeline order**: Drag and reorder built-in timelines (requires restart)

## Client-Side Filters

Filter timeline posts by type using Timeline > Filter Timeline:

- Original posts (not replies or boosts)
- Replies to others
- Replies to me
- Threads (self-replies)
- Boosts/Reposts
- Quote posts
- Posts with media
- Posts without media
- Your posts
- Your replies
- Text search (searches post text, display name, and username)

Filters are applied client-side and can be cleared to restore all posts.

## Audio Playback

FastSM can play audio from posts including:
- Direct audio/video attachments
- YouTube videos (audio extracted via yt-dlp)
- Twitter/X videos
- TikTok videos
- Twitch streams
- SoundCloud tracks
- Direct media URLs (mp3, ogg, wav, etc.)

### Audio Player Controls

When audio is playing, open the Audio Player (Audio menu or Ctrl+Win+Shift+A in invisible mode):
- **Up/Down arrows**: Adjust volume
- **Left/Right arrows**: Seek 5 seconds
- **Space**: Play/Pause
- **E**: Speak elapsed time
- **R**: Speak remaining time
- **T**: Speak total time
- **Escape**: Close player

## Soundpacks

FastSM supports custom soundpacks. Place soundpack folders in:
- `sounds/` folder in your FastSM directory
- User config directory:
  - Windows: `%APPDATA%\FastSM\sounds\`
  - macOS: `~/Library/Application Support/FastSM/sounds/`
  - Linux: `~/.config/FastSM/sounds/`

The official soundpacks repository: [FastSM Soundpacks](https://github.com/FastSMApp/FastSM-soundpacks)

## Troubleshooting

### Checkboxes read as buttons
If your screen reader announces checkboxes as buttons, go to Global Options > Advanced and set **Dark mode** to "Off".

## Multiple Accounts

FastSM supports multiple accounts across both Mastodon and Bluesky:
- Use **Application > Account Manager** to add/remove accounts
- Switch between accounts using the account selector
- Each account can have its own soundpack and sound settings

## Keymaps

Custom keymaps can be placed in the `keymaps/` folder. Available keymaps:
- **default**: Standard Windows keymap
- **win11**: Optimized for Windows 11 compatibility

When enabling the invisible interface on Windows 11, FastSM will offer to switch to the win11 keymap automatically.

Enjoy FastSM!
