# AI Diplomacy: 

## Extended AI Features (Experimental)

This repository is an extension of the original [Diplomacy](https://github.com/diplomacy/diplomacy) project. This repository has been extended to integrate multiple Large Language Models (LLMs) into Diplomacy gameplay. **These extensions are experimental, subject to change**, and actively in development. The main additions are as follows:

- **Conversation & Negotiation**: Powers can have multi-turn negotiations with each other via `lm_game.py`. They can exchange private or global messages, allowing for more interactive diplomacy.  
- **Order Generation**: Each power can choose its orders (moves, holds, supports, etc.) using LLMs via `lm_service_versus.py`. Currently supports OpenAI, Claude, Gemini, DeepSeek
- **Phase Summaries**: Modifications in the `game.py` engine allow the generation of "phase summaries," providing a succinct recap of each turn's events. This could help both human spectators and the LLMs themselves to understand the game state more easily.  
- **Agent State Architecture**: Powers are represented by DiplomacyAgent instances that maintain goals, relationships, and a journal tracking thoughts and decisions. This stateful design allows for more consistent and strategic play.
- **Prompt Templates**: Prompts used by the LLMs are stored in `/prompts/`. You can edit these to customize how models are instructed for both orders and conversations.  
- **Experimental & WIP**: Ongoing development includes adding strategic goals for each power, more flexible conversation lengths, and a readiness check to advance the phase if all powers are done negotiating.

### How it Works

1. **`lm_game.py`**  
   - Orchestrates a Diplomacy game where each power's moves are decided by an LLM.  
   - Manages conversation rounds (currently up to 3 by default) and calls `get_conversation_reply()` for each power.  
   - After negotiations, each power's orders are gathered concurrently (via threads), using `get_orders()` from the respective LLM client.  
   - Calls `game.process()` to move to the next phase, optionally collecting phase summaries along the way.
   - Updates agent state after each phase to maintain continuity and strategic direction.

2. **`lm_service_versus.py`**  
   - Defines a base class (`BaseModelClient`) for hitting any LLM endpoint.  
   - Subclasses (`OpenAIClient`, `ClaudeClient`, etc.) implement `generate_response()` and `get_conversation_reply()` with the specifics of each LLM's API.  
   - Handles prompt construction for orders and conversation, JSON extraction to parse moves or messages, and fallback logic for invalid LLM responses.  

3. **`agent.py`**
   - Implements the DiplomacyAgent class that maintains state for each power.
   - Tracks goals, relationships with other powers, and a private journal of thoughts.
   - Provides robust JSON parsing for LLM responses with case-insensitive validation.
   - Updates goals and relationships based on game events to maintain coherent strategies.

4. **Modifications in `game.py` (Engine)**  
   - Added a `_generate_phase_summary()` method and `phase_summaries` dict to store short textual recaps of each phase.  
   - Summaries can be viewed or repurposed for real-time commentary or as additional context fed back into the LLM.  

### Future Explorations

- **Longer Conversation Phases**: Support for more than 3 message rounds, or an adaptive approach that ends negotiation early if all powers signal "ready."  
- **Enhanced Agent Memory**: Further develop agent memory and learning from past interactions to influence future decisions.
- **Strategic Map Analysis**: Leverage the map graph structure to help agents make better tactical decisions.
- **Live Front-End Integration**: Display phase summaries, conversation logs, and highlights of completed orders in a real-time UI. (an attempt to display phase summaries currently in progress)

---


<p align="center">
  <img width="500" src="docs/images/map_overview.png" alt="Diplomacy Map Overview">
</p>

## Documentation

The complete documentation is available at [diplomacy.readthedocs.io](https://diplomacy.readthedocs.io/).

## Getting Started

### Installation

The latest version of the package can be installed with:

```python3
pip install diplomacy
```

The package is compatible with Python 3.5, 3.6, and 3.7.

### Running a game

The following script plays a game locally by submitting random valid orders until the game is completed.

```python3
import random
from diplomacy import Game
from diplomacy.utils.export import to_saved_game_format

# Creating a game
# Alternatively, a map_name can be specified as an argument. e.g. Game(map_name='pure')
game = Game()
while not game.is_game_done:

    # Getting the list of possible orders for all locations
    possible_orders = game.get_all_possible_orders()

    # For each power, randomly sampling a valid order
    for power_name, power in game.powers.items():
        power_orders = [random.choice(possible_orders[loc]) for loc in game.get_orderable_locations(power_name)
                        if possible_orders[loc]]
        game.set_orders(power_name, power_orders)

    # Messages can be sent locally with game.add_message
    # e.g. game.add_message(Message(sender='FRANCE',
    #                               recipient='ENGLAND',
    #                               message='This is a message',
    #                               phase=self.get_current_phase(),
    #                               time_sent=int(time.time())))

    # Processing the game to move to the next phase
    game.process()

# Exporting the game to disk to visualize (game is appended to file)
# Alternatively, we can do >> file.write(json.dumps(to_saved_game_format(game)))
to_saved_game_format(game, output_path='game.json')
```

## Web interface

It is also possible to install a web interface in React to play against bots and/or other humans and to visualize games.

The web interface can be installed with:

```bash
# Install NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.34.0/install.sh | bash

# Clone repo
git clone https://github.com/diplomacy/diplomacy.git

# Install package locally
# You may want to install it in a conda or virtualenv environment
cd diplomacy/
pip install -r requirements_dev.txt

# Build node modules
cd diplomacy/web
npm install .
npm install . --only=dev

# In a terminal window or tab - Launch React server
npm start

# In another terminal window or tab - Launch diplomacy server
python -m diplomacy.server.run
```

The web interface will be accessible at http://localhost:3000.

To login, users can use admin/password or username/password. Additional users can be created by logging in with a username that does not exist in the database.

![](docs/images/web_interface.png)

### Visualizing a game

It is possible to visualize a game by using the "Load a game from disk" menu on the top-right corner of the web interface.

![](docs/images/visualize_game.png)


## Network Game

It is possible to join a game remotely over a network using websockets. The script below plays a game over a network.

Note. The server must be started with `python -m diplomacy.server.run` for the script to work.

```python3
import asyncio
import random
from diplomacy.client.connection import connect
from diplomacy.utils import exceptions

POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']

async def create_game(game_id, hostname='localhost', port=8432):
    """ Creates a game on the server """
    connection = await connect(hostname, port)
    channel = await connection.authenticate('random_user', 'password')
    await channel.create_game(game_id=game_id, rules={'REAL_TIME', 'NO_DEADLINE', 'POWER_CHOICE'})

async def play(game_id, power_name, hostname='localhost', port=8432):
    """ Play as the specified power """
    connection = await connect(hostname, port)
    channel = await connection.authenticate('user_' + power_name, 'password')

    # Waiting for the game, then joining it
    while not (await channel.list_games(game_id=game_id)):
        await asyncio.sleep(1.)
    game = await channel.join_game(game_id=game_id, power_name=power_name)

    # Playing game
    while not game.is_game_done:
        current_phase = game.get_current_phase()

        # Submitting orders
        if game.get_orderable_locations(power_name):
            possible_orders = game.get_all_possible_orders()
            orders = [random.choice(possible_orders[loc]) for loc in game.get_orderable_locations(power_name)
                      if possible_orders[loc]]
            print('[%s/%s] - Submitted: %s' % (power_name, game.get_current_phase(), orders))
            await game.set_orders(power_name=power_name, orders=orders, wait=False)

        # Messages can be sent with game.send_message
        # await game.send_game_message(message=game.new_power_message('FRANCE', 'This is the message'))

        # Waiting for game to be processed
        while current_phase == game.get_current_phase():
            await asyncio.sleep(0.1)

    # A local copy of the game can be saved with to_saved_game_format
    # To download a copy of the game with messages from all powers, you need to export the game as an admin
    # by logging in as 'admin' / 'password'

async def launch(game_id):
    """ Creates and plays a network game """
    await create_game(game_id)
    await asyncio.gather(*[play(game_id, power_name) for power_name in POWERS])

if __name__ == '__main__':
    asyncio.run(launch(game_id=str(random.randint(1, 1000))))

## License

This project is licensed under the APGLv3 License - see the [LICENSE](LICENSE) file for details
