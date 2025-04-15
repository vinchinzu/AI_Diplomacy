import logging
from collections import deque
from typing import Dict, Set, List, Tuple, Callable, Any, Optional
from diplomacy.map import Map

logger = logging.getLogger(__name__)


class DiplomacyGraph:
    """Custom graph implementation for Diplomacy map connectivity."""

    def __init__(self):
        # Main graph structure: dict of dict of sets
        # graph[node1][node2] = {'A', 'F'} means both army and fleet can move between nodes
        # graph[node1][node2] = {'A'} means only army can move between nodes
        self.graph: Dict[str, Dict[str, Set[str]]] = {}

    def add_node(self, node: str):
        """Add a node if it doesn't exist."""
        if node not in self.graph:
            self.graph[node] = {}

    def add_edge(self, node1: str, node2: str, unit_type: str):
        """Add an edge between nodes for specific unit type ('A' or 'F')."""
        self.add_node(node1)
        self.add_node(node2)

        # Add connection for node1 -> node2
        if node2 not in self.graph[node1]:
            self.graph[node1][node2] = set()
        self.graph[node1][node2].add(unit_type)

        # Add connection for node2 -> node1 (undirected graph)
        if node1 not in self.graph[node2]:
            self.graph[node2][node1] = set()
        self.graph[node2][node1].add(unit_type)

    def get_adjacent(self, node: str) -> List[str]:
        """Get all nodes adjacent to given node."""
        return list(self.graph.get(node, {}).keys())

    def get_allowed_units(self, node1: str, node2: str) -> Set[str]:
        """Get set of unit types that can move between these nodes."""
        return self.graph.get(node1, {}).get(node2, set())

    def nodes(self) -> List[str]:
        """Return all nodes in the graph."""
        return list(self.graph.keys())

    def edges(self) -> List[Tuple[str, str, Set[str]]]:
        """Return all edges with their unit types as (node1, node2, unit_types)."""
        edges = []
        seen = set()  # To avoid duplicates in undirected graph

        for node1 in self.graph:
            for node2, unit_types in self.graph[node1].items():
                # Ensure consistent ordering for the 'seen' check
                edge_tuple = tuple(sorted((node1, node2)))
                if edge_tuple not in seen:
                    edges.append((node1, node2, unit_types))
                    seen.add(edge_tuple)

        return edges

# --- BFS Functions --- 
def bfs_shortest_path(
    graph: DiplomacyGraph,
    start: str,
    match_condition: Callable[[str], Any], # Function returns non-None/non-False if matched
    allowed_unit_types: Set[str]
) -> Tuple[Optional[List[str]], Any]:
    """
    Performs Breadth-First Search on a DiplomacyGraph from 'start' to find the first territory 
    for which 'match_condition(territory)' returns a truthy value.

    Args:
        graph: The DiplomacyGraph instance to search.
        start: The starting territory node name (e.g., 'PAR').
        match_condition: A function that takes a territory name (str) and returns 
                         any value that evaluates to True if the condition is met, 
                         or False/None otherwise. The returned value is included in the output.
        allowed_unit_types: A set of unit types ('A', 'F') allowed for traversal.

    Returns:
        Tuple[Optional[List[str]], Any]: 
            - A list of territory names representing the shortest path from 'start' to the matched 
              territory (inclusive), or None if no path is found.
            - The truthy value returned by match_condition for the matched territory, or None.
    """
    if start not in graph.graph: # Access the internal graph dict
        logger.warning(f"BFS shortest path: Start node '{start}' not in graph.")
        return None, None
    
    visited: Set[str] = {start}
    # Queue stores paths (lists of nodes)
    queue: deque[List[str]] = deque([[start]])

    # Check if the starting territory itself satisfies match_condition
    initial_match = match_condition(start)
    if initial_match:
        return [start], initial_match

    while queue:
        path = queue.popleft()
        current = path[-1]
        
        # Check neighbors of the current node
        for neighbor in graph.get_adjacent(current):
            edge_types = graph.get_allowed_units(current, neighbor)
            
            # Check if any allowed unit type can traverse this edge
            if edge_types.intersection(allowed_unit_types):
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = path + [neighbor]
                    
                    # Check if the neighbor meets the match condition
                    match_result = match_condition(neighbor)
                    if match_result:
                        return new_path, match_result
                        
                    queue.append(new_path)
                    
    logger.debug(f"BFS shortest path: No node matching condition found from '{start}'.")
    return None, None

