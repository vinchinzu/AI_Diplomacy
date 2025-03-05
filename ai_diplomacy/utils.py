from dotenv import load_dotenv
import logging
import random

logger = logging.getLogger("utils")
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)

load_dotenv()


def assign_models_to_powers():
    """
    Example usage: define which model each power uses.
    Return a dict: { power_name: model_id, ... }
    POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']
    """

    return {
        "FRANCE": "o3-mini",
        "GERMANY": "claude-3-5-sonnet-latest",
        "ENGLAND": "gemini-2.0-flash",
        "RUSSIA": "claude-3.7-sonnet-latest",
        "ITALY": "gpt-4o",
        "AUSTRIA": "gpt-4o-mini",
        "TURKEY": "claude-3-5-haiku-20241022",
    }


def gather_possible_orders(game, power_name):
    """
    Returns a dictionary mapping each orderable location to the list of valid orders.
    """
    orderable_locs = game.get_orderable_locations(power_name)
    all_possible = game.get_all_possible_orders()

    result = {}
    for loc in orderable_locs:
        result[loc] = all_possible.get(loc, [])
    
    order_count = sum(len(orders) for orders in result.values())
    logger.debug(f"ORDERS | {power_name} | Found {len(result)} orderable locations with {order_count} total possible orders")
    return result


def get_valid_orders(
    game,
    client,
    board_state,
    power_name,
    possible_orders,
    game_history,
    phase_summaries,
    model_error_stats,
):
    """
    Tries up to 'max_retries' to generate and validate orders.
    If invalid, we append the error feedback to the conversation
    context for the next retry. If still invalid, return fallback.
    """
    # Track invalid orders for feedback
    invalid_info = []

    # Ask the LLM for orders
    logger.debug(f"ORDERS | {power_name} | Requesting orders from {client.model_name}")
    orders = client.get_orders(
        game=game,
        board_state=board_state,
        power_name=power_name,
        possible_orders=possible_orders,
        conversation_text=game_history,
        phase_summaries=phase_summaries,
        model_error_stats=model_error_stats,
    )

    # Validate each order
    for move in orders:
        # Example move: "A PAR H" -> unit="A PAR", order_part="H"
        tokens = move.split(" ", 2)
        if len(tokens) < 3:
            invalid_info.append(
                f"Order '{move}' is malformed; expected 'A PAR H' style."
            )
            continue
        unit = " ".join(tokens[:2])  # e.g. "A PAR"
        order_part = tokens[2]  # e.g. "H" or "S A MAR"

        # Use the internal game validation method
        if order_part == "B":
            validity = 1  # hack because game._valid_order doesn't support 'B'
        else:
            validity = game._valid_order(
                game.powers[power_name], unit, order_part, report=1
            )

        if validity == 1:
            # All orders are fully valid
            logger.debug(f"ORDERS | {power_name} | Validated {len(orders)} orders successfully")
            return orders
        else:
            logger.warning(
                f"ORDERS | {power_name} | Failed validation: '{move}' is invalid"
            )
            model_error_stats[power_name]["order_decoding_errors"] += 1
            logger.debug(f"ORDERS | {power_name} | Using fallback orders")
            fallback = client.fallback_orders(possible_orders)
            return fallback


def expand_phase_info(game, board_state):
    """
    Convert a phase like 'S1901M' into a more descriptive string:
       'Spring 1901 Movement (early game): Units can move, support, or convoy...'
    This function also references the current year to classify early/mid/late game.
    """
    phase_abbrev = board_state["phase"]  # e.g. 'S1901M'
    # Basic mapping of abbreviations
    season_map = {
        'S': "Spring",
        'F': "Fall",
        'W': "Winter",
    }
    phase_type_map = {
        'M': "Movement",
        'R': "Retreat",
        'A': "Adjustment",  # builds/disbands
    }
    
    season_char = phase_abbrev[0]  # S / F / W
    year = int(phase_abbrev[1:5])  # 1901
    phase_char = phase_abbrev[-1]  # M / R / A
    
    season_str = season_map.get(season_char, "Unknown Season")
    phase_str = phase_type_map.get(phase_char, "Unknown Phase")
    
    # Approximate game stage
    if year <= 1902:
        stage = "early game"
    elif year <= 1906:
        stage = "mid game"
    else:
        stage = "late game"
    
    # Phase-specific action text
    if phase_char == 'M':
        actions = "Players issue move, support, or convoy orders."
    elif phase_char == 'R':
        actions = "Dislodged units must retreat or disband."
    elif phase_char == 'A':
        actions = "Powers may build new units if they have more centers than units, otherwise disband if fewer."
    else:
        actions = "Unknown phase actions."
    
    return f"{season_str} {year} {phase_str} ({stage}): {actions}"


