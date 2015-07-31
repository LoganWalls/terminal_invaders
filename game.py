import time
import curses
from copy import deepcopy


class Controller(object):

    def __init__(self, g, input_terminal):
        # A reference to the parent game object.
        self.g = g

        # A terminal to read the input
        self.terminal = input_terminal

        # Read key inputs.
        self.terminal.keypad(1)
        # Make getch non-blocking
        self.terminal.nodelay(1)

        self.__set_default_keybinds__()

    def __set_default_keybinds__(self):
        self.keybinds = {
            27: self.g.quit,
            258: lambda: self.g.player.move((0, 1)),
            259: lambda: self.g.player.move((0, -1)),
            260: lambda: self.g.player.move((-1, 0)),
            261: lambda: self.g.player.move((1, 0)),
            32: self.g.player.shoot,
            101: lambda: Enemy(
                self.g,
                x=self.g.width / 2 + 1,
                y=self.g.height / 10
            ).spawn()
        }

    def handle_input(self):
        input_value = self.terminal.getch()
        if input_value != -1:
            try:
                self.keybinds[input_value]()
            except:
                self.g.renderer.screen.addstr(
                    self.g.height / 2,
                    self.g.width / 2,
                    str(input_value)
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


class Game(object):

    def __init__(self, width, height):

        # State
        self.state = 'init'
        self.valid_states = ['init', 'play', 'pause', 'gameover', 'quit']

        # Rendering
        self.renderer = Renderer(curses.initscr(), width, height)
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
        self.controller = Controller(self, curses.newwin(1, 1))

        # Framerate
        self.framerate_max = 30
        self.last_tick = time.time()

        # Collision Detection
        self.collisions = []

    def reset_collision_arr(self):
        self.actor_pos = [
            [None for i in range(self.height+1)] for j in range(self.width+1)]

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
            self.handle_collisions()
            # Update the screen
            self.draw_all()
            # Render to the screen
            self.renderer.render()

    def handle_collisions(self):
        while len(self.collisions):
            colliders = self.collisions.pop()
            instigator, recipient = colliders
            instigator.collide(recipient)

    def play(self):
        self.set_state('play')

        while self.state == 'play':
            self.controller.handle_input()
            self.tick()

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
        orient=-1
    ):
        self.hp = hp
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.speed = speed
        # self.disp = ord(disp)
        self.disp = disp
        self.g = g
        self.orient = orient

    def __getitem__(self, item):
        return self.__getattribute__(item)

    def __setitem__(self, key, value):
        self.__setattr__(key, value)

    # magnitudes is a tuple of magnitudes (x, y)
    def move(self, magnitudes):

        if magnitudes[0] != 0 or magnitudes[1] != 0:

            # Where are we trying to move to?
            target = [self.x, self.y]

            for i, m in enumerate(magnitudes):
                magnitude = int(m * self.speed)
                if i == 0:
                    axis = 'x'
                elif i == 1:
                    axis = 'y'
                target[i] = self[axis] + magnitude 

            screen_col = self.screen_check(target)
            if screen_col != None:
                self.on_screen_collide(screen_col)
            else:
                collided = False
                # Check for collisions along the entire sprite.
                for i in range(len(self.disp)):
                    collider = self.collision_check([target[0] + i, target[1]])
                    if collider:
                        collided = True
                        # Handle the collison.
                        self.collide(collider)

                # If we didn't collide, update our position.
                if not collided:
                    self.update_position(target)
                    self.on_move()

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
        pass

    # Check to see if we are going out of bounds.
    def screen_check(self, target):
        if target[0] < 0:
            direction = 'left'
        elif target[0] > self.g.width - len(self.disp):
            direction = 'right'
        elif target[1] < 0:
            direction = 'top'
        elif target[1] > self.g.height - 1:
            direction = 'bottom'
        else:
            direction = None

        return direction

    # Check and handle collisions
    def collision_check(self, target):
        # Check the position we're moving into
        tx, ty = target
        new_pos = self.g.collision_arr[tx][ty]
        if new_pos != None and new_pos != self:
            return new_pos
        else:
            return None

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

    def collide(self, instigator):
        i_type = type(instigator)

    def shoot(self):
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
         
         #Die if no HP left.
         if self.hp <= 0:
             self.destroy()

    def destroy(self):
        self.g.collision_arr[self.x][self.y] = None
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
        self.disp = disp
        self.g.projectiles.append(self)
        self.update_position([self.x, self.y])

    def on_screen_collide(self, direction):
        self.destroy()

    def collide(self, recipient):
        r_type = type(recipient)
        #write_log('COLLISION: '+str(r_type))

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

    def on_screen_collide(self, direction):
        x = min([self.x, self.g.width - len(self.disp)])
        x = max([x, 0])
        y = min([self.y, self.g.height - 1])
        y = max([y, 0])
        self.update_position([x,y])


class Enemy(Actor):

    def spawn(self, damage=1, disp='<->'):
        self.damage = damage
        self.disp = disp
        self.g.enemies.append(self)
        self.update_position([self.x, self.y])

    def on_destroy(self):
        if self in self.g.enemies:
            self.g.enemies.remove(self)


class VFX(object):

    def __init__(self, disp, x, y, timeout):
        self.disp = disp
        self.x = x
        self.y = y
        self.timeout = timeout

    def on_tick(self):
        pass


def main():
    #with open('log.txt', 'wb') as f:
    #    f.write('')
    
    g = Game(100, 24)
    g.play()


def write_log(message):
    with open('log.txt', 'ab') as f:
        f.write(str(message)+'\n\n')

main()




######It's an even odd thing. Make collision handle the sprite width.
