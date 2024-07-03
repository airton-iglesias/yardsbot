import discord
import sys
import os
import traceback
import aiohttp
import function as func

from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
from voicelink import VoicelinkException
from addons import Settings
class Yardsbot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_message(self, message: discord.Message, /) -> None:
        if message.author.bot or not message.guild:
            return False

        if self.user.id in message.raw_mentions and not message.mention_everyone:
            prefix = await self.command_prefix(self, message)
            if not prefix:
                return await message.channel.send("I don't have a bot prefix set.")
            await message.channel.send(f"My prefix is `{prefix}`")

        await self.process_commands(message)

    async def connect_db(self) -> None:
        if not ((db_name := func.tokens.mongodb_name) and (db_url := func.tokens.mongodb_url)):
            raise Exception("MONGODB_NAME and MONGODB_URL can't not be empty in settings.json")

        try:
            func.MONGO_DB = AsyncIOMotorClient(host=db_url)
            await func.MONGO_DB.server_info()
            print("Successfully connected to MongoDB!")

        except Exception as e:
            raise Exception("Not able to connect MongoDB! Reason:", e)
        
        func.SETTINGS_DB = func.MONGO_DB[db_name]["Settings"]
        func.USERS_DB = func.MONGO_DB[db_name]["Users"]

    async def setup_hook(self) -> None:
        func.langs_setup()
        
        # Connecting to MongoDB
        await self.connect_db()

        # Loading all the module in `cogs` folder
        for module in os.listdir(func.ROOT_DIR + '/cogs'):
            if module.endswith('.py'):
                try:
                    await self.load_extension(f"cogs.{module[:-3]}")
                    print(f"Loaded {module[:-3]}")
                except Exception as e:
                    print(traceback.format_exc())

        await self.tree.sync()

    async def on_ready(self):
        print("------------------")
        print(f"Logged As {self.user}")
        print(f"Bot ID: {self.user.id}")
        print("------------------")

        func.tokens.client_id = self.user.id
        func.LOCAL_LANGS.clear()

    async def on_command_error(self, ctx: commands.Context, exception, /) -> None:
        error = getattr(exception, 'original', exception)
        if ctx.interaction:
            error = getattr(error, 'original', error)
            
        if isinstance(error, (commands.CommandNotFound, aiohttp.client_exceptions.ClientOSError, discord.errors.NotFound)):
            return

        elif isinstance(error, (commands.CommandOnCooldown, commands.MissingPermissions, commands.RangeError, commands.BadArgument)):
            pass

        elif isinstance(error, (commands.MissingRequiredArgument, commands.MissingRequiredAttachment)):
            command = f"{ctx.prefix}" + (f"{ctx.command.parent.qualified_name} " if ctx.command.parent else "") + f"{ctx.command.name} {ctx.command.signature}"
            position = command.find(f"<{ctx.current_parameter.name}>") + 1
            description = f"**Correct Usage:**\n```{command}\n" + " " * position + "^" * len(ctx.current_parameter.name) + "```\n"
            if ctx.command.aliases:
                description += f"**Aliases:**\n`{', '.join([f'{ctx.prefix}{alias}' for alias in ctx.command.aliases])}`\n\n"
            description += f"**Description:**\n{ctx.command.help}\n\u200b"

            embed = discord.Embed(description=description, color=func.settings.embed_color)
            embed.set_footer(icon_url=ctx.me.display_avatar.url, text=f"More infos: {func.settings.invite_link}")
            return await ctx.reply(embed=embed)

        elif not issubclass(error.__class__, VoicelinkException):
            error = await func.get_lang(ctx.guild.id, "unknownException") + func.settings.invite_link
            if (guildId := ctx.guild.id) not in func.ERROR_LOGS:
                func.ERROR_LOGS[guildId] = {}
            func.ERROR_LOGS[guildId][round(datetime.timestamp(datetime.now()))] = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

        try:
            return await ctx.reply(error, ephemeral=True)
        except:
            pass

class CommandCheck(discord.app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in guilds!")
            return False

        return await super().interaction_check(interaction)
    
async def get_prefix(bot, message: discord.Message):
    settings = await func.get_settings(message.guild.id)
    return settings.get("prefix", func.settings.bot_prefix)

# Loading settings
func.settings = Settings(func.open_json("settings.json"))

# Setup the bot object
intents = discord.Intents.default()
intents.message_content = True if func.settings.bot_prefix else False
intents.members = True
member_cache = discord.MemberCacheFlags(
    voice=True,
    joined=False
)

bot = Yardsbot(
    command_prefix=get_prefix,
    help_command=None,
    tree_cls=CommandCheck,
    chunk_guilds_at_startup=False,
    member_cache_flags=member_cache,
    activity=discord.Activity(type=discord.ActivityType.listening, name="Starting..."),
    case_insensitive=True,
    intents=intents
)

if __name__ == "__main__":
    bot.run(func.tokens.token, log_handler=None)