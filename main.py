import pygame
import sys
import os
import json

# Inicjalizacja Pygame
pygame.init()

# Stałe
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 900
FPS = 60

# Kolory
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GRAY = (128, 128, 128)
YELLOW = (255, 255, 0)

class Line:
    def __init__(self, start_pos, end_pos):
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.rect = self._create_rect()

    def _create_rect(self, thickness=1):
        x1, y1 = self.start_pos
        x2, y2 = self.end_pos
        if x1 == x2:  # Linia pionowa
            return pygame.Rect(x1 - thickness/2, min(y1, y2), thickness, abs(y2 - y1))
        elif y1 == y2:  # Linia pozioma
            return pygame.Rect(min(x1, x2), y1 - thickness/2, abs(x2 - x1), thickness)
        else:
            return pygame.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

    def draw(self, screen):
        # Linie są niewidoczne
        pass

class GameState:
    def __init__(self):
        self.current_level = 0
        self.levels = load_levels_from_file()
        self.load_background()
        
    def load_background(self):
        background_path = os.path.join('images', 'levels', f'{self.current_level + 1}.png')
        try:
            self.background_image = pygame.image.load(background_path)
            self.background_image = pygame.transform.scale(self.background_image, (WINDOW_WIDTH, WINDOW_HEIGHT))
        except pygame.error as e:
            print(f"Nie można załadować tła: {e}")
            self.background_image = None
            
    def next_level(self):
        if self.current_level < len(self.levels) - 1:
            self.current_level += 1
            self.load_background()
            return True
        return False
        
    def previous_level(self):
        if self.current_level > 0:
            self.current_level -= 1
            self.load_background()
            return True
        return False
        
    def get_current_level(self):
        return self.levels[self.current_level]

def load_levels_from_file(filename="levels.json"):
    with open(filename, 'r') as f:
        data = json.load(f)
    levels = []
    for level_data in data['levels']:
        level = []
        for line_data in level_data['lines']:
            start = tuple(line_data['start'])
            end = tuple(line_data['end'])
            level.append(Line(start, end))
        levels.append(level)
    return levels

