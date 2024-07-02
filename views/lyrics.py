import discord
import function as func

class LyricsDropdown(discord.ui.Select):
    def __init__(self, langs: list[str]) -> None:
        self.view: LyricsView

        super().__init__(
            placeholder="Select A Lyrics Translation",
            min_values=1, max_values=1,
            options=[discord.SelectOption(label=lang) for lang in langs], 
            custom_id="selectLyricsLangs"
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.lang = self.values[0]
        self.view.current_page = 1
        self.view.pages = len(self.view.source.get(self.values[0]))
        await interaction.response.edit_message(embed=self.view.build_embed())

class LyricsView(discord.ui.View):
    def __init__(self, name: str, source: dict, author: discord.Member) -> None:
        super().__init__(timeout=60)

        self.name: str = name
        self.source: dict[str, list[str]] = source
        self.lang: list[str] = list(source.keys())[0]
        self.author: discord.Member = author

        self.response: discord.Message = None
        self.pages: int = len(self.source.get(self.lang))
        self.current_page: int = 1
        self.add_item(LyricsDropdown(list(source.keys())))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass
    
    async def on_error(self, error, item, interaction) -> None:
        return

    def build_embed(self) -> discord.Embed:
        chunk = self.source.get(self.lang)[self.current_page - 1]
        embed=discord.Embed(description=chunk, color=func.settings.embed_color)
        embed.set_author(name=f"Searching Query: {self.name}", icon_url=self.author.display_avatar.url)
        embed.set_footer(text=f"Page: {self.current_page}/{self.pages}")
        return embed

    @discord.ui.button(label='<<', style=discord.ButtonStyle.grey)
    async def fast_back_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.current_page != 1:
            self.current_page = 1
            return await interaction.response.edit_message(embed=self.build_embed())
        await interaction.response.defer()

    @discord.ui.button(label='Back', style=discord.ButtonStyle.blurple)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.current_page > 1:
            self.current_page -= 1
            return await interaction.response.edit_message(embed=self.build_embed())
        await interaction.response.defer()

    @discord.ui.button(label='Next', style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.current_page < self.pages:
            self.current_page += 1
            return await interaction.response.edit_message(embed=self.build_embed())
        await interaction.response.defer()

    @discord.ui.button(label='>>', style=discord.ButtonStyle.grey)
    async def fast_next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.current_page != self.pages:
            self.current_page = self.pages
            return await interaction.response.edit_message(embed=self.build_embed())
        await interaction.response.defer()

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.response.delete()
        self.stop()