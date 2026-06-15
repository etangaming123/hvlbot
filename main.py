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

if not os.path.exists("env.json"):
    with open("env.json", "w") as file:
        json.dump({
            "token": "your_discord_bot_token_here",
            "openweatherapikey": "your_openweather_api_key_here",
            "fontpath": "path_to_a_font_file.ttf"
        }, file)
    input("env.json file not found. A sample one has been created, please fill it, then press enter to continue...")

env = json.load(open("env.json", "r"))

# variables // i cba adding these to env so eh
joinandleavechannelid = 1477467436193153064
messageloggingchannelid = 1477471562075607081
experimentalqueuecheckchannelid = 1477480555372089587
memberroleid = 1477467126049800282
etanid = 723053854194663456
membercountid = 1478161791992336394
serverid = 1477464211981603040
SUPASECRETLOGGINGCHANNELID = 1478658570169094194
weatherannouncementschannelid = 1478934995299995698
channelstolockdown = [1477464213420113923, 1477468857449971783, 1477479294233083954, 1477470746354778173, 1477470832870555668, 1477470860926255166, 1477896206804844636, 1477468091523924039, 1477478856595083407, 1477499265071714325, 1477499295459446885, 1477468914178064557, 1477468930384597186, 1477468946197254356, 1477468011215589510, 1477468031142596649, 1477468715711987875, 1477468757499711608, 1477468773647782073, 1477468788789346488, 1477470608856973453, 1477470632064319548, 1477474002955141120, 1477474031111241899, 1477474054889017427, 1477474068864438356, 1477475065674072348]
moderatorroleid = 1477466624452853801
moderatorplusplusroleid = 1477466855944884357
starboardchannel = 1480349980521664513
ruiroleid = 1477484699893891146
bottrapchannelid = 1482874313924411503
altaccountroleid = 1513700188521234533
lastcachedmembercount = 0
bottraproleid = 1516000045332430918

# what the bot is "playing", will cycle through randomly every minute
prescencecycles = ["Project SEKAI COLORFUL STAGE!", "hvl.etangaming.xyz!", "Yoyoyo!", "coded by etangaming123!", "maimaiDX!", "[mai²] server tag!", "reply to a message with r>quote, trust me"]

openweatherapikey = env["openweatherapikey"]

# customqueuecheck
playersinqueue = 0
playersplaying = 0
userincontrol = 0
userlastbuttontime = 0
didwealreadyreset = True # to prevent multiple resets in a row, which could cause issues with the queue check buttons and to stop rate limits
didwealreadyresetanditsnight = False # to prevent the queue check from resetting multiple times at night when no one is using it, which could also cause issues with the queue check buttons and to stop rate limits
userlastbuttontimebutmorepermanent = 0 # for automatic queue reset

datastores = ["customroles", "ships", "profiles", "achievements", "playerachievements", "alts"] # json files to create
for item in datastores:
    if os.path.exists(f"{item}.pkl"):
        data = pickle.load(open(f"{item}.pkl", "rb"))
        with open(f"{item}.json", "w") as file:
            json.dump(data, file, indent=4)
            print(f"Converted [{item}.pkl] to [{item}.json]")
    if not os.path.exists(f"{item}.json"):
        with open(f"{item}.json", "w") as file:
            json.dump({}, file)
        print(f"Created new file [{item}.json]")

datastoresbuttheseonesarelists = ["starboard", "bannedecqc"] # json files to create but these are lists
for item in datastoresbuttheseonesarelists:
    if os.path.exists(f"{item}.pkl"):
        data = pickle.load(open(f"{item}.pkl", "rb"))
        with open(f"{item}.json", "w") as file:
            json.dump(data, file, indent=4)
            print(f"Converted [{item}.pkl] to [{item}.json]")
    if not os.path.exists(f"{item}.json"):
        with open(f"{item}.json", "w") as file:
            json.dump([], file)
        print(f"Created new file [{item}.json]")

del datastores
del datastoresbuttheseonesarelists

# other functions
def formatUsername(user: discord.User): # Fancy formatting for usernames // displayname (@username)
    if user.display_name == None:
        return f"{user.name}"
    else:
        return f"{user.display_name} (@{user.name})"

def getDisplay(user: discord.User): # incase we only want to get display name and the users display is same as username
    if user.display_name == None:
        return user.name
    else:
        return user.display_name

def saveData(store: str, newdata: dict): # Saves data to a specified .json file
    print(f"Saving [{store}]...")
    try:
        backup = loadData(store)
        with open(f"{store}_backup.json", "w") as file:
            json.dump(backup, file)
        with open(f"{store}.json", "w") as file:
            json.dump(newdata, file)
        os.remove(f"{store}_backup.json")
        return True # Return true if it succeeds
    except Exception:
        traceback.print_exc()
        with open(f"{store}.json", "w") as file:
            json.dump(backup, file)
        return False # Otherwise return false

def loadData(store: str): # Gets data from a specified .json file
    try:
        with open(f"{store}.json", "r") as file:
            return json.load(file) # Return file data if it succeeds
    except Exception:
        traceback.print_exc()
        return "" # Otherwise return an empty string

def truncateMessage(message, length): 
    if len(message) <= length:
        return message
    else:
        return message[:length-40] + f"... [{len(message)-length+40} more characters]"

def returnAllAlts(userid):
    altaccounts = loadData("alts")
    if altaccounts == "":
        print("Error loading alts data.")
        return []
    for main, alts in altaccounts.items():
        if str(userid) == main or str(userid) in alts:
            return [str(main)] + [str(alt) for alt in alts]
    return []

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
    print("Loading, please wait...")
    await bot.wait_until_ready()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await experimentalQueueCheck()
    await bot.tree.sync()
    await weatherUpdate.start()
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
    if "discord.gg/" in message.content.lower(): # block invite links
        if message.author.id == etanid: # but if it's etan it's okay
            return
        await message.delete()
        await message.channel.send(f"[A message from {formatUsername(message.author)} has been blocked. (Invite links disabled)]")
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

