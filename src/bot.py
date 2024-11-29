import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import json
import asyncio
from collections import deque, defaultdict
import logging
from roles import load_roles

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot configuration
TOKEN = os.getenv('DISCORD_TOKEN')
# Load environment variables with debug info
logger.info("Starting bot...")
TOKEN = os.getenv('DISCORD_TOKEN')
logger.info(f"Token loaded: {'Yes' if TOKEN else 'No'}")
logger.info(f"Token length: {len(TOKEN) if TOKEN else 0}")
PREFIX = '!'
GUILD = os.getenv("DISCORD_GUILD")


# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

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

class SpawnBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.roles_data = load_roles('spawn')

    @app_commands.command(name='search')
    async def search(self, interaction: discord.Interaction, keyword: str):
        """Search for roles or terms containing the keyword"""
        keyword = keyword.lower()
        matched_roles = []

        # Search for roles that match the keyword
        for role, info in self.roles_data.items():
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

                await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"No results found for '{keyword}'")

    @app_commands.command(name='modqueue')
    async def modqueue(self, interaction: discord.Interaction):
        """Join the moderator queue"""
        if interaction.user.id in mod_queue or interaction.user.id in active_mods:
            await interaction.response.send_message("You are already in the queue or actively moderating!")
            return

        mod_queue.append(interaction.user.id)
        await interaction.response.send_message(f"{interaction.user.mention} has been added to the mod queue! Position: {len(mod_queue)}")

    @app_commands.command(name='nextmod')
    @commands.has_permissions(administrator=True)
    async def nextmod(self, interaction: discord.Interaction):
        """Activate the next moderator in queue"""
        if not mod_queue:
            await interaction.response.send_message("No moderators in queue!")
            return

        next_mod_id = mod_queue.popleft()
        active_mods.add(next_mod_id)
        next_mod = await bot.fetch_user(next_mod_id)
        await interaction.response.send_message(f"{next_mod.mention} is now the active moderator!")

    @app_commands.command(name='nominate')
    async def nominate(self, interaction: discord.Interaction, member: discord.Member):
        """Nominate a player for an action."""
        global current_round

        # Check if player was already nominated in this round
        if member.id in nominations[current_round]:
            await interaction.response.send_message(f"{member.mention} has already been nominated this round!")
            return

        # Add nomination
        nominations[current_round].append(member.id)
        nomination_message = await interaction.response.send_message(f"{interaction.user.mention} has nominated {member.mention}! React with 👍 to support the nomination.")

        # Add message ID and nominated member to the nominations data
        nominations_data[nomination_message.id] = member.id

        # Add thumbs up reaction to the message
        await nomination_message.add_reaction('👍')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle reactions to support nominations."""
        if payload.emoji.name == '👍':
            channel = await bot.fetch_channel(payload.channel_id)
            message_id = payload.message_id

            # Check if the message is a nomination message
            if message_id not in nominations_data:
                return

            message = await channel.fetch_message(message_id)
            user = await bot.fetch_user(payload.user_id)

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
                    nominated_user = await bot.fetch_user(nominated_id)
                    await channel.send(f"Nomination successful! {nominated_user.mention} is up for a blood test. Blood tests remaining: {blood_tests_left}")
                    logger.info(f"Nomination successful for {nominated_user.name}. Blood tests remaining: {blood_tests_left}")
                else:
                    await channel.send(f"No blood tests remaining this round!")
                    logger.info("No blood tests remaining this round!")

    @app_commands.command(name='newround')
    @commands.has_permissions(administrator=True)
    async def newround(self, interaction: discord.Interaction):
        """Start a new round of nominations."""
        global current_round, blood_tests_left, up_for_blood_test, votes
        current_round += 1
        blood_tests_left = 3
        up_for_blood_test = []
        votes = defaultdict(int)
        await interaction.response.send_message(f"Round {current_round} has begun! All players are now eligible for nomination again. Blood tests available: {blood_tests_left}")
        logger.info(f"New round {current_round} started. Blood tests available: {blood_tests_left}")

    @app_commands.command(name='create_vote_channels')
    @commands.has_permissions(administrator=True)
    async def create_vote_channels(self, interaction: discord.Interaction):
        """Create private voting channels for each member and the moderator."""
        guild = interaction.guild
        moderator_role = discord.utils.get(guild.roles, name='Moderator')

        for member in guild.members:
            if not member.bot:
                # Create a private channel for each member
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    member: discord.PermissionOverwrite(read_messages=True),
                    moderator_role: discord.PermissionOverwrite(read_messages=True)
                }
                channel = await guild.create_text_channel(f'vote-{member.display_name}', overwrites=overwrites)
                vote_channels[member.id] = channel.id
                logger.info(f"Created voting channel for {member.display_name}")

    @app_commands.command(name='vote')
    async def vote(self, interaction: discord.Interaction, member: discord.Member):
        """Vote for a player who has been blood tested."""
        if interaction.channel.id != vote_channels.get(interaction.user.id):
            await interaction.response.send_message("You can only vote in your private voting channel.")
            return

        if member.id not in up_for_blood_test:
            await interaction.response.send_message(f"{member.mention} is not eligible for voting this round!")
            return

        votes[member.id] += 1
        await interaction.response.send_message(f"Your vote for {member.mention} has been recorded.")
        logger.info(f"{interaction.user.display_name} voted for {member.display_name}")

    @commands.command(name='eject')
    @commands.has_permissions(administrator=True)
    async def eject(self, interaction: discord.Interaction):
        """Determine if a player should be ejected based on votes."""
        if not votes:
            await interaction.response.send_message("No votes have been cast this round.")
            return

        max_votes = max(votes.values())
        ejected_candidates = [member_id for member_id, count in votes.items() if count == max_votes]

        if len(ejected_candidates) == 1:
            ejected_member = await bot.fetch_user(ejected_candidates[0])
            await interaction.response.send_message(f"{ejected_member.mention} has been ejected with {max_votes} votes!")
            logger.info(f"{ejected_member.display_name} has been ejected with {max_votes} votes")
        else:
            await interaction.response.send_message("No one was ejected due to a tie.")
            logger.info("No one was ejected due to a tie.")

    @commands.command(name='*')
    async def spectate(self, interaction: discord.Interaction):
        """Toggle spectator status for a user"""
        member = interaction.user
        try:
            if member.display_name.startswith('[S]'):
                # Remove spectator status
                new_name = member.display_name[4:]
                await member.edit(nick=new_name)
                await interaction.response.send_message(f"{member.mention} is no longer spectating.")
                logger.info(f"{member.display_name} is no longer spectating.")
            else:
                # Add spectator status
                new_name = f"[S] {member.display_name}"
                await member.edit(nick=new_name)
                await interaction.response.send_message(f"{member.mention} is now spectating.")
                logger.info(f"{member.display_name} is now spectating.")
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to change nicknames!")
            logger.error(f"Forbidden error: Could not change nickname for {member.display_name}. Check role hierarchy and permissions.")
        except Exception as e:
            await interaction.response.send_message("An unexpected error occurred.")
            logger.error(f"Unexpected error: {str(e)}")

    @commands.command(name='spawn_help')
    async def help_command(self, interaction: discord.Interaction):
        """Show available commands"""
        help_text = """
