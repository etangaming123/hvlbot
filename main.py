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

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

COG_EXTENSIONS = [
    "cogs.moderation",
    "cogs.queueadmin",
    "cogs.admin",
    "cogs.customroles",
    "cogs.fun",
    "cogs.profiles",
    "cogs.achievements",
    "cogs.alts",
]

cogs_loaded = False

if not os.path.exists("env.json"):
    with open("env.json", "w") as file:
        json.dump({
            "token": "your_discord_bot_token_here",
            "openweatherapikey": "your_openweather_api_key_here",
            "fontpath": "path_to_a_font_file.ttf"
        }, file)
    input("env.json file not found. A sample one has been created, please fill it, then press enter to continue...")

env = json.load(open("env.json", "r"))

from common import *

# async functions
async def editQueueCheckMessage():
    channel = bot.get_channel(experimentalqueuecheckchannelid)
    try:
        message = await channel.fetch_message(queuecheckmessageid)
        await message.edit(content=f"{(playersplaying)} playing, {(playersinqueue)} in queue\nLast updated by {formatUsername(bot.get_user(userincontrol)) if userincontrol != 0 else 'no one'} {f'<t:{round(userlastbuttontime)}:R>' if userlastbuttontime != 0 else 'at an unknown time'}")
    except Exception as e:
        print(f"Error editing queue check message: {e}")

async def resetQueueCheckMessage():
    global playersinqueue, playersplaying, userincontrol, userlastbuttontime
    playersinqueue = 0
    playersplaying = 0
    userincontrol = 0
    userlastbuttontime = 0
    channel = bot.get_channel(experimentalqueuecheckchannelid)
    try:
        message = await channel.fetch_message(queuecheckmessageid)
        await message.edit(content=f"Awaiting queue action... [Queue check was reset <t:{round(time.time())}:R>]")
    except Exception as e:
        print(f"Error resetting queue check message: {e}")

def checkIfBannedFromQueueCheck(userId): # checks if user is banned from using queue check buttons
    bannedlist = loadData("bannedecqc")
    if bannedlist == "":
        print("Error loading banned list for queue check.")
        return False
    if userId in bannedlist:
        return True
    else:
        return False

