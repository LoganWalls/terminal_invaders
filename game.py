#!/usr/bin/python2.7
import time
import curses
import random


class Controller(object):

    def __init__(self, g):
        # A reference to the parent game object.
        self.g = g

        num_pads = 2
        self.k_pads = []
        # A terminal to read the input
        for i in range(num_pads):
            k = curses.newpad(1, 1)
            # Read key inputs.
            k.keypad(1)
            # Make getch non-blocking
            k.nodelay(1)
            self.k_pads.append(k)

        self.__set_default_keybinds__()

    def __set_default_keybinds__(self):
        self.keybinds = {
            27: self.g.quit,
            258: lambda: self.g.player.move((0, 1)),
            259: lambda: self.g.player.move((0, -1)),
            260: lambda: self.g.player.move((-1, 0)),
            261: lambda: self.g.player.move((1, 0)),
            393: lambda: self.g.player.move((-3, 0)),
            402: lambda: self.g.player.move((3, 0)),
            32: self.g.player.shoot,
            101: lambda: Enemy(
                self.g,
                x=int((self.g.width - 5) * random.random()),
                y=self.g.height / 10
            ).spawn()
        }

    def handle_input(self):
        input_values = []
        for k in self.k_pads:
            val = k.getch()
            if val != -1:
                input_values.append(val)

        for v in input_values:
            try:
                self.keybinds[v]()
            except:
                self.g.renderer.screen.addstr(
                    self.g.height / 2,
                    self.g.width / 2,
                    str(v)
                )


class Renderer(object):

    def __init__(self, disp_terminal, width, height):
        # Height and Width in Characters
        self.width = width
        self.height = height
        self.buffering = False

        # Screen setup
        self.screen = disp_terminal

        # Remove cursor and input echo.
        curses.curs_set(0)
        curses.noecho()

        # Remove enter requirement.
        curses.cbreak()

    def get_screen_dims(self):
        return (self.width, self.height)

    def render(self):
        if not self.buffering:
            raise ValueError('Cannot render without buffering.')

        else:
            self.buffering = False

            # Draw the buffer to the screen.
            self.screen.refresh()

            # Flush the buffer.
            self.screen.clear()

    def draw(self, o):
        if not self.buffering:
            self.buffering = True
        self.screen.addstr(o.y, o.x, o.disp)

    def kill(self):
        curses.nocbreak()
        self.screen.keypad(0)
        curses.echo()
        curses.endwin()

    def p(self, val):
        self.screen.addstr(self.height - 1, 1, str(val))

    def print_center(self, message):
        self.buffering = True
        message = str(message)
        self.screen.addstr(
            self.height / 2, self.width / 2 - len(message), message)


class Game(object):

    def __init__(self):

        # State
        self.state = 'init'
        self.valid_states = ['init', 'play', 'pause', 'gameover', 'quit']

        # Rendering
        scr = curses.initscr()
        height, width = scr.getmaxyx()
        self.renderer = Renderer(scr, width, height)
        self.width = width
        self.height = height

        # Actors
        self.player = Player(self, x=self.width / 2, y=self.height - 1)
        self.enemies = []
        self.projectiles = []
        self.vfx = []
        self.collision_arr = [
            [None for i in range(self.height)] for j in range(self.width)]

        # Controls / Input
        self.controller = Controller(self)

        # Framerate
        self.framerate_max = 30
        self.last_tick = time.time()

    def reset_collision_arr(self):
        self.actor_pos = [
            [None for i in range(self.height + 1)] for j in range(self.width + 1)]

    def set_state(self, new_state):
        if new_state in self.valid_states:
            self.state = new_state
        else:
            raise ValueError('Invalid game state: ' + str(new_state))

    def draw_all(self):

        object_lists = [
            [self.player],
            self.enemies,
            self.projectiles,
            self.vfx
        ]
        for o_list in object_lists:
            for o in o_list:
                self.renderer.draw(o)

    def __tick__(self):
        object_lists = [
            [self.player],
            self.enemies,
            self.projectiles,
            self.vfx
        ]

        for o_list in object_lists:
            for o in o_list:
                o.on_tick()

    def tick(self):
        # Figure out how long it has been since last tick.
        cur_time = time.time()
        lag = cur_time - self.last_tick

        # Only tick if we're under the framerate limit.
        if lag > 1. / self.framerate_max:
            self.last_tick = cur_time
            # Tick logic
            self.__tick__()
            # Update the screen
            self.draw_all()
            # Render to the screen
            self.renderer.render()

    def play(self):
        self.set_state('play')

        while self.state == 'play':
            self.controller.handle_input()
            self.tick()

        self.quit()

    def gameover(self):
        self.set_state('gameover')
        self.renderer.print_center('GAMEOVER')
        self.renderer.render()
        time.sleep(5)
        self.quit()

    def quit(self):
        self.set_state('quit')
        self.renderer.kill()
        exit()


