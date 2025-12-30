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
CAMERA_PLAYER_VERTICAL_FRACTION = 0.9

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

# Game States
class GameState(Enum):
    TITLE = "title"
    PLAYING = "playing"
    GAME_OVER = "game_over"
    HIGH_SCORES = "high_scores"

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
    required: bool = False

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

@dataclass
class BackgroundImage:
    layer_index: int  # 0-3 (0 = far background, 3 = closest)
    image_path: str
    image: Optional[pygame.Surface]
    x: int
    y: int
    width: int
    height: int
    repeat_x: bool
    repeat_y: bool
    parallax_factor: float

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

        # Attack
        self.attacking = False
        self.attack_timer = 0
        self.attack_duration = 10  # frames
        self.attack_cooldown = 20  # frames
        self.attack_cooldown_timer = 0
        self.attack_damage = 25
        self.attack_range = 35

        # Animation
        self.facing_right = True
        
    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def get_attack_rect(self) -> pygame.Rect:
        """Get the hitbox for the sword swing"""
        if not self.attacking:
            return pygame.Rect(0, 0, 0, 0)

        if self.facing_right:
            # Attack in front of player
            return pygame.Rect(
                int(self.x + self.width),
                int(self.y),
                self.attack_range,
                self.height
            )
        else:
            # Attack to the left
            return pygame.Rect(
                int(self.x - self.attack_range),
                int(self.y),
                self.attack_range,
                self.height
            )

    def start_attack(self):
        """Start an attack if not on cooldown"""
        if self.attack_cooldown_timer <= 0 and not self.attacking:
            self.attacking = True
            self.attack_timer = self.attack_duration

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
        
        # Jumping (removed spacebar - now used for attack)
        if (keys[pygame.K_UP] or keys[pygame.K_w]) and self.on_ground and not self.on_ladder:
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

        # Update attack timers
        if self.attacking:
            self.attack_timer -= 1
            if self.attack_timer <= 0:
                self.attacking = False
                self.attack_cooldown_timer = self.attack_cooldown

        if self.attack_cooldown_timer > 0:
            self.attack_cooldown_timer -= 1

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
        """Prevent player from moving past level boundaries (except bottom - allow falling to death)"""
        # Clamp horizontal position
        max_x = level.width * TILE_SIZE - self.width
        self.x = max(0, min(self.x, max_x))

        # Only clamp top boundary (allow falling off bottom for death)
        if self.y < 0:
            self.y = 0
            self.vel_y = 0

        # Stop velocity if hitting side boundaries
        if self.x <= 0 or self.x >= max_x:
            self.vel_x = 0
    
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

        # Draw sword swing if attacking
        if self.attacking:
            attack_rect = self.get_attack_rect()
            sword_draw_x = int(attack_rect.x - camera_x)
            sword_draw_y = int(attack_rect.y - camera_y)

            # Draw sword as a semi-transparent yellow rectangle
            sword_surface = pygame.Surface((attack_rect.width, attack_rect.height))
            sword_surface.set_alpha(150)
            sword_surface.fill((255, 255, 100))  # Yellow
            screen.blit(sword_surface, (sword_draw_x, sword_draw_y))

            # Draw sword outline
            pygame.draw.rect(screen, (255, 255, 0),
                           (sword_draw_x, sword_draw_y, attack_rect.width, attack_rect.height), 2)

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
        self.required_enemies_total = 0
        self.required_enemies_killed = 0
        # Background image (legacy - for backwards compatibility)
        self.background_image: Optional[pygame.Surface] = None
        self.background_x = 0
        self.background_y = 0
        self.background_width = 0
        self.background_height = 0
        # Background layers (new parallax system)
        self.background_layers: List[BackgroundImage] = []
        # Viewport settings (camera starting position and zoom)
        self.viewport_x = 0
        self.viewport_y = 0
        self.viewport_width = SCREEN_WIDTH
        self.viewport_height = SCREEN_HEIGHT
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
                    color=tuple(etype_data['color']),
                    required=etype_data.get('required', False)
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
                    # Count required enemies
                    if enemy_type.required:
                        self.required_enemies_total += 1

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

        # Load background image (legacy - for backwards compatibility)
        if 'background' in data and data['background']:
            bg_data = data['background']
            image_path = bg_data.get('image_path')
            self.background_x = bg_data.get('x', 0)
            self.background_y = bg_data.get('y', 0)
            self.background_width = bg_data.get('width', 0)
            self.background_height = bg_data.get('height', 0)

            if image_path and os.path.exists(image_path):
                try:
                    self.background_image = pygame.image.load(image_path)
                except Exception as e:
                    print(f"Error loading background image: {e}")
                    self.background_image = None

        # Load background layers (new parallax system)
        if 'background_layers' in data:
            for bg_data in data['background_layers']:
                try:
                    image_path = bg_data['image_path']
                    image = None
                    if image_path and os.path.exists(image_path):
                        image = pygame.image.load(image_path)

                    layer_idx = bg_data['layer_index']
                    default_parallax = 0.1 + (layer_idx * 0.2)
                    bg_img = BackgroundImage(
                        layer_index=layer_idx,
                        image_path=image_path,
                        image=image,
                        x=bg_data['x'],
                        y=bg_data['y'],
                        width=bg_data['width'],
                        height=bg_data['height'],
                        repeat_x=bg_data.get('repeat_x', False),
                        repeat_y=bg_data.get('repeat_y', False),
                        parallax_factor=bg_data.get('parallax_factor', default_parallax)
                    )
                    self.background_layers.append(bg_img)
                except Exception as e:
                    print(f"Error loading background layer: {e}")

        # Load viewport settings
        if 'viewport' in data:
            vp_data = data['viewport']
            self.viewport_x = vp_data.get('x', 0)
            self.viewport_y = vp_data.get('y', 0)
            self.viewport_width = vp_data.get('width', SCREEN_WIDTH)
            self.viewport_height = vp_data.get('height', SCREEN_HEIGHT)

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

    def all_requirements_met(self):
        """Check if all level completion requirements are met (collectibles AND enemies)"""
        collectibles_done = self.required_collectibles_collected >= self.required_collectibles_total
        enemies_done = self.required_enemies_killed >= self.required_enemies_total
        return collectibles_done and enemies_done

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
        # Draw new parallax background layers (sorted from far to near: 0, 1, 2, 3)
        sorted_backgrounds = sorted(self.background_layers, key=lambda bg: bg.layer_index)
        for bg_img in sorted_backgrounds:
            if bg_img.image:
                # Apply parallax effect: further layers scroll slower
                parallax_x = bg_img.x - (camera_x * bg_img.parallax_factor)
                parallax_y = bg_img.y - (camera_y * bg_img.parallax_factor)

                # Scale and draw the background
                scaled_bg = pygame.transform.scale(bg_img.image, (bg_img.width, bg_img.height))
                if bg_img.repeat_x or bg_img.repeat_y:
                    tile_width = bg_img.width
                    tile_height = bg_img.height
                    start_x = parallax_x
                    start_y = parallax_y

                    if bg_img.repeat_x and tile_width > 0:
                        start_x = (parallax_x % tile_width) - tile_width
                    if bg_img.repeat_y and tile_height > 0:
                        start_y = (parallax_y % tile_height) - tile_height

                    if bg_img.repeat_x and bg_img.repeat_y:
                        tile_x = start_x
                        while tile_x < SCREEN_WIDTH:
                            tile_y = start_y
                            while tile_y < SCREEN_HEIGHT:
                                screen.blit(scaled_bg, (tile_x, tile_y))
                                tile_y += tile_height
                            tile_x += tile_width
                    elif bg_img.repeat_x:
                        tile_x = start_x
                        while tile_x < SCREEN_WIDTH:
                            screen.blit(scaled_bg, (tile_x, parallax_y))
                            tile_x += tile_width
                    elif bg_img.repeat_y:
                        tile_y = start_y
                        while tile_y < SCREEN_HEIGHT:
                            screen.blit(scaled_bg, (parallax_x, tile_y))
                            tile_y += tile_height
                else:
                    screen.blit(scaled_bg, (parallax_x, parallax_y))

        # Draw legacy background image if loaded (for backwards compatibility)
        if self.background_image and self.background_width > 0 and self.background_height > 0:
            screen_x = self.background_x - camera_x
            screen_y = self.background_y - camera_y
            scaled_bg = pygame.transform.scale(self.background_image, (self.background_width, self.background_height))
            screen.blit(scaled_bg, (screen_x, screen_y))

        # Draw tiles
        for layer in ['background', 'main', 'foreground']:
            for (tile_x, tile_y), tile in self.tiles[layer].items():
                screen_x = tile_x * TILE_SIZE - camera_x
                screen_y = tile_y * TILE_SIZE - camera_y

                # Only draw if visible
                if -TILE_SIZE < screen_x < SCREEN_WIDTH and -TILE_SIZE < screen_y < SCREEN_HEIGHT:
                    tile_type = self.tile_types.get(tile.tile_type_id)
                    if tile_type:
                        # Only show END_LEVEL tiles when all requirements are met
                        if TileProperty.END_LEVEL.value in tile_type.properties:
                            if not self.all_requirements_met():
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