async def experimentalQueueCheck(): # queue check for maimai. maimai is arcade rhythm game, only 2 people can play at once (at least in hurstville, things get complicated when there are multiple cabs)
    channel = bot.get_channel(experimentalqueuecheckchannelid)
    class queueCheckButtons(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="+1 queue", style=discord.ButtonStyle.green, custom_id="queuecheck_plus") # add one to queue
        async def queuecheck_plus(self, interaction: discord.Interaction, button: discord.ui.Button):
            if time.localtime().tm_hour < 9:
                await interaction.response.send_message(content=f"KOKO amusement Hurstville is currently closed, goodnight!", ephemeral=True)
                return
            if checkIfBannedFromQueueCheck(interaction.user.id):
                await interaction.response.send_message(content=f"You are either banned from using the queue buttons, or there was an error.", ephemeral=True)
                return
            global playersinqueue, userincontrol, userlastbuttontime, didwealreadyreset, userlastbuttontimebutmorepermanent
            didwealreadyreset = False
            if userincontrol != 0 and userincontrol != interaction.user.id and time.time() - userlastbuttontime < 60:
                await interaction.response.send_message(content=f"Someone else is currently controlling the queue.", ephemeral=True)
                return
            if playersinqueue == 9999:
                playersinqueue = 0
            playersinqueue += 1
            userincontrol = interaction.user.id
            userlastbuttontime = time.time()
            userlastbuttontimebutmorepermanent = time.time()
            await interaction.response.send_message(content=f"Queue count is now {playersinqueue}", ephemeral=True)
            await editQueueCheckMessage()

        @discord.ui.button(label="-1 queue", style=discord.ButtonStyle.red, custom_id="queuecheck_minus") # remove one from queue
        async def queuecheck_minus(self, interaction: discord.Interaction, button: discord.ui.Button):
            if time.localtime().tm_hour < 9:
                await interaction.response.send_message(content=f"KOKO amusement Hurstville is currently closed, goodnight!", ephemeral=True)
                return
            if checkIfBannedFromQueueCheck(interaction.user.id):
                await interaction.response.send_message(content=f"You are either banned from using the queue buttons, or there was an error.", ephemeral=True)
                return
            global playersinqueue, userincontrol, userlastbuttontime, didwealreadyreset, userlastbuttontimebutmorepermanent
            didwealreadyreset = False
            if userincontrol != 0 and userincontrol != interaction.user.id and time.time() - userlastbuttontime < 60:
                await interaction.response.send_message(content=f"Someone else is currently controlling the queue.", ephemeral=True)
                return
            if playersinqueue == 9999:
                playersinqueue = 0
            playersinqueue -= 1
            if playersinqueue < 0:
                playersinqueue = 0
            userincontrol = interaction.user.id
            userlastbuttontimebutmorepermanent = time.time()
            userlastbuttontime = time.time()
            await interaction.response.send_message(content=f"Queue count is now {playersinqueue}", ephemeral=True)
            await editQueueCheckMessage()
        
        @discord.ui.button(label="1 playing", style=discord.ButtonStyle.gray, custom_id="one_playing") # move one from queue to playing
        async def one_playing(self, interaction: discord.Interaction, button: discord.ui.Button):
            if time.localtime().tm_hour < 9:
                await interaction.response.send_message(content=f"KOKO amusement Hurstville is currently closed, goodnight!", ephemeral=True)
                return
            if checkIfBannedFromQueueCheck(interaction.user.id):
                await interaction.response.send_message(content=f"You are either banned from using the queue buttons, or there was an error.", ephemeral=True)
                return
            global playersplaying, playersinqueue, userincontrol, userlastbuttontime, didwealreadyreset, userlastbuttontimebutmorepermanent
            didwealreadyreset = False
            if userincontrol != 0 and userincontrol != interaction.user.id and time.time() - userlastbuttontime < 60:
                await interaction.response.send_message(content=f"Someone else is currently controlling the queue.", ephemeral=True)
                return
            playersplaying = 1
            playersinqueue -= playersplaying
            if playersinqueue < 0:
                playersinqueue = 0
            userincontrol = interaction.user.id
            userlastbuttontime = time.time()
            userlastbuttontimebutmorepermanent = time.time()
            await interaction.response.send_message(content=f"{playersplaying} player is on", ephemeral=True)
            await editQueueCheckMessage()
        
        @discord.ui.button(label="2 playing", style=discord.ButtonStyle.gray, custom_id="two_playing") # move two from queue to playing
        async def two_playing(self, interaction: discord.Interaction, button: discord.ui.Button):
            if time.localtime().tm_hour < 9:
                await interaction.response.send_message(content=f"KOKO amusement Hurstville is currently closed, goodnight!", ephemeral=True)
                return
            if checkIfBannedFromQueueCheck(interaction.user.id):
                await interaction.response.send_message(content=f"You are either banned from using the queue buttons, or there was an error.", ephemeral=True)
                return
            global playersplaying, playersinqueue, userincontrol, userlastbuttontime, didwealreadyreset, userlastbuttontimebutmorepermanent
            didwealreadyreset = False
            if userincontrol != 0 and userincontrol != interaction.user.id and time.time() - userlastbuttontime < 60:
                await interaction.response.send_message(content=f"Someone else is currently controlling the queue.", ephemeral=True)
                return
            playersplaying = 2
            playersinqueue -= playersplaying
            if playersinqueue < 0:
                playersinqueue = 0
            userincontrol = interaction.user.id
            userlastbuttontime = time.time()
            userlastbuttontimebutmorepermanent = time.time()
            await interaction.response.send_message(content=f"{playersplaying} players are on", ephemeral=True)
            await editQueueCheckMessage()
        
        @discord.ui.button(label="Game end, no fallback", style=discord.ButtonStyle.red, custom_id="game_end") # remove all from playing
        async def game_end(self, interaction: discord.Interaction, button: discord.ui.Button):
            if time.localtime().tm_hour < 9:
                await interaction.response.send_message(content=f"KOKO amusement Hurstville is currently closed, goodnight!", ephemeral=True)
                return
            if checkIfBannedFromQueueCheck(interaction.user.id):
                await interaction.response.send_message(content=f"You are either banned from using the queue buttons, or there was an error.", ephemeral=True)
                return
            global playersplaying, playersinqueue, userincontrol, userlastbuttontime, didwealreadyreset, userlastbuttontimebutmorepermanent
            didwealreadyreset = False
            if userincontrol != 0 and userincontrol != interaction.user.id and time.time() - userlastbuttontime < 60:
                await interaction.response.send_message(content=f"Someone else is currently controlling the queue.", ephemeral=True)
                return
            if playersplaying == 9999 or playersplaying == 0:
                await interaction.response.send_message(content=f"No players are currently playing.", ephemeral=True)
                return
            userincontrol = interaction.user.id
            userlastbuttontime = time.time()
            userlastbuttontimebutmorepermanent = time.time()
            await interaction.response.send_message(content=f"{playersplaying} players have left (and have not rejoined queue)", ephemeral=True)
            playersplaying = 0
            await editQueueCheckMessage()
        
        @discord.ui.button(label="Game end, fallback to queue", style=discord.ButtonStyle.green, custom_id="game_end_fallback") # move all from playing back to queue
        async def game_end_fallback(self, interaction: discord.Interaction, button: discord.ui.Button):
            if time.localtime().tm_hour < 9:
                await interaction.response.send_message(content=f"KOKO amusement Hurstville is currently closed, goodnight!", ephemeral=True)
                return
            if checkIfBannedFromQueueCheck(interaction.user.id):
                await interaction.response.send_message(content=f"You are either banned from using the queue buttons, or there was an error.", ephemeral=True)
                return
            global playersplaying, playersinqueue, userincontrol, userlastbuttontime, didwealreadyreset, userlastbuttontimebutmorepermanent
            didwealreadyreset = False
            if userincontrol != 0 and userincontrol != interaction.user.id and time.time() - userlastbuttontime < 60:
                await interaction.response.send_message(content=f"Someone else is currently controlling the queue.", ephemeral=True)
                return
            if playersplaying == 9999 or playersplaying == 0:
                await interaction.response.send_message(content=f"No players are currently playing.", ephemeral=True)
                return
            if playersinqueue == 9999:
                playersinqueue = 0
            playersinqueue += playersplaying
            userincontrol = interaction.user.id
            userlastbuttontime = time.time()
            userlastbuttontimebutmorepermanent = time.time()
            await interaction.response.send_message(content=f"{playersplaying} players have rejoined queue, queue is now {playersinqueue}", ephemeral=True)
            playersplaying = 0
            await editQueueCheckMessage()
        
        @discord.ui.button(label="End Button Ownership", style=discord.ButtonStyle.red, custom_id="end_ownership") # if user has control of queue and wishes to prematurely end it, this function exists
        async def end_ownership(self, interaction: discord.Interaction, button: discord.ui.Button):
            global userincontrol, userlastbuttontime, didwealreadyreset
            didwealreadyreset = False

            if userincontrol != interaction.user.id:
                await interaction.response.send_message(content=f"You do not currently have control of the queue.", ephemeral=True)
                return
            userincontrol = 0
            userlastbuttontime = 0
            await interaction.response.send_message(content=f"Queue buttons are now active for everyone.", ephemeral=True)

    view = queueCheckButtons()
    oldmessages = [message async for message in channel.history(limit=2)]
    for message in oldmessages:
        if message.author.id == bot.user.id:
            await message.delete()
    message = await channel.send(content=f"Awaiting queue action... [Bot has just started up]", view=view)
    global queuecheckmessageid
    queuecheckmessageid = message.id

