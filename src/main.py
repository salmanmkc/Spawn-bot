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

client.run(TOKEN)
