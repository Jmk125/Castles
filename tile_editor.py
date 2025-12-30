import pygame
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from tkinter import filedialog
import tkinter as tk

# Initialize Pygame
pygame.init()

# Constants
SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 900
TILE_SIZE = 16
DEFAULT_LEVEL_WIDTH = 200  # tiles
DEFAULT_LEVEL_HEIGHT = 50  # tiles
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
LIGHT_GRAY = (200, 200, 200)
DARK_GRAY = (64, 64, 64)
BLUE = (100, 150, 255)
GREEN = (100, 255, 100)
RED = (255, 100, 100)
YELLOW = (255, 255, 100)
PURPLE = (200, 100, 255)
ORANGE = (255, 165, 0)

# Editor Tabs
class EditorTab(Enum):
    TILES = "tiles"
    ENEMIES = "enemies"
    OBJECTS = "objects"
    BACKGROUND = "background"

# Tile Properties
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
    color: Tuple[int, int, int]  # Fallback color if no image
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'image_path': self.image_path,
            'properties': self.properties,
            'color': self.color
        }

@dataclass
class Tile:
    tile_type_id: int
    layer: str

    def to_dict(self):
        return {
            'tile_type_id': self.tile_type_id,
            'layer': self.layer
        }

@dataclass
class EnemyType:
    id: int
    name: str
    image_path: Optional[str]
    image: Optional[pygame.Surface]
    ai_type: str  # EnemyAI enum value
    health: int
    damage: int
    speed: float
    color: Tuple[int, int, int]  # Fallback color
    behavior_script: Optional[str] = None  # Path to custom behavior .py file
    required: bool = False  # Required to kill to complete level

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'image_path': self.image_path,
            'ai_type': self.ai_type,
            'health': self.health,
            'damage': self.damage,
            'speed': self.speed,
            'color': self.color,
            'behavior_script': self.behavior_script
        }

@dataclass
class EnemyInstance:
    x: int
    y: int
    enemy_type_id: int
    patrol_range: int = 100  # For patrol AI

    def to_dict(self):
        return {
            'x': self.x,
            'y': self.y,
            'enemy_type_id': self.enemy_type_id,
            'patrol_range': self.patrol_range
        }

@dataclass
class CollectibleType:
    id: int
    name: str
    image_path: Optional[str]
    image: Optional[pygame.Surface]
    effect: str  # CollectibleEffect enum value
    value: int  # How much health, score, etc.
    color: Tuple[int, int, int]  # Fallback color
    required: bool = False  # Required to complete level

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'image_path': self.image_path,
            'effect': self.effect,
            'value': self.value,
            'color': self.color,
            'required': self.required
        }

@dataclass
class CollectibleInstance:
    x: int
    y: int
    collectible_type_id: int

    def to_dict(self):
        return {
            'x': self.x,
            'y': self.y,
            'collectible_type_id': self.collectible_type_id
        }

@dataclass
class BackgroundImage:
    layer_index: int  # 0-3 (0 = far background, 3 = closest)
    image_path: str
    image: Optional[pygame.Surface]
    x: int
    y: int
    width: int
    height: int
    repeat_x: bool = False  # Repeat horizontally
    repeat_y: bool = False  # Repeat vertically
    parallax_factor: float = 0.5  # Parallax scroll speed (0.0 = no scroll, 1.0 = scroll with camera)
    aspect_ratio_locked: bool = True  # Lock aspect ratio when resizing

    def to_dict(self):
        return {
            'layer_index': self.layer_index,
            'image_path': self.image_path,
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'repeat_x': self.repeat_x,
            'repeat_y': self.repeat_y,
            'parallax_factor': self.parallax_factor,
            'aspect_ratio_locked': self.aspect_ratio_locked
        }

class Tool(Enum):
    PENCIL = "pencil"
    RECTANGLE = "rectangle"
    LINE = "line"
    ERASER = "eraser"