# bot tasks
@tasks.loop(minutes=1)
async def weatherUpdate():
    global lastcachedmembercount # weatherupdate includes this as well cuz discord.py doesn't allow multiple tasks THAT TOOK AGES TO FIND OUT LMAO
    global didwealreadyreset, didwealreadyresetanditsnight
    guild = bot.get_guild(serverid) # putting this here cuz idk if discord.py allows one task. if it does im gonna crashout cuz that shit took AGES // hi etan it did

    leesto = [0, 10, 20, 30, 40, 50] # this is probably the worst way to do it
    if time.localtime().tm_min in leesto: # only run at an interval of 10 minutes, in theory
        altaccounts = loadData("alts")
        if altaccounts != "": # we only update member count if we can read the alts data
            altcount = 0
            for _, altlist in altaccounts.items():
                altcount += len(altlist)
            membercountchannel = guild.get_channel(membercountid)
            realmembercount = guild.member_count - sum(1 for member in guild.members if member.bot) - altcount # alternate accounts should not be included in the member count
            if lastcachedmembercount != realmembercount:
                lastcachedmembercount = realmembercount
                await membercountchannel.edit(name=f"Members: {realmembercount}")
        
        await bot.change_presence(activity=discord.Game(prescencecycles[random.randint(0, len(prescencecycles) - 1)]), status=discord.Status.online)

        bottraprole = guild.get_role(bottraproleid)
        loggus = bot.get_channel(messageloggingchannelid)
        for member in guild.members:
            if bottraprole in member.roles:
                try:
                    await guild.ban(member, delete_message_days=1, reason="Assigned bot trap role.")
                    await loggus.send(f"Banned {formatUsername(member)} for having bot trap role.")
                except discord.Forbidden:
                    await loggus.send(f"Failed to ban {formatUsername(member)} for having bot trap role.")
                    print(f"Failed to ban member: {member.name}")

    if time.localtime().tm_hour == 0 and didwealreadyresetanditsnight == False:
        didwealreadyresetanditsnight = True
        await resetQueueCheckMessage()
    else:   
        didwealreadyresetanditsnight = False

    if time.time() - userlastbuttontimebutmorepermanent > 7200 and didwealreadyreset == False:  # 2 hours, i think
        await resetQueueCheckMessage()
        didwealreadyreset = True

    try:
        if time.localtime().tm_hour < 6 or time.localtime().tm_hour == 0:
            return # only post weather updates between 6am and 12 midnight inclusive
        if time.localtime().tm_min != 0:
            return # only post weather updates at the start of the hour
        response = requests.get(f"https://api.openweathermap.org/data/2.5/weather?lat=-33.968109&lon=151.104080&appid={openweatherapikey}&units=metric")
        data = response.json()
        if response.status_code == 200:
            string = f"# Weather Update [ <t:{int(time.time())}:F> ]\nWeather: {data['weather'][0]['main']} // {data['weather'][0]['description']}\nTemperature: {data['main']['temp']}°C\nFeels Like: {data['main']['feels_like']}°C\nHumidity: {data['main']['humidity']}%"
            if 'rain' in data['weather'][0]['main'].lower():
                string += f"\nRain Volume (last 1h): {data['rain']['1h']}mm"
            channel = bot.get_channel(weatherannouncementschannelid)
            message = await channel.send(string)
            await message.publish()
        else:
            print(f"Failed to fetch weather data. Status code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Error occurred while fetching weather data: {e}")

