"""
Example: Enemy that moves in a sine wave pattern

This is a simpler example showing horizontal movement with vertical sine wave motion.
Perfect for flying enemies or boss patterns!
"""

import math


def update(enemy, player, level):
    """
    Enemy moves horizontally while bobbing up and down in a sine wave pattern

    Args:
        enemy: The enemy instance
        player: The player instance
        level: The level instance

    Returns:
        List of projectiles (empty in this case)
    """
    # Initialize a counter if it doesn't exist (used for sine wave)
    if not hasattr(enemy, 'wave_counter'):
        enemy.wave_counter = 0

    # Move horizontally
    enemy.vel_x = enemy.enemy_type.speed * enemy.direction

    # Reverse direction at boundaries or when hitting walls
    level_width = level.width * 16  # TILE_SIZE = 16
    if enemy.x <= 50 or enemy.x >= level_width - 50:
        enemy.direction *= -1

    # Calculate sine wave motion for vertical movement
    enemy.wave_counter += 0.1
    wave_amplitude = 30  # How far up/down to move
    wave_frequency = 0.1  # How fast to oscillate

    # Set vertical velocity based on sine wave
    enemy.vel_y = math.sin(enemy.wave_counter) * 2

    # Apply movement
    enemy.x += enemy.vel_x
    enemy.y += enemy.vel_y

    # No projectiles in this simple example
    return []
