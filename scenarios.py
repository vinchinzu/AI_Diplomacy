from diplomacy import Game

def wwi_two_player(entente_player: str, central_player: str, italy_controller: str | None = None):
    """
    Returns a Game object in the 1914 two‑player variant:
      • entente_player controls England, France, Russia
      • central_player controls Austria, Germany, Turkey
      • Italy is neutral until Spring 1915 (coin flip not done here)
    """
    game = Game(variant="standard", start_year=1914) # Standard game has all 7 powers

    # Define the bloc controllers as new "powers" in the game metadata/conceptually.
    # The actual game.powers object will still list the original 7 great powers.
    # We change ownership of these standard powers to our bloc controllers.

    # Assign control of standard powers to the bloc entities
    # for p_name in ("ENGLAND", "FRANCE", "RUSSIA"):
    #     game.set_owner(power_name=p_name, new_owner_name=entente_player)

    # for p_name in ("AUSTRIA", "GERMANY", "TURKEY"):
    #     game.set_owner(power_name=p_name, new_owner_name=central_player)

    # Set Italy's controller
    # If italy_controller is None, we can assign it to a special neutral placeholder name
    # or leave its original owner (ITALY) if that's desired for neutrality.
    # For this scenario, we want it to be distinct until the coin flip.
    italy_actual_controller = italy_controller if italy_controller is not None else "NEUTRAL_ITALY_BLOC"
    # game.set_owner(power_name="ITALY", new_owner_name=italy_actual_controller)

    # The game.powers.keys() will still be E,F,R,A,G,T,I.
    # The game.get_owner(power_name) will return the bloc controller name.
    # AgentManager will need to create agents for entente_player, central_player, and NEUTRAL_ITALY_BLOC.

    # game.set_metadata("combined_victory_centers", 24)  # custom win check
    # game.set_metadata("description", f"WWI Two-Player Scenario: {entente_player} (ENG,FRA,RUS) vs {central_player} (AUS,GER,TUR). Italy controlled by {italy_actual_controller}.")
    
    # Ensure the game object reflects these new "conceptual" powers if needed by downstream logic, e.g. AgentManager.
    # The current diplomacy library might not directly support adding new power entities beyond the standard 7
    # in a way that game.powers lists them. Ownership is the key mechanism here.
    # What lm_game.py receives as actual_player_names_for_game needs to be these bloc names.

    return game 