class HVLBot(commands.Bot):
    async def setup_hook(self):
        await self.load_extension("cogs.moderation.py")

# bot events
@bot.event
async def on_message_delete(message):
    if message.author.bot == False:
        channel = bot.get_channel(messageloggingchannelid)
        embed = discord.Embed(title="Message Deleted", description=f"Message from {formatUsername(message.author)} in {message.channel.mention}", color=discord.Color.red())
        embed.add_field(name="Content", value=truncateMessage(message.content, 1024) if message.content else "No content", inline=False)
        embed.add_field(name="Attachments", value=f"{len(message.attachments)} attachment(s)" if message.attachments else "No attachments", inline=False)
        embed.add_field(name="Attachment URLs", value="\n".join([attachment.url for attachment in message.attachments]) if message.attachments else "No attachments", inline=False)
        embed.set_image(url=message.attachments[0].url if message.attachments else None)
        await channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot == False and before.content != after.content:
        channel = bot.get_channel(messageloggingchannelid)
        embed = discord.Embed(title="Message Edited", description=f"Message from {formatUsername(before.author)} in {before.channel.mention}", color=discord.Color.orange())
        embed.add_field(name="Before", value=truncateMessage(before.content, 1024) if before.content else "No content", inline=False)
        embed.add_field(name="After", value=truncateMessage(after.content, 1024) if after.content else "No content", inline=False)
        await channel.send(embed=embed)

