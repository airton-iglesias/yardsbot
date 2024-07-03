
import discord
from discord.ext import commands

import function as func

class HelpDropdown(discord.ui.Select):
    def __init__(self, categorys:list):
        self.view: HelpView

        super().__init__(
            placeholder="Select Category!",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(emoji="🏠", label="Help", description="View new updates of Yardsbot."),
            ] + [
                discord.SelectOption(emoji=emoji, label=f"{category} Commands", description=f"This is {category.lower()} Category.")
                for category, emoji in zip(categorys, ["2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"])
            ],
            custom_id="select"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        embed = self.view.build_embed(self.values[0].split(" ")[0])
        await interaction.response.edit_message(embed=embed)

class HelpView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member) -> None:
        super().__init__(timeout=60)

        self.author: discord.Member = author
        self.bot: commands.Bot = bot
        self.response: discord.Message = None
        self.categorys: list[str] = [ name.capitalize() for name, cog in bot.cogs.items() if len([c for c in cog.walk_commands()]) ]

        self.add_item(discord.ui.Button(label='Discord', emoji=':invite:915152589056790589', url=f'https://discord.gg/P83hMtsj9Q'))
        self.add_item(discord.ui.Button(label='Patreon', emoji=':patreon:913397909024800878', url='https://bit.ly/Yardzin'))
        self.add_item(HelpDropdown(self.categorys))
    
    async def on_error(self, error, item, interaction) -> None:
        return

    async def on_timeout(self) -> None:
        for child in self.children:
            if child.custom_id == "select":
                child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> None:
        return interaction.user == self.author

    def build_embed(self, category: str) -> discord.Embed:
        category = category.lower()
        if category == "help":
            embed = discord.Embed(title="Yardsbot Help Menu", url="https://discord.com/channels/1040118156523487323/1040118157047762948", color=func.settings.embed_color)
            embed.add_field(
                name=f"Available Categories: [{2 + len(self.categorys)}]",
                value="```py\n👉 Help\n{}```".format("".join(f"{i}. {c}\n" for i, c in enumerate(self.categorys, start=2))),
                inline=True
            )

            update = "Yardsbot is a multi-purpose bot. Supporting moderation, YouTube, Spotify, and more!"
            embed.add_field(name="📰 Information:", value=update, inline=True)
            embed.add_field(name="Get Started", value="```Join a voice channel and /play {Song/URL} a song. (Names, Youtube Video Links or Playlist links or Spotify links are supported)```", inline=False)
            
            return embed

        embed = discord.Embed(title=f"Category: {category.capitalize()}", color=func.settings.embed_color)
        embed.add_field(name=f"Categories: [{2 + len(self.categorys)}]",
                        value="```py\n" + "\n".join(("👉 " if c == category.capitalize() else f"{i}. ") + c for i, c in enumerate(['Help'] + self.categorys, start=1)) + "```",
                        inline=True
        )

        if category == 'tutorial':
            pass
        else:
            cog = [c for _, c in self.bot.cogs.items() if _.lower() == category][0]

            commands = [command for command in cog.walk_commands()]
            embed.description = cog.description
            embed.add_field(
                name=f"{category} Commands: [{len(commands)}]",
                value="```{}```".format("".join(f"/{command.qualified_name}\n" for command in commands if not command.qualified_name == cog.qualified_name))
            )

        return embed