# bot commands
# queue admin
@bot.tree.command(name="resetqueuecheck", description="Resets the queue check (admin only)")
async def resetqueuecheck(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.id == etanid:
        await interaction.edit_original_response(content=f"You do not have permission to use this command.")
        return
    global playersinqueue, playersplaying, userincontrol, userlastbuttontime
    playersinqueue = 0
    playersplaying = 0
    userincontrol = 0
    userlastbuttontime = 0
    await resetQueueCheckMessage()
    await interaction.edit_original_response(content=f"Queue check has been reset.")

@bot.tree.command(name="manualqueuesetup", description="Manually sets the queue and playing counts (admin only)")
@app_commands.describe(playing="The number of players currently playing.", inqueue="The number of players currently in queue.")
async def manualqueuesetup(interaction: discord.Interaction, playing: int, inqueue: int):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.id == etanid:
        await interaction.edit_original_response(content=f"You do not have permission to use this command.")
        return
    if playing < 0 or inqueue < 0:
        await interaction.edit_original_response(content=f"Playing and inqueue counts must be non-negative.")
        return
    global playersinqueue, playersplaying, userincontrol, userlastbuttontime
    playersplaying = playing
    playersinqueue = inqueue
    userincontrol = interaction.user.id
    userlastbuttontime = time.time()
    await editQueueCheckMessage()
    await interaction.edit_original_response(content=f"Queue check has been manually set to {playersplaying} playing and {playersinqueue} in queue.")

@bot.tree.command(name="ban-queue", description="Ban a user from using the queue buttons.")
@app_commands.describe(user="The user to ban from the queue.")
async def ban_queue(interaction: discord.Interaction, user: discord.User):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.id == etanid:
        await interaction.edit_original_response(content=f"You do not have permission to use this command.")
        return
    banned_users = loadData("bannedecqc")
    if not isinstance(banned_users, list):
        banned_users = []
    if user.id not in banned_users:
        banned_users.append(user.id)
        if saveData("bannedecqc", banned_users):
            await interaction.edit_original_response(content=f"{user.mention} has been banned from using the queue buttons.")
        else:
            await interaction.edit_original_response(content=f"An error occurred while saving the banned users data.")
    else:
        await interaction.edit_original_response(content=f"{user.mention} is already banned from using the queue buttons.")

@bot.tree.command(name="unban-queue", description="Unban a user from using the queue buttons.")
@app_commands.describe(user="The user to unban from the queue.")
async def unban_queue(interaction: discord.Interaction, user: discord.User):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.id == etanid:
        await interaction.edit_original_response(content=f"You do not have permission to use this command.")
        return
    banned_users = loadData("bannedecqc")
    if not isinstance(banned_users, list):
        banned_users = []
    if user.id in banned_users:
        banned_users.remove(user.id)
        if saveData("bannedecqc", banned_users):
            await interaction.edit_original_response(content=f"{user.mention} has been unbanned from using the queue buttons.")
        else:
            await interaction.edit_original_response(content=f"An error occurred while saving the banned users data.")
    else:
        await interaction.edit_original_response(content=f"{user.mention} is not currently banned from using the queue buttons.")

# say commands
@bot.tree.command(name="say", description="wonder what this does")
@app_commands.describe(message="The message to send in the channel.")
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.id == etanid:
        await interaction.edit_original_response(content=f"You do not have permission to use this command.")
        return
    await interaction.channel.send(message)
    await interaction.edit_original_response(content=f"Done!")

@bot.tree.command(name="say-dm", description="wonder what this does but in dms")
@app_commands.describe(user="The user to send the DM to.", message="The message to send.")
async def say_dm(interaction: discord.Interaction, user: discord.User, message: str):
    await interaction.response.defer(ephemeral=True)
    if not interaction.user.id == etanid:
        await interaction.edit_original_response(content=f"You do not have permission to use this command.")
        return
    try:
        dm = await user.create_dm()
        await dm.send(message)
    except discord.Forbidden:
        await interaction.edit_original_response(content=f"Failed to send DM. The user might have DMs disabled.")
        return
    await interaction.edit_original_response(content=f"Done!")

@bot.tree.command(name="say-form", description="same as /say but with a form, so you can multiline")
async def say_form(interaction: discord.Interaction):
    if not interaction.user.id == etanid:
        await interaction.response.send_message(content=f"You do not have permission to use this command.", ephemeral=True)
        return
    
    class SayModal(discord.ui.Modal, title="Say Command"):
        message = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph)

        async def on_submit(self, interaction: discord.Interaction):
            await interaction.channel.send(self.message.value)
            await interaction.response.send_message(content=f"Done!", ephemeral=True)

    await interaction.response.send_modal(SayModal())

