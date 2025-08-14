#!/usr/bin/env python

import tkinter as tk
from tkinter import ttk
import asyncio
import discord
from discord.ext import commands
from discord import FFmpegPCMAudio
import threading
import sys
from yt_dlp import YoutubeDL
import json
import random
from functools import partial
import os
from audiomixer import MixedAudio, MixedAudioSource

CONFIG_FILE = "./config.json"

# Load config or create default if missing
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump({}, f)

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

#region ====== CONFIG ======
TOKEN = config.get("bot_token")
CHANNEL_ID = config.get("channel_id")
VOICE_ID = config.get("vchannel_id")
PLAYLIST_DICTIONARY = "./playlists.json"
AMBIENCE_DICTIONARY = "./ambience.json"

YDL_OPTS = {
    'format': 'bestaudio[ext=webm][acodec=opus]/bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # avoid IPv6 issues
}

FFMPEG_OPTS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}
#endregion ====================

#region ==== Global Variables ====

playlist_Info = {
    "playlist_name": None,
    "playlist": {},
    "queue": {},
    "playlist_previous" : {},
    "playlist_current" : {},
    "playlist_next" : {},
    "ambience_current" : {}
}

ambience_Info = {
    "ambience_name" : None,
    "current_url" : None
}

bot_Status = {
    "voice_client": None,
    "is_music_playing": False,
    "is_ambience_playing": False,
    "queue_message": None,
    "shuffle_mode": True,
    "loop_mode": False,
}

edit_Mode = {
    "playlist_name" : None,
    "edited_playlist" : {},
    "selected_song" : {},
    "current_song_button" : None,
    "prev_song_button" : None,
    "current_playlist_button" : None,
    "prev_playlist_button" : None,
    "add_remove_button" : None,
    "title_label" : None,
    "title_entry" : None,
    "url_label" : None,
    "url_entry" : None,
    "update_btn" : None,
    "playlist_dictionary" : {},

    "edited_ambience_list" : {},
    "ambiance_dictionary" : {},
    "selected_ambience" : {},
    "selected_ambience_btn" : None,
    "previous_ambience_btn" : None,
    "add_rmv_ambi_btn" : None,
    "change_ambi_btn" : None
}


voiceChat_button = None
playback_button = None

current_selected_button = None
previous_selected_button = None

playlists_frame = None
ambience_frame = None

audioMixer = MixedAudio()
audioSource = MixedAudioSource(audioMixer)
#endregion ==========================



# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Global reference to loop for GUI thread
loop = asyncio.get_event_loop()

# Function to shut down bot
async def shutdown():
    bot_Status["is_music_playing"] = False
    bot_Status["is_ambience_playing"] = False
    if bot_Status["queue_message"] is not None:
        await bot_Status["queue_message"].delete()
    await bot.close()
    root.quit()
    sys.exit(0)


#region ==== Helper Functions ====

def load_playlists():
    # Load the given playlist from the JSON file
    try:
        with open(PLAYLIST_DICTIONARY, 'r') as f:
            return  json.load(f)
    except FileNotFoundError:
        # Return empty dictionary if the file does not exist
        if not os.path.exists(PLAYLIST_DICTIONARY):
            with open(PLAYLIST_DICTIONARY, "w") as f:
                json.dump({}, f)
        return {}

def save_playlist(playlist_name, edited_playlist: dict = {}):
    # Save the playlist to a JSON file
    playlists = load_playlists()

    playlists[playlist_name.lower()] = edited_playlist

    with open(PLAYLIST_DICTIONARY, 'w') as f:
        json.dump(playlists, f, indent=4)

def select_playlist(playlist_name):
    # Get the playlist from the JSON file
    playlists = load_playlists()
    if playlist_name.lower() not in playlists:
        return None
    
    # Set basic playlist info
    playlist_Info["playlist"] = playlists[playlist_name.lower()]
    playlist_Info["playlist_name"] = playlist_name.capitalize()
    playlist_Info["queue"] = playlists[playlist_name.lower()].copy()
    playlist_Info["playlist_previous"] = {}
    playlist_Info["playlist_current"] = {}
    playlist_Info["playlist_next"] = {}

    return playlist_Info["playlist"]

async def send_message(bot: discord.Client, channel_id: int, message: str):
    try:
        channel = bot.get_channel(channel_id)
        if channel is None:
            channel = await bot.fetch_channel(channel_id)
        await channel.send(message)
    except Exception as e:
        print(f"Error sending message {e}")

async def initialize_queue(bot: discord.Client, channel_id: int, message: str):
    try:
        channel = bot.get_channel(channel_id)
        if channel is None:
            channel = await bot.fetch_channel(channel_id)
        bot_Status["queue_message"] = await channel.send(message)
    except Exception as e:
        print(f"Error sending message {e}")

async def join_vc(bot: discord.Client, voice_id: int, button: tk.Button = None):
    try:

        if bot_Status["voice_client"]:
            await bot_Status["voice_client"].disconnect()
            bot_Status["voice_client"] = None
            button.config(text = "Join VC", bg = "firebrick1")
            return

        channel = bot.get_channel(voice_id)
        if channel and isinstance(channel, discord.VoiceChannel):
            bot_Status["voice_client"] = await channel.connect()
    except Exception as e:
        print(f"Error connecting to VC: {e}")
    button.config(text = "Leave VC", bg = "SpringGreen4")

