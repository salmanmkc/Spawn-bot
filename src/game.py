from roles import ROLES, roles_to_verbose
from discord.ui import Button, View, Select
from discord import SelectOption
import discord
import uuid
import datetime
import logging

logger = logging.getLogger('discord')

STAGES = ['players_join', 'distributing_roles']
GAMES = {}

async def intialize_game(
        interaction,
        data={},
    ):
    game_id = uuid.uuid1()
    roles = ROLES
    
    user = interaction.user
    GAMES[game_id] = {
        'name': f'{user.display_name}\'s game',
        'stage': 'players_join',
        'initial_roles': roles,
        'players': {},
        'moderators': {},
        'created': datetime.datetime.now(),
        'channel_id': interaction.channel_id,
    }
    current_game = GAMES[game_id]
    view = GameStartView(game_id=game_id, data=current_game)
    embed = discord.Embed(
            title=f"{GAMES[game_id]['name']} is about to start",
        )
    #if image:
    #    embed.set_image()
    await interaction.response.send_message(view=view, embed=embed)

class JoinButton(Button):
    def __init__(self, label, game_id):
        self.game_id = game_id
        super().__init__(label=label, style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        if user.id in GAMES[self.game_id]['players']:
            await interaction.response.send_message("You already joined the game", ephemeral=True)
            return
        if GAMES[self.game_id]['stage'] != 'players_join':
            await interaction.response.send_message("The game already started", ephemeral=True)
            return
        GAMES[self.game_id]['players'][user.id] = {
            'username': user.display_name,
            'role': None,
            'is_alive': True
        }
        await interaction.response.send_message("You Joined the game!", ephemeral=True)

class LeaveButton(Button):
    def __init__(self, label, game_id):
        self.game_id = game_id
        super().__init__(label=label, style=discord.ButtonStyle.red)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        if user.id not in GAMES[self.game_id]['players']:
            await interaction.response.send_message("You are not in the game", ephemeral=True)
            return
        if GAMES[self.game_id]['stage'] != 'players_join':
            await interaction.response.send_message("The game already started, ask for a mod kill", ephemeral=True)
            return
        GAMES[self.game_id]['players'].pop(user.id, None)
        await interaction.response.send_message("You left the game", ephemeral=True)


class GameSelect(Select):

    def __init__(self, stage_name, data, **kwargs):
        self.data = data
        self.stage_name = stage_name
        return super().__init__(**kwargs)
            
    
    async def callback(self, interaction: discord.Interaction):
        self.data[self.stage_name] = self.values[0]
        return

class GameStartView(View):
    def __init__(self, game_id, data={}):
        self.game_id = game_id
        self.data = data
        super().__init__()
    
    @discord.ui.button(label="Join!", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user.id in GAMES[self.game_id]['players']:
            await interaction.response.send_message("You already joined the game", ephemeral=True)
            return
        if GAMES[self.game_id]['stage'] != 'players_join':
            await interaction.response.send_message("The game already started", ephemeral=True)
            return
        GAMES[self.game_id]['players'][user.id] = {
            'username': user.display_name,
            'role': None,
            'is_alive': True
        }
        
        await interaction.response.send_message("You Joined the game!", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user.id not in GAMES[self.game_id]['players']:
            await interaction.response.send_message("You are not in the game", ephemeral=True)
            return
        if GAMES[self.game_id]['stage'] != 'players_join':
            await interaction.response.send_message("The game already started, ask for a mod kill", ephemeral=True)
            return
        GAMES[self.game_id]['players'].pop(user.id, None)
        await interaction.response.send_message("You left the game", ephemeral=True)
    
    
    @discord.ui.button(label="Join as mod", style=discord.ButtonStyle.secondary, row=2)
    async def mod_join(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user.id in GAMES[self.game_id]['players']:
            await interaction.response.send_message("You already joined the game as player", ephemeral=True)
            return
        if user.id in GAMES[self.game_id]['moderators']:
            await interaction.response.send_message("You already joined the game as mod", ephemeral=True)
            return
        if GAMES[self.game_id]['stage'] != 'players_join':
            await interaction.response.send_message("The game already started", ephemeral=True)
            return
        GAMES[self.game_id]['moderators'][user.id] = {
            'username': user.display_name,
        }
        await interaction.response.send_message("You Joined the game as mod!", ephemeral=True)
        
        embed = discord.Embed(
            title=f"{GAMES[self.game_id]['name']} setup panel",
        )
        await user.send(view=GameSetupView(self.game_id), embed=embed)


class GameSetupView(View):
    def __init__(self, game_id, data={}):
        self.game_id = game_id
        self.data = data
        
        super().__init__()
        
        players = GAMES[self.game_id]['players']
        if len(players) != 0:
            options = [
                SelectOption(label=players[player_id]['username'], value=player_id)
                for player_id in players
            ]
            user_select = Select(placeholder="Select an user", min_values=1, options=options) # 
            self.add_item(user_select)
    
    @discord.ui.button(label="Randomly distribute roles", style=discord.ButtonStyle.success)
    async def randomly_distribute_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        import random
        roles = GAMES[self.game_id]['initial_roles']
        players = GAMES[self.game_id]['players']
        if len(players) > len(roles):
            await interaction.response.send_message(f"Not enough roles for this amount of users: {len(players)}/{len(roles)}", ephemeral=True)
            return
        random_roles = random.sample(roles, len(players))
        GAMES[self.game_id]['roles_at_play'] = random_roles
        embed = discord.Embed(
            title="This are the randomly assigned roles",
        )
        
        player_list_verbose = []
        role_name_list_verbose = []
        role_faction_list_verbose = []
        for i, user_id in enumerate(players):
            GAMES[self.game_id]['players'][user_id]['role'] = random_roles[i]
            player_list_verbose.append(players[user_id]['username'])
            role_name_list_verbose.append(random_roles[i]['name'] + random_roles[i]['emoji'])
            role_faction_list_verbose.append(random_roles[i]['faction'])
        
        embed.add_field(
            name="Player",
            value='\n'.join(player_list_verbose)
        )
        embed.add_field(
            name="Role",
            value='\n'.join(role_name_list_verbose)
        )
        embed.add_field(
            name="Faction",
            value='\n'.join(role_faction_list_verbose)
        )
        await interaction.response.send_message("This are the asigned roles", embed=embed)
    
    @discord.ui.button(label="Start Game", style=discord.ButtonStyle.primary, row=2)
    async def continue_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        GAMES[self.game_id]['stage'] = 'distributing_roles'
        mod_list_verbose = '\n'.join([x['username'] for x in GAMES[self.game_id]['moderators'].values()])
        player_list_verbose = '\n'.join([x['username'] for x in GAMES[self.game_id]['players'].values()])
        embed = discord.Embed(
                title="Game registration over, starting to distribute roles",
            )
        embed.add_field(
            name="Players", 
            value=player_list_verbose
        )
        embed.add_field(
            name="Moding", 
            value=mod_list_verbose
        )
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            embed=embed,
        )
        
        # message mods the control panel
        for moderator_id in GAMES[self.game_id]['moderators']:
            logger.info(moderator_id)
            user = await interaction.client.fetch_user(moderator_id)
            embed = discord.Embed(
                title=f"{GAMES[self.game_id]['name']} mod panel",
            )
            await user.send(view=ModPanelView(self.game_id), embed=embed)
    
class ModPanelView(View):
    # sent via dm
    def __init__(self, game_id, data={}):
        self.game_id = game_id
        self.data = data
        
        super().__init__()
    
    @discord.ui.button(label="Start Nominations", style=discord.ButtonStyle.primary)
    async def start_nominations(self, interaction: discord.Interaction, button: discord.ui.Button):
        if GAMES[self.game_id]['stage'] != 'running':
            await interaction.response.send_message("The game has not started", ephemeral=True)
            return
        await interaction.response.send_message("You started nominations", ephemeral=True)
    
    @discord.ui.button(label="Start Vote", style=discord.ButtonStyle.primary)
    async def start_vote(self, interaction: discord.Interaction, button: discord.ui.Button):
        if GAMES[self.game_id]['stage'] != 'running':
            await interaction.response.send_message("The game has not started", ephemeral=True)
            return
        await interaction.response.send_message("You started votes", ephemeral=True)
