import discord
from discord.ext import commands
from discord import app_commands

from common import experimentalqueuecheckchannelid, formatUsername, loadData, saveData, truncateMessage, returnAllAlts, serverid, etanid, membercountid, bottraproleid, messageloggingchannelid, weatherannouncementschannelidreturnAllAlts, formatUsername, loadData, saveData, truncateMessage, prescencecycles, openweatherapikey, lastcachedmembercount, didwealreadyreset, didwealreadyresetanditsnight, userlastbuttontimebutmorepermanent, starboardchannelbottraproleid, memberroleid, altaccountroleid, ruiroleid, joinandleavechannelid, SUPASECRETLOGGINGCHANNELID, moderatorroleid, moderatorplusplusroleid, channelstolockdown, bottrapchannelid, weatherannouncementschannelid, experimentalqueuecheckchannelid, playersinqueue, playersplaying, userincontrol, userlastbuttontime, getDisplay


class CustomRoles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="addcustomrole", description="Gives a user a custom role they can edit!")
    @app_commands.describe(user="The user to give the role to.")
    async def addcustomrole(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You don't have permission to use this command!")
            return
        customroledata = loadData("customroles")
        if customroledata == "":
            await interaction.edit_original_response(content="An error occurred while loading custom role data.")
            return
        if str(user.id) in customroledata:
            await interaction.edit_original_response(content="This user already has a custom role!")
            return
        guild = self.bot.get_guild(serverid)
        role = await guild.create_role(name=f"{user.name}'s Custom Role", color=discord.Color.default())
        pos = guild.get_role(ruiroleid).position - 1
        await role.edit(position=pos)
        await user.add_roles(role)
        customroledata[str(user.id)] = role.id
        if not saveData("customroles", customroledata):
            await interaction.edit_original_response(content="An error occurred while saving custom role data.")
            return
        await interaction.edit_original_response(content=f"Custom role has been created and assigned to {formatUsername(user)}.")

    @app_commands.command(name="removecustomrole", description="Removes a user's custom role.")
    @app_commands.describe(user="The user to remove the role from.")
    async def removecustomrole(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You don't have permission to use this command!")
            return
        customroledata = loadData("customroles")
        if customroledata == "":
            await interaction.edit_original_response(content="An error occurred while loading custom role data.")
            return
        if str(user.id) not in customroledata:
            await interaction.edit_original_response(content="This user does not have a custom role!")
            return
        guild = self.bot.get_guild(serverid)
        role = guild.get_role(customroledata[str(user.id)])
        if role:
            await role.delete()
        del customroledata[str(user.id)]
        if not saveData("customroles", customroledata):
            await interaction.edit_original_response(content="An error occurred while saving custom role data.")
            return
        await interaction.edit_original_response(content=f"Custom role for {formatUsername(user)} has been removed.")

    @app_commands.command(name="editcustomrole", description="Edit your custom role here!")
    @app_commands.describe(name="The new name for your custom role.", color="The new color for your custom role (in hex, e.g. #ff0000), or 'none' to reset to default. (boring!)")
    async def editcustomrole(self, interaction: discord.Interaction, name: str, color: str):
        await interaction.response.defer(ephemeral=True)
        customroledata = loadData("customroles")
        if customroledata == "":
            await interaction.edit_original_response(content="An error occurred while loading custom role data.")
            return
        if str(interaction.user.id) not in customroledata:
            await interaction.edit_original_response(content="You do not have a custom role!")
            return
        guild = self.bot.get_guild(serverid)
        role = guild.get_role(customroledata[str(interaction.user.id)])
        if role:
            colorreal = None
            if color.lower() == "none":
                colorreal = discord.Color.default()
            try:
                colorreal = discord.Color.from_str(color)
            except ValueError:
                try:
                    colorreal = discord.Color.from_str(f"#{color}")
                except ValueError:
                    await interaction.edit_original_response(content="Invalid color format. Please provide a hex color code (e.g. #ff0000).")
                    return
            await role.edit(name=name, color=colorreal)
        if not saveData("customroles", customroledata):
            await interaction.edit_original_response(content="An error occurred while saving custom role data.")
            return
        await interaction.edit_original_response(content=f"Custom role for {formatUsername(interaction.user)} has been edited.")


async def setup(bot: commands.Bot):
    await bot.add_cog(CustomRoles(bot))