def format_location_with_expansion(game, loc, include_adjacency=False):
    """
    Return a string like 'Paris (PAR) [LAND]',
    optionally including a list of adjacent locations if include_adjacency=True.
    """
    full_name = next((name for name, abbrev in game.map.loc_name.items() if abbrev == loc), loc)
    loc_type = game.map.loc_type.get(loc, "UNKNOWN")
    formatted = f"{full_name} ({loc}) [{loc_type}]"
    
    if include_adjacency:
        adjacent_locs = game.map.loc_abut.get(loc, [])
        if adjacent_locs:
            adjacent_info = []
            for adj_loc in adjacent_locs:
                adj_full_name = game.map.loc_name.get(adj_loc, adj_loc)
                adj_type = game.map.loc_type.get(adj_loc, "UNKNOWN")
                adjacent_info.append(f"{adj_full_name} ({adj_loc}) [{adj_type}]")
            formatted += f"\n  Adjacent to: {', '.join(adjacent_info)}"
    
    return formatted


def format_power_units_and_centers(game, power_name, board_state):
    """
    Show a summarized view of a given power's units and supply centers, 
    with expansions of location names, plus a quick 'strength' count.
    Also includes information about neutral centers.
    """
    # Add neutral centers info
    output = ""
    if power_name == "NEUTRAL":
        all_controlled = set()
        for centers in board_state["centers"].values():
            all_controlled.update(centers)
        neutral_centers = [sc for sc in game.map.scs if sc not in all_controlled]
        
        if neutral_centers:
            output = "  Neutral Supply Centers:\n"
            for c in neutral_centers:
                output += f"    {format_location_with_expansion(game, c)}\n"
    else:
        units_info = board_state["units"].get(power_name, [])
        centers_info = board_state["centers"].get(power_name, [])
        
        output = f"{power_name} FORCES:\n"
        
        if units_info:
            output += "  Units:\n"
            for unit in units_info:
                # Example unit: "A PAR"
                # First char is 'A' or 'F'; substring after space is the location
                parts = unit.split(" ", 1)
                if len(parts) == 2:
                    unit_type, loc = parts
                    output += f"    {unit_type} in {format_location_with_expansion(game, loc)}\n"
                else:
                    output += f"    {unit}\n"
        else:
            output += "  Units: None\n"
        
        if centers_info:
            output += "  Supply Centers:\n"
            for c in centers_info:
                output += f"    {format_location_with_expansion(game, c)}\n"
        else:
            output += "  Supply Centers: None\n"
        
        
        # Summaries
        output += f"  Current Strength: {len(centers_info)} centers, {len(units_info)} units\n\n"
    return output


def organize_history_by_relationship(conversation_text: str) -> str:
    """
    This simplified version takes the entire conversation text
    (e.g., from game_history.get_game_history(power_name)) and returns it.
    
    Previously, we assumed we had a structured list of messages, but in practice,
    game_history is just a string, so we skip relationship-based grouping.
    
    In the future, if 'GameHistory' becomes more structured, we can parse it here.
    """
    if not conversation_text.strip():
        return "(No game history yet)\n"
    
    # For now, we can simply return the conversation text
    # or do minimal formatting as we see fit.
    output = "COMMUNICATION HISTORY:\n\n"
    output += conversation_text.strip() + "\n"
    return output