@bot.event
async def on_ready():
    global cogs_loaded
    print("Loading, please wait...")
    await bot.wait_until_ready()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    if not cogs_loaded:
        for extension in COG_EXTENSIONS:
            await bot.load_extension(extension)
        cogs_loaded = True
    await experimentalQueueCheck()
    await bot.tree.sync()
    if not weatherUpdate.is_running():
        weatherUpdate.start()
    print("Bot is ready!")

@bot.event
async def on_member_join(member):
    channel = bot.get_channel(joinandleavechannelid)
    await channel.send(f"[+] Welcome {member.mention} to the server!")
    for _, altlist in loadData("alts").items():
        if str(member.id) in altlist:
            await member.add_roles(member.guild.get_role(altaccountroleid))
            return
    await member.add_roles(member.guild.get_role(memberroleid))

@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(joinandleavechannelid)
    await channel.send(f"[-] {formatUsername(member)} has left the server.")

@bot.event
async def on_raw_reaction_add(payload): # starboard function
    message = await bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
    reaction = discord.utils.get(message.reactions, emoji="⭐")
    starboarddata = loadData("starboard")
    if starboarddata == "":
        print("Error loading starboard data.")
        return
    if message.id in starboarddata:
        return
    if message.channel.id == starboardchannel:
        return
    if reaction and reaction.count >= 3:
        channel = bot.get_channel(starboardchannel)
        embed = discord.Embed(title="Starred Message", description=f"Message from {formatUsername(message.author)} in {message.channel.mention}", color=discord.Color.gold(), timestamp=message.created_at)
        embed.add_field(name="Content", value=truncateMessage(message.content, 1024) if message.content else "No content", inline=False)
        embed.add_field(name="Attachments", value=f"{len(message.attachments)} attachment(s)" if message.attachments else "No attachments", inline=False)
        embed.add_field(name="Attachment URLs", value="\n".join([attachment.url for attachment in message.attachments]) if message.attachments else "No attachments", inline=False)
        embed.add_field(name="Jump Link", value=f"[Click here to jump to the message]({message.jump_url})", inline=False)
        embed.set_image(url=message.attachments[0].url if message.attachments else None)
        embed.set_footer(text=f"Starboard is a beta feature! Please report bugs to etangaming123.")
        starboarddata.append(message.id)
        saveData("starboard", starboarddata)
        await channel.send(embed=embed)

# alt account punishment linking (to avoid evasion)
@bot.event
async def on_ban(guild, user):
    if guild.id == serverid:
        everyuser = returnAllAlts(user.id)
        loggingchannelreal = bot.get_channel(messageloggingchannelid)
        for userid in everyuser:
            if userid == str(user.id): # ignore the original banned account (because it's already banned)
                continue
            try:
                await loggingchannelreal.send(f"Also banning alt account with ID {userid} for user {formatUsername(user)} (ID: {user.id})")
                await guild.ban(discord.Object(id=int(userid)), delete_message_days=1)
            except Exception:
                await loggingchannelreal.send(f"Failed to ban alt account with ID {userid} for user {formatUsername(user)} (ID: {user.id})")