class Player:
    def __init__(self, x, y):
        self.initial_x = x
        self.initial_y = y
        self.reset_position()
        
        self.width = int(86)  
        self.height = int(86)  
        
        # Inicjalizacja dźwięków
        try:
            self.jump_sound = pygame.mixer.Sound('sounds/jump.mp3')
            self.land_sound = pygame.mixer.Sound('sounds/land.mp3')
            self.bump_sound = pygame.mixer.Sound('sounds/bump.mp3')
        except pygame.error as e:
            print(f"Nie można załadować dźwięków: {e}")
            self.jump_sound = None
            self.land_sound = None
            self.bump_sound = None
        
        try:
            # Słownik na wszystkie sprite'y
            self.sprites = {}
            
            # Lista nazw plików sprite'ów
            sprite_files = {
                'idle': 'idle.png',
                'prepare': 'prepare.png',
                'jump': 'jump.png',
                'fall': 'fall.png',
                'knockback': 'knockback.png',
                'run1': 'run1.png',
                'run2': 'run2.png',
                'run3': 'run3.png'
            }
            
            # Wczytaj każdy sprite
            for state, filename in sprite_files.items():
                image = pygame.image.load(os.path.join('images', 'player', filename)).convert_alpha()
                image = pygame.transform.scale(image, (self.width, self.height))
                self.sprites[state] = image
                # Tworzenie odwróconej wersji
                self.sprites[f"{state}_flipped"] = pygame.transform.flip(image, True, False)
                
        except pygame.error as e:
            print(f"Nie można załadować sprite'ów gracza: {e}")
            self.sprites = None

        # Dodajemy zmienne do animacji biegu
        self.run_animation_frame = 0
        self.run_animation_timer = 0
        self.run_frame_durations = {
            'run1': 10,  # Klatki (około 167ms przy 60 FPS)
            'run2': 5,   # Klatki (około 83ms przy 60 FPS)
            'run3': 10   # Klatki (około 167ms przy 60 FPS)
        }
        self.current_run_frame = 'run1'

        self.vel_y = 0
        self.vel_x = 0
        self.is_jumping = False
        self.is_falling = False
        self.charging_jump = False
        self.jump_power = 0
        self.max_jump_power = 25
        self.gravity = 0.6
        self.max_fall_speed = 30
        self.jump_direction = 0
        self.horizontal_jump_speed = 8
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.moving_direction = 0
        self.facing_left = False
        self.wall_collision = False
        self.was_in_air = False  # Nowa zmienna do śledzenia czy postać była w powietrzu

    def update_run_animation(self):
        # Aktualizuj animację tylko jeśli postać się porusza po ziemi
        if abs(self.vel_x) > 0 and not self.is_jumping and not self.is_falling and not self.charging_jump:
            self.run_animation_timer += 1
            
            # Sprawdź czy czas trwania obecnej klatki minął
            if self.run_animation_timer >= self.run_frame_durations[self.current_run_frame]:
                self.run_animation_timer = 0
                
                # Przejdź do następnej klatki
                if self.current_run_frame == 'run1':
                    self.current_run_frame = 'run2'
                elif self.current_run_frame == 'run2':
                    self.current_run_frame = 'run3'
                elif self.current_run_frame == 'run3':
                    self.current_run_frame = 'run1'
        else:
            # Resetuj animację gdy postać się zatrzyma
            self.current_run_frame = 'run1'
            self.run_animation_timer = 0

    def get_current_sprite(self):
        # Wybierz odpowiedni sprite na podstawie stanu
        if self.wall_collision and (self.is_jumping or self.is_falling):
            state = 'knockback'
        elif self.charging_jump:
            state = 'prepare'
        elif self.is_jumping and self.vel_y < 0:
            state = 'jump'
        elif self.is_falling or (self.is_jumping and self.vel_y > 0):
            state = 'fall'
        elif abs(self.vel_x) > 0 and not self.is_jumping and not self.is_falling:
            # Użyj aktualnej klatki animacji biegu
            state = self.current_run_frame
        else:
            state = 'idle'
            
        # Dodaj '_flipped' jeśli postać jest odwrócona w lewo
        if self.facing_left:
            state += '_flipped'
            
        return self.sprites[state]

    def reset_position(self):
        self.x = self.initial_x
        self.y = self.initial_y
        self.previous_x = self.x
        self.previous_y = self.y
        self.vel_y = 0
        self.vel_x = 0
        self.is_jumping = False
        self.is_falling = False
        self.charging_jump = False
        self.jump_power = 0
        self.moving_direction = 0
        self.wall_collision = False
        self.current_run_frame = 'run1'
        self.run_animation_timer = 0
        self.was_in_air = False

    def transition_to_level(self, going_up=True):
        current_state = {
            'x': self.x,
            'vel_y': self.vel_y,
            'vel_x': self.vel_x,
            'is_jumping': self.is_jumping,
            'is_falling': self.is_falling,
            'moving_direction': self.moving_direction
        }
        
        if going_up:
            self.y = WINDOW_HEIGHT - 5
        else:
            self.y = 5
            
        self.x = current_state['x']
        self.vel_y = current_state['vel_y']
        self.vel_x = current_state['vel_x']
        self.is_jumping = current_state['is_jumping']
        self.is_falling = current_state['is_falling']
        self.moving_direction = current_state['moving_direction']
        
        return True

    def check_collision_with_lines(self, lines):
        prev_rect = pygame.Rect(self.previous_x, self.previous_y, self.width, self.height)
        current_rect = pygame.Rect(self.x, self.y, self.width, self.height)
        
        collision_occurred = False
        
        # Najpierw sprawdź kolizje z podłożem
        for line in lines:
            if current_rect.colliderect(line.rect):
                if prev_rect.bottom <= line.rect.top + 5:
                    self.y = line.rect.top - self.height
                    self.vel_y = 0
                    self.is_jumping = False
                    self.is_falling = False
                    self.moving_direction = 0
                    self.wall_collision = False
                    # Odtwórz dźwięk lądowania jeśli postać była w powietrzu
                    if self.was_in_air and self.land_sound:
                        self.land_sound.play()
                    self.was_in_air = False
                    collision_occurred = True
                    break

        # Następnie sprawdź kolizje boczne
        if not collision_occurred:
            for line in lines:
                if current_rect.colliderect(line.rect):
                    if prev_rect.right <= line.rect.left + 5:
                        self.x = line.rect.left - self.width
                        self.vel_x = 0
                        if self.is_jumping or self.is_falling:
                            self.moving_direction = -1
                            self.wall_collision = True
                            # Odtwórz dźwięk uderzenia
                            if self.bump_sound:
                                self.bump_sound.play()
                        collision_occurred = True
                    elif prev_rect.left >= line.rect.right - 5:
                        self.x = line.rect.right
                        self.vel_x = 0
                        if self.is_jumping or self.is_falling:
                            self.moving_direction = 1
                            self.wall_collision = True
                            # Odtwórz dźwięk uderzenia
                            if self.bump_sound:
                                self.bump_sound.play()
                        collision_occurred = True

        # Na końcu sprawdź kolizje z sufitem
        if not collision_occurred:
            for line in lines:
                if current_rect.colliderect(line.rect):
                    if prev_rect.top >= line.rect.bottom - 5:
                        self.y = line.rect.bottom
                        self.vel_y = 0
                        collision_occurred = True

        return collision_occurred

    def update(self, lines, game_state):
        # Aktualizuj animację biegu
        self.update_run_animation()
        
        self.previous_x = self.x
        self.previous_y = self.y

        # Aktualizacja kierunku tylko podczas ruchu po ziemi
        if not self.is_jumping and not self.is_falling:
            if self.vel_x < 0:
                self.facing_left = True
            elif self.vel_x > 0:
                self.facing_left = False

        if not self.is_jumping and not self.is_falling and not self.charging_jump:
            test_rect = pygame.Rect(self.x, self.y + 2, self.width, self.height)
            has_platform_below = False
            for line in lines:
                if test_rect.colliderect(line.rect):
                    has_platform_below = True
                    break 
            
            if not has_platform_below:
                self.is_falling = True
                self.was_in_air = True
                if self.vel_x > 0:
                    self.moving_direction = 0.8
                elif self.vel_x < 0:
                    self.moving_direction = -0.8
                else:
                    self.moving_direction = 0

        if not self.charging_jump:
            if self.is_jumping or self.is_falling:
                self.x += self.moving_direction * self.horizontal_jump_speed
            else:
                self.x += self.vel_x
        
        if not self.charging_jump:
            self.vel_y += self.gravity
            self.vel_y = min(self.vel_y, self.max_fall_speed)
            self.y += self.vel_y

        self.check_collision_with_lines(lines)

        if self.y < -self.height:
            if game_state.next_level():
                self.transition_to_level(going_up=True)
            else:
                self.y = -self.height
        elif self.y > WINDOW_HEIGHT:
            if game_state.previous_level():
                self.transition_to_level(going_up=False)
            else:
                self.y = WINDOW_HEIGHT - self.height

        # Odbijanie od krawędzi ekranu
        if self.x < 0:
            self.x = 0
            if self.is_jumping or self.is_falling:
                self.moving_direction = 1
                self.wall_collision = True
                # Odtwórz dźwięk uderzenia przy kolizji ze ścianą
                if self.bump_sound:
                    self.bump_sound.play()
        elif self.x > WINDOW_WIDTH - self.width:
            self.x = WINDOW_WIDTH - self.width
            if self.is_jumping or self.is_falling:
                self.moving_direction = -1
                self.wall_collision = True
                # Odtwórz dźwięk uderzenia przy kolizji ze ścianą
                if self.bump_sound:
                    self.bump_sound.play()

        self.rect.x = self.x
        self.rect.y = self.y

    def charge_jump(self, keys):
        if not self.is_jumping and not self.is_falling:
            self.charging_jump = True
            self.jump_power = min(self.jump_power + 0.5, self.max_jump_power)
            
            # Ustawiamy kierunek skoku i kierunek patrzenia
            if keys[pygame.K_LEFT]:
                self.jump_direction = -1
                self.facing_left = True
            elif keys[pygame.K_RIGHT]:
                self.jump_direction = 1
                self.facing_left = False
            else:
                self.jump_direction = 0

    def release_jump(self):
        if self.charging_jump:
            self.charging_jump = False
            self.is_jumping = True
            self.was_in_air = True
            self.vel_y = -self.jump_power
            self.jump_power = 0
            self.moving_direction = self.jump_direction
            if self.jump_sound:
                self.jump_sound.play()

    def draw(self, screen):
        if self.sprites is not None:
            # Używamy odpowiedniego sprite'a na podstawie stanu
            current_sprite = self.get_current_sprite()
            screen.blit(current_sprite, (self.x, self.y))
            
            # Rysuj pasek ładowania skoku
            if self.charging_jump:
                pygame.draw.rect(screen, (255, 255, 255), 
                               (self.x, self.y - 10, 
                                (self.jump_power / self.max_jump_power) * self.width, 5))
                
                
# Utworzenie okna
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Jump King")
clock = pygame.time.Clock()

# Utworzenie gracza
player = Player(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 200)

# Stan gry
game_state = GameState()

# Główna pętla gry
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYUP:
            if event.key == pygame.K_SPACE:
                player.release_jump()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                player.reset_position()
                game_state.current_level = 0
                game_state.load_background()

    keys = pygame.key.get_pressed()
    if keys[pygame.K_SPACE]:
        player.charge_jump(keys)
    
    if not player.charging_jump and not player.is_jumping:
        if keys[pygame.K_LEFT]:
            player.vel_x = -5
        elif keys[pygame.K_RIGHT]:
            player.vel_x = 5
        else:
            player.vel_x = 0
    else:
        player.vel_x = 0

    # Aktualizacja
    player.update(game_state.get_current_level(), game_state)

    # Rysowanie
    if game_state.background_image:
        screen.blit(game_state.background_image, (0, 0))
    else:
        screen.fill(BLACK)
        
    player.draw(screen)
    
    pygame.display.flip()
    clock.tick(FPS)
    

pygame.quit()
sys.exit()