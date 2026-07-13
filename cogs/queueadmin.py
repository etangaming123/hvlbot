import time

import discord
from discord.ext import commands
from discord import app_commands

from common import experimentalqueuecheckchannelid, formatUsername, loadData, saveData, truncateMessage, returnAllAlts, serverid, etanid, membercountid, bottraproleid, messageloggingchannelid, weatherannouncementschannelidreturnAllAlts, formatUsername, loadData, saveData, truncateMessage, prescencecycles, openweatherapikey, lastcachedmembercount, didwealreadyreset, didwealreadyresetanditsnight, userlastbuttontimebutmorepermanent, starboardchannel, bot, bottraproleid, memberroleid, altaccountroleid, ruiroleid, joinandleavechannelid, SUPASECRETLOGGINGCHANNELID, moderatorroleid, moderatorplusplusroleid, channelstolockdown, bottrapchannelid, weatherannouncementschannelid, experimentalqueuecheckchannelid, playersinqueue, playersplaying, userincontrol, userlastbuttontime, getDisplay



class QueueAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_queue_check_message(self):
        channel = self.bot.get_channel(experimentalqueuecheckchannelid)
        if channel is None:
            return None
        async for message in channel.history(limit=25):
            if message.author.id == self.bot.user.id:
                return message
        return None

    async def _set_queue_message(self, content: str):
        message = await self._get_queue_check_message()
        if message is not None:
            await message.edit(content=content)

    @app_commands.command(name="resetqueuecheck", description="Resets the queue check (admin only)")
    async def resetqueuecheck(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You do not have permission to use this command.")
            return

        await self._set_queue_message(content=f"Awaiting queue action... [Queue check was reset <t:{round(time.time())}:R>]")
        await interaction.edit_original_response(content="Queue check has been reset.")

    @app_commands.command(name="manualqueuesetup", description="Manually sets the queue and playing counts (admin only)")
    @app_commands.describe(playing="The number of players currently playing.", inqueue="The number of players currently in queue.")
    async def manualqueuesetup(self, interaction: discord.Interaction, playing: int, inqueue: int):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You do not have permission to use this command.")
            return
        if playing < 0 or inqueue < 0:
            await interaction.edit_original_response(content="Playing and inqueue counts must be non-negative.")
            return

        await self._set_queue_message(content=f"{playing} playing, {inqueue} in queue\nLast updated by {formatUsername(interaction.user)} <t:{round(time.time())}:R>")
        await interaction.edit_original_response(content=f"Queue check has been manually set to {playing} playing and {inqueue} in queue.")

    @app_commands.command(name="ban-queue", description="Ban a user from using the queue buttons.")
    @app_commands.describe(user="The user to ban from the queue.")
    async def ban_queue(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You do not have permission to use this command.")
            return

        banned_users = loadData("bannedecqc")
        if not isinstance(banned_users, list):
            banned_users = []
        if user.id in banned_users:
            await interaction.edit_original_response(content=f"{user.mention} is already banned from using the queue buttons.")
            return

        banned_users.append(user.id)
        if saveData("bannedecqc", banned_users):
            await interaction.edit_original_response(content=f"{user.mention} has been banned from using the queue buttons.")
        else:
            await interaction.edit_original_response(content="An error occurred while saving the banned users data.")

    @app_commands.command(name="unban-queue", description="Unban a user from using the queue buttons.")
    @app_commands.describe(user="The user to unban from the queue.")
    async def unban_queue(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You do not have permission to use this command.")
            return

        banned_users = loadData("bannedecqc")
        if not isinstance(banned_users, list):
            banned_users = []
        if user.id not in banned_users:
            await interaction.edit_original_response(content=f"{user.mention} is not currently banned from using the queue buttons.")
            return

        banned_users.remove(user.id)
        if saveData("bannedecqc", banned_users):
            await interaction.edit_original_response(content=f"{user.mention} has been unbanned from using the queue buttons.")
        else:
            await interaction.edit_original_response(content="An error occurred while saving the banned users data.")


async def setup(bot: commands.Bot):
    await bot.add_cog(QueueAdmin(bot))
