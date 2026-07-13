import discord
from discord.ext import commands
from discord import app_commands

import common as common_module

for name in dir(common_module):
    if not name.startswith("_"):
        globals()[name] = getattr(common_module, name)


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
            await interaction.response.send_message(content="Profile updated successfully!", embed=None, view=None, ephemeral=True)
        else:
            await interaction.response.send_message(content=f"An error occurred while updating your profile. Please try again later. Here's your bio if you need to copy and paste:\n{self.profile['bio']}", embed=None, view=None, ephemeral=True)


class Profiles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create-profile", description="Creates a profile for you, viewable using /view-profile!")
    async def create_profile(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        profiles = loadData("profiles")
        if str(interaction.user.id) in profiles.keys():
            await interaction.edit_original_response(content="You already have a profile! Use /view-profile to view it.")
            return
        profiles[str(interaction.user.id)] = {
            "bio": "Nothing yet... use /edit-profile to edit this! Max 256 characters.",
            "links": {},
        }
        if saveData("profiles", profiles):
            await interaction.edit_original_response(content="Profile created successfully!")
        else:
            await interaction.edit_original_response(content="An error occurred while creating your profile. Please try again later.")

    @app_commands.command(name="view-profile", description="View your profile or someone else's!")
    @app_commands.describe(user="The user to view the profile of. Defaults to yourself.", viewprivately="Want to make it so only you can see the profile? (defaults to nah)")
    async def viewprofile(self, interaction: discord.Interaction, user: discord.User = None, viewprivately: bool = False):
        containsatsymbol = ["tiktok", "youtube"]
        await interaction.response.defer(ephemeral=viewprivately)
        if user is None:
            user = interaction.user
        profiles = loadData("profiles")
        if str(user.id) not in profiles:
            await interaction.edit_original_response(content="This user does not have a profile yet! They can create one using /create-profile.")
            return
        profile = profiles[str(user.id)]
        if "color" not in profile:
            profile["color"] = 0x00FF00
        embed = discord.Embed(title=f"{formatUsername(user)}'s Profile", color=profile.get("color", 0x00FF00))
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

    @app_commands.command(name="edit-profile", description="Edit your profile's bio!")
    async def editprofile(self, interaction: discord.Interaction):
        profiles = loadData("profiles")
        if str(interaction.user.id) not in profiles.keys():
            await interaction.response.send_message(content="You don't have a profile yet! Use /create-profile to create one.", ephemeral=True)
            return
        profile = profiles[str(interaction.user.id)]
        await interaction.response.send_modal(ProfileEditModal(profile))

    @app_commands.command(name="delete-profile", description="Delete your profile! This cannot be undone.")
    async def deleteprofile(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        profiles = loadData("profiles")
        if str(interaction.user.id) not in profiles.keys():
            await interaction.edit_original_response(content="You don't have a profile yet! Use /create-profile to create one.")
            return
        del profiles[str(interaction.user.id)]
        if saveData("profiles", profiles):
            await interaction.edit_original_response(content="Profile deleted successfully!")
        else:
            await interaction.edit_original_response(content="An error occurred while deleting your profile. Please try again later.")

    @app_commands.command(name="change-profile-color", description="Change the color of your profile embed! (hex code, no #, default is green)")
    @app_commands.describe(color="The hex code of the color you want to set for your profile embed (no #, default is green)")
    async def changeprofilecolor(self, interaction: discord.Interaction, color: str):
        await interaction.response.defer(ephemeral=True)
        profiles = loadData("profiles")
        if str(interaction.user.id) not in profiles.keys():
            await interaction.edit_original_response(content="You don't have a profile yet! Use /create-profile to create one.")
            return
        try:
            color_value = int(color, 16)
        except ValueError:
            await interaction.edit_original_response(content="Invalid color format. Please use a valid hex code (no #).")
            return
        profiles[str(interaction.user.id)]["color"] = color_value
        if saveData("profiles", profiles):
            await interaction.edit_original_response(content="Profile color updated successfully!")
        else:
            await interaction.edit_original_response(content="An error occurred while updating your profile color. Please try again later.")

    @app_commands.command(name="add-profile-link", description="Add a link to your profile! (tiktok, instagram, twitter, more later!)")
    @app_commands.describe(platform="Only shows supported platforms for now!", username="Your username/handle on the platform (no urls or @, just the username)")
    @app_commands.choices(platform=[
        discord.app_commands.Choice(name="TikTok", value="tiktok"),
        discord.app_commands.Choice(name="Instagram", value="instagram"),
        discord.app_commands.Choice(name="Twitter", value="twitter"),
        discord.app_commands.Choice(name="YouTube", value="youtube"),
    ])
    async def addprofilelink(self, interaction: discord.Interaction, platform: discord.app_commands.Choice[str], username: str):
        await interaction.response.defer(ephemeral=True)
        profiles = loadData("profiles")
        if str(interaction.user.id) not in profiles.keys():
            await interaction.edit_original_response(content="You don't have a profile yet! Use /create-profile to create one.")
            return
        if "links" not in profiles[str(interaction.user.id)]:
            profiles[str(interaction.user.id)]["links"] = {}
        profiles[str(interaction.user.id)]["links"][platform.value] = username
        if not saveData("profiles", profiles):
            await interaction.edit_original_response(content="An error occurred while adding the link to your profile. Please try again later.")
            return
        await interaction.edit_original_response(content="Link added successfully!")

    @app_commands.command(name="remove-profile-link", description="Remove a link from your profile.")
    @app_commands.describe(platform="The platform of the link you want to remove.")
    @app_commands.choices(platform=[
        discord.app_commands.Choice(name="TikTok", value="tiktok"),
        discord.app_commands.Choice(name="Instagram", value="instagram"),
        discord.app_commands.Choice(name="Twitter", value="twitter"),
        discord.app_commands.Choice(name="YouTube", value="youtube"),
    ])
    async def removeprofilelink(self, interaction: discord.Interaction, platform: discord.app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        profiles = loadData("profiles")
        if str(interaction.user.id) not in profiles.keys():
            await interaction.edit_original_response(content="You don't have a profile yet! Use /create-profile to create one.")
            return
        if "links" not in profiles[str(interaction.user.id)] or platform.value not in profiles[str(interaction.user.id)]["links"]:
            await interaction.edit_original_response(content="You don't have a link for that platform on your profile!")
            return
        del profiles[str(interaction.user.id)]["links"][platform.value]
        if not saveData("profiles", profiles):
            await interaction.edit_original_response(content="An error occurred while removing the link from your profile. Please try again later.")
            return
        await interaction.edit_original_response(content="Link removed successfully!")


async def setup(bot: commands.Bot):
    await bot.add_cog(Profiles(bot))
