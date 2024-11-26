import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import os
from dotenv import load_dotenv
import json
import asyncio
from collections import deque, defaultdict
import logging
import random

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
logger.info("Starting bot...")
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
nominations_author = {}  # Maps message ID to the author of the nomination
supports = defaultdict(lambda: defaultdict(int))  # Keeps track of support counts for nominations
current_round = 1
blood_tests_left = 3  # Number of blood tests available per round
up_for_blood_test = []

# Players and roles
players_roles = {}  # Maps player ID to their role (public and private)
signed_up_players = set()  # Set of players who signed up for the game

# Votes
votes = defaultdict(int)  # Track votes for each player

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

    @commands.command(name='startgame')
    async def startgame(self, ctx):
        """Start a new game. Only allowed by the current moderator."""
        if not mod_queue or mod_queue[0] != ctx.author.id:
            await ctx.send("Only the current moderator at the front of the queue can start the game!")
            return

        view = SignupView()
        await ctx.send("A new game is starting! Click the button below to sign up:", view=view)
        logger.info(f"Game signup started by {ctx.author.display_name}")

    @commands.command(name='assignroles')
    async def assignroles(self, ctx):
        """Assign roles to all players who signed up. Only allowed by the current moderator."""
        if not mod_queue or mod_queue[0] != ctx.author.id:
            await ctx.send("Only the current moderator at the front of the queue can assign roles!")
            return

        if not signed_up_players:
            await ctx.send("No players have signed up for the game!")
            return

        roles_list = list(self.roles_data.keys())
        random.shuffle(roles_list)

        servo_bot_count = 0
        for player_id in signed_up_players:
            if roles_list:
                assigned_role = roles_list.pop()
                if assigned_role == "Servo Bot" and servo_bot_count < 4:
                    servo_bot_count += 1
                elif assigned_role == "Servo Bot" and servo_bot_count >= 4:
                    assigned_role = roles_list.pop() if roles_list else "Villager"
            else:
                assigned_role = "Villager"
            players_roles[player_id] = assigned_role
            player_user = await bot.fetch_user(player_id)
            await player_user.send(f"You have been assigned the role: {assigned_role}")
            logger.info(f"Assigned role {assigned_role} to {player_user.display_name}")

        await ctx.send("Roles have been assigned to all players!")
        logger.info("Roles have been assigned to all signed-up players.")
        signed_up_players.clear()

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
        nominations_author[nomination_message.id] = ctx.author.id

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
            nominator_id = nominations_author[message_id]
            if user.id == nominator_id:
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
                if blood_tests_left == 0:
                    await channel.send("Processing blood test results...")
                    logger.info("Processing blood test results...")
                    await self.process_blood_test_results(channel)

    async def process_blood_test_results(self, channel):
        global current_round, up_for_blood_test
        senior_analyst_role = "Senior Analyst"
        hacker_role = "Hacker"
        senior_analyst = None
        hacker_alive = False

        # Find if there is a Senior Analyst and a Hacker in play
        for player_id, role in players_roles.items():
            if role == senior_analyst_role:
                senior_analyst = player_id
            if role == hacker_role:
                hacker_alive = True

        # Determine the number of fails
        fail_count = sum(1 for player_id in up_for_blood_test if players_roles[player_id] in ["Bounty Hunter", "Malware Droid"])

        # If a hacker is alive, randomly adjust the fail count
        if hacker_alive:
            adjustment = random.choice([-1, 0, 1])
            fail_count = max(0, fail_count + adjustment)

        # Send results to the moderator
        moderator_id = mod_queue[0] if mod_queue else None
        if moderator_id:
            moderator = await bot.fetch_user(moderator_id)
            original_fail_count = sum(1 for player_id in up_for_blood_test if players_roles[player_id] in ["Bounty Hunter", "Malware Droid"])
            results_message = f"Blood test results for this round:\nOriginal Fail Count: {original_fail_count}\nAdjusted Fail Count (due to Hacker influence): {fail_count}\n"
            for player_id in up_for_blood_test:
                user = await bot.fetch_user(player_id)
                results_message += f"- {user.display_name}: {players_roles[player_id]}\n"
            await moderator.send(results_message)
            logger.info(f"Sent blood test results to moderator: {moderator.display_name}")

        # Send fail count to the channel
        await channel.send(f"Blood test results: {fail_count} fail(s) detected.")
        logger.info(f"Sent blood test results to channel: {fail_count} fail(s) detected.")

        # Reset blood tests for the next round
        up_for_blood_test = []

    @commands.command(name='vote')
    async def vote(self, ctx):
        """Vote for a player who has been blood tested via DM."""
        if not up_for_blood_test:
            await ctx.send("No players are currently up for a blood test.")
            return

        # Send a DM to the user with buttons to vote
        user = ctx.author
        view = VoteView(up_for_blood_test, user)
        await user.send("Please cast your vote for one of the players up for a blood test:", view=view)
        await ctx.send(f"{user.mention}, check your DMs to cast your vote.")

    @commands.command(name='eject')
    @commands.has_permissions(administrator=True)
    async def eject(self, ctx):
        """Determine if a player should be ejected based on votes."""
        if not votes:
            await ctx.send("No votes have been cast this round.")
            return

        max_votes = max(votes.values())
        ejected_candidates = [member_id for member_id, count in votes.items() if count == max_votes]

        if len(ejected_candidates) == 1:
            ejected_member = await bot.fetch_user(ejected_candidates[0])
            await ctx.send(f"{ejected_member.mention} has been ejected with {max_votes} votes!")
            logger.info(f"{ejected_member.display_name} has been ejected with {max_votes} votes")
        else:
            await ctx.send("No one was ejected due to a tie.")
            logger.info("No one was ejected due to a tie.")

    @commands.command(name='newround')
    @commands.has_permissions(administrator=True)
    async def newround(self, ctx):
        """Start a new round of nominations."""
        global current_round, blood_tests_left, up_for_blood_test, votes
        current_round += 1
        blood_tests_left = 3
        up_for_blood_test = []
        votes = defaultdict(int)
        await ctx.send(f"Round {current_round} has begun! All players are now eligible for nomination again. Blood tests available: {blood_tests_left}")
        logger.info(f"New round {current_round} started. Blood tests available: {blood_tests_left}")

