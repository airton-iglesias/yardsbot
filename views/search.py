from __future__ import annotations

import discord

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from voicelink import Track

class SearchDropdown(discord.ui.Select):
    def __init__(self, tracks: list[Track], texts: list[str]) -> None:
        self.view: SearchView
        self.texts: list[str] = texts
        
        super().__init__(
            placeholder=texts[0],
            min_values=1, max_values=len(tracks),
            options=[
                discord.SelectOption(label=f"{i}. {track.title[:50]}", description=f"{track.author[:50]} · {track.formatted_length}")
                for i, track in enumerate(tracks, start=1)    
            ]
        )
        
    async def callback(self, interaction: discord.Interaction) -> None:
        self.disabled = True
        self.placeholder = self.texts[1]
        await interaction.response.edit_message(view=self.view)
        self.view.values = self.values          
        self.view.stop()

class SearchView(discord.ui.View):
    def __init__(self, tracks: list[Track], texts: list[str]) -> None:
        super().__init__(timeout=60)

        self.response: discord.Message = None
        self.values: list[str] = None
        self.add_item(SearchDropdown(tracks, texts))

    async def on_error(self, error, item, interaction):
        return

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass