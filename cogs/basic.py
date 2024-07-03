import discord, requests, os, asyncio
from discord import app_commands
from discord.ext import commands, tasks
from function import (
    send,
    cooldown_check,
    get_aliases,
    update_user,
    get_user,
    is_email_registered
)
from views import HelpView
from dotenv import load_dotenv

load_dotenv()

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

    @commands.hybrid_command(name="supporter", aliases=get_aliases("supporter"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def supporter(self, ctx, email: str):
        """Activate your supporter benefit."""
        async def send_message(message: str):
            try:
                message_info = await ctx.send(message)
                await asyncio.sleep(5)
                await message_info.delete()
            except discord.Forbidden:
                await ctx.send("I don't have permission to delete messages.")

        sync_message = await ctx.send('Syncing supporter information...')
        await asyncio.sleep(1)
        await sync_message.delete()

        PATREON_API_URL = os.getenv('PATREON_API_URL')
        PATREON_ACCESS_TOKEN = os.getenv('PATREON_ACCESS_TOKEN')
        SUPPORTER_ROLE_ID = int(os.getenv('SUPPORTER_ROLE_ID'))

        email = email.lower()
        supporter_role = ctx.guild.get_role(SUPPORTER_ROLE_ID)
        member = ctx.guild.get_member(ctx.author.id)

        if member is None:
            try:
                member = await ctx.guild.fetch_member(ctx.author.id)
            except discord.NotFound:
                await send_message(f'Member with ID [ {ctx.author.id} ] not found.')
                return

        #database fetching dates
        try:
            user_data = await get_user(member.id)
            if not user_data:
                await send_message(f'Member with ID [ {member.id} ] is not registered.')
                return

            stored_email = user_data.get("email")
            user_id = user_data.get("_id")

        except Exception as e:
            await send_message(f"Error accessing the database: {e}")
            return

        #Treatment if the user is already registered in the database but don't have support role
        if stored_email == email and user_id == ctx.author.id:
            if supporter_role not in member.roles:
                try:
                    await member.add_roles(supporter_role)
                    await update_user(member.id, {"$set": {"email": email}})
                    await send_message(f'Added supporter role for {member.name}')
                    return
                except Exception as e:
                    await send_message(f"Error updating the database: {e}")
                    return
            else:
                await send_message("You're already a supporter.")
                return

        # Treatment if the email is already registered but not for the current user
        elif await is_email_registered(email) and stored_email is None:
            await send_message("This email is already registered.")
            return

        # Treatment to register the user's email
        else:
            # patreon api request
            headers = {'Authorization': f'Bearer {PATREON_ACCESS_TOKEN}'}

            try:
                response = requests.get(PATREON_API_URL, headers=headers)
                response.raise_for_status()
                data = response.json()
            except requests.RequestException as e:
                await send_message(f"Error connecting to Patreon API: {e}")
                return

            active_supporters = {user['attributes']['email'].lower() for user in data['data'] if
                                 user['attributes']['patron_status'] == 'active_patron' and user['attributes']['email']}

            # checks if the user is an active patron
            if email in active_supporters:
                if supporter_role not in member.roles:
                    try:
                        await member.add_roles(supporter_role)
                        await update_user(member.id, {"$set": {"email": email}})
                        await send_message(f'Added supporter role for {member.name}')
                    except Exception as e:
                        await send_message(f"Error updating the database: {e}")
                else:
                    await send_message("You're already a supporter.")
            else:
                await send_message("The email is not associated with a supporter.")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Basic(bot))
