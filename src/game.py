from roles import load_roles
from polls import intialize_vote
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
    roles = load_roles('werewolf')
    
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
        
        # notify moderators
        for moderator_id in GAMES[self.game_id]['moderators']:
            moderator = await interaction.client.fetch_user(moderator_id)
            await moderator.send(f"{user.display_name} joined the game, {len(GAMES[self.game_id]['players'])} players")
        
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
        
        # notify moderators
        for moderator_id in GAMES[self.game_id]['moderators']:
            moderator = await interaction.client.fetch_user(moderator_id)
            await moderator.send(f"{user.display_name} left the game, {len(GAMES[self.game_id]['players'])} players")
    
    
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
        
        # notify moderators
        for moderator_id in GAMES[self.game_id]['moderators']:
            moderator = await interaction.client.fetch_user(moderator_id)
            await moderator.send(f"{user.display_name} joined the game as mod, {len(GAMES[self.game_id]['players'])} players")
        
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
        self.selected_roles = []
        self.game_id = game_id
        self.data = data
        
        super().__init__()
        
        roles = GAMES[self.game_id]['initial_roles']
        if len(roles) != 0:
            options = [
                SelectOption(label=roles[role_key]['name'], value=role_key)
                for role_key in roles
            ]
            self.role_select = Select(placeholder="Select roles for the game", min_values=1, max_values=len(options), options=options) # 
            self.role_select.callback = self.role_select_callback
            self.add_item(self.role_select)
        
    async def role_select_callback(self, interaction: discord.Interaction):
        self.selected_roles = []
        for value in self.role_select.values:
            role = GAMES[self.game_id]['initial_roles'][value]
            self.selected_roles.append(
                role
            )
        await interaction.response.send_message(
            f"Roles at play updated", ephemeral=True
        )
    
    @discord.ui.button(label="Randomly distribute roles", style=discord.ButtonStyle.success, row=2)
    async def randomly_distribute_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        import random
        roles = self.selected_roles
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
        
        # Game started and button is disabled
        button.disabled = True
        channel = interaction.client.get_channel(GAMES[self.game_id]['channel_id'])
        await interaction.response.edit_message(view=self)
        
        await channel.send(embed=embed)
        #await interaction.followup.send(
        #    embed=embed,
        #)
        
        # message mods the control panel
        for moderator_id in GAMES[self.game_id]['moderators']:
            logger.info(moderator_id)
            user = await interaction.client.fetch_user(moderator_id)
            embed = discord.Embed(
                title=f"{GAMES[self.game_id]['name']} mod panel",
            )
            await user.send(view=ModPanelView(self.game_id), embed=embed)

        for player_id in GAMES[self.game_id]['players']:
            player = GAMES[self.game_id]['players'][player_id]
            user = await interaction.client.fetch_user(player_id)
            if player['role']:
                await user.send(f"The game started and you are... {player['role']['name']} {player['role']['emoji']}")

class ModPanelView(View):
    # sent via dm
    def __init__(self, game_id, data={}):
        self.selected_users = []
        self.game_id = game_id
        self.data = data
        
        super().__init__()
        
        players = GAMES[self.game_id]['players']
        if len(players) != 0:
            options = [
                SelectOption(label=players[player_id]['username'], value=player_id)
                for player_id in players
            ]
            self.user_select = Select(placeholder="Select users for the ballot", min_values=1, max_values=len(options), options=options) # 
            self.user_select.callback = self.user_select_callback
            self.add_item(self.user_select)
    
    async def user_select_callback(self, interaction: discord.Interaction):
        self.selected_users = []
        for value in self.user_select.values:
            player = GAMES[self.game_id]['players'][int(value)]
            self.selected_users.append(
                (player['username'], value)
            )
        await interaction.response.send_message(
            f"Ballot updated", ephemeral=True
        )
    
    # @discord.ui.button(label="Start Nominations", style=discord.ButtonStyle.primary)
    # async def start_nominations(self, interaction: discord.Interaction, button: discord.ui.Button):
    #    await interaction.response.send_message("You started nominations", ephemeral=True)
    
    @discord.ui.button(label="Start Vote", style=discord.ButtonStyle.primary)
    async def start_vote(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.client.get_channel(GAMES[self.game_id]['channel_id'])
        await intialize_vote(interaction, channel, options=self.selected_users, notify_to=GAMES[self.game_id]['moderators'])
        await interaction.response.send_message("You started a vote", ephemeral=True)