def bfs_nearest_adjacent(
    graph: DiplomacyGraph, 
    start: str, 
    occupant_map: Dict[str, Any], # Map territory_name -> occupant_info 
    allowed_unit_types: Set[str]
) -> Tuple[Optional[List[str]], Tuple[Optional[str], Any]]:
    """
    Performs Breadth-First Search from 'start' to find the shortest path to a territory 
    that is *adjacent* to any territory listed in the 'occupant_map'.

    Args:
        graph: The DiplomacyGraph instance to search.
        start: The starting territory node name.
        occupant_map: A dictionary where keys are territory names occupied by entities 
                      we want to find adjacency to. Values can be any associated info 
                      (e.g., the occupying unit type or power).
        allowed_unit_types: A set of unit types ('A', 'F') allowed for traversal.

    Returns:
        Tuple[Optional[List[str]], Tuple[Optional[str], Any]]:
            - A list representing the shortest path from 'start' to the territory adjacent 
              to an occupied one, or None if no such path exists.
            - A tuple containing: 
                - The name of the occupied territory that was found adjacent to the path's end.
                - The value associated with that occupied territory from occupant_map.
              Returns (None, None) if no path is found.
    """
    if not occupant_map or start not in graph.graph: # Access the internal graph dict
        logger.warning(f"BFS nearest adjacent: Invalid input - occupant_map empty or start node '{start}' not in graph.")
        return None, (None, None)
        
    visited: Set[str] = {start}
    # Queue stores paths (lists of nodes)
    queue: deque[List[str]] = deque([[start]])

    while queue:
        path = queue.popleft()
        current = path[-1]
        
        # Check if ANY neighbor of the current node is in the occupant_map
        for neighbor in graph.get_adjacent(current):
            if neighbor in occupant_map:
                # Found a path ending adjacent to an occupied territory
                occupant_info = occupant_map[neighbor]
                return path, (neighbor, occupant_info)

        # If no adjacent occupant found, expand the search to neighbors
        for neighbor in graph.get_adjacent(current):
            edge_types = graph.get_allowed_units(current, neighbor)
            
            # Check if traversal is possible with allowed unit types
            if edge_types.intersection(allowed_unit_types):
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = path + [neighbor]
                    queue.append(new_path)

    logger.debug(f"BFS nearest adjacent: No path found from '{start}' adjacent to occupied territories.")
    return None, (None, None)

# --- Build Function --- 
def build_diplomacy_graph(game_map: Map) -> DiplomacyGraph:
    """
    Builds a DiplomacyGraph representing the connectivity of a given diplomacy map.

    Args:
        game_map: An instance of the diplomacy.map.Map class.

    Returns:
        A populated DiplomacyGraph instance.
    """
    graph = DiplomacyGraph()
    processed_edges = set() # To avoid redundant checks in undirected graph

    for loc1_name in game_map.locs:
        graph.add_node(loc1_name)
        loc1_area = game_map.area_data[loc1_name]

        for loc2_name, coast_spec in loc1_area.adjacencies:
            # Ensure loc2 exists in map data (should always be true)
            if loc2_name not in game_map.area_data:
                logger.warning(f"Adjacent location '{loc2_name}' for '{loc1_name}' not found in map data. Skipping.")
                continue

            loc2_area = game_map.area_data[loc2_name]
            
            # Create a canonical representation for the edge to avoid duplicates
            edge_tuple = tuple(sorted((loc1_name, loc2_name)))
            if edge_tuple in processed_edges:
                continue

            # --- Determine Army ('A') Movement ---            
            can_army_move = False
            # Army moves between land/coastal areas. Cannot move if both are sea.
            if not (loc1_area.is_sea and loc2_area.is_sea):
                 can_army_move = True # Simplified: Assumes land connectivity if not both sea
                 # More precise check might involve pathfinding logic or specific land borders,
                 # but this covers basic adjacency for armies.
            
            if can_army_move:
                graph.add_edge(loc1_name, loc2_name, 'A')

            # --- Determine Fleet ('F') Movement ---            
            can_fleet_move = False
            # Fleet moves between sea/coastal areas. Cannot move if both are pure land.
            if not (loc1_area.is_land and not loc1_area.is_coastal and 
                    loc2_area.is_land and not loc2_area.is_coastal):
                # Check coasts if both are coastal
                if loc1_area.is_coastal and loc2_area.is_coastal:
                    # Fleet can only move if the adjacency specifically allows it (matching coasts)
                    # The adjacency tuple (loc2_name, coast_spec) provides this info. 
                    # We need to check if loc1 can reach loc2 via the specified coast(s).
                    # This often means loc1 needs to have a coast matching coast_spec, 
                    # or the adjacency implies general coastal access.
                    # Using game_map.coast_data might be needed for complex checks.
                    # Let's use a simplified check based on whether coast_spec exists.
                    # A more robust method might directly check map.is_valid_move for fleets.
                    if coast_spec: # Adjacency has coastal specification
                        # Check if loc1_area's coasts are compatible with coast_spec
                        # This logic can be complex; assuming adjacency implies possibility for now.
                         if game_map.is_valid_move('F', loc1_name, loc2_name): # Use built-in check
                            can_fleet_move = True
                    else: # No specific coast needed
                        if game_map.is_valid_move('F', loc1_name, loc2_name): # Use built-in check
                            can_fleet_move = True
                else:
                    # One or both are sea, or one is coastal and one is sea/land
                    # Generally possible if not land-to-land
                    if game_map.is_valid_move('F', loc1_name, loc2_name): # Use built-in check
                         can_fleet_move = True
            
            if can_fleet_move:
                 graph.add_edge(loc1_name, loc2_name, 'F')

            processed_edges.add(edge_tuple)

    logger.info(f"Built DiplomacyGraph with {len(graph.nodes())} nodes and {len(graph.edges())} edges.")
    return graph
