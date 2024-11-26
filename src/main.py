import discord
from discord.ui import Button, View, Select
from discord import app_commands
from discord.ext import commands
import os
import logging
import logging.handlers
from polls import intialize_vote
from game import intialize_game
from collections import deque, defaultdict
from roles import load_roles

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables with debug info
logger.info("Starting bot...")
TOKEN = os.getenv('DISCORD_TOKEN')
logger.info(f"Token loaded: {'Yes' if TOKEN else 'No'}")
logger.info(f"Token length: {len(TOKEN) if TOKEN else 0}")

logging.getLogger('discord.http').setLevel(logging.INFO)


# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
API_URL = os.getenv("API_URL")

GUILD = os.getenv("DISCORD_GUILD")

# Load data
SPAWN_ROLES_DATA = load_roles('spawn')

# Moderator queue
mod_queue = deque()
active_mods = set()

# Nominations
nominations = defaultdict(list)  # Keeps track of nominations per round
nominations_data = {}  # Maps message ID to nominated member ID
supports = defaultdict(lambda: defaultdict(int))  # Keeps track of support counts for nominations
current_round = 1
blood_tests_left = 3  # Number of blood tests available per round
up_for_blood_test = []

# Votes
votes = defaultdict(int)  # Track votes for each player
vote_channels = {}  # Store private channels for each player to vote

@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD))
    print(f'We have logged in as {client.user}')


@tree.command(name="play", description="Starts a game", guild=discord.Object(id=GUILD))
async def start_game(interaction:discord.Interaction):
    try:
        await intialize_game(interaction=interaction, data={})
    except Exception as e:
        logger.error(e)
        await interaction.response.send_message("Server Error")


@tree.command(name="vote", description="Starts a vote", guild=discord.Object(id=GUILD))
async def start_vote(interaction:discord.Interaction):
    try:
        await intialize_vote(interaction=interaction, data={})
    except Exception as e:
        logger.error(e)
        await interaction.response.send_message("Server Error")


@tree.command(name="search", description="Search for roles or terms containing the keyword", guild=discord.Object(id=GUILD))
async def search(interaction:discord.Interaction, keyword:str):
    keyword = keyword.lower()
    matched_roles = []

    # Search for roles that match the keyword
    for role, info in SPAWN_ROLES_DATA.items():
        if keyword in role.lower():
            matched_roles.append((role, info))

    # If roles are found, send formatted response
    if matched_roles:
        for role, info in matched_roles:
            embed = discord.Embed(
                title=role,
                description=info.get('power', 'No description available'),
                color=discord.Color.blue()
            )
            embed.add_field(name="Species", value=info.get('species', 'Unknown'), inline=False)
            embed.add_field(name="Alignment", value=info.get('allegiance', 'Unknown'), inline=False)
            embed.add_field(name="Difficulty", value=info.get('difficulty', 'Unknown'), inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(f"No results found for '{keyword}'", ephemeral=True)

@tree.command(name="modqueue", description="Join the moderator queue", guild=discord.Object(id=GUILD))
async def modqueue(interaction:discord.Interaction):
    """Join the moderator queue"""
    if interaction.user.id in mod_queue or interaction.user.id in active_mods:
        await interaction.response.send_message("You are already in the queue or actively moderating!")
        return

    mod_queue.append(interaction.user.id)
    await interaction.response.send_message(f"{interaction.user.mention} has been added to the mod queue! Position: {len(mod_queue)}")

# TODO: add tree command permissions
# @commands.has_permissions(administrator=True)
@tree.command(name="nextmod", description="Activate the next moderator in queue", guild=discord.Object(id=GUILD))
# @tree.has_permissions(administrator=True)
async def nextmod(interaction:discord.Interaction):
    """Activate the next moderator in queue"""
    if not mod_queue:
        await interaction.response.send_message("No moderators in queue!")
        return

    next_mod_id = mod_queue.popleft()
    active_mods.add(next_mod_id)
    next_mod = await interaction.client.fetch_user(next_mod_id)
    await interaction.response.send_message(f"{next_mod.mention} is now the active moderator!")

@tree.command(name="nominate", description="Nominate a player for an action.", guild=discord.Object(id=GUILD))
async def nominate(interaction:discord.Interaction, member: discord.Member):
    """Nominate a player for an action."""
    global current_round

    # Check if player was already nominated in this round
    if member.id in nominations[current_round]:
        await interaction.response.send_message(f"{member.mention} has already been nominated this round!")
        return

    # Add nomination
    nominations[current_round].append(member.id)
    await interaction.response.send_message(f"{interaction.user.mention} has nominated {member.mention}! React with 👍 to support the nomination.")

    # Add message ID and nominated member to the nominations data
    nomination_message = await interaction.original_response()
    nominations_data[nomination_message.id] = member.id

    # Add thumbs up reaction to the message
    await nomination_message.add_reaction('👍')


@client.event
async def on_raw_reaction_add(payload):
        """Handle reactions to support nominations."""
        if payload.emoji.name == '👍':
            channel = await client.fetch_channel(payload.channel_id)
            message_id = payload.message_id

            # Check if the message is a nomination message
            if message_id not in nominations_data:
                return

            message = await channel.fetch_message(message_id)
            user = await client.fetch_user(payload.user_id)

            logger.info(f"Reaction added by: {user.name}, Emoji: {payload.emoji.name}, Message ID: {message_id}")

            if user.bot:
                return

            nominated_id = nominations_data[message_id]
            if user.id == message.mentions[0].id:
                await channel.send(f"{user.mention}, you cannot support your own nomination!")
                return

            # Increment support count for the nomination
            supports[current_round][nominated_id] += 1

            # Check if the nomination has enough supports
            if supports[current_round][nominated_id] >= 2:
                global blood_tests_left
                if blood_tests_left > 0:
                    up_for_blood_test.append(nominated_id)
                    blood_tests_left -= 1
                    nominated_user = await client.fetch_user(nominated_id)
                    await channel.send(f"Nomination successful! {nominated_user.mention} is up for a blood test. Blood tests remaining: {blood_tests_left}")
                    logger.info(f"Nomination successful for {nominated_user.name}. Blood tests remaining: {blood_tests_left}")
                else:
                    await channel.send(f"No blood tests remaining this round!")
                    logger.info("No blood tests remaining this round!")

@tree.command(name="newround", description="Start a new round of nominations.", guild=discord.Object(id=GUILD))
# @commands.has_permissions(administrator=True)
async def newround(interaction:discord.Interaction):
    """Start a new round of nominations."""
    global current_round, blood_tests_left, up_for_blood_test, votes
    current_round += 1
    blood_tests_left = 3
    up_for_blood_test = []
    votes = defaultdict(int)
    await interaction.response.send_message(f"Round {current_round} has begun! All players are now eligible for nomination again. Blood tests available: {blood_tests_left}")
    logger.info(f"New round {current_round} started. Blood tests available: {blood_tests_left}")

client.run(TOKEN)
