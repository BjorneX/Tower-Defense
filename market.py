import pygame
import defenses.cannon as cannon
import constants
import economy
import effects
import config  # configuration file for drag-and-drop settings
import math
import path  # used to generate the path points
import defenses.barrier as barrier
import defenses.defense as defense
from effects import get_flash_instance, get_invalid_placement_flash_instance

class MarketButton:
    def __init__(
        self,
        x,
        y,
        width,
        height,
        text="Buy",
        color=(50, 205, 50),
        hover_color=(70, 225, 70),
        text_color=(255, 255, 255),
        border_radius=0,
    ):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.text = text
        self.current_color = color
        self.font = pygame.font.SysFont(None, 24)
        self.border_radius = border_radius

    def draw(self, surface):
        pygame.draw.rect(
            surface, self.current_color, self.rect, border_radius=self.border_radius
        )
        text_surface = self.font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)

    def update(self, events, cached_mouse_pos):
        self.current_color = (
            self.hover_color if self.rect.collidepoint(cached_mouse_pos) else self.color
        )
        for event in events:
            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.rect.collidepoint(event.pos)
            ):
                return True
        return False


def make_market_btn(screen, button_width=100, button_height=40, margin=10):
    screen_width, _ = screen.get_size()
    x = screen_width - button_width - margin
    return MarketButton(x, margin, button_width, button_height)


# --- New Container class for inventory management ---
class Container:
    def __init__(self, container_id, row, col, category):
        self.id = container_id   # A unique ID for the container
        self.row = row           # The grid row (0-indexed)
        self.col = col           # The grid column (0-indexed)
        self.category = category # Which category this container belongs to
        self.defense = None      # Holds a defense instance when assigned