class TileEditor:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Castlevania Tile Editor")
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Level data
        self.level_width = DEFAULT_LEVEL_WIDTH
        self.level_height = DEFAULT_LEVEL_HEIGHT
        self.tiles: Dict[str, Dict[Tuple[int, int], Tile]] = {
            'background': {},
            'main': {},
            'foreground': {}
        }
        
        # Camera
        self.camera_x = 0
        self.camera_y = 0
        self.dragging_camera = False
        self.drag_start_pos = None
        
        # UI Layout
        self.palette_width = 300
        self.canvas_rect = pygame.Rect(0, 0, SCREEN_WIDTH - self.palette_width, SCREEN_HEIGHT)
        self.palette_rect = pygame.Rect(SCREEN_WIDTH - self.palette_width, 0, self.palette_width, SCREEN_HEIGHT)
        
        # Tile types (with placeholder tiles)
        self.tile_types: Dict[int, TileType] = {}
        self.next_tile_id = 0
        self._create_placeholder_tiles()

        # Enemy types and instances
        self.enemy_types: Dict[int, EnemyType] = {}
        self.next_enemy_type_id = 0
        self.enemies: List[EnemyInstance] = []
        self._create_placeholder_enemies()

        # Collectible types and instances
        self.collectible_types: Dict[int, CollectibleType] = {}
        self.next_collectible_type_id = 0
        self.collectibles: List[CollectibleInstance] = []
        self._create_placeholder_collectibles()

        # Background image (legacy - still used for TILES tab)
        self.background_image_path: Optional[str] = None
        self.background_image: Optional[pygame.Surface] = None
        self.background_x = 0
        self.background_y = 0
        self.background_width = 0
        self.background_height = 0
        self.resizing_background = False
        self.resize_start_pos = None

        # Background layers (new system for BACKGROUND tab)
        self.background_layers: List[BackgroundImage] = []  # All background images across all layers
        self.selected_bg_image_index: Optional[int] = None  # Currently selected background image
        self.dragging_bg_image = False
        self.resizing_bg_image = False
        self.bg_drag_start_pos = None
        self.bg_resize_start_pos = None
        self.current_bg_layer = 0  # 0-3, which layer is selected in the UI

        # Current state
        self.current_tab = EditorTab.TILES
        self.current_tile_type_id = 0
        self.current_enemy_type_id = None
        self.current_collectible_type_id = None
        self.current_layer = 'main'
        self.layer_visibility = {'background': True, 'main': True, 'foreground': True}
        self.current_tool = Tool.PENCIL
        self.selected_entity_index = None  # For selecting placed enemies/collectibles
        
        # Drawing state
        self.drawing = False
        self.draw_start_tile = None
        self.preview_tiles = []
        
        # UI state
        self.selected_property_tile_id = None
        self.scroll_offset = 0
        self.max_scroll = 0
        self.editing_tile_id = None
        self.show_property_editor = False
        self.property_checkboxes = {}

        # Enemy/Collectible editor state
        self.editing_enemy_id = None
        self.editing_collectible_id = None
        self.show_enemy_editor = False
        self.show_collectible_editor = False
        self.enemy_ai_buttons = {}  # For AI type selection
        self.collectible_effect_buttons = {}  # For effect type selection

        # Font
        self.font = pygame.font.Font(None, 20)
        self.small_font = pygame.font.Font(None, 16)

        # Input state for property editor
        self.input_text = ""
        self.input_active = False
        self.input_field = None  # 'name', 'color', 'health', 'damage', 'speed', 'value', etc.

        # Viewport settings (for game camera preview)
        self.viewport_width = VIEWPORT_WIDTH
        self.viewport_height = VIEWPORT_HEIGHT
        self.viewport_x = 0  # Position in world coordinates
        self.viewport_y = 0
        self.dragging_viewport = False
        self.resizing_viewport = False
        self.viewport_drag_start = None
        self.viewport_resize_start = None

        # Top bar buttons
        self.new_button_rect = None
        self.open_button_rect = None
        self.save_as_button_rect = None
        
    def _create_placeholder_tiles(self):
        """Create starter placeholder tiles"""
        # Ground tile
        self.add_tile_type("Ground", None, [TileProperty.SOLID.value], GREEN)

        # Platform tile
        self.add_tile_type("Platform", None, [TileProperty.PLATFORM.value], BLUE)

        # Hazard tile
        self.add_tile_type("Hazard", None, [TileProperty.HAZARD.value, TileProperty.SOLID.value], RED)

        # Background tile
        self.add_tile_type("Background", None, [TileProperty.BACKGROUND.value], LIGHT_GRAY)

        # Ladder tile
        self.add_tile_type("Ladder", None, [TileProperty.LADDER.value], YELLOW)

        # Breakable tile
        self.add_tile_type("Breakable", None, [TileProperty.BREAKABLE.value, TileProperty.SOLID.value], ORANGE)

    def _create_placeholder_enemies(self):
        """Create starter enemy types"""
        # Skeleton - basic patrol enemy
        self.add_enemy_type("Skeleton", None, EnemyAI.PATROL.value, 3, 1, 1.5, RED)

        # Ghost - flying chase enemy
        self.add_enemy_type("Ghost", None, EnemyAI.FLYING.value, 2, 1, 2.0, PURPLE)

        # Spikes - stationary hazard
        self.add_enemy_type("Spikes", None, EnemyAI.STATIONARY.value, 999, 2, 0, DARK_GRAY)

    def _create_placeholder_collectibles(self):
        """Create starter collectible types"""
        # Health potion
        self.add_collectible_type("Health Potion", None, CollectibleEffect.HEALTH.value, 20, GREEN)

        # Coin
        self.add_collectible_type("Coin", None, CollectibleEffect.SCORE.value, 100, YELLOW)

        # Key
        self.add_collectible_type("Key", None, CollectibleEffect.KEY.value, 1, BLUE)

        # Power Up
        self.add_collectible_type("Power Up", None, CollectibleEffect.POWERUP.value, 1, PURPLE)

    def add_tile_type(self, name: str, image_path: Optional[str], properties: List[str], color: Tuple[int, int, int]):
        """Add a new tile type"""
        image = None
        if image_path and os.path.exists(image_path):
            try:
                image = pygame.image.load(image_path)
                image = pygame.transform.scale(image, (TILE_SIZE, TILE_SIZE))
            except:
                pass

        tile_type = TileType(
            id=self.next_tile_id,
            name=name,
            image_path=image_path,
            image=image,
            properties=properties,
            color=color
        )
        self.tile_types[self.next_tile_id] = tile_type
        self.next_tile_id += 1
        return tile_type.id

    def add_enemy_type(self, name: str, image_path: Optional[str], ai_type: str, health: int, damage: int, speed: float, color: Tuple[int, int, int], behavior_script: Optional[str] = None):
        """Add a new enemy type"""
        image = None
        if image_path and os.path.exists(image_path):
            try:
                image = pygame.image.load(image_path)
                image = pygame.transform.scale(image, (TILE_SIZE, TILE_SIZE))
            except:
                pass

        enemy_type = EnemyType(
            id=self.next_enemy_type_id,
            name=name,
            image_path=image_path,
            image=image,
            ai_type=ai_type,
            health=health,
            damage=damage,
            speed=speed,
            color=color,
            behavior_script=behavior_script
        )
        self.enemy_types[self.next_enemy_type_id] = enemy_type
        self.next_enemy_type_id += 1
        return enemy_type.id

    def add_collectible_type(self, name: str, image_path: Optional[str], effect: str, value: int, color: Tuple[int, int, int], required: bool = False):
        """Add a new collectible type"""
        image = None
        if image_path and os.path.exists(image_path):
            try:
                image = pygame.image.load(image_path)
                image = pygame.transform.scale(image, (TILE_SIZE, TILE_SIZE))
            except:
                pass

        collectible_type = CollectibleType(
            id=self.next_collectible_type_id,
            name=name,
            image_path=image_path,
            image=image,
            effect=effect,
            value=value,
            color=color,
            required=required
        )
        self.collectible_types[self.next_collectible_type_id] = collectible_type
        self.next_collectible_type_id += 1
        return collectible_type.id
    
    def apply_input_text(self):
        """Apply text input to the property being edited"""
        if self.input_field is None:
            return

        # Handle tile editing
        if self.editing_tile_id is not None:
            tile_type = self.tile_types.get(self.editing_tile_id)
            if tile_type:
                if self.input_field == 'name':
                    tile_type.name = self.input_text if self.input_text else tile_type.name
                elif self.input_field == 'color':
                    try:
                        parts = self.input_text.replace(',', ' ').split()
                        if len(parts) == 3:
                            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                tile_type.color = (r, g, b)
                    except:
                        pass

        # Handle enemy editing
        elif self.editing_enemy_id is not None:
            enemy_type = self.enemy_types.get(self.editing_enemy_id)
            if enemy_type:
                if self.input_field == 'name':
                    enemy_type.name = self.input_text if self.input_text else enemy_type.name
                elif self.input_field == 'health':
                    try:
                        enemy_type.health = max(1, int(self.input_text))
                    except:
                        pass
                elif self.input_field == 'damage':
                    try:
                        enemy_type.damage = max(0, int(self.input_text))
                    except:
                        pass
                elif self.input_field == 'speed':
                    try:
                        enemy_type.speed = max(0.0, float(self.input_text))
                    except:
                        pass
                elif self.input_field == 'color':
                    try:
                        parts = self.input_text.replace(',', ' ').split()
                        if len(parts) == 3:
                            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                enemy_type.color = (r, g, b)
                    except:
                        pass

        # Handle collectible editing
        elif self.editing_collectible_id is not None:
            collectible_type = self.collectible_types.get(self.editing_collectible_id)
            if collectible_type:
                if self.input_field == 'name':
                    collectible_type.name = self.input_text if self.input_text else collectible_type.name
                elif self.input_field == 'value':
                    try:
                        collectible_type.value = max(0, int(self.input_text))
                    except:
                        pass
                elif self.input_field == 'color':
                    try:
                        parts = self.input_text.replace(',', ' ').split()
                        if len(parts) == 3:
                            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                                collectible_type.color = (r, g, b)
                    except:
                        pass

        self.input_text = ""
        self.input_field = None
        
    def screen_to_tile(self, screen_x: int, screen_y: int) -> Optional[Tuple[int, int]]:
        """Convert screen coordinates to tile coordinates"""
        if not self.canvas_rect.collidepoint(screen_x, screen_y):
            return None
        
        world_x = screen_x + self.camera_x
        world_y = screen_y + self.camera_y
        
        tile_x = world_x // TILE_SIZE
        tile_y = world_y // TILE_SIZE
        
        if 0 <= tile_x < self.level_width and 0 <= tile_y < self.level_height:
            return (tile_x, tile_y)
        return None
    
    def place_tile(self, tile_x: int, tile_y: int):
        """Place a tile at the given position"""
        if self.current_tile_type_id is not None:
            self.tiles[self.current_layer][(tile_x, tile_y)] = Tile(
                tile_type_id=self.current_tile_type_id,
                layer=self.current_layer
            )
    
    def erase_tile(self, tile_x: int, tile_y: int):
        """Erase a tile at the given position"""
        if (tile_x, tile_y) in self.tiles[self.current_layer]:
            del self.tiles[self.current_layer][(tile_x, tile_y)]
    
    def get_line_tiles(self, start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get all tiles in a line using Bresenham's algorithm"""
        tiles = []
        x0, y0 = start
        x1, y1 = end
        
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        
        while True:
            tiles.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy
        
        return tiles
    
    def get_rectangle_tiles(self, start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get all tiles in a rectangle"""
        tiles = []
        x0, y0 = start
        x1, y1 = end
        
        min_x, max_x = min(x0, x1), max(x0, x1)
        min_y, max_y = min(y0, y1), max(y0, y1)
        
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                tiles.append((x, y))
        
        return tiles
    
    def handle_events(self):
        """Handle all input events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.KEYDOWN:
                # Handle text input for property editor
                if self.show_property_editor and self.input_active:
                    if event.key == pygame.K_RETURN:
                        self.input_active = False
                        self.apply_input_text()
                    elif event.key == pygame.K_ESCAPE:
                        self.input_active = False
                        self.input_text = ""
                    elif event.key == pygame.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                    else:
                        self.input_text += event.unicode
                # Normal hotkeys
                elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    self.save_level_as_dialog()
                elif event.key == pygame.K_o and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    self.open_level_dialog()
                elif event.key == pygame.K_ESCAPE:
                    self.show_property_editor = False
                    self.input_active = False
                elif event.key == pygame.K_1:
                    self.current_layer = 'background'
                elif event.key == pygame.K_2:
                    self.current_layer = 'main'
                elif event.key == pygame.K_3:
                    self.current_layer = 'foreground'
                elif event.key == pygame.K_p:
                    self.current_tool = Tool.PENCIL
                elif event.key == pygame.K_r:
                    self.current_tool = Tool.RECTANGLE
                elif event.key == pygame.K_l:
                    self.current_tool = Tool.LINE
                elif event.key == pygame.K_e:
                    self.current_tool = Tool.ERASER
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    self.handle_left_click(event.pos)
                elif event.button == 2:  # Middle click
                    self.dragging_camera = True
                    self.drag_start_pos = event.pos
                elif event.button == 3:  # Right click
                    self.handle_right_click(event.pos)
                elif event.button == 4:  # Scroll up
                    if pygame.key.get_mods() & pygame.KMOD_CTRL:
                        # Pan left
                        self.camera_x = max(0, self.camera_x - 50)
                    elif self.palette_rect.collidepoint(event.pos):
                        # Scroll palette up
                        self.scroll_offset = max(0, self.scroll_offset - 30)
                elif event.button == 5:  # Scroll down
                    if pygame.key.get_mods() & pygame.KMOD_CTRL:
                        # Pan right
                        self.camera_x = min(self.level_width * TILE_SIZE - self.canvas_rect.width, 
                                          self.camera_x + 50)
                    elif self.palette_rect.collidepoint(event.pos):
                        # Scroll palette down
                        self.scroll_offset = min(self.max_scroll, self.scroll_offset + 30)
            
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.handle_left_release(event.pos)
                elif event.button == 2:
                    self.dragging_camera = False
                elif event.button == 3:  # Right click release
                    # Stop resizing background image
                    if self.resizing_bg_image:
                        self.resizing_bg_image = False
                        self.bg_resize_start_pos = None
            
            elif event.type == pygame.MOUSEMOTION:
                if self.dragging_viewport and self.viewport_drag_start:
                    # Drag viewport
                    dx = event.pos[0] - self.viewport_drag_start[0]
                    dy = event.pos[1] - self.viewport_drag_start[1]
                    self.viewport_x += dx
                    self.viewport_y += dy
                    # Clamp to level boundaries
                    self.viewport_x = max(0, min(self.viewport_x, self.level_width * TILE_SIZE - self.viewport_width))
                    self.viewport_y = max(0, min(self.viewport_y, self.level_height * TILE_SIZE - self.viewport_height))
                    self.viewport_drag_start = event.pos
                elif self.resizing_viewport and self.viewport_resize_start:
                    # Resize viewport from top-left (maintain 16:9 aspect ratio)
                    dx = event.pos[0] - self.viewport_resize_start[0]
                    dy = event.pos[1] - self.viewport_resize_start[1]
                    # Use the larger of the two deltas to determine size change
                    delta = max(abs(dx), abs(dy)) * (-1 if dx + dy > 0 else 1)
                    new_width = max(160, self.viewport_width + delta)
                    # Maintain 16:9 aspect ratio
                    new_height = int(new_width * 9 / 16)
                    # Adjust position to keep bottom-right corner fixed
                    width_change = new_width - self.viewport_width
                    height_change = new_height - self.viewport_height
                    self.viewport_x = max(0, self.viewport_x - width_change)
                    self.viewport_y = max(0, self.viewport_y - height_change)
                    self.viewport_width = new_width
                    self.viewport_height = new_height
                    self.viewport_resize_start = event.pos
                elif self.resizing_background and self.resize_start_pos:
                    # Resize background image from top-left (legacy TILES tab)
                    dx = event.pos[0] - self.resize_start_pos[0]
                    dy = event.pos[1] - self.resize_start_pos[1]
                    new_width = max(50, self.background_width - dx)
                    new_height = max(50, self.background_height - dy)
                    # Adjust position
                    self.background_x += self.background_width - new_width
                    self.background_y += self.background_height - new_height
                    self.background_width = new_width
                    self.background_height = new_height
                    self.resize_start_pos = event.pos
                elif self.dragging_camera and self.drag_start_pos:
                    dx = self.drag_start_pos[0] - event.pos[0]
                    dy = self.drag_start_pos[1] - event.pos[1]
                    self.camera_x = max(0, min(self.camera_x + dx, self.level_width * TILE_SIZE - self.canvas_rect.width))
                    self.camera_y = max(0, min(self.camera_y + dy, self.level_height * TILE_SIZE - self.canvas_rect.height))
                    self.drag_start_pos = event.pos
                elif self.dragging_bg_image or self.resizing_bg_image:
                    # Handle background image dragging/resizing
                    self.handle_mouse_motion(event.pos)
                elif self.drawing:
                    self.handle_mouse_motion(event.pos)
            
            elif event.type == pygame.DROPFILE:
                self.handle_file_drop(event.file)
    
    def handle_left_click(self, pos):
        """Handle left mouse click"""
        # Check if clicking on top bar buttons
        if self.new_button_rect and self.new_button_rect.collidepoint(pos):
            self.new_level()
            return

        if self.open_button_rect and self.open_button_rect.collidepoint(pos):
            self.open_level_dialog()
            return

        if self.save_as_button_rect and self.save_as_button_rect.collidepoint(pos):
            self.save_level_as_dialog()
            return

        # Check if clicking on viewport controls (in canvas area)
        # Skip viewport controls when on BACKGROUND tab to allow background image dragging
        if self.current_tab != EditorTab.BACKGROUND and self.canvas_rect.collidepoint(pos):
            viewport_screen_x = self.viewport_x - self.camera_x
            viewport_screen_y = self.viewport_y - self.camera_y

            # Check resize handle (top-left corner)
            handle_size = 12
            handle_rect = pygame.Rect(viewport_screen_x, viewport_screen_y, handle_size, handle_size)
            if handle_rect.collidepoint(pos):
                self.resizing_viewport = True
                self.viewport_resize_start = pos
                return

            # Check if clicking on viewport border (not inside) for dragging
            border_thickness = 4
            viewport_rect = pygame.Rect(viewport_screen_x, viewport_screen_y, self.viewport_width, self.viewport_height)
            # Create inner rect (the area inside the border)
            inner_rect = pygame.Rect(viewport_screen_x + border_thickness,
                                    viewport_screen_y + border_thickness,
                                    self.viewport_width - border_thickness * 2,
                                    self.viewport_height - border_thickness * 2)

            # If click is on viewport but NOT on inner area, it's on the border
            if viewport_rect.collidepoint(pos) and not inner_rect.collidepoint(pos):
                self.dragging_viewport = True
                self.viewport_drag_start = pos
                return

        # Check if clicking on background resize handle (legacy background in TILES tab)
        if self.background_image and self.background_width > 0 and self.background_height > 0:
            handle_size = 12
            screen_x = self.background_x - self.camera_x
            screen_y = self.background_y - self.camera_y
            handle_rect = pygame.Rect(screen_x, screen_y, handle_size, handle_size)

            if handle_rect.collidepoint(pos):
                self.resizing_background = True
                self.resize_start_pos = pos
                return

        # Check if clicking on background layer images (new system - SIMPLE!)
        # Selection is done via palette - canvas only allows drag/resize of selected image
        if self.current_tab == EditorTab.BACKGROUND and self.canvas_rect.collidepoint(pos):
            # Only allow dragging if there's a selected image
            if self.selected_bg_image_index is not None:
                bg_img = self.background_layers[self.selected_bg_image_index]
                screen_x = bg_img.x - self.camera_x
                screen_y = bg_img.y - self.camera_y
                img_rect = pygame.Rect(screen_x, screen_y, bg_img.width, bg_img.height)

                # Left click anywhere on selected image = drag to move
                if img_rect.collidepoint(pos):
                    self.dragging_bg_image = True
                    self.bg_drag_start_pos = pos
                    return

        # Check if clicking in palette
        if self.palette_rect.collidepoint(pos):
            self.handle_palette_click(pos)
        # Check if clicking in canvas
        elif self.canvas_rect.collidepoint(pos):
            if self.current_tab == EditorTab.TILES:
                # Tile placement logic
                tile_pos = self.screen_to_tile(pos[0], pos[1])
                if tile_pos:
                    self.drawing = True
                    self.draw_start_tile = tile_pos

                    if self.current_tool == Tool.PENCIL:
                        self.place_tile(*tile_pos)
                    elif self.current_tool == Tool.ERASER:
                        self.erase_tile(*tile_pos)

            elif self.current_tab == EditorTab.ENEMIES:
                # Enemy placement logic
                if self.current_enemy_type_id is not None:
                    world_x = pos[0] + self.camera_x
                    world_y = pos[1] + self.camera_y
                    # Snap to grid
                    snap_x = (world_x // TILE_SIZE) * TILE_SIZE
                    snap_y = (world_y // TILE_SIZE) * TILE_SIZE
                    enemy = EnemyInstance(x=snap_x, y=snap_y, enemy_type_id=self.current_enemy_type_id)
                    self.enemies.append(enemy)

            elif self.current_tab == EditorTab.OBJECTS:
                # Collectible placement logic
                if self.current_collectible_type_id is not None:
                    world_x = pos[0] + self.camera_x
                    world_y = pos[1] + self.camera_y
                    # Snap to grid
                    snap_x = (world_x // TILE_SIZE) * TILE_SIZE
                    snap_y = (world_y // TILE_SIZE) * TILE_SIZE
                    collectible = CollectibleInstance(x=snap_x, y=snap_y, collectible_type_id=self.current_collectible_type_id)
                    self.collectibles.append(collectible)

            # BACKGROUND tab clicks are handled above
    
    def handle_left_release(self, pos):
        """Handle left mouse release"""
        # Stop dragging/resizing viewport
        if self.dragging_viewport:
            self.dragging_viewport = False
            self.viewport_drag_start = None
            return

        if self.resizing_viewport:
            self.resizing_viewport = False
            self.viewport_resize_start = None
            return

        # Stop resizing background (legacy)
        if self.resizing_background:
            self.resizing_background = False
            self.resize_start_pos = None
            return

        # Stop dragging/resizing background image (new system)
        if self.dragging_bg_image:
            self.dragging_bg_image = False
            self.bg_drag_start_pos = None
            return

        if self.resizing_bg_image:
            self.resizing_bg_image = False
            self.bg_resize_start_pos = None
            return

        if self.drawing and self.draw_start_tile:
            tile_pos = self.screen_to_tile(pos[0], pos[1])
            if tile_pos:
                if self.current_tool == Tool.RECTANGLE:
                    tiles = self.get_rectangle_tiles(self.draw_start_tile, tile_pos)
                    for t in tiles:
                        self.place_tile(*t)
                elif self.current_tool == Tool.LINE:
                    tiles = self.get_line_tiles(self.draw_start_tile, tile_pos)
                    for t in tiles:
                        self.place_tile(*t)
        
        self.drawing = False
        self.draw_start_tile = None
        self.preview_tiles = []
    
    def handle_right_click(self, pos):
        """Handle right mouse click"""
        if self.canvas_rect.collidepoint(pos):
            if self.current_tab == EditorTab.TILES:
                tile_pos = self.screen_to_tile(pos[0], pos[1])
                if tile_pos and tile_pos in self.tiles[self.current_layer]:
                    self.erase_tile(*tile_pos)

            elif self.current_tab == EditorTab.ENEMIES:
                # Delete enemy at clicked position
                world_x = pos[0] + self.camera_x
                world_y = pos[1] + self.camera_y
                # Find and remove enemy at this position (within TILE_SIZE range)
                for i, enemy in enumerate(self.enemies):
                    if abs(enemy.x - world_x) < TILE_SIZE and abs(enemy.y - world_y) < TILE_SIZE:
                        self.enemies.pop(i)
                        break

            elif self.current_tab == EditorTab.OBJECTS:
                # Delete collectible at clicked position
                world_x = pos[0] + self.camera_x
                world_y = pos[1] + self.camera_y
                for i, collectible in enumerate(self.collectibles):
                    if abs(collectible.x - world_x) < TILE_SIZE and abs(collectible.y - world_y) < TILE_SIZE:
                        self.collectibles.pop(i)
                        break

            elif self.current_tab == EditorTab.BACKGROUND:
                # Right click on selected background image = resize
                if self.selected_bg_image_index is not None:
                    bg_img = self.background_layers[self.selected_bg_image_index]
                    screen_x = bg_img.x - self.camera_x
                    screen_y = bg_img.y - self.camera_y
                    img_rect = pygame.Rect(screen_x, screen_y, bg_img.width, bg_img.height)

                    # Right click anywhere on selected image = resize
                    if img_rect.collidepoint(pos):
                        self.resizing_bg_image = True
                        self.bg_resize_start_pos = pos
    
    def handle_mouse_motion(self, pos):
        """Handle mouse motion while drawing, dragging, or resizing"""
        # Handle dragging background image
        if self.dragging_bg_image and self.selected_bg_image_index is not None:
            bg_img = self.background_layers[self.selected_bg_image_index]
            dx = pos[0] - self.bg_drag_start_pos[0]
            dy = pos[1] - self.bg_drag_start_pos[1]
            bg_img.x += dx
            bg_img.y += dy
            self.bg_drag_start_pos = pos
            return

        # Handle resizing background image (from top-left corner)
        if self.resizing_bg_image and self.selected_bg_image_index is not None:
            bg_img = self.background_layers[self.selected_bg_image_index]
            dx = pos[0] - self.bg_resize_start_pos[0]
            dy = pos[1] - self.bg_resize_start_pos[1]

            if bg_img.aspect_ratio_locked and bg_img.image:
                # Maintain aspect ratio - resize from top-left
                original_aspect = bg_img.image.get_width() / bg_img.image.get_height()
                # Use the larger delta to determine size change
                delta = max(abs(dx), abs(dy)) * (-1 if dx + dy > 0 else 1)
                new_width = max(10, bg_img.width + delta)
                new_height = int(new_width / original_aspect)
                # Adjust position to keep bottom-right corner fixed
                width_change = new_width - bg_img.width
                height_change = new_height - bg_img.height
                bg_img.x -= width_change
                bg_img.y -= height_change
                bg_img.width = new_width
                bg_img.height = new_height
            else:
                # Free resize from top-left
                new_width = max(10, bg_img.width - dx)
                new_height = max(10, bg_img.height - dy)
                # Adjust position
                bg_img.x += bg_img.width - new_width
                bg_img.y += bg_img.height - new_height
                bg_img.width = new_width
                bg_img.height = new_height

            self.bg_resize_start_pos = pos
            return

        if self.draw_start_tile:
            tile_pos = self.screen_to_tile(pos[0], pos[1])
            if tile_pos:
                if self.current_tool == Tool.PENCIL:
                    self.place_tile(*tile_pos)
                elif self.current_tool == Tool.ERASER:
                    self.erase_tile(*tile_pos)
                elif self.current_tool == Tool.RECTANGLE:
                    self.preview_tiles = self.get_rectangle_tiles(self.draw_start_tile, tile_pos)
                elif self.current_tool == Tool.LINE:
                    self.preview_tiles = self.get_line_tiles(self.draw_start_tile, tile_pos)
    
    def handle_palette_click(self, pos):
        """Handle clicking in the tile palette"""
        # Check if clicking in property editor dialog (only if it's open)
        if self.show_property_editor:
            # Property editor bounds (must match draw_property_editor)
            editor_x = self.palette_rect.x + 20
            editor_y = 150
            editor_width = self.palette_width - 40
            editor_height = 450
            editor_rect = pygame.Rect(editor_x, editor_y, editor_width, editor_height)

            if editor_rect.collidepoint(pos):
                # Click is inside the editor, handle it
                self.handle_property_editor_click(pos)
                return
            else:
                # Click is outside the editor, close it
                self.show_property_editor = False
                self.editing_tile_id = None
                self.input_active = False
                return

        # Check if clicking in enemy editor dialog
        if self.show_enemy_editor:
            editor_x = self.palette_rect.x + 20
            editor_y = 100
            editor_width = self.palette_width - 40
            editor_height = 550
            editor_rect = pygame.Rect(editor_x, editor_y, editor_width, editor_height)

            if editor_rect.collidepoint(pos):
                self.handle_enemy_editor_click(pos)
                return
            else:
                self.show_enemy_editor = False
                self.editing_enemy_id = None
                self.input_active = False
                return

        # Check if clicking in collectible editor dialog
        if self.show_collectible_editor:
            editor_x = self.palette_rect.x + 20
            editor_y = 100
            editor_width = self.palette_width - 40
            editor_height = 500
            editor_rect = pygame.Rect(editor_x, editor_y, editor_width, editor_height)

            if editor_rect.collidepoint(pos):
                self.handle_collectible_editor_click(pos)
                return
            else:
                self.show_collectible_editor = False
                self.editing_collectible_id = None
                self.input_active = False
                return

        # Check tab buttons (4 tabs in 2 rows)
        y_offset = 10
        tab_width = (self.palette_width - 40) // 2
        tab_height = 25
        tab_x = self.palette_rect.x + 10

        tabs = [EditorTab.TILES, EditorTab.ENEMIES, EditorTab.OBJECTS, EditorTab.BACKGROUND]
        for i, tab in enumerate(tabs):
            row = i // 2
            col = i % 2
            tab_rect = pygame.Rect(tab_x + col * (tab_width + 5), y_offset + row * (tab_height + 5), tab_width, tab_height)
            if tab_rect.collidepoint(pos):
                self.current_tab = tab
                self.scroll_offset = 0  # Reset scroll when switching tabs
                return

        y_offset += 65

        # Handle tile-specific controls
        if self.current_tab == EditorTab.TILES:
            y_offset += 25  # "Layers:" label

            # Check layer toggles
            layer_y = y_offset
            for i, layer in enumerate(['background', 'main', 'foreground']):
                checkbox_rect = pygame.Rect(self.palette_rect.x + 10, layer_y, 15, 15)
                if checkbox_rect.collidepoint(pos):
                    self.layer_visibility[layer] = not self.layer_visibility[layer]
                    return
                layer_y += 20

            y_offset += 60  # layer checkboxes (3 * 20)
            y_offset += 10  # gap
            y_offset += 20  # "Tool:"
            y_offset += 20  # tool keys
            y_offset += 20  # level size

            # Check resize buttons
            resize_button_width = (self.palette_width - 30) // 2
            wider_button = pygame.Rect(self.palette_rect.x + 10, y_offset, resize_button_width, 25)
            narrower_button = pygame.Rect(self.palette_rect.x + 15 + resize_button_width, y_offset, resize_button_width, 25)

            if wider_button.collidepoint(pos):
                self.level_width += 10
                return
            elif narrower_button.collidepoint(pos):
                self.level_width = max(50, self.level_width - 10)
                return

            y_offset += 35  # gap after resize buttons

            # Background image button
            bg_button_rect = pygame.Rect(self.palette_rect.x + 10, y_offset, self.palette_width - 20, 25)
            if bg_button_rect.collidepoint(pos):
                self.load_background_image()
                return

            y_offset += 35  # gap after background button

        # Check plus button (all tabs)
        plus_button_rect = pygame.Rect(self.palette_rect.x + 10, y_offset, self.palette_width - 20, 30)

        if plus_button_rect.collidepoint(pos):
            if self.current_tab == EditorTab.TILES:
                self.add_tile_type(f"New Tile {self.next_tile_id}", None, [TileProperty.SOLID.value], (128, 128, 128))
            elif self.current_tab == EditorTab.ENEMIES:
                new_id = self.add_enemy_type(f"New Enemy {self.next_enemy_type_id}", None, EnemyAI.PATROL.value, 3, 1, 1.5, (200, 100, 100))
                self.current_enemy_type_id = new_id
            elif self.current_tab == EditorTab.OBJECTS:
                new_id = self.add_collectible_type(f"New Object {self.next_collectible_type_id}", None, CollectibleEffect.SCORE.value, 10, (255, 200, 0))
                self.current_collectible_type_id = new_id
            # BACKGROUND tab doesn't use the plus button
            return

        y_offset += 40  # gap after plus button
        y_offset += 25  # section label

        # Content area
        content_area_top = y_offset
        content_area_height = SCREEN_HEIGHT - y_offset - 100

        # Handle clicks on content based on current tab
        if self.current_tab == EditorTab.TILES:
            item_y = y_offset - self.scroll_offset
            for tile_id, tile_type in self.tile_types.items():
                if item_y + 60 < content_area_top or item_y > content_area_top + content_area_height:
                    item_y += 70
                    continue

                item_rect = pygame.Rect(self.palette_rect.x + 10, item_y, self.palette_width - 20, 60)

                if not item_rect.collidepoint(pos):
                    item_y += 70
                    continue

                # Edit button (only for tiles)
                edit_button = pygame.Rect(item_rect.x + item_rect.width - 55, item_rect.y + 5, 50, 20)

                if edit_button.collidepoint(pos):
                    self.editing_tile_id = tile_id
                    self.show_property_editor = True
                    self.property_checkboxes = {prop.value: prop.value in tile_type.properties
                                               for prop in TileProperty}
                    return
                else:
                    self.current_tile_type_id = tile_id
                    return

                item_y += 70

        elif self.current_tab == EditorTab.ENEMIES:
            item_y = y_offset - self.scroll_offset
            for enemy_id, enemy_type in self.enemy_types.items():
                if item_y + 60 < content_area_top or item_y > content_area_top + content_area_height:
                    item_y += 70
                    continue

                item_rect = pygame.Rect(self.palette_rect.x + 10, item_y, self.palette_width - 20, 60)

                if not item_rect.collidepoint(pos):
                    item_y += 70
                    continue

                # Edit button
                edit_button = pygame.Rect(item_rect.x + item_rect.width - 55, item_rect.y + 5, 50, 20)

                if edit_button.collidepoint(pos):
                    self.editing_enemy_id = enemy_id
                    self.show_enemy_editor = True
                    # Initialize AI buttons
                    self.enemy_ai_buttons = {ai.value: ai.value == enemy_type.ai_type for ai in EnemyAI}
                    return
                else:
                    self.current_enemy_type_id = enemy_id
                    return

                item_y += 70

        elif self.current_tab == EditorTab.OBJECTS:
            item_y = y_offset - self.scroll_offset
            for collectible_id, collectible_type in self.collectible_types.items():
                if item_y + 60 < content_area_top or item_y > content_area_top + content_area_height:
                    item_y += 70
                    continue

                item_rect = pygame.Rect(self.palette_rect.x + 10, item_y, self.palette_width - 20, 60)

                if not item_rect.collidepoint(pos):
                    item_y += 70
                    continue

                # Edit button
                edit_button = pygame.Rect(item_rect.x + item_rect.width - 55, item_rect.y + 5, 50, 20)

                if edit_button.collidepoint(pos):
                    self.editing_collectible_id = collectible_id
                    self.show_collectible_editor = True
                    # Initialize effect buttons
                    self.collectible_effect_buttons = {effect.value: effect.value == collectible_type.effect for effect in CollectibleEffect}
                    return
                else:
                    self.current_collectible_type_id = collectible_id
                    return

                item_y += 70

        else:  # BACKGROUND tab
            # Handle layer selection buttons
            layer_y = y_offset - self.scroll_offset
            for layer_idx in range(4):
                layer_button = pygame.Rect(self.palette_rect.x + 10, layer_y, self.palette_width - 20, 30)
                if layer_button.collidepoint(pos):
                    self.current_bg_layer = layer_idx
                    return
                layer_y += 35

            layer_y += 10  # Gap after layer buttons
            layer_y += 20  # "Images in Layer X:" text

            # Handle clicks on background images
            layer_images = [img for img in self.background_layers if img.layer_index == self.current_bg_layer]

            # Add space for hint text (matches drawing code)
            if layer_images:
                layer_y += 18  # "Click to select image" hint

            for idx, bg_img in enumerate(layer_images):
                bg_img_idx = self.background_layers.index(bg_img)
                item_rect = pygame.Rect(self.palette_rect.x + 10, layer_y, self.palette_width - 20, 60)

                if not item_rect.collidepoint(pos):
                    layer_y += 65
                    continue

                # Delete button
                del_button = pygame.Rect(item_rect.x + item_rect.width - 25, item_rect.y + 5, 20, 20)
                if del_button.collidepoint(pos):
                    self.background_layers.pop(bg_img_idx)
                    if self.selected_bg_image_index == bg_img_idx:
                        self.selected_bg_image_index = None
                    return

                # Repeat toggle buttons and aspect ratio lock
                repeat_x_btn = pygame.Rect(item_rect.x + 60, item_rect.y + 40, 35, 15)
                repeat_y_btn = pygame.Rect(item_rect.x + 100, item_rect.y + 40, 35, 15)
                aspect_lock_btn = pygame.Rect(item_rect.x + 140, item_rect.y + 40, 50, 15)

                if repeat_x_btn.collidepoint(pos):
                    bg_img.repeat_x = not bg_img.repeat_x
                    return

                if repeat_y_btn.collidepoint(pos):
                    bg_img.repeat_y = not bg_img.repeat_y
                    return

                if aspect_lock_btn.collidepoint(pos):
                    bg_img.aspect_ratio_locked = not bg_img.aspect_ratio_locked
                    return

                # Select this image and pan camera to show it
                self.selected_bg_image_index = bg_img_idx

                # Pan camera to center on this image
                center_x = bg_img.x + bg_img.width // 2
                center_y = bg_img.y + bg_img.height // 2
                self.camera_x = max(0, min(center_x - self.canvas_rect.width // 2,
                                           self.level_width * TILE_SIZE - self.canvas_rect.width))
                self.camera_y = max(0, min(center_y - self.canvas_rect.height // 2,
                                           self.level_height * TILE_SIZE - self.canvas_rect.height))
                return

                layer_y += 65
    
    def handle_property_editor_click(self, pos):
        """Handle clicks in the property editor dialog"""
        if self.editing_tile_id is None:
            return
        
        tile_type = self.tile_types.get(self.editing_tile_id)
        if not tile_type:
            return
        
        # Property editor is centered in palette
        editor_x = self.palette_rect.x + 20
        editor_y = 150
        editor_width = self.palette_width - 40
        
        # Close button
        close_button = pygame.Rect(editor_x + editor_width - 60, editor_y + 10, 50, 25)
        if close_button.collidepoint(pos):
            # Apply changes
            tile_type.properties = [prop for prop, checked in self.property_checkboxes.items() if checked]
            self.show_property_editor = False
            self.editing_tile_id = None
            self.input_active = False
            return
        
        # Match the draw function exactly
        y = editor_y + 45

        # Image preview label
        y += 20
        # Image preview (64px)
        y += 75  # Skip image + gap

        # Name field - match draw function exactly
        name_label_y = y
        y += 20
        name_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        if name_field.collidepoint(pos):
            self.input_active = True
            self.input_field = 'name'
            self.input_text = tile_type.name
            return
        y += 35

        # Color field - match draw function exactly
        color_label_y = y
        y += 20
        color_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        if color_field.collidepoint(pos):
            self.input_active = True
            self.input_field = 'color'
            self.input_text = f"{tile_type.color[0]},{tile_type.color[1]},{tile_type.color[2]}"
            return
        y += 35

        # Property checkboxes - match draw function exactly
        props_label_y = y
        y += 25
        for prop in TileProperty:
            checkbox_rect = pygame.Rect(editor_x + 10, y, 15, 15)
            if checkbox_rect.collidepoint(pos):
                self.property_checkboxes[prop.value] = not self.property_checkboxes.get(prop.value, False)
                return
            y += 25
    
    def handle_file_drop(self, filepath):
        """Handle file drop for adding new tiles, replacing tile images, or adding behavior scripts"""
        # Handle .py files for enemy behavior scripts
        if filepath.lower().endswith('.py'):
            if self.show_enemy_editor and self.editing_enemy_id is not None:
                enemy_type = self.enemy_types.get(self.editing_enemy_id)
                if enemy_type:
                    enemy_type.behavior_script = filepath
                    print(f"Added behavior script to {enemy_type.name}: {filepath}")
                return
            else:
                print("Drop .py files when enemy editor is open to add behavior scripts")
                return

        if not filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            return

        # Get mouse position to see where the file was dropped
        mouse_pos = pygame.mouse.get_pos()

        # Handle BACKGROUND tab - add image to current layer
        if self.current_tab == EditorTab.BACKGROUND:
            try:
                image = pygame.image.load(filepath)
                # Add to current layer at a default position
                # Calculate parallax factor: layer 0=0.1, 1=0.3, 2=0.5, 3=0.7
                parallax_factor = 0.1 + (self.current_bg_layer * 0.2)
                bg_img = BackgroundImage(
                    layer_index=self.current_bg_layer,
                    image_path=filepath,
                    image=image,
                    x=0,
                    y=0,
                    width=image.get_width(),
                    height=image.get_height(),
                    repeat_x=False,
                    repeat_y=False,
                    parallax_factor=parallax_factor,
                    aspect_ratio_locked=True
                )
                self.background_layers.append(bg_img)
                self.selected_bg_image_index = len(self.background_layers) - 1
                print(f"Added background image to layer {self.current_bg_layer}: {filepath}")
            except Exception as e:
                print(f"Error loading background image: {e}")
            return
        
        # If property editor is open and file dropped in palette area, update current editing tile
        if self.show_property_editor and self.editing_tile_id is not None and self.palette_rect.collidepoint(mouse_pos):
            tile_type = self.tile_types.get(self.editing_tile_id)
            if tile_type:
                try:
                    image = pygame.image.load(filepath)
                    image = pygame.transform.scale(image, (TILE_SIZE, TILE_SIZE))
                    tile_type.image = image
                    tile_type.image_path = filepath
                    print(f"Updated image for tile: {tile_type.name}")
                except Exception as e:
                    print(f"Error loading image: {e}")
                return
        
        # Check if dropped on a tile in the palette
        if self.palette_rect.collidepoint(mouse_pos):
            # Calculate which tile was dropped on
            y_offset = 10 + 25 + 60 + 10 + 20 + 20 + 20 + 25 + 35 + 40 + 25  # Match palette layout
            tile_area_top = y_offset
            
            tile_y = y_offset - self.scroll_offset
            for tile_id, tile_type in self.tile_types.items():
                # Skip if not visible
                if tile_y + 60 < tile_area_top or tile_y > SCREEN_HEIGHT - 100:
                    tile_y += 70
                    continue
                
                tile_rect = pygame.Rect(self.palette_rect.x + 10, tile_y, self.palette_width - 20, 60)
                
                if tile_rect.collidepoint(mouse_pos):
                    # Replace this tile's image
                    try:
                        image = pygame.image.load(filepath)
                        image = pygame.transform.scale(image, (TILE_SIZE, TILE_SIZE))
                        tile_type.image = image
                        tile_type.image_path = filepath
                        print(f"Updated image for tile: {tile_type.name}")
                    except Exception as e:
                        print(f"Error loading image: {e}")
                    return
                
                tile_y += 70
        
        # If not dropped on a tile, add as new tile
        name = Path(filepath).stem.replace('_', ' ').title()
        self.add_tile_type(name, filepath, [TileProperty.SOLID.value], GRAY)
        print(f"Added new tile: {name}")

    def select_behavior_script(self):
        """Open file dialog to select a .py behavior script"""
        # Create a hidden root window
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        # Open file dialog
        filepath = filedialog.askopenfilename(
            title="Select Behavior Script",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )

        root.destroy()

        if filepath and self.editing_enemy_id is not None:
            enemy_type = self.enemy_types.get(self.editing_enemy_id)
            if enemy_type:
                enemy_type.behavior_script = filepath
                print(f"Selected behavior script: {filepath}")

    def load_background_image(self):
        """Open file dialog to select a background image"""
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        filepath = filedialog.askopenfilename(
            title="Select Background Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")]
        )

        root.destroy()

        if filepath:
            try:
                self.background_image = pygame.image.load(filepath)
                self.background_image_path = filepath
                # Set initial size to image size
                self.background_width = self.background_image.get_width()
                self.background_height = self.background_image.get_height()
                self.background_x = 0
                self.background_y = 0
                print(f"Loaded background image: {filepath}")
            except Exception as e:
                print(f"Error loading background image: {e}")

    def draw_canvas(self):
        """Draw the main canvas area"""
        # Draw background
        self.screen.fill(DARK_GRAY, self.canvas_rect)

        # Draw background image if loaded (legacy, for TILES tab)
        if self.background_image and self.background_width > 0 and self.background_height > 0:
            screen_x = self.background_x - self.camera_x
            screen_y = self.background_y - self.camera_y
            scaled_bg = pygame.transform.scale(self.background_image, (self.background_width, self.background_height))
            self.screen.blit(scaled_bg, (screen_x, screen_y))

            # Draw resize handle (top-left corner)
            handle_size = 12
            pygame.draw.rect(self.screen, YELLOW, (screen_x, screen_y, handle_size, handle_size))
            pygame.draw.rect(self.screen, BLACK, (screen_x, screen_y, handle_size, handle_size), 1)

        # Draw background layers (new system, all 4 layers from far to near)
        for layer_idx in range(4):
            layer_images = [img for img in self.background_layers if img.layer_index == layer_idx]
            for bg_img in layer_images:
                screen_x = bg_img.x - self.camera_x
                screen_y = bg_img.y - self.camera_y

                if bg_img.repeat_x or bg_img.repeat_y:
                    # Calculate how many times to repeat
                    start_x = screen_x
                    start_y = screen_y

                    # For repeating, we need to tile the image
                    if bg_img.repeat_x and bg_img.repeat_y:
                        # Repeat in both directions
                        tile_x = start_x
                        while tile_x < self.canvas_rect.width:
                            tile_y = start_y
                            while tile_y < self.canvas_rect.height:
                                if tile_x + bg_img.width > 0 and tile_y + bg_img.height > 0:
                                    scaled_img = pygame.transform.scale(bg_img.image, (bg_img.width, bg_img.height))
                                    self.screen.blit(scaled_img, (tile_x, tile_y))
                                tile_y += bg_img.height
                            tile_x += bg_img.width
                    elif bg_img.repeat_x:
                        # Repeat horizontally only
                        tile_x = start_x
                        while tile_x < self.canvas_rect.width:
                            if tile_x + bg_img.width > 0 and screen_y + bg_img.height > 0 and screen_y < self.canvas_rect.height:
                                scaled_img = pygame.transform.scale(bg_img.image, (bg_img.width, bg_img.height))
                                self.screen.blit(scaled_img, (tile_x, screen_y))
                            tile_x += bg_img.width
                    elif bg_img.repeat_y:
                        # Repeat vertically only
                        tile_y = start_y
                        while tile_y < self.canvas_rect.height:
                            if screen_x + bg_img.width > 0 and screen_x < self.canvas_rect.width and tile_y + bg_img.height > 0:
                                scaled_img = pygame.transform.scale(bg_img.image, (bg_img.width, bg_img.height))
                                self.screen.blit(scaled_img, (screen_x, tile_y))
                            tile_y += bg_img.height
                else:
                    # No repeat, just draw once
                    if screen_x + bg_img.width > 0 and screen_y + bg_img.height > 0 and screen_x < self.canvas_rect.width and screen_y < self.canvas_rect.height:
                        scaled_img = pygame.transform.scale(bg_img.image, (bg_img.width, bg_img.height))
                        self.screen.blit(scaled_img, (screen_x, screen_y))

                # If this image is selected in BACKGROUND tab, draw handles
                if self.current_tab == EditorTab.BACKGROUND:
                    bg_img_idx = self.background_layers.index(bg_img)
                    if bg_img_idx == self.selected_bg_image_index:
                        # Draw selection border (THICK for easier clicking)
                        border_thickness = 8
                        pygame.draw.rect(self.screen, GREEN, (screen_x, screen_y, bg_img.width, bg_img.height), border_thickness)

                        # Draw resize handle (top-left corner, GREEN and LARGE)
                        handle_size = 24
                        pygame.draw.rect(self.screen, GREEN, (screen_x, screen_y, handle_size, handle_size))
                        pygame.draw.rect(self.screen, BLACK, (screen_x, screen_y, handle_size, handle_size), 2)

                        # Draw a cross in the handle to make it more obvious
                        pygame.draw.line(self.screen, BLACK,
                                       (screen_x + handle_size//4, screen_y + handle_size//2),
                                       (screen_x + 3*handle_size//4, screen_y + handle_size//2), 2)
                        pygame.draw.line(self.screen, BLACK,
                                       (screen_x + handle_size//2, screen_y + handle_size//4),
                                       (screen_x + handle_size//2, screen_y + 3*handle_size//4), 2)

        # Draw grid
        start_x = -(self.camera_x % TILE_SIZE)
        start_y = -(self.camera_y % TILE_SIZE)
        
        for x in range(start_x, self.canvas_rect.width, TILE_SIZE):
            pygame.draw.line(self.screen, (80, 80, 80), (x, 0), (x, self.canvas_rect.height))
        for y in range(start_y, self.canvas_rect.height, TILE_SIZE):
            pygame.draw.line(self.screen, (80, 80, 80), (0, y), (self.canvas_rect.width, y))
        
        # Draw tiles
        for layer in ['background', 'main', 'foreground']:
            if not self.layer_visibility[layer]:
                continue
            
            for (tile_x, tile_y), tile in self.tiles[layer].items():
                screen_x = tile_x * TILE_SIZE - self.camera_x
                screen_y = tile_y * TILE_SIZE - self.camera_y
                
                # Only draw if visible
                if -TILE_SIZE < screen_x < self.canvas_rect.width and -TILE_SIZE < screen_y < self.canvas_rect.height:
                    tile_type = self.tile_types.get(tile.tile_type_id)
                    if tile_type:
                        if tile_type.image:
                            self.screen.blit(tile_type.image, (screen_x, screen_y))
                        else:
                            pygame.draw.rect(self.screen, tile_type.color, 
                                           (screen_x, screen_y, TILE_SIZE, TILE_SIZE))
                        
                        # Draw semi-transparent overlay for non-main layers
                        if layer == 'background':
                            overlay = pygame.Surface((TILE_SIZE, TILE_SIZE))
                            overlay.set_alpha(128)
                            overlay.fill((0, 0, 100))
                            self.screen.blit(overlay, (screen_x, screen_y))
                        elif layer == 'foreground':
                            overlay = pygame.Surface((TILE_SIZE, TILE_SIZE))
                            overlay.set_alpha(128)
                            overlay.fill((100, 0, 0))
                            self.screen.blit(overlay, (screen_x, screen_y))
        
        # Draw preview tiles
        if self.preview_tiles and self.current_tile_type_id is not None:
            tile_type = self.tile_types.get(self.current_tile_type_id)
            if tile_type:
                for tile_x, tile_y in self.preview_tiles:
                    screen_x = tile_x * TILE_SIZE - self.camera_x
                    screen_y = tile_y * TILE_SIZE - self.camera_y
                    
                    if tile_type.image:
                        img = tile_type.image.copy()
                        img.set_alpha(128)
                        self.screen.blit(img, (screen_x, screen_y))
                    else:
                        surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
                        surf.set_alpha(128)
                        surf.fill(tile_type.color)
                        self.screen.blit(surf, (screen_x, screen_y))
        
        # Draw enemies
        for enemy in self.enemies:
            screen_x = enemy.x - self.camera_x
            screen_y = enemy.y - self.camera_y

            # Only draw if visible
            if -TILE_SIZE < screen_x < self.canvas_rect.width and -TILE_SIZE < screen_y < self.canvas_rect.height:
                enemy_type = self.enemy_types.get(enemy.enemy_type_id)
                if enemy_type:
                    if enemy_type.image:
                        self.screen.blit(enemy_type.image, (screen_x, screen_y))
                    else:
                        pygame.draw.rect(self.screen, enemy_type.color,
                                       (screen_x, screen_y, TILE_SIZE, TILE_SIZE))
                    # Draw border to indicate it's an enemy
                    pygame.draw.rect(self.screen, RED, (screen_x, screen_y, TILE_SIZE, TILE_SIZE), 2)

        # Draw collectibles
        for collectible in self.collectibles:
            screen_x = collectible.x - self.camera_x
            screen_y = collectible.y - self.camera_y

            # Only draw if visible
            if -TILE_SIZE < screen_x < self.canvas_rect.width and -TILE_SIZE < screen_y < self.canvas_rect.height:
                collectible_type = self.collectible_types.get(collectible.collectible_type_id)
                if collectible_type:
                    if collectible_type.image:
                        self.screen.blit(collectible_type.image, (screen_x, screen_y))
                    else:
                        pygame.draw.circle(self.screen, collectible_type.color,
                                         (screen_x + TILE_SIZE // 2, screen_y + TILE_SIZE // 2), TILE_SIZE // 2)
                    # Draw border to indicate it's a collectible
                    pygame.draw.circle(self.screen, YELLOW,
                                     (screen_x + TILE_SIZE // 2, screen_y + TILE_SIZE // 2), TILE_SIZE // 2, 2)

        # Draw viewport indicator (game camera preview) - thicker border for easier clicking
        viewport_screen_x = self.viewport_x - self.camera_x
        viewport_screen_y = self.viewport_y - self.camera_y
        pygame.draw.rect(self.screen, YELLOW, (viewport_screen_x, viewport_screen_y, self.viewport_width, self.viewport_height), 4)

        # Draw resize handle for viewport (top-left corner)
        handle_size = 12
        handle_x = viewport_screen_x
        handle_y = viewport_screen_y
        pygame.draw.rect(self.screen, YELLOW, (handle_x, handle_y, handle_size, handle_size))
        pygame.draw.rect(self.screen, BLACK, (handle_x, handle_y, handle_size, handle_size), 1)

        # Draw minimap
        self.draw_minimap()
    
    def draw_minimap(self):
        """Draw the minimap in the bottom-right corner of canvas"""
        minimap_width = 200
        minimap_height = 150
        minimap_x = self.canvas_rect.width - minimap_width - 10
        minimap_y = self.canvas_rect.height - minimap_height - 10
        
        # Background
        pygame.draw.rect(self.screen, BLACK, (minimap_x, minimap_y, minimap_width, minimap_height))
        pygame.draw.rect(self.screen, WHITE, (minimap_x, minimap_y, minimap_width, minimap_height), 1)
        
        # Scale
        scale_x = minimap_width / (self.level_width * TILE_SIZE)
        scale_y = minimap_height / (self.level_height * TILE_SIZE)
        
        # Draw tiles on minimap
        for layer in ['background', 'main', 'foreground']:
            if not self.layer_visibility[layer]:
                continue
            for (tile_x, tile_y), tile in self.tiles[layer].items():
                x = minimap_x + int(tile_x * TILE_SIZE * scale_x)
                y = minimap_y + int(tile_y * TILE_SIZE * scale_y)
                size = max(1, int(TILE_SIZE * scale_x))
                
                tile_type = self.tile_types.get(tile.tile_type_id)
                if tile_type:
                    color = tile_type.color
                    pygame.draw.rect(self.screen, color, (x, y, size, size))
        
        # Draw camera view rectangle
        cam_x = minimap_x + int(self.camera_x * scale_x)
        cam_y = minimap_y + int(self.camera_y * scale_y)
        cam_w = int(self.canvas_rect.width * scale_x)
        cam_h = int(self.canvas_rect.height * scale_y)
        pygame.draw.rect(self.screen, RED, (cam_x, cam_y, cam_w, cam_h), 1)
        
        # Draw viewport indicator
        viewport_minimap_x = minimap_x + int(self.viewport_x * scale_x)
        viewport_minimap_y = minimap_y + int(self.viewport_y * scale_y)
        viewport_w = int(self.viewport_width * scale_x)
        viewport_h = int(self.viewport_height * scale_y)
        pygame.draw.rect(self.screen, YELLOW, (viewport_minimap_x, viewport_minimap_y, viewport_w, viewport_h), 1)
    
    def draw_palette(self):
        """Draw the tile palette"""
        # Background
        self.screen.fill(LIGHT_GRAY, self.palette_rect)
        pygame.draw.line(self.screen, BLACK, (self.palette_rect.x, 0),
                        (self.palette_rect.x, SCREEN_HEIGHT), 2)

        # Tab buttons (4 tabs in 2 rows)
        y_offset = 10
        tab_width = (self.palette_width - 40) // 2
        tab_height = 25
        tab_x = self.palette_rect.x + 10

        tabs = [EditorTab.TILES, EditorTab.ENEMIES, EditorTab.OBJECTS, EditorTab.BACKGROUND]
        for i, tab in enumerate(tabs):
            row = i // 2
            col = i % 2
            tab_rect = pygame.Rect(tab_x + col * (tab_width + 5), y_offset + row * (tab_height + 5), tab_width, tab_height)

            # Draw button
            if self.current_tab == tab:
                pygame.draw.rect(self.screen, BLUE, tab_rect)
            else:
                pygame.draw.rect(self.screen, WHITE, tab_rect)
            pygame.draw.rect(self.screen, BLACK, tab_rect, 2)

            # Draw text
            tab_text = self.small_font.render(tab.value.title(), True, BLACK)
            text_rect = tab_text.get_rect(center=tab_rect.center)
            self.screen.blit(tab_text, text_rect)

        y_offset += 65

        # Only show layer toggles for tiles tab
        if self.current_tab == EditorTab.TILES:
            text = self.font.render("Layers:", True, BLACK)
            self.screen.blit(text, (self.palette_rect.x + 10, y_offset))
            y_offset += 25

            for layer in ['background', 'main', 'foreground']:
                # Checkbox
                checkbox_rect = pygame.Rect(self.palette_rect.x + 10, y_offset, 15, 15)
                pygame.draw.rect(self.screen, WHITE, checkbox_rect)
                pygame.draw.rect(self.screen, BLACK, checkbox_rect, 1)
                if self.layer_visibility[layer]:
                    pygame.draw.line(self.screen, BLACK, checkbox_rect.topleft, checkbox_rect.bottomright, 2)
                    pygame.draw.line(self.screen, BLACK, checkbox_rect.topright, checkbox_rect.bottomleft, 2)

                # Label
                color = BLACK if layer == self.current_layer else DARK_GRAY
                text = self.small_font.render(layer.title(), True, color)
                self.screen.blit(text, (self.palette_rect.x + 30, y_offset))
                y_offset += 20

            y_offset += 10

        # Tool selection (only for tiles)
        if self.current_tab == EditorTab.TILES:
            text = self.font.render(f"Tool: {self.current_tool.value.title()}", True, BLACK)
            self.screen.blit(text, (self.palette_rect.x + 10, y_offset))
            y_offset += 20

            text = self.small_font.render("P:Pencil R:Rect L:Line E:Erase", True, DARK_GRAY)
            self.screen.blit(text, (self.palette_rect.x + 10, y_offset))
            y_offset += 20

            # Level size controls
            text = self.small_font.render(f"Level: {self.level_width}x{self.level_height}", True, BLACK)
            self.screen.blit(text, (self.palette_rect.x + 10, y_offset))
            y_offset += 20

            # Resize buttons
            resize_button_width = (self.palette_width - 30) // 2
            wider_button = pygame.Rect(self.palette_rect.x + 10, y_offset, resize_button_width, 25)
            narrower_button = pygame.Rect(self.palette_rect.x + 15 + resize_button_width, y_offset, resize_button_width, 25)

            pygame.draw.rect(self.screen, GREEN, wider_button)
            pygame.draw.rect(self.screen, BLACK, wider_button, 1)
            pygame.draw.rect(self.screen, RED, narrower_button)
            pygame.draw.rect(self.screen, BLACK, narrower_button, 1)

            wider_text = self.small_font.render("Wider", True, BLACK)
            narrower_text = self.small_font.render("Narrower", True, BLACK)
            self.screen.blit(wider_text, (wider_button.x + 15, wider_button.y + 5))
            self.screen.blit(narrower_text, (narrower_button.x + 5, narrower_button.y + 5))

            y_offset += 35

            # Background image button
            bg_button = pygame.Rect(self.palette_rect.x + 10, y_offset, self.palette_width - 20, 25)
            pygame.draw.rect(self.screen, BLUE if self.background_image else WHITE, bg_button)
            pygame.draw.rect(self.screen, BLACK, bg_button, 1)
            bg_text = self.small_font.render("Load Background Image", True, BLACK)
            bg_text_rect = bg_text.get_rect(center=bg_button.center)
            self.screen.blit(bg_text, bg_text_rect)

            y_offset += 35

        # Plus button to add new items
        plus_button = pygame.Rect(self.palette_rect.x + 10, y_offset, self.palette_width - 20, 30)
        pygame.draw.rect(self.screen, GREEN, plus_button)
        pygame.draw.rect(self.screen, BLACK, plus_button, 2)

        if self.current_tab == EditorTab.TILES:
            plus_text = self.font.render("+ Add New Tile", True, BLACK)
        elif self.current_tab == EditorTab.ENEMIES:
            plus_text = self.font.render("+ Add New Enemy", True, BLACK)
        elif self.current_tab == EditorTab.OBJECTS:
            plus_text = self.font.render("+ Add New Object", True, BLACK)
        else:  # BACKGROUND
            plus_text = self.font.render("Drag & Drop Images", True, BLACK)

        text_rect = plus_text.get_rect(center=plus_button.center)
        self.screen.blit(plus_text, text_rect)

        y_offset += 40

        # Section header
        if self.current_tab == EditorTab.TILES:
            text = self.font.render("Tiles:", True, BLACK)
        elif self.current_tab == EditorTab.ENEMIES:
            text = self.font.render("Enemy Types:", True, BLACK)
        elif self.current_tab == EditorTab.OBJECTS:
            text = self.font.render("Collectibles:", True, BLACK)
        else:  # BACKGROUND
            text = self.font.render("Background Layers:", True, BLACK)

        self.screen.blit(text, (self.palette_rect.x + 10, y_offset))
        y_offset += 25
        
        # Create clip rect for scrollable area
        content_area_top = y_offset
        content_area_height = SCREEN_HEIGHT - y_offset - 100  # Leave room for instructions

        # Draw border around content area
        content_area_rect = pygame.Rect(self.palette_rect.x, content_area_top, self.palette_width, content_area_height)
        pygame.draw.rect(self.screen, DARK_GRAY, content_area_rect, 2)

        # Set clipping rectangle to prevent overflow
        clip_rect = pygame.Rect(self.palette_rect.x, content_area_top, self.palette_width, content_area_height)
        self.screen.set_clip(clip_rect)

        # Draw content based on current tab
        if self.current_tab == EditorTab.TILES:
            # Calculate total height needed
            total_height = len(self.tile_types) * 70
            self.max_scroll = max(0, total_height - content_area_height)

            # Draw tiles (scrollable)
            item_y = y_offset - self.scroll_offset
            for tile_id, tile_type in self.tile_types.items():
                # Only draw if visible in clip area
                if item_y + 60 < content_area_top or item_y > content_area_top + content_area_height:
                    item_y += 70
                    continue

                # Tile preview
                item_rect = pygame.Rect(self.palette_rect.x + 10, item_y, self.palette_width - 20, 60)

                # Highlight if selected
                if tile_id == self.current_tile_type_id:
                    pygame.draw.rect(self.screen, BLUE, item_rect, 3)
                else:
                    pygame.draw.rect(self.screen, DARK_GRAY, item_rect, 1)

                # Draw tile preview
                preview_rect = pygame.Rect(item_rect.x + 5, item_rect.y + 5, 32, 32)
                if tile_type.image:
                    scaled_img = pygame.transform.scale(tile_type.image, (32, 32))
                    self.screen.blit(scaled_img, preview_rect.topleft)
                else:
                    pygame.draw.rect(self.screen, tile_type.color, preview_rect)
                pygame.draw.rect(self.screen, BLACK, preview_rect, 1)

                # Name
                name_text = self.small_font.render(tile_type.name[:15], True, BLACK)
                self.screen.blit(name_text, (item_rect.x + 45, item_rect.y + 5))

                # Properties
                props_text = self.small_font.render(", ".join(tile_type.properties[:2]), True, DARK_GRAY)
                self.screen.blit(props_text, (item_rect.x + 45, item_rect.y + 25))

                # Edit button
                edit_button = pygame.Rect(item_rect.x + item_rect.width - 55, item_rect.y + 5, 50, 20)
                pygame.draw.rect(self.screen, YELLOW, edit_button)
                pygame.draw.rect(self.screen, BLACK, edit_button, 1)
                edit_text = self.small_font.render("Edit", True, BLACK)
                self.screen.blit(edit_text, (edit_button.x + 10, edit_button.y + 2))

                item_y += 70

        elif self.current_tab == EditorTab.ENEMIES:
            # Calculate total height needed
            total_height = len(self.enemy_types) * 70
            self.max_scroll = max(0, total_height - content_area_height)

            # Draw enemy types (scrollable)
            item_y = y_offset - self.scroll_offset
            for enemy_id, enemy_type in self.enemy_types.items():
                # Only draw if visible
                if item_y + 60 < content_area_top or item_y > content_area_top + content_area_height:
                    item_y += 70
                    continue

                item_rect = pygame.Rect(self.palette_rect.x + 10, item_y, self.palette_width - 20, 60)

                # Highlight if selected
                if enemy_id == self.current_enemy_type_id:
                    pygame.draw.rect(self.screen, BLUE, item_rect, 3)
                else:
                    pygame.draw.rect(self.screen, DARK_GRAY, item_rect, 1)

                # Draw enemy preview
                preview_rect = pygame.Rect(item_rect.x + 5, item_rect.y + 5, 32, 32)
                if enemy_type.image:
                    scaled_img = pygame.transform.scale(enemy_type.image, (32, 32))
                    self.screen.blit(scaled_img, preview_rect.topleft)
                else:
                    pygame.draw.rect(self.screen, enemy_type.color, preview_rect)
                pygame.draw.rect(self.screen, BLACK, preview_rect, 1)

                # Name with required marker
                name_display = enemy_type.name[:15]
                if enemy_type.required:
                    name_display += " [REQ]"
                name_text = self.small_font.render(name_display, True, BLACK)
                self.screen.blit(name_text, (item_rect.x + 45, item_rect.y + 5))

                # Stats
                stats_text = self.small_font.render(f"HP:{enemy_type.health} DMG:{enemy_type.damage}", True, DARK_GRAY)
                self.screen.blit(stats_text, (item_rect.x + 45, item_rect.y + 25))

                # Edit button
                edit_button = pygame.Rect(item_rect.x + item_rect.width - 55, item_rect.y + 5, 50, 20)
                pygame.draw.rect(self.screen, YELLOW, edit_button)
                pygame.draw.rect(self.screen, BLACK, edit_button, 1)
                edit_text = self.small_font.render("Edit", True, BLACK)
                self.screen.blit(edit_text, (edit_button.x + 10, edit_button.y + 2))

                item_y += 70

        elif self.current_tab == EditorTab.OBJECTS:
            # Calculate total height needed
            total_height = len(self.collectible_types) * 70
            self.max_scroll = max(0, total_height - content_area_height)

            # Draw collectible types (scrollable)
            item_y = y_offset - self.scroll_offset
            for collectible_id, collectible_type in self.collectible_types.items():
                # Only draw if visible
                if item_y + 60 < content_area_top or item_y > content_area_top + content_area_height:
                    item_y += 70
                    continue

                item_rect = pygame.Rect(self.palette_rect.x + 10, item_y, self.palette_width - 20, 60)

                # Highlight if selected
                if collectible_id == self.current_collectible_type_id:
                    pygame.draw.rect(self.screen, BLUE, item_rect, 3)
                else:
                    pygame.draw.rect(self.screen, DARK_GRAY, item_rect, 1)

                # Draw collectible preview
                preview_rect = pygame.Rect(item_rect.x + 5, item_rect.y + 5, 32, 32)
                if collectible_type.image:
                    scaled_img = pygame.transform.scale(collectible_type.image, (32, 32))
                    self.screen.blit(scaled_img, preview_rect.topleft)
                else:
                    # Draw circle for collectibles
                    pygame.draw.circle(self.screen, collectible_type.color,
                                     (preview_rect.centerx, preview_rect.centery), 14)
                pygame.draw.rect(self.screen, BLACK, preview_rect, 1)

                # Name
                name_text = self.small_font.render(collectible_type.name[:15], True, BLACK)
                self.screen.blit(name_text, (item_rect.x + 45, item_rect.y + 5))

                # Effect - show required marker
                req_marker = "[REQ] " if collectible_type.required else ""
                effect_text = self.small_font.render(f"{req_marker}{collectible_type.effect}: +{collectible_type.value}", True, DARK_GRAY)
                self.screen.blit(effect_text, (item_rect.x + 45, item_rect.y + 25))

                # Edit button
                edit_button = pygame.Rect(item_rect.x + item_rect.width - 55, item_rect.y + 5, 50, 20)
                pygame.draw.rect(self.screen, YELLOW, edit_button)
                pygame.draw.rect(self.screen, BLACK, edit_button, 1)
                edit_text = self.small_font.render("Edit", True, BLACK)
                self.screen.blit(edit_text, (edit_button.x + 10, edit_button.y + 2))

                item_y += 70

        else:  # BACKGROUND tab
            # Draw layer selection buttons
            layer_y = y_offset - self.scroll_offset
            layer_names = ["Layer 1 (Far)", "Layer 2", "Layer 3", "Layer 4 (Near)"]

            for layer_idx in range(4):
                layer_button = pygame.Rect(self.palette_rect.x + 10, layer_y, self.palette_width - 20, 30)

                # Highlight if selected
                if layer_idx == self.current_bg_layer:
                    pygame.draw.rect(self.screen, BLUE, layer_button)
                else:
                    pygame.draw.rect(self.screen, WHITE, layer_button)
                pygame.draw.rect(self.screen, BLACK, layer_button, 2)

                # Layer name
                layer_text = self.small_font.render(layer_names[layer_idx], True, BLACK)
                self.screen.blit(layer_text, (layer_button.x + 10, layer_button.y + 8))

                # Count images in this layer
                layer_images = [img for img in self.background_layers if img.layer_index == layer_idx]
                count_text = self.small_font.render(f"({len(layer_images)} images)", True, DARK_GRAY)
                self.screen.blit(count_text, (layer_button.x + layer_button.width - 80, layer_button.y + 8))

                layer_y += 35

            layer_y += 10

            # Show images in selected layer
            text = self.small_font.render(f"Images in {layer_names[self.current_bg_layer]}:", True, BLACK)
            self.screen.blit(text, (self.palette_rect.x + 10, layer_y))
            layer_y += 20

            layer_images = [img for img in self.background_layers if img.layer_index == self.current_bg_layer]

            # Show helpful hint
            if layer_images:
                hint = self.small_font.render("Click to select image", True, DARK_GRAY)
                self.screen.blit(hint, (self.palette_rect.x + 10, layer_y))
                layer_y += 18

            if not layer_images:
                hint_text = self.small_font.render("Drag & drop images here", True, DARK_GRAY)
                self.screen.blit(hint_text, (self.palette_rect.x + 10, layer_y))
                layer_y += 18
                hint_text2 = self.small_font.render("Then click to select", True, DARK_GRAY)
                self.screen.blit(hint_text2, (self.palette_rect.x + 10, layer_y))
                layer_y += 18
                hint_text3 = self.small_font.render("Canvas: L=Move R=Resize", True, DARK_GRAY)
                self.screen.blit(hint_text3, (self.palette_rect.x + 10, layer_y))
            else:
                for idx, bg_img in enumerate(layer_images):
                    bg_img_idx = self.background_layers.index(bg_img)
                    item_rect = pygame.Rect(self.palette_rect.x + 10, layer_y, self.palette_width - 20, 60)

                    # Highlight if selected
                    if bg_img_idx == self.selected_bg_image_index:
                        pygame.draw.rect(self.screen, BLUE, item_rect, 3)
                    else:
                        pygame.draw.rect(self.screen, DARK_GRAY, item_rect, 1)

                    # Preview
                    preview_rect = pygame.Rect(item_rect.x + 5, item_rect.y + 5, 50, 50)
                    if bg_img.image:
                        # Scale image to fit preview
                        aspect = bg_img.image.get_width() / bg_img.image.get_height()
                        if aspect > 1:
                            preview_w = 50
                            preview_h = int(50 / aspect)
                        else:
                            preview_h = 50
                            preview_w = int(50 * aspect)
                        scaled_img = pygame.transform.scale(bg_img.image, (preview_w, preview_h))
                        center_x = preview_rect.x + (50 - preview_w) // 2
                        center_y = preview_rect.y + (50 - preview_h) // 2
                        self.screen.blit(scaled_img, (center_x, center_y))
                    pygame.draw.rect(self.screen, BLACK, preview_rect, 1)

                    # Image info
                    filename = os.path.basename(bg_img.image_path)[:12]
                    name_text = self.small_font.render(filename, True, BLACK)
                    self.screen.blit(name_text, (item_rect.x + 60, item_rect.y + 5))

                    # Repeat info
                    repeat_str = ""
                    if bg_img.repeat_x and bg_img.repeat_y:
                        repeat_str = "Repeat: X+Y"
                    elif bg_img.repeat_x:
                        repeat_str = "Repeat: X"
                    elif bg_img.repeat_y:
                        repeat_str = "Repeat: Y"
                    else:
                        repeat_str = "No repeat"

                    repeat_text = self.small_font.render(repeat_str, True, DARK_GRAY)
                    self.screen.blit(repeat_text, (item_rect.x + 60, item_rect.y + 25))

                    # Repeat toggle buttons and aspect ratio lock
                    repeat_x_btn = pygame.Rect(item_rect.x + 60, item_rect.y + 40, 35, 15)
                    repeat_y_btn = pygame.Rect(item_rect.x + 100, item_rect.y + 40, 35, 15)
                    aspect_lock_btn = pygame.Rect(item_rect.x + 140, item_rect.y + 40, 50, 15)

                    # Repeat X button
                    pygame.draw.rect(self.screen, BLUE if bg_img.repeat_x else WHITE, repeat_x_btn)
                    pygame.draw.rect(self.screen, BLACK, repeat_x_btn, 1)
                    rx_text = self.small_font.render("Rep X", True, BLACK)
                    self.screen.blit(rx_text, (repeat_x_btn.x + 2, repeat_x_btn.y + 1))

                    # Repeat Y button
                    pygame.draw.rect(self.screen, BLUE if bg_img.repeat_y else WHITE, repeat_y_btn)
                    pygame.draw.rect(self.screen, BLACK, repeat_y_btn, 1)
                    ry_text = self.small_font.render("Rep Y", True, BLACK)
                    self.screen.blit(ry_text, (repeat_y_btn.x + 2, repeat_y_btn.y + 1))

                    # Aspect ratio lock button
                    pygame.draw.rect(self.screen, BLUE if bg_img.aspect_ratio_locked else WHITE, aspect_lock_btn)
                    pygame.draw.rect(self.screen, BLACK, aspect_lock_btn, 1)
                    ar_text = self.small_font.render("Lock AR", True, BLACK)
                    self.screen.blit(ar_text, (aspect_lock_btn.x + 2, aspect_lock_btn.y + 1))

                    # Delete button
                    del_button = pygame.Rect(item_rect.x + item_rect.width - 25, item_rect.y + 5, 20, 20)
                    pygame.draw.rect(self.screen, RED, del_button)
                    pygame.draw.rect(self.screen, BLACK, del_button, 1)
                    del_text = self.small_font.render("X", True, WHITE)
                    self.screen.blit(del_text, (del_button.x + 5, del_button.y + 2))

                    layer_y += 65

            self.max_scroll = 0  # No scrolling needed for background tab

        # Reset clipping
        self.screen.set_clip(None)

        # Draw property editor if open
        if self.show_property_editor and self.editing_tile_id is not None:
            self.draw_property_editor()

        # Draw enemy editor if open
        if self.show_enemy_editor and self.editing_enemy_id is not None:
            self.draw_enemy_editor()

        # Draw collectible editor if open
        if self.show_collectible_editor and self.editing_collectible_id is not None:
            self.draw_collectible_editor()

        # Instructions at bottom
        instructions = [
            "Ctrl+S: Save",
            "Ctrl+O: Load",
            "1/2/3: Switch Layer",
            "Middle Click: Pan",
            "Ctrl+Scroll: Pan H"
        ]
        inst_y = SCREEN_HEIGHT - len(instructions) * 18 - 10
        for inst in instructions:
            text = self.small_font.render(inst, True, DARK_GRAY)
            self.screen.blit(text, (self.palette_rect.x + 10, inst_y))
            inst_y += 18
    
    def draw_property_editor(self):
        """Draw the property editor dialog"""
        if self.editing_tile_id is None:
            return
        
        tile_type = self.tile_types.get(self.editing_tile_id)
        if not tile_type:
            return
        
        # Semi-transparent overlay
        overlay = pygame.Surface((self.palette_width, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(LIGHT_GRAY)
        self.screen.blit(overlay, (self.palette_rect.x, 0))
        
        # Editor box
        editor_x = self.palette_rect.x + 20
        editor_y = 150
        editor_width = self.palette_width - 40
        editor_height = 450
        
        pygame.draw.rect(self.screen, WHITE, (editor_x, editor_y, editor_width, editor_height))
        pygame.draw.rect(self.screen, BLACK, (editor_x, editor_y, editor_width, editor_height), 2)
        
        # Title
        title = self.font.render("Edit Tile Properties", True, BLACK)
        self.screen.blit(title, (editor_x + 10, editor_y + 10))
        
        # Close button
        close_button = pygame.Rect(editor_x + editor_width - 60, editor_y + 10, 50, 25)
        pygame.draw.rect(self.screen, RED, close_button)
        pygame.draw.rect(self.screen, BLACK, close_button, 1)
        close_text = self.small_font.render("Close", True, BLACK)
        self.screen.blit(close_text, (close_button.x + 8, close_button.y + 5))
        
        y = editor_y + 45
        
        # Image preview with upload hint
        preview_label = self.small_font.render("Image (drag file here):", True, BLACK)
        self.screen.blit(preview_label, (editor_x + 10, y))
        y += 20
        
        preview_rect = pygame.Rect(editor_x + 10, y, 64, 64)
        if tile_type.image:
            scaled_img = pygame.transform.scale(tile_type.image, (64, 64))
            self.screen.blit(scaled_img, preview_rect.topleft)
        else:
            pygame.draw.rect(self.screen, tile_type.color, preview_rect)
        pygame.draw.rect(self.screen, BLACK, preview_rect, 2)
        y += 75
        
        # Name field
        name_label = self.small_font.render("Name:", True, BLACK)
        self.screen.blit(name_label, (editor_x + 10, y))
        y += 20
        
        name_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        pygame.draw.rect(self.screen, WHITE if not (self.input_active and self.input_field == 'name') else YELLOW, 
                        name_field)
        pygame.draw.rect(self.screen, BLACK, name_field, 1)
        name_text = self.small_font.render(
            self.input_text if (self.input_active and self.input_field == 'name') else tile_type.name,
            True, BLACK
        )
        self.screen.blit(name_text, (name_field.x + 5, name_field.y + 5))
        y += 35
        
        # Color field
        color_label = self.small_font.render("Color (R,G,B):", True, BLACK)
        self.screen.blit(color_label, (editor_x + 10, y))
        y += 20
        
        color_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        pygame.draw.rect(self.screen, WHITE if not (self.input_active and self.input_field == 'color') else YELLOW,
                        color_field)
        pygame.draw.rect(self.screen, BLACK, color_field, 1)
        color_display = self.input_text if (self.input_active and self.input_field == 'color') else \
                       f"{tile_type.color[0]},{tile_type.color[1]},{tile_type.color[2]}"
        color_text = self.small_font.render(color_display, True, BLACK)
        self.screen.blit(color_text, (color_field.x + 5, color_field.y + 5))
        y += 35
        
        # Properties checkboxes
        props_label = self.font.render("Properties:", True, BLACK)
        self.screen.blit(props_label, (editor_x + 10, y))
        y += 25
        
        for prop in TileProperty:
            checkbox_rect = pygame.Rect(editor_x + 10, y, 15, 15)
            pygame.draw.rect(self.screen, WHITE, checkbox_rect)
            pygame.draw.rect(self.screen, BLACK, checkbox_rect, 1)
            
            if self.property_checkboxes.get(prop.value, False):
                pygame.draw.line(self.screen, BLACK, checkbox_rect.topleft, checkbox_rect.bottomright, 2)
                pygame.draw.line(self.screen, BLACK, checkbox_rect.topright, checkbox_rect.bottomleft, 2)
            
            prop_text = self.small_font.render(prop.value.title(), True, BLACK)
            self.screen.blit(prop_text, (editor_x + 30, y))
            y += 25

    def draw_enemy_editor(self):
        """Draw the enemy editor dialog"""
        if self.editing_enemy_id is None:
            return

        enemy_type = self.enemy_types.get(self.editing_enemy_id)
        if not enemy_type:
            return

        # Semi-transparent overlay
        overlay = pygame.Surface((self.palette_width, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(LIGHT_GRAY)
        self.screen.blit(overlay, (self.palette_rect.x, 0))

        # Editor box
        editor_x = self.palette_rect.x + 20
        editor_y = 100
        editor_width = self.palette_width - 40
        editor_height = 550

        pygame.draw.rect(self.screen, WHITE, (editor_x, editor_y, editor_width, editor_height))
        pygame.draw.rect(self.screen, BLACK, (editor_x, editor_y, editor_width, editor_height), 2)

        # Title
        title = self.font.render("Edit Enemy", True, BLACK)
        self.screen.blit(title, (editor_x + 10, editor_y + 10))

        # Close button
        close_button = pygame.Rect(editor_x + editor_width - 60, editor_y + 10, 50, 25)
        pygame.draw.rect(self.screen, RED, close_button)
        pygame.draw.rect(self.screen, BLACK, close_button, 1)
        close_text = self.small_font.render("Close", True, BLACK)
        self.screen.blit(close_text, (close_button.x + 8, close_button.y + 5))

        y = editor_y + 45

        # Name field
        name_label = self.small_font.render("Name:", True, BLACK)
        self.screen.blit(name_label, (editor_x + 10, y))
        y += 20
        name_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        pygame.draw.rect(self.screen, WHITE if not (self.input_active and self.input_field == 'name') else YELLOW, name_field)
        pygame.draw.rect(self.screen, BLACK, name_field, 1)
        name_text = self.small_font.render(self.input_text if (self.input_active and self.input_field == 'name') else enemy_type.name, True, BLACK)
        self.screen.blit(name_text, (name_field.x + 5, name_field.y + 5))
        y += 35

        # Health field
        health_label = self.small_font.render("Health:", True, BLACK)
        self.screen.blit(health_label, (editor_x + 10, y))
        y += 20
        health_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        pygame.draw.rect(self.screen, WHITE if not (self.input_active and self.input_field == 'health') else YELLOW, health_field)
        pygame.draw.rect(self.screen, BLACK, health_field, 1)
        health_text = self.small_font.render(self.input_text if (self.input_active and self.input_field == 'health') else str(enemy_type.health), True, BLACK)
        self.screen.blit(health_text, (health_field.x + 5, health_field.y + 5))
        y += 35

        # Damage field
        damage_label = self.small_font.render("Damage:", True, BLACK)
        self.screen.blit(damage_label, (editor_x + 10, y))
        y += 20
        damage_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        pygame.draw.rect(self.screen, WHITE if not (self.input_active and self.input_field == 'damage') else YELLOW, damage_field)
        pygame.draw.rect(self.screen, BLACK, damage_field, 1)
        damage_text = self.small_font.render(self.input_text if (self.input_active and self.input_field == 'damage') else str(enemy_type.damage), True, BLACK)
        self.screen.blit(damage_text, (damage_field.x + 5, damage_field.y + 5))
        y += 35

        # Speed field
        speed_label = self.small_font.render("Speed:", True, BLACK)
        self.screen.blit(speed_label, (editor_x + 10, y))
        y += 20
        speed_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        pygame.draw.rect(self.screen, WHITE if not (self.input_active and self.input_field == 'speed') else YELLOW, speed_field)
        pygame.draw.rect(self.screen, BLACK, speed_field, 1)
        speed_text = self.small_font.render(self.input_text if (self.input_active and self.input_field == 'speed') else str(enemy_type.speed), True, BLACK)
        self.screen.blit(speed_text, (speed_field.x + 5, speed_field.y + 5))
        y += 35

        # Color field
        color_label = self.small_font.render("Color (R,G,B):", True, BLACK)
        self.screen.blit(color_label, (editor_x + 10, y))
        y += 20
        color_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        pygame.draw.rect(self.screen, WHITE if not (self.input_active and self.input_field == 'color') else YELLOW, color_field)
        pygame.draw.rect(self.screen, BLACK, color_field, 1)
        color_display = self.input_text if (self.input_active and self.input_field == 'color') else f"{enemy_type.color[0]},{enemy_type.color[1]},{enemy_type.color[2]}"
        color_text = self.small_font.render(color_display, True, BLACK)
        self.screen.blit(color_text, (color_field.x + 5, color_field.y + 5))
        y += 35

        # AI Type buttons
        ai_label = self.font.render("AI Type:", True, BLACK)
        self.screen.blit(ai_label, (editor_x + 10, y))
        y += 25
        for ai in EnemyAI:
            ai_button = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
            is_selected = self.enemy_ai_buttons.get(ai.value, False)
            pygame.draw.rect(self.screen, BLUE if is_selected else WHITE, ai_button)
            pygame.draw.rect(self.screen, BLACK, ai_button, 1)
            ai_text = self.small_font.render(ai.value.title(), True, BLACK)
            self.screen.blit(ai_text, (ai_button.x + 5, ai_button.y + 5))
            y += 30

        # Behavior script section
        script_label = self.small_font.render("Behavior Script:", True, BLACK)
        self.screen.blit(script_label, (editor_x + 10, y))
        y += 20

        # Display current script path
        script_display = enemy_type.behavior_script if enemy_type.behavior_script else "None"
        if enemy_type.behavior_script:
            # Show just the filename if path is too long
            script_filename = os.path.basename(enemy_type.behavior_script)
            script_text = self.small_font.render(script_filename[:30], True, BLACK)
        else:
            script_text = self.small_font.render("None (drag .py file or click Select)", True, DARK_GRAY)
        self.screen.blit(script_text, (editor_x + 10, y))
        y += 25

        # Select file button
        select_button = pygame.Rect(editor_x + 10, y, 100, 25)
        pygame.draw.rect(self.screen, GREEN, select_button)
        pygame.draw.rect(self.screen, BLACK, select_button, 1)
        select_text = self.small_font.render("Select File", True, BLACK)
        self.screen.blit(select_text, (select_button.x + 10, select_button.y + 5))

        # Clear button (only show if a script is set)
        if enemy_type.behavior_script:
            clear_button = pygame.Rect(editor_x + 120, y, 80, 25)
            pygame.draw.rect(self.screen, RED, clear_button)
            pygame.draw.rect(self.screen, BLACK, clear_button, 1)
            clear_text = self.small_font.render("Clear", True, BLACK)
            self.screen.blit(clear_text, (clear_button.x + 20, clear_button.y + 5))

        y += 35

        # Required checkbox
        required_checkbox = pygame.Rect(editor_x + 10, y, 15, 15)
        pygame.draw.rect(self.screen, WHITE, required_checkbox)
        pygame.draw.rect(self.screen, BLACK, required_checkbox, 1)
        if enemy_type.required:
            pygame.draw.line(self.screen, BLACK, required_checkbox.topleft, required_checkbox.bottomright, 2)
            pygame.draw.line(self.screen, BLACK, required_checkbox.topright, required_checkbox.bottomleft, 2)
        required_text = self.small_font.render("Required to kill to complete level", True, BLACK)
        self.screen.blit(required_text, (editor_x + 30, y))

    def draw_collectible_editor(self):
        """Draw the collectible editor dialog"""
        if self.editing_collectible_id is None:
            return

        collectible_type = self.collectible_types.get(self.editing_collectible_id)
        if not collectible_type:
            return

        # Semi-transparent overlay
        overlay = pygame.Surface((self.palette_width, SCREEN_HEIGHT))
        overlay.set_alpha(200)
        overlay.fill(LIGHT_GRAY)
        self.screen.blit(overlay, (self.palette_rect.x, 0))

        # Editor box
        editor_x = self.palette_rect.x + 20
        editor_y = 100
        editor_width = self.palette_width - 40
        editor_height = 500

        pygame.draw.rect(self.screen, WHITE, (editor_x, editor_y, editor_width, editor_height))
        pygame.draw.rect(self.screen, BLACK, (editor_x, editor_y, editor_width, editor_height), 2)

        # Title
        title = self.font.render("Edit Collectible", True, BLACK)
        self.screen.blit(title, (editor_x + 10, editor_y + 10))

        # Close button
        close_button = pygame.Rect(editor_x + editor_width - 60, editor_y + 10, 50, 25)
        pygame.draw.rect(self.screen, RED, close_button)
        pygame.draw.rect(self.screen, BLACK, close_button, 1)
        close_text = self.small_font.render("Close", True, BLACK)
        self.screen.blit(close_text, (close_button.x + 8, close_button.y + 5))

        y = editor_y + 45

        # Name field
        name_label = self.small_font.render("Name:", True, BLACK)
        self.screen.blit(name_label, (editor_x + 10, y))
        y += 20
        name_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        pygame.draw.rect(self.screen, WHITE if not (self.input_active and self.input_field == 'name') else YELLOW, name_field)
        pygame.draw.rect(self.screen, BLACK, name_field, 1)
        name_text = self.small_font.render(self.input_text if (self.input_active and self.input_field == 'name') else collectible_type.name, True, BLACK)
        self.screen.blit(name_text, (name_field.x + 5, name_field.y + 5))
        y += 35

        # Value field
        value_label = self.small_font.render("Value:", True, BLACK)
        self.screen.blit(value_label, (editor_x + 10, y))
        y += 20
        value_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        pygame.draw.rect(self.screen, WHITE if not (self.input_active and self.input_field == 'value') else YELLOW, value_field)
        pygame.draw.rect(self.screen, BLACK, value_field, 1)
        value_text = self.small_font.render(self.input_text if (self.input_active and self.input_field == 'value') else str(collectible_type.value), True, BLACK)
        self.screen.blit(value_text, (value_field.x + 5, value_field.y + 5))
        y += 35

        # Color field
        color_label = self.small_font.render("Color (R,G,B):", True, BLACK)
        self.screen.blit(color_label, (editor_x + 10, y))
        y += 20
        color_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        pygame.draw.rect(self.screen, WHITE if not (self.input_active and self.input_field == 'color') else YELLOW, color_field)
        pygame.draw.rect(self.screen, BLACK, color_field, 1)
        color_display = self.input_text if (self.input_active and self.input_field == 'color') else f"{collectible_type.color[0]},{collectible_type.color[1]},{collectible_type.color[2]}"
        color_text = self.small_font.render(color_display, True, BLACK)
        self.screen.blit(color_text, (color_field.x + 5, color_field.y + 5))
        y += 35

        # Effect Type buttons
        effect_label = self.font.render("Effect Type:", True, BLACK)
        self.screen.blit(effect_label, (editor_x + 10, y))
        y += 25
        for effect in CollectibleEffect:
            effect_button = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
            is_selected = self.collectible_effect_buttons.get(effect.value, False)
            pygame.draw.rect(self.screen, BLUE if is_selected else WHITE, effect_button)
            pygame.draw.rect(self.screen, BLACK, effect_button, 1)
            effect_text = self.small_font.render(effect.value.title(), True, BLACK)
            self.screen.blit(effect_text, (effect_button.x + 5, effect_button.y + 5))
            y += 30

        # Required checkbox
        required_checkbox = pygame.Rect(editor_x + 10, y, 15, 15)
        pygame.draw.rect(self.screen, WHITE, required_checkbox)
        pygame.draw.rect(self.screen, BLACK, required_checkbox, 1)
        if collectible_type.required:
            pygame.draw.line(self.screen, BLACK, required_checkbox.topleft, required_checkbox.bottomright, 2)
            pygame.draw.line(self.screen, BLACK, required_checkbox.topright, required_checkbox.bottomleft, 2)
        required_text = self.small_font.render("Required to complete level", True, BLACK)
        self.screen.blit(required_text, (editor_x + 30, y))

    def handle_enemy_editor_click(self, pos):
        """Handle clicks in the enemy editor dialog"""
        if self.editing_enemy_id is None:
            return

        enemy_type = self.enemy_types.get(self.editing_enemy_id)
        if not enemy_type:
            return

        editor_x = self.palette_rect.x + 20
        editor_y = 100
        editor_width = self.palette_width - 40

        # Close button
        close_button = pygame.Rect(editor_x + editor_width - 60, editor_y + 10, 50, 25)
        if close_button.collidepoint(pos):
            self.show_enemy_editor = False
            self.editing_enemy_id = None
            self.input_active = False
            return

        y = editor_y + 45

        # Name field
        y += 20
        name_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        if name_field.collidepoint(pos):
            self.input_active = True
            self.input_field = 'name'
            self.input_text = enemy_type.name
            return
        y += 35

        # Health field
        y += 20
        health_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        if health_field.collidepoint(pos):
            self.input_active = True
            self.input_field = 'health'
            self.input_text = str(enemy_type.health)
            return
        y += 35

        # Damage field
        y += 20
        damage_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        if damage_field.collidepoint(pos):
            self.input_active = True
            self.input_field = 'damage'
            self.input_text = str(enemy_type.damage)
            return
        y += 35

        # Speed field
        y += 20
        speed_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        if speed_field.collidepoint(pos):
            self.input_active = True
            self.input_field = 'speed'
            self.input_text = str(enemy_type.speed)
            return
        y += 35

        # Color field
        y += 20
        color_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        if color_field.collidepoint(pos):
            self.input_active = True
            self.input_field = 'color'
            self.input_text = f"{enemy_type.color[0]},{enemy_type.color[1]},{enemy_type.color[2]}"
            return
        y += 35

        # AI Type buttons
        y += 25
        for ai in EnemyAI:
            ai_button = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
            if ai_button.collidepoint(pos):
                enemy_type.ai_type = ai.value
                self.enemy_ai_buttons = {a.value: a.value == ai.value for a in EnemyAI}
                return
            y += 30

        # Behavior script buttons
        y += 20  # script label
        y += 25  # script display

        # Select file button
        select_button = pygame.Rect(editor_x + 10, y, 100, 25)
        if select_button.collidepoint(pos):
            self.select_behavior_script()
            return

        # Clear button (only if script is set)
        if enemy_type.behavior_script:
            clear_button = pygame.Rect(editor_x + 120, y, 80, 25)
            if clear_button.collidepoint(pos):
                enemy_type.behavior_script = None
                print("Cleared behavior script")
                return

        y += 35

        # Required checkbox
        required_checkbox = pygame.Rect(editor_x + 10, y, 15, 15)
        if required_checkbox.collidepoint(pos):
            enemy_type.required = not enemy_type.required
            return

    def handle_collectible_editor_click(self, pos):
        """Handle clicks in the collectible editor dialog"""
        if self.editing_collectible_id is None:
            return

        collectible_type = self.collectible_types.get(self.editing_collectible_id)
        if not collectible_type:
            return

        editor_x = self.palette_rect.x + 20
        editor_y = 100
        editor_width = self.palette_width - 40

        # Close button
        close_button = pygame.Rect(editor_x + editor_width - 60, editor_y + 10, 50, 25)
        if close_button.collidepoint(pos):
            self.show_collectible_editor = False
            self.editing_collectible_id = None
            self.input_active = False
            return

        y = editor_y + 45

        # Name field - match draw function exactly
        name_label_y = y
        y += 20
        name_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        if name_field.collidepoint(pos):
            self.input_active = True
            self.input_field = 'name'
            self.input_text = collectible_type.name
            return
        y += 35

        # Value field - match draw function exactly
        value_label_y = y
        y += 20
        value_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        if value_field.collidepoint(pos):
            self.input_active = True
            self.input_field = 'value'
            self.input_text = str(collectible_type.value)
            return
        y += 35

        # Color field - match draw function exactly
        color_label_y = y
        y += 20
        color_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        if color_field.collidepoint(pos):
            self.input_active = True
            self.input_field = 'color'
            self.input_text = f"{collectible_type.color[0]},{collectible_type.color[1]},{collectible_type.color[2]}"
            return
        y += 35

        # Effect Type buttons - match draw function exactly
        effect_label_y = y
        y += 25
        for effect in CollectibleEffect:
            effect_button = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
            if effect_button.collidepoint(pos):
                collectible_type.effect = effect.value
                self.collectible_effect_buttons = {e.value: e.value == effect.value for e in CollectibleEffect}
                return
            y += 30

        # Required checkbox
        required_checkbox = pygame.Rect(editor_x + 10, y, 15, 15)
        if required_checkbox.collidepoint(pos):
            collectible_type.required = not collectible_type.required
            return

    def new_level(self):
        """Create a new blank level"""
        # Reset level data
        self.level_width = DEFAULT_LEVEL_WIDTH
        self.level_height = DEFAULT_LEVEL_HEIGHT
        self.tiles = {
            'background': {},
            'main': {},
            'foreground': {}
        }

        # Clear enemies and collectibles
        self.enemies = []
        self.collectibles = []

        # Reset background images
        self.background_image_path = None
        self.background_image = None
        self.background_x = 0
        self.background_y = 0
        self.background_width = 0
        self.background_height = 0
        self.background_layers = []
        self.selected_bg_image_index = None

        # Reset camera and viewport
        self.camera_x = 0
        self.camera_y = 0
        self.viewport_x = 0
        self.viewport_y = 0
        self.viewport_width = VIEWPORT_WIDTH
        self.viewport_height = VIEWPORT_HEIGHT

        print("New level created")

    def open_level_dialog(self):
        """Open a file dialog to load a level"""
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        root.attributes('-topmost', True)  # Keep dialog on top

        filename = filedialog.askopenfilename(
            title="Open Level",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            defaultextension=".json"
        )

        root.destroy()

        if filename:
            self.load_level(filename)

    def save_level_as_dialog(self):
        """Open a file dialog to save the level"""
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        root.attributes('-topmost', True)  # Keep dialog on top

        filename = filedialog.asksaveasfilename(
            title="Save Level As",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            defaultextension=".json",
            initialfile=self.get_next_level_filename()
        )

        root.destroy()

        if filename:
            self.save_level(filename)

    def get_next_level_filename(self) -> str:
        """Get the next available level filename (level1.json, level2.json, etc.)"""
        level_num = 1
        while os.path.exists(f"level{level_num}.json"):
            level_num += 1
        return f"level{level_num}.json"

    def save_level(self, filename: str):
        """Save the current level to JSON"""
        data = {
            'width': self.level_width,
            'height': self.level_height,
            'tile_types': {tid: ttype.to_dict() for tid, ttype in self.tile_types.items()},
            'layers': {
                layer: {f"{x},{y}": tile.to_dict() for (x, y), tile in tiles.items()}
                for layer, tiles in self.tiles.items()
            },
            'enemy_types': {eid: etype.to_dict() for eid, etype in self.enemy_types.items()},
            'enemies': [enemy.to_dict() for enemy in self.enemies],
            'collectible_types': {cid: ctype.to_dict() for cid, ctype in self.collectible_types.items()},
            'collectibles': [collectible.to_dict() for collectible in self.collectibles],
            'background': {
                'image_path': self.background_image_path,
                'x': self.background_x,
                'y': self.background_y,
                'width': self.background_width,
                'height': self.background_height
            } if self.background_image_path else None,
            'background_layers': [bg_img.to_dict() for bg_img in self.background_layers],
            'viewport': {
                'x': self.viewport_x,
                'y': self.viewport_y,
                'width': self.viewport_width,
                'height': self.viewport_height
            }
        }

        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Level saved to {filename}")
    
    def load_level(self, filename: str):
        """Load a level from JSON"""
        if not os.path.exists(filename):
            print(f"File {filename} not found")
            return

        with open(filename, 'r') as f:
            data = json.load(f)

        self.level_width = data['width']
        self.level_height = data['height']

        # Load tile types
        self.tile_types = {}
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
            self.next_tile_id = max(self.next_tile_id, tid + 1)

        # Load tiles
        self.tiles = {'background': {}, 'main': {}, 'foreground': {}}
        for layer, tiles_data in data['layers'].items():
            for pos_str, tile_data in tiles_data.items():
                x, y = map(int, pos_str.split(','))
                self.tiles[layer][(x, y)] = Tile(
                    tile_type_id=tile_data['tile_type_id'],
                    layer=tile_data['layer']
                )

        # Load enemy types
        self.enemy_types = {}
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
                    behavior_script=etype_data.get('behavior_script'),
                    required=etype_data.get('required', False)
                )
                self.next_enemy_type_id = max(self.next_enemy_type_id, eid + 1)

        # Load enemies
        self.enemies = []
        if 'enemies' in data:
            for enemy_data in data['enemies']:
                self.enemies.append(EnemyInstance(
                    x=enemy_data['x'],
                    y=enemy_data['y'],
                    enemy_type_id=enemy_data['enemy_type_id'],
                    patrol_range=enemy_data.get('patrol_range', 100)
                ))

        # Load collectible types
        self.collectible_types = {}
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
                self.next_collectible_type_id = max(self.next_collectible_type_id, cid + 1)

        # Load collectibles
        self.collectibles = []
        if 'collectibles' in data:
            for collectible_data in data['collectibles']:
                self.collectibles.append(CollectibleInstance(
                    x=collectible_data['x'],
                    y=collectible_data['y'],
                    collectible_type_id=collectible_data['collectible_type_id']
                ))

        # Load background image
        if 'background' in data and data['background']:
            bg_data = data['background']
            self.background_image_path = bg_data.get('image_path')
            self.background_x = bg_data.get('x', 0)
            self.background_y = bg_data.get('y', 0)
            self.background_width = bg_data.get('width', 0)
            self.background_height = bg_data.get('height', 0)

            if self.background_image_path and os.path.exists(self.background_image_path):
                try:
                    self.background_image = pygame.image.load(self.background_image_path)
                except Exception as e:
                    print(f"Error loading background image: {e}")
                    self.background_image = None
            else:
                self.background_image = None
        else:
            # Clear background if not in data
            self.background_image_path = None
            self.background_image = None
            self.background_x = 0
            self.background_y = 0
            self.background_width = 0
            self.background_height = 0

        # Load background layers
        self.background_layers = []
        if 'background_layers' in data:
            for bg_data in data['background_layers']:
                image = None
                if bg_data['image_path'] and os.path.exists(bg_data['image_path']):
                    try:
                        image = pygame.image.load(bg_data['image_path'])
                    except Exception as e:
                        print(f"Error loading background layer image: {e}")

                if image:
                    # Calculate default parallax factor if not in saved data
                    layer_idx = bg_data['layer_index']
                    default_parallax = 0.1 + (layer_idx * 0.2)
                    bg_img = BackgroundImage(
                        layer_index=layer_idx,
                        image_path=bg_data['image_path'],
                        image=image,
                        x=bg_data['x'],
                        y=bg_data['y'],
                        width=bg_data['width'],
                        height=bg_data['height'],
                        repeat_x=bg_data.get('repeat_x', False),
                        repeat_y=bg_data.get('repeat_y', False),
                        parallax_factor=bg_data.get('parallax_factor', default_parallax),
                        aspect_ratio_locked=bg_data.get('aspect_ratio_locked', True)
                    )
                    self.background_layers.append(bg_img)

        # Load viewport settings
        if 'viewport' in data:
            viewport_data = data['viewport']
            self.viewport_x = viewport_data.get('x', 0)
            self.viewport_y = viewport_data.get('y', 0)
            self.viewport_width = viewport_data.get('width', VIEWPORT_WIDTH)
            self.viewport_height = viewport_data.get('height', VIEWPORT_HEIGHT)
        else:
            # Reset to defaults if not in data
            self.viewport_x = 0
            self.viewport_y = 0
            self.viewport_width = VIEWPORT_WIDTH
            self.viewport_height = VIEWPORT_HEIGHT

        print(f"Level loaded from {filename}")

    def draw_top_bar(self):
        """Draw the top bar with New, Open, and Save As buttons"""
        bar_height = 32
        bar_rect = pygame.Rect(0, 0, SCREEN_WIDTH, bar_height)
        pygame.draw.rect(self.screen, (60, 60, 60), bar_rect)
        pygame.draw.line(self.screen, BLACK, (0, bar_height), (SCREEN_WIDTH, bar_height), 2)

        # Button dimensions
        button_width = 90
        button_height = 24
        button_margin = 6

        # New button
        self.new_button_rect = pygame.Rect(button_margin, (bar_height - button_height) // 2, button_width, button_height)
        pygame.draw.rect(self.screen, YELLOW, self.new_button_rect)
        pygame.draw.rect(self.screen, BLACK, self.new_button_rect, 2)
        new_text = self.font.render("New", True, BLACK)
        text_rect = new_text.get_rect(center=self.new_button_rect.center)
        self.screen.blit(new_text, text_rect)

        # Open button
        self.open_button_rect = pygame.Rect(button_margin * 2 + button_width, (bar_height - button_height) // 2, button_width, button_height)
        pygame.draw.rect(self.screen, GREEN, self.open_button_rect)
        pygame.draw.rect(self.screen, BLACK, self.open_button_rect, 2)
        open_text = self.font.render("Open", True, BLACK)
        text_rect = open_text.get_rect(center=self.open_button_rect.center)
        self.screen.blit(open_text, text_rect)

        # Save As button
        self.save_as_button_rect = pygame.Rect(button_margin * 3 + button_width * 2,
                                                 (bar_height - button_height) // 2,
                                                 button_width, button_height)
        pygame.draw.rect(self.screen, BLUE, self.save_as_button_rect)
        pygame.draw.rect(self.screen, BLACK, self.save_as_button_rect, 2)
        save_text = self.font.render("Save As", True, BLACK)
        text_rect = save_text.get_rect(center=self.save_as_button_rect.center)
        self.screen.blit(save_text, text_rect)

        # Adjust canvas and palette rects to account for top bar
        self.canvas_rect = pygame.Rect(0, bar_height, SCREEN_WIDTH - self.palette_width, SCREEN_HEIGHT - bar_height)
        self.palette_rect = pygame.Rect(SCREEN_WIDTH - self.palette_width, bar_height, self.palette_width, SCREEN_HEIGHT - bar_height)

    def run(self):
        """Main game loop"""
        while self.running:
            self.handle_events()

            # Draw
            self.screen.fill(BLACK)
            self.draw_canvas()
            self.draw_palette()
            self.draw_top_bar()
            
            pygame.display.flip()
            self.clock.tick(FPS)
        
        pygame.quit()

if __name__ == "__main__":
    editor = TileEditor()
    editor.run()