class HighScoreManager:
    """Manages high scores with persistence"""
    def __init__(self, filename: str = "high_scores.json"):
        self.filename = filename
        self.scores: List[Tuple[str, int]] = []
        self.load_scores()

    def load_scores(self):
        """Load high scores from file"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    self.scores = [(entry['name'], entry['score']) for entry in data]
        except Exception as e:
            print(f"Error loading high scores: {e}")
            self.scores = []

    def save_scores(self):
        """Save high scores to file"""
        try:
            data = [{'name': name, 'score': score} for name, score in self.scores]
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving high scores: {e}")

    def add_score(self, name: str, score: int):
        """Add a new score and keep top 10"""
        self.scores.append((name, score))
        self.scores.sort(key=lambda x: x[1], reverse=True)
        self.scores = self.scores[:10]  # Keep top 10
        self.save_scores()

    def is_high_score(self, score: int) -> bool:
        """Check if score qualifies as a high score"""
        if len(self.scores) < 10:
            return True
        return score > self.scores[-1][1]

    def get_scores(self) -> List[Tuple[str, int]]:
        """Get all high scores"""
        return self.scores

class TitleScreen:
    """Retro-style title screen with menu"""
    def __init__(self, screen, font, large_font):
        self.screen = screen
        self.font = font
        self.large_font = large_font
        self.title_font = pygame.font.Font(None, 72)

        # Menu options
        self.menu_items = ["Start Run", "High Scores", "Quit"]
        self.selected_index = 0

        # Colors for retro effect
        self.title_color = (220, 180, 100)  # Gold
        self.menu_color = (200, 200, 200)   # Light gray
        self.selected_color = (255, 255, 100)  # Yellow
        self.bg_color = (20, 10, 30)  # Dark purple

        # Animation
        self.pulse_timer = 0

    def handle_input(self, event) -> Optional[str]:
        """Handle menu input, returns action or None"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP or event.key == pygame.K_w:
                self.selected_index = (self.selected_index - 1) % len(self.menu_items)
            elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                self.selected_index = (self.selected_index + 1) % len(self.menu_items)
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                return self.menu_items[self.selected_index]
            elif event.key == pygame.K_ESCAPE:
                return "Quit"
        return None

    def update(self):
        """Update animations"""
        self.pulse_timer += 1

    def draw(self):
        """Draw the title screen"""
        # Background
        self.screen.fill(self.bg_color)

        # Draw decorative elements (retro style)
        for i in range(0, SCREEN_WIDTH, 40):
            for j in range(0, SCREEN_HEIGHT, 40):
                if (i + j) % 80 == 0:
                    pygame.draw.rect(self.screen, (30, 20, 40), (i, j, 20, 20))

        # Title with shadow effect
        title_text = "CASTLES"
        # Shadow
        title_shadow = self.title_font.render(title_text, True, BLACK)
        shadow_rect = title_shadow.get_rect(center=(SCREEN_WIDTH // 2 + 4, 120 + 4))
        self.screen.blit(title_shadow, shadow_rect)
        # Main title
        pulse_offset = int(5 * abs(((self.pulse_timer % 60) / 60.0) * 2 - 1))
        title_color_pulsed = (
            min(255, self.title_color[0] + pulse_offset),
            min(255, self.title_color[1] + pulse_offset),
            min(255, self.title_color[2] + pulse_offset)
        )
        title = self.title_font.render(title_text, True, title_color_pulsed)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 120))
        self.screen.blit(title, title_rect)

        # Subtitle
        subtitle = self.font.render("A Retro Adventure", True, self.menu_color)
        subtitle_rect = subtitle.get_rect(center=(SCREEN_WIDTH // 2, 180))
        self.screen.blit(subtitle, subtitle_rect)

        # Menu items
        menu_start_y = 300
        menu_spacing = 50

        for i, item in enumerate(self.menu_items):
            # Determine color
            if i == self.selected_index:
                color = self.selected_color
                # Draw selection indicator
                indicator = "> "
                indicator_text = self.large_font.render(indicator, True, color)
                indicator_rect = indicator_text.get_rect(center=(SCREEN_WIDTH // 2 - 100, menu_start_y + i * menu_spacing))
                self.screen.blit(indicator_text, indicator_rect)
            else:
                color = self.menu_color

            # Draw menu item
            text = self.large_font.render(item, True, color)
            text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, menu_start_y + i * menu_spacing))
            self.screen.blit(text, text_rect)

        # Instructions at bottom
        instructions = self.font.render("Use Arrow Keys or W/S to navigate, Enter/Space to select", True, (150, 150, 150))
        instructions_rect = instructions.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50))
        self.screen.blit(instructions, instructions_rect)

