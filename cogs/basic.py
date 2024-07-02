import discord
from discord import app_commands
from discord.ext import commands
from function import (
    send,
    cooldown_check,
    get_aliases
)
from views import HelpView

class Basic(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.description = "This category is available to anyone on this server. Voting is required in certain commands."

    async def help_autocomplete(self, interaction: discord.Interaction, current: str) -> list:
        return [app_commands.Choice(name=c.capitalize(), value=c) for c in self.bot.cogs if
                c not in ["Nodes", "Task"] and current.lower() in c.lower()]

    @commands.hybrid_command(name="help", aliases=get_aliases("help"))
    @app_commands.autocomplete(category=help_autocomplete)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def help(self, ctx: commands.Context, category: str = "Help") -> None:
        "Lists all the commands in Yardsbot."
        if category not in self.bot.cogs:
            category = "Help"
        view = HelpView(self.bot, ctx.author)
        embed = view.build_embed(category)
        view.response = await ctx.send(embed=embed, view=view)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Basic(bot))
