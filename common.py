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

env = json.load(open("env.json", "r"))

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