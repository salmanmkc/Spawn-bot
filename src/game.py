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
        'day_number': 0,
        'night_actions': {}
    }
    current_game = GAMES[game_id]
    
    embed = discord.Embed(
            title=f"{GAMES[game_id]['name']} is about to start",
        )
    async def update_user_dashboard(interaction, game_id):
        mod_list_verbose = '\n'.join([x['username'] for x in GAMES[game_id]['moderators'].values()])
        player_list_verbose = '\n'.join([x['username'] for x in GAMES[game_id]['players'].values()])
        embed.clear_fields()
        embed.add_field(
            name="Players", 
            value=player_list_verbose
        )
        embed.add_field(
            name="Moding", 
            value=mod_list_verbose
        )
        await interaction.response.edit_message(embed=embed)
    
    view = GameStartView(game_id=game_id, data=current_game, update_user_dashboard=update_user_dashboard)
    #if image:
    #    embed.set_image()
    await interaction.response.send_message(view=view, embed=embed)

def initializer_player(game_id, user):
    GAMES[game_id]['players'][user.id] = {
        'username': user.display_name,
        'role': None,
        'is_alive': True,
        'death_at_day': None,
    }

async def notify_moderators(game_id, interaction, *args, **kwargs):
    for moderator_id in GAMES[game_id]['moderators']:
        user = await interaction.client.fetch_user(moderator_id)
        await user.send(*args, **kwargs)

class GameSelect(Select):

    def __init__(self, stage_name, data, **kwargs):
        self.data = data
        self.stage_name = stage_name
        return super().__init__(**kwargs)
            
    
    async def callback(self, interaction: discord.Interaction):
        self.data[self.stage_name] = self.values[0]
        return