async def update_queue_message():

    if bot_Status["queue_message"] is None:
        await initialize_queue(bot, CHANNEL_ID, "Putting in the queue message to be edited!")


    message = ""
    queueIndex = 1

    # Update the queue message with our formating for previously played songs [*Song Title*](<URL>)
    message += f"\n\n\n# Current Playlist: {playlist_Info['playlist_name']}\n"
    for song in playlist_Info["playlist_previous"]:
        message += f"\n{queueIndex}. - [*{playlist_Info["playlist_previous"][song]}*](<{song}>)"
        queueIndex += 1

    # Update the queue message with our formating for currently playing song ## [Song Title](<URL>)
    for song in playlist_Info["playlist_current"]:
        message += f"\n## {queueIndex}. - [{playlist_Info["playlist_current"][song]}](<{song}>)"
        queueIndex += 1

    # Update the queue message with our formating for next song [**Song Title**](<URL>)
    for song in playlist_Info["playlist_next"]:
        message += f"\n{queueIndex}. - [**{playlist_Info['playlist_next'][song]}**](<{song}>)"
        queueIndex += 1

    await bot_Status["queue_message"].edit(content=message)

def get_direct_url(url):
    
    with YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
        return info["url"]  # Direct media link

def load_ambience_dictionary():
    try:
        with open(AMBIENCE_DICTIONARY, 'r') as f:
            return  json.load(f)
    except FileNotFoundError:
        # Return empty dictionary if the file does not exist
        if not os.path.exists(AMBIENCE_DICTIONARY):
            with open(AMBIENCE_DICTIONARY, "w") as f:
                json.dump({}, f)
        return {}

def save_ambience_dictionary(ambience_list : dict = {}):
    with open(AMBIENCE_DICTIONARY, 'w') as f:
        json.dump(ambience_list, f, indent=4)

#endregion

#region ======= MUSIC PLAYBACK =========

async def rewind_playlist():

    # Setup a new empty dictionary and copy everything from "previous" to the new dictionary
    # Then clear the "previous" dictionary 
    new_playlist = {}
    new_playlist.update(playlist_Info["playlist_previous"])
    playlist_Info["playlist_previous"].clear()

    playlist_Info["queue"] = new_playlist.copy()

    # Simple check to see if we are in shuffle mode
    if bot_Status["shuffle_mode"]:
        await shuffle_playlist()

async def shuffle_playlist():
    # Convert the dictionary to a list of items and shuffle it
    queue_items = list(playlist_Info["queue"].items())
    random.shuffle(queue_items)

    # Convert the shuffled list back to a dictionary
    playlist_Info["queue"] = dict(queue_items)

async def toggle_shuffle(shuffle_btn: tk.Button):
    bot_Status["shuffle_mode"] = not bot_Status["shuffle_mode"]

    if bot_Status["shuffle_mode"]:
        shuffle_btn.config(bg = "SpringGreen4", fg = "white")
    else:
        shuffle_btn.config(bg = "firebrick1", fg = "white")

async def toggle_loop(loop_btn: tk.Button):
    bot_Status["loop_mode"] = not bot_Status["loop_mode"]

    if bot_Status["loop_mode"]:
        loop_btn.config(bg = "SpringGreen4", fg = "white")
    else:
        loop_btn.config(bg = "firebrick1", fg = "white")

async def check_song_end():
    while True:
        # Poll the mixer process
        if not audioMixer.proc_music or audioMixer.proc_music.poll() is not None:
            # Song ended, play next
            await load_next_song()
            break
        await asyncio.sleep(1)  # check every second

async def load_next_song():
    
    if bot_Status["loop_mode"] is True and playlist_Info["playlist_current"]:
        audioMixer.start_music(get_direct_url(next(iter(playlist_Info["playlist_current"]))))
        return

    if playlist_Info["playlist_current"]:
        playlist_Info["playlist_previous"].update(playlist_Info["playlist_current"])

    if playlist_Info["queue"]:
        first_song_url = next(iter(playlist_Info["queue"]))  # Get the first key (URL)
        playlist_Info["playlist_current"] = {first_song_url : playlist_Info["queue"][first_song_url]}
        playlist_Info["queue"].pop(first_song_url)  # Remove the song from the queue
    else:
        await rewind_playlist()
        first_song_url = next(iter(playlist_Info["queue"]))  # Get the first key (URL)
        playlist_Info["playlist_current"] = {first_song_url : playlist_Info["queue"][first_song_url]}
        playlist_Info["queue"].pop(first_song_url)  # Remove the song from the queue

    playlist_Info["playlist_next"] = playlist_Info["queue"]
    
    current_url = get_direct_url(next(iter(playlist_Info["playlist_current"])))
    audioMixer.start_music(current_url)


    await update_queue_message()
    asyncio.get_event_loop().create_task(check_song_end())

async def start_music():

    try:
        await load_next_song()
        if playlist_Info["playlist_current"]:
            if not bot_Status["is_music_playing"]: 
                bot_Status["voice_client"].play(audioSource)
                bot_Status["is_music_playing"] = True

    except Exception as e:
        print(f"Error playing audio: {e}")

async def toggle_playback_music(music_play_btn : tk.Button):

    if not bot_Status["voice_client"]:
        print("Not currently playing a loaded playlist")


    if not audioMixer.music_paused:
        audioMixer.pause_music()
        music_play_btn.config(text="Play", bg = "firebrick1")
    elif audioMixer.music_paused:
        audioMixer.resume_music()
        music_play_btn.config(text="Pause", bg = "SpringGreen4")

async def skip_current_song():
    
    audioMixer.stop_music()
    await load_next_song()
    
    global playback_button
    playback_button.config(text="Pause Playback", bg = "SpringGreen4")

async def goto_previous_song():

    if not playlist_Info["playlist_previous"]:
        print("No previous song available")
        return
        
    # Move current song to front of queue
    playlist_Info["queue"] = {**playlist_Info["playlist_current"], **playlist_Info["queue"]}


    # Pull most recent song from previous list
    if playlist_Info["playlist_previous"]:
        last_url, last_title = list(playlist_Info["playlist_previous"].items())[-1]
        playlist_Info["playlist_current"] = None

        # Remove it from previous
        del playlist_Info["playlist_previous"][last_url]
        playlist_Info["queue"] = {**{last_url : last_title}, **playlist_Info["queue"]}

    audioMixer.stop_music()
    await load_next_song()

    global playback_button
    playback_button.config(text="Pause Playback", bg = "SpringGreen4")

def music_volume_changed(vol):
    vol = float(vol) / 100

    audioMixer.set_music_volume(vol)

#endregion ================================

#region ====== AMBIENCE PLAYBACK =======
def ambient_volume_changed(vol):
    vol = float(vol) / 100

    audioMixer.set_ambience_volume(vol)

async def toggle_playback_ambience(btn : tk.Button):
    if not bot_Status["voice_client"]:
        print("Not currently playing a loaded playlist")

    if not audioMixer.ambience_paused:
        audioMixer.pause_ambience()
        btn.config(text="Play", bg = "firebrick1")
    elif audioMixer.ambience_paused:
        audioMixer.resume_ambience()
        btn.config(text="Pause", bg = "SpringGreen4")

async def start_ambience():

    try:
        await load_ambience()
        if ambience_Info["current_url"]:
            if not bot_Status["is_ambience_playing"]:
                bot_Status["voice_client"].play(audioSource)
                bot_Status["is_ambience_playing"] = True
    except Exception as e:
        print(f"Error playing ambience: {e}")

async def load_ambience():
    audioMixer.start_ambience(get_direct_url(ambience_Info["current_url"]), True)


#endregion ================================

#region ===== GUI =====

def start_gui():
    global root
    root = tk.Tk()
    root.title("Ambience-inator 4.1")
    root.resizable(False, False)

    root.config(bg="gray25")
#region Playlist Selection
    # ===== Top Frame for Playlists =====
    playlist_frame = tk.Frame(root)
    playlist_frame.grid(row=0, column=0, sticky="n")  # top & centered
    playlist_frame.config(bg="gray25")
    global playlists_frame
    playlists_frame = playlist_frame

    create_playlist_buttons(playlist_frame)  # This will grid into the playlist_frame
#endregion

#region Music Controls
    # ==== Music controls frame ====
    music_control = tk.Frame(root)
    music_control.grid(row = 1, column = 0, pady = 40)
    music_control.config(bg="gray25")

    music_label = tk.Label(music_control, text="Music Controls", font=("Arial", 14, "bold"))
    music_label.grid(row=0, column=0, columnspan=5, pady=(0, 10))  # span all columns with some bottom padding
    music_label.config(bg="gray25", fg="white")

    # Previous Song Button
    prev_btn = tk.Button(music_control, text="Previous", width=5, height = 1, bg = "light steel blue", command=lambda: asyncio.run_coroutine_threadsafe(goto_previous_song(), loop))
    prev_btn.grid(row = 1, column = 0, padx = 5, pady=2, stick = "ew")
    
    # Music Volume Slider
    music_volume = tk.DoubleVar()
    volume_slider = tk.Scale(music_control, from_=0, to=100, orient="horizontal", length=50, sliderlength=10, width=15, showvalue=False, tickinterval=0, bg = "gray25", variable=music_volume, command=lambda vol = music_volume: music_volume_changed(vol), border=0)
    volume_slider.set(100)
    volume_slider.grid(row=1, column=1, padx=5)

    # Music Progress Bar
    progress_var = tk.DoubleVar()
    progress_bar = ttk.Progressbar(music_control, variable=progress_var, maximum=100, length=200)
    progress_bar.grid(row=1, column=2, padx=10, sticky="ew")

    # Play/Pause Button
    music_playback_btn = tk.Button(music_control, text="Pause", bg = "SpringGreen4", fg="white", width=5, height = 1, command=lambda: asyncio.run_coroutine_threadsafe(toggle_playback_music(music_playback_btn), loop))
    music_playback_btn.grid(row = 1, column = 3, padx = 5, pady=2, stick = "ew")

    # Next Song Button
    skip_btn = tk.Button(music_control, text="Next", width=5, bg = "light steel blue", height = 1, command=lambda: asyncio.run_coroutine_threadsafe(skip_current_song(), loop))
    skip_btn.grid(row = 1, column = 4, padx = 5, pady=2, stick = "ew")

    # Shuffle Playlist Button
    shuffle_btn = tk.Button(music_control, text="Shuffle Playlist", width = 10, height = 1, bg="SpringGreen4", fg="white", command = lambda: asyncio.run_coroutine_threadsafe(toggle_shuffle(shuffle_btn), loop))
    shuffle_btn.grid(row = 2, column = 0, columnspan=2, padx = 5, pady=2, stick = "ew")

    # Loop Song Button
    loop_btn = tk.Button(music_control, text="Loop Current Song", width = 10, height = 1, bg="firebrick1", fg="white", command = lambda: asyncio.run_coroutine_threadsafe(toggle_loop(loop_btn), loop))
    loop_btn.grid(row = 2, column = 3, columnspan=2, padx = 5, pady=2, stick = "ew")
#endregion

