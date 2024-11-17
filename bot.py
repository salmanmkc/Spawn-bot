import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import json
import asyncio
from collections import deque

# Bot configuration
TOKEN = os.getenv('DISCORD_TOKEN')
# Load environment variables with debug info
print("Starting bot...")
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
print(f"Token loaded: {'Yes' if TOKEN else 'No'}")
print(f"Token length: {len(TOKEN) if TOKEN else 0}")
PREFIX = '!'

# Initialize bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Load role data from JSON file
def load_roles():
    try:
        with open('roles.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: roles.json not found. Creating empty roles dictionary.")
        return {}
# Moderator queue
mod_queue = deque()
active_mods = set()

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
            else:
                # Add spectator status
                new_name = f"[S] {member.display_name}"
                await member.edit(nick=new_name)
                await ctx.send(f"{member.mention} is now spectating.")
        except discord.Forbidden:
            await ctx.send("I don't have permission to change nicknames!")
            print(f"Forbidden error: Could not change nickname for {member.display_name}. Check role hierarchy and permissions.")
        except Exception as e:
            await ctx.send("An unexpected error occurred.")
            print(f"Unexpected error: {str(e)}")

    @commands.command(name='spawn_help')
    async def help_command(self, ctx):
        """Show available commands"""
        help_text = """
**Spawn Game Bot Commands**
`!search <keyword>` - Search for roles or terms
`!modqueue` - Join the moderator queue
`!nextmod` - (Admin only) Activate next moderator
`!*` - Toggle spectator status
        """
        await ctx.send(help_text)

# Example roles.json structure
example_roles = {
    "Werewolf": {
        "description": "A villager who secretly kills at night.",
        "alignment": "evil"
    },
    "Seer": {
        "description": "Can see the true role of one player each night.",
        "alignment": "good"
    }
}

@bot.event
async def on_ready():
    print(f'✅ {bot.user} has connected to Discord!')
    print(f'Bot is ready to use with the following commands:')
    print(f'  !search <keyword> - Search for roles or terms')
    print(f'  !modqueue - Join the moderator queue')
    print(f'  !nextmod - (Admin only) Activate next moderator')
    print(f'  !* - Toggle spectator status')
    await bot.add_cog(SpawnBot(bot))

# Run the bot with error handling
if __name__ == "__main__":
    try:
        print("Attempting to start bot...")
        bot.run(TOKEN)
    except discord.LoginFailure as e:
        print(f"❌ Login Failed! Error: {str(e)}")
        print("Common causes:")
        print("1. Token might be invalid or expired")
        print("2. .env file might not be in the correct location")
        print("3. .env file might have extra spaces or quotes")
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")