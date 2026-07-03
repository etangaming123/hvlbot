import discord
from discord.ext import commands
from discord import app_commands
import json
import random

from common import *


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
    for index in data.keys():
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
    return data[selectedindex]


textvalues = {
    0: "Awful",
    10: "Enemies",
    20: "Terrible",
    30: "Not Too Great",
    40: "Worse than average",
    50: "Barely",
    60: "Not Bad",
    70: "Pretty Good",
    80: "Great",
    90: "Amazing",
    100: "PERFECT!",
    101: "WOAH!!",
}


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="8ball", description="Ask the magic 8ball a question!")
    @app_commands.describe(question="The question to ask the 8ball. (a yes or no question, and keep it short!)")
    async def eight_ball(self, interaction: discord.Interaction, question: str):
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
            "Very doubtful.",
        ]
        await interaction.response.send_message(content=f"You asked the 8ball \"{question}\"...\nThe 8ball says... {random.choice(responses)}")

    @app_commands.command(name="braincells", description="Check how many braincells you (or someone else) has left. (highest is 1000)")
    @app_commands.describe(user="The user to check braincells for (defaults to yourself).")
    async def braincells(self, interaction: discord.Interaction, user: discord.User = None):
        if user is None:
            user = interaction.user
        braincellcount = random.randint(0, 1000)
        await interaction.response.send_message(content=f"{formatUsername(user)} has {braincellcount} braincells.")

    @app_commands.command(name="pizoelectric", description="[Thing] is turning [something else] into electricity!")
    @app_commands.describe(thing="Who is turning something into electricity?", somethingelse="What is being turned into electricity?")
    async def pizoelectric(self, interaction: discord.Interaction, thing: str = None, somethingelse: str = None):
        if thing is None:
            thing = "Japan"
        if somethingelse is None:
            somethingelse = "footsteps"
        await interaction.response.send_message(content=f"{thing} is turning {somethingelse} into electricity! ⚡Using piezoelectric tiles, every step you take generates a small amount of energy. Millions of steps together can power LED lights and displays in busy places like Shibuya Station. A brilliant way to create a sustainable and smart city -- turning movement into clean, renewable energy 🌱💡")

    @app_commands.command(name="ship", description="Ship 2 discord users! (do not take this seriously it's a random number gen)")
    @app_commands.describe(user1="The first user", user2="The second user")
    async def ship(self, interaction: discord.Interaction, user1: discord.User, user2: discord.User):
        await interaction.response.defer()
        if interaction.user.id == user1.id and interaction.user.id == user2.id:
            await interaction.edit_original_response(content="You can't ship yourself with yourself!")
            return
        if user1.id == user2.id:
            await interaction.edit_original_response(content="You can't ship a user with themselves!")
            return

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
        embed.add_field(name="User 1", value=f"{formatUsername(user1)}", inline=True)
        embed.add_field(name="User 2", value=f"{formatUsername(user2)}", inline=True)
        await interaction.edit_original_response(content=f"Shipping {formatUsername(user1)} and {formatUsername(user2)}...", embed=embed)

    @app_commands.command(name="ship-random", description="Ships you with a random user! (do not take this seriously it's a random number gen)")
    async def shiprandom(self, interaction: discord.Interaction):
        await interaction.response.defer()
        realmembers = [member for member in interaction.guild.members if not member.bot and member.id != interaction.user.id]
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
        embed.add_field(name="User 1", value=f"{formatUsername(interaction.user)}", inline=True)
        embed.add_field(name="User 2", value=f"{formatUsername(selected)}", inline=True)
        await interaction.edit_original_response(content=f"Shipping {formatUsername(interaction.user)} and {formatUsername(selected)}...", embed=embed)

    @app_commands.command(name="ship-true-random", description="Ships TWO random users!!!! (do not take this seriously it's a random number gen)")
    async def shiptruerandom(self, interaction: discord.Interaction):
        await interaction.response.defer()
        realmembers = [member for member in interaction.guild.members if not member.bot]
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
        embed.add_field(name="User 1", value=f"{formatUsername(selected1)}", inline=True)
        embed.add_field(name="User 2", value=f"{formatUsername(selected2)}", inline=True)
        await interaction.edit_original_response(content=f"Shipping {formatUsername(selected1)} and {formatUsername(selected2)}...", embed=embed)

    @app_commands.command(name="test-command", description="Internal backend testing for a specific command.")
    @app_commands.describe(user1="The first user", user2="The second user (if needed)", number="0-100")
    async def setcustomship(self, interaction: discord.Interaction, user1: discord.User, user2: discord.User, number: int):
        if interaction.user.id != etanid:
            await interaction.response.send_message("You don't have permission to use this command!", ephemeral=True)
            return
        saveShip(user1.id, user2.id, number)
        await interaction.response.send_message(f"Set {formatUsername(user1)} and {formatUsername(user2)} to {str(number)}%!", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
