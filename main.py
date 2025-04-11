from dotenv import load_dotenv
import os
import discord
from discord import app_commands
from discord.ext import commands
from pymongo import MongoClient
import aiohttp
import random
import json

# MongoDB setup
load_dotenv()

TOKEN = os.getenv("TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["discord_bot"]
collection = db["auto_replies"]

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

GUILD_ID = discord.Object(id=840157628628729857)  # Replace with your server (guild) ID

# Utility: check if user is admin
def is_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.administrator

@bot.event
async def on_ready():
    await tree.sync(guild=GUILD_ID)
    print(f"Logged in as {bot.user.name}")
    
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if not before.premium_since and after.premium_since:
        channel = after.guild.system_channel or discord.utils.get(after.guild.text_channels, name="boost")
        if channel:
            await channel.send(f"**{after.mention} just boosted the server!** Thank you for the support!")
    

# Slash Command: /ping
@tree.command(name="ping", description="Check the bot's latency", guild=GUILD_ID)
async def ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency is **{latency_ms}ms**.")

# Slash Command: Add new auto-reply
@tree.command(name="autoreply", description="Set a new auto-reply", guild=GUILD_ID)
@app_commands.describe(trigger="Word to trigger the reply", response="Bot's response message")
async def autoreply(interaction: discord.Interaction, trigger: str, response: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("You must be an admin to use this.", ephemeral=True)

    collection.update_one(
        {"guild_id": interaction.guild.id, "trigger": trigger.lower()},
        {"$set": {"response": response}},
        upsert=True
    )
    await interaction.response.send_message(f'Auto-reply added: **"{trigger}"** → "{response}"', ephemeral=True)

# Slash Command: Edit existing reply
@tree.command(name="editreply", description="Edit an existing auto-reply", guild=GUILD_ID)
@app_commands.describe(trigger="Existing trigger word", new_response="New reply text")
async def editreply(interaction: discord.Interaction, trigger: str, new_response: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("You must be an admin to use this.", ephemeral=True)

    result = collection.update_one(
        {"guild_id": interaction.guild.id, "trigger": trigger.lower()},
        {"$set": {"response": new_response}}
    )
    if result.matched_count:
        await interaction.response.send_message(f'Reply for **"{trigger}"** updated.', ephemeral=True)
    else:
        await interaction.response.send_message(f'No existing reply found for **"{trigger}"**.', ephemeral=True)

# Slash Command: Delete a reply
@tree.command(name="deletereply", description="Delete an auto-reply", guild=GUILD_ID)
@app_commands.describe(trigger="Trigger word to delete")
async def deletereply(interaction: discord.Interaction, trigger: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("You must be an admin to use this.", ephemeral=True)

    result = collection.delete_one({"guild_id": interaction.guild.id, "trigger": trigger.lower()})
    if result.deleted_count:
        await interaction.response.send_message(f'Reply for **"{trigger}"** deleted.', ephemeral=True)
    else:
        await interaction.response.send_message(f'No auto-reply found for **"{trigger}"**.', ephemeral=True)

# Slash Command: List all auto-replies
@tree.command(name="listreplies", description="List all current auto-reply triggers", guild=GUILD_ID)
async def listreplies(interaction: discord.Interaction):
    replies = collection.find({"guild_id": interaction.guild.id})
    triggers = [f'• **{doc["trigger"]}** → {doc["response"]}' for doc in replies]

    if triggers:
        response = "\n".join(triggers)
    else:
        response = "No auto-replies have been set yet."

    await interaction.response.send_message(response, ephemeral=True)

# Slash Command: Admin-only /say
@tree.command(name="say", description="Make the bot say something", guild=GUILD_ID)
@app_commands.describe(message="The message the bot will say")
async def say(interaction: discord.Interaction, message: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("You must be an admin to use this.", ephemeral=True)

    await interaction.response.send_message("Sent!", ephemeral=True)
    await interaction.channel.send(message)
    
    
# Slash Command: /createembed
@tree.command(name="createembed", description="Send one or more embeds using full JSON format", guild=GUILD_ID)
@app_commands.describe(data="Embed JSON with 'embeds' key (like webhook format)")
async def createembed(interaction: discord.Interaction, data: str):
    if not is_admin(interaction):
        return await interaction.response.send_message("You must be an admin to use this.", ephemeral=True)

    try:
        parsed = json.loads(data)

        if not isinstance(parsed, dict) or "embeds" not in parsed:
            return await interaction.response.send_message("Invalid JSON format. Wrap your data in `{\"embeds\": [...]}`.", ephemeral=True)

        embeds = []
        for e in parsed["embeds"]:
            embed = discord.Embed(
                title=e.get("title", ""),
                description=e.get("description", ""),
                color=e.get("color", 0x2f3136)
            )

            # Handle nested dicts for footer, thumbnail, image
            if "footer" in e and isinstance(e["footer"], dict):
                embed.set_footer(text=e["footer"].get("text", ""))

            if "thumbnail" in e and isinstance(e["thumbnail"], dict):
                embed.set_thumbnail(url=e["thumbnail"].get("url", ""))

            if "image" in e and isinstance(e["image"], dict):
                embed.set_image(url=e["image"].get("url", ""))

            if "fields" in e and isinstance(e["fields"], list):
                for field in e["fields"]:
                    embed.add_field(
                        name=field.get("name", "No Name"),
                        value=field.get("value", "No Value"),
                        inline=field.get("inline", False)
                    )

            embeds.append(embed)

        await interaction.response.send_message("Embed(s) sent!", ephemeral=True)
        await interaction.channel.send(embeds=embeds)

    except json.JSONDecodeError:
        await interaction.response.send_message("❌ Invalid JSON. Paste must be valid JSON format.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: `{str(e)}`", ephemeral=True)

# Slash Command: /howgay
@tree.command(name="howgay", description="Check how gay someone is", guild=GUILD_ID)
@app_commands.describe(user="User to rate")
async def howgay(interaction: discord.Interaction, user: discord.Member):
    percent = random.randint(0, 100)

    if percent >= 90:
        emoji = "🌈🔥"
        comment = "Certified rainbow legend!"
    elif percent >= 70:
        emoji = "🌈"
        comment = "Super fabulously gay!"
    elif percent >= 40:
        emoji = "✨"
        comment = "Slight sparkle detected!"
    else:
        emoji = "❌"
        comment = "Not gay... but maybe in denial?"

    await interaction.response.send_message(
        f"{emoji} **{user.mention} is {percent}% gay!**\n*{comment}*"
    )

# Slash Command: /ship
@tree.command(name="ship", description="Ship two users and see their compatibility", guild=GUILD_ID)
@app_commands.describe(user1="First user", user2="Second user")
async def ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    percent = random.randint(0, 100)

    if percent >= 90:
        emoji = "❤️‍🔥"
        comment = "SOULMATES! Meant to be!"
    elif percent >= 70:
        emoji = "❤️"
        comment = "Cute couple potential!"
    elif percent >= 40:
        emoji = "💞"
        comment = "Some sparks flying!"
    else:
        emoji = "💔"
        comment = "Better as friends..."

    await interaction.response.send_message(
        f"{emoji} **{user1.mention} + {user2.mention} = {percent}% love match!**\n*{comment}*"
    )
    

# Slash Command: /pickupline (API-based)
@tree.command(name="pickupline", description="Send a pickup line to someone", guild=GUILD_ID)
@app_commands.describe(user="Who do you want to flirt with?")
async def pickupline(interaction: discord.Interaction, user: discord.Member):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://testwary.vercel.app/api/gombal") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    line = data.get("data", {}).get("gombal_wrd", "You're looking fine today!")
                else:
                    line = "You're looking fine today!"
        except Exception:
            line = "You're looking fine today!"

    await interaction.response.send_message(f"{user.mention}, {line}")
    
 # Slash Command: /choose
@tree.command(name="choose", description="Let the bot choose between multiple options", guild=GUILD_ID)
@app_commands.describe(options="Separate choices with | (example: apple | banana | orange)")
async def choose(interaction: discord.Interaction, options: str):
    choices = [opt.strip() for opt in options.split("|") if opt.strip()]

    if len(choices) < 2:
        await interaction.response.send_message("Please provide at least two choices separated by `|`.", ephemeral=True)
        return

    picked = random.choice(choices)
    await interaction.response.send_message(f"I choose: **{picked}**!")
    
    
# Listen for trigger words (exact match, case-insensitive)
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    record = collection.find_one({
        "guild_id": message.guild.id,
        "trigger": message.content.lower()
    })
    if record:
        await message.channel.send(record["response"])

    await bot.process_commands(message)

# Run the bot
bot.run("TOKEN")