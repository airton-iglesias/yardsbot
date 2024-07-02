import discord

class LinkView(discord.ui.View):
    def __init__(self, label=None, emoji=None, url=None):
        super().__init__(timeout=60)
        self.add_item(discord.ui.Button(label=label, emoji=emoji, url=url))