#region Ambience Selection

    # ==== Frame for Ambience ====
    amb_frame = tk.Frame(root)
    amb_frame.grid(row=2, column=0, stick="n")
    amb_frame.config(bg="gray25")
    global ambience_frame
    ambience_frame = amb_frame

    create_ambience_buttons(amb_frame)
#endregion

#region Ambience Controls
    # ==== Ambience controls frame ====
    amb_control = tk.Frame(root)
    amb_control.grid(row = 3, column = 0, pady = 40)
    amb_control.config(bg="gray25")

    amb_label = tk.Label(amb_control, text="Ambience Controls", font=("Arial", 14, "bold"))
    amb_label.grid(row=0, column=0, columnspan=5, pady=(0, 10))  # span all columns with some bottom padding
    amb_label.config(bg="gray25", fg="white")

    # Music Volume Slider
    amb_volume = tk.DoubleVar()
    amb_volume_slider = tk.Scale(amb_control, from_=0, to=100, orient="horizontal", length=500, sliderlength=10, width=15, showvalue=False, tickinterval=0, bg = "gray25", variable=amb_volume, command=lambda vol = amb_volume: ambient_volume_changed(vol), border=0)
    amb_volume_slider.set(25)
    amb_volume_slider.grid(row=1, column=0, padx=5, columnspan=4)

    # Play/Pause Button
    amb_playback_btn = tk.Button(amb_control, text="Pause", bg = "SpringGreen4", fg="white", width=5, height = 1)
    amb_playback_btn.grid(row = 2, column = 0, padx = 4, pady=2, stick = "ew", columnspan=5)
    amb_playback_btn.config(command=lambda: asyncio.run_coroutine_threadsafe(toggle_playback_ambience(amb_playback_btn), loop))

#endregion

#region Bot Controls
    # ===== Bottom Frame for Controls =====
    control_frame = tk.Frame(root)
    control_frame.grid(row=4, column=0, pady=10)
    control_frame.config(bg="gray25")

    controls_label = tk.Label(control_frame, text="Bot Controls", font=("Arial", 14, "bold"))
    controls_label.grid(row=0, column=0, columnspan=4, pady=(0, 10))  # span all columns with some bottom padding
    controls_label.config(bg="gray25", fg="white")

    editAmb_btn = tk.Button(control_frame, text="Edit Ambience", width=15, height = 1, bg = "light steel blue", command=lambda: asyncio.run_coroutine_threadsafe(open_ambience_popup(), loop))
    editAmb_btn.grid(row = 1, column = 0, padx = 5, pady=2, stick = "ew")

    voiceChat_button = tk.Button(control_frame, text="Join VC", width=15, height = 1, bg="firebrick1", fg="white")
    voiceChat_button.grid(row = 1, column = 1, padx = 5, pady=2, stick = "ew")
    voiceChat_button.config(command=lambda: asyncio.run_coroutine_threadsafe(join_vc(bot, VOICE_ID, voiceChat_button), loop))

    editMusic_btn = tk.Button(control_frame, text="Edit Playlists", width=15, height = 1, bg = "light steel blue", command=lambda: asyncio.run_coroutine_threadsafe(open_edit_popup(), loop))
    editMusic_btn.grid(row = 2, column = 0, padx = 5, pady=2, stick = "ew")

    stop_btn = tk.Button(control_frame, text="Shutdown", width=15, height = 1, bg = "light steel blue", command=lambda: asyncio.run_coroutine_threadsafe(shutdown(), loop))
    stop_btn.grid(row = 2, column = 2, padx = 5, pady=2, stick = "ew")
#endregion
    root.mainloop()

def create_playlist_buttons(parent):
    playlists = load_playlists()
    col = 0
    row = 1

    btn_width = 10
    btn_height = 1

    # Add the label at the top row 0
    label = tk.Label(parent, text="Playlist Selection", font=("Arial", 14, "bold"))
    label.grid(row=0, column=0, columnspan=4, pady=(0, 10))  # span all columns with some bottom padding
    label.config(bg="gray25", fg="white")

    max_per_row = 4

    for playlist_name in playlists.keys():
        if len(playlists[playlist_name]) < 1:
            continue
        btn = tk.Button(
            parent,
            text = playlist_name,
            width = btn_width,
            height = btn_height,
            bg = "light steel blue"
        )
        btn.grid(row = row, column = col, padx = 5, pady = 5, sticky = "ew")

        btn.config(command = partial(handle_playlist_click, playlist_name, btn))

        col += 1
        if col >= max_per_row:
            col = 0
            row += 1

def handle_playlist_click(playlist_name, button):

    global current_selected_button, previous_selected_button

    select_playlist(playlist_name)

    if bot_Status["shuffle_mode"]:
        asyncio.run_coroutine_threadsafe(shuffle_playlist(), loop)
        print("Shuffling playlist!")

    if bot_Status["voice_client"] is None:
        # asyncio.run_coroutine_threadsafe(join_vc(bot, VOICE_ID), loop)
        print("Wasn't in a VC")
        return


    if bot_Status["is_music_playing"] is False:
        asyncio.run_coroutine_threadsafe(start_music(), loop)
        print("No song was playing, starting playback!")


    elif bot_Status["is_music_playing"] is True:
        audioMixer.stop_music()
        bot_Status["is_music_playing"] = False
        asyncio.run_coroutine_threadsafe(start_music(), loop)
        print("A song was playing, loading new playlist!")


    if current_selected_button == button:
        return

    if current_selected_button is not None:
        previous_selected_button = current_selected_button
    
    current_selected_button = button

    if current_selected_button is not None:
        current_selected_button.config(bg = "slate blue")

    if previous_selected_button is not None:
        previous_selected_button.config(bg = "light steel blue")

