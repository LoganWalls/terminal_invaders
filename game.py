import time
from copy import deepcopy

class Renderer(object):

    def __init__(self, height=100, width=24):
        # Height and Width in Characters
        self.width = 100
        self.height = 24
        self.buffering = False
        self.background = ' '
        self.blank_screen = [[self.background for i in range(self.width)] for j in range(self.height)]
        self.canvas  = deepcopy(self.blank_screen)
        self.buffer = deepcopy(self.blank_screen)

    def get_screen_dims(self):
        return (self.width, self.height)

    def render(self):
        if not self.buffering:
            raise ValueError('Cannot render without buffering.')

        else:
            self.canvas = deepcopy(self.buffer)
            self.buffer = deepcopy(self.blank_screen)
            self.buffering = False
            out = ''
            for row in self.canvas:
                out = out + ''.join(row) + '\n'

            print out[:-1]

    def draw(self, o):
        if not self.buffering:
            self.buffering = True
        self.buffer[o.y][o.x] = o.disp


class Game(object):

    def __init__(self):

        # State
        self.state = 'init'
        self.valid_states = ['init', 'play', 'pause', 'gameover']

        # Rendering
        self.renderer = Renderer()
        self.width, self.height = self.renderer.get_screen_dims()

        # Actors
        self.player = Actor(x=self.width / 2, y=self.height-1)
        self.enemies = []
        self.projectiles = []

        # Framerate
        self.framerate_max = 60
        self.last_tick = time.time()


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
        self.move(self.player, 'x', self.player.dx)
        self.move(self.player, 'y', self.player.dy)

        for e in self.enemies:
            self.move(e, 'x', e.dx)
            self.move(e, 'y', e.dy)

        for p in self.projectiles:
            self.move(p, 'x', p.dx)
            self.move(p, 'y', p.dy)


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
            self.tick()

    def move(self, o, axis, magnitude):
        if axis == 'x':
            dim = self.width
        elif axis == 'y':
            dim = self.height

        # If they are going in the negative direction, stop at lower bound.
        if magnitude < 0:
            o[axis] = max([o[axis] + magnitude, 1])
        # If they are going in the positive direction, stop at upper bound.
        else:
            o[axis] = min([o[axis] + magnitude, dim - 1])

    def __set_default_keybinds__(self):
        self.keybinds = {''}


class Actor(object):

    def __init__(self, x=0, y=0, dx=0, dy=-1, hp=3, disp='^'):
        self.hp = hp
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.disp = disp

    def __getitem__(self, item):
        return self.__getattribute__(item)

    def __setitem__(self, key, value):
        self.__setattr__(key, value)


def main():
    g = Game()
    g.play()
    u_in = ''
    # while u_in not 'e':
    #     u_in = raw_input()

main()