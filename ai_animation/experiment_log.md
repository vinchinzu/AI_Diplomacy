# Experiment Log

| Problem                                                      | Attempted Solution | Real Outcome | Current $ Balance |
| :----------------------------------------------------------- | :----------------- | :----------- | :---------------- |
| 1. Relationships chart is blank. <br> 2. Game stops after narrator summary in phase 2. | 1. Updated `PhaseSchema` in `types/gameState.ts` to include `agent_relationships` definition. <br> 2. Uncommented `updateChatWindows(currentPhase, true);` in `phase.ts`. |              | $0                |
| Add webhook notifications for phase changes | 1. Added `webhookUrl` config to `src/config.ts` <br> 2. Created `src/webhooks/phaseNotifier.ts` with fire-and-forget webhook notification <br> 3. Added `notifyPhaseChange()` call in `_setPhase()` function <br> 4. Updated `.env.example` with `VITE_WEBHOOK_URL` |              | $0                |