async def open_edit_popup():

    # bot_Status["edit_mode"] = True

    popup = tk.Toplevel(bg="gray25")
    popup.title("Edit Playlist")
    popup.geometry("800x600")
    popup.resizable(False, False)
    popup.grab_set()  # Modal window

    popup.grid_rowconfigure(0, weight=1)
    popup.grid_columnconfigure(0, weight=1)
    popup.grid_columnconfigure(1, weight=1)


    left_container = tk.Frame(popup, bd=2, relief="sunken")
    left_container.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

    right_container = tk.Frame(popup, bd=2, relief="sunken")
    right_container.grid(row=0, column=1, sticky="nsew", padx=(10, 5), pady=10)

    # Configure rows and columns for left and right containers
    for container in (left_container, right_container):
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)


    # Left: Canvas + Scrollbar for playlist buttons

    left_canvas = tk.Canvas(left_container)
    left_scrollbar = tk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
    left_canvas.config(yscrollcommand=left_scrollbar.set)

    left_canvas.grid(row=0, column=0, sticky="nsew")
    left_scrollbar.grid(row=0, column=1, sticky="ns")

    left_buttons_frame = tk.Frame(left_canvas)
    left_canvas.create_window((0, 0), window=left_buttons_frame, anchor="nw")

    def on_left_frame_configure(event):
        left_canvas.configure(scrollregion=left_canvas.bbox("all"))

    left_buttons_frame.bind("<Configure>", on_left_frame_configure)


    # Right: Canvas + Scrollbar for playlist songs
    right_canvas = tk.Canvas(right_container)
    right_scrollbar = tk.Scrollbar(right_container, orient="vertical", command=right_canvas.yview)
    right_canvas.config(yscrollcommand=right_scrollbar.set)

    right_canvas.grid(row=0, column=0, sticky="nsew")
    right_scrollbar.grid(row=0, column=1, sticky="ns")

    right_songs_frame = tk.Frame(right_canvas)
    right_canvas.create_window((0, 0), window=right_songs_frame, anchor="nw")

    def on_right_frame_configure(event):
        right_canvas.configure(scrollregion=right_canvas.bbox("all"))

    right_songs_frame.bind("<Configure>", on_right_frame_configure)


    edit_Mode["playlist_dictionary"] = load_playlists()

    def clear_right_songs():
        for widget in right_songs_frame.winfo_children():
            widget.destroy()

    def show_playlist_songs():
        clear_right_songs()
        songs = edit_Mode["edited_playlist"]
        if not songs:
            label = tk.Label(right_songs_frame, text="(No songs in this playlist)", fg="gray")
            label.pack(pady=10)
            return
        
        for i, (url, title) in enumerate(songs.items(), start=1):
            text = f"{i}. {title}"
            btn = tk.Button(right_songs_frame, text=text, anchor="w", padx=5, bg = "light steel blue")
            btn.config(command=lambda u=url, t=title, b=btn: on_song_button_click(u, t, b))
            btn.pack(fill="x", pady=1)
    
    def on_playlist_button_click(name, btn):

        title_entry.delete(0, tk.END)
        url_entry.delete(0, tk.END)

        if edit_Mode["playlist_name"] == name:
            edit_Mode["playlist_name"] = None
            edit_Mode["edited_playlist"] = {}
            edit_Mode["selected_song"] = None

            edit_Mode["title_label"].config(text="Playlist:")
            
            edit_Mode["current_playlist_button"].config(bg = "light steel blue")
            edit_Mode["current_playlist_button"] = None
            edit_Mode["prev_playlist_button"] = None
            edit_Mode["current_song_button"] = None
            edit_Mode["prev_song_button"] = None

            edit_Mode["update_btn"].config(text="Create Playlist")
            edit_Mode["add_remove_button"].config(text="Add New Song")
            edit_Mode["add_remove_button"].grid_forget()
            edit_Mode["url_label"].grid_forget()
            edit_Mode["url_entry"].grid_forget()

            clear_right_songs()

            return
        
        edit_Mode["playlist_name"] = name
        edit_Mode["edited_playlist"] = edit_Mode["playlist_dictionary"][name.lower()]
        edit_Mode["selected_song"] = None


        if edit_Mode["current_playlist_button"] == btn:
            return
        
        if edit_Mode["current_playlist_button"]:
            edit_Mode["prev_playlist_button"] = edit_Mode["current_playlist_button"]

        edit_Mode["current_playlist_button"] = btn

        edit_Mode["current_playlist_button"].config(bg = "slate blue")

        if edit_Mode["prev_playlist_button"]:
            edit_Mode["prev_playlist_button"].config(bg = "light steel blue")



        edit_Mode["current_song_button"] = None
        edit_Mode["prev_song_button"] = None

        edit_Mode["title_label"].config(text="Title:")
        edit_Mode["update_btn"].config(text="Update Info")
        edit_Mode["add_remove_button"].grid(row=1, column=2, rowspan=1, padx=10, pady=2, sticky="ns")
        edit_Mode["url_label"].grid(row=1, column=0, sticky="e", padx=5, pady=2)
        edit_Mode["url_entry"].grid(row=1, column=1, sticky="ew", padx=5, pady=2)


        show_playlist_songs()

    def on_song_button_click(url, title, btn):
        if edit_Mode["selected_song"] == {url : title}:
            edit_Mode["selected_song"] = None
            title_entry.delete(0, tk.END)
            url_entry.delete(0, tk.END)
            edit_Mode["current_song_button"].config(bg = "light steel blue")
            edit_Mode["current_song_button"] = None
            edit_Mode["prev_song_button"] = None
            edit_Mode["add_remove_button"].config(text="Add New Song")
            return
        
        
        edit_Mode["selected_song"] = {url : title}

        title_entry.delete(0, tk.END)
        title_entry.insert(0, title)
        url_entry.delete(0, tk.END)
        url_entry.insert(0, url)

        
        if edit_Mode["current_song_button"] == btn:
            return
        
        if edit_Mode["current_song_button"]:
            edit_Mode["prev_song_button"] = edit_Mode["current_song_button"]

        edit_Mode["current_song_button"] = btn

        edit_Mode["current_song_button"].config(bg = "slate blue")

        if edit_Mode["prev_song_button"]:
            edit_Mode["prev_song_button"].config(bg = "light steel blue")

        edit_Mode["add_remove_button"].config(text="Remove Song")
            
    def clear_left_playlists():
        for widget in left_buttons_frame.winfo_children():
            widget.destroy()

    def show_playlists():
        clear_left_playlists()
        playlists = edit_Mode["playlist_dictionary"]  # Your function to load playlists dict
        if not playlists:
            label = tk.Label(left_buttons_frame, text="(No playlists found)", fg="gray")
            label.pack(pady=10)
            return
        
        for i, playlist_name in enumerate(playlists.keys()):
            btn = tk.Button(left_buttons_frame, text=playlist_name, width=20, bg = "light steel blue")
            btn.grid(row=i, column=0, pady=1, padx=1, sticky="ew")
            btn.config(command=lambda n=playlist_name, b=btn: on_playlist_button_click(n, b))

    def update_selected_song():

        if not edit_Mode["edited_playlist"]:
            newName = edit_Mode["title_entry"].get()
            edit_Mode["playlist_dictionary"][newName.lower()] = {}
            show_playlists()

        if not edit_Mode["selected_song"]:
            return
        
        newTitle = title_entry.get()
        newURL = url_entry.get()

        edit_Mode["edited_playlist"].pop(next(iter(edit_Mode["selected_song"])))
        edit_Mode["edited_playlist"][newURL] = newTitle


        playlists = edit_Mode["playlist_dictionary"]
        playlists[edit_Mode["playlist_name"]] = edit_Mode["edited_playlist"]

        edit_Mode["current_song_button"] = None
        edit_Mode["prev_song_button"] = None

        show_playlist_songs()

    def modify_selected_song():


        newTitle = title_entry.get()
        newURL = url_entry.get()

        if edit_Mode["selected_song"]:
            edit_Mode["edited_playlist"].pop(next(iter(edit_Mode["selected_song"])))
            edit_Mode["current_song_button"] = None
        else:
            if newTitle == "":
                # Get the title of the video from the URL
                with YoutubeDL(YDL_OPTS) as ydl:
                    info = ydl.extract_info(newURL, download=False)
                    newTitle = info.get('title', None)
            edit_Mode["edited_playlist"][newURL] = newTitle


        title_entry.delete(0, tk.END)
        url_entry.delete(0, tk.END)

        playlists = edit_Mode["playlist_dictionary"]
        playlists[edit_Mode["playlist_name"]] = edit_Mode["edited_playlist"]

        edit_Mode["current_song_button"] = None
        edit_Mode["prev_song_button"] = None

        show_playlist_songs()

    def close_edit_mode():

        edit_Mode["playlist_name"] = None
        edit_Mode["edited_playlist"] = {}
        edit_Mode["selected_song"] = {}
        edit_Mode["current_song_button"] = None
        edit_Mode["prev_song_button"] = None
        edit_Mode["current_playlist_button"] = None
        edit_Mode["prev_playlist_button"] = None
        edit_Mode["add_remove_button"] = None
        edit_Mode["title_label"] = None
        edit_Mode["title_entry"] = None
        edit_Mode["url_label"] = None
        edit_Mode["url_entry"] = None
        edit_Mode["update_btn"] = None
        edit_Mode["playlist_dictionary"] = {}

        clear_playlist_buttons()
        popup.destroy()


    def save_changes():
        for i, name in enumerate(edit_Mode["playlist_dictionary"]):
            edited_Playlist = edit_Mode["playlist_dictionary"][name]

            if len(edited_Playlist) < 1:
                continue
            save_playlist(name, edited_Playlist)


    bottom_controls_frame = tk.Frame(popup)
    bottom_controls_frame.grid(row=2, column=0, columnspan=2, pady=10, sticky="ew")
    bottom_controls_frame.grid_columnconfigure(0, weight=1)
    bottom_controls_frame.grid_columnconfigure(1, weight=1)
    bottom_controls_frame.grid_columnconfigure(2, weight=0)
    bottom_controls_frame.grid_columnconfigure(3, weight=0)


    # Title Entry
    title_label = tk.Label(bottom_controls_frame, text="Playlist:")
    title_label.grid(row=0, column=0, sticky="e", padx=5, pady=2)
    title_entry = tk.Entry(bottom_controls_frame, width=40)
    title_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
    edit_Mode["title_label"] = title_label
    edit_Mode["title_entry"] = title_entry

    # URL Entry
    url_label = tk.Label(bottom_controls_frame, text="URL:")
    url_entry = tk.Entry(bottom_controls_frame, width=40)
    edit_Mode["url_label"] = url_label
    edit_Mode["url_entry"] = url_entry

    # Add/Remove Button
    add_remove_btn = tk.Button(bottom_controls_frame, text="Add Song", width=10, command=lambda: modify_selected_song())
    edit_Mode["add_remove_button"] = add_remove_btn

    # Update Button
    update_btn = tk.Button(bottom_controls_frame, text="Create Playlist", width=10, command= lambda: update_selected_song())
    update_btn.grid(row=0, column=2, rowspan=1, padx=10, pady=2, sticky="ns")
    edit_Mode["update_btn"] = update_btn

    # Save Button
    save_btn = tk.Button(bottom_controls_frame, text="Save", width=5, command= lambda: save_changes())
    save_btn.grid(row=0, column=3, rowspan=1, padx=10, pady=2, sticky="ns")

    # Cancel Button
    cancel_btn = tk.Button(bottom_controls_frame, text="Cancel", width=5, command=lambda: close_edit_mode())
    cancel_btn.grid(row=1, column=3, rowspan=1, padx=10, pady=2, sticky="ns")

    show_playlists()

