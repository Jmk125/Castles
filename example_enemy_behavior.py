"""
Example custom enemy behavior script for Castles

This script demonstrates how to create custom enemy behaviors.
Your script must define an `update` function that takes three parameters:
- enemy: The Enemy instance (access enemy.x, enemy.y, enemy.vel_x, enemy.vel_y, etc.)
- player: The Player instance (access player.x, player.y, etc.)
- level: The Level instance

The function should return a list of Projectile objects (or empty list/None).

You have full control over the enemy's movement, attacks, and behavior!
"""

import math


def update(enemy, player, level):
    """
    Example: Enemy circles around the player while shooting occasionally

    Args:
        enemy: The enemy instance (modify enemy.x, enemy.y, enemy.vel_x, enemy.vel_y)
        player: The player instance
        level: The level instance

    Returns:
        List of projectiles to spawn (or empty list/None)
    """
    new_projectiles = []

    # Calculate distance and angle to player
    dx = player.x - enemy.x
    dy = player.y - enemy.y
    distance = math.sqrt(dx**2 + dy**2)

    # Circle around the player at a distance of 150 pixels
    target_distance = 150

    if distance > 0:
        # Calculate angle to player
        angle = math.atan2(dy, dx)

        # Add perpendicular component to create circular motion
        circle_angle = angle + math.pi / 2

        # Move towards/away from player to maintain target distance
        if distance > target_distance:
            # Move closer to player
            enemy.vel_x = (dx / distance) * enemy.enemy_type.speed
            enemy.vel_y = (dy / distance) * enemy.enemy_type.speed
        elif distance < target_distance - 20:
            # Move away from player
            enemy.vel_x = -(dx / distance) * enemy.enemy_type.speed
            enemy.vel_y = -(dy / distance) * enemy.enemy_type.speed
        else:
            # Circle around player
            enemy.vel_x = math.cos(circle_angle) * enemy.enemy_type.speed
            enemy.vel_y = math.sin(circle_angle) * enemy.enemy_type.speed

        # Apply movement
        enemy.x += enemy.vel_x
        enemy.y += enemy.vel_y

        # Shoot at player periodically
        if hasattr(enemy, 'shoot_timer'):
            if enemy.shoot_timer > 0:
                enemy.shoot_timer -= 1

            # Shoot if in range and timer is ready
            if distance <= 300 and enemy.shoot_timer <= 0:
                # Import Projectile class (available from game.py)
                from game import Projectile

                projectile_x = enemy.x + enemy.width / 2
                projectile_y = enemy.y + enemy.height / 2
                target_x = player.x + player.width / 2
                target_y = player.y + player.height / 2

                projectile = Projectile(
                    x=projectile_x,
                    y=projectile_y,
                    target_x=target_x,
                    target_y=target_y,
                    speed=enemy.enemy_type.projectile_speed,
                    damage=enemy.enemy_type.projectile_damage
                )
                new_projectiles.append(projectile)

                # Reset shoot timer
                enemy.shoot_timer = enemy.shoot_cooldown

    return new_projectiles
