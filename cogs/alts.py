import discord
from discord.ext import commands
from discord import app_commands

from common import *


class Alts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="list-alts", description="Check if a user has any alts linked to their account!")
    @app_commands.describe(user="The user to check for linked alts.")
    async def whois(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer(ephemeral=True)
        altlinks = loadData("alts")
        if altlinks == "":
            await interaction.edit_original_response(content="An error occurred while loading alt account data.")
            return

        linked_alts = altlinks.get(str(user.id), [])
        if linked_alts:
            alt_usernames = [f"<@{alt}>" for alt in linked_alts]
            await interaction.edit_original_response(content=f"{formatUsername(user)} has the following alt accounts linked: {', '.join(alt_usernames)}")
            return

        for ownerid, alts in altlinks.items():
            if str(user.id) in alts:
                await interaction.edit_original_response(content=f"{formatUsername(user)} is an alt account linked to <@{ownerid}>.")
                return

        await interaction.edit_original_response(content=f"{formatUsername(user)} does not have any linked alt accounts.")

    @app_commands.command(name="link-alt", description="Link an alt account to a main account. (owner only)")
    @app_commands.describe(mainaccount="The main account to link to.", altaccount="The alt account to link by user ID.")
    async def linkalt(self, interaction: discord.Interaction, mainaccount: discord.User, altaccount: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You don't have permission to use this command!")
            return

        altlinks = loadData("alts")
        if altlinks == "":
            await interaction.edit_original_response(content="An error occurred while loading alt account data.")
            return
        if str(altaccount) in altlinks:
            await interaction.edit_original_response(content="That alt account is already linked to a main account.")
            return

        if str(mainaccount.id) not in altlinks:
            altlinks[str(mainaccount.id)] = []
        altlinks[str(mainaccount.id)].append(str(altaccount))

        if not saveData("alts", altlinks):
            await interaction.edit_original_response(content="An error occurred while saving alt account data.")
            return

        await interaction.edit_original_response(content=f"Linked <@{altaccount}> as an alt of <@{mainaccount.id}> successfully!")

    @app_commands.command(name="unlink-alt", description="Unlink an alt account from its main account. (owner only)")
    @app_commands.describe(altaccount="The alt account to unlink by user ID.")
    async def unlinkalt(self, interaction: discord.Interaction, altaccount: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You don't have permission to use this command!")
            return

        altlinks = loadData("alts")
        if altlinks == "":
            await interaction.edit_original_response(content="An error occurred while loading alt account data.")
            return

        for alts in altlinks.values():
            if str(altaccount) in alts:
                break
        else:
            await interaction.edit_original_response(content="That alt account is not linked to any main account.")
            return

        for mainaccount_id, alt_list in list(altlinks.items()):
            if str(altaccount) in alt_list:
                alt_list.remove(str(altaccount))
                if not alt_list:
                    del altlinks[mainaccount_id]
                break

        if not saveData("alts", altlinks):
            await interaction.edit_original_response(content="An error occurred while saving alt account data.")
            return

        await interaction.edit_original_response(content=f"Unlinked <@{altaccount}> from its main account successfully!")


async def setup(bot: commands.Bot):
    await bot.add_cog(Alts(bot))
