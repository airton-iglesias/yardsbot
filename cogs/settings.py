import discord
import voicelink
import psutil
import function as func

from typing import Tuple
from discord import app_commands
from discord.ext import commands
from function import (
    LANGS,
    send,
    update_settings,
    get_settings,
    get_lang,
    time as ctime,
    get_aliases,
    cooldown_check
)
from views import HelpView, EmbedBuilderView

def formatBytes(bytes: int, unit: bool = False):
    if bytes <= 1_000_000_000:
        return f"{bytes / (1024 ** 2):.1f}" + ("MB" if unit else "")
    
    else:
        return f"{bytes / (1024 ** 3):.1f}" + ("GB" if unit else "")

class Settings(commands.Cog, name="settings"):
    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot
        self.description = "This category is only available to admin permissions on the server."
    
    @commands.hybrid_group(name="settings", aliases=get_aliases("settings"), invoke_without_command=True)
    async def settings(self, ctx: commands.Context):
        view = HelpView(self.bot, ctx.author)
        embed = view.build_embed(self.qualified_name)
        view.response = await ctx.send(embed=embed, view=view)
    
    @settings.command(name="prefix", aliases=get_aliases("prefix"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def prefix(self, ctx: commands.Context, prefix: str):
        "Change the default prefix for message commands."
        await update_settings(ctx.guild.id, {"$set": {"prefix": prefix}})
        await send(ctx, "setPrefix", prefix, prefix)

    @settings.command(name="language", aliases=get_aliases("language"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def language(self, ctx: commands.Context, language: str):
        "You can choose your preferred language, the bot message will change to the language you set."
        language = language.upper()
        if language not in LANGS:
            return await send(ctx, "languageNotFound")

        await update_settings(ctx.guild.id, {"$set": {'lang': language}})
        await send(ctx, 'changedLanguage', language)

    @language.autocomplete('language')
    async def autocomplete_callback(self, interaction: discord.Interaction, current: str) -> list:
        if current:
            return [app_commands.Choice(name=lang, value=lang) for lang in LANGS.keys() if current.upper() in lang]
        return [app_commands.Choice(name=lang, value=lang) for lang in LANGS.keys()]

    @settings.command(name="queue", aliases=get_aliases("queue"))
    @app_commands.choices(mode=[
        app_commands.Choice(name="FairQueue", value="FairQueue"),
        app_commands.Choice(name="Queue", value="Queue")
    ])
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def queue(self, ctx: commands.Context, mode: str):
        "Change to another type of queue mode."
        mode = "FairQueue" if mode.lower() == "fairqueue" else "Queue"
        await update_settings(ctx.guild.id, {"$set": {"queueType": mode}})
        await send(ctx, "setqueue", mode)

    @settings.command(name="volume", aliases=get_aliases("volume"))
    @app_commands.describe(value="Input a integer.")
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def volume(self, ctx: commands.Context, value: commands.Range[int, 1, 150]):
        "Set the player's volume."
        player: voicelink.Player = ctx.guild.voice_client
        if player:
            await player.set_volume(value, ctx.author)

        await update_settings(ctx.guild.id, {"$set": {'volume': value}})
        await send(ctx, 'setVolume', value)

    @settings.command(name="togglecontroller", aliases=get_aliases("togglecontroller"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def togglecontroller(self, ctx: commands.Context):
        "Toggles the music controller."
        settings = await get_settings(ctx.guild.id)
        toggle = not settings.get('controller', True)

        player: voicelink.Player = ctx.guild.voice_client
        if player and toggle is False and player.controller:
            try:
                await player.controller.delete()
            except:
                discord.ui.View.from_message(player.controller).stop()

        await update_settings(ctx.guild.id, {"$set": {'controller': toggle}})
        await send(ctx, 'togglecontroller', await get_lang(ctx.guild.id, "enabled" if toggle else "disabled"))

    @settings.command(name="duplicatetrack", aliases=get_aliases("duplicatetrack"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def duplicatetrack(self, ctx: commands.Context):
        "Toggle Yardsbot to prevent duplicate songs from queuing."
        settings = await get_settings(ctx.guild.id)
        toggle = not settings.get('duplicateTrack', False)
        player: voicelink.Player = ctx.guild.voice_client
        if player:
            player.queue._allow_duplicate = toggle

        await update_settings(ctx.guild.id, {"$set": {'duplicateTrack': toggle}})
        return await send(ctx, "toggleDuplicateTrack", await get_lang(ctx.guild.id, "disabled" if toggle else "enabled"))
    
    @settings.command(name="customcontroller", aliases=get_aliases("customcontroller"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def customcontroller(self, ctx: commands.Context):
        "Customizes music controller embeds."
        settings = await get_settings(ctx.guild.id)
        controller_settings = settings.get("default_controller", func.settings.controller)

        view = EmbedBuilderView(ctx, controller_settings.get("embeds").copy())
        view.response = await ctx.send(embed=view.build_embed(), view=view)

    @settings.command(name="controllermsg", aliases=get_aliases("controllermsg"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def controllermsg(self, ctx: commands.Context):
        "Toggles to send a message when clicking the button in the music controller."
        settings = await get_settings(ctx.guild.id)
        toggle = not settings.get('controller_msg', True)

        await update_settings(ctx.guild.id, {"$set": {'controller_msg': toggle}})
        await send(ctx, 'toggleControllerMsg', await get_lang(ctx.guild.id, "enabled" if toggle else "disabled"))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Settings(bot))
