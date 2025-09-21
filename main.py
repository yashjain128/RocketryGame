import pygame
import sys
import random

# Initialize pygame
pygame.init()

# Screen dimensions
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Rocket Game")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (135, 206, 250)  # Sky blue
GREEN = (0, 255, 0)
BROWN = (120, 72, 0)
GREY = (169, 169, 169)
ORANGE = (252, 173, 3)

air_resistance = 0.9

# Fonts
font = pygame.font.Font(None, 20)
big_font = pygame.font.Font(None, 30)
# Aesthetic font specifically for the height display (keep existing `font` variable unchanged)
try:
    # Try a nicer system font; common choices: 'Montserrat', 'Fira Sans', 'Helvetica'
    height_font = pygame.font.SysFont('Montserrat', 36, bold=True)
except Exception:
    # Fallback to a default font at a larger size
    height_font = pygame.font.Font(None, 36)

# Ground properties
ground_height = 50
ground_y = HEIGHT - ground_height

# Rocket properties
rocket_width, rocket_height = 50, 100
rocket_x = WIDTH // 2 - rocket_width // 2
# Start rocket sitting on the ground
rocket_y = ground_y - rocket_height
rocket_speed = 0
gravity = 0.1
# Thrust is a small negative acceleration applied each frame while holding space
thrust = -0.15

# Button properties
button_width, button_height = 150, 50
button_x = 50
button_y = HEIGHT - button_height - 20
button_pressed = False

# Parachute button (placed above the launch button)
parachute_button_width, parachute_button_height = 120, 36
# Place parachute button to the right of Launch button with same spacing (10px)
parachute_button_x = button_x + button_width + 10
parachute_button_y = button_y
parachute_deployed = False

# Smoke particle system for launch effect
smoke_particles = []  # each particle: [x, y, vx, vy, life, size, alpha]
smoke_spawned = False
smoke_timer = 0
SMOKE_DURATION = 100  # frames
LAUNCH_SMOKE_FRAMES = 120  # spawn smoke when holding space during first ~2 seconds after launch (120 frames @60fps)
launch_ticks = 0

# Height tracker
rocket_height_meters = 0

# Cloud properties
clouds = []
for _ in range(5):  # Generate 5 clouds at random positions
    cloud_x = random.randint(0, WIDTH - 100)
    cloud_y = random.randint(-HEIGHT, HEIGHT - 100)
    clouds.append([cloud_x, cloud_y])

cloud_speed = 2

# Fuel bar properties
fuel = 100
max_fuel = 100
fuel_consumption_rate = 0.5
repair_costs = 0
fuel_colour = GREEN

# New: Money and upgrades
money = 200  # starting dollars
prev_money = 0

upgrade_names = ["Controls", "Propulsion", "Airframe", "Payload", "Recovery"]
# initial prices for each upgrade
upgrade_prices = {
    "Controls": 100,
    "Propulsion": 150,
    "Airframe": 120,
    "Payload": 80,
    "Recovery": 90
}
upgrade_levels = {name: 0 for name in upgrade_names}

# Upgrade button layout (right side)
upgrade_button_width = 180
upgrade_button_height = 40
upgrade_button_x = WIDTH - upgrade_button_width - 20
upgrade_button_y_start = 50
upgrade_button_spacing = 10
upgrade_buttons = []
_y = upgrade_button_y_start
for name in upgrade_names:
    upgrade_buttons.append((name, pygame.Rect(upgrade_button_x, _y, upgrade_button_width, upgrade_button_height)))
    _y += upgrade_button_height + upgrade_button_spacing




# Track whether rocket was in flight to detect landing
was_in_flight = False

# Clock for controlling the frame rate
clock = pygame.time.Clock()

