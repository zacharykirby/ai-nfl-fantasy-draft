def snake_picks(pos, size=8):
    """Calculate snake draft picks for a given position"""
    picks = []
    for round_num in range(1, 16):  # 15 rounds
        if round_num % 2 == 1:  # Odd rounds (1, 3, 5, etc.)
            pick = pos
        else:  # Even rounds (2, 4, 6, etc.)
            pick = size - pos + 1
        picks.append(pick)
    return picks

print("🐍 SNAKE DRAFT PICK CALCULATIONS")
print("="*50)

# Show examples for different positions
positions = [1, 4, 8]
for pos in positions:
    picks = snake_picks(pos)
    print(f"\nPosition {pos}: {picks}")
    print(f"Rounds 1-8: {picks[:8]}")

print("\n📋 DETAILED BREAKDOWN:")
print("="*50)

# Show the full draft order for position 4
pos = 4
picks = snake_picks(pos)
print(f"\nPosition {pos} Draft Order:")
for i, pick in enumerate(picks[:8], 1):
    print(f"Round {i}: Pick {pick}") 