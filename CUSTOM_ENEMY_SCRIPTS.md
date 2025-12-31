# Custom Enemy Behavior Scripts

Custom enemy behavior scripts allow you to create unique enemy behaviors by writing Python code. This gives you complete control over how an enemy moves, attacks, and interacts with the player.

## Quick Start

1. **Create a Python script** with an `update` function
2. **Link the script** to an enemy in the tile editor (drag-and-drop or use "Select File")
3. **The script takes full control** of that enemy's behavior

## Script API

Your script must define an `update` function with this signature:

```python
def update(enemy, player, level):
    """
    Args:
        enemy: The Enemy instance you're controlling
        player: The Player instance
        level: The Level instance

    Returns:
        List of Projectile objects to spawn (or empty list/None)
    """
    # Your code here
    return []
```

## Available Enemy Properties

You can read and modify these enemy properties:

### Position & Movement
- `enemy.x` - X position (float)
- `enemy.y` - Y position (float)
- `enemy.vel_x` - X velocity (float)
- `enemy.vel_y` - Y velocity (float)
- `enemy.width` - Enemy width (default: 16)
- `enemy.height` - Enemy height (default: 16)

### Enemy State
- `enemy.health` - Current health (int)
- `enemy.alive` - Is enemy alive (bool)
- `enemy.direction` - Direction: 1=right, -1=left (int)
- `enemy.start_x` - Original spawn X position (float)

### Enemy Type Properties (read-only)
- `enemy.enemy_type.speed` - Movement speed
- `enemy.enemy_type.damage` - Contact damage to player
- `enemy.enemy_type.health` - Max health
- `enemy.enemy_type.projectile_speed` - Projectile speed
- `enemy.enemy_type.projectile_damage` - Projectile damage

### Custom Properties
You can add your own properties to track state:
```python
if not hasattr(enemy, 'my_counter'):
    enemy.my_counter = 0
enemy.my_counter += 1
```

## Available Player Properties

Access player information:

- `player.x`, `player.y` - Player position
- `player.width`, `player.height` - Player size (14x28)
- `player.vel_x`, `player.vel_y` - Player velocity
- `player.health` - Player health
- `player.facing_right` - Direction player is facing (bool)

## Available Level Properties

Access level information:

- `level.width`, `level.height` - Level dimensions in tiles
- `level.get_solid_tiles()` - Get solid tiles for collision detection
- `level.projectiles` - List of active projectiles

## Creating Projectiles

To make the enemy shoot, import and create Projectile objects:

```python
from game import Projectile

def update(enemy, player, level):
    new_projectiles = []

    # Create a projectile aimed at the player
    projectile = Projectile(
        x=enemy.x + enemy.width / 2,
        y=enemy.y + enemy.height / 2,
        target_x=player.x + player.width / 2,
        target_y=player.y + player.height / 2,
        speed=4.0,
        damage=10
    )
    new_projectiles.append(projectile)

    return new_projectiles
```

## Example Behaviors

### Example 1: Chase Player
```python
import math

def update(enemy, player, level):
    # Calculate direction to player
    dx = player.x - enemy.x
    dy = player.y - enemy.y
    distance = math.sqrt(dx**2 + dy**2)

    if distance > 0:
        # Move towards player
        enemy.vel_x = (dx / distance) * enemy.enemy_type.speed
        enemy.vel_y = (dy / distance) * enemy.enemy_type.speed
        enemy.x += enemy.vel_x
        enemy.y += enemy.vel_y

    return []
```

### Example 2: Patrol with Shooting
```python
from game import Projectile

def update(enemy, player, level):
    new_projectiles = []

    # Patrol back and forth
    enemy.vel_x = enemy.enemy_type.speed * enemy.direction
    enemy.x += enemy.vel_x

    # Reverse at patrol boundaries
    if enemy.x >= enemy.start_x + 100:
        enemy.direction = -1
    elif enemy.x <= enemy.start_x - 100:
        enemy.direction = 1

    # Shoot timer
    if not hasattr(enemy, 'shoot_timer'):
        enemy.shoot_timer = 0

    if enemy.shoot_timer > 0:
        enemy.shoot_timer -= 1
    else:
        # Shoot at player
        dx = player.x - enemy.x
        dy = player.y - enemy.y
        distance = math.sqrt(dx**2 + dy**2)

        if distance < 200:
            projectile = Projectile(
                x=enemy.x + enemy.width / 2,
                y=enemy.y + enemy.height / 2,
                target_x=player.x,
                target_y=player.y,
                speed=3.0,
                damage=5
            )
            new_projectiles.append(projectile)
            enemy.shoot_timer = 60  # Cooldown frames

    return new_projectiles
```

### Example 3: Teleporting Enemy
```python
import random

def update(enemy, player, level):
    # Initialize teleport timer
    if not hasattr(enemy, 'teleport_timer'):
        enemy.teleport_timer = 120

    enemy.teleport_timer -= 1

    # Teleport near player every 2 seconds
    if enemy.teleport_timer <= 0:
        # Random position near player
        offset_x = random.randint(-100, 100)
        offset_y = random.randint(-100, 100)
        enemy.x = player.x + offset_x
        enemy.y = player.y + offset_y
        enemy.teleport_timer = 120

    return []
```

## Tips

1. **Use math module** for advanced movement patterns (sine waves, circles, etc.)
2. **Add custom properties** to track state between frames (counters, timers, etc.)
3. **Handle edge cases** - check if enemy is off-screen or out of bounds
4. **Test incrementally** - start simple and add complexity gradually
5. **Return empty list** if not spawning projectiles: `return []`

## Common Patterns

### Distance to Player
```python
import math
dx = player.x - enemy.x
dy = player.y - enemy.y
distance = math.sqrt(dx**2 + dy**2)
```

### Angle to Player
```python
import math
angle = math.atan2(player.y - enemy.y, player.x - enemy.x)
```

### Cooldown Timer
```python
if not hasattr(enemy, 'action_timer'):
    enemy.action_timer = 0

if enemy.action_timer > 0:
    enemy.action_timer -= 1
else:
    # Do action
    enemy.action_timer = 60  # Reset cooldown
```

## Full Examples

See these example scripts:
- `example_enemy_behavior.py` - Circling enemy that shoots
- `example_sinewave_enemy.py` - Sine wave movement pattern

## Error Handling

If your script has an error, the game will:
1. Print the error message to console
2. Fall back to default AI behavior (based on ai_type)
3. Continue running

Check the console output for debugging information.