def format_possible_orders(game, possible_orders):
    """
    Display orders with strategic context, maintaining the exact order syntax
    while adding meaningful descriptions about their tactical purpose.
    """
    # First pass - analyze game state for strategic context
    supply_centers = set(game.map.scs)
    power_centers = {}
    contested_regions = set()
    
    # Gather supply center ownership
    for power_name, centers in game.get_centers().items():
        for center in centers:
            power_centers[center] = power_name
    
    # Identify contested regions (simplified approach)
    # A more sophisticated implementation would analyze unit adjacencies
    
    # Classify orders by strategic purpose
    strategic_orders = {
        "OFFENSIVE": [],  # Orders that can capture centers or threaten enemy units
        "DEFENSIVE": [],  # Orders that protect your centers or units
        "TACTICAL": [],   # Orders that improve position without immediate captures
        "SUPPORT": []     # Support orders
    }
    
    # Process each order
    for loc, orders in possible_orders.items():
        for order in orders:
            order_parts = order.split()
            order_type = None
            
            # Determine order type
            if " H" in order:
                order_type = "DEFENSIVE"
            elif " S " in order:
                order_type = "SUPPORT"
            elif " - " in order:
                # Get destination
                dest = order_parts[-1].split(" VIA")[0] if " VIA" in order else order_parts[-1]
                
                # Check if destination is a supply center
                if dest[:3] in supply_centers:
                    # If center is neutral or enemy-owned, it's offensive
                    if dest[:3] not in power_centers or power_centers[dest[:3]] != game.role:
                        order_type = "OFFENSIVE"
                    else:
                        order_type = "DEFENSIVE"  # Moving to own supply center
                else:
                    order_type = "TACTICAL"  # Non-center destination
            elif " C " in order:
                order_type = "SUPPORT"  # Classify convoy as support
            
            # Generate strategic description
            description = generate_order_description(game, order, order_type, power_centers, supply_centers)
            
            # Add to appropriate category
            if order_type:
                strategic_orders[order_type].append((order, description))
    
    # Generate formatted output
    output = "POSSIBLE ORDERS:\n\n"
    
    # Add offensive moves first - these are highest priority
    if strategic_orders["OFFENSIVE"]:
        output += "Offensive Moves (capture territory):\n"
        for order, desc in strategic_orders["OFFENSIVE"]:
            output += f"  {order} {desc}\n"
        output += "\n"
    
    # Add defensive moves
    if strategic_orders["DEFENSIVE"]:
        output += "Defensive Moves (protect territory):\n"
        for order, desc in strategic_orders["DEFENSIVE"]:
            output += f"  {order} {desc}\n"
        output += "\n"
    
    # Add tactical positioning moves
    if strategic_orders["TACTICAL"]:
        output += "Tactical Moves (improve position):\n"
        for order, desc in strategic_orders["TACTICAL"]:
            output += f"  {order} {desc}\n"
        output += "\n"
    
    # Add support moves
    if strategic_orders["SUPPORT"]:
        output += "Support Options (strengthen attacks/defense):\n"
        for order, desc in strategic_orders["SUPPORT"]:
            output += f"  {order} {desc}\n"
    
    # Log order counts for debugging
    logger.debug(f"ORDERS | Strategic classification: " + 
                 f"Offensive: {len(strategic_orders['OFFENSIVE'])}, " +
                 f"Defensive: {len(strategic_orders['DEFENSIVE'])}, " +
                 f"Tactical: {len(strategic_orders['TACTICAL'])}, " +
                 f"Support: {len(strategic_orders['SUPPORT'])}")
    
    return output


def generate_order_description(game, order, order_type, power_centers, supply_centers):
    """
    Generate a strategic description for an order based on its type and context.
    """
    order_parts = order.split()
    
    # Hold orders
    if order_type == "DEFENSIVE" and " H" in order:
        unit_loc = order_parts[1]
        if unit_loc[:3] in supply_centers:
            if unit_loc[:3] in power_centers and power_centers[unit_loc[:3]] == game.role:
                return "(secure your supply center)"
            else:
                return "(maintain position at supply center)"
        return "(maintain strategic position)"
    
    # Move orders
    elif order_type in ["OFFENSIVE", "TACTICAL", "DEFENSIVE"] and " - " in order:
        unit_type = order_parts[0]  # A or F
        unit_loc = order_parts[1]
        dest = order_parts[3].split(" VIA")[0] if len(order_parts) > 3 and "VIA" in order_parts[-1] else order_parts[3]
        
        # Moving to a supply center
        if dest[:3] in supply_centers:
            if dest[:3] not in power_centers:
                return f"(capture neutral supply center)"
            else:
                target_power = power_centers[dest[:3]]
                return f"(attack {target_power}'s supply center)"
        
        # Moving to a non-supply center
        if unit_type == "A":
            # Army moves to tactical positions
            return f"(strategic positioning)"
        else:
            # Fleet moves often about sea control
            return f"(secure sea route)"
    
    # Support orders
    elif order_type == "SUPPORT" and " S " in order:
        # Find the unit being supported and its action
        supported_part = " ".join(order_parts[3:])
        
        if " - " in supported_part:
            # Supporting a move
            supported_unit = order_parts[3]
            supported_dest = order_parts[-1]
            
            if supported_dest[:3] in supply_centers:
                if supported_dest[:3] not in power_centers:
                    return f"(support capture of neutral center)"
                else:
                    target_power = power_centers[supported_dest[:3]]
                    return f"(strengthen attack on {target_power})"
            return "(strengthen attack)"
        else:
            # Supporting a hold
            return "(reinforce defense)"
    
    # Convoy orders
    elif " C " in order:
        return "(enable army transport by sea)"
    
    # Default
    return ""


