import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import ctypes.util
import functools
import sys
import traceback
import yt_dlp

from common import loadData, saveData, etanid, moderatorplusplusroleid, formatUsername


def _load_opus():
    # On Windows, discord.py ships and auto-loads its own bundled libopus-0.x64/x86.dll
    # the first time an Encoder is built (see discord/opus.py's _load_default()) - nothing
    # to do here, and none of the POSIX paths below would apply anyway.
    if sys.platform == "win32":
        return
    if discord.opus.is_loaded():
        return
    candidates = [
        ctypes.util.find_library("opus"),
        "/opt/homebrew/lib/libopus.dylib",
        "/opt/homebrew/lib/libopus.0.dylib",
        "/usr/local/lib/libopus.dylib",
        "/usr/local/lib/libopus.0.dylib",
        "libopus.so.0",
        "libopus.so.1",
        "opus",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            discord.opus.load_opus(candidate)
            if discord.opus.is_loaded():
                return
        except OSError:
            continue
    print("Warning: could not load libopus - voice playback will fail. Install it (e.g. `brew install opus` on macOS, `apt install libopus0` on Linux).")


_load_opus()

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "default_search": "ytsearch",
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
}

FFMPEG_BEFORE_OPTS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTS = "-vn"

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


class QueueItem:
    def __init__(self, requester_id: int, title: str, stream_url: str, webpage_url: str, duration: int):
        self.requester_id = requester_id
        self.title = title
        self.stream_url = stream_url
        self.webpage_url = webpage_url
        self.duration = duration


class ChannelState:
    def __init__(self):
        self.voice_client: discord.VoiceClient | None = None
        self.queue: list[QueueItem] = []
        self.current: QueueItem | None = None
        self.vote_skips: set[int] = set()
        self.lock = asyncio.Lock()


