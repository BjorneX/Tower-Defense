import pygame
import enemies
import math
import economy  # for refunding when selling
import defenses.defense as defense




class Cannon(defense.Defense):
    def __init__(self, screen, market, enemy_list, width=4, height=4, hp=250, dmg=1, cost=1000, snapbox=35, scope=400, type="default", has_front=False, front_img=False):
        super().__init__(screen, market, enemy_list, width, height, hp, dmg, cost, snapbox, scope, type, has_front, front_img)
        self.cannon_base = pygame.image.load("assets/cannon/base3.png").convert_alpha()
        self.cannon_pipe = pygame.image.load("assets/cannon/pipe3.png").convert_alpha()
        self.cannon_pipe_original = self.cannon_pipe.copy()
        self.base_rect = self.cannon_base.get_rect(center=self.get_rect().center)
        self.pipe_rect = self.cannon_pipe.get_rect(center=self.get_rect().center)
        self.pos = self.get_rect().center  # Set the cannon's position
        #self.start_time = pygame.time.get_ticks()
        self.delay = 750
        self.start_time = 0
        #self.elapsed_time = self.current_time-self.start_time




    def get_distance(self, pos1, pos2):
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def get_closest_enemy(self):
        closest_enemy = None
        scope_distance = self.scope
        # Reference the global enemy list from the enemies module
        for enemy in enemies.enemies_list:
            distance = self.get_distance(self.pos, enemy.get_position())
            if distance < scope_distance:
                scope_distance = distance
                closest_enemy = enemy
        return closest_enemy

    def get_angle_to(self, enemy):
        dx = enemy.posx - self.pos[0]
        dy = enemy.posy - self.pos[1]
        return math.atan2(dy, dx)
    
    def aim_at_enemy(self):
        enemy = self.get_closest_enemy()
        if enemy and self.pos:
            self.angle = self.get_angle_to(enemy)
            # Rotate the instance-specific pipe image.
            rotated_pipe = pygame.transform.rotate(self.cannon_pipe_original, -(math.degrees(self.angle) - 90))
            self.cannon_pipe = rotated_pipe
            current_time = pygame.time.get_ticks()
            elapsed_time = current_time - self.start_time
            if elapsed_time == self.delay:
                Projectile.fire()

        else:
            self.angle = 0
            self.cannon_pipe = self.cannon_pipe_original.copy()

        
    
    def draw(self):
        if hasattr(self, 'pos') and self.pos is not None:
            # Update the rects to be centered at the cannon's position
            self.base_rect = self.cannon_base.get_rect(center=self.pos)
            self.pipe_rect = self.cannon_pipe.get_rect(center=self.pos)
            self.screen.blit(self.cannon_base, self.base_rect)
            self.screen.blit(self.cannon_pipe, self.pipe_rect)

class Projectile:
    def __init__(self, screen, startx=100, starty=100):
        self.screen = screen  # ✅ Store screen reference
        self.width, self.height = screen.get_size()
        self.dia = 25
        self.startx = startx
        self.starty = starty
        self.rect = pygame.Rect(self.startx, self.starty, self.dia, self.dia)
        self.speed = 5  # ✅ Set speed

    def fire(self):
        print("Fire!")
        self.rect.x += self.speed 