import discord
from discord.ext import commands
from discord import app_commands
import traceback
import json
import io

from common import experimentalqueuecheckchannelid, formatUsername, loadData, saveData, truncateMessage, returnAllAlts, serverid, etanid, membercountid, bottraproleid, messageloggingchannelid, weatherannouncementschannelid, returnAllAlts, formatUsername, loadData, saveData, truncateMessage, prescencecycles, openweatherapikey, lastcachedmembercount, didwealreadyreset, didwealreadyresetanditsnight, userlastbuttontimebutmorepermanent, memberroleid, altaccountroleid, ruiroleid, joinandleavechannelid, SUPASECRETLOGGINGCHANNELID, moderatorroleid, moderatorplusplusroleid, channelstolockdown, bottrapchannelid, weatherannouncementschannelid, experimentalqueuecheckchannelid, playersinqueue, playersplaying, userincontrol, userlastbuttontime, getDisplay, env, starboardchannel



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

    @app_commands.command(name="say-file", description="same as /say but with a file, so you can send files")
    @app_commands.describe(file="The file to send.")
    async def say_file(self, interaction: discord.Interaction, file: discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You do not have permission to use this command.")
            return
        try:
            await interaction.channel.send(file=await file.to_file())
        except Exception as e:
            await interaction.edit_original_response(content=f"Failed to send file: {e}")
            traceback.print_exc()
            return
        await interaction.edit_original_response(content="Done!")

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

    @app_commands.command(name="export-dms", description="Export the bot's DM history with a user (admin only)")
    @app_commands.describe(
        user="The user whose DMs to export.",
        format="json = full history, no limit. text = last few messages, fit into one 2000 char message.",
        count="Text mode only: how many recent messages to try to fit (default 20, max 100).",
    )
    @app_commands.choices(format=[
        app_commands.Choice(name="JSON file (full history)", value="json"),
        app_commands.Choice(name="Text message (recent messages)", value="text"),
    ])
    async def export_dms(self, interaction: discord.Interaction, user: discord.User, format: app_commands.Choice[str], count: int = 20):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You do not have permission to use this command.")
            return

        try:
            dm = await user.create_dm()
        except discord.Forbidden:
            await interaction.edit_original_response(content="Failed to open a DM channel with that user.")
            return

        try:
            if format.value == "json":
                messages = []
                async for msg in dm.history(limit=None, oldest_first=True):
                    messages.append({
                        "id": msg.id,
                        "author_id": msg.author.id,
                        "author": formatUsername(msg.author),
                        "is_bot": msg.author.id == self.bot.user.id,
                        "timestamp": msg.created_at.isoformat(),
                        "content": msg.content,
                        "attachments": [a.url for a in msg.attachments],
                        "embeds": [e.to_dict() for e in msg.embeds],
                    })
                data = json.dumps(messages, indent=2, ensure_ascii=False)
                file = discord.File(io.BytesIO(data.encode("utf-8")), filename=f"dms_{user.id}.json")
                await interaction.edit_original_response(content=f"Exported {len(messages)} messages with {formatUsername(user)}.", attachments=[file])
                return

            # text mode
            count = max(1, min(count, 100))
            recent = [msg async for msg in dm.history(limit=count, oldest_first=False)]
            recent.reverse()

            lines = []
            for msg in recent:
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M")
                line = f"**{formatUsername(msg.author)}** [{ts}]: {msg.content}"
                if msg.attachments:
                    line += " " + " ".join(a.url for a in msg.attachments)
                lines.append(line)

            header = f"DM log with {formatUsername(user)} (most recent messages that fit):\n"
            body_lines = []
            total_len = len(header)
            for line in reversed(lines):
                if total_len + len(line) + 1 > 2000:
                    break
                body_lines.insert(0, line)
                total_len += len(line) + 1

            if not body_lines:
                await interaction.edit_original_response(content="No messages fit within Discord's 2000 character limit.")
                return

            await interaction.edit_original_response(content=header + "\n".join(body_lines))
        except Exception as e:
            await interaction.edit_original_response(content=f"Failed to export DMs: {e}")
            traceback.print_exc()


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
