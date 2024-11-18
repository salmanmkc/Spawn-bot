import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import json
import asyncio
from collections import deque, defaultdict
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot configuration
TOKEN = os.getenv('DISCORD_TOKEN')
# Load environment variables with debug info
logger.info("Starting bot...")
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
logger.info(f"Token loaded: {'Yes' if TOKEN else 'No'}")
logger.info(f"Token length: {len(TOKEN) if TOKEN else 0}")
PREFIX = '!'

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Load role data from JSON file
def load_roles():
    try:
        with open('roles.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("roles.json not found. Creating empty roles dictionary.")
        return {}

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

class SpawnBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.roles_data = load_roles()

    @commands.command(name='search')
    async def search(self, ctx, keyword: str):
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

                await ctx.send(embed=embed)
        else:
            await ctx.send(f"No results found for '{keyword}'")

    @commands.command(name='modqueue')
    async def modqueue(self, ctx):
        """Join the moderator queue"""
        if ctx.author.id in mod_queue or ctx.author.id in active_mods:
            await ctx.send("You are already in the queue or actively moderating!")
            return

        mod_queue.append(ctx.author.id)
        await ctx.send(f"{ctx.author.mention} has been added to the mod queue! Position: {len(mod_queue)}")

    @commands.command(name='nextmod')
    @commands.has_permissions(administrator=True)
    async def nextmod(self, ctx):
        """Activate the next moderator in queue"""
        if not mod_queue:
            await ctx.send("No moderators in queue!")
            return

        next_mod_id = mod_queue.popleft()
        active_mods.add(next_mod_id)
        next_mod = await bot.fetch_user(next_mod_id)
        await ctx.send(f"{next_mod.mention} is now the active moderator!")

    @commands.command(name='nominate')
    async def nominate(self, ctx, member: discord.Member):
        """Nominate a player for an action."""
        global current_round

        # Check if player was already nominated in this round
        if member.id in nominations[current_round]:
            await ctx.send(f"{member.mention} has already been nominated this round!")
            return

        # Add nomination
        nominations[current_round].append(member.id)
        nomination_message = await ctx.send(f"{ctx.author.mention} has nominated {member.mention}! React with 👍 to support the nomination.")

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

    @commands.command(name='newround')
    @commands.has_permissions(administrator=True)
    async def newround(self, ctx):
        """Start a new round of nominations."""
        global current_round, blood_tests_left, up_for_blood_test
        current_round += 1
        blood_tests_left = 3
        up_for_blood_test = []
        await ctx.send(f"Round {current_round} has begun! All players are now eligible for nomination again. Blood tests available: {blood_tests_left}")
        logger.info(f"New round {current_round} started. Blood tests available: {blood_tests_left}")

    @commands.command(name='*')
    async def spectate(self, ctx):
        """Toggle spectator status for a user"""
        member = ctx.author
        try:
            if member.display_name.startswith('[S]'):
                # Remove spectator status
                new_name = member.display_name[4:]
                await member.edit(nick=new_name)
                await ctx.send(f"{member.mention} is no longer spectating.")
                logger.info(f"{member.display_name} is no longer spectating.")
            else:
                # Add spectator status
                new_name = f"[S] {member.display_name}"
                await member.edit(nick=new_name)
                await ctx.send(f"{member.mention} is now spectating.")
                logger.info(f"{member.display_name} is now spectating.")
        except discord.Forbidden:
            await ctx.send("I don't have permission to change nicknames!")
            logger.error(f"Forbidden error: Could not change nickname for {member.display_name}. Check role hierarchy and permissions.")
        except Exception as e:
            await ctx.send("An unexpected error occurred.")
            logger.error(f"Unexpected error: {str(e)}")

    @commands.command(name='spawn_help')
    async def help_command(self, ctx):
        """Show available commands"""
        help_text = """
**Spawn Game Bot Commands**
`!search <keyword>` - Search for roles or terms
`!modqueue` - Join the moderator queue
`!nextmod` - (Admin only) Activate next moderator
`!nominate <user>` - Nominate a player for an action
`!newround` - (Admin only) Start a new round of nominations
`!*` - Toggle spectator status
        """
        await ctx.send(help_text)

@bot.event
async def on_ready():
    logger.info(f'✅ {bot.user} has connected to Discord!')
    logger.info(f'Bot is ready to use with the following commands:')
    logger.info(f'  !search <keyword> - Search for roles or terms')
    logger.info(f'  !modqueue - Join the moderator queue')
    logger.info(f'  !nextmod - (Admin only) Activate next moderator')
    logger.info(f'  !nominate <user> - Nominate a player for an action')
    logger.info(f'  !newround - (Admin only) Start a new round of nominations')
    logger.info(f'  !* - Toggle spectator status')
    await bot.add_cog(SpawnBot(bot))

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