class GameStartView(View):
    def __init__(self, game_id, update_user_dashboard, data={}):
        self.game_id = game_id
        self.data = data
        self.update_user_dashboard = update_user_dashboard
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
        
        initializer_player(self.game_id, user)
        
        # do not notify moderators
        if False:
            for moderator_id in GAMES[self.game_id]['moderators']:
                moderator = await interaction.client.fetch_user(moderator_id)
                await moderator.send(f"{user.display_name} joined the game, {len(GAMES[self.game_id]['players'])} players")
        
        await self.update_user_dashboard(interaction, self.game_id)
        await interaction.followup.send("You Joined the game!", ephemeral=True)

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
        await self.update_user_dashboard(interaction, self.game_id)
        await interaction.followup.send("You left the game", ephemeral=True)
        
        # notify moderators
        # do not notify moderators
        if False:
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
        
        # do not notify moderators
        if False:
            for moderator_id in GAMES[self.game_id]['moderators']:
                moderator = await interaction.client.fetch_user(moderator_id)
                await moderator.send(f"{user.display_name} joined the game as mod, {len(GAMES[self.game_id]['players'])} players")
        
        GAMES[self.game_id]['moderators'][user.id] = {
            'username': user.display_name,
        }
        await self.update_user_dashboard(interaction, self.game_id)
        await interaction.followup.send("You Joined the game as mod!", ephemeral=True)
        
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
        
        self.set_child_disabled(label='Randomly distribute roles', disabled = False)

        await interaction.response.edit_message(view=self)
            
        await interaction.followup.send(
            f"Roles at play updated", ephemeral=True
        )
    
    def set_child_disabled(self, label, disabled):
        for child in self.children:
            if type(child) is Button and child.label == label:
                child.disabled = disabled
    
    @discord.ui.button(label="Randomly distribute roles", style=discord.ButtonStyle.success, row=2, disabled=True)
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
            description="you can re rol as many times as you want",
        )
        
        player_list_verbose = []
        role_name_list_verbose = []
        role_faction_list_verbose = []
        for i, user_id in enumerate(players):
            GAMES[self.game_id]['players'][user_id]['role'] = random_roles[i]
            player_list_verbose.append(players[user_id]['username'])
            role_name_list_verbose.append(f"{random_roles[i]['name']} {random_roles[i]['emoji']}")
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
        
        self.set_child_disabled(label='Start Game', disabled = False)
        
        await interaction.response.edit_message(view=self)
            
        await interaction.followup.send("This are the asigned roles", embed=embed)
    
    @discord.ui.button(label="Start Game", style=discord.ButtonStyle.primary, row=2, disabled=True)
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
        
        # Game started and buttons get disabled
        button.disabled = True
        self.role_select.disabled = True
        self.set_child_disabled(label='Randomly distribute roles', disabled = True)
        await interaction.response.edit_message(view=self)
        
        channel = interaction.client.get_channel(GAMES[self.game_id]['channel_id'])
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
            self.user_select = Select(placeholder="Select users for the ballot", min_values=1, max_values=len(options), options=options, disabled=True) # 
            self.user_select.callback = self.user_select_callback
            self.add_item(self.user_select)
    
    def set_child_disabled(self, label, disabled):
        for child in self.children:
            if type(child) is Button and child.label == label:
                child.disabled = disabled
    
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
    
    @discord.ui.button(label="Start Vote", style=discord.ButtonStyle.primary, disabled=True)
    async def start_vote(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.client.get_channel(GAMES[self.game_id]['channel_id'])
        await intialize_vote(interaction, channel, options=self.selected_users, notify_to=GAMES[self.game_id]['moderators'])
        await interaction.response.send_message("You started a vote", ephemeral=True)
    
    @discord.ui.button(label="Start Night", style=discord.ButtonStyle.primary)
    async def start_night(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.client.get_channel(GAMES[self.game_id]['channel_id'])
        GAMES[self.game_id]['day_number'] += 1
        await channel.send(f"Night {GAMES[self.game_id]['day_number']} is upon us :new_moon_with_face:")
        await self.message_night_actions(interaction)
        
        # disable night, enable day
        button.disabled = True
        self.set_child_disabled('Start Day', disabled=False)
        self.set_child_disabled('Start Vote', disabled=True)
        self.user_select.disabled=True
        await interaction.response.edit_message(view=self)
        
        await interaction.followup.send("You started Night phase", ephemeral=True)
        
    async def message_night_actions(self, interaction):
        day_number = GAMES[self.game_id]['day_number']
        total_players = GAMES[self.game_id]['players']
        alive_players = {p_id:total_players[p_id] for p_id in total_players if total_players[p_id]['is_alive']}
        
        for player_id in alive_players:
            player_data = GAMES[self.game_id]['players'][player_id]
            role = player_data['role']
            night_action = role.get('night_action')
            night_action_on = role.get('night_action_on')
            if not night_action:
                continue
            
            user = await interaction.client.fetch_user(player_id)
            is_select = True
            selections = []
            if is_select:
                if night_action_on == 'night deaths':
                    # message should be sent after wolfs decide
                    continue
                if night_action_on == 'last deaths':
                    selections = {p_id:total_players[p_id] for p_id in total_players if total_players[p_id]['death_at_day'] != day_number - 1}
                elif night_action_on == 'alive':
                    selections = alive_players
                elif night_action_on == 'other alive':
                    selections = {p_id:total_players[p_id] for p_id in total_players if p_id != player_id}
            if len(selections) != 0:
                options = [
                    SelectOption(label=selections[role_key]['username'], value=role_key)
                    for role_key in selections
                ]
                night_action_select = Select(placeholder=f"Select player to {night_action}", min_values=1, max_values=1, options=options) #
                async def night_action_select_callback(interaction: discord.Interaction):
                    return await self.role_night_action_select_callback(interaction, role, night_action_select)
                night_action_select.callback = night_action_select_callback
                view = View()
                view.add_item(night_action_select)
                await user.send(f"action for night {day_number} {role['emoji']}", view=view)
    
    async def role_night_action_select_callback(self, interaction: discord.Interaction, role, night_action_select):
        day_number = GAMES[self.game_id]['day_number']
        night_order = role.get('night_order')
        
        # clean selection
        selections = []
        verbose_selections = []
        for value in night_action_select.values:
            player = GAMES[self.game_id]['players'][int(value)]
            selections.append(
                player
            )
            verbose_selections.append(player['username'])
        verbose_selections = ', '.join(verbose_selections)
        
        # intialize night if not already
        if day_number not in GAMES[self.game_id]['night_actions']:
            GAMES[self.game_id]['night_actions'][day_number] = {}
        
        # set night action
        GAMES[self.game_id]['night_actions'][day_number][night_order] = {
            'role': role,
            'selections': selections
        }
        
        await notify_moderators(self.game_id, interaction, f"{interaction.user.display_name} {role['name']} {role['emoji']} selected {verbose_selections} for {role['night_action']}")
        
        await interaction.response.send_message(
            f"Selection updated", ephemeral=True
        )

    @discord.ui.button(label="Start Day", style=discord.ButtonStyle.primary, disabled=True)
    async def start_day(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.client.get_channel(GAMES[self.game_id]['channel_id'])
        await channel.send(f"The sun rises :sun_with_face:, Day {GAMES[self.game_id]['day_number']}")
        
        # disable day, enable night
        button.disabled=True
        self.set_child_disabled('Start Night', disabled=False)
        self.set_child_disabled('Start Vote', disabled=False)
        self.user_select.disabled=False
        await interaction.response.edit_message(view=self)
        
        await interaction.followup.send("You started Day phase", ephemeral=True)
    