def clear_playlist_buttons():
    for widget in playlists_frame.winfo_children():
        widget.destroy()

    create_playlist_buttons(playlists_frame)

def create_ambience_buttons(parent):
    ambience = load_ambience_dictionary()
    col = 0
    row = 1

    btn_width = 5
    btn_height = 1

    # Add the label at the top row 0
    label = tk.Label(parent, text="Ambience Selection", font=("Arial", 14, "bold"))
    label.grid(row=0, column=0, columnspan=6, pady=(0, 10))  # span all columns with some bottom padding
    label.config(bg="gray25", fg="white")

    max_per_row = 6

    for url in ambience:
        btn = tk.Button(
            parent,
            text = ambience[url],
            width = btn_width,
            height = btn_height,
            bg = "light steel blue"
        )
        btn.grid(row = row, column = col, padx = 5, pady = 5, sticky = "ew", columnspan=1)

        btn.config(command = partial(handle_ambience_click, url, ambience[url], btn))

        col += 1
        if col >= max_per_row:
            col = 0
            row += 1

def handle_ambience_click(url, name, button):
    ambience_Info["ambience_name"] = name
    ambience_Info["current_url"] = url

    if bot_Status["voice_client"] is None:
        # asyncio.run_coroutine_threadsafe(join_vc(bot, VOICE_ID), loop)
        print("Wasn't in a VC")
        return


    if bot_Status["is_ambience_playing"] is False:
        asyncio.run_coroutine_threadsafe(start_ambience(), loop)


    elif bot_Status["is_ambience_playing"] is True:
        audioMixer.stop_ambience()
        bot_Status["is_ambience_playing"] = False
        asyncio.run_coroutine_threadsafe(start_ambience(), loop)

