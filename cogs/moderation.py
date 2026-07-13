import discord
from discord.ext import commands, tasks
from discord import app_commands
import time
import traceback
import requests
import random
import pickle
import os
import datetime
from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp
import numpy as np
import json

import common as common_module

for name in dir(common_module):
    if not name.startswith("_"):
        globals()[name] = getattr(common_module, name)

# moderation
class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="purge", description="Purge a bunch of messages.")
    @app_commands.describe(messageid="The ID of the first message in the conversation.")
    async def purge(self, interaction: discord.Interaction, messageid: str):
        await interaction.response.defer(ephemeral=True)
        if not moderatorroleid in [role.id for role in interaction.user.roles]:
            await interaction.edit_original_response(content="You don't have permission to use this command!")
            return
        try:
            await interaction.edit_original_response(content=f"Just a sec...")
            bunchofmessages = []
            async for msg in interaction.channel.history(after=discord.Object(id=messageid)):
                bunchofmessages.append(msg)
                if msg.id == messageid:
                    break
            bunchofmessages.append(await interaction.channel.fetch_message(messageid))
            wowbroimovedthismanymessages = len(bunchofmessages)
            loggingchannel = await self.bot.get_channel(messageloggingchannelid)
            embed = discord.Embed(title="Bulk Message Deletion", description=f"{formatUsername(interaction.user)} purged {wowbroimovedthismanymessages} messages in {interaction.channel.mention}.", color=discord.Color.red(), timestamp=discord.utils.utcnow())
            await loggingchannel.send(embed=embed)
            await interaction.channel.purge(limit=len(bunchofmessages))
            await interaction.edit_original_response(content=f"Purged {wowbroimovedthismanymessages} messages.")
        except Exception as e:
            await interaction.edit_original_response(content=f"An error occurred: {e}")
            traceback.print_exc()
            return

    @app_commands.command(name="lockdown", description="Removes send message permissions from @everyone.")
    async def lockdown(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not moderatorplusplusroleid in [role.id for role in interaction.user.roles]:
            await interaction.edit_original_response(content=f"You don't have permission to use this command!")
            return
        guild = self.bot.get_guild(serverid)
        everyone = guild.default_role
        perms = everyone.permissions
        perms.update(send_messages=False, add_reactions=False)
        loggingchannel = await self.bot.get_channel(messageloggingchannelid)
        embed = discord.Embed(title="Lockdown Initiated", description=f"Lockdown has been initiated by {formatUsername(interaction.user)}. Send message and add reaction permissions have been removed from @everyone.", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        await loggingchannel.send(embed=embed)
        await everyone.edit(permissions=perms, reason=f"Lockdown initiated by {formatUsername(interaction.user)}")
        await interaction.edit_original_response(content=f"Removed send message permissions from @everyone.")

    @app_commands.command(name="remove-lockdown", description="Restores send message permissions to @everyone.")
    async def unlockdown(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not moderatorplusplusroleid in [role.id for role in interaction.user.roles]:
            await interaction.edit_original_response(content=f"You don't have permission to use this command!")
            return
        guild = self.bot.get_guild(serverid)
        everyone = guild.default_role
        perms = everyone.permissions
        perms.update(send_messages=True, add_reactions=True)
        await everyone.edit(permissions=perms, reason=f"Lockdown removed by {formatUsername(interaction.user)}")
        loggingchannel = await self.bot.get_channel(messageloggingchannelid)
        embed = discord.Embed(title="Lockdown Removed", description=f"Lockdown has been removed by {formatUsername(interaction.user)}.", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        await loggingchannel.send(embed=embed)
        await interaction.edit_original_response(content=f"Restored send message permissions to @everyone.")

    # additional moderator commands, these ones being pulled from discord, but also having some custom functionality like DMing the user when they get kicked
    @app_commands.command(name="kick", description="Kick a user from the server.")
    @app_commands.describe(user="The user to kick.", reason="The reason for the kick. (will show in dms if you decide to dm)", dm="Whether to DM the user about the kick or not (defaults to false).")
    async def kick(self, interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided.", dm: bool = False):
        await interaction.response.defer()
        if not moderatorroleid in [role.id for role in interaction.user.roles]:
            await interaction.edit_original_response(content=f"You don't have permission to use this command!")
            return
        if moderatorroleid in [role.id for role in user.roles] or moderatorplusplusroleid in [role.id for role in user.roles]:
            await interaction.edit_original_response(content=f"No.")
            return
        guild = self.bot.get_guild(serverid)
        await guild.kick(user, reason=reason)
        loggingchannel = await self.bot.get_channel(messageloggingchannelid)
        embed = discord.Embed(title="User Kicked via HVLBot", description=f"{formatUsername(user)} was kicked by {formatUsername(interaction.user)}.", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Reason", value=reason, inline=False)
        await loggingchannel.send(embed=embed)
        dmmm = False
        if dm:
            try:
                dm = await user.create_dm()
                await dm.send(f"You have been kicked from hurstville lurkers. // {reason}")
                dmmm = True
            except discord.Forbidden:
                dmmm = False
        if dm and dmmm:
            await interaction.edit_original_response(content=f"{formatUsername(user)} has been kicked from the server and has been DM'd about the kick.")
        elif dm and not dmmm:
            await interaction.edit_original_response(content=f"{formatUsername(user)} has been kicked from the server, but I was unable to DM them about the kick.")
        else:
            await interaction.edit_original_response(content=f"{formatUsername(user)} has been kicked from the server.")

    @app_commands.command(name="ban", description="Ban a user from the server.")
    @app_commands.describe(user="The user to ban.", reason="The reason for the ban. (will show in dms if you decide to dm)", dm="Whether to DM the user about the ban or not (defaults to false).")
    async def ban(self, interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided.", dm: bool = False):
        await interaction.response.defer()
        if not moderatorplusplusroleid in [role.id for role in interaction.user.roles]:
            await interaction.edit_original_response(content=f"You don't have permission to use this command!")
            return
        if moderatorroleid in [role.id for role in user.roles] or moderatorplusplusroleid in [role.id for role in user.roles]:
            await interaction.edit_original_response(content=f"No.")
            return
        guild = self.bot.get_guild(serverid)
        await guild.ban(user, reason=reason)
        loggingchannel = await self.bot.get_channel(messageloggingchannelid)
        embed = discord.Embed(title="User Banned via HVLBot", description=f"{formatUsername(user)} was banned by {formatUsername(interaction.user)}.", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Reason", value=reason, inline=False)
        await loggingchannel.send(embed=embed)
        dmmm = False
        if dm:
            try:
                dm = await user.create_dm()
                await dm.send(f"You have been banned from hurstville lurkers. // {reason}")
                dmmm = True
            except discord.Forbidden:
                dmmm = False
        if dm and dmmm:
            await interaction.edit_original_response(content=f"{formatUsername(user)} has been banned from the server and has been DM'd about the ban.")
        elif dm and not dmmm:
            await interaction.edit_original_response(content=f"{formatUsername(user)} has been banned from the server, but I was unable to DM them about the ban.")
        else:
            await interaction.edit_original_response(content=f"{formatUsername(user)} has been banned from the server.")

    @app_commands.command(name="unban", description="Unban a user from the server. [user id]")
    @app_commands.describe(userid="The ID of the user to unban.")
    async def unban(self, interaction: discord.Interaction, userid: int):
        await interaction.response.defer()
        if not moderatorplusplusroleid in [role.id for role in interaction.user.roles]:
            await interaction.edit_original_response(content=f"You don't have permission to use this command!")
            return
        if moderatorroleid in [role.id for role in user.roles] or moderatorplusplusroleid in [role.id for role in user.roles]:
            await interaction.edit_original_response(content=f"No.")
            return
        try:
            guild = self.bot.get_guild(serverid)
            user = await self.bot.fetch_user(userid)
            await guild.unban(user)
            loggingchannel = await self.bot.get_channel(messageloggingchannelid)
            embed = discord.Embed(title="User Unbanned via HVLBot", description=f"{formatUsername(user)} was unbanned by {formatUsername(interaction.user)}.", color=discord.Color.green(), timestamp=discord.utils.utcnow())
            await loggingchannel.send(embed=embed)
            await interaction.edit_original_response(content=f"{formatUsername(user)} has been unbanned from the server.")
        except Exception as e:
            await interaction.edit_original_response(content=f"An error occurred: {e}")
            traceback.print_exc()
            return

    @app_commands.command(name="timeout", description="Timeout a user from chatting in the server for a certain amount of time.")
    @app_commands.choices(duration=[
        app_commands.Choice(name="1 minute", value=60),
        app_commands.Choice(name="5 minutes", value=300),
        app_commands.Choice(name="10 minutes", value=600),
        app_commands.Choice(name="1 hour", value=3600),
        app_commands.Choice(name="1 day", value=86400),
        app_commands.Choice(name="1 week", value=1209600)
    ])
    @app_commands.describe(user="The user to timeout.", duration="The duration of the timeout.", reason="The reason for the timeout.")
    async def timeout(self, interaction: discord.Interaction, user: discord.User, duration: app_commands.Choice[int], reason: str = "No reason provided."):
        await interaction.response.defer()
        if not moderatorroleid in [role.id for role in interaction.user.roles]:
            await interaction.edit_original_response(content=f"You don't have permission to use this command!")
            return
        if moderatorroleid in [role.id for role in user.roles] or moderatorplusplusroleid in [role.id for role in user.roles]:
            await interaction.edit_original_response(content=f"No.")
            return
        guild = self.bot.get_guild(serverid)
        member = guild.get_member(user.id)
        if member is None:
            await interaction.edit_original_response(content=f"User not found in the server.")
            return
        try:
            await member.timeout(discord.utils.utcnow() + datetime.timedelta(seconds=duration.value), reason=reason)
            loggingchannel = await self.bot.get_channel(messageloggingchannelid)
            embed = discord.Embed(title="User Timed Out via HVLBot", description=f"{formatUsername(user)} was timed out by {formatUsername(interaction.user)} for {duration.name}.", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
            embed.add_field(name="Reason", value=reason, inline=False)
            await loggingchannel.send(embed=embed)
            await interaction.edit_original_response(content=f"{formatUsername(user)} has been timed out for {duration.name}.")
        except Exception as e:
            await interaction.edit_original_response(content=f"An error occurred: {e}")
            traceback.print_exc()
            return

    @app_commands.command(name="timeout-custom", description="Timeout a user for a custom amount of time (in minutes).")
    @app_commands.describe(user="The user to timeout.", duration="The duration of the timeout in minutes.", reason="The reason for the timeout.")
    async def timeout_custom(self, interaction: discord.Interaction, user: discord.User, duration: int, reason: str = "No reason provided."):
        await interaction.response.defer()
        if not moderatorroleid in [role.id for role in interaction.user.roles]:
            await interaction.edit_original_response(content=f"You don't have permission to use this command!")
            return
        if moderatorroleid in [role.id for role in user.roles] or moderatorplusplusroleid in [role.id for role in user.roles]:
            await interaction.edit_original_response(content=f"No.")
            return
        guild = self.bot.get_guild(serverid)
        member = guild.get_member(user.id)
        if member is None:
            await interaction.edit_original_response(content=f"User not found in the server.")
            return
        try:
            await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=duration), reason=reason)
            loggingchannel = await self.bot.get_channel(messageloggingchannelid)
            embed = discord.Embed(title="User Timed Out via HVLBot", description=f"{formatUsername(user)} was timed out by {formatUsername(interaction.user)} for {duration} minutes.", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
            embed.add_field(name="Reason", value=reason, inline=False)
            await loggingchannel.send(embed=embed)
            await interaction.edit_original_response(content=f"{formatUsername(user)} has been timed out for {duration} minutes.")
        except Exception as e:
            await interaction.edit_original_response(content=f"An error occurred: {e}")
            traceback.print_exc()
            return

    @app_commands.command(name="untimeout", description="Remove timeout from a user.")
    @app_commands.describe(user="The user to remove timeout from.")
    async def untimeout(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer()
        if not moderatorroleid in [role.id for role in interaction.user.roles]:
            await interaction.edit_original_response(content=f"You don't have permission to use this command!")
            return
        if moderatorroleid in [role.id for role in user.roles] or moderatorplusplusroleid in [role.id for role in user.roles]:
            await interaction.edit_original_response(content=f"No.")
            return
        guild = self.bot.get_guild(serverid)
        member = guild.get_member(user.id)
        if member is None:
            await interaction.edit_original_response(content=f"User not found in the server.")
            return
        try:
            await member.timeout(None, reason="Timeout removed.")
            loggingchannel = await self.bot.get_channel(messageloggingchannelid)
            embed = discord.Embed(title="User Untimed Out via HVLBot", description=f"{formatUsername(user)} was untimed out by {formatUsername(interaction.user)}.", color=discord.Color.green(), timestamp=discord.utils.utcnow())
            await loggingchannel.send(embed=embed)
            await interaction.edit_original_response(content=f"Timeout has been removed from {formatUsername(user)}.")
        except Exception as e:
            await interaction.edit_original_response(content=f"An error occurred: {e}")
            traceback.print_exc()
            return

    @app_commands.command(name="delete-message", description="Delete a message by its ID. (admin only)")
    @app_commands.describe(messageid="The ID of the message to delete.")
    async def delete_message(self, interaction: discord.Interaction, messageid: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content=f"You don't have permission to use this command!")
            return
        try:        
            message = await interaction.channel.fetch_message(messageid)
            await message.delete()
            await interaction.edit_original_response(content=f"Message with ID {messageid} has been deleted.")
        except Exception as e:
            await interaction.edit_original_response(content=f"An error occurred: {e}")
            traceback.print_exc()
            return

    @app_commands.command(name="pin-message", description="Pin a message by its ID. (admin only)")
    @app_commands.describe(messageid="The ID of the message to pin.")
    async def pin_message(self, interaction: discord.Interaction, messageid: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content=f"You don't have permission to use this command!")
            return
        try:
            message = await interaction.channel.fetch_message(messageid)
            await message.pin()
            await interaction.edit_original_response(content=f"Message with ID {messageid} has been pinned.")
        except Exception as e:
            await interaction.edit_original_response(content=f"An error occurred: {e}")
            traceback.print_exc()
            return


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))