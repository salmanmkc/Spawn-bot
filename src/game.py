from roles import load_roles
from polls import intialize_vote, top_two_poll_results
from discord.ui import Button, View, Select, UserSelect
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
        'night_actions': {},
        'day_nominations': {},
        'role_id': '<@&1316122485741191179>'# <@&1313162194086793286>'
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

def initialize_player(game_id, user):
    GAMES[game_id]['players'][user.id] = {
        'id': user.id,
        'username': user.display_name,
        'role': None,
        'is_alive': True,
        'death_at_day': None,
    }

async def notify_moderators(game_id, interaction, *args, **kwargs):
    for moderator_id in GAMES[game_id]['moderators']:
        user = await interaction.client.fetch_user(moderator_id)
        await user.send(*args, **kwargs)

async def edit_moderators_pannel(game_id, interaction, *args, **kwargs):
    for moderator_id, moderator in GAMES[game_id]['moderators'].items():
        user = await interaction.client.fetch_user(moderator_id)
        mod_panel_message_id = moderator.get('mod_panel_message')
        message = await user.fetch_message(mod_panel_message_id)
        await message.edit(*args, **kwargs)

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
        
        self.user_select = UserSelect(placeholder="Add users", min_values=1, max_values=10, disabled=False) # 
        self.user_select.callback = self.user_select_callback
        self.add_item(self.user_select)
    
    async def user_select_callback(self, interaction: discord.Interaction):
        if interaction.user.id not in GAMES[self.game_id]['moderators']:
            await interaction.response.send_message(
                f"Only mods can add users", ephemeral=True
            )
            return
        self.selected_users = []
        for user in self.user_select.values:
            initialize_player(self.game_id, user)
        await self.update_user_dashboard(interaction, self.game_id)
        await interaction.followup.send(
            f"Added user(s) to game", ephemeral=True
        )
    
    @discord.ui.button(label="Join!", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        if user.id in GAMES[self.game_id]['players']:
            await interaction.response.send_message("You already joined the game", ephemeral=True)
            return
        if GAMES[self.game_id]['stage'] != 'players_join':
            await interaction.response.send_message("The game already started", ephemeral=True)
            return
        
        initialize_player(self.game_id, user)
        
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
            'mod_panel_message': None,
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
                SelectOption(label=f"{roles[role_key]['name']} {roles[role_key]['emoji']}", value=role_key)
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
            mod_panel_message = await user.send(view=ModPanelView(self.game_id), embed=embed)
            GAMES[self.game_id]['moderators'][moderator_id]['mod_panel_message'] = mod_panel_message.id

        for player_id in GAMES[self.game_id]['players']:
            player = GAMES[self.game_id]['players'][player_id]
            user = await interaction.client.fetch_user(player_id)
            if player['role']:
                await user.send(f"The game started and you are the... {player['role']['name']} {player['role']['emoji']}")

class ModPanelView(View):
    # sent via dm
    def __init__(self, game_id, data={}, manual_killing=True):
        self.selected_players = {}
        self.selected_players_for_kill = []
        self.night_action_selects = {}
        self.game_id = game_id
        self.data = data
        self.manual_killing = manual_killing
        
        super().__init__()
        if manual_killing:
            total_players = GAMES[self.game_id]['players']
            if len(total_players) != 0:
                options = [
                    SelectOption(label=f"{total_players[role_key]['username']}", value=role_key)
                    for role_key in total_players
                ]
                self.ballot_select = Select(placeholder="Select players for the ballot", min_values=1, max_values=len(options), options=options) # 
                self.ballot_select.callback = self.ballot_select_callback
                self.add_item(self.ballot_select)
                
                self.kill_select = Select(placeholder="Select players to kill", min_values=1, max_values=len(options), options=options) # 
                self.kill_select.callback = self.kill_select_callback
                self.add_item(self.kill_select)
                
                #self.revive_select = Select(placeholder="Select players to revive", min_values=1, max_values=len(options), options=options) # 
                #self.revive_select.callback = self.kill_select_callback
                #self.add_item(self.revive_select)
            
    
    async def ballot_select_callback(self, interaction: discord.Interaction):
        self.selected_players = {}
        for value in self.ballot_select.values:
            player = GAMES[self.game_id]['players'][int(value)]
            self.selected_players[int(value)] = player
        
        await interaction.response.edit_message(view=self)
            
        await interaction.followup.send(
            f"Players in ballot updated", ephemeral=True
        )
    
    async def kill_select_callback(self, interaction: discord.Interaction):
        self.selected_players_for_kill = []
        for value in self.kill_select.values:
            player = GAMES[self.game_id]['players'][int(value)]
            self.selected_players_for_kill.append(
                player
            )
        logger.info(f'selected_players_for_kill {self.selected_players_for_kill}')
        
        await interaction.response.edit_message(view=self)
        
        await interaction.followup.send(
            f"Players set for kill updated", ephemeral=True
        )
        
    def set_child_disabled(self, label, disabled):
        for child in self.children:
            if type(child) is Button and child.label == label:
                child.disabled = disabled
    
    @discord.ui.button(label="Start Accusations", style=discord.ButtonStyle.primary, disabled=True)
    async def start_nominations(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.client.get_channel(GAMES[self.game_id]['channel_id'])
        
        if self.manual_killing:
            alive_players_ids = [p_id for p_id in self.selected_players]
            alive_players_options = [(p['username'], p_id) for p_id, p in self.selected_players.items()]
        else:
            total_players = GAMES[self.game_id]['players']
            alive_players_ids = [p_id for p_id in total_players if total_players[p_id]['is_alive']]
            alive_players_options = [(p['username'], p_id) for p_id, p in total_players.items() if p['is_alive']]
        
        # send votes to users
        await intialize_vote(
            interaction,
            channel,
            participant_ids=alive_players_ids,
            options=alive_players_options,
            notify_to=GAMES[self.game_id]['moderators'],
            on_close=self.on_nomintions_close,
        )
        
        # notify
        await channel.send(f"{GAMES[self.game_id]['role_id']} Accusations have started, a ballot was sent to you privately")
        await interaction.response.send_message("You started Accusations", ephemeral=True)
    
    async def on_nomintions_close(self, interaction, vote_counts):
        day_number = GAMES[self.game_id]['day_number']
        players_who_halve_votes = [player_id for player_id, player in GAMES[self.game_id]['players'].items() if player['role'].get('halves_votes_for_self')]
        for player_id in players_who_halve_votes:
            if player_id in vote_counts:
                vote_counts[player_id] = round(vote_counts[player_id] / 2)
                
        # {(434904918709633025, 'Jai'): 1}
        GAMES[self.game_id]['day_nominations'][day_number] = top_two_poll_results(vote_counts)
        
        # enable next buttons
        self.set_child_disabled('Start Accusations', disabled=True)
        self.set_child_disabled('Start Execution', disabled=False)
        
        await edit_moderators_pannel(game_id=self.game_id, interaction=interaction, view=self)
    
    @discord.ui.button(label="Start Execution", style=discord.ButtonStyle.primary, disabled=True)
    async def start_executions(self, interaction: discord.Interaction, button: discord.ui.Button):
        day_number = GAMES[self.game_id]['day_number']
        total_players = GAMES[self.game_id]['players']
        
        if self.manual_killing:
            options = [(p['username'], p_id) for p_id, p in self.selected_players.items()]
            options_ids = [p_id for p_id in self.selected_players]
        else:
            options = GAMES[self.game_id]['day_nominations'][day_number]
            options_ids = [x[1] for x in options]
            options = list(options.keys())
        
        # alive, outside of ballot or seducer
        elegible_players_ids = [
            p_id
            for p_id, p in total_players.items()
            if p['is_alive'] and (p.get('can_vote_on_ballot') or p_id not in options_ids)
        ]
        channel = interaction.client.get_channel(GAMES[self.game_id]['channel_id'])
        await intialize_vote(
            interaction,
            channel,
            participant_ids=elegible_players_ids,
            options=options,
            notify_to=GAMES[self.game_id]['moderators'],
            on_close=self.on_executions_close,
        )
        await channel.send(f"{GAMES[self.game_id]['role_id']} Executions have started, a ballot was sent to you privately")        
        
        # enable next buttons
        self.disabled = True
        self.set_child_disabled("Start Night", disabled=False)
        await interaction.response.edit_message(view=self)
        
        await interaction.followup.send("You started executions", ephemeral=True)
        
    
    async def on_executions_close(self, interaction, vote_counts):
        day_number = GAMES[self.game_id]['day_number']
        players_who_halve_votes = [player_id for player_id, player in GAMES[self.game_id]['players'].items() if player['role'].get('halves_votes_for_self')]
        for player_id in players_who_halve_votes:
            if player_id in vote_counts:
                vote_counts[player_id] = round(vote_counts[player_id] / 2)
        
        channel = interaction.client.get_channel(GAMES[self.game_id]['channel_id'])
        
        # enable next buttons
        self.set_child_disabled('Start Execution', disabled=True)
        self.set_child_disabled('Start Night', disabled=False)
        
        await edit_moderators_pannel(game_id=self.game_id, interaction=interaction, view=self)
    
    @discord.ui.button(label="Start Night", style=discord.ButtonStyle.primary)
    async def start_night(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.client.get_channel(GAMES[self.game_id]['channel_id'])
        await channel.send(f"{GAMES[self.game_id]['role_id']} Night {GAMES[self.game_id]['day_number']} is upon us :new_moon_with_face:\ncameras off, microphones off")
        await self.message_night_actions(interaction)
        
        # disable night, enable day
        button.disabled = True
        self.set_child_disabled('Start Day', disabled=False)
        self.set_child_disabled('Start Vote', disabled=True)
        await interaction.response.edit_message(view=self)
        
        # daytime executions
        if self.manual_killing:
            deaths = self.kill_selection()
            await self.notify_deaths(deaths=deaths, channel=channel, is_night=False)
        
        await interaction.followup.send("You started Night phase", ephemeral=True)
        
    async def message_night_actions(self, interaction, night_deaths_actions=False):
        day_number = GAMES[self.game_id]['day_number']
        total_players = GAMES[self.game_id]['players']
        alive_players = {p_id:total_players[p_id] for p_id in total_players if total_players[p_id]['is_alive']}
        self.night_action_selects = {}
        
        for player_id in alive_players:
            player_data = GAMES[self.game_id]['players'][player_id]
            role = player_data['role']
            night_action = role.get('night_action')
            night_action_on = role.get('night_action_on')
            night_action_from_day = role.get('night_action_from_day', 0)
            
            if day_number < night_action_from_day:
                continue
            
            if not night_action:
                continue
            
            is_select = True
            selections = []
            if is_select:
                if night_deaths_actions:
                    if night_action_on == 'night deaths':
                        selections = {p_id:total_players[p_id] for p_id in total_players if total_players[p_id]['death_at_day'] != day_number}
                        continue
                else:
                    if night_action_on == 'last deaths':
                        selections = {p_id:total_players[p_id] for p_id in total_players if total_players[p_id]['death_at_day'] != day_number - 1}
                    elif night_action_on == 'alive':
                        selections = alive_players
                    elif night_action_on == 'others alive':
                        selections = {p_id:total_players[p_id] for p_id in total_players if p_id != player_id}
            if len(selections) == 0:
                continue
            
            # message
            options = [
                SelectOption(label=selections[role_key]['username'], value=role_key)
                for role_key in selections
            ]
            night_action_select = Select(placeholder=f"Select player to {night_action}", min_values=1, max_values=1, options=options) #
            
            night_action_select.callback = self.role_night_action_select_callback
            self.night_action_selects[int(player_id)] = night_action_select
            
            view = View()
            view.add_item(night_action_select)
            
            user = await interaction.client.fetch_user(player_id)
            await user.send(f"action for night {day_number} {role['emoji']}", view=view)
    
    async def role_night_action_select_callback(self, interaction: discord.Interaction):
        player_data = GAMES[self.game_id]['players'][interaction.user.id]
        role = player_data['role']
        night_action_select = self.night_action_selects[int(interaction.user.id)]
        day_number = GAMES[self.game_id]['day_number']
        night_order = role['night_order']
        
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
        logger.info(f"night_actions AAAAAAAAAAAA {night_order}")
        GAMES[self.game_id]['night_actions'][day_number][night_order] = {
            'role': role,
            'selections': selections
        }
        
        await notify_moderators(
            self.game_id,
            interaction,
            f"**{interaction.user.display_name}** {role['name']} {role['emoji']} selected **{verbose_selections}** to get *{role['night_action']}* tonight"
        )
        
        # notify player
        night_action_select.disabled = True
        await interaction.response.edit_message(view=night_action_select.view)
        
        await interaction.followup.send(
            f"Selection submitted", ephemeral=True
        )
        
        await self.message_night_actions(interaction, night_deaths_actions=True)
        
    @discord.ui.button(label="Start Day", style=discord.ButtonStyle.primary, disabled=True)
    async def start_day(self, interaction: discord.Interaction, button: discord.ui.Button):
        GAMES[self.game_id]['day_number'] += 1
        channel = interaction.client.get_channel(GAMES[self.game_id]['channel_id'])
        await channel.send(f"{GAMES[self.game_id]['role_id']} The sun rises in our lovely town :sun_with_face:, Day {GAMES[self.game_id]['day_number']}")
        
        # disable day, enable night
        button.disabled=True
        self.set_child_disabled('Start Accusations', disabled=False)
        await interaction.response.edit_message(view=self)
        
        logger.info(f"night_calculations")
        await self.night_calculations(interaction, channel)
        await interaction.followup.send("You started Day phase", ephemeral=True)
    
    def kill_selection(self):
        day_number = GAMES[self.game_id]['day_number']
        deaths = []
        logger.info(f'selected_players_for_kill {self.selected_players_for_kill}')
        for death_player in self.selected_players_for_kill:
            GAMES[self.game_id]['players'][death_player['id']]['is_alive'] = False
            GAMES[self.game_id]['players'][death_player['id']]['death_at_day'] = day_number
            deaths.append(death_player['username'])
        self.selected_players_for_kill = []
        return deaths
    
    async def notify_deaths(self, deaths, channel, is_night):
        if deaths:
            await channel.send(f"{' and '.join(deaths)} {'were' if len(deaths) > 1 else 'was'} {'killed during the night' if is_night else 'burnt today'}")
        else:
            await channel.send(f"no one was {'killed during the night' if is_night else 'burnt today'}")
                
    async def night_calculations(self, interaction, channel):
        logger.info(f"night_calculations 2")
        day_number = GAMES[self.game_id]['day_number'] - 1
        total_players = GAMES[self.game_id]['players']
        if not (day_number in GAMES[self.game_id]['night_actions']):
            return
        night_actions = GAMES[self.game_id]['night_actions'][day_number]
        
        # intial actions
        is_cv_alive = False
        is_cv_check_corrupt = False
        death_attempts = []
        protection = []
        
        logger.info(f"total player action {total_players}")
        for p_id, player in total_players.items():
            logger.info(f"player action {p_id}")
            if not player['is_alive']:
                continue
            role = player['role']
            if role.get('night_action') in ['kill']:
                night_action = night_actions.get(role['night_order'])
                if night_action:
                    death_attempts = night_action['selections']
            if role.get('night_action') in ['protect from shadow attacks']:
                night_action = night_actions.get(role['night_order'])
                if night_action:
                    protection = protection.append(night_action['selections'])
            if role['name'] in ['Clairvoyant']:
                is_cv_alive = True
                night_action = night_actions.get(role['night_order'])
                for selection in night_action['selections']:
                    is_cv_check_corrupt = selection['role'].get('corrupted', False)
                
                logger.info(f"CV check {is_cv_check_corrupt}")
                user = await interaction.client.fetch_user(p_id)
                await user.send(f"**{selection['username']}** is {'corrupt :skull:' if is_cv_check_corrupt else 'non corrupt 👍'}")
        # deaths
        if self.manual_killing:
            deaths = self.kill_selection()
        else:
            deaths = []
            for death_player in death_attempts:
                death_confirmed = True
                for protected_player in protection:
                    if death_player['id'] == protected_player['id']:
                        death_confirmed = False
                if death_player.get('night_action') == 'self protect from shadow attacks':
                    death_confirmed = False
                if not death_confirmed:
                    continue
                GAMES[self.game_id]['players'][death_player['id']]['is_alive'] = False
                GAMES[self.game_id]['players'][death_player['id']]['death_at_day'] = day_number
                deaths.append(death_player['username'])
        
        await self.notify_deaths(deaths=deaths, channel=channel, is_night=True)
            
        # news
        for p_id in total_players:
            if not total_players[p_id]['is_alive']:
                continue
            if is_cv_alive:
                if not is_cv_check_corrupt and total_players[p_id]['role']['name'] in ['Bard']:
                    await channel.send("A non corrupt person was found yesterday")
                if is_cv_check_corrupt and total_players[p_id]['role']['name'] in ['Innkeeper']:
                    await channel.send("A corrupt person was found yesterday")
    