def _is_dj(user_id: int) -> bool:
    if user_id == etanid:
        return True
    djlist = loadData("djs")
    if djlist == "":
        return False
    return user_id in djlist


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channels: dict[int, ChannelState] = {}

    def _get_state(self, channel_id: int) -> ChannelState:
        return self.channels.setdefault(channel_id, ChannelState())

    def _has_queue_slot_taken(self, state: ChannelState, user_id: int) -> bool:
        if state.current is not None and state.current.requester_id == user_id:
            return True
        return any(item.requester_id == user_id for item in state.queue)

    async def _start_next(self, channel_id: int):
        # must only be called while holding state.lock for this channel
        state = self.channels.get(channel_id)
        if state is None:
            return
        if not state.queue:
            state.current = None
            return
        item = state.queue.pop(0)
        state.current = item
        state.vote_skips.clear()
        source = discord.FFmpegPCMAudio(item.stream_url, before_options=FFMPEG_BEFORE_OPTS, options=FFMPEG_OPTS)

        def _after(error, channel_id=channel_id):
            if error:
                print(f"Playback error in channel {channel_id}: {error}")
            asyncio.run_coroutine_threadsafe(self._advance(channel_id), self.bot.loop)

        state.voice_client.play(source, after=_after)

    async def _advance(self, channel_id: int):
        state = self.channels.get(channel_id)
        if state is None:
            return
        async with state.lock:
            await self._start_next(channel_id)

    async def _disconnect_and_clear(self, state: ChannelState):
        # must only be called while holding state.lock
        if state.voice_client is not None:
            try:
                await state.voice_client.disconnect(force=True)
            except Exception:
                traceback.print_exc()
            state.voice_client = None
        state.queue = []
        state.current = None
        state.vote_skips.clear()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        channel = before.channel
        if channel is None or before.channel == after.channel:
            return
        state = self.channels.get(channel.id)
        if state is None or state.voice_client is None:
            return
        if any(not m.bot for m in channel.members):
            return
        async with state.lock:
            if state.voice_client is None or any(not m.bot for m in channel.members):
                return
            await self._disconnect_and_clear(state)

    @app_commands.command(name="play", description="Add a song to the queue in your current voice channel.")
    @app_commands.describe(query="A YouTube URL or search term.")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(ephemeral=True)
        try:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.edit_original_response(content="You need to be in a voice channel to use this command!")
                return
            if not _is_dj(interaction.user.id):
                await interaction.edit_original_response(content="You don't have permission to use this command!")
                return

            channel = interaction.user.voice.channel
            state = self._get_state(channel.id)

            async with state.lock:
                if self._has_queue_slot_taken(state, interaction.user.id):
                    await interaction.edit_original_response(content="You already have a song queued or playing in this channel! Wait for it to finish or get skipped.")
                    return

                if state.voice_client is None or not state.voice_client.is_connected():
                    state.voice_client = await channel.connect()

                loop = asyncio.get_running_loop()
                extractor = functools.partial(ytdl.extract_info, query, download=False)
                try:
                    info = await loop.run_in_executor(None, extractor)
                except Exception:
                    traceback.print_exc()
                    await interaction.edit_original_response(content="Couldn't find or load that video. Try a different search or URL.")
                    return

                if info is None:
                    await interaction.edit_original_response(content="Couldn't find or load that video. Try a different search or URL.")
                    return
                if "entries" in info:
                    entries = info.get("entries") or []
                    if not entries:
                        await interaction.edit_original_response(content="No results found for that search.")
                        return
                    info = entries[0]

                item = QueueItem(
                    requester_id=interaction.user.id,
                    title=info.get("title", "Unknown title"),
                    stream_url=info["url"],
                    webpage_url=info.get("webpage_url", query),
                    duration=info.get("duration", 0),
                )
                state.queue.append(item)

                if state.current is None:
                    await self._start_next(channel.id)
                    await interaction.edit_original_response(content=f"Now playing: **{item.title}**")
                else:
                    await interaction.edit_original_response(content=f"Added **{item.title}** to the queue (position {len(state.queue)}).")
        except Exception as e:
            traceback.print_exc()
            await interaction.edit_original_response(content=f"An error occurred: {e}")

    @app_commands.command(name="skip", description="Force skip the current song in your voice channel (poweruser/mods++ only).")
    async def skip(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.edit_original_response(content="You need to be in a voice channel to use this command!")
                return
            if interaction.user.id != etanid and moderatorplusplusroleid not in [role.id for role in interaction.user.roles]:
                await interaction.edit_original_response(content="You don't have permission to use this command!")
                return

            channel = interaction.user.voice.channel
            state = self.channels.get(channel.id)
            if state is None or state.current is None:
                await interaction.edit_original_response(content="Nothing is playing in this channel.")
                return

            async with state.lock:
                if state.current is None:
                    await interaction.edit_original_response(content="Nothing is playing in this channel.")
                    return
                title = state.current.title
                state.voice_client.stop()
            await interaction.edit_original_response(content=f"Skipped **{title}**.")
        except Exception as e:
            traceback.print_exc()
            await interaction.edit_original_response(content=f"An error occurred: {e}")

    @app_commands.command(name="voteskip", description="Vote to skip the current song (3 votes needed).")
    async def voteskip(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.edit_original_response(content="You need to be in a voice channel to use this command!")
                return

            channel = interaction.user.voice.channel
            state = self.channels.get(channel.id)
            if state is None or state.current is None:
                await interaction.edit_original_response(content="Nothing is playing in this channel to vote to skip.")
                return

            async with state.lock:
                if state.current is None:
                    await interaction.edit_original_response(content="Nothing is playing in this channel to vote to skip.")
                    return
                if interaction.user.id in state.vote_skips:
                    await interaction.edit_original_response(content="You've already voted to skip this song.")
                    return
                state.vote_skips.add(interaction.user.id)
                if len(state.vote_skips) >= 3:
                    title = state.current.title
                    state.voice_client.stop()
                    await interaction.edit_original_response(content=f"Vote to skip passed! Skipped **{title}**.")
                else:
                    await interaction.edit_original_response(content=f"Vote to skip registered ({len(state.vote_skips)}/3).")
        except Exception as e:
            traceback.print_exc()
            await interaction.edit_original_response(content=f"An error occurred: {e}")

    @app_commands.command(name="queue", description="View the song queue for your current voice channel.")
    async def queue(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.edit_original_response(content="You need to be in a voice channel to use this command!")
                return

            channel = interaction.user.voice.channel
            state = self.channels.get(channel.id)
            if state is None or (state.current is None and not state.queue):
                await interaction.edit_original_response(content="The queue is empty in this channel.")
                return

            embed = discord.Embed(title=f"Queue — {channel.name}", color=discord.Color.blurple())
            if state.current is not None:
                requester = self.bot.get_user(state.current.requester_id)
                embed.add_field(name="Now Playing", value=f"{state.current.title} (requested by {formatUsername(requester) if requester else state.current.requester_id})", inline=False)
            else:
                embed.add_field(name="Now Playing", value="Nothing playing", inline=False)

            if state.queue:
                lines = []
                for i, item in enumerate(state.queue[:10], start=1):
                    requester = self.bot.get_user(item.requester_id)
                    lines.append(f"{i}. {item.title} (requested by {formatUsername(requester) if requester else item.requester_id})")
                if len(state.queue) > 10:
                    lines.append(f"+{len(state.queue) - 10} more")
                embed.add_field(name="Up Next", value="\n".join(lines), inline=False)
            else:
                embed.add_field(name="Up Next", value="Nothing queued", inline=False)

            await interaction.edit_original_response(content=None, embed=embed)
        except Exception as e:
            traceback.print_exc()
            await interaction.edit_original_response(content=f"An error occurred: {e}")

    @app_commands.command(name="leave", description="Disconnect the bot from your voice channel and clear its queue.")
    async def leave(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.edit_original_response(content="You need to be in a voice channel to use this command!")
                return
            if interaction.user.id != etanid:
                await interaction.edit_original_response(content="You don't have permission to use this command!")
                return

            channel = interaction.user.voice.channel
            state = self.channels.get(channel.id)
            if state is None or state.voice_client is None:
                await interaction.edit_original_response(content="The bot isn't active in this channel.")
                return

            async with state.lock:
                await self._disconnect_and_clear(state)

            await interaction.edit_original_response(content="Left the voice channel and cleared the queue.")
        except Exception as e:
            traceback.print_exc()
            await interaction.edit_original_response(content=f"An error occurred: {e}")

    @app_commands.command(name="dj-add", description="Add a user to the DJ allowlist (poweruser only).")
    @app_commands.describe(user="The user to add as a DJ.")
    async def dj_add(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer(ephemeral=True)
        try:
            if interaction.user.id != etanid:
                await interaction.edit_original_response(content="You don't have permission to use this command!")
                return

            djlist = loadData("djs")
            if djlist == "":
                await interaction.edit_original_response(content="Error loading DJ data.")
                return
            if user.id in djlist:
                await interaction.edit_original_response(content=f"{formatUsername(user)} is already a DJ.")
                return
            djlist.append(user.id)
            saveData("djs", djlist)
            await interaction.edit_original_response(content=f"Added {formatUsername(user)} as a DJ.")
        except Exception as e:
            traceback.print_exc()
            await interaction.edit_original_response(content=f"An error occurred: {e}")

    @app_commands.command(name="dj-remove", description="Remove a user from the DJ allowlist (poweruser only).")
    @app_commands.describe(user="The user to remove from the DJs.")
    async def dj_remove(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer(ephemeral=True)
        try:
            if interaction.user.id != etanid:
                await interaction.edit_original_response(content="You don't have permission to use this command!")
                return

            djlist = loadData("djs")
            if djlist == "":
                await interaction.edit_original_response(content="Error loading DJ data.")
                return
            if user.id not in djlist:
                await interaction.edit_original_response(content=f"{formatUsername(user)} isn't a DJ.")
                return
            djlist.remove(user.id)
            saveData("djs", djlist)
            await interaction.edit_original_response(content=f"Removed {formatUsername(user)} from the DJs.")
        except Exception as e:
            traceback.print_exc()
            await interaction.edit_original_response(content=f"An error occurred: {e}")

    @app_commands.command(name="dj-list", description="List all users on the DJ allowlist (poweruser only).")
    async def dj_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if interaction.user.id != etanid:
                await interaction.edit_original_response(content="You don't have permission to use this command!")
                return

            djlist = loadData("djs")
            if djlist == "":
                await interaction.edit_original_response(content="Error loading DJ data.")
                return
            if not djlist:
                await interaction.edit_original_response(content="No DJs are currently configured.")
                return
            await interaction.edit_original_response(content="\n".join(f"<@{uid}>" for uid in djlist))
        except Exception as e:
            traceback.print_exc()
            await interaction.edit_original_response(content=f"An error occurred: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
