import pygame
import os
import time
import logging
from threading import Timer, Thread
from fontTools.ttLib import TTFont
from fontTools.unicode import Unicode
from itertools import chain
import json
import urllib
import io
import random
import re
import webcolors
BADGE_TYPES = ['global_mod', 'admin', 'broadcaster', 'mod', 'staff', 'turbo', 'subscriber']
logger = logging.getLogger("display")
WIDTH = 0
HEIGHT = 1

TWITCH_COLORS = ['Blue', 'Coral', 'DodgerBlue', 'SpringGreen', 'YellowGreen', 'Green', 'OrangeRed', 'Red', 'GoldenRod',
                 'HotPink', 'CadetBlue', 'SeaGreen', 'Chocolate', 'BlueViolet', 'Firebrick']


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
        self.emotes = {}
        self.usercolors = {}
        self.follower_to_display = None
        self.badges = {}
        self.logos = {}

    def download_logo(self, channel):
        response = urllib.urlopen('https://api.twitch.tv/kraken/users/{0}'.format(channel))
        data = json.load(response)
        response = urllib.urlopen(data['logo'])
        image_str = response.read()
        img_file = open('logocache/{0}.png'.format(channel), 'w')
        img_file.write(image_str)
        img_file.close()

    def load_logo(self, channel):
        if not os.path.isfile('logocache/{0}.png'.format(channel)):
            if not os.path.isdir('logocache'):
                os.mkdir('logocache')
            self.download_logo(channel)
        self.logos[channel] = {}
        if os.path.isfile('logocache/{0}.png'.format(channel)):
            image_str = open('logocache/{0}.png'.format(channel), 'r').read()
            image_file = io.BytesIO(image_str)
            surface = pygame.image.load(image_file)
            ratio = self.font_height / float(surface.get_height())
            new_size = (int(surface.get_width() * ratio), self.font_height)
            resized = pygame.transform.scale(surface, new_size)
            self.logos[channel] = resized.convert_alpha()

    def get_logo(self, channel):
        if channel not in self.logos:
            self.load_logo(channel)
        return self.logos[channel]

    def download_badges(self, channel):
        response = urllib.urlopen('https://api.twitch.tv/kraken/chat/{0}/badges'.format(channel))
        data = json.load(response)
        for btype in BADGE_TYPES:
            if data[btype]:
                response = urllib.urlopen(data[btype]['image'])
                image_str = response.read()
                img_file = open('badgecache/{0}_{1}.png'.format(channel, btype), 'w')
                img_file.write(image_str)
                img_file.close()

    def load_badges(self, channel):
        if not os.path.isfile('badgecache/{0}_{1}.png'.format(channel, BADGE_TYPES[0])):
            if not os.path.isdir('badgecache'):
                os.mkdir('badgecache')
            self.download_badges(channel)
        self.badges[channel] = {}
        for btype in BADGE_TYPES:
            if os.path.isfile('badgecache/{0}_{1}.png'.format(channel, btype)):
                image_str = open('badgecache/{0}_{1}.png'.format(channel, btype), 'r').read()
                image_file = io.BytesIO(image_str)
                surface = pygame.image.load(image_file)
                ratio = self.font_height / float(surface.get_height())
                new_size = (int(surface.get_width() * ratio), self.font_height)
                resized = pygame.transform.scale(surface, new_size)
                self.badges[channel][btype] = resized.convert_alpha()

    def get_badge(self, channel, btype):
        if channel not in self.badges:
            self.load_badges(channel)
        return self.badges[channel][btype]

    def load_emote(self, id):
        if not os.path.isfile('emotecache/{0}.png'.format(id)):
            if not os.path.isdir('emotecache'):
                os.mkdir('emotecache')
            response = urllib.urlopen('http://static-cdn.jtvnw.net/emoticons/v1/{0}/3.0'.format(id))
            if response.getcode() == 404:
                response = urllib.urlopen('http://static-cdn.jtvnw.net/emoticons/v1/{0}/2.0'.format(id))
            if response.getcode() == 404:
                response = urllib.urlopen('http://static-cdn.jtvnw.net/emoticons/v1/{0}/1.0'.format(id))
            image_str = response.read()
            img_file = open('emotecache/{0}.png'.format(id), 'w')
            img_file.write(image_str)
            img_file.close()
        else:
            image_str = open('emotecache/{0}.png'.format(id), 'r').read()
        image_file = io.BytesIO(image_str)
        surface = pygame.image.load(image_file)
        ratio = self.font_height / float(surface.get_height())
        new_size = (int(surface.get_width() * ratio), self.font_height)
        resized = pygame.transform.scale(surface, new_size)
        self.emotes[id] = resized.convert_alpha()

    def blit_quicktext(self, text):
        font = pygame.font.Font("FreeSans.ttf", 72)
        surf = font.render(text, True, self.txt_color)
        self.txt_layer.fill(self.bg_color)
        self.txt_layer.blit(surf, (self.rect.width / 2 - surf.get_rect().width / 2,
                                   self.rect.height / 2 - surf.get_rect().height / 2, 0, 0))
        self.screen.blit(self.txt_layer, self.rect)
        pygame.display.update()

    def load_fonts(self):
        logger.info("Loading fonts")
        self.font_size = 62
        font_paths = ["FreeSans.ttf", "Cyberbit.ttf", "unifont.ttf"]
        self.fonts = []
        self.font_height = 0
        for fontp in font_paths:
            self.blit_quicktext("Loading font {0}".format(fontp))
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
        # probably dont need a crazy font for ascii range
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
        prepends = [self.get_logo(channel)]
        if usertype == 'mod':
            prepends.append(self.get_badge(channel, 'mod'))
        elif usertype:
            prepends.append('^' + usertype + '^_')
        if subscriber:
            prepends.append(self.get_badge(channel, 'subscriber'))
        return prepends

    def wraptext(self, text, maxwidth):
        print text
        lines = []
        cut_i = len(text) - 1
        while text:
            width = self.get_list_rendered_length(text[:cut_i + 1])
            if width > maxwidth:
                cut_i -= 1
            else:
                lines.append(text[:cut_i + 1])
                text = text[cut_i + 1:]
                if text:
                    cut_i = len(text) - 1
        return lines

    def get_list_rendered_length(self, target_list):
        width = 0
        for item in target_list:
            if isinstance(item, str):
                width += self.get_text_width(item)
            else:
                width += item.get_width()
        return width

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
        surfaces = []
        if isinstance(text, list):
            for item in text:
                surfaces.extend(self.render_text(item, color, aa))
        elif isinstance(text, str):
            current_font = self.fonts[0]
            i = 0
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
        else:
            return [text]
        return surfaces

    def make_emote_surfs(self, message):
        for emote in self.emotes:
            matches = re.finditer(emote['regex'], message)
            indexes = []
            for match in matches:
                indexes.append(match.span(0))

    def get_emote(self, id):
        if id not in self.emotes:
            self.load_emote(id)
        return self.emotes[id]

    def generate_emoteindex(self, emotelist):
        emoteindxs = {}
        for emoteinfo in emotelist:
            id_rgx = r"(\d*):"
            id = re.search(id_rgx, emoteinfo)
            index_rgx = r"(\d*)-(\d*)"
            results = re.findall(index_rgx, emoteinfo)
            for indexes in results:
                emoteindxs[int(indexes[0])] = (int(indexes[1]), id.group(1))
        return emoteindxs

    def insert_emotesurfs(self, text, emoteindxs):
        rendered = []
        i = 0
        while i < len(text):
            if i in emoteindxs:
                start_index = i
                end_index, id = emoteindxs[start_index]
                rendered.append(self.get_emote(id))
                i = end_index + 1
            else:
                rendered.append(text[i])
                i += 1
        return rendered

    def render_emotes(self, text, emotes):
        if emotes:
            emotelist = emotes.split('/')
            emoteindxs = self.generate_emoteindex(emotelist)
            rendered = self.insert_emotesurfs(text, emoteindxs)
            return rendered
        else:
            return list(text)

    def prepare_surfaces(self, prepends, username, usercolor, text, emotes):
        # each line consists of a list of surfaces
        prepends = self.render_text(prepends, self.txt_color)
        if usercolor:
            usercolor = usercolor[1:]  # cut off the # from the start of the string
            hexcolor = (int(usercolor[:2], 16), int(usercolor[2:4], 16), int(usercolor[4:], 16))
        else:
            hexcolor = self.get_usercolor(username)
        prepends.extend(self.render_text(username, hexcolor))
        prepends.extend(self.render_text(' : ', self.txt_color))
        prepends.extend(self.render_emotes(text, emotes))
        wrapped = self.wraptext(prepends, self.size[WIDTH])
        new_lines = []
        for wrapped_line in wrapped:
            new_lines.append(self.render_text(wrapped_line, self.txt_color))
        return new_lines

    def get_usercolor(self, username):
        if username not in self.usercolors:
            self.usercolors[username] = webcolors.name_to_rgb(random.choice(TWITCH_COLORS))
        return self.usercolors[username]

    def blit_lines(self, lines, surface):
        y_pos = self.size[HEIGHT] - (self.font_height * (len(lines)))
        for line in lines:
            x_pos = 0
            for part in line:
                surface.blit(part, (x_pos, y_pos, 0, 0))
                x_pos += part.get_width()
            y_pos += self.font_height

    def new_activity(self):
        if self.idle_timer.is_alive():
            self.idle_timer.cancel()
        self.enable_display()
        self.changed = True
        self.idle_timer = Timer(60 * 10, self.disable_display)
        self.idle_timer.start()

    def new_twitchmessage(self, result):
        self.new_activity()
        prepends = self.make_prependstr(result['user-type'], bool(int(result['subscriber'])), result['channel'])
        new_lines = self.prepare_surfaces(prepends, result['display-name'] or result['username'], result['color'],
                                          result['message'], result['emotes'])
        self.lines.extend(new_lines)
        self.lines = self.lines[-(self.max_lines):len(self.lines)]
        return

    def new_follower(self, followerinfo, name):
        self.follower_to_display = (followerinfo['display_name'] or followerinfo['name'], name)
        self.new_activity()
        pass

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
                if self.follower_to_display:
                    self.blit_quicktext("{0} Followed {1}!".format(self.follower_to_display[0],
                                                                   self.follower_to_display[1]))
                    self.follower_to_display = None
                    self.changed = False
                    self.display_follower_timer = Timer(3, self.start_rendering)
                    self.display_follower_timer.start()
                    break
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
