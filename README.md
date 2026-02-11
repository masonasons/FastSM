# FastSM
FastSM is a (currently) Mastodon/Bluesky client which is based off of the code for the [Quinter](https://github.com/QuinterApp/Quinter) twitter app that I wrote alongside [Quin](https://github.com/trypsynth) in 2021. Note that although this is based off of that code, it is heavily modified and modernized. My hope here is to create a Mastodon/Bluesky app with a similar feel to the Quinter client.

## Features

- Multi-account support for both Mastodon and Bluesky
- Timeline caching for faster startup
- Gap detection for missed posts
- Position restore across restarts
- Audio player with YouTube/Twitter support via yt-dlp
- AI-powered image descriptions (GPT/Gemini)
- Customizable soundpacks
- Invisible interface mode (Windows/Linux)
- Explore/Discover dialog for finding users and content
- Poll support (viewing and voting)
- Content warning handling
- Server-side filters (Mastodon)
- Timeline filtering by user or text

## Options

The options dialog (accessible via Application menu > Global Options) is organized into the following tabs:

- **General**: Basic application settings
- **Timelines**: Ask before dismissing, reverse timelines, sync home timeline position, and timeline caching settings
- **Audio**: Sound settings for media, navigation, and errors, plus audio output device selection
- **YouTube**: yt-dlp path, cookies file, and Deno path settings for YouTube/Twitter audio extraction
- **Templates**: Post display templates, demojify display names, and 24-hour time settings
- **Invisible Interface** (Windows/Linux): Invisible interface settings and keymap selection
- **Advanced**: API settings and general application settings
- **Confirmation**: Toggle confirmations for actions like follow, unfollow, boost, favorite, etc.
- **AI**: Configure GPT/Gemini API keys and prompts for AI image descriptions