class SignupView(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(SignupButton())

class SignupButton(Button):
    def __init__(self):
        super().__init__(label="Sign Up", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        if user.id in signed_up_players:
            await interaction.response.send_message("You are already signed up for the game.", ephemeral=True)
        else:
            signed_up_players.add(user.id)
            await interaction.response.send_message("You have successfully signed up for the game!", ephemeral=True)
            logger.info(f"{user.display_name} signed up for the game.")

class VoteView(View):
    def __init__(self, candidates, voter):
        super().__init__(timeout=60)
        self.candidates = candidates
        self.voter = voter
        for candidate_id in candidates:
            self.add_item(VoteButton(candidate_id))

class VoteButton(Button):
    def __init__(self, candidate_id):
        self.candidate_id = candidate_id
        super().__init__(label=f"Vote for {candidate_id}", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.view.voter:
            await interaction.response.send_message("You cannot vote on behalf of someone else.", ephemeral=True)
            return

        votes[self.candidate_id] += 1
        await interaction.response.send_message(f"You have successfully voted for <@{self.candidate_id}>.", ephemeral=True)
        logger.info(f"{interaction.user.display_name} voted for {self.candidate_id}")
        self.view.stop()

@bot.event
async def on_ready():
    logger.info(f'✅ {bot.user} has connected to Discord!')
    await bot.add_cog(SpawnBot(bot))

# Run the bot with error handling
if __name__ == "__main__":
    try:
        logger.info("Attempting to start bot...")
        bot.run(TOKEN)
    except discord.LoginFailure as e:
        logger.error(f"❌ Login Failed! Error: {str(e)}")
    except Exception as e:
        logger.error(f"❌ An error occurred: {str(e)}")
