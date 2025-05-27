import json
from ai_diplomacy.game_history import GameHistory, Phase


def test_game_history_to_dict_serialization():
    # Instantiate Objects
    game_history = GameHistory()

    # Phase 1
    game_history.add_phase("S1901M")
    phase1 = game_history.get_phase_by_name("S1901M")
    assert phase1 is not None  # Ensure phase was added

    phase1.add_plan("FRANCE", "Plan for France in S1901M")
    phase1.add_message("ENGLAND", "FRANCE", "Hello from England in S1901M!")
    # For add_orders on Phase object, it takes power, orders, results
    # The GameHistory.add_orders takes phase_name, power_name, orders (without results)
    # The GameHistory.add_results takes phase_name, power_name, results
    # For testing to_dict, we need to populate orders_by_power and results_by_power on the Phase object.
    # The Phase.add_orders method is a bit confusing as it also takes results.
    # Let's directly manipulate the dictionaries for clarity in testing to_dict structure.
    phase1.orders_by_power["ITALY"].extend(["F ROM - NAP"])
    phase1.results_by_power["ITALY"].extend([["SUCCESSFUL"]])

    phase1.phase_summaries["GERMANY"] = "Germany did well in S1901M."
    phase1.experience_updates["RUSSIA"] = "Learned about betrayal in S1901M."

    # Phase 2
    game_history.add_phase("F1901M")
    phase2 = game_history.get_phase_by_name("F1901M")
    assert phase2 is not None

    phase2.add_plan("AUSTRIA", "Plan for Austria in F1901M")
    phase2.add_message("TURKEY", "GLOBAL", "Turkey's global message in F1901M.")
    phase2.orders_by_power["ENGLAND"].extend(["A LON H", "F EDI S A LON H"])
    phase2.results_by_power["ENGLAND"].extend([["SUCCESSFUL"], ["SUCCESSFUL"]])
    phase2.phase_summaries["FRANCE"] = "France struggled in F1901M."
    phase2.experience_updates["ITALY"] = "Italy gained valuable experience in F1901M."

    # Call to_dict()
    history_dict = game_history.to_dict()

    # Assert Dictionary Type
    assert isinstance(history_dict, dict)

    # Assert Key Fields
    assert "phases" in history_dict
    assert isinstance(history_dict["phases"], list)
    assert len(history_dict["phases"]) == 2

    # Check Phase 1
    phase_1_dict = history_dict["phases"][0]
    assert phase_1_dict["name"] == "S1901M"
    assert "plans" in phase_1_dict and isinstance(phase_1_dict["plans"], dict)
    assert phase_1_dict["plans"]["FRANCE"] == "Plan for France in S1901M"

    assert "messages" in phase_1_dict and isinstance(phase_1_dict["messages"], list)
    assert len(phase_1_dict["messages"]) == 1
    message_1_dict = phase_1_dict["messages"][0]
    assert message_1_dict["sender"] == "ENGLAND"
    assert message_1_dict["recipient"] == "FRANCE"
    assert message_1_dict["content"] == "Hello from England in S1901M!"

    assert "orders_by_power" in phase_1_dict and isinstance(
        phase_1_dict["orders_by_power"], dict
    )
    assert phase_1_dict["orders_by_power"]["ITALY"] == ["F ROM - NAP"]
    assert "results_by_power" in phase_1_dict and isinstance(
        phase_1_dict["results_by_power"], dict
    )
    assert phase_1_dict["results_by_power"]["ITALY"] == [["SUCCESSFUL"]]

    assert "phase_summaries" in phase_1_dict and isinstance(
        phase_1_dict["phase_summaries"], dict
    )
    assert phase_1_dict["phase_summaries"]["GERMANY"] == "Germany did well in S1901M."
    assert "experience_updates" in phase_1_dict and isinstance(
        phase_1_dict["experience_updates"], dict
    )
    assert (
        phase_1_dict["experience_updates"]["RUSSIA"]
        == "Learned about betrayal in S1901M."
    )

    # Check Phase 2 (basic check for existence and name)
    phase_2_dict = history_dict["phases"][1]
    assert phase_2_dict["name"] == "F1901M"
    assert phase_2_dict["plans"]["AUSTRIA"] == "Plan for Austria in F1901M"
    assert phase_2_dict["messages"][0]["sender"] == "TURKEY"

    # Assert JSON Serialization
    json_string = json.dumps(
        history_dict, indent=2
    )  # Add indent for easier debugging if it fails
    assert isinstance(json_string, str)

    reloaded_dict = json.loads(json_string)
    assert reloaded_dict == history_dict


