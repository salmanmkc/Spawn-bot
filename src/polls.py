import discord
from discord.ui import Button, View, Select
import uuid


POLLS = {}
class VoteButton(Button):
    def __init__(self, label, value, poll):
        self.value = value
        self.poll = poll
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        try:
            # Sending a DM to the user
            POLLS[self.poll]['votes'][user.id] = self.value
            await interaction.response.send_message("You voted", ephemeral=True)
        except discord.Forbidden:
            # Handling if the bot can't send DMs to the user
            await interaction.response.send_message(
                "I couldn't send you a DM. Please check your privacy settings.", ephemeral=True
            )

class BallotButton(Button):
    def __init__(self, poll_id, options=[]):
        self.poll_id = poll_id
        self.options = options
        super().__init__(label="Get Ballot", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        try:
            # Sending a DM to the user
            embed = discord.Embed(
                title="Vote for the wherewolf game",
                description="Who we killing."
            )
            view = View()
            for option in self.options:
                view.add_item(VoteButton(option[0], option[1], self.poll_id))
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
        # Sending a DM to the user
        from collections import Counter
        vote_counts = Counter(POLLS[self.poll_id]['votes'].values())
        embed = discord.Embed(
            title="results",
            description=str(vote_counts)
        )
        await interaction.response.send_message(
            embed=embed, ephemeral=True
        )

async def intialize_vote(
        interaction,
        data={},
    ):
    poll_id = str(uuid.uuid1())
    options = [('player 1', '1'),('player 2', '2'),('player 3', '3')]
    participants = [('player 1', '1'),('player 2', '2'),('player 3', '3')]
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
    view = View()
    view.add_item(BallotButton(poll_id, options=options))
    view.add_item(PollResultsButton(poll_id))

    # Send the message with the button
    await interaction.response.send_message(embed=embed, view=view)
