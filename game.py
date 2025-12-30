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
        for layer in ['background', 'main', 'foreground']:
            for (tile_x, tile_y), tile in self.tiles[layer].items():
                screen_x = tile_x * TILE_SIZE - camera_x
                screen_y = tile_y * TILE_SIZE - camera_y
                
                # Only draw if visible
                if -TILE_SIZE < screen_x < SCREEN_WIDTH and -TILE_SIZE < screen_y < SCREEN_HEIGHT:
                    tile_type = self.tile_types.get(tile.tile_type_id)
                    if tile_type:
                        if tile_type.image:
                            screen.blit(tile_type.image, (screen_x, screen_y))
                        else:
                            pygame.draw.rect(screen, tile_type.color,
                                           (screen_x, screen_y, TILE_SIZE, TILE_SIZE))

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
        
        # Font for UI
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
    
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
        self.player = Player(100, 100)
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
            
            # Get input
            keys = pygame.key.get_pressed()
            
            # Update
            self.player.update(keys, self.level)
            self.update_camera()
            
            # Draw
            self.screen.fill(BLACK)
            self.level.draw(self.screen, self.camera_x, self.camera_y)
            self.player.draw(self.screen, self.camera_x, self.camera_y)
            self.draw_ui()
            
            pygame.display.flip()
            self.clock.tick(FPS)
        
        pygame.quit()

if __name__ == "__main__":
    game = Game()
    game.run()
