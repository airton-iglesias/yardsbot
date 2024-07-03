import asyncio, discord, voicelink, re

from io import StringIO
from discord import app_commands
from discord.ext import commands
from function import (
    settings,
    send,
    time as ctime,
    formatTime,
    get_source,
    get_user,
    get_lang,
    truncate_string,
    cooldown_check,
    get_aliases
)

from views import SearchView, ListView, LinkView, HelpView
from validators import url

searchPlatform = {
    "spotify": "spsearch",
    "youtube": "ytsearch",
    "youtubemusic": "ytmsearch"
}


async def nowplay(ctx: commands.Context, player: voicelink.Player):
    track = player.current
    if not track:
        return await send(ctx, 'noTrackPlaying', ephemeral=True)

    texts = await get_lang(ctx.guild.id, "nowplayingDesc", "nowplayingField", "nowplayingLink")
    upnext = "\n".join(f"`{index}.` `[{track.formatted_length}]` [{truncate_string(track.title)}]({track.uri})" for index, track in enumerate(player.queue.tracks()[:2], start=2))

    embed = discord.Embed(description=texts[0].format(track.title), color=settings.embed_color)
    embed.set_author(
        name=track.requester.display_name,
        icon_url=track.requester.display_avatar.url
    )
    embed.set_thumbnail(url=track.thumbnail)

    if upnext:
        embed.add_field(name=texts[1], value=upnext)

    pbar = "".join(":radio_button:" if i == round(player.position // round(track.length // 15)) else "▬" for i in range(15))
    icon = ":red_circle:" if track.is_stream else (":pause_button:" if player.is_paused else ":arrow_forward:")
    embed.add_field(name="\u2800", value=f"{icon} {pbar} **[{ctime(player.position)}/{track.formatted_length}]**", inline=False)

    return await ctx.send(embed=embed, view=LinkView(texts[2].format(track.source), track.emoji, track.uri))

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.description = "This category is available to anyone on this server. Voting is required in certain commands."

    @commands.hybrid_group(
        name="music",
        aliases=get_aliases("music"),
        invoke_without_command=True
    )
    async def music(self, ctx: commands.Context):
        view = HelpView(self.bot, ctx.author)
        embed = view.build_embed(self.qualified_name)
        view.response = await ctx.send(embed=embed, view=view)

        await ctx.send("Invalid command, these are the commands for the music category.")

    async def play_autocomplete(self, interaction: discord.Interaction, current: str) -> list:
        if voicelink.pool.URL_REGEX.match(current): return

        history: dict[str, str] = {}
        for track_id in reversed(await get_user(interaction.user.id, "history")):
            track_dict = voicelink.decode(track_id)
            history[track_dict["identifier"]] = track_dict

        history_tracks = [app_commands.Choice(name=truncate_string(f"🕒 {track['author']} - {track['title']}", 100), value=track['uri']) for track in history.values()][:25]
        if not current:
            return history_tracks

        node = voicelink.NodePool.get_node()
        if node and node.spotify_client:
            tracks: list[voicelink.Track] = await node.spotifySearch(current, requester=interaction.user)
            return  history_tracks[:5] + [app_commands.Choice(name=f"🎵 {track.author} - {track.title}", value=f"{track.author} - {track.title}") for track in tracks]

    @music.command(name="connect", aliases=get_aliases("connect"))
    @app_commands.describe(channel="Provide a channel to connect.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def connect(self, ctx: commands.Context, channel: discord.VoiceChannel = None) -> None:
        "Connect to a voice channel."
        try:
            player = await voicelink.connect_channel(ctx, channel)
        except discord.errors.ClientException:
            return await send(ctx, "alreadyConnected")

        await send(ctx, 'connect', player.channel)

    @music.command(name="play", aliases=get_aliases("play"))
    @app_commands.describe(query="Input a query or a searchable link.")
    @app_commands.autocomplete(query=play_autocomplete)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        "Loads your input and added it to the queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            player = await voicelink.connect_channel(ctx)

        if not player.is_user_join(ctx.author):
            return await send(ctx, "notInChannel", ctx.author.mention, player.channel.mention, ephemeral=True)

        tracks = await player.get_tracks(query, requester=ctx.author)
        if not tracks:
            return await send(ctx, "noTrackFound")

        try:
            if isinstance(tracks, voicelink.Playlist):
                index = await player.add_track(tracks.tracks)
                music_add_message = await send(ctx, "playlistLoad", tracks.name, index)
                await asyncio.sleep(5)
                await music_add_message.delete()
            else:
                position = await player.add_track(tracks[0])
                texts = await get_lang(ctx.guild.id, "live", "trackLoad_pos", "trackLoad")
                await ctx.send((f"`{texts[0]}`" if tracks[0].is_stream else "") + (texts[1].format(tracks[0].title, tracks[0].uri, tracks[0].author, tracks[0].formatted_length, position) if position >= 1 and player.is_playing else texts[2].format(tracks[0].title, tracks[0].uri, tracks[0].author, tracks[0].formatted_length)), allowed_mentions=False)

        except voicelink.QueueFull as e:
            await ctx.send(e)
        finally:
            if not player.is_playing:
                await player.do_next()

    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def _play(self, interaction: discord.Interaction, message: discord.Message):
        query = ""

        if message.content:
            url = re.findall(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", message.content)
            if url:
                query = url[0]

        elif message.attachments:
            query = message.attachments[0].url

        if not query:
            return await send(interaction, "noPlaySource", ephemeral=True)

        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            player = await voicelink.connect_channel(interaction)

        if not player.is_user_join(interaction.user):
            return await send(interaction, "notInChannel", interaction.user.mention, player.channel.mention, ephemeral=True)

        tracks = await player.get_tracks(query, requester=interaction.user)
        if not tracks:
            return await send(interaction, "noTrackFound")

        try:
            if isinstance(tracks, voicelink.Playlist):
                index = await player.add_track(tracks.tracks)
                await send(interaction, "playlistLoad", tracks.name, index)
            else:
                position = await player.add_track(tracks[0])
                texts = await get_lang(interaction.guild.id, "live", "trackLoad_pos", "trackLoad")
                await interaction.response.send_message((f"`{texts[0]}`" if tracks[0].is_stream else "") + (texts[1].format(tracks[0].title, tracks[0].uri, tracks[0].author, tracks[0].formatted_length, position) if position >= 1 and player.is_playing else texts[2].format(tracks[0].title, tracks[0].uri, tracks[0].author, tracks[0].formatted_length)), allowed_mentions=False)
        except voicelink.QueueFull as e:
            await interaction.response.send_message(e)

        except Exception as e:
            return await interaction.response.send_message(e, ephemeral=True)

        finally:
            if not player.is_playing:
                await player.do_next()

    @music.command(name="search", aliases=get_aliases("search"))
    @app_commands.describe(
        query="Input the name of the song.",
        platform="Select the platform you want to search."
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="Spotify", value="Spotify"),
        app_commands.Choice(name="Youtube", value="Youtube"),
        app_commands.Choice(name="Youtube Music", value="YoutubeMusic"),
    ])
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def search(self, ctx: commands.Context, *, query: str, platform: str = "Youtube"):
        "Loads your input and added it to the queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            player = await voicelink.connect_channel(ctx)

        if not player.is_user_join(ctx.author):
            return await send(ctx, "notInChannel", ctx.author.mention, player.channel.mention, ephemeral=True)

        if url(query):
            return await send(ctx, "noLinkSupport", ephemeral=True)

        platform = platform.lower()
        if platform != 'spotify':
            query_platform = searchPlatform.get(platform, 'ytsearch') + f":{query}"
            tracks = await player.get_tracks(query=query_platform, requester=ctx.author)
        else:
            tracks = await player.node.spotifySearch(query=query, requester=ctx.author)

        if not tracks:
            return await send(ctx, "noTrackFound")

        texts = await get_lang(ctx.guild.id, "searchTitle", "searchDesc", "live", "trackLoad_pos", "trackLoad", "searchWait", "searchSuccess")
        query_track = "\n".join(f"`{index}.` `[{track.formatted_length}]` **{track.title[:35]}**" for index, track in enumerate(tracks[0:10], start=1))
        embed = discord.Embed(title=texts[0].format(query), description=texts[1].format(get_source(platform, "emoji"), platform, len(tracks[0:10]), query_track), color=settings.embed_color)
        view = SearchView(tracks=tracks[0:10], texts=[texts[5], texts[6]])
        view.response = await ctx.send(embed=embed, view=view, ephemeral=True)

        await view.wait()
        if view.values is not None:
            msg = ""
            for value in view.values:
                track = tracks[int(value.split(". ")[0]) - 1]
                position = await player.add_track(track)
                msg += (f"`{texts[2]}`" if track.is_stream else "") + (texts[3].format(track.title, track.uri, track.author, track.formatted_length, position) if position >= 1 else texts[4].format(track.title, track.uri, track.author, track.formatted_length))
            await ctx.send(msg, allowed_mentions=False)

            if not player.is_playing:
                await player.do_next()

    @music.command(name="playtop", aliases=get_aliases("playtop"))
    @app_commands.describe(query="Input a query or a searchable link.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def playtop(self, ctx: commands.Context, *, query: str):
        "Adds a song with the given url or query on the top of the queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            player = await voicelink.connect_channel(ctx)

        if not player.is_user_join(ctx.author):
            return await send(ctx, "notInChannel", ctx.author.mention, player.channel.mention, ephemeral=True)

        tracks = await player.get_tracks(query, requester=ctx.author)
        if not tracks:
            return await send(ctx, "noTrackFound")

        try:
            if isinstance(tracks, voicelink.Playlist):
                index = await player.add_track(tracks.tracks, at_font=True)
                play_song_top_message = await send(ctx, "playlistLoad", tracks.name, index)
                await asyncio.sleep(5)
                await play_song_top_message.delete()
            else:
                position = await player.add_track(tracks[0], at_font=True)
                texts = await get_lang(ctx.guild.id, "live", "trackLoad_pos", "trackLoad")
                play_song_top_message = await ctx.send((f"`{texts[0]}`" if tracks[0].is_stream else "") + (texts[1].format(tracks[0].title, tracks[0].uri, tracks[0].author, tracks[0].formatted_length, position) if position >= 1 and player.is_playing else texts[2].format(tracks[0].title, tracks[0].uri, tracks[0].author, tracks[0].formatted_length)), allowed_mentions=False)
                await asyncio.sleep(5)
                await play_song_top_message.delete()

        except voicelink.QueueFull as e:
            await ctx.send(e)

        finally:
            if not player.is_playing:
                await player.do_next()

    @music.command(name="forceplay", aliases=get_aliases("forceplay"))
    @app_commands.describe(query="Input a query or a searchable link.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def forceplay(self, ctx: commands.Context, query: str):
        "Enforce playback using the given URL or query."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            player = await voicelink.connect_channel(ctx)

        if not player.is_privileged(ctx.author):
            return await send(ctx, "missingPerms_function", ephemeral=True)

        tracks = await player.get_tracks(query, requester=ctx.author)
        if not tracks:
            return await send(ctx, "noTrackFound")

        try:
            if isinstance(tracks, voicelink.Playlist):
                index = await player.add_track(tracks.tracks, at_font=True)
                song_force_message = await send(ctx, "playlistLoad", tracks.name, index)
                await asyncio.sleep(5)
                await song_force_message.delete()

            else:
                texts = await get_lang(ctx.guild.id, "live", "trackLoad")
                await player.add_track(tracks[0], at_font=True)
                song_force_message = await ctx.send((f"`{texts[0]}`" if tracks[0].is_stream else "") + texts[1].format(tracks[0].title, tracks[0].uri, tracks[0].author, tracks[0].formatted_length), allowed_mentions=False)
                await asyncio.sleep(5)
                await song_force_message.delete()
        except voicelink.QueueFull as e:
            await ctx.send(e)

        finally:
            if player.queue._repeat.mode == voicelink.LoopType.track:
                await player.set_repeat(voicelink.LoopType.off.name)

            await player.stop() if player.is_playing else await player.do_next()

    @music.command(name="pause", aliases=get_aliases("pause"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def pause(self, ctx: commands.Context):
        "Pause the music."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if player.is_paused:
            return await send(ctx, "pauseError", ephemeral=True)

        if not player.is_privileged(ctx.author):
            if ctx.author in player.pause_votes:
                return await send(ctx, "voted", ephemeral=True)
            else:
                player.pause_votes.add(ctx.author)
                if len(player.pause_votes) >= (required := player.required()):
                    pass
                else:
                    return await send(ctx, "pauseVote", ctx.author, len(player.pause_votes), required)

        await player.set_pause(True, ctx.author)
        player.pause_votes.clear()
        song_pause = await send(ctx, "paused", ctx.author)
        await asyncio.sleep(5)
        await song_pause.delete()

    @music.command(name="resume", aliases=get_aliases("resume"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def resume(self, ctx: commands.Context):
        "Resume the music."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_paused:
            return await send(ctx, "resumeError")

        if not player.is_privileged(ctx.author):
            if ctx.author in player.resume_votes:
                return await send(ctx, "voted", ephemeral=True)
            else:
                player.resume_votes.add(ctx.author)
                if len(player.resume_votes) >= (required := player.required()):
                    pass
                else:
                    return await send(ctx, "resumeVote", ctx.author, len(player.resume_votes), required)

        await player.set_pause(False, ctx.author)
        player.resume_votes.clear()
        resumed_song_message = await send(ctx, "resumed", ctx.author)
        await asyncio.sleep(5)
        await resumed_song_message.delete()

    @music.command(name="skip", aliases=get_aliases("skip"))
    @app_commands.describe(index="Enter a index that you want to skip to.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def skip(self, ctx: commands.Context, index: int = 0):
        "Skips to the next song or skips to the specified song."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_playing:
            return await send(ctx, "skipError", ephemeral=True)

        if not player.is_privileged(ctx.author):
            if ctx.author == player.current.requester:
                pass
            elif ctx.author in player.skip_votes:
                return await send(ctx, "voted", ephemeral=True)
            else:
                player.skip_votes.add(ctx.author)
                if len(player.skip_votes) >= (required := player.required()):
                    pass
                else:
                    return await send(ctx, "skipVote", ctx.author, len(player.skip_votes), required)

        if not player.node._available:
            return await send(ctx, "nodeReconnect")

        if index:
            player.queue.skipto(index)

        song_skipped_message = await send(ctx, "skipped", ctx.author)
        await asyncio.sleep(5)
        await song_skipped_message.delete()

        if player.queue._repeat.mode == voicelink.LoopType.track:
            await player.set_repeat(voicelink.LoopType.off.name)

        await player.stop()

    @music.command(name="back", aliases=get_aliases("back"))
    @app_commands.describe(index="Enter a index that you want to skip back to.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def back(self, ctx: commands.Context, index: int = 1):
        "Skips back to the previous song or skips to the specified previous song."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_privileged(ctx.author):
            if ctx.author in player.previous_votes:
                return await send(ctx, "voted", ephemeral=True)
            else:
                player.previous_votes.add(ctx.author)
                if len(player.previous_votes) >= (required := player.required()):
                    pass
                else:
                    return await send(ctx, "backVote", ctx.author, len(player.previous_votes), required)

        if not player.node._available:
            return await send(ctx, "nnodeReconnectode")

        if not player.is_playing:
            player.queue.backto(index)
            await player.do_next()
        else:
            player.queue.backto(index + 1)
            await player.stop()

        song_backed_message = await send(ctx, "backed", ctx.author)
        await asyncio.sleep(5)
        await song_backed_message.delete()

        if player.queue._repeat.mode == voicelink.LoopType.track:
            await player.set_repeat(voicelink.LoopType.off.name)

    @music.command(name="seek", aliases=get_aliases("seek"))
    @app_commands.describe(position="Input position. Exmaple: 1:20.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def seek(self, ctx: commands.Context, position: str):
        "Change the player position."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_privileged(ctx.author):
            return await send(ctx, "missingPerms_pos", ephemeral=True)

        if not player.current or player.position == 0:
            return await send(ctx, "noTrackPlaying", ephemeral=True)

        num = formatTime(position)
        if num is None:
            return await send(ctx, "timeFormatError", ephemeral=True)

        await player.seek(num, ctx.author)
        seek_message = await send(ctx, "seek", position)
        await asyncio.sleep(5)
        await seek_message.delete()

    @music.command(name="queue", aliases=get_aliases("queue"), fallback="list", invoke_without_command=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def queue(self, ctx: commands.Context):
        "Display the players queue songs in your queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_user_join(ctx.author):
            return await send(ctx, "notInChannel", ctx.author.mention, player.channel.mention, ephemeral=True)

        if player.queue.is_empty:
            return await nowplay(ctx, player)
        view = ListView(player=player, author=ctx.author)
        view.response = await ctx.send(embed=await view.build_embed(), view=view)

    @music.command(name="history", aliases=get_aliases("history"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def history(self, ctx: commands.Context):
        "Display the players queue songs in your history queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_user_join(ctx.author):
            return await send(ctx, "notInChannel", ctx.author.mention, player.channel.mention, ephemeral=True)

        if not player.queue.history():
            return await nowplay(ctx, player)

        view = ListView(player=player, author=ctx.author, is_queue=False)
        view.response = await ctx.send(embed=await view.build_embed(), view=view)

    @music.command(name="leave", aliases=get_aliases("leave"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def leave(self, ctx: commands.Context):
        "Disconnects the bot from your voice channel and chears the queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_privileged(ctx.author):
            if ctx.author in player.stop_votes:
                return await send(ctx, "voted", ephemeral=True)
            else:
                player.stop_votes.add(ctx.author)
                if len(player.stop_votes) >= (required := player.required(leave=True)):
                    pass
                else:
                    return await send(ctx, "leaveVote", ctx.author, len(player.stop_votes), required)

        music_stopped_message = await send(ctx, "left", ctx.author)
        await asyncio.sleep(5)
        await music_stopped_message.delete()
        await player.teardown()

    @music.command(name="nowplaying", aliases=get_aliases("nowplaying"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def nowplaying(self, ctx: commands.Context):
        "Shows details of the current track."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_user_join(ctx.author):
            return await send(ctx, "notInChannel", ctx.author.mention, player.channel.mention, ephemeral=True)

        await nowplay(ctx, player)

    @music.command(name="loop", aliases=get_aliases("loop"))
    @app_commands.describe(mode="Choose a looping mode.")
    @app_commands.choices(mode=[
        app_commands.Choice(name='Off', value='off'),
        app_commands.Choice(name='Track', value='track'),
        app_commands.Choice(name='Queue', value='queue')
    ])
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def loop(self, ctx: commands.Context, mode: str):
        "Changes Loop mode."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_privileged(ctx.author):
            return await send(ctx, "missingPerms_mode", ephemeral=True)

        await player.set_repeat(mode)
        music_repeat_message = await send(ctx, "repeat", mode.capitalize())
        await asyncio.sleep(5)
        await music_repeat_message.delete()

    @music.command(name="clear", aliases=get_aliases("clear"))
    @app_commands.describe(queue="Choose a queue that you want to clear.")
    @app_commands.choices(queue=[
        app_commands.Choice(name='Queue', value='queue'),
        app_commands.Choice(name='History', value='history')
    ])
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def clear(self, ctx: commands.Context, queue: str = "queue"):
        "Remove all the tracks in your queue or history queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_privileged(ctx.author):
            return await send(ctx, "missingPerms_queue", ephemeral=True)

        queue = queue.lower()
        if queue == 'history':
            player.queue.history_clear(player.is_playing)
        else:
            queue = "queue"
            player.queue.clear()

        song_queue_cleared_message = await send(ctx, "cleared", queue.capitalize())
        await asyncio.sleep(5)
        await song_queue_cleared_message.delete()

    @music.command(name="remove", aliases=get_aliases("remove"))
    @app_commands.describe(
        position1="Input a position from the queue to be removed.",
        position2="Set the range of the queue to be removed.",
        member="Remove tracks requested by a specific member."
    )
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def remove(self, ctx: commands.Context, position1: int, position2: int = None, member: discord.Member = None):
        "Removes specified track or a range of tracks from the queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_privileged(ctx.author):
            return await send(ctx, "missingPerms_queue", ephemeral=True)

        removedTrack = player.queue.remove(position1, position2, member=member)

        removed_song_message = await send(ctx, "removed", len(removedTrack))
        await asyncio.sleep(5)
        await removed_song_message.delete()

    @music.command(name="replay", aliases=get_aliases("replay"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def replay(self, ctx: commands.Context):
        "Reset the progress of the current song."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_privileged(ctx.author):
            return await send(ctx, "missingPerms_pos", ephemeral=True)

        if not player.current:
            return await send(ctx, "noTrackPlaying", ephemeral=True)

        await player.seek(0)
        replay_message = await send(ctx, "replay")
        await asyncio.sleep(5)
        await replay_message.delete()

    @music.command(name="shuffle", aliases=get_aliases("shuffle"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def shuffle(self, ctx: commands.Context):
        "Randomizes the tracks in the queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_privileged(ctx.author):
            if ctx.author in player.shuffle_votes:
                return await send(ctx, "voted", ephemeral=True)
            else:
                player.shuffle_votes.add(ctx.author)
                if len(player.shuffle_votes) >= (required := player.required()):
                    pass
                else:
                    return await send(ctx, "shuffleVote", ctx.author, len(player.shuffle_votes), required)

        await player.shuffle("queue", ctx.author)
        suffled_message = await send(ctx, "shuffled")
        await asyncio.sleep(5)
        await suffled_message.delete()

    @music.command(name="swap", aliases=get_aliases("swap"))
    @app_commands.describe(
        position1="The track to swap. Example: 2",
        position2="The track to swap with position1. Exmaple: 1"
    )
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def swap(self, ctx: commands.Context, position1: int, position2: int):
        "Swaps the specified song to the specified song."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_privileged(ctx.author):
            return await send(ctx, "missingPerms_pos", ephemeral=True)

        track1, track2 = player.queue.swap(position1, position2)
        songs_swapped_message = await send(ctx, "swapped", track1.title, track2.title)
        await asyncio.sleep(5)
        await songs_swapped_message.delete()

    @music.command(name="move", aliases=get_aliases("move"))
    @app_commands.describe(
        target="The track to move. Example: 2",
        to="The new position to move the track to. Exmaple: 1"
    )
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def move(self, ctx: commands.Context, target: int, to: int):
        "Moves the specified song to the specified position."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_privileged(ctx.author):
            return await send(ctx, "missingPerms_pos", ephemeral=True)

        moved_track = player.queue.move(target, to)
        song_moved_message = await send(ctx, "moved", moved_track, to)
        await asyncio.sleep(5)
        await song_moved_message.delete()

    @music.command(name="autoplay", aliases=get_aliases("autoplay"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def autoplay(self, ctx: commands.Context):
        "Toggles autoplay mode, it will automatically queue the best songs to play."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await send(ctx, "noPlayer", ephemeral=True)

        if not player.is_privileged(ctx.author):
            return await send(ctx, "missingPerms_autoplay", ephemeral=True)

        check = not player.settings.get("autoplay", False)
        player.settings['autoplay'] = check
        auto_play_message = await send(ctx, "autoplay", await get_lang(ctx.guild.id, "enabled" if check else "disabled"))
        await asyncio.sleep(5)
        await auto_play_message.delete()

        if not player.is_playing:
            await player.do_next()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))