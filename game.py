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
                                x=self.g.width / 2,
                                y=self.g.height / 10
                                ).spawn()
                        }

    def handle_input(self):
        input_value = self.terminal.getch()
        if input_value != -1:
            self.keybinds[input_value]()
            try:
                pass
            except:
                self.g.renderer.screen.addstr(
                                    self.g.height/2,
                                    self.g.width/2,
                                    str(input_value)
                                )


class Renderer(object):

    def __init__(self, disp_terminal, width, height):
        # Height and Width in Characters
        self.width = width
        self.height = height
        self.buffering = False
        #self.canvas  = [[None for i in range(self.width)] for j in range(self.height)]

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


    def _draw(self, o):
        if not self.buffering:
            self.buffering = True
        self.buffer[o.y][o.x] = o.disp

    def draw(self, o):
        if not self.buffering:
            self.buffering = True
        self.screen.addstr(o.y, o.x, o.disp)

    def kill(self):
        curses.nocbreak()
        self.screen.keypad(0)
        curses.echo()
        curses.endwin()


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
        self.player = Player(self, x=self.width / 2, y=self.height-1)
        self.enemies = []
        self.projectiles = []
        self.vfx = []

        #Controls / Input
        self.controller = Controller(self, curses.newwin(1,1))

        # Framerate
        self.framerate_max = 60
        self.last_tick = time.time()

        # Collision Detection
        self.collisions = []


    def set_state(self, new_state):
        if new_state in self.valid_states:
            self.state = new_state
        else:
            raise ValueError('Invalid game state: '+str(new_state))

    def draw_all(self):

        self.renderer.draw(self.player)

        for e in self.enemies:
            self.renderer.draw(e)

        for p in self.projectiles:
            self.renderer.draw(p)


    def __tick__(self):
        # self.player.move((self.player.dx, self.player.dy))

        # for e in self.enemies:
        #     e.move((e.dx, e.dy))

        # for p in self.projectiles:
        #     p.move((p.dx, p.dy))
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

        for i, m in enumerate(magnitudes): 
            magnitude = m * self.speed

            if i == 0:
                axis = 'x'
                dim = self.g.width - 2
            elif i == 1:
                axis = 'y'
                dim = self.g.height - 1

            # If they are going in the negative direction, stop at lower bound.
            if magnitude < 0:
                self[axis] = int(max([self[axis] + magnitude, 0]))
            # If they are going in the positive direction, stop at upper bound.
            else:
                self[axis] = int(min([self[axis] + magnitude, dim]))

        self.collision_check()


    def screen_collide(self, direction):
        # Behaviour when this actor reaches an edge.
        pass

    def collision_check(self):
        # If we collide with a screen edge, add it to the collisions queue.
        if self.x == 0:
            direction = 'left'
        elif self.x == self.g.width - 2:
            direction = 'right'
        elif self.y == 0:
            direction = 'top'
        elif self.y == self.g.height - 1:
            direction = 'bottom'
        else:
            direction = None

        if direction:
            self.screen_collide(direction)

        # Check for collisions with other objects
        o_lists = [[self.g.player], self.g.enemies, self.g.projectiles]
        for objects in o_lists:
            for o in objects:
                if o.x == self.x and o.y == self.y:
                    if o != self:
                        self.g.collisions.append((self, o))


    # Magnitudes is a tuple of magnitudes (x, y)
    def apply_force(self, magnitudes):
        self.dx += magnitudes[0]
        self.dy += magnitudes[1]

    def get_center(self):
        x = self.x + len(self.disp)/2
        x = max([x, 0])
        x = min([x, self.g.width - 2])

        y = self.y + len(self.disp)/2
        y = max([y, 0])
        y = min([y, self.g.height - 1])

        return (x, y)

    def collide(self, instigator):
        i_type = type(instigator)


    def shoot(self):
        power = 1
        velocity = 0.75 * self.orient # Up is negative.
        x, y = self.get_center()

        # Make it spawn above the actor if possible
        y += self.orient
        y = max([y, 0])
        y = min([y, self.g.height - 1])

        Projectile(self.g, x=x, y=y, dy=velocity).spawn(damage=power)

    def add_hp(self, amount):
        self.hp += amount
        if self.hp <= 0:
            self.destroy()

    def on_tick(self):
        self.move((self.dx, self.dy))





class Projectile(Actor):

    def spawn(self, damage=1, disp='|'):
        self.damage = damage
        self.disp = disp
        self.g.projectiles.append(self)

    def screen_collide(self, dir):
        self.destroy()

    def collide(self, recipient):
        r_type = type(recipient)

        if r_type == Player or r_type == Enemy:
            recipient.add_hp(-1 * self.damage)

        elif r_type == Projectile:
            recipient.destroy()

        self.destroy()



    def destroy(self):
        if self in self.g.projectiles:
            self.g.projectiles.remove(self)

class Player(Actor):

    def UI(self):
        pass

class Enemy(Actor):

    def spawn(self, damage=1, disp='<->'):
        self.damage = damage
        self.disp = disp
        self.g.enemies.append(self)

    def ai(self):
        pass

    def destroy(self):
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
    g = Game(100, 24)
    g.play()

main()
