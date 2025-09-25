import subprocess
import numpy as np
import discord
import os

class MixedAudio():
    def __init__(self):
        self.chunk_size = 960 * 4  # 3840 bytes for 16-bit stereo 48kHz
        self.proc_amb = None
        self.proc_music = None
        self.music_volume = 1.0
        self.ambience_volume = 0.25
        self.music_paused = False
        self.ambience_paused = False

    def set_music_volume(self, volume: float):
        self.music_volume = max(0.0, min(volume, 1.0))

    def set_ambience_volume(self, volume: float):
        self.ambience_volume = max(0.0, min(volume, 1.0))

    def _start_ffmpeg(self, url, loop=False):
        cmd = [
            "ffmpeg",
            "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5"
        ]
        if loop:
            cmd += ["-stream_loop", "-1"]
        cmd += [
            "-i", url,
            "-f", "s16le",
            "-ar", "48000",
            "-ac", "2",
            "pipe:1",
            "-loglevel", "quiet"
        ]
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, preexec_fn=os.setsid)

    # ===== Control Methods =====
    def start_ambience(self, url, loop=True):
        self.stop_ambience()  # Prevent multiple
        self.proc_amb = self._start_ffmpeg(url, loop=loop)

    def pause_ambience(self):
        if self.proc_amb and self.proc_amb.poll() is None:
            self.ambience_paused = True

    def resume_ambience(self):
        if self.proc_amb and self.proc_amb.poll() is None:
            self.ambience_paused = False

    def stop_ambience(self):
        if self.proc_amb:
            self.proc_amb.kill()
            self.proc_amb = None

    def start_music(self, url, loop=False):
        self.stop_music()
        self.proc_music = self._start_ffmpeg(url, loop=loop)

    def pause_music(self):
        if self.proc_music and self.proc_music.poll() is None:
            self.music_paused = True

    def resume_music(self):
        if self.proc_music and self.proc_music.poll() is None:
            self.music_paused = False

    def stop_music(self):
        if self.proc_music:
            self.proc_music.kill()
            self.proc_music = None

    # ===== Mixing =====
    def read(self):

        # Read chunks or produce silence if paused
        if self.proc_amb and not self.ambience_paused:
            amb_chunk = self.proc_amb.stdout.read(self.chunk_size)
        else:
            amb_chunk = b'\x00' * self.chunk_size

        if self.proc_music and not self.music_paused:
            music_chunk = self.proc_music.stdout.read(self.chunk_size)
        else:
            music_chunk = b'\x00' * self.chunk_size


        # pad missing chunks with silence
        if len(amb_chunk) < self.chunk_size:
            amb_chunk += b'\x00' * (self.chunk_size - len(amb_chunk))
        if len(music_chunk) < self.chunk_size:
            music_chunk += b'\x00' * (self.chunk_size - len(music_chunk))

        amb_np = np.frombuffer(amb_chunk, dtype=np.int16).astype(np.float32) * self.ambience_volume
        music_np = np.frombuffer(music_chunk, dtype=np.int16).astype(np.float32) * self.music_volume

        mixed = np.clip(amb_np + music_np, -32768, 32767).astype(np.int16)
        return mixed.tobytes()
    

class MixedAudioSource(discord.AudioSource):
    def __init__(self, mixer: MixedAudio):
        self.mixer = mixer

    def read(self):
        return self.mixer.read()

    def is_opus(self):
        return False  # We’re providing raw PCM