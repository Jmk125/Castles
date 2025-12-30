import pygame
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# Initialize Pygame
pygame.init()

# Constants
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
TILE_SIZE = 16
FPS = 60
GRAVITY = 0.5
MAX_FALL_SPEED = 10

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 100, 100)
GREEN = (100, 255, 100)
BLUE = (100, 150, 255)

# Tile Properties (must match editor)
class TileProperty(Enum):
    SOLID = "solid"
    PLATFORM = "platform"
    BREAKABLE = "breakable"
    HAZARD = "hazard"
    BACKGROUND = "background"
    LADDER = "ladder"
    END_LEVEL = "end_level"

# Enemy AI Types
class EnemyAI(Enum):
    STATIONARY = "stationary"
    PATROL = "patrol"
    CHASE = "chase"
    FLYING = "flying"

# Collectible Types
class CollectibleEffect(Enum):
    HEALTH = "health"
    SCORE = "score"
    KEY = "key"
    POWERUP = "powerup"

@dataclass
class TileType:
    id: int
    name: str
    image_path: Optional[str]
    image: Optional[pygame.Surface]
    properties: List[str]
    color: Tuple[int, int, int]

@dataclass
class Tile:
    tile_type_id: int
    layer: str

@dataclass
class EnemyType:
    id: int
    name: str
    image_path: Optional[str]
    image: Optional[pygame.Surface]
    ai_type: str
    health: int
    damage: int
    speed: float
    color: Tuple[int, int, int]

@dataclass
class CollectibleType:
    id: int
    name: str
    image_path: Optional[str]
    image: Optional[pygame.Surface]
    effect: str
    value: int
    color: Tuple[int, int, int]
    required: bool = False

