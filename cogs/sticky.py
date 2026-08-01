import discord
from discord.ext import commands
from discord import app_commands

from common import loadData, saveData, etanid


class Sticky(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="sticky", description="Sets a sticky message in the current channel (owner only)")
    @app_commands.describe(message="The message to stick to the channel.")
    async def sticky(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You do not have permission to use this command.")
            return

        targetchannel = interaction.channel
        stickydata = loadData("sticky")
        if stickydata == "":
            await interaction.edit_original_response(content="Error loading sticky message data.")
            return

        oldentry = stickydata.get(str(targetchannel.id))
        if oldentry is not None:
            try:
                oldmessage = await targetchannel.fetch_message(oldentry["message_id"])
                await oldmessage.delete()
            except (discord.NotFound, discord.Forbidden):
                pass

        try:
            newmessage = await targetchannel.send(f"📌 **Sticky Message**\n{message}")
        except discord.Forbidden:
            await interaction.edit_original_response(content="I don't have permission to send messages in that channel.")
            return

        stickydata[str(targetchannel.id)] = {"message_id": newmessage.id, "content": message}
        saveData("sticky", stickydata)
        await interaction.edit_original_response(content=f"Sticky message set in {targetchannel.mention}.")

    @app_commands.command(name="removesticky", description="Removes the sticky message from the current channel (owner only)")
    async def removesticky(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You do not have permission to use this command.")
            return

        targetchannel = interaction.channel
        stickydata = loadData("sticky")
        if stickydata == "":
            await interaction.edit_original_response(content="Error loading sticky message data.")
            return

        entry = stickydata.pop(str(targetchannel.id), None)
        if entry is None:
            await interaction.edit_original_response(content=f"There is no sticky message set in {targetchannel.mention}.")
            return

        try:
            oldmessage = await targetchannel.fetch_message(entry["message_id"])
            await oldmessage.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

        saveData("sticky", stickydata)
        await interaction.edit_original_response(content=f"Sticky message removed from {targetchannel.mention}.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not isinstance(message.channel, discord.TextChannel):
            return

        stickydata = loadData("sticky")
        if stickydata == "":
            return

        entry = stickydata.get(str(message.channel.id))
        if entry is None:
            return

        try:
            oldmessage = await message.channel.fetch_message(entry["message_id"])
            await oldmessage.delete()
        except (discord.NotFound, discord.Forbidden):
            pass
        except Exception:
            return

        try:
            newmessage = await message.channel.send(f"📌 **Sticky Message**\n{entry['content']}")
        except (discord.Forbidden, discord.HTTPException):
            return

        stickydata[str(message.channel.id)] = {"message_id": newmessage.id, "content": entry["content"]}
        saveData("sticky", stickydata)


async def setup(bot: commands.Bot):
    await bot.add_cog(Sticky(bot))
