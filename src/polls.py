import discord
from discord.ui import Button, View, Select
import uuid
from collections import Counter
import logging

logger = logging.getLogger('bot')


POLLS = {}
class VoteButton(Button):
    def __init__(self, label, value, poll, on_user_vote):
        self.value = value
        self.poll = poll
        self.on_user_vote = on_user_vote
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        try:
            already_voted = user.id in POLLS[self.poll]['votes']
            # Sending a DM to the user
            POLLS[self.poll]['votes'][user.id] = (self.label, self.value)
            await interaction.response.send_message("You voted", ephemeral=True)
            await self.on_user_vote(user, self.label, already_voted=already_voted)
        except discord.Forbidden:
            # Handling if the bot can't send DMs to the user
            await interaction.response.send_message(
                "I couldn't send you a DM. Please check your privacy settings.", ephemeral=True
            )

async def send_private_vote(interaction, participant_id, poll_id, options, on_user_vote):
    user = await interaction.client.fetch_user(participant_id)
    # Sending a DM to the user
    embed = discord.Embed(
        title="Votes for the werewolf game",
        description="Choose one"
    )
    view = View()
    for option in options:
        view.add_item(VoteButton(option[0], option[1], poll_id, on_user_vote=on_user_vote))
    await user.send(view=view, embed=embed)
            
class BallotButton(Button):
    def __init__(self, poll_id, options, on_user_vote):
        self.poll_id = poll_id
        self.options = options
        self.on_user_vote = on_user_vote
        super().__init__(label="Get Ballot", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        try:
            # Sending a DM to the user
            embed = discord.Embed(
                title="Vote for the wherewolf game",
                description="Choose one"
            )
            view = View()
            for option in self.options:
                view.add_item(VoteButton(option[0], option[1], self.poll_id, on_user_vote= self.on_user_vote))
            await user.send(view=view, embed=embed)
            await interaction.response.send_message(
                "I have sent you a DM! Please check your messages.", ephemeral=True
            )
        except discord.Forbidden:
            # Handling if the bot can't send DMs to the user
            await interaction.response.send_message(
                "I couldn't send you a DM. Please check your privacy settings.", ephemeral=True
            )

class PollResultsButton(Button):
    def __init__(self, poll_id, on_close):
        self.poll_id = poll_id
        self.on_close = on_close
        super().__init__(label="Get Results", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        # Count the votes from the poll
        vote_counts = Counter(list(POLLS[self.poll_id]['votes'].values()))

        # Format the results into a human-readable string
        results = "\n".join(f"{option[0]}: {count} vote(s)" for option, count in vote_counts.items())

        # Create the embed with the results
        embed = discord.Embed(
            title="Poll Results",
            description=results,
            color=discord.Color.blue()
        )

        # Send the embed as a response
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True  # Only visible to the user who interacted
        )
        
        await self.on_close(interaction, vote_counts)
        

async def intialize_vote(
        interaction,
        channel,
        options = [('player 1', 'user_id 1'),('player 2', '2'),('player 3', '3')],
        participant_ids = [],
        notify_to = None,
        on_close=None,
        
    ):
    poll_id = str(uuid.uuid1())
    def poll_db_creation(poll_id, options=[]):
        POLLS[poll_id] = {
            'options': options,
            'votes': {}
        }
    poll_db_creation(poll_id, options)

    # Create the button and view
    async def on_user_vote(user, vote, already_voted=False):
        total_votes = len(POLLS[poll_id]['votes'])
        total_participants = len(participant_ids)
        
        if not total_participants:
            total_participants = '-'
        
        for moderator_id in notify_to:
            moderator = await interaction.client.fetch_user(moderator_id)
            if not already_voted:
                await moderator.send(f"user **{user.display_name}** voted for **{vote}** {total_votes}/{total_participants}")
                logger.info(f"user **{user.display_name}** voted for **{vote}** {total_votes}/{total_participants}")
            else:
                await moderator.send(f"user **{user.display_name}** changed their vote, new vote for **{vote}** {total_votes}/{total_participants}")
                logger.info(f"user **{user.display_name}** changed their vote, new vote for **{vote}** {total_votes}/{total_participants}")
    
    # Send the message with the button
    if participant_ids:
        for participant_id in participant_ids:
            await send_private_vote(interaction, participant_id, poll_id, options, on_user_vote)
    else:
        embed = discord.Embed(
            title="Request ballot",
            description="Click the button below to receive The Ballot."
        )
        view = View()
        view.add_item(BallotButton(poll_id, options=options, on_user_vote=on_user_vote))
        await channel.send(embed=embed, view=view)
    
    # notify
    for moderator_id in notify_to:
        user = await interaction.client.fetch_user(moderator_id)
        result_mod_view = View()
        result_mod_view.add_item(PollResultsButton(poll_id, on_close=on_close))
        await user.send("Close poll", view=result_mod_view)


def top_two_poll_results(poll_results):
    # Step 1: Sort results by votes in descending order
    sorted_results = sorted(poll_results.items(), key=lambda x: x[1], reverse=True)
    
    if not sorted_results:
        return {}
    
    # Step 2: Determine the highest and second-highest vote counts
    top_votes = sorted_results[0][1]
    second_votes = None
    
    result = {}
    
    for user, votes in sorted_results:
        if votes == 0:
            continue
        if votes == top_votes:
            result[user] = votes
        elif second_votes is None or votes == second_votes:
            second_votes = votes
            result[user] = votes
        else:
            break
    
    return result


from discord.ui import UserSelect

class SetupBallotView(View):
    # sent via dm
    def __init__(self, owner_id):
        self.owner_id = owner_id
        self.selected_participants = []
        self.selected_ballot_options = []
        
        super().__init__()
        self.participants_select = UserSelect(placeholder="Select participants", max_values=20) # 
        self.participants_select.callback = self.participants_select_callback
        self.add_item(self.participants_select)
        
        self.ballot_select = UserSelect(placeholder="Select ballot", max_values=20) # 
        self.ballot_select.callback = self.ballot_select_callback
        self.add_item(self.ballot_select)
    
    async def participants_select_callback(self, interaction: discord.Interaction):
        self.selected_participants = self.participants_select.values
        
        await interaction.response.send_message(
            f"Players in participation list updated", ephemeral=True
        )
    
    async def ballot_select_callback(self, interaction: discord.Interaction):
        self.selected_ballot_options = self.ballot_select.values
        
        await interaction.response.send_message(
            f"Players in ballot list updated", ephemeral=True
        )
    
    async def on_close(self, interaction, vote_counts):
        # {(434904918709633025, 'Jai'): 1}
        results = top_two_poll_results(vote_counts)
        
        user = await interaction.client.fetch_user(self.owner_id)
        await user.send("Voting was closed")
    
    @discord.ui.button(label="set ballot same as participants", style=discord.ButtonStyle.success)
    async def ballot_same_as_participants(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        self.selected_ballot_options = self.selected_participants
        
        await interaction.response.send_message(
            f"Players in ballot list updated", ephemeral=True
        )
        
    @discord.ui.button(label="start", style=discord.ButtonStyle.success)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info("Vote started")
        user = interaction.user
        
        await intialize_vote(
            interaction=interaction,
            channel=interaction.channel,
            options=[(user.display_name, user.id) for user in self.selected_ballot_options],
            participant_ids=[user.id for user in self.selected_participants],
            notify_to=[user.id],
            on_close=self.on_close
        )
        
        # button.is_disabled = True
        # await interaction.response.edit_message(view=self)
        
        await interaction.response.send_message(
            f"Vote started, you will recieve the results via dm", ephemeral=True
        )
