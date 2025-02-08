// ==============================================================================
// Copyright (C) 2019 - Philip Paquette, Steven Bocco
//
//  This program is free software: you can redistribute it and/or modify it under
//  the terms of the GNU Affero General Public License as published by the Free
//  Software Foundation, either version 3 of the License, or (at your option) any
//  later version.
//
//  This program is distributed in the hope that it will be useful, but WITHOUT
//  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
//  FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
//  details.
//
//  You should have received a copy of the GNU Affero General Public License along
//  with this program.  If not, see <https://www.gnu.org/licenses/>.
// ==============================================================================
import $ from "jquery";
import {STRINGS} from "../../diplomacy/utils/strings";
import {Game} from "../../diplomacy/engine/game";

export function loadGameFromDisk() {
    return new Promise((onLoad, onError) => {
        const input = $(document.createElement('input'));
        input.attr("type", "file");
        input.trigger('click');
        input.change(event => {
            const file = event.target.files[0];
            if (!file.name.match(/\.json$/i)) {
                onError(`Invalid JSON filename ${file.name}`);
                return;
            }
            const reader = new FileReader();
            reader.onload = () => {
                console.log('[loadGameFromDisk] Reading JSON file...');
                let savedData;
                try {
                    savedData = JSON.parse(reader.result);
                } catch (e) {
                    onError('Could not parse JSON file: ' + e);
                    return;
                }

                const gameObject = {
                    game_id: `(local) ${savedData.id}`,
                    map_name: savedData.map,
                    rules: savedData.rules,
                    state_history: {},
                    message_history: {},
                    order_history: {},
                    result_history: {},
                    phase_summaries: {}
                };

                // Load older phases into history
                for (let i = 0; i < savedData.phases.length - 1; ++i) {
                    const savedPhase = savedData.phases[i];
                    const gameState = savedPhase.state;
                    const phaseOrders = savedPhase.orders || {};
                    const phaseResults = savedPhase.results || {};

                    // 1) Fix or parse messages if they're a string
                    let phaseMessages = savedPhase.messages;
                    if (typeof phaseMessages === 'string') {
                        console.warn('[loadGameFromDisk] Phase', savedPhase.name,
                                     'has messages as string. Attempting fallback parse...');
                        // If it starts with "SortedDict", we can't trivially parse. 
                        // Minimal fallback: set to empty object or parse if you have a custom parser.
                        if (phaseMessages.startsWith('SortedDict{')) {
                            phaseMessages = {};
                        }
                    } else if (!phaseMessages) {
                        phaseMessages = {};
                    } else {
                        // Convert array -> object keyed by time_sent
                        const obj = {};
                        for (const msg of phaseMessages) {
                            if (msg && msg.time_sent !== undefined) {
                                obj[msg.time_sent] = msg;
                            }
                        }
                        phaseMessages = obj;
                    }

                    if (!gameState.name) gameState.name = savedPhase.name;

                    gameObject.state_history[gameState.name] = gameState;
                    gameObject.message_history[gameState.name] = phaseMessages;
                    gameObject.order_history[gameState.name] = phaseOrders;
                    gameObject.result_history[gameState.name] = phaseResults;

                    // Summaries
                    if (savedPhase.summary) {
                        console.log(`[loadGameFromDisk] Loading summaries for phase`, gameState.name);
                        gameObject.phase_summaries[gameState.name] = savedPhase.summary;
                    } else {
                        console.log(`[loadGameFromDisk] No summary for phase ${savedPhase.name}`);
                    }
                }

                // Load latest phase
                const latestPhase = savedData.phases[savedData.phases.length - 1];
                const latestGameState = latestPhase.state;
                const latestPhaseOrders = latestPhase.orders || {};
                const latestPhaseResults = latestPhase.results || {};
                let latestPhaseMessages = latestPhase.messages;
                if (typeof latestPhaseMessages === 'string') {
                    console.warn('[loadGameFromDisk] Latest phase has messages as string. Fallback parse...');
                    if (latestPhaseMessages.startsWith('SortedDict{')) {
                        latestPhaseMessages = {};
                    }
                } else if (!latestPhaseMessages) {
                    latestPhaseMessages = {};
                } else {
                    const obj = {};
                    for (const msg of latestPhaseMessages) {
                        if (msg && msg.time_sent !== undefined) {
                            obj[msg.time_sent] = msg;
                        }
                    }
                    latestPhaseMessages = obj;
                }

                if (!latestGameState.name)
                    latestGameState.name = latestPhase.name;
                gameObject.result_history[latestGameState.name] = latestPhaseResults;

                if (latestPhase.summary) {
                    console.log(`[loadGameFromDisk] Loading summary for latest phase ${latestGameState.name}:`, latestPhase.summary);
                    gameObject.phase_summaries[latestGameState.name] = latestPhase.summary;
                } else {
                    console.log(`[loadGameFromDisk] No summary for latest phase ${latestGameState.name}`);
                }

                // Final game metadata
                gameObject.messages = [];
                gameObject.role = STRINGS.OBSERVER_TYPE;
                gameObject.status = STRINGS.COMPLETED;
                gameObject.timestamp_created = 0;
                gameObject.deadline = 0;
                gameObject.n_controls = 0;
                gameObject.registration_password = '';

                const game = new Game(gameObject);

                // Set the current phase to the latest
                game.setPhaseData({
                    name: latestGameState.name,
                    state: latestGameState,
                    orders: latestPhaseOrders,
                    messages: latestPhaseMessages
                });

                onLoad(game);
            };
            reader.readAsText(file);
        });
    });
}