@bot.event
async def on_timeout(guild, user):
    if guild.id == serverid:
        everyuser = returnAllAlts(user.id)
        loggingchannelreal = bot.get_channel(messageloggingchannelid)
        for userid in everyuser:
            if userid == str(user.id): # ignore the original timed out account (because it's already timed out)
                continue
            try:
                await loggingchannelreal.send(f"Also timing out alt account [1 hour] with ID {userid} for user {formatUsername(user)} (ID: {user.id})")
                await guild.timeout(discord.Object(id=int(userid)), duration=3600) # 1 hour timeout for alt accounts, to prevent punishment evasion by messaging on alt
            except Exception:
                await loggingchannelreal.send(f"Failed to time out alt account with ID {userid} for user {formatUsername(user)} (ID: {user.id})")

@bot.event
async def on_message(message):
    if message.author.bot: # ignore bot actions
        return
    if isinstance(message.channel, discord.DMChannel): # log dms
        channel = bot.get_channel(SUPASECRETLOGGINGCHANNELID)
        embed = discord.Embed(title="DM Received", description=f"DM from {formatUsername(message.author)}", color=discord.Color.blue())
        embed.add_field(name="Content", value=truncateMessage(message.content, 1024) if message.content else "No content", inline=False)
        embed.add_field(name="Attachments", value=f"{len(message.attachments)} attachment(s)" if message.attachments else "No attachments", inline=False)
        embed.add_field(name="Attachment URLs", value="\n".join([attachment.url for attachment in message.attachments]) if message.attachments else "No attachments", inline=False)
        embed.set_image(url=message.attachments[0].url if message.attachments else None)
        await channel.send(embed=embed)
        return
    if message.channel.id == bottrapchannelid: # ban those who send messages in the oh so obvious trap
        lchannelreal = bot.get_channel(messageloggingchannelid)
        try:
            await message.author.ban(delete_message_days=1)
        except discord.Forbidden:
            await message.delete()
            await lchannelreal.send(f"sum bot known as {formatUsername(message.author)} fell for the trap but i couldn't ban them...")
            return
        await lchannelreal.send(f"dumbass bot by the name {formatUsername(message.author)} fell for the trap")
        return
    
    if message.content == "r>quote": # i have no idea how this works
        await message.channel.typing()
        if not message.reference or not message.reference.resolved:
            await message.channel.send("Please reply to a message to quote someone!", reference=message, mention_author=False)
            return
        original_message = message.reference.resolved
        if not hasattr(original_message.author, "display_avatar") or not original_message.author.display_avatar:
            await message.channel.send("The original author has no profile picture!", reference=message, mention_author=False) # sorry default pfp users
            return
        try:
            W, H = 1200, 630

            # Download avatar
            async with aiohttp.ClientSession() as session:
                async with session.get(original_message.author.display_avatar.url) as resp:
                    avatar_bytes = await resp.read()
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")

            # Black background
            img = Image.new('RGB', (W, H), (0, 0, 0))

            # Radial spotlight gradient with user's role color
            y_coords, x_coords = np.mgrid[0:H, 0:W]
            cx, cy = W // 4, H // 2
            max_r = H * 0.78
            dist = np.sqrt((x_coords - cx) ** 2 + (y_coords - cy) ** 2)
            brightness = np.clip(1.0 - dist / max_r, 0, 1) ** 0.55
            brightness = (brightness * 255).astype(np.uint8)
            
            # Get user's role color, default to white
            role_color = (255, 255, 255)  # white default
            availablecolors = []
            for role in original_message.author.roles:
                if role.color.value != 0:
                    availablecolors.append(role.color.to_rgb())
            availablecolors.reverse() # reverse so higher roles take precedence
            if availablecolors: 
                role_color = availablecolors[0]            
            # Apply color to gradient
            brightness_f = brightness.astype(np.float32)
            r = (brightness_f * role_color[0] / 255).astype(np.uint8)
            g = (brightness_f * role_color[1] / 255).astype(np.uint8)
            b = (brightness_f * role_color[2] / 255).astype(np.uint8)
            gradient = Image.fromarray(np.stack([r, g, b], axis=2), 'RGB')
            img.paste(gradient, (0, 0), Image.fromarray(brightness))

            # Circular avatar
            av_size = 300
            avatar_img = avatar_img.resize((av_size, av_size), Image.LANCZOS)
            mask = Image.new('L', (av_size, av_size), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, av_size - 1, av_size - 1], fill=255)
            ax, ay = cx - av_size // 2, cy - av_size // 2
            img.paste(avatar_img.convert('RGB'), (ax, ay), mask)

            draw = ImageDraw.Draw(img)

            FONT_PATH = env["fontpath"]

            # Fonts
            try:
                font_name     = ImageFont.truetype(FONT_PATH, 38)
                font_username = ImageFont.truetype(FONT_PATH, 28)
                font_wm       = ImageFont.truetype(FONT_PATH, 20)
            except Exception:
                font_name = font_username = font_wm = ImageFont.load_default()

            # Text area: right half
            tx, ty_pad = W // 2 + 30, 40
            text_w = W - tx - ty_pad

            # Truncate message if too long (e.g. > 200 chars)
            max_chars = 200
            quote_text = original_message.content
            if len(quote_text) > max_chars:
                quote_text = quote_text[:max_chars] + f"... [{len(quote_text)-max_chars} more characters]"

            def wrap_text(text, font, max_width):
                words = text.split()
                lines, line = [], ""
                for word in words:
                    # Break word character-by-character if it alone exceeds max_width
                    if draw.textbbox((0, 0), word, font=font)[2] > max_width:
                        if line:
                            lines.append(line)
                            line = ""
                        chunk = ""
                        for ch in word:
                            if draw.textbbox((0, 0), chunk + ch, font=font)[2] <= max_width:
                                chunk += ch
                            else:
                                lines.append(chunk)
                                chunk = ch
                        word = chunk  # remainder treated as normal word
                    test = (line + " " + word).strip()
                    if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
                        line = test
                    else:
                        if line:
                            lines.append(line)
                        line = word
                if line:
                    lines.append(line)
                return lines

            # Dynamically shrink font until the wrapped text fits vertically
            max_text_h = H - 80 - (font_name.size + 8) - font_username.size - 20
            font_size = 62
            while font_size >= 16:
                try:
                    font_quote = ImageFont.truetype(FONT_PATH, font_size)
                except Exception:
                    font_quote = ImageFont.load_default()
                quote_lines = wrap_text(quote_text, font_quote, text_w)
                lh = int(font_size * 1.25)
                if len(quote_lines) * lh <= max_text_h:
                    break
                font_size -= 2

            lh = int(font_size * 1.25)
            total_q_h = len(quote_lines) * lh
            name_h = font_name.size + 8
            uname_h = font_username.size
            total_h = total_q_h + name_h + uname_h + 20
            start_y = (H - total_h) // 2

            # Quote lines (centered in text area)
            for i, line in enumerate(quote_lines):
                lw = draw.textbbox((0, 0), line, font=font_quote)[2]
                draw.text((tx + (text_w - lw) // 2, start_y + i * lh), line, fill=(255, 255, 255), font=font_quote)

            y = start_y + total_q_h + 10

            # "- DisplayName"
            dname = f"- {getDisplay(original_message.author)}"
            dw = draw.textbbox((0, 0), dname, font=font_name)[2]
            draw.text((tx + (text_w - dw) // 2, y), dname, fill=(255, 255, 255), font=font_name)
            y += name_h

            # "@username"
            uname = f"@{original_message.author.name}"
            uw = draw.textbbox((0, 0), uname, font=font_username)[2]
            draw.text((tx + (text_w - uw) // 2, y), uname, fill=(160, 160, 160), font=font_username)

            # Watermark bottom-right
            wm = f"rui kamishiro // coded by etangaming123 // join at hvl.etangaming.xyz"
            draw.text((W - 12, H - 12), wm, fill=(90, 90, 90), font=font_wm, anchor="rb")

            # Save and send
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            buffered.seek(0)
            await message.channel.send(file=discord.File(buffered, filename="quote.png"), reference=message, mention_author=False)
        except Exception as e: # FAH
            traceback.print_exc()
            await message.channel.send(f"Error creating quote image: {str(e)}", reference=message, mention_author=False)


bot.run(env["token"])
