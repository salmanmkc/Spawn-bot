from collections import deque, defaultdict

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

# Votes
votes = defaultdict(int)  # Track votes for each player
vote_channels = {}  # Store private channels for each player to vote