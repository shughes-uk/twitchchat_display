import pygame
import os
import time
import logging
from threading import Timer, Thread
from fontTools.ttLib import TTFont
from fontTools.unicode import Unicode
from itertools import chain
logger = logging.getLogger("display")
WIDTH = 0
HEIGHT = 1


def turn_screen_off():
    os.system('/opt/vc/bin/tvservice -o')


def turn_screen_on():
    os.system('/opt/vc/bin/tvservice -p ;fbset -depth 8; fbset -depth 16;')


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
        self.load_fonts()
        self.max_lines = (self.size[HEIGHT] / self.font_height)
        self.changed = True
        self.lines = []

    def load_fonts(self):
        logger.info("Loading fonts")
        self.font_size = 62
        font_paths = ["FreeSans.ttf", "Cyberbit.ttf", "unifont.ttf"]
        self.fonts = []
        self.font_height = 0
        for fontp in font_paths:
            pg_font = pygame.font.Font(fontp, self.font_size)
            fontinfo = self.get_font_details(fontp)
            if pg_font.get_linesize() > self.font_height:
                self.font_height = pg_font.get_linesize()
            self.fonts.append((pg_font, fontinfo, fontp))
            logger.debug("Loaded {0}".format(fontp))
        logger.info("Fonts loaded successfully")

    def get_font_details(self, font_path):
        ttf = TTFont(font_path, 0, verbose=0, allowVID=0, ignoreDecompileErrors=True, fontNumber=-1)
        chars = chain.from_iterable([y + (Unicode[y[0]],) for y in x.cmap.items()] for x in ttf["cmap"].tables)
        font_chars = list(chars)
        ttf.close()
        char_dict = {}
        for char_info in font_chars:
            char_dict[char_info[0]] = True
        return char_dict

    def required_font(self, char):
        #probably dont need a crazy font for ascii range
        if ord(char) > 128:
            for font in self.fonts:
                if ord(char) in font[1]:
                    return font
            logger.critical("Couldn't find font for character {0}".format(repr(char)))
            return self.fonts[0]
        else:
            return self.fonts[0]

    def init_default_cfg(self):
        self.bg_color = [0x32, 0x32, 0x3E]
        self.txt_color = [0xFF, 0xFF, 0xFF]

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

    def wraptext(self, text, maxwidth):
        lines = []
        while text:
            width = 0
            cut_i = len(text)
            width = self.get_text_width(text[:cut_i])
            while width > maxwidth:
                cut_i -= 1
                width = self.get_text_width(text[:cut_i])
            lines.append(text[:cut_i])
            text = text[cut_i:]
        return lines

    def get_text_width(self, text):
        current_font = self.fonts[0]
        i = 0
        total_width = 0
        while i < len(text):
            rq_font = self.required_font(text[i])
            if rq_font != current_font:
                if text[:i]:
                    width = current_font[0].size(text[:i])[WIDTH]
                    total_width += width
                    text = text[i:]
                    i = 0
                current_font = rq_font
            else:
                i += 1
        width = current_font[0].size(text)[WIDTH]
        total_width += width
        return total_width

    def render_text(self, text, color, aa=True):
        current_font = self.fonts[0]
        i = 0
        surfaces = []
        while i < len(text):
            rq_font = self.required_font(text[i])
            if rq_font != current_font:
                if text[:i]:
                    part = current_font[0].render(text[:i], aa, color)
                    surfaces.append(part)
                    text = text[i:]
                    i = 0
                current_font = rq_font
            else:
                i += 1
        part = current_font[0].render(text, aa, color)
        surfaces.append(part)
        return surfaces

    def prepare_surfaces(self, prepends, username, usercolor, text):
        # each line consists of a list of surfaces
        new_lines = []
        new_line = []
        before_message = '%s%s : ' % (prepends, username)
        wrapped = self.wraptext(before_message + text, self.size[WIDTH])
        first_line = wrapped[0]
        new_line.extend(self.render_text(prepends, self.txt_color))
        if usercolor:
            hexcolor = (int(usercolor[:2], 16), int(usercolor[2:4], 16), int(usercolor[4:], 16))
            new_line.extend(self.render_text(username, hexcolor))
        else:
            new_line.extend(self.render_text(username, self.txt_color))
        new_line.extend(self.render_text(' : ', self.txt_color))
        new_line.extend(self.render_text(first_line[len(before_message):], self.txt_color))
        new_lines.append(new_line)
        for wrappedline in wrapped[1:]:
            new_lines.append(self.render_text(wrappedline, self.txt_color))
        return new_lines

    def blit_lines(self, lines, surface):
        y_pos = self.size[HEIGHT] - (self.font_height * (len(lines)))
        for line in lines:
            x_pos = 0
            for part in line:
                surface.blit(part, (x_pos, y_pos, 0, 0))
                x_pos += part.get_width()
            y_pos += self.font_height

    def new_twitchmessage(self, message):
        if self.idle_timer.is_alive():
            self.idle_timer.cancel()
        prepends = self.make_prependstr(message['user-type'], message['subscriber'], message['channel'])
        new_lines = self.prepare_surfaces(prepends, message['display-name'] or message['username'], message['color'],
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
