"""Utility functions for model assignment in AI Diplomacy."""

import logging
import random
from typing import Optional, List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .game_config import GameConfig
from .constants import DEFAULT_AGENT_MANAGER_FALLBACK_MODEL # Import from constants

logger = logging.getLogger(__name__)

__all__ = ["assign_models_to_powers"]

# DEFAULT_AGENT_MANAGER_FALLBACK_MODEL has been moved to constants.py

def assign_models_to_powers(game_config: "GameConfig", all_game_powers: List[str]) -> Dict[str, str]:
    """
    Assigns LLM model IDs to each participating power in the game.

    This function considers:
    - A specific power controlled by a specific model (from config.power_name & config.model_id).
    - A list of fixed models to be assigned to other powers (from config.fixed_models).
    - Randomization of fixed model assignments (config.randomize_fixed_models).
    - Powers to be excluded (config.exclude_powers).
    - The total number of LLM-controlled players (config.num_players).

    Args:
        game_config: The game configuration object.
        all_game_powers: A list of all power names in the game (e.g., ["AUSTRIA", "ENGLAND", ...]).

    Returns:
        A dictionary mapping power names to their assigned model IDs.
    """
    logger.info(
        "Assigning models to powers using TOML config and GameConfig overrides..."
    )

    # Handle None exclude_powers by using empty list
    exclude_powers = game_config.exclude_powers or []

    # Start with TOML configurations from GameConfig
    powers_and_models: Dict[str, str] = dict(
        game_config.power_model_assignments
    )
    default_model = (
        game_config.default_model_from_config
        or DEFAULT_AGENT_MANAGER_FALLBACK_MODEL
    )
    logger.info(
        f"Using default model: '{default_model}' (from TOML or AgentManager fallback)"
    )

    # Override or fill in based on primary agent settings from GameConfig (CLI overrides)
    primary_agent_power = game_config.power_name
    primary_agent_model_cli = (
        game_config.model_id
    )  # Model specified via CLI for primary agent

    if primary_agent_power and primary_agent_model_cli:
        if primary_agent_power in exclude_powers:
            logger.warning(
                f"Primary agent power {primary_agent_power} is excluded. Ignoring CLI model assignment."
            )
        else:
            logger.info(
                f"CLI override: Assigning primary agent {primary_agent_power} -> {primary_agent_model_cli}"
            )
            powers_and_models[primary_agent_power] = primary_agent_model_cli
    elif primary_agent_power and primary_agent_power not in powers_and_models:
        # Primary power specified but no model via CLI, and not in TOML.
        # Assign default model to it if it's not excluded.
        if primary_agent_power not in exclude_powers:
            logger.info(
                f"Primary power {primary_agent_power} specified without model, assigning default: {default_model}"
            )
            powers_and_models[primary_agent_power] = default_model

    # Fill remaining LLM slots using fixed_models from CLI or default model
    # Count how many LLM-controlled powers we have so far from TOML + primary CLI override.
    current_llm_powers = {
        p for p, m in powers_and_models.items() if p not in exclude_powers
    }
    num_llm_controlled_so_far = len(current_llm_powers)

    num_additional_llm_players_needed = (
        game_config.num_players - num_llm_controlled_so_far
    )

    # Consider powers from TOML that are not excluded for this calculation
    candidate_powers_for_filling_slots = [
        p
        for p in all_game_powers
        if p not in exclude_powers and p not in current_llm_powers
    ]

    if game_config.randomize_fixed_models:
        random.shuffle(candidate_powers_for_filling_slots)

    fixed_models_cli_list = (
        list(game_config.fixed_models) if game_config.fixed_models else []
    )
    if game_config.randomize_fixed_models and fixed_models_cli_list:
        random.shuffle(fixed_models_cli_list)

    additional_llm_assigned_count = 0
    # Loop variable 'i' was not used. Replaced with '_'
    for _, power_to_assign_additional_model in enumerate(
        candidate_powers_for_filling_slots
    ):
        if additional_llm_assigned_count >= num_additional_llm_players_needed:
            break

        if (
            fixed_models_cli_list
        ):  # Use CLI fixed_models first for these additional slots
            model_to_assign = fixed_models_cli_list[
                additional_llm_assigned_count % len(fixed_models_cli_list)
            ]
        else:  # If no CLI fixed_models, use the default (from TOML or AgentManager fallback)
            model_to_assign = default_model

        powers_and_models[power_to_assign_additional_model] = model_to_assign
        logger.info(
            f"Assigned additional LLM agent: {power_to_assign_additional_model} -> {model_to_assign} (num_players target)"
        )
        additional_llm_assigned_count += 1

    # Final filter: ensure only num_players are LLM controlled, respecting exclusions
    final_llm_assignments: Dict[str, str] = {}
    powers_considered_for_final_llm_list = [
        p for p in all_game_powers if p not in exclude_powers
    ]

    # Prioritize powers that have specific assignments (CLI primary, then TOML)
    priority_order: List[str] = []
    if (
        primary_agent_power
        and primary_agent_power in powers_and_models
        and primary_agent_power not in exclude_powers
    ):
        priority_order.append(primary_agent_power)
    for p in powers_and_models.keys():  # Iterate keys from TOML based assignments
        if p not in priority_order and p not in exclude_powers:
            priority_order.append(p)
    for p in powers_considered_for_final_llm_list:
        if p not in priority_order:  # Add remaining non-excluded powers
            priority_order.append(p)

    llm_slots_filled = 0
    for power_name in priority_order:
        if llm_slots_filled >= game_config.num_players:
            break
        if (
            power_name in powers_and_models
        ):  # Has an assignment from TOML or CLI override or additional filling
            final_llm_assignments[power_name] = powers_and_models[power_name]
            llm_slots_filled += 1
        elif (
            power_name not in exclude_powers
        ):  # Needs a default because it wasn't specified earlier
            final_llm_assignments[power_name] = default_model
            logger.info(
                f"Assigning default model '{default_model}' to {power_name} to meet num_players target."
            )
            llm_slots_filled += 1

    logger.info(
        f"Final model assignments after considering num_players ({game_config.num_players}): {final_llm_assignments}"
    )

    return final_llm_assignments
