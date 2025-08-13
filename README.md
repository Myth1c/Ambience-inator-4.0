# Ambience-inator
## A discord music bot that handles playlists. Designed for use in my own D&D sessions for background music.

## Features
- Able to save as many playlists as you'd like
- Takes youtube URLs and plays audio directly onto discord
- Can handle shuffling playlists or looping a single song
- Loops to the start of the playlist when reaching the end
- Controlled entirely with a GUI using python's tkinter libraries
- Prints out a queue for previously played songs, currently playing, and songs left in the playlist in a text channel of your choice

## Main window
<img width="502" height="506" alt="Main window of Ambience-inator" src="https://github.com/user-attachments/assets/778063e3-dfca-4fc3-9094-4ce363d50a84" />

## Edit Mode Window
<img width="828" height="652" alt="Edit Mode | Updating/Removing a song from the Combat playlist" src="https://github.com/user-attachments/assets/42733be2-19ab-41f1-aa1c-d7ff95f98380" />

## Discord Queue Message
<img width="594" height="490" alt="image" src="https://github.com/user-attachments/assets/b5ef8428-08e2-477c-888d-bdc3e10a2d1e" />


# SETUP
1. Create a new file named "config.json" in the root folder
2. Open the file and paste this in:
   ```json
   {
        "bot_token" : "YOUR_BOT_TOKEN",
        "channel_id" : YOUR_TEXT_CHANNEL_ID,
        "vchannel_id" : YOUR_VOICE_CHANNEL_ID
   }
3. Replace the `"YOUR_BOT_TOKEN"` with your bot token (Keep the quotes). If you aren't sure how to get IDs refer to the "How to get channel IDs" section below.
4. Replace `YOUR_TEXT_CHANNEL_ID` with the ID of the text channel where you wish the bot to display the Queue message (Make sure the channel ID isn't in quotes)
5. Replace `YOUR_VOICE_CHANNEL_ID` with the ID of the voice channel you want the bot to join (Make sure the voice channel ID isn't in quotes)
6. Open a terminal/command prompt to the desired location and run `python main.py` and this should start the bot
7. Marking as executable on Linux: open a terminal in the directory of ambience-inator. Run `chmod +x main.py`



# EDIT MODE USAGE
1. Enter "Edit Mode" by clicking the "Edit Mode" button
2. Enter a playlist name and hit "Create Playlist"
3. Provide a YouTube URL in the "URL" text entry field
4. Hit "Add New Song". If you don't supply a title, the bot will fetch the title of the YouTube video.
5. Hit "Save"
6. Hit "Cancel" to exit Edit Mode


# PLAYLIST USAGE
1. Hit the "Join VC" button. The bot should then connect to the specified VC in the config file
2. Select a playlist
3. The bot should start playing a song (given that the URL provided is valid) and it will display a Queue message in the provided text channel in the config files


# How to get channel IDs
1. Go to your discord settings
2. Scroll down to "Advanced" under "App Settings"
3. Check "Developer Mode" box
4. Right click channel you want the ID of and click "Copy Channel ID"
5. If you don't see that, try restarting discord first


# Dependencies
- discord.py (pip)
- yt-dlp (pip)
- FFmpeg (system install)
- tkinter (bundled with Python, but may need python3-tk on Linux)