# Game loop
running = True
launched = False
off_the_ground = False
max_height = 0
while running:
    screen.fill(BLUE)  # Set the background to blue

    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            # Upgrade button clicks
            for name, rect in upgrade_buttons:
                if rect.collidepoint(mouse_x, mouse_y):
                    price = upgrade_prices[name]
                    if money >= price:
                        money -= price
                        upgrade_levels[name] += 1
                        # increase price (50% growth)
                        upgrade_prices[name] = max(1, int(price * 1.5))
                    break
            else:
                # Parachute button (only usable while launched)
                if parachute_button_x <= mouse_x <= parachute_button_x + parachute_button_width and parachute_button_y <= mouse_y <= parachute_button_y + parachute_button_height:
                    if launched and not parachute_deployed:
                        money -= 100
                        parachute_deployed = True
                
                if repair_costs>0 and button_x <= mouse_x <= button_x + button_width and button_y-80 <= mouse_y <= button_y-80 + button_height:
                    if money>=repair_costs:
                        money -= price
                        repair_costs = 0
                        fuel = max_fuel

                # Launch button (only when not launched)
                if not launched and repair_costs == 0 and button_x <= mouse_x <= button_x + button_width and button_y <= mouse_y <= button_y + button_height:
                    launched = True
                    button_pressed = True
                    # reset launch tick counter so initial smoke window starts
                    launch_ticks = 0
        # Continuous thrust is handled every frame when checking keys below.


    # Rocket physics
    if launched:
        # Determine effective physics values from upgrades
        controls_lvl = upgrade_levels["Controls"]
        propulsion_lvl = upgrade_levels["Propulsion"]
        airframe_lvl = upgrade_levels["Airframe"]
        payload_lvl = upgrade_levels["Payload"]
        recovery_lvl = upgrade_levels["Recovery"]

        # Effective thrust increases with propulsion level
        effective_thrust = thrust * (1 + 0.2 * propulsion_lvl)
        # Effective gravity reduced by airframe upgrades (gravity is negative in this code)
        effective_gravity = gravity * (1 - 0.05 * airframe_lvl)
        # Payload increases effective mass, reducing thrust effect
        payload_multiplier = 1 + 0.1 * payload_lvl
        # Controls reduce fuel consumption
        effective_fuel_rate = fuel_consumption_rate * max(0.1, (1 - 0.05 * controls_lvl))
        # Reward multiplier on landing from recovery upgrades
        reward_multiplier = 1 + 0.1 * recovery_lvl

        # Check keys every frame for continuous thrust
        keys = pygame.key.get_pressed()
        if keys[pygame.K_SPACE] and fuel > 0:
            # Apply continuous thrust while space is held (adjusted for payload)
            rocket_speed += effective_thrust / payload_multiplier
            # Consume fuel while thrusting (adjusted by controls)
            fuel -= effective_fuel_rate
            if fuel < 0:
                fuel = 0

        # Parachute effect: if deployed, dampen vertical speed and slow descent
        if parachute_deployed:
            # Reduce speed magnitude gradually, simulate drag
            rocket_speed *= 0.95

        # Gravity and movement applied every frame
        rocket_speed += effective_gravity
        # rocket_y += rocket_speed
        rocket_height_meters += rocket_speed * 0.1  # Convert speed to height (arbitrary scaling)

        if rocket_height_meters > 0:
            rocket_height_meters = 0
            if off_the_ground:
                launched = False
                repair_costs = (rocket_speed * 3) + (max_fuel - fuel) / 20
                off_the_ground = False
                prev_money = (-max_height)
                money += prev_money
            rocket_speed = 0
        else:
            max_height = min(max_height, rocket_height_meters)

        # Mark off_the_ground when the rocket is above the ground (negative height)
        if rocket_height_meters < 0:
            off_the_ground = True

        # Mark that we've been in flight if we leave the ground
        if rocket_y < ground_y - rocket_height - 1:
            was_in_flight = True

        # Move clouds downward only when rocket is actually moving (speed != 0)
        # Use a small epsilon to avoid floating point near-zero issues.
        if abs(rocket_speed) > 1e-4:
            for cloud in clouds:
                if (not (rocket_height_meters==0 and rocket_speed>1)):
                    cloud[1] -= ((rocket_speed)/5) 
                if cloud[1] > HEIGHT:  # Reset cloud position when it moves off-screen
                    cloud[0] = random.randint(0, WIDTH - 100)
                    cloud[1] = random.randint(-HEIGHT, -100)

        # Prevent rocket from going below the ground
        if rocket_y > ground_y - rocket_height:
            rocket_y = ground_y - rocket_height
            rocket_speed = 0
            # If we landed after being in flight, award money and reset flight state
            if was_in_flight:
                reward = int(max(0, rocket_height_meters) * reward_multiplier)
                money += reward
                # Reset flight state
                launched = False
                button_pressed = False
                rocket_height_meters = 0
                fuel = max_fuel  # refill fuel on landing
                was_in_flight = False


    # Draw the clouds
    for cloud in clouds:
        pygame.draw.ellipse(screen, WHITE, (cloud[0], cloud[1], 100, 50))

    # If rocket just launched, track launch_ticks; reset when not launched
    if launched:
        launch_ticks += 1
    else:
        launch_ticks = 0

    # Spawn smoke while holding space during the initial launch window
    keys = pygame.key.get_pressed()
    if launched and launch_ticks < LAUNCH_SMOKE_FRAMES and keys[pygame.K_SPACE] and fuel > 0:
        # spawn a few smoke particles per frame at the rocket base
        for i in range(6):
            px = rocket_x + rocket_width * 0.5 + random.uniform(-8, 8)
            py = rocket_y + rocket_height
            vx = random.uniform(-1.2, 1.2)
            vy = random.uniform(-2.5, -0.5)
            life = random.randint(20, 45)
            size = random.uniform(4, 12)
            alpha = random.randint(100, 220)
            smoke_particles.append([px, py, vx, vy, life, size, alpha])

    # Update and draw smoke particles (any existing particles)
    if len(smoke_particles) > 0:
        new_particles = []
        for p in smoke_particles:
            x, y, vx, vy, life, size, alpha = p
            # update
            x += vx
            y += vy
            vy -= 0.02  # slight upward acceleration to simulate rising smoke
            life -= 1
            alpha = max(0, alpha - 3)
            size = min(size + 0.1, size + 2)
            if life > 0 and alpha > 0:
                new_particles.append([x, y, vx, vy, life, size, alpha])
                # draw smoke (semi-transparent)
                surf = pygame.Surface((int(size * 2), int(size * 2)), pygame.SRCALPHA)
                pygame.draw.circle(surf, (120, 120, 120, int(alpha)), (int(size), int(size)), int(size))
                screen.blit(surf, (x - size, y - size))
        smoke_particles[:] = new_particles

    # Draw the rocket (body, nose cone, fins, window)
    # Body
    body_rect = pygame.Rect(rocket_x + rocket_width * 0.15, rocket_y + rocket_height * 0.15,
                            rocket_width * 0.7, rocket_height * 0.75)
    pygame.draw.rect(screen, GREY, body_rect)

    # Nose cone (triangle)
    nose_top = (rocket_x + rocket_width * 0.5, rocket_y)
    nose_left = (rocket_x + rocket_width * 0.15, rocket_y + rocket_height * 0.15)
    nose_right = (rocket_x + rocket_width * 0.85, rocket_y + rocket_height * 0.15)
    pygame.draw.polygon(screen, RED, [nose_top, nose_left, nose_right])

    # Fins (left and right)
    fin_height = rocket_height * 0.2
    fin_y = rocket_y + rocket_height * 0.7
    left_fin = [(rocket_x + rocket_width * 0.15, fin_y),
                (rocket_x, fin_y + fin_height),
                (rocket_x + rocket_width * 0.15, fin_y + fin_height / 2)]
    right_fin = [(rocket_x + rocket_width * 0.85, fin_y),
                 (rocket_x + rocket_width, fin_y + fin_height),
                 (rocket_x + rocket_width * 0.85, fin_y + fin_height / 2)]
    pygame.draw.polygon(screen, BLACK, left_fin)
    pygame.draw.polygon(screen, BLACK, right_fin)

    # Window
    window_radius = int(rocket_width * 0.12)
    window_center = (int(rocket_x + rocket_width * 0.5), int(rocket_y + rocket_height * 0.4))
    pygame.draw.circle(screen, BLUE, window_center, window_radius)
    pygame.draw.circle(screen, WHITE, window_center, int(window_radius * 0.5))

    # Flame when thrusting
    keys = pygame.key.get_pressed()
    if launched and keys[pygame.K_SPACE] and fuel > 0:
        # Flame is a triangle under the rocket body
        flame_top = (rocket_x + rocket_width * 0.5, rocket_y + rocket_height - 10)
        flame_left = (rocket_x + rocket_width * 0.3, rocket_y + rocket_height + rocket_height * 0.25 - 10)
        flame_right = (rocket_x + rocket_width * 0.7, rocket_y + rocket_height + rocket_height * 0.25 - 10)
        pygame.draw.polygon(screen, (255, 165, 0), [flame_top, flame_left, flame_right])  # orange
        inner_flame_left = (rocket_x + rocket_width * 0.42, rocket_y + rocket_height + rocket_height * 0.12 - 10)
        inner_flame_right = (rocket_x + rocket_width * 0.58, rocket_y + rocket_height + rocket_height * 0.12 - 10)
        pygame.draw.polygon(screen, (255, 220, 0), [flame_top, inner_flame_left, inner_flame_right])  # yellow

    # Draw parachute graphic above the rocket if deployed
    if parachute_deployed:
        canopy_rect = pygame.Rect(rocket_x - rocket_width * 0.3, rocket_y - rocket_height * 0.6, rocket_width * 1.6, rocket_height * 0.6)
        pygame.draw.ellipse(screen, (255, 105, 180), canopy_rect)  # pink canopy
        # Draw lines from canopy to rocket
        left_line_start = (canopy_rect.left + 10, canopy_rect.centery)
        right_line_start = (canopy_rect.right - 10, canopy_rect.centery)
        rocket_top_center = (rocket_x + rocket_width * 0.5, rocket_y + rocket_height * 0.1)
        pygame.draw.line(screen, BLACK, left_line_start, rocket_top_center, 2)
        pygame.draw.line(screen, BLACK, right_line_start, rocket_top_center, 2)

    # Draw the ground only when the rocket is not moving upward (rocket sitting on ground)
    # Ground disappears as soon as rocket leaves ground (rocket_y < ground level)
    pygame.draw.rect(screen, BROWN, (0, rocket_y + rocket_height + (-rocket_height_meters), WIDTH, ground_height))
    # optional simple grass line
    # pygame.draw.line(screen, GREEN, (0, rocket_y), (WIDTH, rocket_y), 3)

    # Draw the button
    # Parachute button (above launch)
    parachute_color = (70, 130, 180) if not parachute_deployed else (34, 139, 34)
    pygame.draw.rect(screen, parachute_color, (parachute_button_x, parachute_button_y, parachute_button_width, parachute_button_height))
    parachute_label = font.render("Parachute (100$)", True, WHITE)
    screen.blit(parachute_label, (parachute_button_x + 8, parachute_button_y + 8))

    if repair_costs>0:
        pygame.draw.rect(screen, RED, (button_x, button_y - 80, button_width, button_height))
        repair_text = font.render(f"Repair/fuel \n(${(repair_costs):.1f})", True, WHITE)
        screen.blit(repair_text, (button_x + 20, button_y - 80 + 10))

        pygame.draw.rect(screen, GREY, (button_x, button_y, button_width, button_height))
        button_text = font.render("Launch", True, WHITE)
        screen.blit(button_text, (button_x + 20, button_y + 10))
    elif not launched:
        pygame.draw.rect(screen, RED, (button_x, button_y, button_width, button_height))
        button_text = font.render("Launch", True, WHITE)
    else:
        pygame.draw.rect(screen, GREY, (button_x, button_y, button_width, button_height))
        button_text = font.render("Launched", True, WHITE)
    screen.blit(button_text, (button_x + 20, button_y + 10))

    # Draw the fuel bar with a horizontal gradient (red -> orange -> green)
    fuel_bar_rect = pygame.Rect(button_x, button_y - 20, button_width, 10)
    pygame.draw.rect(screen, BLACK, fuel_bar_rect)  # Fuel bar background

    # Ensure fraction between 0 and 1
    fuel_frac = max(0.0, min(1.0, fuel / max_fuel))

    # Create a single-color fill whose color shifts from green (full) -> orange (mid) -> red (low)
    fill_width = int(button_width * fuel_frac)
    if fill_width > 0:
        # Determine color by fuel fraction: map 1.0 -> green, 0.5 -> orange, 0.0 -> red
        if fuel_frac >= 0.5:
            # Interpolate green -> orange for 0.5..1.0 (map t from 0..1)
            t = (fuel_frac - 0.5) / 0.5
            r = int(ORANGE[0] + (GREEN[0] - ORANGE[0]) * t)
            g = int(ORANGE[1] + (GREEN[1] - ORANGE[1]) * t)
            b = int(ORANGE[2] + (GREEN[2] - ORANGE[2]) * t)
        else:
            # Interpolate red -> orange for 0.0..0.5 (map t from 0..1)
            t = fuel_frac / 0.5
            r = int(RED[0] + (ORANGE[0] - RED[0]) * t)
            g = int(RED[1] + (ORANGE[1] - RED[1]) * t)
            b = int(RED[2] + (ORANGE[2] - RED[2]) * t)

        fill_color = (r, g, b)
        pygame.draw.rect(screen, fill_color, (fuel_bar_rect.x, fuel_bar_rect.y, fill_width, fuel_bar_rect.height))

    # Display the height using the aesthetic `height_font` (top-left)
    height_text = height_font.render(f"{int(-rocket_height_meters)} m", True, BLACK)
    height_pos = (10, 10)
    screen.blit(height_text, height_pos)

    # Display speed indicator under the height (use existing `font` variable for consistency)
    speed_display = f"Velocity: {rocket_speed:.1f}"
    speed_text = font.render(speed_display, True, BLACK)
    # Position speed_text just below the height text
    speed_pos = (10, 10 + height_text.get_height() + 4)
    screen.blit(speed_text, speed_pos)
    
    res_display = f"Air resistance: {abs(air_resistance):.1f}"
    res_text = font.render(res_display, True, BLACK)
    # Position speed_text just below the height text
    res_pos = (10, 30 + height_text.get_height() + 4)
    screen.blit(res_text, res_pos)

    # New: Draw money counter (top-right)
    money_text = big_font.render(f"Total: ${int(money)}", True, (0, 100, 0))
    money_rect = money_text.get_rect(topright=(WIDTH - 10, 10))
    screen.blit(money_text, money_rect)

    prev_money_text = font.render(f"Previous launch: ${int(prev_money)}", True, BLACK)
    prev_money_rect = money_text.get_rect(topright=(WIDTH - 30, 40))
    screen.blit(prev_money_text, prev_money_rect)

    # New: Draw upgrade buttons and their labels on the right side
    for name, rect in upgrade_buttons:
        price = upgrade_prices[name]
        lvl = upgrade_levels[name]
        # color change if unaffordable
        color = GREY if money < price else RED
        pygame.draw.rect(screen, color, rect)
        label = font.render(f"{name} ${price} L{lvl}", True, WHITE)
        # small padding inside button
        screen.blit(label, (rect.x + 6, rect.y + 6))

    # Update the display
    pygame.display.flip()

    # Cap the frame rate
    clock.tick(60)

# Quit pygame
pygame.quit()
sys.exit()