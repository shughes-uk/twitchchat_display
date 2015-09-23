import pygame
import os
import time
from threading import Timer, Thread

WIDTH = 0
HEIGHT = 1


def turn_screen_off():
    os.system('/opt/vc/bin/tvservice -o')


def turn_screen_on():
    os.system('/opt/vc/bin/tvservice -p ;fbset -depth 8; fbset -depth 16;')


def wraptext(text, font, maxwidth):
    lines = []
    while text:
        width = 0
        cut_i = len(text)
        width = font.size(text[:cut_i])[WIDTH]
        while width > maxwidth:
            cut_i -= 1
            width = font.size(text[:cut_i])[WIDTH]

        lines.append(text[:cut_i])
        text = text[cut_i:]
    return lines


class console:

    def __init__(self, screen_width, screen_height):
        if not pygame.display.get_init():
            turn_screen_on()
            pygame.init()
        self.screen = pygame.display.set_mode((screen_width, screen_height))
        self.init_default_cfg()
        self.rect = pygame.Rect(self.screen.get_rect())
        self.rect.size = self.screen.get_size()
        self.size = self.screen.get_size()
        self.txt_layer = pygame.Surface(self.size)
        self.font_size = 62
        self.font = pygame.font.SysFont('droidserif.ttf', self.font_size)
        self.font_height = self.font.get_linesize()
        self.max_lines = (self.size[HEIGHT] / self.font_height)
        self.changed = True
        self.lines = []

    def init_default_cfg(self):
        self.bg_color = [0xFF, 0xFF, 0xFF]
        self.txt_color = [0x0, 0x0, 0x0]

    def make_prependstr(self, usertype, subscriber, channel):
        prepends = ''
        if usertype == 'mod':
            prepends = '@' + prepends
        elif usertype:
            prepends = '^' + usertype + '^_' + prepends
        if subscriber:
            prepends = '$' + prepends
        prepends = '[' + channel[:3] + ']' + prepends
        return prepends

    def prepare_surfaces(self, prepends, username, usercolor, text):
        new_lines = []
        before_message = '%s%s : ' % (prepends, username)
        wrapped = wraptext(before_message + text, self.font, self.size[WIDTH])
        first_line = wrapped[0]
        prepends_surf = self.font.render(prepends, True, self.txt_color)
        if usercolor:
            hexcolor = (int(usercolor[:2], 16), int(usercolor[2:4], 16), int(usercolor[4:], 16))
            username_surf = self.font.render(username, True, hexcolor)
        else:
            username_surf = self.font.render(username, True, self.txt_color)
        filler_surf = self.font.render(' : ', True, self.txt_color)
        message_surf = self.font.render(first_line[len(before_message):], True, self.txt_color)
        new_lines.append([prepends_surf, username_surf, filler_surf, message_surf])
        for wrappedline in wrapped[1:]:
            new_lines.append(self.font.render(wrappedline, True, self.txt_color))
        return new_lines

    def blit_lines(self, lines, surface):
        y_pos = self.size[HEIGHT] - (self.font_height * (len(lines)))
        for line in lines:
            if isinstance(line, list):
                x_pos = 0
                for part in line:
                    surface.blit(part, (x_pos, y_pos, 0, 0))
                    x_pos += part.get_width()
            else:
                surface.blit(line, (0, y_pos, 0, 0))
            y_pos += self.font_height

    def new_twitchmessage(self, message):
        if self.idle_timer.is_alive():
            self.idle_timer.cancel()
        prepends = self.make_prependstr(message['usertype'], message['subscribed'], message['channel'])
        new_lines = self.prepare_surfaces(prepends, message['displayname'] or message['username'], message['color'],
                                          message['message'])
        self.lines.extend(new_lines)
        self.lines = self.lines[-(self.max_lines):len(self.lines)]
        self.enable_display()
        self.changed = True
        self.idle_timer = Timer(60 * 10, self.disable_display)
        self.idle_timer.start()
        return

    def start(self):
        self.idle_timer = Timer(10, self.disable_display)
        self.idle_timer.start()
        self.start_rendering()

    def stop(self):
        turn_screen_on()
        if self.idle_timer.is_alive():
            self.idle_timer.cancel()
        if self.rendering:
            self.rendering = False
            if self.render_thread.is_alive():
                self.render_thread.join()
        pygame.quit()

    def start_rendering(self):
        self.rendering = True
        self.render_thread = Thread(target=self.render_loop)
        self.render_thread.start()

    def stop_rendering(self):
        self.rendering = False
        if self.render_thread.is_alive():
            self.render_thread.join()

    def render_loop(self):
        while self.rendering:
            time.sleep(0.01)
            if self.changed:
                self.txt_layer.fill(self.bg_color)
                self.blit_lines(self.lines, self.txt_layer)
                self.changed = False
                self.screen.blit(self.txt_layer, self.rect)
                pygame.display.update()

    def enable_display(self):
        if not pygame.display.get_init():
            turn_screen_on()
            pygame.display.init()
            self.screen = pygame.display.set_mode((self.size[WIDTH], self.size[HEIGHT]))
            self.rect = pygame.Rect(self.screen.get_rect())

    def disable_display(self):
        if pygame.display.get_init():
            turn_screen_off()
            pygame.display.quit()
