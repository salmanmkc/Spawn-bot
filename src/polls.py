import discord
from discord.ui import Button, View, Select
import uuid
from collections import Counter


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
            POLLS[self.poll]['votes'][user.id] = (self.value, self.label)
            await interaction.response.send_message("You voted", ephemeral=True)
            await self.on_user_vote(user, self.label, already_voted=already_voted)
        except discord.Forbidden:
            # Handling if the bot can't send DMs to the user
            await interaction.response.send_message(
                "I couldn't send you a DM. Please check your privacy settings.", ephemeral=True
            )

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
    def __init__(self, poll_id):
        self.poll_id = poll_id
        super().__init__(label="Get Results", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user

        # Count the votes from the poll
        vote_counts = Counter([POLLS[self.poll_id]['votes'].values()])

        # Format the results into a human-readable string
        results = "\n".join(f"{option}: {count} votes" for option, count in vote_counts.items())

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

async def intialize_vote(
        interaction,
        channel,
        options = [('player 1', 'user_id 1'),('player 2', '2'),('player 3', '3')],
        participants = ['user_id'],
        notify_to = None,
        
    ):
    poll_id = str(uuid.uuid1())
    def poll_db_creation(poll_id, options=[]):
        POLLS[poll_id] = {
            'options': options,
            'votes': {}
        }
    poll_db_creation(poll_id, options)
    embed = discord.Embed(
        title="Request ballot",
        description="Click the button below to receive The Ballot."
    )

    # Create the button and view
    async def on_user_vote(user, vote, already_voted=False):
        for moderator_id in notify_to:
            user = await interaction.client.fetch_user(moderator_id)
            if not already_voted:
                await user.send(f"user {user.display_name} voted for {vote}")
            else:
                await user.send(f"user {user.display_name} changed their vote, new vote for {vote}")
            
    view = View()
    view.add_item(BallotButton(poll_id, options=options, on_user_vote=on_user_vote))
    
    # notify
    for moderator_id in notify_to:
        user = await interaction.client.fetch_user(moderator_id)
        result_mod_view = View()
        result_mod_view.add_item(PollResultsButton(poll_id))
        await user.send(view=result_mod_view)

    # Send the message with the button
    await channel.send(embed=embed, view=view)
