from diplomacy import Game as DipGame
from .board import BoardState
from .phase import PhaseState, PhaseKey

def game_to_phase(game: DipGame) -> PhaseState:
    """Converts a diplomacy.Game object to a PhaseState."""
    key = PhaseKey(
        state=game.state,
        scs=game.scs,
        year=game.year,
        season=game.season,
        name=game.phase,
    )
    
    board = BoardState(
        units=game.units,
        supply_centers=game.get_supply_centers(),
    )
    history = [] # This will be implemented later
    return PhaseState(key=key, board=board, history=history)
