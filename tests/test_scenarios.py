import pytest
from diplomacy import Game
from scenarios import (
    SCENARIO_REGISTRY,
    wwi_two_player,
    five_player_scenario,
    six_player_scenario,
    standard_game_template, # Added for completeness, though not explicitly registered by name
)

def test_scenario_registry_populated():
    """Tests that the SCENARIO_REGISTRY is populated correctly."""
    assert SCENARIO_REGISTRY, "SCENARIO_REGISTRY should not be empty."
    
    expected_scenarios = {
        "wwi_two_player": wwi_two_player,
        "five_player_scenario": five_player_scenario,
        "six_player_scenario": six_player_scenario,
    }
    
    for name, func in expected_scenarios.items():
        assert name in SCENARIO_REGISTRY, f"Scenario '{name}' not found in registry."
        assert SCENARIO_REGISTRY[name] == func, f"Registry entry for '{name}' does not point to the correct function."

    # Also check that standard_game_template is not in the registry by a specific name unless intended
    # This test assumes standard_game_template is a helper, not a directly registered scenario by that name.
    # If it were registered, it would be in expected_scenarios.
    assert standard_game_template not in SCENARIO_REGISTRY.values(), \
        "'standard_game_template' function itself should not be a value in the registry unless it's registered by a key."


def test_registered_scenarios_return_game_objects():
    """Tests that all registered scenario factories return diplomacy.Game objects."""
    assert SCENARIO_REGISTRY, "SCENARIO_REGISTRY is empty, cannot test factories."
    
    for name, factory_func in SCENARIO_REGISTRY.items():
        game_instance: Game
        if name == "wwi_two_player":
            # wwi_two_player requires specific arguments
            game_instance = factory_func(entente_player="ENTENTE_POWERS", central_player="CENTRAL_POWERS")
        elif name in ["five_player_scenario", "six_player_scenario"]:
            # These scenarios currently take no arguments
            game_instance = factory_func()
        else:
            # Fallback for any other registered scenarios, assuming they take no args
            # This might need adjustment if more complex scenarios are added
            try:
                game_instance = factory_func()
            except TypeError as e:
                pytest.fail(f"Scenario '{name}' factory function could not be called without arguments. "
                            f"Test needs adjustment for this scenario's required parameters. Error: {e}")
        
        assert isinstance(game_instance, Game), \
            f"Scenario factory '{name}' did not return a diplomacy.Game object. Returned: {type(game_instance)}"

# Example of how a scenario that is not registered might be tested (if it existed standalone)
# def test_unregistered_scenario_returns_game():
#     game = standard_game_template() # Assuming this is a valid factory, though not registered by this name
#     assert isinstance(game, Game)

# Test that wwi_two_player sets the start year correctly (as an example of specific scenario logic)
def test_wwi_two_player_specifics():
    """Tests specific properties of the wwi_two_player scenario."""
    game = wwi_two_player(entente_player="P1", central_player="P2")
    assert game.year == 1914, "wwi_two_player scenario should start in 1914."
    # Game variant is standard by default in Game constructor, can be asserted if variant was passed.
    # assert game.variant_name.lower() == "standard" # diplomacy.Game().variant_name
    assert "standard" in game.variant.name.lower(), "wwi_two_player should use a standard variant base."

def test_five_player_scenario_metadata():
    """Tests metadata set by five_player_scenario."""
    game = five_player_scenario()
    assert game.metadata.get("description") == "Standard game, intended for 5 active players. Neutral powers (2) to be configured by agent assignments."

def test_six_player_scenario_metadata():
    """Tests metadata set by six_player_scenario."""
    game = six_player_scenario()
    assert game.metadata.get("description") == "Standard game, intended for 6 active players. Neutral power (1) to be configured by agent assignments."