**Spawn Game Bot Commands**
`!search <keyword>` - Search for roles or terms
`!modqueue` - Join the moderator queue
`!nextmod` - (Admin only) Activate next moderator
`!nominate <user>` - Nominate a player for an action
`!newround` - (Admin only) Start a new round of nominations
`!create_vote_channels` - (Admin only) Create private voting channels for each player
`!vote <user>` - Vote for a player who has been blood tested
`!eject` - (Admin only) Determine if a player should be ejected based on votes
`!*` - Toggle spectator status
        """
        await interaction.response.send_message(help_text)

@bot.event
async def on_ready():
    logger.info(f'✅ {bot.user} has connected to Discord!')
    logger.info(f'Bot is ready to use with the following commands:')
    logger.info(f'  !search <keyword> - Search for roles or terms')
    logger.info(f'  !modqueue - Join the moderator queue')
    logger.info(f'  !nextmod - (Admin only) Activate next moderator')
    logger.info(f'  !nominate <user> - Nominate a player for an action')
    logger.info(f'  !newround - (Admin only) Start a new round of nominations')
    logger.info(f'  !create_vote_channels - (Admin only) Create private voting channels for each player')
    logger.info(f'  !vote <user> - Vote for a player who has been blood tested')
    logger.info(f'  !eject - (Admin only) Determine if a player should be ejected based on votes')
    logger.info(f'  !* - Toggle spectator status')
    await bot.add_cog(SpawnBot(bot), guilds=[discord.Object(id=GUILD)]) # guilds_ids=[discord.Object(id=GUILD)]
    await bot.tree.sync(guild=discord.Object(id=GUILD))


# Run the bot with error handling
if __name__ == "__main__":
    try:
        logger.info("Attempting to start bot...")
        bot.run(TOKEN)
    except discord.LoginFailure as e:
        logger.error(f"❌ Login Failed! Error: {str(e)}")
        logger.error("Common causes:")
        logger.error("1. Token might be invalid or expired")
        logger.error("2. .env file might not be in the correct location")
        logger.error("3. .env file might have extra spaces or quotes")
    except Exception as e:
        logger.error(f"❌ An error occurred: {str(e)}")