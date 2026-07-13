import discord
from discord.ext import commands
from discord import app_commands

from common import experimentalqueuecheckchannelid, formatUsername, loadData, saveData, truncateMessage, returnAllAlts, serverid, etanid, membercountid, bottraproleid, messageloggingchannelid, weatherannouncementschannelid, returnAllAlts, formatUsername, loadData, saveData, truncateMessage, prescencecycles, openweatherapikey, lastcachedmembercount, didwealreadyreset, didwealreadyresetanditsnight, userlastbuttontimebutmorepermanent, memberroleid, altaccountroleid, ruiroleid, joinandleavechannelid, SUPASECRETLOGGINGCHANNELID, moderatorroleid, moderatorplusplusroleid, channelstolockdown, bottrapchannelid, weatherannouncementschannelid, experimentalqueuecheckchannelid, playersinqueue, playersplaying, userincontrol, userlastbuttontime, getDisplay, env, starboardchannel



class Achievements(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create-achievement", description="Make new achievement")
    @app_commands.describe(name="Name of the achievement", description="Description of the achievement", vanity="Should this achievement have a role?")
    async def createachievement(self, interaction: discord.Interaction, name: str, description: str, vanity: bool = False):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You don't have permission to use this command!")
            return

        achievementdata = loadData("achievements")
        if achievementdata == "":
            await interaction.edit_original_response(content="An error occurred while loading achievement data.")
            return

        achievementid = 1
        while str(achievementid) in achievementdata:
            achievementid += 1

        if vanity:
            guild = self.bot.get_guild(serverid)
            role = await guild.create_role(name=f"{name}", mentionable=False)
            memberrole = guild.get_role(memberroleid)
            await role.edit(position=(memberrole.position - 1))
            achievementdata[str(achievementid)] = {
                "name": name,
                "description": description,
                "roleid": role.id,
            }
        else:
            achievementdata[str(achievementid)] = {
                "name": name,
                "description": description,
                "roleid": None,
            }

        if not saveData("achievements", achievementdata):
            await interaction.edit_original_response(content="An error occurred while saving achievement data.")
            return
        await interaction.edit_original_response(content=f"Achievement created successfully with ID {achievementid}!")

    @app_commands.command(name="edit-achievement", description="Edit an existing achievement")
    @app_commands.describe(id="The id of the achievement you want to edit.", name="New name of the achievement", description="New description of the achievement")
    async def editachievement(self, interaction: discord.Interaction, id: str, name: str = None, description: str = None):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You don't have permission to use this command!")
            return

        achievementdata = loadData("achievements")
        if achievementdata == "":
            await interaction.edit_original_response(content="An error occurred while loading achievement data.")
            return

        achievementinfo = achievementdata.get(str(id))
        if not achievementinfo:
            await interaction.edit_original_response(content="That achievement does not exist.")
            return

        if name:
            achievementinfo["name"] = name
        if description:
            achievementinfo["description"] = description
        achievementdata[str(id)] = achievementinfo

        if not saveData("achievements", achievementdata):
            await interaction.edit_original_response(content="An error occurred while saving achievement data.")
            return
        await interaction.edit_original_response(content="Achievement edited successfully!")

    @app_commands.command(name="equip-achievement", description="Equip an achievement you have earned to show off your accomplishment!")
    @app_commands.describe(achievement="The achievement you want to equip.")
    async def equipachievement(self, interaction: discord.Interaction, achievement: str):
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
            if item.id in achievementroleids and item.id != achievementinfo.get("roleid"):
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
    async def equipachievement_autocomplete(self, interaction: discord.Interaction, current: str):
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

    @app_commands.command(name="player-achievements", description="View all achievements you or someone else have earned!")
    @app_commands.describe(user="The user to check achievements for. Defaults to yourself.")
    async def listachievements(self, interaction: discord.Interaction, user: discord.User = None):
        await interaction.response.defer(ephemeral=True)
        if user is None:
            user = interaction.user

        allachievements = loadData("achievements")
        playerachievements = loadData("playerachievements")
        if allachievements == "" or playerachievements == "":
            await interaction.edit_original_response(content="An error occurred while loading achievement data.")
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

    @app_commands.command(name="award-achievement", description="Award an achievement to a user!")
    @app_commands.describe(user="The user to award the achievement to.", achievement="The achievement to award by ID.")
    async def awardachievement(self, interaction: discord.Interaction, user: discord.User, achievement: str):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You don't have permission to use this command!")
            return

        allachievements = loadData("achievements")
        playerachievements = loadData("playerachievements")
        if allachievements == "" or playerachievements == "":
            await interaction.edit_original_response(content="An error occurred while loading achievement data.")
            return

        achievementinfo = allachievements.get(str(achievement))
        if not achievementinfo:
            await interaction.edit_original_response(content="That achievement does not exist.")
            return
        if str(user.id) not in playerachievements:
            playerachievements[str(user.id)] = []
        if achievement in playerachievements[str(user.id)]:
            await interaction.edit_original_response(content="That user already has that achievement!")
            return

        playerachievements[str(user.id)].append(achievement)
        saveData("playerachievements", playerachievements)
        await interaction.edit_original_response(content=f"Awarded the achievement '{achievementinfo.get('name')}' to {user.mention}!")

    @app_commands.command(name="list-achievements", description="List all achievement names and ids (owner only)")
    async def listallachievements(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != etanid:
            await interaction.edit_original_response(content="You don't have permission to use this command!")
            return

        allachievements = loadData("achievements")
        if allachievements == "":
            await interaction.edit_original_response(content="An error occurred while loading achievement data.")
            return
        if not allachievements:
            await interaction.edit_original_response(content="There are no achievements yet!")
            return

        string = "All achievements:\n"
        for achievementid, achievementinfo in allachievements.items():
            string += f"- {achievementinfo.get('name', f'ID {achievementid}')} (ID: {achievementid})\n"

        await interaction.edit_original_response(content=string)


async def setup(bot: commands.Bot):
    await bot.add_cog(Achievements(bot))