def test_game_history_to_dict_empty():
    game_history = GameHistory()
    history_dict = game_history.to_dict()
    assert isinstance(history_dict, dict)
    assert "phases" in history_dict
    assert isinstance(history_dict["phases"], list)
    assert len(history_dict["phases"]) == 0

    # Test JSON serialization for empty history
    json_string = json.dumps(history_dict)
    assert isinstance(json_string, str)
    reloaded_dict = json.loads(json_string)
    assert reloaded_dict == history_dict


def test_phase_add_orders_internal_consistency():
    """
    This test is more about the Phase.add_orders method if it's used for populating,
    but to_dict relies on consistent internal structure.
    """
    phase = Phase(name="T1900M")
    # Phase.add_orders(power, orders, results)
    phase.add_orders("FRANCE", ["A PAR H"], [["SUCCESSFUL"]])
    phase.add_orders("FRANCE", ["F BRE - MAO"], [["BOUNCED", "F ENG - MAO"]])

    phase_dict = {
        "name": phase.name,
        "plans": dict(phase.plans),
        "messages": [
            vars(msg) for msg in phase.messages
        ],  # vars() works for simple dataclasses
        "orders_by_power": {p: list(o) for p, o in phase.orders_by_power.items()},
        "results_by_power": {p: list(r) for p, r in phase.results_by_power.items()},
        "phase_summaries": dict(phase.phase_summaries),
        "experience_updates": dict(phase.experience_updates),
    }

    assert phase_dict["orders_by_power"]["FRANCE"] == ["A PAR H", "F BRE - MAO"]
    assert phase_dict["results_by_power"]["FRANCE"] == [
        ["SUCCESSFUL"],
        ["BOUNCED", "F ENG - MAO"],
    ]

    # Test with GameHistory.to_dict()
    gh = GameHistory()
    gh.phases.append(phase)
    gh_dict = gh.to_dict()

    assert gh_dict["phases"][0]["orders_by_power"]["FRANCE"] == [
        "A PAR H",
        "F BRE - MAO",
    ]
    assert gh_dict["phases"][0]["results_by_power"]["FRANCE"] == [
        ["SUCCESSFUL"],
        ["BOUNCED", "F ENG - MAO"],
    ]


# Test with empty orders/results lists for a power
def test_game_history_to_dict_empty_orders_for_power():
    game_history = GameHistory()
    game_history.add_phase("S1901M")
    phase1 = game_history.get_phase_by_name("S1901M")
    assert phase1 is not None

    # Add a power but no orders for it
    phase1.orders_by_power["AUSTRIA"] = []  # Explicitly empty
    phase1.results_by_power["AUSTRIA"] = []

    history_dict = game_history.to_dict()
    phase_1_dict = history_dict["phases"][0]

    assert "AUSTRIA" in phase_1_dict["orders_by_power"]
    assert phase_1_dict["orders_by_power"]["AUSTRIA"] == []
    assert "AUSTRIA" in phase_1_dict["results_by_power"]
    assert phase_1_dict["results_by_power"]["AUSTRIA"] == []

    json_string = json.dumps(history_dict)
    reloaded_dict = json.loads(json_string)
    assert reloaded_dict == history_dict


# Test with a phase that has no messages, plans, etc.
def test_game_history_to_dict_empty_phase_fields():
    game_history = GameHistory()
    game_history.add_phase("S1901M")  # Phase with no sub-data

    history_dict = game_history.to_dict()
    phase_1_dict = history_dict["phases"][0]

    assert phase_1_dict["name"] == "S1901M"
    assert phase_1_dict["plans"] == {}
    assert phase_1_dict["messages"] == []
    assert phase_1_dict["orders_by_power"] == {}  # defaultdict(list) becomes {}
    assert phase_1_dict["results_by_power"] == {}  # defaultdict(list) becomes {}
    assert phase_1_dict["phase_summaries"] == {}
    assert phase_1_dict["experience_updates"] == {}

    json_string = json.dumps(history_dict)
    reloaded_dict = json.loads(json_string)
    assert reloaded_dict == history_dict
