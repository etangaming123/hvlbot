import discord
from discord.ext import commands
from discord import app_commands
import traceback

from common import experimentalqueuecheckchannelid, formatUsername, loadData, saveData, truncateMessage, returnAllAlts, serverid, etanid, membercountid, bottraproleid, messageloggingchannelid, weatherannouncementschannelidreturnAllAlts, formatUsername, loadData, saveData, truncateMessage, prescencecycles, openweatherapikey, lastcachedmembercount, didwealreadyreset, didwealreadyresetanditsnight, userlastbuttontimebutmorepermanent, starboardchannelbottraproleid, memberroleid, altaccountroleid, ruiroleid, joinandleavechannelid, SUPASECRETLOGGINGCHANNELID, moderatorroleid, moderatorplusplusroleid, channelstolockdown, bottrapchannelid, weatherannouncementschannelid, experimentalqueuecheckchannelid, playersinqueue, playersplaying, userincontrol, userlastbuttontime, getDisplay



class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="say", description="wonder what this does")
    @app_commands.describe(message="The message to send in the channel.")
    async def say(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You do not have permission to use this command.")
            return
        await interaction.channel.send(message)
        await interaction.edit_original_response(content="Done!")

    @app_commands.command(name="say-dm", description="wonder what this does but in dms")
    @app_commands.describe(user="The user to send the DM to.", message="The message to send.")
    async def say_dm(self, interaction: discord.Interaction, user: discord.User, message: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You do not have permission to use this command.")
            return
        try:
            dm = await user.create_dm()
            await dm.send(message)
        except discord.Forbidden:
            await interaction.edit_original_response(content="Failed to send DM. The user might have DMs disabled.")
            return
        await interaction.edit_original_response(content="Done!")

    @app_commands.command(name="say-form", description="same as /say but with a form, so you can multiline")
    async def say_form(self, interaction: discord.Interaction):
        if interaction.user.id != etanid:
            await interaction.response.send_message(content="You do not have permission to use this command.", ephemeral=True)
            return

        class SayModal(discord.ui.Modal, title="Say Command"):
            message = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph)

            async def on_submit(self, interaction: discord.Interaction):
                await interaction.channel.send(self.message.value)
                await interaction.response.send_message(content="Done!", ephemeral=True)

        await interaction.response.send_modal(SayModal())

    @app_commands.command(name="changerpc", description="Manually change the bot's RPC (admin only)")
    @app_commands.describe(newrpc="The new RPC to set for the bot.")
    async def changerpc(self, interaction: discord.Interaction, newrpc: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You don't have permission to use this command!")
            return
        try:
            await self.bot.change_presence(activity=discord.Game(newrpc), status=discord.Status.online)
        except Exception as e:
            await interaction.edit_original_response(content=f"An error occurred while changing RPC: {e}")
            traceback.print_exc()
            return
        await interaction.edit_original_response(content="RPC has been changed.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