class Actor(object):

    def __init__(
        self,
        g,
        x=0, y=0,
        dx=0, dy=0,
        hp=3,
        speed=2,
        disp='/=\\',
        orient=-1,
        cooldown=0
    ):
        self.hp = hp
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.speed = speed
        self.disp = disp
        self.g = g
        self.orient = orient
        self.cooldown = cooldown
        self.last_shot = 0

    def __getitem__(self, item):
        return self.__getattribute__(item)

    def __setitem__(self, key, value):
        self.__setattr__(key, value)

    # magnitudes is a tuple of magnitudes (x, y)
    def __move__(self, target):

        screen_col = self.screen_check(target)

        if screen_col is not None:
            self.on_screen_collide(screen_col)
        else:
            collided = self.collision_check(target)

            # If we didn't collide, update our position.
            if not collided:
                self.update_position(target)
                self.on_move()

    def move(self, magnitudes):
        x, y = magnitudes
        x = int(x * self.speed)
        y = int(y * self.speed)

        # Move while either direction has distance left.
        while x != 0 or y != 0:
            if x < 0:
                x_dir = -1
            elif x > 0:
                x_dir = 1
            else:
                x_dir = 0

            if y < 0:
                y_dir = - 1
            elif y > 0:
                y_dir = 1
            else:
                y_dir = 0

            x -= x_dir
            y -= y_dir
            self.__move__([self.x + x_dir,  self.y + y_dir])

    def update_position(self, target):

        disp_len = len(self.disp)

        # Clear previous position.
        for i in range(disp_len):
            self.g.collision_arr[self.x + i][self.y] = None

        # Change position.
        self.x, self.y = target

        # Update collision array.
        for i in range(disp_len):
            self.g.collision_arr[self.x + i][self.y] = self

    def on_screen_collide(self, direction):
        x = min([self.x, self.g.width - len(self.disp)])
        x = max([x, 0])
        y = min([self.y, self.g.height - 1])
        y = max([y, 0])
        self.update_position([x, y])

    # Check to see if we are going out of bounds.
    def screen_check(self, target):
        if target[0] < 0:
            direction = 'left'
        elif target[0] > self.g.width - len(self.disp) - 1:
            direction = 'right'
        elif target[1] < 0:
            direction = 'top'
        elif target[1] > self.g.height - 1:
            direction = 'bottom'
        else:
            direction = None

        return direction

    def __collision_check__(self, target):
        # Check the position we're moving into
        tx, ty = target
        new_pos = self.g.collision_arr[tx][ty]
        if new_pos != None and new_pos != self:
            return new_pos
        else:
            return None

    # Check and handle collisions
    def collision_check(self, target):
        collided = False
        # Check for collisions along the entire sprite.
        for i in range(len(self.disp)):
            collider = self.__collision_check__([target[0] + i, target[1]])
            if collider:
                collided = True
                # Handle the collison.
                self.collide(collider)

        return collided

    # Magnitudes is a tuple of magnitudes (x, y)
    def apply_force(self, magnitudes):
        self.dx += magnitudes[0]
        self.dy += magnitudes[1]

    def get_center(self):
        x = self.x + len(self.disp) / 2
        x = max([x, 0])
        x = min([x, self.g.width - 2])

        y = self.y + len(self.disp) / 2
        y = max([y, 0])
        y = min([y, self.g.height - 1])

        return (x, y)

    def collide(self, recipient):
        r_type = type(recipient)

    def shoot(self):
        t = time.time()
        if t - self.last_shot > self.cooldown:
            self.last_shot = t
            power = 1
            velocity = 1 * self.orient  # Up is negative.
            x, y = self.get_center()

            # Make it spawn above the actor if possible
            y += self.orient
            y = max([y, 0])
            y = min([y, self.g.height - 1])

            Projectile(self.g, x=x, y=y, dy=velocity).spawn(damage=power)

    def add_hp(self, amount):
        self.hp += amount

        # Die if no HP left.
        if self.hp <= 0:
            self.destroy()

    def destroy(self):
        for i in range(len(self.disp)):
            self.g.collision_arr[self.x + i][self.y] = None
        self.on_destroy()

    def on_tick(self):
        self.move((self.dx, self.dy))

    def on_destroy(self):
        pass

    def on_move(self):
        pass