class Market:
    def __init__(
        self,
        screen,
        x=None,
        y=0,
        width=175,
        height=450,
        text="Items...",
        color=constants.color_theme,
        text_color=(255, 255, 255),
    ):
        if x is None:
            screen_width, _ = screen.get_size()
            x = screen_width - width  # align flush with the right edge
        self.rect = pygame.Rect(x, y, width, height)
        self.screen = screen
        self.color = color
        self.text_color = text_color
        self.text = text
        self.current_color = color
        self.font = pygame.font.SysFont(None, 24)

        # Colors for non-focused and focused buttons.
        self.non_focus_color = constants.color_theme
        self.focus_color = (255, 0, 0)

        self.focused_btn = None
        self.category_btns = []
        button_height = 40
        base_button_width = self.rect.width // 3
        for i in range(3):
            current_button_width = (
                base_button_width
                if i < 2
                else self.rect.width - base_button_width * 2
            )
            x_button = self.rect.x + base_button_width * i
            btn = MarketButton(
                x_button,
                self.rect.y,
                current_button_width,
                button_height,
                text=f"{i+1}",
                color=self.non_focus_color,
            )
            self.category_btns.append(btn)
        if self.category_btns:
            self.focused_btn = self.category_btns[0]
            self.focused_btn.current_color = self.focus_color
            self.category_index = 0

        # For drag-and-drop functionality:
        self.drag_drop_enabled = config.DRAG_DROP_ENABLED  # use configuration value
        self.dragging_item = None
        self.drag_offset = (0, 0)

        self.placed_defenses = []
        self.market_is_pinned = False
        # New attribute to debounce the small pin button
        self.pin_btn_pressed = False

        # Add the market_is_opened boolean.
        self.market_is_opened = False

        # Set up an inventory for the market's containers.
        # Assuming we have 5 rows x 2 columns (10 containers); you can adjust the logic here.
        self.num_cols = 2
        self.num_rows = 5
        self.gap = 5
        self.container_size = 70
        
        self.inventory = [False] * 10  
        self.all_container_indices = [(r, c) for r in range(self.num_rows) for c in range(self.num_cols)]
        self.chunk_size = len(self.all_container_indices) // (len(self.category_btns)-1)  # Determine how many elements per sublist
        self.container_index = [self.all_container_indices[i * self.chunk_size: (i + 1) * self.chunk_size] for i in range(3)]        

        # Load the small icon image for items.
        # Make sure that the image file exists in the specified path.
        self.item_icon = pygame.image.load("assets/up-arrow.png").convert_alpha()
        # Scale the icon to a desired size (e.g. 20x20 pixels).
        self.item_icon = pygame.transform.scale(self.item_icon, (20, 20))
        
        # Pre-calculate the path points using the current screen dimensions.
        screen_width, screen_height = screen.get_size()
        self.path_points = path.generate_path_points(screen_width, screen_height)

        # Add a very small button in the bottom-left corner of the market.
        small_button_width = 10
        small_button_height = 10
        small_button_x = self.rect.x + 5  # align with the market's left edge
        small_button_y = self.rect.y - 5 + self.rect.height - small_button_height  # bottom aligned with the market
        self.pin_btn = MarketButton(
            small_button_x,
            small_button_y,
            small_button_width,
            small_button_height,
            text="",
            color=(150, 150, 150),
            hover_color=(180, 180, 180)
        )

        # --- Improved Inventory System ---
        self.num_cols = 2
        self.num_rows = 5
        self.gap = 5
        self.container_size = 70

        # Get grid positions for all containers (row, col tuples).
        self.all_container_indices = [(r, c) for r in range(self.num_rows) for c in range(self.num_cols)]
        num_categories = len(self.category_btns)
        # Divide the total containers among categories (using ceiling division).
        containers_per_category = math.ceil(len(self.all_container_indices) / num_categories)
        self.containers_by_category = {}
        self.containers_all = []
        container_id = 0
        for cat in range(num_categories):
            self.containers_by_category[cat] = []
            for i in range(containers_per_category):
                idx = cat * containers_per_category + i
                if idx < len(self.all_container_indices):
                    row, col = self.all_container_indices[idx]
                    container = Container(container_id, row, col, cat)
                    self.containers_by_category[cat].append(container)
                    self.containers_all.append(container)
                    container_id += 1

        self.temp_defense = defense.Defense(self.screen, market=self, width=0, height=0, hp=0, dmg=0, cost=0, snapbox=0, type="default", scope=0, hasfront=False)
        self.defensetypes = ["default", "special", "other"]
        self.defenselist = [
            cannon.Cannon(self.screen, market=self),
            barrier.Barrier(self.screen, market=self)
        ]

        self.cached_mouse_pos = None
        self.orientation = None

    def handle_dragging(self, defense_item):
        """Handles dragging logic for a defense item."""
        
        if defense_item is None:
            return  # Avoid errors if defense_item is not set

        # Get mouse position
        mouse_x, mouse_y = pygame.mouse.get_pos()

        # Call the ondrag method if it exists
        if hasattr(defense_item, "ondrag"):
            defense_item.ondrag(self.screen)
        
        # Update position and angle
        defense_item.pos = (mouse_x, mouse_y)
        defense_item.angle = 90 if self.orientation == "vertical" else 0
        defense_item.draw()

        # Validate placement
        flash = get_invalid_placement_flash_instance()
        if not self.is_placeable((mouse_x, mouse_y), defense_item) and not self.rect.collidepoint((mouse_x, mouse_y)):
            flash.trigger()
        else:
            flash.stop()


    def draw_defenses_for_category(self, category_index):
        # Get the center of the container for positioning
        center = self.get_container_center(category_index)
        self.pos = center  # Update container position if needed
        
        # Filter defenses that belong to the current category
        filtered_defenses = [
            defense for defense in self.defenselist 
            if defense.type == self.defensetypes[category_index]
        ]
        
        for defense in filtered_defenses:
            # Optionally, add debugging info:
            print(f"Drawing defense: {defense} of type {defense.type}")
            defense.draw(self)
            if defense.hasfront:
                print("hasfront")
            else:
                print("no front")


    def ondrag(self, screen):
        mouse_x, mouse_y = self.cached_mouse_pos
        self.orientation, _ = self.get_continuous_path_orientation((mouse_x, mouse_y))
        self.angle = 90 if self.orientation == "vertical" else 0 
        if self.orientation == "vertical":
            self.defenselist[1].angle = 90
        else:
            self.defenselist[1].angle = 0
        return self.defenselist[1].draw()
    
    def get_container_rect(self, category_index):
        # Calculate the total grid dimensions.
        grid_width = self.num_cols * self.container_size + (self.num_cols + 1) * self.gap
        grid_height = self.num_rows * self.container_size + (self.num_rows + 1) * self.gap
        vertical_offset = 20  # Moves the grid 20 pixels lower.

        # Center the grid inside self.rect.
        start_x = self.rect.x + (self.rect.width - grid_width) // 2
        start_y = self.rect.y + (self.rect.height - grid_height) // 2 + vertical_offset

        # Determine the row and column based on the category index.
        row = category_index // self.num_cols
        col = category_index % self.num_cols

        # Calculate the x and y coordinates for the container.
        container_x = start_x + self.gap + col * (self.container_size + self.gap)
        container_y = start_y + self.gap + row * (self.container_size + self.gap)

        return pygame.Rect(container_x, container_y, self.container_size, self.container_size)

    def get_container_center(self, category_index):
        """
        Returns the (x, y) coordinates for the center of the container (category)
        specified by its index.
        """
        rect = self.get_container_rect(category_index)
        return rect.center


    def distance_to_segment(self, point, start, end):
        # Compute the distance from a point to a line segment (start to end)
        x, y = point
        x1, y1 = start
        x2, y2 = end
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(x - x1, y - y1)
        t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
        t = max(0, min(1, t))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(x - proj_x, y - proj_y)

    def is_near_path(self, point, tolerance=10):
        # Check if the point is within a given tolerance of any segment in the path
        for i in range(len(self.path_points) - 1):
            seg_start = self.path_points[i]
            seg_end = self.path_points[i + 1]
            if self.distance_to_segment(point, seg_start, seg_end) <= tolerance:
                return True
        return False

    def get_path_orientation(self, point, tolerance=10):
        # Existing logic: find orientation of the single nearest segment.
        for i in range(len(self.path_points) - 1):
            seg_start = self.path_points[i]
            seg_end = self.path_points[i + 1]
            if self.distance_to_segment(point, seg_start, seg_end) <= tolerance:
                dx = seg_end[0] - seg_start[0]
                dy = seg_end[1] - seg_start[1]
                if abs(dx) >= abs(dy):
                    return "horizontal"
                else:
                    return "vertical"
        return "horizontal"

    def get_continuous_path_orientation(self, point, tolerance=10, window=5):
        """
        Find the index of the nearest segment to point, then examine a window of segments
        around that point to determine if the orientation is continuous.
        Returns a tuple (orientation, continuous) where orientation is either "horizontal" or "vertical"
        and continuous is a boolean that is True when at least 70% of the segments in the window
        share the same orientation.
        """
        min_dist = float('inf')
        min_idx = 0
        for i in range(len(self.path_points) - 1):
            d = self.distance_to_segment(point, self.path_points[i], self.path_points[i + 1])
            if d < min_dist:
                min_dist = d
                min_idx = i

        h_count = 0
        v_count = 0
        total = 0
        start_idx = max(0, min_idx - window)
        end_idx = min(len(self.path_points) - 1, min_idx + window)
        for i in range(start_idx, end_idx):
            p1 = self.path_points[i]
            p2 = self.path_points[i + 1]
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            if abs(dx) >= abs(dy):
                h_count += 1
            else:
                v_count += 1
            total += 1

        if total == 0:
            return (self.get_path_orientation(point, tolerance), False)
        if h_count / total >= 0.7:
            return ("horizontal", True)
        elif v_count / total >= 0.7:
            return ("vertical", True)
        else:
            return (self.get_path_orientation(point, tolerance), False)

    def snap_point_to_path(self, point, snap_tolerance=15):
        """
        Instead of projecting the drop point onto the segment,
        snap to the midpoint of the nearest segment if the midpoint is within snap_tolerance.
        """
        best_midpoint = None
        min_dist = float('inf')
        # Loop over every segment in the path.
        for i in range(len(self.path_points) - 1):
            A = self.path_points[i]
            B = self.path_points[i + 1]
            # Calculate the midpoint of the segment.
            midpoint = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
            #remember this!!!
            d = math.hypot(point[0] - midpoint[0], point[1] - midpoint[1])
        if d < min_dist:
            min_dist = d
            best_midpoint = (int(midpoint[0]), int(midpoint[1]))
        if min_dist <= snap_tolerance:
            return best_midpoint
        else:
            return None

    def is_placeable(self, point, defense, base_tolerance=10):
        """
        Determines if the given point is close enough to some path segment,
        using an increased tolerance in areas where the path orientation is continuous.
        Also ensures the point is on-screen.
        """
        if defense is None:
            return False  # If there's no defense, placement is invalid

        if not self.screen.get_rect().collidepoint(point):
            return False  # Ensure point is inside the screen

        # Get the orientation and check if the path is continuous at this point
        self.orientation, continuous = self.get_continuous_path_orientation(point)
        
        # Ensure defense has a `snapbox` attribute before accessing it
        tolerance = base_tolerance + (getattr(defense, "snapbox", 0) * 0.5 if continuous else 0)

        # Check if the point is close to the path
        near_path = any(
            self.distance_to_segment(point, self.path_points[i], self.path_points[i + 1]) <= tolerance
            for i in range(len(self.path_points) - 1)
        )

        # Placement rules:
        if isinstance(defense, barrier.Barrier):
            return near_path  # Barriers must be near the path
        return not near_path  # Other defenses must be placed away from the path


    def update(self, events):
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # If the click is inside the market
                if self.rect.collidepoint(event.pos):
                    # Open the market if it's not already open.
                    if not self.market_is_opened:
                        self.market_is_opened = True

                    # Immediately check containers for a defense drag initiation.
                    for container in self.containers_all:
                        container_rect = self.get_container_rect(container.id)
                        if container_rect.collidepoint(event.pos) and container.defense is None:
                            # Check which defense is being clicked based on the active category button
                            if self.focused_btn == self.category_btns[0]:
                                # For Cannon (cost: 1000)
                                if economy.balance >= 1000:
                                    self.dragging_item = cannon.Cannon(self.screen, self)
                                else:
                                    flash = get_flash_instance()
                                    flash.trigger()
                            elif self.focused_btn == self.category_btns[2]:
                                # For barrier (cost: 500)
                                if economy.balance >= 500:
                                    self.dragging_item = barrier.Barrier(self.screen, self)
                                else:
                                    flash = get_flash_instance()
                                    flash.trigger()
                            break
                else:
                    # If clicked outside and the market is not pinned, close the market.
                    if not self.market_is_pinned:
                        self.market_is_opened = False
                        return True

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.dragging_item:
                    drop_point = event.pos
                    self.orientation, continuous = self.get_continuous_path_orientation(drop_point)
                    self.dragging_item.angle = 90 if self.orientation == "vertical" else 0
                    if self.is_placeable(drop_point, self.dragging_item):
                        snapped_point = self.snap_point_to_path(drop_point)
                        final_point = snapped_point if snapped_point is not None else drop_point
                        self.dragging_item.pos = final_point
                        self.placed_defenses.append(self.dragging_item)
                        economy.balance -= self.dragging_item.cost
                    flash = get_invalid_placement_flash_instance()
                    flash.stop()
                    self.dragging_item = None

        # Update category buttons and market open state.
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.rect.collidepoint(event.pos):
                    self.market_is_opened = True
                    for btn in self.category_btns:
                        if btn.rect.collidepoint(event.pos):
                            if self.focused_btn and self.focused_btn != btn:
                                self.focused_btn.current_color = self.non_focus_color
                            self.focused_btn = btn
                            self.focused_btn.current_color = self.focus_color
                            self.category_index = self.category_btns.index(btn)
                            break
                else:
                    if not self.market_is_pinned:
                        self.market_is_opened = False
                        return True
        return False

    def draw(self, screen, cached_mouse_pos):
        # Draw market background
        pygame.draw.rect(screen, self.current_color, self.rect)

                # Assuming your grid has num_cols * num_rows containers:
        num_containers = self.num_cols * self.num_rows

        for container_index in range(num_containers):
            container_rect = self.get_container_rect(container_index)
            pygame.draw.rect(self.screen, (15, 15, 15), container_rect, border_radius=3)

        for idx, btn in enumerate(self.category_btns):
                    
            btn.draw(screen)  # Draw the container button
            
            # If this container is focused, draw its defenses
            if self.focused_btn == btn:
                self.draw_defenses_for_category(idx)

        # Assuming self.category_btns and self.defensetypes correspond,
        # and self.focused_btn is the currently active category button

        self.handle_dragging(self.dragging_item)

        # Update and draw the invalid placement flash
        flash = get_invalid_placement_flash_instance()
        flash.update()  
        flash.draw()
        # Draw the very small button (pin button) in the bottom-left corner of the market.
        self.pin_btn.draw(self.screen)
        if self.pin_btn.rect.collidepoint(cached_mouse_pos):
            pygame.draw.rect(screen, (255, 255, 255), self.pin_btn.rect, 2)
            # Use rising edge detection to avoid multiple toggles per press.
            if pygame.mouse.get_pressed()[0]:
                if not self.pin_btn_pressed:
                    self.market_is_pinned = not self.market_is_pinned
                    self.pin_btn_pressed = True
            else:
                self.pin_btn_pressed = False
            self.pin_btn.current_color = (255, 255, 255) if self.market_is_pinned else (150, 150, 150)

    def draw_defenses(self, screen):
        """
        Draws all placed defenses so they remain visible regardless
        of whether the market menu is open.
        """
        for defense in self.placed_defenses:
            defense.draw()


