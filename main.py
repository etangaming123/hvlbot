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
import re
import emoji as emojilib
from fontTools.ttLib import TTFont

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
    "cogs.sticky",
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

from common import experimentalqueuecheckchannelid, formatUsername, loadData, saveData, truncateMessage, returnAllAlts, serverid, etanid, membercountid, bottraproleid, messageloggingchannelid, weatherannouncementschannelid, returnAllAlts, formatUsername, loadData, saveData, truncateMessage, prescencecycles, openweatherapikey, lastcachedmembercount, didwealreadyreset, didwealreadyresetanditsnight, userlastbuttontimebutmorepermanent, memberroleid, altaccountroleid, ruiroleid, joinandleavechannelid, SUPASECRETLOGGINGCHANNELID, moderatorroleid, moderatorplusplusroleid, channelstolockdown, bottrapchannelid, weatherannouncementschannelid, experimentalqueuecheckchannelid, playersinqueue, playersplaying, userincontrol, userlastbuttontime, getDisplay, env, starboardchannel

blacklistedterms = ["m>info", "m>scores"]
didblacklistedtermgetrecieved = False

# ---- quote command helpers ----

MENTION_RE = re.compile(r"<@!?(\d+)>|<@&(\d+)>|<#(\d+)>")
CUSTOM_EMOJI_RE = re.compile(r"<(a?):(\w+):(\d+)>")

FALLBACK_FONT_PATHS = env.get("fallbackfontpaths", [
    r"C:\Windows\Fonts\seguisym.ttf",  # Segoe UI Symbol: broad symbol/script coverage
    r"C:\Windows\Fonts\msyh.ttc",      # Microsoft YaHei: Chinese
    r"C:\Windows\Fonts\malgun.ttf",    # Malgun Gothic: Korean
    r"C:\Windows\Fonts\meiryo.ttc",    # Meiryo: Japanese
    r"C:\Windows\Fonts\arial.ttf",     # Arial: broad Latin/Cyrillic/Greek fallback
])

_cmap_cache = {}
_font_obj_cache = {}
_emoji_img_cache = {}

def fontHasGlyph(path, ch):
    if ch.isspace():
        return True
    if path not in _cmap_cache:
        try:
            ttf = TTFont(path, lazy=True)
            cmap = ttf.getBestCmap() or {}
            ttf.close()
            _cmap_cache[path] = cmap
        except Exception:
            traceback.print_exc()
            return False  # don't cache the failure; retry next time in case it was transient
    return ord(ch) in _cmap_cache[path]

def choosePathForChar(ch, primary_path):
    if fontHasGlyph(primary_path, ch):
        return primary_path
    for fp in FALLBACK_FONT_PATHS:
        if os.path.exists(fp) and fontHasGlyph(fp, ch):
            return fp
    return primary_path  # last resort: may render as tofu, better than crashing

def getFontObj(path, size):
    key = (path, size)
    if key not in _font_obj_cache:
        try:
            _font_obj_cache[key] = ImageFont.truetype(path, size)
        except Exception:
            traceback.print_exc()
            return ImageFont.load_default()  # don't cache the failure; retry next time in case it was transient
    return _font_obj_cache[key]

def buildRuns(word, size, primary_path):
    # split a word into (text, font) runs so mixed-script words each render with a font that has the glyphs
    runs = []
    cur_path, cur_text = None, ""
    for ch in word:
        path = choosePathForChar(ch, primary_path)
        if path == cur_path:
            cur_text += ch
        else:
            if cur_text:
                runs.append((cur_text, getFontObj(cur_path, size)))
            cur_path, cur_text = path, ch
    if cur_text:
        runs.append((cur_text, getFontObj(cur_path, size)))
    return runs

def resolveMentions(text, message):
    def repl(m):
        if m.group(1):
            uid = int(m.group(1))
            user = discord.utils.get(message.mentions, id=uid) or (message.guild.get_member(uid) if message.guild else None)
            return f"@{getDisplay(user)}" if user else "@unknown-user"
        if m.group(2):
            rid = int(m.group(2))
            role = discord.utils.get(message.role_mentions, id=rid) or (message.guild.get_role(rid) if message.guild else None)
            return f"@{role.name}" if role else "@unknown-role"
        if m.group(3):
            cid = int(m.group(3))
            chan = discord.utils.get(message.channel_mentions, id=cid) or (message.guild.get_channel(cid) if message.guild else None)
            return f"#{chan.name}" if chan else "#unknown-channel"
    return MENTION_RE.sub(repl, text)

def findEmojiSpans(text):
    spans = [(m.start(), m.end(), "custom", {"animated": bool(m.group(1)), "name": m.group(2), "id": m.group(3)}) for m in CUSTOM_EMOJI_RE.finditer(text)]
    spans += [(e["match_start"], e["match_end"], "unicode", {"char": e["emoji"]}) for e in emojilib.emoji_list(text)]
    spans.sort(key=lambda s: s[0])
    filtered, last_end = [], 0
    for s in spans:
        if s[0] >= last_end:
            filtered.append(s)
            last_end = s[1]
    return filtered

def safeTruncate(text, max_chars):
    if len(text) <= max_chars:
        return text, 0
    cut = max_chars
    for start, end, _, _ in findEmojiSpans(text):
        if start < cut < end:
            cut = start
    return text[:cut], len(text) - cut

def tokenizeContent(text):
    spans = findEmojiSpans(text)
    tokens, pos = [], 0
    for start, end, kind, data in spans:
        if start > pos:
            tokens.append(("text", text[pos:start]))
        tokens.append((kind, data))
        pos = end
    if pos < len(text):
        tokens.append(("text", text[pos:]))
    atoms = []
    for kind, data in tokens:
        if kind == "text":
            atoms.extend(("word", w) for w in data.split())
        else:
            atoms.append((kind, data))
    return atoms