class Player:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.width = 14
        self.height = 28
        self.vel_x = 0
        self.vel_y = 0
        self.on_ground = False
        self.on_ladder = False
        self.climbing = False
        
        # Player stats
        self.speed = 3
        self.jump_strength = 10
        self.health = 100
        self.max_health = 100
        
        # Animation
        self.facing_right = True
        
    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)
    
    def update(self, keys, level):
        """Update player physics and movement"""
        # Horizontal movement
        self.vel_x = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.vel_x = -self.speed
            self.facing_right = False
            self.climbing = False
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.vel_x = self.speed
            self.facing_right = True
            self.climbing = False
        
        # Climbing
        if self.on_ladder:
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                self.climbing = True
                self.vel_y = -self.speed
            elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                self.climbing = True
                self.vel_y = self.speed
            else:
                if self.climbing:
                    self.vel_y = 0
        
        # Jumping
        if (keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]) and self.on_ground and not self.on_ladder:
            self.vel_y = -self.jump_strength
            self.on_ground = False
        
        # Apply gravity if not climbing
        if not self.climbing:
            self.vel_y += GRAVITY
            if self.vel_y > MAX_FALL_SPEED:
                self.vel_y = MAX_FALL_SPEED
        
        # Apply horizontal movement
        self.x += self.vel_x
        self.handle_horizontal_collisions(level)
        
        # Apply vertical movement
        self.y += self.vel_y
        self.handle_vertical_collisions(level)

        # Enforce level boundaries
        self.handle_level_boundaries(level)

        # Check for hazards
        self.check_hazards(level)
        
    def handle_horizontal_collisions(self, level):
        """Handle collisions in the X direction"""
        player_rect = self.get_rect()
        
        for (tile_x, tile_y), tile in level.get_solid_tiles():
            tile_rect = pygame.Rect(tile_x * TILE_SIZE, tile_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            
            if player_rect.colliderect(tile_rect):
                # Push player out
                if self.vel_x > 0:  # Moving right
                    self.x = tile_rect.left - self.width
                elif self.vel_x < 0:  # Moving left
                    self.x = tile_rect.right
                self.vel_x = 0
    
    def handle_vertical_collisions(self, level):
        """Handle collisions in the Y direction"""
        player_rect = self.get_rect()
        self.on_ground = False
        self.on_ladder = False
        
        # Check for ladders
        for (tile_x, tile_y), tile_type in level.get_ladder_tiles():
            tile_rect = pygame.Rect(tile_x * TILE_SIZE, tile_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            if player_rect.colliderect(tile_rect):
                self.on_ladder = True
        
        # Check solid tiles
        for (tile_x, tile_y), tile in level.get_solid_tiles():
            tile_rect = pygame.Rect(tile_x * TILE_SIZE, tile_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            
            if player_rect.colliderect(tile_rect):
                if self.vel_y > 0:  # Falling down
                    self.y = tile_rect.top - self.height
                    self.vel_y = 0
                    self.on_ground = True
                    self.climbing = False
                elif self.vel_y < 0:  # Moving up
                    self.y = tile_rect.bottom
                    self.vel_y = 0
        
        # Check platform tiles (only from above)
        for (tile_x, tile_y), tile in level.get_platform_tiles():
            tile_rect = pygame.Rect(tile_x * TILE_SIZE, tile_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            
            # Only collide if falling and player's bottom was above platform top last frame
            if player_rect.colliderect(tile_rect) and self.vel_y > 0:
                # Check if player's feet are within platform tolerance
                if player_rect.bottom <= tile_rect.top + 8:
                    self.y = tile_rect.top - self.height
                    self.vel_y = 0
                    self.on_ground = True
                    self.climbing = False
    
    def check_hazards(self, level):
        """Check if player is touching hazards"""
        player_rect = self.get_rect()

        for (tile_x, tile_y), tile in level.get_hazard_tiles():
            tile_rect = pygame.Rect(tile_x * TILE_SIZE, tile_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)

            if player_rect.colliderect(tile_rect):
                self.health -= 1  # Damage over time
                if self.health <= 0:
                    self.health = 0

    def handle_level_boundaries(self, level):
        """Prevent player from moving past level boundaries"""
        # Clamp horizontal position
        max_x = level.width * TILE_SIZE - self.width
        self.x = max(0, min(self.x, max_x))

        # Clamp vertical position
        max_y = level.height * TILE_SIZE - self.height
        self.y = max(0, min(self.y, max_y))

        # Stop velocity if hitting boundaries
        if self.x <= 0 or self.x >= max_x:
            self.vel_x = 0
        if self.y <= 0 or self.y >= max_y:
            self.vel_y = 0
    
    def draw(self, screen, camera_x, camera_y):
        """Draw the player"""
        draw_x = int(self.x - camera_x)
        draw_y = int(self.y - camera_y)
        
        # Draw simple rectangle for now (can be replaced with sprite later)
        pygame.draw.rect(screen, RED, (draw_x, draw_y, self.width, self.height))

        # Draw direction indicator
        if self.facing_right:
            pygame.draw.rect(screen, WHITE, (draw_x + self.width - 3, draw_y + 5, 3, 3))
        else:
            pygame.draw.rect(screen, WHITE, (draw_x, draw_y + 5, 3, 3))

class Enemy:
    def __init__(self, x: int, y: int, enemy_type: EnemyType, patrol_range: int = 100):
        self.x = float(x)
        self.y = float(y)
        self.enemy_type = enemy_type
        self.patrol_range = patrol_range
        self.width = TILE_SIZE
        self.height = TILE_SIZE
        self.health = enemy_type.health
        self.vel_x = 0
        self.vel_y = 0
        self.direction = 1  # 1 for right, -1 for left
        self.start_x = x  # For patrol AI
        self.alive = True

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def update(self, player, level):
        """Update enemy AI and physics"""
        if not self.alive:
            return

        # AI behavior based on type
        if self.enemy_type.ai_type == EnemyAI.STATIONARY.value:
            # Don't move
            pass

        elif self.enemy_type.ai_type == EnemyAI.PATROL.value:
            # Move back and forth within patrol range
            self.vel_x = self.enemy_type.speed * self.direction

            # Check if reached patrol boundary
            if self.x >= self.start_x + self.patrol_range:
                self.direction = -1
            elif self.x <= self.start_x - self.patrol_range:
                self.direction = 1

            # Apply horizontal movement
            self.x += self.vel_x

            # Apply gravity if not flying
            self.vel_y += GRAVITY
            if self.vel_y > MAX_FALL_SPEED:
                self.vel_y = MAX_FALL_SPEED

            self.y += self.vel_y

            # Simple ground collision (enemies don't need full collision like player)
            for (tile_x, tile_y), tile in level.get_solid_tiles():
                tile_rect = pygame.Rect(tile_x * TILE_SIZE, tile_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                enemy_rect = self.get_rect()

                if enemy_rect.colliderect(tile_rect):
                    if self.vel_y > 0:  # Falling
                        self.y = tile_rect.top - self.height
                        self.vel_y = 0

        elif self.enemy_type.ai_type == EnemyAI.CHASE.value:
            # Move towards player
            dx = player.x - self.x
            dy = player.y - self.y
            distance = (dx**2 + dy**2) ** 0.5

            if distance > 0:
                self.vel_x = (dx / distance) * self.enemy_type.speed
                self.vel_y = (dy / distance) * self.enemy_type.speed
                self.x += self.vel_x
                self.y += self.vel_y

        elif self.enemy_type.ai_type == EnemyAI.FLYING.value:
            # Flying chase - similar to chase but with vertical movement
            dx = player.x - self.x
            dy = player.y - self.y
            distance = (dx**2 + dy**2) ** 0.5

            if distance > 0 and distance < 300:  # Only chase if within range
                self.vel_x = (dx / distance) * self.enemy_type.speed
                self.vel_y = (dy / distance) * self.enemy_type.speed
                self.x += self.vel_x
                self.y += self.vel_y

    def take_damage(self, amount: int):
        """Take damage and check if dead"""
        self.health -= amount
        if self.health <= 0:
            self.alive = False

    def draw(self, screen, camera_x, camera_y):
        """Draw the enemy"""
        if not self.alive:
            return

        draw_x = int(self.x - camera_x)
        draw_y = int(self.y - camera_y)

        if self.enemy_type.image:
            screen.blit(self.enemy_type.image, (draw_x, draw_y))
        else:
            pygame.draw.rect(screen, self.enemy_type.color, (draw_x, draw_y, self.width, self.height))

        # Draw health bar for enemies with finite health
        if self.enemy_type.health < 999:
            bar_width = TILE_SIZE
            bar_height = 3
            health_ratio = self.health / self.enemy_type.health
            pygame.draw.rect(screen, RED, (draw_x, draw_y - 5, bar_width, bar_height))
            pygame.draw.rect(screen, GREEN, (draw_x, draw_y - 5, int(bar_width * health_ratio), bar_height))

class Collectible:
    def __init__(self, x: int, y: int, collectible_type: CollectibleType):
        self.x = x
        self.y = y
        self.collectible_type = collectible_type
        self.width = TILE_SIZE
        self.height = TILE_SIZE
        self.collected = False

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def draw(self, screen, camera_x, camera_y):
        """Draw the collectible"""
        if self.collected:
            return

        draw_x = int(self.x - camera_x)
        draw_y = int(self.y - camera_y)

        if self.collectible_type.image:
            screen.blit(self.collectible_type.image, (draw_x, draw_y))
        else:
            # Draw as a circle
            center_x = draw_x + self.width // 2
            center_y = draw_y + self.height // 2
            pygame.draw.circle(screen, self.collectible_type.color, (center_x, center_y), TILE_SIZE // 2)

class Level:
    def __init__(self, filename: str):
        self.filename = filename
        self.width = 0
        self.height = 0
        self.tile_types: Dict[int, TileType] = {}
        self.tiles: Dict[str, Dict[Tuple[int, int], Tile]] = {
            'background': {},
            'main': {},
            'foreground': {}
        }
        self.enemy_types: Dict[int, EnemyType] = {}
        self.enemies: List[Enemy] = []
        self.collectible_types: Dict[int, CollectibleType] = {}
        self.collectibles: List[Collectible] = []
        self.score = 0
        self.keys_collected = 0
        self.required_collectibles_total = 0
        self.required_collectibles_collected = 0
        self.load_level(filename)
    
    def load_level(self, filename: str):
        """Load level from JSON file"""
        with open(filename, 'r') as f:
            data = json.load(f)

        self.width = data['width']
        self.height = data['height']

        # Load tile types
        for tid_str, ttype_data in data['tile_types'].items():
            tid = int(tid_str)
            image = None
            if ttype_data['image_path'] and os.path.exists(ttype_data['image_path']):
                try:
                    image = pygame.image.load(ttype_data['image_path'])
                    image = pygame.transform.scale(image, (TILE_SIZE, TILE_SIZE))
                except:
                    pass

            self.tile_types[tid] = TileType(
                id=tid,
                name=ttype_data['name'],
                image_path=ttype_data['image_path'],
                image=image,
                properties=ttype_data['properties'],
                color=tuple(ttype_data['color'])
            )

        # Load tiles
        for layer, tiles_data in data['layers'].items():
            for pos_str, tile_data in tiles_data.items():
                x, y = map(int, pos_str.split(','))
                self.tiles[layer][(x, y)] = Tile(
                    tile_type_id=tile_data['tile_type_id'],
                    layer=tile_data['layer']
                )

        # Load enemy types
        if 'enemy_types' in data:
            for eid_str, etype_data in data['enemy_types'].items():
                eid = int(eid_str)
                image = None
                if etype_data['image_path'] and os.path.exists(etype_data['image_path']):
                    try:
                        image = pygame.image.load(etype_data['image_path'])
                        image = pygame.transform.scale(image, (TILE_SIZE, TILE_SIZE))
                    except:
                        pass

                self.enemy_types[eid] = EnemyType(
                    id=eid,
                    name=etype_data['name'],
                    image_path=etype_data['image_path'],
                    image=image,
                    ai_type=etype_data['ai_type'],
                    health=etype_data['health'],
                    damage=etype_data['damage'],
                    speed=etype_data['speed'],
                    color=tuple(etype_data['color'])
                )

        # Load enemies
        if 'enemies' in data:
            for enemy_data in data['enemies']:
                enemy_type = self.enemy_types.get(enemy_data['enemy_type_id'])
                if enemy_type:
                    enemy = Enemy(
                        x=enemy_data['x'],
                        y=enemy_data['y'],
                        enemy_type=enemy_type,
                        patrol_range=enemy_data.get('patrol_range', 100)
                    )
                    self.enemies.append(enemy)

        # Load collectible types
        if 'collectible_types' in data:
            for cid_str, ctype_data in data['collectible_types'].items():
                cid = int(cid_str)
                image = None
                if ctype_data['image_path'] and os.path.exists(ctype_data['image_path']):
                    try:
                        image = pygame.image.load(ctype_data['image_path'])
                        image = pygame.transform.scale(image, (TILE_SIZE, TILE_SIZE))
                    except:
                        pass

                self.collectible_types[cid] = CollectibleType(
                    id=cid,
                    name=ctype_data['name'],
                    image_path=ctype_data['image_path'],
                    image=image,
                    effect=ctype_data['effect'],
                    value=ctype_data['value'],
                    color=tuple(ctype_data['color']),
                    required=ctype_data.get('required', False)
                )

        # Load collectibles
        if 'collectibles' in data:
            for collectible_data in data['collectibles']:
                collectible_type = self.collectible_types.get(collectible_data['collectible_type_id'])
                if collectible_type:
                    collectible = Collectible(
                        x=collectible_data['x'],
                        y=collectible_data['y'],
                        collectible_type=collectible_type
                    )
                    self.collectibles.append(collectible)
                    # Count required collectibles
                    if collectible_type.required:
                        self.required_collectibles_total += 1
    
    def get_solid_tiles(self):
        """Get all tiles with solid property"""
        solid_tiles = []
        for layer in ['background', 'main', 'foreground']:
            for (tile_x, tile_y), tile in self.tiles[layer].items():
                tile_type = self.tile_types.get(tile.tile_type_id)
                if tile_type and TileProperty.SOLID.value in tile_type.properties:
                    solid_tiles.append(((tile_x, tile_y), tile))
        return solid_tiles
    
    def get_platform_tiles(self):
        """Get all tiles with platform property"""
        platform_tiles = []
        for layer in ['background', 'main', 'foreground']:
            for (tile_x, tile_y), tile in self.tiles[layer].items():
                tile_type = self.tile_types.get(tile.tile_type_id)
                if tile_type and TileProperty.PLATFORM.value in tile_type.properties:
                    platform_tiles.append(((tile_x, tile_y), tile))
        return platform_tiles
    
    def get_hazard_tiles(self):
        """Get all tiles with hazard property"""
        hazard_tiles = []
        for layer in ['background', 'main', 'foreground']:
            for (tile_x, tile_y), tile in self.tiles[layer].items():
                tile_type = self.tile_types.get(tile.tile_type_id)
                if tile_type and TileProperty.HAZARD.value in tile_type.properties:
                    hazard_tiles.append(((tile_x, tile_y), tile))
        return hazard_tiles

    def get_end_level_tiles(self):
        """Get all tiles with end_level property"""
        end_level_tiles = []
        for layer in ['background', 'main', 'foreground']:
            for (tile_x, tile_y), tile in self.tiles[layer].items():
                tile_type = self.tile_types.get(tile.tile_type_id)
                if tile_type and TileProperty.END_LEVEL.value in tile_type.properties:
                    end_level_tiles.append(((tile_x, tile_y), tile))
        return end_level_tiles

    def all_required_collectibles_collected(self):
        """Check if all required collectibles have been collected"""
        return self.required_collectibles_collected >= self.required_collectibles_total

    def get_ladder_tiles(self):
        """Get all tiles with ladder property"""
        ladder_tiles = []
        for layer in ['background', 'main', 'foreground']:
            for (tile_x, tile_y), tile in self.tiles[layer].items():
                tile_type = self.tile_types.get(tile.tile_type_id)
                if tile_type and TileProperty.LADDER.value in tile_type.properties:
                    ladder_tiles.append(((tile_x, tile_y), tile_type))
        return ladder_tiles
    
    def draw(self, screen, camera_x, camera_y):
        """Draw the level"""
        # Draw tiles
        for layer in ['background', 'main', 'foreground']:
            for (tile_x, tile_y), tile in self.tiles[layer].items():
                screen_x = tile_x * TILE_SIZE - camera_x
                screen_y = tile_y * TILE_SIZE - camera_y

                # Only draw if visible
                if -TILE_SIZE < screen_x < SCREEN_WIDTH and -TILE_SIZE < screen_y < SCREEN_HEIGHT:
                    tile_type = self.tile_types.get(tile.tile_type_id)
                    if tile_type:
                        # Only show END_LEVEL tiles when all required collectibles are collected
                        if TileProperty.END_LEVEL.value in tile_type.properties:
                            if not self.all_required_collectibles_collected():
                                continue  # Skip drawing END_LEVEL tile

                        if tile_type.image:
                            screen.blit(tile_type.image, (screen_x, screen_y))
                        else:
                            pygame.draw.rect(screen, tile_type.color,
                                           (screen_x, screen_y, TILE_SIZE, TILE_SIZE))

        # Draw collectibles
        for collectible in self.collectibles:
            collectible.draw(screen, camera_x, camera_y)

        # Draw enemies
        for enemy in self.enemies:
            enemy.draw(screen, camera_x, camera_y)

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Castlevania Game")
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Load levels
        self.levels = self.load_all_levels()
        self.current_level_index = 0
        
        if not self.levels:
            print("No level files found! Please create a level first.")
            self.running = False
            return
        
        self.level = self.levels[self.current_level_index]
        
        # Create player at spawn point (for now, just start at a safe location)
        self.player = Player(100, 100)
        
        # Camera
        self.camera_x = 0
        self.camera_y = 0

        # Game state
        self.game_over = False

        # Font for UI
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
        self.large_font = pygame.font.Font(None, 48)
    
    def load_all_levels(self):
        """Load all level JSON files from current directory"""
        levels = []
        level_files = sorted(Path('.').glob('level*.json'))
        
        for filepath in level_files:
            try:
                level = Level(str(filepath))
                levels.append(level)
                print(f"Loaded level: {filepath}")
            except Exception as e:
                print(f"Error loading {filepath}: {e}")
        
        return levels
    
    def update_camera(self):
        """Update camera to follow player"""
        # Center camera on player
        target_x = self.player.x + self.player.width // 2 - SCREEN_WIDTH // 2
        target_y = self.player.y + self.player.height // 2 - SCREEN_HEIGHT // 2

        # Clamp camera to level bounds
        max_camera_x = max(0, self.level.width * TILE_SIZE - SCREEN_WIDTH)
        max_camera_y = max(0, self.level.height * TILE_SIZE - SCREEN_HEIGHT)

        self.camera_x = max(0, min(target_x, max_camera_x))
        self.camera_y = max(0, min(target_y, max_camera_y))

    def check_enemy_collisions(self):
        """Check for player-enemy collisions"""
        player_rect = self.player.get_rect()

        for enemy in self.level.enemies:
            if not enemy.alive:
                continue

            enemy_rect = enemy.get_rect()
            if player_rect.colliderect(enemy_rect):
                # Player takes damage
                self.player.health -= enemy.enemy_type.damage
                if self.player.health < 0:
                    self.player.health = 0

                # Knockback player
                dx = self.player.x - enemy.x
                if dx > 0:
                    self.player.x += 10  # Push right
                else:
                    self.player.x -= 10  # Push left

    def check_collectible_collisions(self):
        """Check for player-collectible collisions"""
        player_rect = self.player.get_rect()

        for collectible in self.level.collectibles:
            if collectible.collected:
                continue

            collectible_rect = collectible.get_rect()
            if player_rect.colliderect(collectible_rect):
                collectible.collected = True

                # Track required collectibles
                if collectible.collectible_type.required:
                    self.level.required_collectibles_collected += 1

                # Apply collectible effect
                if collectible.collectible_type.effect == CollectibleEffect.HEALTH.value:
                    self.player.health = min(self.player.max_health,
                                            self.player.health + collectible.collectible_type.value)
                elif collectible.collectible_type.effect == CollectibleEffect.SCORE.value:
                    self.level.score += collectible.collectible_type.value
                elif collectible.collectible_type.effect == CollectibleEffect.KEY.value:
                    self.level.keys_collected += collectible.collectible_type.value
                elif collectible.collectible_type.effect == CollectibleEffect.POWERUP.value:
                    # Could implement powerups later
                    pass

    def check_end_level_collision(self):
        """Check if player touches END_LEVEL tile when requirements are met"""
        # Only check if all required collectibles are collected
        if not self.level.all_required_collectibles_collected():
            return False

        player_rect = self.player.get_rect()
        end_level_tiles = self.level.get_end_level_tiles()

        for (tile_x, tile_y), tile in end_level_tiles:
            tile_rect = pygame.Rect(tile_x * TILE_SIZE, tile_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            if player_rect.colliderect(tile_rect):
                return True

        return False

    def advance_level(self):
        """Advance to the next level or restart current level"""
        # For now, just restart the current level
        # In the future, this could load a different level file
        print("Level complete! Restarting level...")
        self.level = Level(self.level.filename)
        self.player.x = 100
        self.player.y = 100
        self.player.health = self.player.max_health

    def check_player_death(self):
        """Check if player is dead"""
        if self.player.health <= 0:
            self.game_over = True

    def draw_game_over(self):
        """Draw game over screen"""
        # Semi-transparent overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        # Game Over text
        game_over_text = self.large_font.render("GAME OVER", True, RED)
        text_rect = game_over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
        self.screen.blit(game_over_text, text_rect)

        # Instructions
        restart_text = self.font.render("Press R to Restart", True, WHITE)
        restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
        self.screen.blit(restart_text, restart_rect)

        quit_text = self.font.render("Press ESC to Quit", True, WHITE)
        quit_rect = quit_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50))
        self.screen.blit(quit_text, quit_rect)

    def draw_ui(self):
        """Draw UI elements"""
        # Health bar
        bar_width = 200
        bar_height = 20
        bar_x = 10
        bar_y = 10
        
        # Background
        pygame.draw.rect(self.screen, BLACK, (bar_x, bar_y, bar_width, bar_height))
        
        # Health
        health_width = int((self.player.health / self.player.max_health) * bar_width)
        pygame.draw.rect(self.screen, RED, (bar_x, bar_y, health_width, bar_height))
        
        # Border
        pygame.draw.rect(self.screen, WHITE, (bar_x, bar_y, bar_width, bar_height), 2)
        
        # Health text
        health_text = self.small_font.render(f"HP: {self.player.health}/{self.player.max_health}", True, WHITE)
        self.screen.blit(health_text, (bar_x + 5, bar_y + 2))
        
        # Level info
        level_text = self.font.render(f"Level {self.current_level_index + 1}/{len(self.levels)}", True, WHITE)
        self.screen.blit(level_text, (SCREEN_WIDTH - 150, 10))

        # Score
        score_text = self.font.render(f"Score: {self.level.score}", True, WHITE)
        self.screen.blit(score_text, (SCREEN_WIDTH - 150, 40))

        # Keys
        keys_text = self.font.render(f"Keys: {self.level.keys_collected}", True, WHITE)
        self.screen.blit(keys_text, (SCREEN_WIDTH - 150, 70))
        
        # Controls hint
        controls = [
            "Arrow Keys/WASD: Move",
            "Space/Up: Jump",
            "R: Restart Level",
            "N: Next Level",
            "ESC: Quit"
        ]
        y = SCREEN_HEIGHT - len(controls) * 20 - 10
        for control in controls:
            text = self.small_font.render(control, True, WHITE)
            self.screen.blit(text, (10, y))
            y += 20
    
    def next_level(self):
        """Load next level"""
        if self.current_level_index < len(self.levels) - 1:
            self.current_level_index += 1
            self.level = self.levels[self.current_level_index]
            self.player = Player(100, 100)
            print(f"Level {self.current_level_index + 1} loaded")
        else:
            print("No more levels!")
    
    def restart_level(self):
        """Restart current level"""
        # Reload the current level
        self.level = Level(self.level.filename)
        self.player = Player(100, 100)
        self.game_over = False
        print("Level restarted")
    
    def handle_events(self):
        """Handle input events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_r:
                    self.restart_level()
                elif event.key == pygame.K_n:
                    self.next_level()
    
    def run(self):
        """Main game loop"""
        while self.running:
            self.handle_events()

            if not self.game_over:
                # Get input
                keys = pygame.key.get_pressed()

                # Update
                self.player.update(keys, self.level)

                # Update enemies
                for enemy in self.level.enemies:
                    enemy.update(self.player, self.level)

                # Check collisions
                self.check_enemy_collisions()
                self.check_collectible_collisions()

                # Check if player is dead
                self.check_player_death()

                # Check if player completed the level
                if self.check_end_level_collision():
                    self.advance_level()

                self.update_camera()

            # Draw
            self.screen.fill(BLACK)
            self.level.draw(self.screen, self.camera_x, self.camera_y)
            self.player.draw(self.screen, self.camera_x, self.camera_y)
            self.draw_ui()

            # Draw game over screen if player is dead
            if self.game_over:
                self.draw_game_over()

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()

if __name__ == "__main__":
    game = Game()
    game.run()
