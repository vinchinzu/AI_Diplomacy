#!/usr/bin/env python3
"""Test lie detection on specific known cases"""

import json
import re
from pathlib import Path

# Load game data
game_path = Path("results/20250522_210700_o3vclaudes_o3win/lmvsgame.json")
with open(game_path, 'r') as f:
    game_data = json.load(f)

# Known lie from the report: Turkey F1901M betrays Austria
# Turkey promised: "orders remain exactly as agreed: A CON-BUL"
# Turkey actually ordered: A BUL-SER

print("Testing known lie case: Turkey F1901M")
print("=" * 50)

# Find Turkey's message to Austria in S1901M
for phase in game_data['phases']:
    if phase['name'] == 'F1901M':
        # Find messages
        for msg in phase.get('messages', []):
            if msg['sender'] == 'TURKEY' and msg['recipient'] == 'AUSTRIA':
                if 'orders remain' in msg['message'].lower():
                    print(f"Found promise message:")
                    print(f"  From: {msg['sender']} to {msg['recipient']}")
                    print(f"  Message: {msg['message'][:200]}...")
                    
                    # Extract promise
                    pattern = r'orders remain (?:exactly )?as agreed:? a (\w{3})-(\w{3})'
                    match = re.search(pattern, msg['message'].lower())
                    if match:
                        print(f"  Promise found: A {match.group(1).upper()}-{match.group(2).upper()}")
        
        # Check actual orders
        turkey_orders = phase.get('orders', {}).get('TURKEY', [])
        print(f"\nTurkey's actual orders:")
        for order in turkey_orders:
            print(f"  {order}")
            
        # Check if promise was kept
        print("\nAnalysis:")
        if any('BUL - SER' in order or 'BUL-SER' in order for order in turkey_orders):
            print("  BETRAYAL DETECTED: Turkey ordered A BUL-SER instead of A CON-BUL")
        
        break

# Check another phase - S1908M Italy betrays Turkey
print("\n\nTesting known lie case: Italy S1908M")
print("=" * 50)

for phase in game_data['phases']:
    if phase['name'] == 'S1908M':
        # Find Italy-Turkey messages
        for msg in phase.get('messages', []):
            if msg['sender'] == 'ITALY' and msg['recipient'] == 'TURKEY':
                if 'support' in msg['message'].lower() and 'gal' in msg['message'].lower():
                    print(f"Found promise message:")
                    print(f"  From: {msg['sender']} to {msg['recipient']}")
                    print(f"  Message excerpt: {msg['message'][:300]}...")
        
        # Check Italy's actual orders
        italy_orders = phase.get('orders', {}).get('ITALY', [])
        print(f"\nItaly's actual orders:")
        for order in italy_orders:
            print(f"  {order}")
            if 'VIE' in order:
                print(f"    ^ This order from Vienna")
        
        print("\nAnalysis:")
        print("  Italy promised to support Turkey into Galicia")
        print("  Italy actually supported something else or held")
        
        break