async def open_ambience_popup():
    popup = tk.Toplevel(bg="gray25")
    popup.title("Edit Ambience Options")
    popup.geometry("800x600")
    popup.resizable(False, False)
    popup.grab_set()

    popup.grid_rowconfigure(0, weight=1)
    popup.grid_columnconfigure(0, weight=1)
    popup.grid_columnconfigure(1, weight=1)

    def close_edit_mode():
        edit_Mode["add_rmv_ambi_btn"] = None
        edit_Mode["previous_ambience_btn"] = None
        edit_Mode["selected_ambience_btn"] = None
        edit_Mode["ambiance_dictionary"] = {}
        edit_Mode["edited_ambience_list"] = {}
        edit_Mode["selected_ambience"] = {}

        clear_ambience_buttons()
        popup.destroy()

    def clear_edited_ambience():
        for widget in ambi_buttons_frame.winfo_children():
            widget.destroy()
    
    def show_ambience_options():

        clear_edited_ambience()
        if not edit_Mode["ambiance_dictionary"]:
            label = tk.Label(ambi_buttons_frame, text="(No ambience added yet)", fg="gray")
            label.pack(pady=10)
            return
        
        for i, (url, title) in enumerate(edit_Mode["ambiance_dictionary"].items()):
            text = f"{i}. {title}"
            btn = tk.Button(ambi_buttons_frame, text=text, anchor="w", padx=5, bg = "light steel blue")
            btn.config(command=lambda u=url, t=title, b=btn: on_ambi_button_click(u, t, b))
            btn.pack(fill="x", pady=1)

    def on_ambi_button_click(url, title, btn):

        if edit_Mode["selected_ambience"] == {url : title}:
            edit_Mode["selected_ambience"] = None
            title_entry.delete(0, tk.END)
            url_entry.delete(0, tk.END)
            edit_Mode["selected_ambience_btn"].config(bg = "light steel blue")
            edit_Mode["selected_ambience_btn"] = None
            edit_Mode["previous_ambience_btn"] = None
            edit_Mode["add_rmv_ambi_btn"].config(text="Add")
            edit_Mode["change_ambi_btn"].grid_forget()
            return
        
        edit_Mode["selected_ambience"] = {url : title}
        title_entry.delete(0, tk.END)
        title_entry.insert(0, title)
        url_entry.delete(0, tk.END)
        url_entry.insert(0, url)


        edit_Mode["change_ambi_btn"].grid(row=1, column=2, rowspan=1, padx=10, pady=2, sticky="ns")

        if edit_Mode["selected_ambience_btn"]:
            edit_Mode["previous_ambience_btn"] = edit_Mode["selected_ambience_btn"]

        edit_Mode["selected_ambience_btn"] = btn

        edit_Mode["selected_ambience_btn"].config(bg = "slate blue")

        if edit_Mode["previous_ambience_btn"]:
            edit_Mode["previous_ambience_btn"].config(bg = "light steel blue")

        edit_Mode["add_rmv_ambi_btn"].config(text="Remove")

    def modify_dictionary():

        newTitle = title_entry.get()
        newURL = url_entry.get()

        if edit_Mode["selected_ambience"]:
            edit_Mode["ambiance_dictionary"].pop(next(iter(edit_Mode["selected_ambience"])))
            edit_Mode["selected_ambience_btn"].config(bg = "light steel blue")
            edit_Mode["selected_ambience_btn"] = None
        else:
            if newTitle == "":
                # Get the title of the video from the URL
                with YoutubeDL(YDL_OPTS) as ydl:
                    info = ydl.extract_info(newURL, download=False)
                    newTitle = info.get('title', None)
            edit_Mode["ambiance_dictionary"][newURL] = newTitle


        title_entry.delete(0, tk.END)
        url_entry.delete(0, tk.END)

        edit_Mode["selected_ambience"] = None
        edit_Mode["selected_ambience_btn"] = None
        edit_Mode["previous_ambience_btn"] = None
        edit_Mode["add_rmv_ambi_btn"].config(text="Add")

        edit_Mode["selected_ambience_btn"] = None
        edit_Mode["previous_ambience_btn"] = None

        show_ambience_options()

    def change_selection():

        if not edit_Mode["selected_ambience"]:
            return
        
        newTitle = title_entry.get()
        newURL = url_entry.get()

        edit_Mode["ambiance_dictionary"].pop(next(iter(edit_Mode["selected_ambience"])))
        edit_Mode["ambiance_dictionary"][newURL] = newTitle



        title_entry.delete(0, tk.END)
        url_entry.delete(0, tk.END)

        edit_Mode["selected_ambience"] = None
        edit_Mode["selected_ambience_btn"] = None
        edit_Mode["previous_ambience_btn"] = None
        edit_Mode["add_rmv_ambi_btn"].config(text="Add")

        edit_Mode["selected_ambience_btn"] = None
        edit_Mode["previous_ambience_btn"] = None

        show_ambience_options()


    def save_ambience_changes():
        save_ambience_dictionary(edit_Mode["ambiance_dictionary"])


    edit_Mode["ambiance_dictionary"] = load_ambience_dictionary()

    ambi_container = tk.Frame(popup, bd=2, relief="sunken")
    ambi_container.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
    
    
    ambi_container.grid_rowconfigure(0, weight=1)
    ambi_container.grid_columnconfigure(0, weight=1)


    ambi_canvas = tk.Canvas(ambi_container)
    ambi_scrollbar = tk.Scrollbar(ambi_container, orient="vertical", command=ambi_canvas.yview)
    ambi_canvas.config(yscrollcommand=ambi_scrollbar.set)

    ambi_canvas.grid(row=0, column=0, sticky="nsew")
    ambi_scrollbar.grid(row=0, column=1, sticky="ns")

    ambi_buttons_frame = tk.Frame(ambi_canvas)
    ambi_canvas.create_window((0, 0), window=ambi_buttons_frame, anchor="nw")

    def on_ambi_frame_configure(event):
        ambi_canvas.configure(scrollregion=ambi_canvas.bbox("all"))

    ambi_buttons_frame.bind("<Configure>", on_ambi_frame_configure)

    

    bottom_controls_frame = tk.Frame(popup)
    bottom_controls_frame.grid(row=2, column=0, columnspan=4, pady=10, sticky="ew")
    bottom_controls_frame.grid_columnconfigure(0, weight=1)
    bottom_controls_frame.grid_columnconfigure(1, weight=1)
    bottom_controls_frame.grid_columnconfigure(2, weight=0)
    bottom_controls_frame.grid_columnconfigure(3, weight=0)

    # Title Entry
    title_label = tk.Label(bottom_controls_frame, text="Name:")
    title_label.grid(row=0, column=0, sticky="e", padx=5, pady=2)
    title_entry = tk.Entry(bottom_controls_frame, width=40)
    title_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

    # URL Entry
    url_label = tk.Label(bottom_controls_frame, text="URL:")
    url_label.grid(row=1, column=0, sticky="e", padx=5, pady=2)
    url_entry = tk.Entry(bottom_controls_frame, width=40)
    url_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

    # Update Button
    update_btn = tk.Button(bottom_controls_frame, text="Add Ambience", width=10, command=lambda: modify_dictionary())
    update_btn.grid(row=0, column=2, rowspan=1, padx=10, pady=2, sticky="ns")
    edit_Mode["add_rmv_ambi_btn"] = update_btn

    # Change Button
    change_btn = tk.Button(bottom_controls_frame, text="Change Info", width=10, command=lambda: change_selection())
    edit_Mode["change_ambi_btn"] = change_btn

    # Save Button
    save_btn = tk.Button(bottom_controls_frame, text="Save", width=5, command=lambda: save_ambience_changes())
    save_btn.grid(row=0, column=3, rowspan=1, padx=10, pady=2, sticky="ns")

    # Cancel Button
    cancel_btn = tk.Button(bottom_controls_frame, text="Cancel", width=5, command=lambda: close_edit_mode())
    cancel_btn.grid(row=1, column=3, rowspan=1, padx=10, pady=2, sticky="ns")

    show_ambience_options()

def clear_ambience_buttons():
    for widget in ambience_frame.winfo_children():
        widget.destroy()

    create_ambience_buttons(ambience_frame)


#endregion









# Run bot and GUI in separate threads
def run_bot():
    loop.create_task(bot.start(TOKEN))
    loop.run_forever()

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")

if __name__ == "__main__":
    threading.Thread(target=start_gui, daemon=True).start()
    run_bot()