def make_market(screen, width=175, height=450):
    return Market(screen, width=width, height=height)

#class UpgradeButton:
    def __init__(self, x, y, width, height, container_index):
        self.rect = pygame.Rect(x, y, width, height)
        self.color = (50, 205, 50)
        self.hover_color = (70, 225, 70)

    def draw(self, screen):    # Calculate the container index (assuming row-major order).
        container_index = Market.row * Market.num_cols + Market.col
        if self.inventory[container_index]:
            # Define the upgrade button dimensions and position.
            upgrade_button_width = 20
            upgrade_button_height = 20
            upgrade_button_color = (50, 205, 50)
            button_padding = 2
            button_x = Market.rect.x + Market.container_size - upgrade_button_width - button_padding
            button_y = Market.rect.y + Market.container_size - upgrade_button_height - button_padding
            upgrade_button_rect = pygame.Rect(button_x, button_y, upgrade_button_width, upgrade_button_height)
            
            # Draw a green rounded rectangle as the upgrade button.
            pygame.draw.rect(screen, (upgrade_button_color), upgrade_button_rect, border_radius=5)
            if Market.cached_mouse_pos.collidepoint(upgrade_button_rect):
                current_upgrade_button_color[container_index] = (70, 225, 70)
                if pygame.mouse.get_pressed()[0]:
                    self.current_upgrades[container_index] += 1
                    print(f"Upgraded container {container_index} to level {self.current_upgrades[container_index]}")
            # Draw a white upward arrow on the upgrade button.
            arrow_points = [
                (button_x + upgrade_button_width // 2, button_y + 4),
                (button_x + 4, button_y + upgrade_button_height - 4),
                (button_x + upgrade_button_width - 4, button_y + upgrade_button_height - 4)
            ]
            pygame.draw.polygon(screen, (255, 255, 255), arrow_points)