def format_convoy_paths(game, convoy_paths_possible, power_name):
    """
    Format convoy paths by region and ownership, focusing on strategically relevant convoys.
    Input format: List of (start_loc, {required_fleets}, {possible_destinations})
    """
    # check if convoy_paths_possible is empty dictionary or list or none
    output = ""
    if not convoy_paths_possible:
        return "CONVOY POSSIBILITIES: None currently available.\n"

    # Get our units and all other powers' units
    our_units = set(game.get_units(power_name))
    our_unit_locs = {unit[2:5] for unit in our_units}
    
    # Get all powers' units and centers for context
    power_units = {}
    power_centers = {}
    for pwr in game.powers:
        power_units[pwr] = {unit[2:5] for unit in game.get_units(pwr)}
        power_centers[pwr] = set(game.get_centers(pwr))

    # Organize convoys by strategic relationship
    convoys = {
        "YOUR CONVOYS": [],           # Convoys using your armies
        "CONVOYS YOU CAN ENABLE": [], # Using your fleets to help others
        "ALLIED OPPORTUNITIES": [],    # Convoys that could help contain common enemies
        "THREATS TO WATCH": []        # Convoys that could threaten your positions
    }

    # Make sea regions more readable
    sea_regions = {
        'NTH': "North Sea",
        'MAO': "Mid-Atlantic",
        'TYS': "Tyrrhenian Sea",
        'BLA': "Black Sea",
        'SKA': "Skagerrak",
        'ION': "Ionian Sea",
        'EAS': "Eastern Mediterranean",
        'WES': "Western Mediterranean",
        'BAL': "Baltic Sea",
        'BOT': "Gulf of Bothnia",
        'ADR': "Adriatic Sea",
        'AEG': "Aegean Sea",
        'ENG': "English Channel"
    }

    for start, fleets, destinations in convoy_paths_possible:
        # Skip if no destinations or fleets
        if not destinations or not fleets:
            continue

        # Identify the power that owns the army at start (if any)
        army_owner = None
        for pwr, locs in power_units.items():
            if start in locs:
                army_owner = pwr
                break

        # Determine if we own any of the required fleets
        our_fleet_count = sum(1 for fleet_loc in fleets if fleet_loc in our_unit_locs)
        
        # Format the fleet path nicely
        fleet_path = " + ".join(sea_regions.get(f, f) for f in fleets)

        for dest in destinations:
            # Get destination owner if any
            dest_owner = None
            for pwr, centers in power_centers.items():
                if dest in centers:
                    dest_owner = pwr
                    break

            # Determine if destination is a supply center
            is_sc = dest in game.map.scs
            sc_note = " (SC)" if is_sc else ""
            
            # Create base convoy description
            convoy_desc = f"A {start} -> {dest}{sc_note} via {fleet_path}"
            
            # Add strategic context based on relationships
            if army_owner == power_name:
                category = "YOUR CONVOYS"
                if dest_owner:
                    note = f"attack {dest_owner}'s position"
                else:
                    note = "gain strategic position" if not is_sc else "capture neutral SC"
                convoys[category].append(f"{convoy_desc} ({note})")
                
            elif our_fleet_count > 0:
                category = "CONVOYS YOU CAN ENABLE"
                # Add diplomatic context
                if army_owner:
                    if dest_owner == power_name:
                        note = f"WARNING: {army_owner} could attack your SC"
                    else:
                        note = f"help {army_owner} attack {dest_owner or 'neutral'} position"
                else:
                    note = "potential diplomatic bargaining chip"
                convoys[category].append(f"{convoy_desc} ({note})")
                
            else:
                # Analyze if this convoy represents opportunity or threat
                if dest_owner == power_name:
                    category = "THREATS TO WATCH"
                    note = f"{army_owner or 'potential'} attack on your position"
                elif army_owner and dest_owner:
                    category = "ALLIED OPPORTUNITIES"
                    note = f"{army_owner} could attack {dest_owner} - potential alliance"
                else:
                    category = "ALLIED OPPORTUNITIES"
                    note = "potential diplomatic leverage"
                
                convoys[category].append(f"{convoy_desc} ({note})")

    # Format output
    output = "CONVOY POSSIBILITIES:\n\n"
    
    # Log convoy counts for debugging
    convoy_counts = {category: len(convoys[category]) for category in convoys}
    logger.debug(f"CONVOYS | {power_name} | Counts: " + 
                 ", ".join(f"{category}: {count}" for category, count in convoy_counts.items()))
    
    for category, convoy_list in convoys.items():
        if convoy_list:
            output += f"{category}:\n"
            for convoy in sorted(convoy_list):
                output += f"  {convoy}\n"
            output += "\n"

    return output