async def fetchEmojiImage(session, kind, data, size):
    cache_key = (kind, data.get("id") or data.get("char"))
    if cache_key not in _emoji_img_cache:
        raw_img = None
        try:
            if kind == "custom":
                ext = "gif" if data["animated"] else "png"
                async with session.get(f"https://cdn.discordapp.com/emojis/{data['id']}.{ext}") as resp:
                    if resp.status == 200:
                        raw_img = Image.open(io.BytesIO(await resp.read()))
                        raw_img.seek(0)  # first frame if animated
                        raw_img = raw_img.convert("RGBA")
            else:
                codepoints_variants = {
                    "-".join(f"{ord(c):x}" for c in data["char"] if ord(c) != 0xFE0F),
                    "-".join(f"{ord(c):x}" for c in data["char"]),
                }
                for cps in codepoints_variants:
                    async with session.get(f"https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/72x72/{cps}.png") as resp:
                        if resp.status == 200:
                            raw_img = Image.open(io.BytesIO(await resp.read())).convert("RGBA")
                            break
        except Exception:
            raw_img = None
        _emoji_img_cache[cache_key] = raw_img
    raw_img = _emoji_img_cache[cache_key]
    return raw_img.resize((size, size), Image.LANCZOS) if raw_img else None

# ---- end quote command helpers ----

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
    global didblacklistedtermgetrecieved
    if message.author.id == 604641359416131585 and didblacklistedtermgetrecieved:
        await message.delete()
        didblacklistedtermgetrecieved = False

    if message.author.id == 1171629295467253806:
        for item in blacklistedterms:
            if item in message.content.lower():
                await message.delete()
                didblacklistedtermgetrecieved = True

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

    if message.content[:7] == "r>quote" or message.content[:7] == "r>qwote": # i have no idea how this works
        await message.channel.typing()
        if message.content[:7] == "r>quote" and random.randint(0, 10) == 10:
            await message.channel.send("r>quote is depricated, please use \"r>qwote\" instead.", reference=message, mention_author=False) # lmao
            return
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

            # Resolve @mentions / #channel-names to readable text, then truncate if too long (e.g. > 200 chars)
            max_chars = 200
            resolved_text = resolveMentions(original_message.content, original_message)
            quote_text, trimmed_chars = safeTruncate(resolved_text, max_chars)
            if trimmed_chars:
                quote_text += f"... [{trimmed_chars} more characters]"

            atoms = tokenizeContent(quote_text)

            # Prefetch emoji images (unicode + custom Discord emoji) once at a large size, resized per font-size trial
            emoji_images = {}
            async with aiohttp.ClientSession() as emoji_session:
                for kind, data in atoms:
                    if kind in ("custom", "unicode"):
                        key = (kind, data.get("id") or data.get("char"))
                        if key not in emoji_images:
                            emoji_images[key] = await fetchEmojiImage(emoji_session, kind, data, 128)

            def elementWidth(el):
                if el[0] == "emoji":
                    return el[2]
                return sum(draw.textbbox((0, 0), t, font=f)[2] for t, f in el[1])

            def wrapAtoms(font_size):
                space_w = draw.textbbox((0, 0), " ", font=getFontObj(FONT_PATH, font_size))[2]
                lines, cur, cur_w = [], [], 0
                for kind, data in atoms:
                    if kind == "word":
                        el = ("text", buildRuns(data, font_size, FONT_PATH))
                    else:
                        img128 = emoji_images.get((kind, data.get("id") or data.get("char")))
                        if img128 is None:
                            el = ("text", buildRuns(data.get("char", ""), font_size, FONT_PATH))
                        else:
                            el = ("emoji", img128.resize((font_size, font_size), Image.LANCZOS), font_size)
                    w = elementWidth(el)
                    add_w = w if not cur else space_w + w
                    if cur and cur_w + add_w > text_w:
                        lines.append(cur)
                        cur, cur_w = [el], w
                    else:
                        cur.append(el)
                        cur_w += add_w
                if cur:
                    lines.append(cur)
                return lines, space_w

            # Dynamically shrink font until the wrapped content fits vertically
            max_text_h = H - 80 - (font_name.size + 8) - font_username.size - 20
            font_size = 62
            while font_size >= 16:
                quote_lines, space_w = wrapAtoms(font_size)
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
                line_w = sum(elementWidth(el) for el in line) + space_w * (len(line) - 1)
                x = tx + (text_w - line_w) // 2
                yy = start_y + i * lh
                for el in line:
                    if el[0] == "emoji":
                        emoji_img = el[1]
                        img.paste(emoji_img, (x, yy), emoji_img)
                        x += el[2]
                    else:
                        for t, f in el[1]:
                            draw.text((x, yy), t, fill=(255, 255, 255), font=f)
                            x += draw.textbbox((0, 0), t, font=f)[2]
                    x += space_w

            y = start_y + total_q_h + 10

            def drawCenteredRuns(text, size, y_top, color):
                runs = buildRuns(text, size, FONT_PATH)
                w = sum(draw.textbbox((0, 0), t, font=f)[2] for t, f in runs)
                x = tx + (text_w - w) // 2
                for t, f in runs:
                    draw.text((x, y_top), t, fill=color, font=f)
                    x += draw.textbbox((0, 0), t, font=f)[2]

            # "- DisplayName"
            drawCenteredRuns(f"- {getDisplay(original_message.author)}", font_name.size, y, (255, 255, 255))
            y += name_h

            # "@username"
            drawCenteredRuns(f"@{original_message.author.name}", font_username.size, y, (160, 160, 160))

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
