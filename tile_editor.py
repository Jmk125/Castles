import pygame
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum

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

# Tile Properties
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
        
        # Current state
        self.current_tile_type_id = 0
        self.current_layer = 'main'
        self.layer_visibility = {'background': True, 'main': True, 'foreground': True}
        self.current_tool = Tool.PENCIL
        
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
        
        # Font
        self.font = pygame.font.Font(None, 20)
        self.small_font = pygame.font.Font(None, 16)
        
        # Input state for property editor
        self.input_text = ""
        self.input_active = False
        self.input_field = None  # 'name' or 'color'
        
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
    
    def apply_input_text(self):
        """Apply text input to the property being edited"""
        if self.editing_tile_id is None or self.input_field is None:
            return
        
        tile_type = self.tile_types.get(self.editing_tile_id)
        if not tile_type:
            return
        
        if self.input_field == 'name':
            tile_type.name = self.input_text if self.input_text else tile_type.name
        elif self.input_field == 'color':
            try:
                # Parse color like "255,100,100" or "255 100 100"
                parts = self.input_text.replace(',', ' ').split()
                if len(parts) == 3:
                    r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                    if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                        tile_type.color = (r, g, b)
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
                    self.save_level("level.json")
                elif event.key == pygame.K_o and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    self.load_level("level.json")
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
            
            elif event.type == pygame.MOUSEMOTION:
                if self.dragging_camera and self.drag_start_pos:
                    dx = self.drag_start_pos[0] - event.pos[0]
                    dy = self.drag_start_pos[1] - event.pos[1]
                    self.camera_x = max(0, min(self.camera_x + dx, self.level_width * TILE_SIZE - self.canvas_rect.width))
                    self.camera_y = max(0, min(self.camera_y + dy, self.level_height * TILE_SIZE - self.canvas_rect.height))
                    self.drag_start_pos = event.pos
                elif self.drawing:
                    self.handle_mouse_motion(event.pos)
            
            elif event.type == pygame.DROPFILE:
                self.handle_file_drop(event.file)
    
    def handle_left_click(self, pos):
        """Handle left mouse click"""
        # Check if clicking in palette
        if self.palette_rect.collidepoint(pos):
            self.handle_palette_click(pos)
        # Check if clicking in canvas
        elif self.canvas_rect.collidepoint(pos):
            tile_pos = self.screen_to_tile(pos[0], pos[1])
            if tile_pos:
                self.drawing = True
                self.draw_start_tile = tile_pos
                
                if self.current_tool == Tool.PENCIL:
                    if self.current_tool == Tool.ERASER:
                        self.erase_tile(*tile_pos)
                    else:
                        self.place_tile(*tile_pos)
                elif self.current_tool == Tool.ERASER:
                    self.erase_tile(*tile_pos)
    
    def handle_left_release(self, pos):
        """Handle left mouse release"""
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
            tile_pos = self.screen_to_tile(pos[0], pos[1])
            if tile_pos and tile_pos in self.tiles[self.current_layer]:
                self.erase_tile(*tile_pos)
    
    def handle_mouse_motion(self, pos):
        """Handle mouse motion while drawing"""
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
                # Fall through to handle normal palette clicks
                return
        
        # Match y_offset calculation from draw_palette
        y_offset = 10  # "Layers:"
        y_offset += 25  # after "Layers:"
        
        # Check layer toggles (these are fixed at top, not scrolled)
        layer_y = 35
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

        y_offset += 35  # gap after resize buttons (matches draw_palette)
        
        # Check plus button (fixed position, not scrolled)
        plus_button_rect = pygame.Rect(self.palette_rect.x + 10, y_offset, self.palette_width - 20, 30)
        
        if plus_button_rect.collidepoint(pos):
            # Add new tile
            self.add_tile_type(f"New Tile {self.next_tile_id}", None, [TileProperty.SOLID.value], 
                             (128, 128, 128))
            return
        
        y_offset += 40  # gap after plus button
        y_offset += 25  # "Tiles:" label
        
        # Tiles start here - this is tile_area_top in draw_palette
        tile_area_top = y_offset
        tile_area_height = SCREEN_HEIGHT - y_offset - 100  # Match draw_palette calculation

        # Check tile selection and edit buttons (these ARE scrolled)
        # Use the exact same calculation as draw_palette
        tile_y = y_offset - self.scroll_offset
        for tile_id, tile_type in self.tile_types.items():
            # Skip if not visible (match draw_palette visibility check)
            if tile_y + 60 < tile_area_top or tile_y > tile_area_top + tile_area_height:
                tile_y += 70
                continue
            
            tile_rect = pygame.Rect(self.palette_rect.x + 10, tile_y, self.palette_width - 20, 60)
            
            # Only process this tile if the click is within its rect
            if not tile_rect.collidepoint(pos):
                tile_y += 70
                continue
            
            # Edit button - match exact position from draw
            edit_button = pygame.Rect(tile_rect.x + tile_rect.width - 55, tile_rect.y + 5, 50, 20)
            
            if edit_button.collidepoint(pos):
                # Open property editor
                self.editing_tile_id = tile_id
                self.show_property_editor = True
                # Initialize checkboxes
                self.property_checkboxes = {prop.value: prop.value in tile_type.properties 
                                           for prop in TileProperty}
                return
            else:
                # Clicked on tile but not edit button - select tile
                self.current_tile_type_id = tile_id
                return
            
            tile_y += 70
    
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
        
        # Name field (after image preview)
        y = editor_y + 45 + 20 + 64 + 11  # title + label + image + gap
        name_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        if name_field.collidepoint(pos):
            self.input_active = True
            self.input_field = 'name'
            self.input_text = tile_type.name
            return
        
        # Color field
        y += 35 + 20  # name field + gap + label
        color_field = pygame.Rect(editor_x + 10, y, editor_width - 20, 25)
        if color_field.collidepoint(pos):
            self.input_active = True
            self.input_field = 'color'
            self.input_text = f"{tile_type.color[0]},{tile_type.color[1]},{tile_type.color[2]}"
            return
        
        # Property checkboxes
        y += 35 + 25  # color field + gap + properties label
        for prop, checked in self.property_checkboxes.items():
            checkbox_rect = pygame.Rect(editor_x + 10, y, 15, 15)
            if checkbox_rect.collidepoint(pos):
                self.property_checkboxes[prop] = not checked
                return
            y += 25
    
    def handle_file_drop(self, filepath):
        """Handle file drop for adding new tiles or replacing tile images"""
        if not filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            return
        
        # Get mouse position to see where the file was dropped
        mouse_pos = pygame.mouse.get_pos()
        
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
    
    def draw_canvas(self):
        """Draw the main canvas area"""
        # Draw background
        self.screen.fill(DARK_GRAY, self.canvas_rect)
        
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
        
        # Draw viewport indicator (1280x720 area)
        viewport_x = -self.camera_x
        viewport_y = -self.camera_y
        pygame.draw.rect(self.screen, YELLOW, (viewport_x, viewport_y, VIEWPORT_WIDTH, VIEWPORT_HEIGHT), 2)
        
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
        viewport_x = minimap_x + int(self.camera_x * scale_x)
        viewport_y = minimap_y + int(self.camera_y * scale_y)
        viewport_w = int(VIEWPORT_WIDTH * scale_x)
        viewport_h = int(VIEWPORT_HEIGHT * scale_y)
        pygame.draw.rect(self.screen, YELLOW, (viewport_x, viewport_y, viewport_w, viewport_h), 1)
    
    def draw_palette(self):
        """Draw the tile palette"""
        # Background
        self.screen.fill(LIGHT_GRAY, self.palette_rect)
        pygame.draw.line(self.screen, BLACK, (self.palette_rect.x, 0), 
                        (self.palette_rect.x, SCREEN_HEIGHT), 2)
        
        # Layer toggles (fixed at top)
        y_offset = 10
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
        
        # Tool selection
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
        
        # Plus button to add new tiles
        plus_button = pygame.Rect(self.palette_rect.x + 10, y_offset, self.palette_width - 20, 30)
        pygame.draw.rect(self.screen, GREEN, plus_button)
        pygame.draw.rect(self.screen, BLACK, plus_button, 2)
        plus_text = self.font.render("+ Add New Tile", True, BLACK)
        text_rect = plus_text.get_rect(center=plus_button.center)
        self.screen.blit(plus_text, text_rect)
        
        y_offset += 40
        
        # Tiles section header
        text = self.font.render("Tiles:", True, BLACK)
        self.screen.blit(text, (self.palette_rect.x + 10, y_offset))
        y_offset += 25
        
        # Create clip rect for scrollable area
        tile_area_top = y_offset
        tile_area_height = SCREEN_HEIGHT - y_offset - 100  # Leave room for instructions
        
        # Draw border around tile area
        tile_area_rect = pygame.Rect(self.palette_rect.x, tile_area_top, self.palette_width, tile_area_height)
        pygame.draw.rect(self.screen, DARK_GRAY, tile_area_rect, 2)
        
        # Set clipping rectangle to prevent overflow
        clip_rect = pygame.Rect(self.palette_rect.x, tile_area_top, self.palette_width, tile_area_height)
        self.screen.set_clip(clip_rect)
        
        # Calculate total height needed
        total_tiles_height = len(self.tile_types) * 70
        self.max_scroll = max(0, total_tiles_height - tile_area_height)
        
        # Draw tiles (scrollable)
        tile_y = y_offset - self.scroll_offset
        for tile_id, tile_type in self.tile_types.items():
            # Only draw if visible in clip area
            if tile_y + 60 < tile_area_top or tile_y > tile_area_top + tile_area_height:
                tile_y += 70
                continue
            
            # Tile preview
            tile_rect = pygame.Rect(self.palette_rect.x + 10, tile_y, self.palette_width - 20, 60)
            
            # Highlight if selected
            if tile_id == self.current_tile_type_id:
                pygame.draw.rect(self.screen, BLUE, tile_rect, 3)
            else:
                pygame.draw.rect(self.screen, DARK_GRAY, tile_rect, 1)
            
            # Draw tile preview
            preview_rect = pygame.Rect(tile_rect.x + 5, tile_rect.y + 5, 32, 32)
            if tile_type.image:
                scaled_img = pygame.transform.scale(tile_type.image, (32, 32))
                self.screen.blit(scaled_img, preview_rect.topleft)
            else:
                pygame.draw.rect(self.screen, tile_type.color, preview_rect)
            pygame.draw.rect(self.screen, BLACK, preview_rect, 1)
            
            # Name
            name_text = self.small_font.render(tile_type.name[:15], True, BLACK)
            self.screen.blit(name_text, (tile_rect.x + 45, tile_rect.y + 5))
            
            # Properties
            props_text = self.small_font.render(", ".join(tile_type.properties[:2]), True, DARK_GRAY)
            self.screen.blit(props_text, (tile_rect.x + 45, tile_rect.y + 25))
            
            # Edit button
            edit_button = pygame.Rect(tile_rect.x + tile_rect.width - 55, tile_rect.y + 5, 50, 20)
            pygame.draw.rect(self.screen, YELLOW, edit_button)
            pygame.draw.rect(self.screen, BLACK, edit_button, 1)
            edit_text = self.small_font.render("Edit", True, BLACK)
            self.screen.blit(edit_text, (edit_button.x + 10, edit_button.y + 2))
            
            tile_y += 70
        
        # Reset clipping
        self.screen.set_clip(None)
        
        # Draw property editor if open
        if self.show_property_editor and self.editing_tile_id is not None:
            self.draw_property_editor()
        
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
    
    def save_level(self, filename: str):
        """Save the current level to JSON"""
        data = {
            'width': self.level_width,
            'height': self.level_height,
            'tile_types': {tid: ttype.to_dict() for tid, ttype in self.tile_types.items()},
            'layers': {
                layer: {f"{x},{y}": tile.to_dict() for (x, y), tile in tiles.items()}
                for layer, tiles in self.tiles.items()
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
        
        print(f"Level loaded from {filename}")
    
    def run(self):
        """Main game loop"""
        while self.running:
            self.handle_events()
            
            # Draw
            self.screen.fill(BLACK)
            self.draw_canvas()
            self.draw_palette()
            
            pygame.display.flip()
            self.clock.tick(FPS)
        
        pygame.quit()

if __name__ == "__main__":
    editor = TileEditor()
    editor.run()