def generate_threat_assessment(game, board_state, power_name):
    """
    High-level function that tries to identify immediate threats 
    from adjacent enemy units to your units or centers.
    """
    our_units = set(loc.split(" ", 1)[1] for loc in board_state["units"].get(power_name, []))
    our_centers = set(board_state["centers"].get(power_name, []))
    
    threats = []
    for enemy_power, enemy_units in board_state["units"].items():
        if enemy_power == power_name:
            continue
        for unit_code in enemy_units:
            try:
                # e.g. "A MUN"
                parts = unit_code.split(" ", 1)
                enemy_loc = parts[1].strip()
            except IndexError:
                continue
            
            # check adjacency to our units or centers
            neighbors = game.map.loc_abut.get(enemy_loc, [])
            threatened = []
            for nbr in neighbors:
                if nbr in our_units:
                    threatened.append(f"our unit @ {nbr}")
                elif nbr in our_centers:
                    threatened.append(f"our center @ {nbr}")
            
            if threatened:
                threats.append((enemy_power, unit_code, threatened))
    
    output = "THREAT ASSESSMENT:\n"
    if not threats:
        output += "  No immediate threats detected.\n\n"
        logger.debug(f"THREATS | {power_name} | No immediate threats detected")
        return output
    
    # Log threat counts for debugging
    logger.debug(f"THREATS | {power_name} | Detected {len(threats)} threats from {len(set(t[0] for t in threats))} powers")
    
    for (enemy_pwr, code, targets) in threats:
        output += f"  {enemy_pwr}'s {code} threatens {', '.join(targets)}\n"
    output += "\n"
    return output


def generate_sc_projection(game, board_state, power_name):
    """
    Estimate potential gains from neutral or weakly held enemy SCs, plus 
    highlight which of your centers are at risk (no unit present).
    """
    our_units = set(loc.split(" ", 1)[1] for loc in board_state["units"].get(power_name, []))
    our_centers = set(board_state["centers"].get(power_name, []))
    all_centers_control = board_state["centers"]  # dict of power -> list of centers
    all_controlled = set()
    for c_list in all_centers_control.values():
        all_controlled.update(c_list)
    
    # Potential neutral SC gains
    neutral_gains = []
    for sc in game.map.scs:
        if sc not in all_controlled:  # neutral
            # see if we have a unit adjacent
            neighbors = game.map.loc_abut.get(sc, [])
            if any(nbr in our_units for nbr in neighbors):
                neutral_gains.append(sc)
    
    # Weakly held enemy SC
    contestable = []
    for e_pwr, e_centers in board_state["centers"].items():
        if e_pwr == power_name:
            continue
        enemy_units = set(loc.split(" ", 1)[1] for loc in board_state["units"].get(e_pwr, []))
        for c in e_centers:
            # if no enemy unit is physically there
            if c not in enemy_units:
                # see if we have a unit adjacent
                neighbors = game.map.loc_abut.get(c, [])
                if any(nbr in our_units for nbr in neighbors):
                    contestable.append((c, e_pwr))
    
    # Our centers at risk (no unit present)
    at_risk = [own_sc for own_sc in our_centers if own_sc not in our_units]
    
    # Format final
    output = "SUPPLY CENTER PROJECTION:\n"
    output += f"  Current Count: {len(our_centers)}\n"
    
    if neutral_gains:
        output += "  Potential neutral gains:\n"
        for sc in neutral_gains:
            output += f"    {format_location_with_expansion(game, sc)}\n"
    
    if contestable:
        output += "  Contestable enemy centers:\n"
        for c, e_pwr in contestable:
            output += f"    {format_location_with_expansion(game, c)} (currently owned by {e_pwr})\n"
    
    if at_risk:
        output += "  Centers at risk (no defending unit):\n"
        for sc in at_risk:
            output += f"    {format_location_with_expansion(game, sc)}\n"
    
    best_case = len(our_centers) + len(neutral_gains) + len(contestable)
    worst_case = len(our_centers) - len(at_risk)
    output += f"  Next-phase range: {worst_case} to {best_case} centers\n\n"
    
    # Log SC projection for debugging
    logger.debug(f"SC_PROJ | {power_name} | " +
                 f"Current: {len(our_centers)}, " +
                 f"Neutral gains: {len(neutral_gains)}, " +
                 f"Contestable: {len(contestable)}, " + 
                 f"At risk: {len(at_risk)}, " +
                 f"Range: {worst_case}-{best_case}")
    
    return output