# moderation
@bot.tree.command(name="purge", description="Purge a bunch of messages.")
@app_commands.describe(messageid="The ID of the first message in the conversation.")
async def purge(interaction: discord.Interaction, messageid: str):
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
        loggingchannel = await bot.get_channel(messageloggingchannelid)
        embed = discord.Embed(title="Bulk Message Deletion", description=f"{formatUsername(interaction.user)} purged {wowbroimovedthismanymessages} messages in {interaction.channel.mention}.", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        await loggingchannel.send(embed=embed)
        await interaction.channel.purge(limit=len(bunchofmessages))
        await interaction.edit_original_response(content=f"Purged {wowbroimovedthismanymessages} messages.")
    except Exception as e:
        await interaction.edit_original_response(content=f"An error occurred: {e}")
        traceback.print_exc()
        return

@bot.tree.command(name="lockdown", description="Removes send message permissions from @everyone.")
async def lockdown(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not moderatorplusplusroleid in [role.id for role in interaction.user.roles]:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    guild = bot.get_guild(serverid)
    everyone = guild.default_role
    perms = everyone.permissions
    perms.update(send_messages=False, add_reactions=False)
    loggingchannel = await bot.get_channel(messageloggingchannelid)
    embed = discord.Embed(title="Lockdown Initiated", description=f"Lockdown has been initiated by {formatUsername(interaction.user)}. Send message and add reaction permissions have been removed from @everyone.", color=discord.Color.red(), timestamp=discord.utils.utcnow())
    await loggingchannel.send(embed=embed)
    await everyone.edit(permissions=perms, reason=f"Lockdown initiated by {formatUsername(interaction.user)}")
    await interaction.edit_original_response(content=f"Removed send message permissions from @everyone.")

@bot.tree.command(name="remove-lockdown", description="Restores send message permissions to @everyone.")
async def unlockdown(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not moderatorplusplusroleid in [role.id for role in interaction.user.roles]:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    guild = bot.get_guild(serverid)
    everyone = guild.default_role
    perms = everyone.permissions
    perms.update(send_messages=True, add_reactions=True)
    await everyone.edit(permissions=perms, reason=f"Lockdown removed by {formatUsername(interaction.user)}")
    loggingchannel = await bot.get_channel(messageloggingchannelid)
    embed = discord.Embed(title="Lockdown Removed", description=f"Lockdown has been removed by {formatUsername(interaction.user)}.", color=discord.Color.green(), timestamp=discord.utils.utcnow())
    await loggingchannel.send(embed=embed)
    await interaction.edit_original_response(content=f"Restored send message permissions to @everyone.")

# fancypants
@bot.tree.command(name="changerpc", description="Manually change the bot's RPC (admin only)")
@app_commands.describe(newrpc="The new RPC to set for the bot.")
async def changerpc(interaction: discord.Interaction, newrpc: str):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id != etanid:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    try:
        await changerpc(newrpc)
    except Exception:
        try:
            await bot.change_presence(activity=discord.Game(newrpc), status=discord.Status.online)
        except Exception as e:
            await interaction.edit_original_response(content=f"An error occurred while changing RPC: {e}")
            traceback.print_exc()
            return
    await interaction.edit_original_response(content=f"RPC has been changed.")

# custom roles
@bot.tree.command(name="addcustomrole", description="Gives a user a custom role they can edit!")
@app_commands.describe(user="The user to give the role to.")
async def addcustomrole(interaction: discord.Interaction, user: discord.User):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id != etanid:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    customroledata = loadData("customroles")
    if customroledata == "":
        await interaction.edit_original_response(content=f"An error occurred while loading custom role data.")
        return
    if str(user.id) in customroledata:
        await interaction.edit_original_response(content=f"This user already has a custom role!")
        return
    guild = bot.get_guild(serverid)
    role = await guild.create_role(name=f"{user.name}'s Custom Role", color=discord.Color.default())
    pos = guild.get_role(ruiroleid).position - 1
    await role.edit(position=pos)
    await user.add_roles(role)
    customroledata[str(user.id)] = role.id
    if not saveData("customroles", customroledata):
        await interaction.edit_original_response(content=f"An error occurred while saving custom role data.")
        return
    await interaction.edit_original_response(content=f"Custom role has been created and assigned to {formatUsername(user)}.")

@bot.tree.command(name="removecustomrole", description="Removes a user's custom role.")
@app_commands.describe(user="The user to remove the role from.")
async def removecustomrole(interaction: discord.Interaction, user: discord.User):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id != etanid:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    customroledata = loadData("customroles")
    if customroledata == "":
        await interaction.edit_original_response(content=f"An error occurred while loading custom role data.")
        return
    if not str(user.id) in customroledata:
        await interaction.edit_original_response(content=f"This user does not have a custom role!")
        return
    guild = bot.get_guild(serverid)
    role = guild.get_role(customroledata[str(user.id)])
    if role:
        await role.delete()
    del customroledata[str(user.id)]
    if not saveData("customroles", customroledata):
        await interaction.edit_original_response(content=f"An error occurred while saving custom role data.")
        return
    await interaction.edit_original_response(content=f"Custom role for {formatUsername(user)} has been removed.")

@bot.tree.command(name="editcustomrole", description="Edit your custom role here!")
@app_commands.describe(name="The new name for your custom role.", color="The new color for your custom role (in hex, e.g. #ff0000), or 'none' to reset to default. (boring!)")
async def editcustomrole(interaction: discord.Interaction, name: str, color: str):
    await interaction.response.defer(ephemeral=True)
    customroledata = loadData("customroles")
    if customroledata == "":
        await interaction.edit_original_response(content=f"An error occurred while loading custom role data.")
        return
    if not str(interaction.user.id) in customroledata:
        await interaction.edit_original_response(content=f"You do not have a custom role!")
        return
    guild = bot.get_guild(serverid)
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
                await interaction.edit_original_response(content=f"Invalid color format. Please provide a hex color code (e.g. #ff0000).")
                return
        await role.edit(name=name, color=colorreal)
    if not saveData("customroles", customroledata):
        await interaction.edit_original_response(content=f"An error occurred while saving custom role data.")
        return
    await interaction.edit_original_response(content=f"Custom role for {formatUsername(interaction.user)} has been edited.")

# additional moderator commands, these ones being pulled from discord, but also having some custom functionality like DMing the user when they get kicked
@bot.tree.command(name="kick", description="Kick a user from the server.")
@app_commands.describe(user="The user to kick.", reason="The reason for the kick. (will show in dms if you decide to dm)", dm="Whether to DM the user about the kick or not (defaults to false).")
async def kick(interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided.", dm: bool = False):
    await interaction.response.defer()
    if not moderatorroleid in [role.id for role in interaction.user.roles]:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    if moderatorroleid in [role.id for role in user.roles] or moderatorplusplusroleid in [role.id for role in user.roles]:
        await interaction.edit_original_response(content=f"No.")
        return
    guild = bot.get_guild(serverid)
    await guild.kick(user, reason=reason)
    loggingchannel = await bot.get_channel(messageloggingchannelid)
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

@bot.tree.command(name="ban", description="Ban a user from the server.")
@app_commands.describe(user="The user to ban.", reason="The reason for the ban. (will show in dms if you decide to dm)", dm="Whether to DM the user about the ban or not (defaults to false).")
async def ban(interaction: discord.Interaction, user: discord.User, reason: str = "No reason provided.", dm: bool = False):
    await interaction.response.defer()
    if not moderatorplusplusroleid in [role.id for role in interaction.user.roles]:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    if moderatorroleid in [role.id for role in user.roles] or moderatorplusplusroleid in [role.id for role in user.roles]:
        await interaction.edit_original_response(content=f"No.")
        return
    guild = bot.get_guild(serverid)
    await guild.ban(user, reason=reason)
    loggingchannel = await bot.get_channel(messageloggingchannelid)
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

@bot.tree.command(name="unban", description="Unban a user from the server. [user id]")
@app_commands.describe(userid="The ID of the user to unban.")
async def unban(interaction: discord.Interaction, userid: int):
    await interaction.response.defer()
    if not moderatorplusplusroleid in [role.id for role in interaction.user.roles]:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    if moderatorroleid in [role.id for role in user.roles] or moderatorplusplusroleid in [role.id for role in user.roles]:
        await interaction.edit_original_response(content=f"No.")
        return
    try:
        guild = bot.get_guild(serverid)
        user = await bot.fetch_user(userid)
        await guild.unban(user)
        loggingchannel = await bot.get_channel(messageloggingchannelid)
        embed = discord.Embed(title="User Unbanned via HVLBot", description=f"{formatUsername(user)} was unbanned by {formatUsername(interaction.user)}.", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        await loggingchannel.send(embed=embed)
        await interaction.edit_original_response(content=f"{formatUsername(user)} has been unbanned from the server.")
    except Exception as e:
        await interaction.edit_original_response(content=f"An error occurred: {e}")
        traceback.print_exc()
        return

@bot.tree.command(name="timeout", description="Timeout a user from chatting in the server for a certain amount of time.")
@app_commands.choices(duration=[
    app_commands.Choice(name="1 minute", value=60),
    app_commands.Choice(name="5 minutes", value=300),
    app_commands.Choice(name="10 minutes", value=600),
    app_commands.Choice(name="1 hour", value=3600),
    app_commands.Choice(name="1 day", value=86400),
    app_commands.Choice(name="1 week", value=1209600)
])
@app_commands.describe(user="The user to timeout.", duration="The duration of the timeout.", reason="The reason for the timeout.")
async def timeout(interaction: discord.Interaction, user: discord.User, duration: app_commands.Choice[int], reason: str = "No reason provided."):
    await interaction.response.defer()
    if not moderatorroleid in [role.id for role in interaction.user.roles]:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    if moderatorroleid in [role.id for role in user.roles] or moderatorplusplusroleid in [role.id for role in user.roles]:
        await interaction.edit_original_response(content=f"No.")
        return
    guild = bot.get_guild(serverid)
    member = guild.get_member(user.id)
    if member is None:
        await interaction.edit_original_response(content=f"User not found in the server.")
        return
    try:
        await member.timeout(discord.utils.utcnow() + datetime.timedelta(seconds=duration.value), reason=reason)
        loggingchannel = await bot.get_channel(messageloggingchannelid)
        embed = discord.Embed(title="User Timed Out via HVLBot", description=f"{formatUsername(user)} was timed out by {formatUsername(interaction.user)} for {duration.name}.", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Reason", value=reason, inline=False)
        await loggingchannel.send(embed=embed)
        await interaction.edit_original_response(content=f"{formatUsername(user)} has been timed out for {duration.name}.")
    except Exception as e:
        await interaction.edit_original_response(content=f"An error occurred: {e}")
        traceback.print_exc()
        return

@bot.tree.command(name="timeout-custom", description="Timeout a user for a custom amount of time (in minutes).")
@app_commands.describe(user="The user to timeout.", duration="The duration of the timeout in minutes.", reason="The reason for the timeout.")
async def timeout_custom(interaction: discord.Interaction, user: discord.User, duration: int, reason: str = "No reason provided."):
    await interaction.response.defer()
    if not moderatorroleid in [role.id for role in interaction.user.roles]:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    if moderatorroleid in [role.id for role in user.roles] or moderatorplusplusroleid in [role.id for role in user.roles]:
        await interaction.edit_original_response(content=f"No.")
        return
    guild = bot.get_guild(serverid)
    member = guild.get_member(user.id)
    if member is None:
        await interaction.edit_original_response(content=f"User not found in the server.")
        return
    try:
        await member.timeout(discord.utils.utcnow() + datetime.timedelta(minutes=duration), reason=reason)
        loggingchannel = await bot.get_channel(messageloggingchannelid)
        embed = discord.Embed(title="User Timed Out via HVLBot", description=f"{formatUsername(user)} was timed out by {formatUsername(interaction.user)} for {duration} minutes.", color=discord.Color.orange(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Reason", value=reason, inline=False)
        await loggingchannel.send(embed=embed)
        await interaction.edit_original_response(content=f"{formatUsername(user)} has been timed out for {duration} minutes.")
    except Exception as e:
        await interaction.edit_original_response(content=f"An error occurred: {e}")
        traceback.print_exc()
        return

@bot.tree.command(name="untimeout", description="Remove timeout from a user.")
@app_commands.describe(user="The user to remove timeout from.")
async def untimeout(interaction: discord.Interaction, user: discord.User):
    await interaction.response.defer()
    if not moderatorroleid in [role.id for role in interaction.user.roles]:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    if moderatorroleid in [role.id for role in user.roles] or moderatorplusplusroleid in [role.id for role in user.roles]:
        await interaction.edit_original_response(content=f"No.")
        return
    guild = bot.get_guild(serverid)
    member = guild.get_member(user.id)
    if member is None:
        await interaction.edit_original_response(content=f"User not found in the server.")
        return
    try:
        await member.timeout(None, reason="Timeout removed.")
        loggingchannel = await bot.get_channel(messageloggingchannelid)
        embed = discord.Embed(title="User Untimed Out via HVLBot", description=f"{formatUsername(user)} was untimed out by {formatUsername(interaction.user)}.", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        await loggingchannel.send(embed=embed)
        await interaction.edit_original_response(content=f"Timeout has been removed from {formatUsername(user)}.")
    except Exception as e:
        await interaction.edit_original_response(content=f"An error occurred: {e}")
        traceback.print_exc()
        return

@bot.tree.command(name="delete-message", description="Delete a message by its ID. (admin only)")
@app_commands.describe(messageid="The ID of the message to delete.")
async def delete_message(interaction: discord.Interaction, messageid: str):
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

@bot.tree.command(name="pin-message", description="Pin a message by its ID. (admin only)")
@app_commands.describe(messageid="The ID of the message to pin.")
async def pin_message(interaction: discord.Interaction, messageid: str):
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

# fun
@bot.tree.command(name="8ball", description="Ask the magic 8ball a question!") # use with caution. its completely random yet can be scarily accurate at times
@app_commands.describe(question="The question to ask the 8ball. (a yes or no question, and keep it short!)")
async def eight_ball(interaction: discord.Interaction, question: str):
    responses = [
        "It is certain.",
        "It is decidedly so.",
        "Without a doubt.",
        "Yes - definitely.",
        "You may rely on it.",
        "As I see it, yes.",
        "Most likely.",
        "Outlook good.",
        "Yes.",
        "Signs point to yes.",
        "Reply hazy, try again.",
        "Ask again later.",
        "Better not tell you now.",
        "Cannot predict now.",
        "Concentrate and ask again.",
        "Don't count on it.",
        "My reply is no.",
        "My sources say no.",
        "Outlook not so good.",
        "Very doubtful."
    ]
    await interaction.response.send_message(content=f"You asked the 8ball \"{question}\"...\nThe 8ball says... {random.choice(responses)}")

@bot.tree.command(name="braincells", description="Check how many braincells you (or someone else) has left. (highest is 1000)")
@app_commands.describe(user="The user to check braincells for (defaults to yourself).")
async def braincells(interaction: discord.Interaction, user: discord.User = None):
    if user is None:
        user = interaction.user
    braincellcount = random.randint(0, 1000)
    await interaction.response.send_message(content=f"{formatUsername(user)} has {braincellcount} braincells.")

@bot.tree.command(name="pizoelectric", description="[Thing] is turning [something else] into electricity!") # based off the infamous copypasta "Japan is turning footsteps into electricity! ⚡Using piezoelectric tiles, every step you take generates a small amount of energy. Millions of steps together can power LED lights and displays in busy places like Shibuya Station. A brilliant way to create a sustainable and smart city -- turning movement into clean, renewable energy 🌱💡"
@app_commands.describe(thing="Who is turning something into electricity?", somethingelse="What is being turned into electricity?")
async def pizoelectric(interaction: discord.Interaction, thing: str = None, somethingelse: str = None):
    if thing is None:
        thing = "Japan"
    if somethingelse is None:
        somethingelse = "footsteps"

    await interaction.response.send_message(content=f"{thing} is turning {somethingelse} into electricity! ⚡Using piezoelectric tiles, every step you take generates a small amount of energy. Millions of steps together can power LED lights and displays in busy places like Shibuya Station. A brilliant way to create a sustainable and smart city -- turning movement into clean, renewable energy 🌱💡")

# shipping
# shipping's data is fucked and i cba changing this code was YOINKED!!!
def saveShip(userid1, userid2, newvalue):
    with open("ships.json", "r") as file:
        data = json.load(file)
    selectedindex = ""
    for index in data.keys():
        if index == f"{userid1},{userid2}":
            selectedindex = index
            break
        if index == f"{userid2},{userid1}":
            selectedindex = index
            break
    if selectedindex == "":
        data[f"{userid1},{userid2}"] = newvalue
    else:
        data[selectedindex] = newvalue
    with open("ships.json", "w") as file:
        json.dump(data, file)

def getShip(userid1, userid2):
    with open("ships.json", "r") as file:
        data = json.load(file)
    selectedindex = ""
    for index in data.keys(): # we never reroll ship values. Have fun.
        if index == f"{userid1},{userid2}":
            selectedindex = index
            break
        if index == f"{userid2},{userid1}":
            selectedindex = index
            break
    if selectedindex == "":
        oohshipvalue = random.randint(0, 100)
        data[f"{userid1},{userid2}"] = oohshipvalue
        saveShip(userid1, userid2, oohshipvalue)
        return data[f"{userid1},{userid2}"]
    else:
        return data[selectedindex]
    
textvalues = {0: "Awful", 10: "Enemies", 20: "Terrible", 30: "Not Too Great", 40: "Worse than average", 50: "Barely", 60: "Not Bad", 70: "Pretty Good", 80: "Great", 90: "Amazing", 100: "PERFECT!", 101: "WOAH!!"}

@bot.tree.command(name="ship", description="Ship 2 discord users! (do not take this seriously it's a random number gen)")
@app_commands.describe(user1="The first user", user2="The second user")
async def ship(interaction: discord.Interaction, user1: discord.User, user2: discord.User):
    await interaction.response.defer()
    if interaction.user.id == user1.id and interaction.user.id == user2.id:
        await interaction.edit_original_response(content="You can't ship yourself with yourself!")
    elif user1.id == user2.id:
        await interaction.edit_original_response(content="You can't ship a user with themselves!")
    else:
        percentage = getShip(user1.id, user2.id)
        extratext = ""
        if percentage == 69:
            extratext = "nice"
        elif percentage == 67:
            extratext = "TUFFFFF"
        else:
            for index, value in textvalues.items():
                if percentage == index or percentage > index:
                    extratext = value
        embed = discord.Embed(title=f"{percentage}% // {extratext}", color=discord.Color.random())
        embed.add_field(name=f"User 1", value=f"{formatUsername(user1)}", inline=True)
        embed.add_field(name=f"User 2", value=f"{formatUsername(user2)}", inline=True)

        await interaction.edit_original_response(content=f"Shipping {formatUsername(user1)} and {formatUsername(user2)}...", embed=embed)

@bot.tree.command(name="ship-random", description="Ships you with a random user! (do not take this seriously it's a random number gen)")
async def shiprandom(interaction: discord.Interaction):
    await interaction.response.defer()
    members = interaction.guild.members
    realmembers = [member for member in members if not member.bot and not member.id == interaction.user.id]
    selected = random.choice(realmembers)
    percentage = getShip(interaction.user.id, selected.id)
    extratext = ""
    if percentage == 69:
        extratext = "nice"
    elif percentage == 67:
        extratext = "TUFFFFF"
    else:
        for index, value in textvalues.items():
            if percentage == index or percentage > index:
                extratext = value
    embed = discord.Embed(title=f"{percentage}% // {extratext}", color=discord.Color.random())
    embed.add_field(name=f"User 1", value=f"{formatUsername(interaction.user)}", inline=True)
    embed.add_field(name=f"User 2", value=f"{formatUsername(selected)}", inline=True)

    await interaction.edit_original_response(content=f"Shipping {formatUsername(interaction.user)} and {formatUsername(selected)}...", embed=embed)

@bot.tree.command(name="ship-true-random", description="Ships TWO random users!!!! (do not take this seriously it's a random number gen)")
async def shiptruerandom(interaction: discord.Interaction):
    await interaction.response.defer()
    members = interaction.guild.members
    realmembers = [member for member in members if not member.bot]
    selected1 = random.choice(realmembers)
    selected2 = random.choice(realmembers)
    while selected2.id == selected1.id:
        selected2 = random.choice(realmembers)
    percentage = getShip(selected1.id, selected2.id)
    extratext = ""
    if percentage == 69:
        extratext = "nice"
    elif percentage == 67:
        extratext = "TUFFFFF"
    else:
        for index, value in textvalues.items():
            if percentage == index or percentage > index:
                extratext = value
    embed = discord.Embed(title=f"{percentage}% // {extratext}", color=discord.Color.random())
    embed.add_field(name=f"User 1", value=f"{formatUsername(selected1)}", inline=True)
    embed.add_field(name=f"User 2", value=f"{formatUsername(selected2)}", inline=True)

    await interaction.edit_original_response(content=f"Shipping {formatUsername(selected1)} and {formatUsername(selected2)}...", embed=embed)

@bot.tree.command(name="test-command", description="Internal backend testing for a specific command.") # welp now that the bot is Open source everyone knows what this does LOL
@app_commands.describe(user1="The first user", user2="The second user (if needed)", number="0-100")
async def setcustomship(interaction: discord.Interaction, user1: discord.User, user2: discord.User, number: int):
    if interaction.user.id == etanid:
        if user1 and user2 and number is not None:
            saveShip(user1.id, user2.id, number)
            await interaction.response.send_message(f"Set {formatUsername(user1)} and {formatUsername(user2)} to {str(number)}%!", ephemeral=True)
    else:
        await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)

# profiles
@bot.tree.command(name="create-profile", description="Creates a profile for you, viewable using /view-profile!")
async def create_profile(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    profiles = loadData("profiles")
    if str(interaction.user.id) in profiles.keys():
        await interaction.edit_original_response(content=f"You already have a profile! Use /view-profile to view it.")
        return
    profiles[str(interaction.user.id)] = {
        "bio": "Nothing yet... use /edit-profile to edit this! Max 256 characters.",
        "links": {}
    }
    if saveData("profiles", profiles):
        await interaction.edit_original_response(content=f"Profile created successfully!")
    else:
        await interaction.edit_original_response(content=f"An error occurred while creating your profile. Please try again later.")

@bot.tree.command(name="view-profile", description="View your profile or someone else's!")
@app_commands.describe(user="The user to view the profile of. Defaults to yourself.", viewprivately="Want to make it so only you can see the profile? (defaults to nah)")
async def viewprofile(interaction: discord.Interaction, user: discord.User = None, viewprivately: bool = False):
    containsatsymbol = ["tiktok", "youtube"] # these platforms require an @ symbol in the url
    await interaction.response.defer(ephemeral=viewprivately)
    if user is None:
        user = interaction.user
    profiles = loadData("profiles")
    if str(user.id) not in profiles:
        await interaction.edit_original_response(content=f"This user does not have a profile yet! They can create one using /create-profile.")
        return
    profile = profiles[str(user.id)]
    if not "color" in profile:
        profile["color"] = 0x00ff00 # default color is green
    embed = discord.Embed(title=f"{formatUsername(user)}'s Profile", color=profile.get("color", 0x00ff00))
    embed.add_field(name="About Me", value=profile["bio"], inline=False)
    stringystringy = ""
    for platform, username in profile["links"].items():
        link = username
        if platform in containsatsymbol:
            link = f"@{username}"
        stringystringy += f"{platform.capitalize()}: [@{username}](https://{platform}.com/{link})\n"
    if stringystringy == "":
        stringystringy = "No social links set."
    embed.add_field(name="Links", value=stringystringy, inline=False)
    embed.set_thumbnail(url=user.display_avatar.url if user.display_avatar else "https://cdn.discordapp.com/embed/avatars/0.png")
    await interaction.edit_original_response(embed=embed)

class ProfileEditModal(discord.ui.Modal, title="Edit Your Profile"):
    def __init__(self, profile):
        super().__init__()
        self.profile = profile
        self.bio = discord.ui.TextInput(label="Bio", style=discord.TextStyle.paragraph, default=profile["bio"], max_length=256)
        self.add_item(self.bio)

    async def on_submit(self, interaction: discord.Interaction):
        profiles = loadData("profiles")
        user_id = str(interaction.user.id)
        if user_id not in profiles:
            await interaction.response.send_message(content=f"Your profile was not found. Please create a new one using /create-profile. Here's your bio if you need to copy and paste:\n{self.profile['bio']}", embed=None, view=None, ephemeral=True)
            return
        profiles[user_id]["bio"] = self.bio.value
        if saveData("profiles", profiles):
            await interaction.response.send_message(content=f"Profile updated successfully!", embed=None, view=None, ephemeral=True)
        else:
            await interaction.response.send_message(content=f"An error occurred while updating your profile. Please try again later. Here's your bio if you need to copy and paste:\n{self.profile['bio']}", embed=None, view=None, ephemeral=True)

@bot.tree.command(name="edit-profile", description="Edit your profile's bio!")
async def editprofile(interaction: discord.Interaction):
    profiles = loadData("profiles")
    if str(interaction.user.id) not in profiles.keys():
        await interaction.edit_original_response(content=f"You don't have a profile yet! Use /create-profile to create one.")
        return
    profile = profiles[str(interaction.user.id)]
    await interaction.response.send_modal(ProfileEditModal(profile))

@bot.tree.command(name="delete-profile", description="Delete your profile! This cannot be undone.")
async def deleteprofile(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    profiles = loadData("profiles")
    if str(interaction.user.id) not in profiles.keys():
        await interaction.edit_original_response(content=f"You don't have a profile yet! Use /create-profile to create one.")
        return
    del profiles[str(interaction.user.id)]
    if saveData("profiles", profiles):
        await interaction.edit_original_response(content=f"Profile deleted successfully!")
    else:
        await interaction.edit_original_response(content=f"An error occurred while deleting your profile. Please try again later.")

@bot.tree.command(name="change-profile-color", description="Change the color of your profile embed! (hex code, no #, default is green)")
@app_commands.describe(color="The hex code of the color you want to set for your profile embed (no #, default is green)")
async def changeprofilecolor(interaction: discord.Interaction, color: str):
    await interaction.response.defer(ephemeral=True)
    profiles = loadData("profiles")
    if str(interaction.user.id) not in profiles.keys():
        await interaction.edit_original_response(content=f"You don't have a profile yet! Use /create-profile to create one.")
        return
    try:
        color = int(color, 16)
    except ValueError:
        await interaction.edit_original_response(content=f"Invalid color format. Please use a valid hex code (no #).")
        return
    profiles[str(interaction.user.id)]["color"] = color
    if saveData("profiles", profiles):
        await interaction.edit_original_response(content=f"Profile color updated successfully!")
    else:
        await interaction.edit_original_response(content=f"An error occurred while updating your profile color. Please try again later.")

@bot.tree.command(name="add-profile-link", description="Add a link to your profile! (tiktok, instagram, twitter, more later!)")
@app_commands.describe(platform="Only shows supported platforms for now!", username="Your username/handle on the platform (no urls or @, just the username)")
@app_commands.choices(platform=[
    discord.app_commands.Choice(name="TikTok", value="tiktok"),
    discord.app_commands.Choice(name="Instagram", value="instagram"),
    discord.app_commands.Choice(name="Twitter", value="twitter"),
    discord.app_commands.Choice(name="YouTube", value="youtube")
])
async def addprofilelink(interaction: discord.Interaction, platform: discord.app_commands.Choice[str], username: str):
    await interaction.response.defer(ephemeral=True)
    profiles = loadData("profiles")
    if str(interaction.user.id) not in profiles.keys():
        await interaction.edit_original_response(content=f"You don't have a profile yet! Use /create-profile to create one.")
        return
    if not "links" in profiles[str(interaction.user.id)]:
        profiles[str(interaction.user.id)]["links"] = {}
    profiles[str(interaction.user.id)]["links"][platform.value] = username

    if not saveData("profiles", profiles):
        await interaction.edit_original_response(content=f"An error occurred while adding the link to your profile. Please try again later.")
        return
    await interaction.edit_original_response(content=f"Link added successfully!")

@bot.tree.command(name="remove-profile-link", description="Remove a link from your profile.")
@app_commands.describe(platform="The platform of the link you want to remove.")
@app_commands.choices(platform=[
    discord.app_commands.Choice(name="TikTok", value="tiktok"),
    discord.app_commands.Choice(name="Instagram", value="instagram"),
    discord.app_commands.Choice(name="Twitter", value="twitter"),
    discord.app_commands.Choice(name="YouTube", value="youtube")
])
async def removeprofilelink(interaction: discord.Interaction, platform: discord.app_commands.Choice[str]):
    await interaction.response.defer(ephemeral=True)
    profiles = loadData("profiles")
    if str(interaction.user.id) not in profiles.keys():
        await interaction.edit_original_response(content=f"You don't have a profile yet! Use /create-profile to create one.")
        return
    if not "links" in profiles[str(interaction.user.id)] or platform.value not in profiles[str(interaction.user.id)]["links"]:
        await interaction.edit_original_response(content=f"You don't have a link for that platform on your profile!")
        return
    del profiles[str(interaction.user.id)]["links"][platform.value]
    if not saveData("profiles", profiles):
        await interaction.edit_original_response(content=f"An error occurred while removing the link from your profile. Please try again later.")
        return
    await interaction.edit_original_response(content=f"Link removed successfully!")

# achievements
@bot.tree.command(name="create-achievement", description="Make new achievement")
@app_commands.describe(name="Name of the achievement", description="Description of the achievement", vanity="Should this achievement have a role?")
async def createachievement(interaction: discord.Interaction, name: str, description: str, vanity: bool = False):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id != etanid:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    achievementdata = loadData("achievements")
    if achievementdata == "":
        await interaction.edit_original_response(content=f"An error occurred while loading achievement data.")
        return
    achievementid = 1
    while str(achievementid) in achievementdata:
        achievementid += 1

    if vanity:
        guild = bot.get_guild(serverid)
        role = await guild.create_role(name=f"{name}", mentionable=False)
        memberrole = guild.get_role(memberroleid)
        await role.edit(position=(memberrole.position - 1))
        achievementdata[str(achievementid)] = {
            "name": name,
            "description": description,
            "roleid": role.id
        }
    else:
        achievementdata[str(achievementid)] = {
            "name": name,
            "description": description,
            "roleid": None
        }
    if not saveData("achievements", achievementdata):
        await interaction.edit_original_response(content=f"An error occurred while saving achievement data.")
        return
    await interaction.edit_original_response(content=f"Achievement created successfully with ID {achievementid}!")

@bot.tree.command(name="edit-achievement", description="Edit an existing achievement")
@app_commands.describe(id="The id of the achievement you want to edit.", name="New name of the achievement", description="New description of the achievement")
async def editachievement(interaction: discord.Interaction, id: str, name: str = None, description: str = None):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id != etanid:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    achievementdata = loadData("achievements")
    if achievementdata == "":
        await interaction.edit_original_response(content=f"An error occurred while loading achievement data.")
        return
    achievementinfo = achievementdata.get(str(id))
    if not achievementinfo:
        await interaction.edit_original_response(content=f"That achievement does not exist.")
        return
    if name:
        achievementinfo["name"] = name
    if description:
        achievementinfo["description"] = description
    achievementdata[str(id)] = achievementinfo
    if not saveData("achievements", achievementdata):
        await interaction.edit_original_response(content=f"An error occurred while saving achievement data.")
        return
    await interaction.edit_original_response(content=f"Achievement edited successfully!")

@bot.tree.command(name="equip-achievement", description="Equip an achievement you have earned to show off your accomplishment!")
@app_commands.describe(achievement="The achievement you want to equip.")
async def equipachievement(interaction: discord.Interaction, achievement: str):
    await interaction.response.defer(ephemeral=True)

    if achievement == "__no_achievements__":
        await interaction.edit_original_response(content="You don't have any achievements yet!")
        return

    allachievements = loadData("achievements")
    playerachievements = loadData("playerachievements")
    if allachievements == "" or playerachievements == "":
        await interaction.edit_original_response(content="An error occurred while loading achievement data.")
        return

    userachievements = playerachievements.get(str(interaction.user.id), [])
    if isinstance(userachievements, dict):
        userachievementids = [str(item) for item in userachievements.keys()]
    elif isinstance(userachievements, (list, set, tuple)):
        userachievementids = [str(item) for item in userachievements]
    else:
        userachievementids = []

    if achievement not in userachievementids:
        await interaction.edit_original_response(content="You don't have that achievement!")
        return

    achievementinfo = allachievements.get(str(achievement))
    if not achievementinfo:
        await interaction.edit_original_response(content="That achievement no longer exists.")
        return

    achievementroleids = []
    for item in allachievements.values():
        roleid = item.get("roleid")
        if roleid:
            achievementroleids.append(roleid)

    for item in interaction.user.roles:
        if item.id == achievementinfo.get("roleid"):
            await interaction.edit_original_response(content="You already have that achievement equipped!")
            return
        if item.id in achievementroleids and not item.id == achievementinfo.get("roleid"):
            await interaction.user.remove_roles(item, reason="Unequipping previous achievement")

    roleid = achievementinfo.get("roleid")
    if roleid:
        role = interaction.guild.get_role(roleid)
        if role is None:
            await interaction.edit_original_response(content="That achievement's role no longer exists.")
            return
        await interaction.user.add_roles(role, reason="Achievement equipped")
        await interaction.edit_original_response(content=f"Equipped achievement **{achievementinfo.get('name', achievement)}** and gave you {role.mention}!")
        return

    await interaction.edit_original_response(content=f"Equipped achievement **{achievementinfo.get('name', achievement)}**!")

@equipachievement.autocomplete("achievement")
async def equipachievement_autocomplete(interaction: discord.Interaction, current: str):
    allachievements = loadData("achievements")
    playerachievements = loadData("playerachievements")
    if allachievements == "" or playerachievements == "":
        return [app_commands.Choice(name="You don't have any!", value="__no_achievements__")]

    userachievements = playerachievements.get(str(interaction.user.id), [])
    if isinstance(userachievements, dict):
        userachievementids = [str(item) for item in userachievements.keys()]
    elif isinstance(userachievements, (list, set, tuple)):
        userachievementids = [str(item) for item in userachievements]
    else:
        userachievementids = []

    if not userachievementids:
        return [app_commands.Choice(name="You don't have any!", value="__no_achievements__")]

    choices = []
    for achievementid in userachievementids:
        achievementinfo = allachievements.get(str(achievementid))
        if not achievementinfo:
            continue

        achievementname = str(achievementinfo.get("name", f"ID {achievementid}"))
        if current and current.lower() not in achievementname.lower():
            continue

        choices.append(app_commands.Choice(name=achievementname[:100], value=str(achievementid)[:100]))
        if len(choices) >= 25:
            break

    if not choices:
        return [app_commands.Choice(name="You don't have any!", value="__no_achievements__")]
    return choices

@bot.tree.command(name="player-achievements", description="View all achievements you or someone else have earned!")
@app_commands.describe(user="The user to check achievements for. Defaults to yourself.")
async def listachievements(interaction: discord.Interaction, user: discord.User = None):
    await interaction.response.defer(ephemeral=True)
    if user is None:
        user = interaction.user

    allachievements = loadData("achievements")
    playerachievements = loadData("playerachievements")
    if allachievements == "" or playerachievements == "":
        await interaction.edit_original_response(content=f"An error occurred while loading achievement data.")
        return

    userachievements = playerachievements.get(str(user.id), [])
    if isinstance(userachievements, dict):
        userachievementids = [str(item) for item in userachievements.keys()]
    elif isinstance(userachievements, (list, set, tuple)):
        userachievementids = [str(item) for item in userachievements]
    else:
        userachievementids = []

    if not userachievementids:
        await interaction.edit_original_response(content=f"{formatUsername(user)} hasn't earned any achievements yet!")
        return

    embed = discord.Embed(title=f"Achievements for {formatUsername(user)}", color=discord.Color.green())
    for achievementid in userachievementids:
        achievementinfo = allachievements.get(str(achievementid))
        if not achievementinfo:
            continue
        embed.add_field(name=achievementinfo.get("name", f"ID {achievementid}"), value=achievementinfo.get("description", "No description"), inline=False)

    await interaction.edit_original_response(embed=embed)

@bot.tree.command(name="award-achievement", description="Award an achievement to a user!")
@app_commands.describe(user="The user to award the achievement to.", achievement="The achievement to award by ID.")
async def awardachievement(interaction: discord.Interaction, user: discord.User, achievement: str):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id != etanid:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    allachievements = loadData("achievements")
    playerachievements = loadData("playerachievements")
    if allachievements == "" or playerachievements == "":
        await interaction.edit_original_response(content=f"An error occurred while loading achievement data.")
        return
    achievementinfo = allachievements.get(str(achievement))
    if not achievementinfo:
        await interaction.edit_original_response(content=f"That achievement does not exist.")
        return
    if str(user.id) not in playerachievements:
        playerachievements[str(user.id)] = []
    if achievement in playerachievements[str(user.id)]:
        await interaction.edit_original_response(content=f"That user already has that achievement!")
        return

    playerachievements[str(user.id)].append(achievement)
    saveData("playerachievements", playerachievements)
    await interaction.edit_original_response(content=f"Awarded the achievement '{achievementinfo.get('name')}' to {user.mention}!")

@bot.tree.command(name="list-achievements", description="List all achievement names and ids (owner only)")
async def listallachievements(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id != etanid:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    allachievements = loadData("achievements")
    if allachievements == "":
        await interaction.edit_original_response(content=f"An error occurred while loading achievement data.")
        return
    if not allachievements:
        await interaction.edit_original_response(content=f"There are no achievements yet!")
        return
    string = "All achievements:\n"
    for achievementid, achievementinfo in allachievements.items():
        string += f"- {achievementinfo.get('name', f'ID {achievementid}')} (ID: {achievementid})\n"

    await interaction.edit_original_response(content=string)

# alt account linking + management
@bot.tree.command(name="list-alts", description="Check if a user has any alts linked to their account!")
@app_commands.describe(user="The user to check for linked alts.")
async def whois(interaction: discord.Interaction, user: discord.User):
    await interaction.response.defer(ephemeral=True)
    altlinks = loadData("alts")
    if altlinks == "":
        await interaction.edit_original_response(content=f"An error occurred while loading alt account data.")
        return
    linked_alts = altlinks.get(str(user.id), [])
    if linked_alts:
        alt_usernames = [f"<@{alt}>" for alt in linked_alts]
        await interaction.edit_original_response(content=f"{formatUsername(user)} has the following alt accounts linked: {', '.join(alt_usernames)}")
    else:
        for ownerid, alts in altlinks.items():
            if str(user.id) in alts:
                await interaction.edit_original_response(content=f"{formatUsername(user)} is an alt account linked to <@{ownerid}>.")
                return
        await interaction.edit_original_response(content=f"{formatUsername(user)} does not have any linked alt accounts.")

@bot.tree.command(name="link-alt", description="Link an alt account to a main account. (owner only)")
@app_commands.describe(mainaccount="The main account to link to.", altaccount="The alt account to link by user ID.")
async def linkalt(interaction: discord.Interaction, mainaccount: discord.User, altaccount: str):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id != etanid:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    altlinks = loadData("alts")
    if altlinks == "":
        await interaction.edit_original_response(content=f"An error occurred while loading alt account data.")
        return
    if str(altaccount) in altlinks:
        await interaction.edit_original_response(content=f"That alt account is already linked to a main account.")
        return
    if not mainaccount.id in altlinks.values():
        altlinks[str(mainaccount.id)] = []
    altlinks[str(mainaccount.id)].append(str(altaccount))
    if not saveData("alts", altlinks):
        await interaction.edit_original_response(content=f"An error occurred while saving alt account data.")
        return
    await interaction.edit_original_response(content=f"Linked <@{altaccount}> as an alt of <@{mainaccount.id}> successfully!")

@bot.tree.command(name="unlink-alt", description="Unlink an alt account from its main account. (owner only)")
@app_commands.describe(altaccount="The alt account to unlink by user ID.")
async def unlinkalt(interaction: discord.Interaction, altaccount: str):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id != etanid:
        await interaction.edit_original_response(content=f"You don't have permission to use this command!")
        return
    altlinks = loadData("alts")
    if altlinks =="":
        await interaction.edit_original_response(content=f"An error occurred while loading alt account data.")
        return
    for alts in altlinks.values():
        if str(altaccount) in alts:
            break
    else:
        await interaction.edit_original_response(content=f"That alt account is not linked to any main account.")
        return
    for mainaccount_id, alt_list in altlinks.items():
        if str(altaccount) in alt_list:
            alt_list.remove(str(altaccount))
            if not alt_list:  # If the main account has no more alts, remove it
                del altlinks[mainaccount_id]
            break
    if not saveData("alts", altlinks):
        await interaction.edit_original_response(content=f"An error occurred while saving alt account data.")
        return
    await interaction.edit_original_response(content=f"Unlinked <@{altaccount}> from its main account successfully!")

bot.run(env["token"])