class Projectile(Actor):

    def spawn(self, damage=1, disp='|'):
        self.damage = damage
        self.speed = 1
        self.disp = disp
        self.g.projectiles.append(self)
        self.update_position([self.x, self.y])

    def on_screen_collide(self, direction):
        self.destroy()

    def collide(self, recipient):
        r_type = type(recipient)
        # write_log('COLLISION: '+str(r_type))

        if r_type == Player or r_type == Enemy:
            recipient.add_hp(-1 * self.damage)

        elif r_type == Projectile:
            recipient.destroy()

        self.destroy()

    def on_destroy(self):
        if self in self.g.projectiles:
            self.g.projectiles.remove(self)

    def on_move(self):
        pass


class Player(Actor):

    def on_tick(self):
        self.move((self.dx, self.dy))

    def on_destroy(self):
        self.g.gameover()


class Enemy(Actor):

    def spawn(self, damage=1, disp='<-->'):
        self.hp = 3
        self.orient = 1
        self.speed = 1
        self.cooldown = 2
        self.damage = damage
        self.disp = disp
        self.g.enemies.append(self)
        self.update_position([self.x, self.y])

    def on_destroy(self):
        if self in self.g.enemies:
            self.g.enemies.remove(self)

    def on_tick(self):
        self.stumble()
        r = random.random()
        if r > 0.1:
            self.shoot()
        self.move((self.dx, self.dy))

    def stumble(self):
        stumble_x = random.random()
        stumble_y = random.random()

        if stumble_x > 0.5:
            self.dx += 0.1
        else:
            self.dx -= 0.1

        if stumble_y > 0.65:
            self.dy += 0.3
        else:
            self.dy = 0.0

        # Cap the values
        self.dx = max([self.dx, -1])
        self.dx = min([self.dx, 1])

        self.dy = max([self.dy, -1])
        self.dy = min([self.dy, 1])

    def on_screen_collide(self, direction):
        x = min([self.x, self.g.width - len(self.disp)])
        x = max([x, 0])
        y = min([self.y, self.g.height - 1])
        y = max([y, 0])

        if direction == 'left' or direction == 'right':
            self.dx *= -0.8
        elif direction == 'top' or direction == 'bottom':
            self.dy *= -0.2

        self.update_position([x, y])

    def collide(self, recipient):
        r_type = type(recipient)
        # write_log('COLLISION: '+str(r_type))

        if r_type == Player:
            recipient.add_hp(-1 * self.damage)

        elif r_type == Enemy:
            self.dx *= -1
            self.dy *= -1

        elif r_type == Projectile:
            self.add_hp(-1 * recipient.damage)
            recipient.destroy()

class VFX(object):

    def __init__(self, disp, x, y, timeout):
        self.disp = disp
        self.x = x
        self.y = y
        self.timeout = timeout

    def on_tick(self):
        pass


def main():
    # with open('log.txt', 'wb') as f:
    #     f.write('')

    g = Game()
    g.play()


def write_log(message):
    with open('log.txt', 'ab') as f:
        f.write(str(message) + '\n\n')

main()


# It's an even odd thing. Make collision handle the sprite width.