class HighScoresScreen:
    """Display high scores"""
    def __init__(self, screen, font, large_font, high_score_manager):
        self.screen = screen
        self.font = font
        self.large_font = large_font
        self.title_font = pygame.font.Font(None, 64)
        self.high_score_manager = high_score_manager

        # Colors
        self.title_color = (220, 180, 100)  # Gold
        self.text_color = (200, 200, 200)   # Light gray
        self.bg_color = (20, 10, 30)  # Dark purple

    def handle_input(self, event) -> Optional[str]:
        """Handle input, returns action or None"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                return "back"
        return None

    def draw(self):
        """Draw the high scores screen"""
        # Background
        self.screen.fill(self.bg_color)

        # Draw decorative elements
        for i in range(0, SCREEN_WIDTH, 40):
            for j in range(0, SCREEN_HEIGHT, 40):
                if (i + j) % 80 == 0:
                    pygame.draw.rect(self.screen, (30, 20, 40), (i, j, 20, 20))

        # Title
        title = self.title_font.render("HIGH SCORES", True, self.title_color)
        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 80))
        self.screen.blit(title, title_rect)

        # Draw scores
        scores = self.high_score_manager.get_scores()
        start_y = 180
        spacing = 45

        if not scores:
            # No scores yet
            no_scores_text = self.large_font.render("No high scores yet!", True, self.text_color)
            no_scores_rect = no_scores_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            self.screen.blit(no_scores_text, no_scores_rect)
        else:
            # Draw header
            header = self.font.render("RANK    NAME                SCORE", True, (150, 150, 100))
            header_rect = header.get_rect(center=(SCREEN_WIDTH // 2, start_y - 40))
            self.screen.blit(header, header_rect)

            # Draw separator line
            pygame.draw.line(self.screen, (100, 100, 100),
                           (SCREEN_WIDTH // 2 - 250, start_y - 20),
                           (SCREEN_WIDTH // 2 + 250, start_y - 20), 2)

            # Draw each score
            for i, (name, score) in enumerate(scores):
                rank_text = f"{i + 1:2d}."
                name_text = f"{name[:15]:15s}"  # Limit name to 15 chars
                score_text = f"{score:8d}"

                # Color based on rank
                if i == 0:
                    color = (255, 215, 0)  # Gold
                elif i == 1:
                    color = (192, 192, 192)  # Silver
                elif i == 2:
                    color = (205, 127, 50)  # Bronze
                else:
                    color = self.text_color

                full_text = f"{rank_text}  {name_text}  {score_text}"
                text_surface = self.large_font.render(full_text, True, color)
                text_rect = text_surface.get_rect(center=(SCREEN_WIDTH // 2, start_y + i * spacing))
                self.screen.blit(text_surface, text_rect)

        # Instructions at bottom
        instructions = self.font.render("Press ESC, Enter, or Space to return", True, (150, 150, 150))
        instructions_rect = instructions.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 50))
        self.screen.blit(instructions, instructions_rect)

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Castles")
        self.clock = pygame.time.Clock()
        self.running = True

        # Font for UI (initialize before screens)
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
        self.large_font = pygame.font.Font(None, 48)

        # Game state - start at title screen
        self.state = GameState.TITLE
        self.game_over = False

        # High score management
        self.high_score_manager = HighScoreManager()

        # Screens
        self.title_screen = TitleScreen(self.screen, self.font, self.large_font)
        self.high_scores_screen = HighScoresScreen(self.screen, self.font, self.large_font, self.high_score_manager)

        # Game data (initialized when starting a run)
        self.levels = []
        self.current_level_index = 0
        self.level = None
        self.player = None

        # Camera
        self.camera_x = 0
        self.camera_y = 0

        # Total score across all levels in current run
        self.total_score = 0
    
    def start_run(self):
        """Start a new game run"""
        # Load all levels
        self.levels = self.load_all_levels()
        self.current_level_index = 0

        if not self.levels:
            print("No level files found! Please create a level first.")
            self.state = GameState.TITLE
            return

        # Initialize game
        self.level = self.levels[self.current_level_index]
        self.player = Player(100, 100)
        # Use viewport settings from level to set initial camera position
        self.camera_x = self.level.viewport_x
        self.camera_y = self.level.viewport_y
        self.game_over = False
        self.total_score = 0

        # Switch to playing state
        self.state = GameState.PLAYING

    def load_all_levels(self):
        """Load all level JSON files from current directory in numerical order"""
        levels = []
        level_files = sorted(Path('.').glob('level*.json'), key=lambda p: int(''.join(filter(str.isdigit, p.stem)) or 0))

        for filepath in level_files:
            try:
                level = Level(str(filepath))
                levels.append(level)
                print(f"Loaded level: {filepath}")
            except Exception as e:
                print(f"Error loading {filepath}: {e}")

        return levels
    
    def update_camera(self):
        """Update camera to follow player, using viewport size for zoom"""
        # Use viewport dimensions (smaller viewport = more zoom)
        viewport_width = self.level.viewport_width
        viewport_height = self.level.viewport_height

        # Center camera on player horizontally, keep player near bottom vertically
        target_x = self.player.x + self.player.width // 2 - viewport_width // 2
        target_y = self.player.y + self.player.height // 2 - int(
            viewport_height * CAMERA_PLAYER_VERTICAL_FRACTION
        )

        # Clamp camera to level bounds
        max_camera_x = max(0, self.level.width * TILE_SIZE - viewport_width)
        max_camera_y = max(0, self.level.height * TILE_SIZE - viewport_height)

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

    def check_player_attack_collisions(self):
        """Check if player's attack hits any enemies"""
        if not self.player.attacking:
            return

        attack_rect = self.player.get_attack_rect()

        for enemy in self.level.enemies:
            if not enemy.alive:
                continue

            enemy_rect = enemy.get_rect()
            if attack_rect.colliderect(enemy_rect):
                # Check if enemy was alive and required before dealing damage
                was_alive = enemy.alive
                was_required = enemy.enemy_type.required

                # Apply damage to enemy
                enemy.take_damage(self.player.attack_damage)

                # Track required enemy kills
                if was_alive and was_required and not enemy.alive:
                    self.level.required_enemies_killed += 1
                    print(f"Required enemy killed! ({self.level.required_enemies_killed}/{self.level.required_enemies_total})")

                # Knockback enemy
                if self.player.facing_right:
                    enemy.x += 15  # Push right
                else:
                    enemy.x -= 15  # Push left

                # Stop checking after hitting one enemy (sword can only hit one at a time)
                # Remove this break if you want the sword to hit multiple enemies
                break

    def check_end_level_collision(self):
        """Check if player touches END_LEVEL tile when requirements are met"""
        # Only check if all requirements are met (collectibles AND enemies)
        if not self.level.all_requirements_met():
            return False

        player_rect = self.player.get_rect()
        end_level_tiles = self.level.get_end_level_tiles()

        for (tile_x, tile_y), tile in end_level_tiles:
            tile_rect = pygame.Rect(tile_x * TILE_SIZE, tile_y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            if player_rect.colliderect(tile_rect):
                return True

        return False

    def advance_level(self):
        """Advance to the next level or restart current level if no next level"""
        # Add current level score to total
        self.total_score += self.level.score

        # Try to move to next level
        next_level_index = self.current_level_index + 1

        if next_level_index < len(self.levels):
            # Move to next level
            self.current_level_index = next_level_index
            self.level = self.levels[self.current_level_index]
            print(f"Level complete! Moving to level {self.current_level_index + 1}")
        else:
            # No more levels - game won! Save high score and return to menu
            print("All levels complete! You won!")
            final_score = self.total_score
            if final_score > 0:
                self.high_score_manager.add_score("PLAYER", final_score)
            self.state = GameState.TITLE
            return

        # Reset player position only (keep health for roguelike continuity)
        self.player.x = 100
        self.player.y = 100

    def check_player_death(self):
        """Check if player is dead"""
        # Death from health loss
        if self.player.health <= 0:
            self.game_over = True
            # Save high score
            final_score = self.total_score + self.level.score
            if final_score > 0:
                self.high_score_manager.add_score("PLAYER", final_score)
            self.total_score = final_score
            return

        # Death from falling off the bottom of the level
        level_bottom = self.level.height * TILE_SIZE
        if self.player.y > level_bottom:
            print("Player fell off the level!")
            self.game_over = True
            self.player.health = 0  # Set health to 0 for consistency
            # Save high score
            final_score = self.total_score + self.level.score
            if final_score > 0:
                self.high_score_manager.add_score("PLAYER", final_score)
            self.total_score = final_score

    def draw_game_over(self):
        """Draw game over screen"""
        # Semi-transparent overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        # Game Over text
        game_over_text = self.large_font.render("GAME OVER", True, RED)
        text_rect = game_over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 100))
        self.screen.blit(game_over_text, text_rect)

        # Show final score
        final_score = self.total_score
        score_text = self.large_font.render(f"Final Score: {final_score}", True, WHITE)
        score_rect = score_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30))
        self.screen.blit(score_text, score_rect)

        # Check if it's a high score
        if self.high_score_manager.is_high_score(final_score) and final_score > 0:
            high_score_text = self.font.render("NEW HIGH SCORE!", True, (255, 215, 0))
            hs_rect = high_score_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 10))
            self.screen.blit(high_score_text, hs_rect)

        # Instructions
        menu_text = self.font.render("Press ENTER to return to menu", True, WHITE)
        menu_rect = menu_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 60))
        self.screen.blit(menu_text, menu_rect)

        quit_text = self.font.render("Press ESC to Quit", True, WHITE)
        quit_rect = quit_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 90))
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
        self.screen.blit(level_text, (SCREEN_WIDTH - 200, 10))

        # Score (show total + current level)
        current_score = self.total_score + self.level.score
        score_text = self.font.render(f"Score: {current_score}", True, WHITE)
        self.screen.blit(score_text, (SCREEN_WIDTH - 200, 40))

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
        """Handle input events based on current state"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            # Handle events based on current state
            if self.state == GameState.TITLE:
                action = self.title_screen.handle_input(event)
                if action == "Start Run":
                    self.start_run()
                elif action == "High Scores":
                    self.state = GameState.HIGH_SCORES
                elif action == "Quit":
                    self.running = False

            elif self.state == GameState.HIGH_SCORES:
                action = self.high_scores_screen.handle_input(event)
                if action == "back":
                    self.state = GameState.TITLE

            elif self.state == GameState.PLAYING:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        # Return to title screen
                        self.state = GameState.TITLE
                    elif event.key == pygame.K_SPACE:
                        # Attack with spacebar
                        if not self.game_over:
                            self.player.start_attack()
                    elif event.key == pygame.K_RETURN:
                        # If game over, return to menu
                        if self.game_over:
                            self.state = GameState.TITLE
    
    def run(self):
        """Main game loop"""
        while self.running:
            self.handle_events()

            # Update and draw based on current state
            if self.state == GameState.TITLE:
                self.title_screen.update()
                self.title_screen.draw()

            elif self.state == GameState.HIGH_SCORES:
                self.high_scores_screen.draw()

            elif self.state == GameState.PLAYING:
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
                    self.check_player_attack_collisions()

                    # Check if player is dead
                    self.check_player_death()

                    # Check if player completed the level
                    if self.check_end_level_collision():
                        self.advance_level()

                    self.update_camera()

                # Draw game with viewport scaling for zoom effect
                self.screen.fill(BLACK)

                if self.level:
                    # Create a surface at viewport size (smaller = more zoomed in)
                    viewport_surface = pygame.Surface((self.level.viewport_width, self.level.viewport_height))
                    viewport_surface.fill(BLACK)

                    # Draw level and player to viewport surface
                    self.level.draw(viewport_surface, self.camera_x, self.camera_y)
                    if self.player:
                        self.player.draw(viewport_surface, self.camera_x, self.camera_y)

                    # Scale viewport surface to fill the screen (creates zoom effect)
                    scaled_surface = pygame.transform.scale(viewport_surface, (SCREEN_WIDTH, SCREEN_HEIGHT))
                    self.screen.blit(scaled_surface, (0, 0))

                    # Draw UI on top (not scaled)
                    if self.player:
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
