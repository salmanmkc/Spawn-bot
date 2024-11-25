import json
import logging
logger = logging.getLogger(__name__)

# Load role data from JSON file
def load_roles(game):
    try:
        with open(f'src/roles_data/{game}.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"src/roles_data/{game}.json not found. Creating empty roles dictionary.")
        return {}

def ww_roles_to_verbose(roles):
    verbose_lines = ''
    for role in roles:
        verbose_lines.append(
            f'{role["name"]} {role["emoji"]} ({role["faction"]}) {"🖤" if role.get("corrupted") else ""} {"✨" if role.get("mystic") else ""}'
        )
    return '\n'.join(verbose_lines)