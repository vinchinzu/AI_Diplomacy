from diplomacy import Game
from typing import Callable


SCENARIO_REGISTRY: dict[str, Callable[..., Game]] = {}


def register_scenario(name: str):
    def decorator(func: Callable[..., Game]):
        SCENARIO_REGISTRY[name] = func
        return func

    return decorator


@register_scenario("wwi_two_player")
def wwi_two_player(
    entente_player: str, central_player: str, italy_controller: str | None = None
):
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


def standard_game_template():  # Helper if common logic arises
    """Returns a standard game instance."""
    return Game()  # Variant "standard" is default


@register_scenario("five_player_scenario")
def five_player_scenario():
    """
    Game setup for 5 active players.

    This function primarily serves as a named factory for a standard game.
    The actual designation of neutral powers (typically 2 for a 5-player game)
    is handled by agent type assignments (e.g., 'neutral' or 'null_agent')
    based on presets or command-line arguments processed by the AgentManager
    or game setup coordinator.
    Returns a standard game instance.
    """
    game = standard_game_template()
    game.set_metadata(
        "description",
        "Standard game, intended for 5 active players. Neutral powers (2) to be configured by agent assignments.",
    )
    return game


@register_scenario("six_player_scenario")
def six_player_scenario():
    """
    Game setup for 6 active players.

    Similar to five_player_scenario, this function acts as a named factory.
    The actual designation of the neutral power (typically 1 for a 6-player game)
    is handled externally by agent type assignments.
    Returns a standard game instance.
    """
    game = standard_game_template()
    game.set_metadata(
        "description",
        "Standard game, intended for 6 active players. Neutral power (1) to be configured by agent assignments.",
    )
    return game
