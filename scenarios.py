from diplomacy import Game
from typing import Callable


SCENARIO_REGISTRY: dict[str, Callable[..., Game]] = {}


def register_scenario(name: str):
    def decorator(func: Callable[..., Game]):
        SCENARIO_REGISTRY[name] = func
        return func

    return decorator


@register_scenario("wwi_two_player")
def wwi_two_player(entente_player: str, central_player: str, italy_controller: str | None = None):
    """
    Returns a Game object in the 1914 two-player variant.

    Player Assignments:
      - entente_player controls England, France, Russia
      - central_player controls Austria, Germany, Turkey
      - Italy is neutral until Spring 1915 (actual neutrality mechanism,
        like a coin flip for controller, is handled outside this scenario setup).

    Notes on Implementation:
    - This function primarily sets up the base Game object for the variant,
      starting in 1914.
    - The actual assignment of control to specific player entities (e.g.,
      `entente_player`, `central_player`) and the creation of agents
      (including one for a neutral or assigned Italy) are typically managed
      by an AgentManager or similar game setup coordinator.
    - Player identifiers (e.g., "ENTENTE_BLOC", "CENTRAL_BLOC", or the
      provided entente_player/central_player strings) are used by the
      AgentManager and become keys in agent configurations.
    - Specialized agents, like a BlocLLMAgent, if used, are internally aware
      of the standard powers they control based on their configuration.
    - The `game.powers.keys()` will still list the standard seven great powers
      (ENGLAND, FRANCE, RUSSIA, AUSTRIA, GERMANY, TURKEY, ITALY).
    - If `game.set_owner()` were to be used directly (it is not, in this current
      setup, to allow flexibility for the AgentManager), `game.get_owner(power_name)`
      would then return the assigned bloc controller name for those powers.
    - Metadata, such as a custom game description or victory conditions (e.g.,
      `game.set_metadata("description", "WWI Two-Player Scenario...")`),
      can be set on the game object here or by the coordinating setup logic.
    """
    game = Game(variant="standard", start_year=1914)  # Standard game has all 7 powers
    return game
