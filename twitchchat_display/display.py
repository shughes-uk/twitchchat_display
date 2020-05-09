import logging
import os
import random
import re
import time
import unicodedata
from threading import Lock, Thread, Timer

import pygame.ftfont
import webcolors
from fontTools.ttLib import TTFont

from .images import TwitchBadges, TwitchEmotes

logging.getLogger("PIL").setLevel(logging.WARNING)

string_types = (str,)
pygame.font = pygame.ftfont

FONT_PATHS = ["FreeSans.ttf", "OpenSansEmoji.ttf", "Cyberbit.ttf", "unifont.ttf"]
BOLD_FONT_PATHS = ["FreeSansBold.ttf"]
BADGE_TYPES = [
    "global_mod",
    "admin",
    "broadcaster",
    "mod",
    "staff",
    "turbo",
    "subscriber",
]
WIDTH = 0
HEIGHT = 1

TWITCH_COLORS = [
    "Blue",
    "Coral",
    "DodgerBlue",
    "SpringGreen",
    "YellowGreen",
    "Green",
    "OrangeRed",
    "Red",
    "GoldenRod",
    "HotPink",
    "CadetBlue",
    "SeaGreen",
    "Chocolate",
    "BlueViolet",
    "Firebrick",
]


def strip_unsupported_chars(msg):
    return unicodedata.normalize("NFKD", msg).encode("ascii", "ignore").decode()


def turn_screen_off():
    os.system("/opt/vc/bin/tvservice -o")


def turn_screen_on():
    os.system("/opt/vc/bin/tvservice -p ;fbset -depth 8; fbset -depth 16;")


class ChatScreen(object):
    def __init__(self, screen_width, screen_height, bg_color):
        self.logger = logging.getLogger(name=__name__)
        if not pygame.display.get_init():
            turn_screen_on()
            pygame.init()
        self.standby_delay = 60 * 10
        self.bg_color = bg_color
        self.lines = []
        self.screen = pygame.display.set_mode((screen_width, screen_height))
        self.rect = pygame.Rect(self.screen.get_rect())
        self.rect.size = self.screen.get_size()
        self.size = self.screen.get_size()
        self.txt_layer = pygame.Surface(self.size)
        self.idle_timer = Timer(self.standby_delay, self.disable_display)
        self.changed = True
        self.lock = Lock()
        self.viewers = {}

    def set_line_height(self, lheight):
        self.line_height = lheight
        self.max_lines = int((self.size[HEIGHT] / self.line_height) - 1)

    def new_activity(self):
        with self.lock:
            if self.idle_timer.is_alive():
                self.idle_timer.cancel()
            self.enable_display()
            self.idle_timer = Timer(self.standby_delay, self.disable_display)
            self.idle_timer.daemon = True
            self.idle_timer.start()
            self.changed = True

    def add_chatlines(self, lines):
        with self.lock:
            self.lines.extend(lines)
            self.lines = self.lines[-(self.max_lines) : len(self.lines)]
        self.new_activity()

    def blit_quicktext(self, text, color=(255, 255, 255)):
        self.new_activity()
        font = pygame.font.Font("FreeSans.ttf", 72)
        surf = font.render(text, True, color)
        self.txt_layer.fill(self.bg_color)
        self.txt_layer.blit(
            surf,
            (
                self.rect.width / 2 - surf.get_rect().width / 2,
                self.rect.height / 2 - surf.get_rect().height / 2,
                0,
                0,
            ),
        )
        self.screen.blit(self.txt_layer, self.rect)
        pygame.display.update()

    def blit_lines(self, lines, surface):
        y_pos = self.size[HEIGHT] - (self.line_height * (len(lines) + 1))
        viewerstring = ""
        for name in self.viewers:
            if self.viewers[name] > 0:
                viewerstring = viewerstring + " {0} : {1}".format(
                    name, self.viewers[name]
                )
        if viewerstring:
            font = pygame.font.Font("FreeSans.ttf", 48)
            surf = font.render(viewerstring, True, (255, 255, 255))
            y = self.size[HEIGHT] - self.line_height
            surface.blit(surf, (0, y, 0, 0))
        for line in lines:
            x_pos = 0
            for part in line:
                surface.blit(part, (x_pos, y_pos, 0, 0))
                x_pos += part.get_width()
            y_pos += self.line_height

    def start(self):
        self.new_activity()
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
        self.render_thread.daemon = True
        self.render_thread.start()

    def stop_rendering(self):
        self.rendering = False
        if self.render_thread.is_alive():
            self.render_thread.join()

    def render_loop(self):
        while self.rendering:
            time.sleep(0.1)
            if self.changed:
                with self.lock:
                    self.enable_display()
                    self.txt_layer.fill(self.bg_color)
                    self.blit_lines(self.lines, self.txt_layer)
                    self.screen.blit(self.txt_layer, self.rect)
                    pygame.display.update()
                    self.changed = False

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


class FontHelper(object):
    def __init__(self):
        self.logger = logging.getLogger(name=__name__)
        self.logger.info("Fonthelper init")
        self.font_size = 48
        self.font_height = 0
        self.fonts = []
        self.bold_fonts = []

    def load_font(self, font_path, bold=False):
        self.logger.info("Loading font {0}".format(font_path))
        pg_font = pygame.font.Font(font_path, self.font_size)
        fontinfo = self.get_font_details(font_path)
        if pg_font.get_linesize() > self.font_height:
            self.font_height = pg_font.get_linesize()
        if bold:
            self.bold_fonts.append((pg_font, fontinfo, font_path))
        else:
            self.fonts.append((pg_font, fontinfo, font_path))
        self.logger.info("Loaded {0}".format(font_path))

    def get_font_details(self, font_path):
        ttf = TTFont(
            font_path, 0, allowVID=0, ignoreDecompileErrors=True, fontNumber=-1,
        )
        try:
            return set(ch for tbl in ttf["cmap"].tables for ch in tbl.cmap)
        finally:
            ttf.close()

    def required_font(self, char, bold=False):
        if bold:
            fontlist = self.bold_fonts
        else:
            fontlist = self.fonts
        # probably dont need a crazy font for ascii range
        if ord(char) > 128:
            for font in fontlist:
                if ord(char) in font[1]:
                    return font
            self.logger.critical(
                "Couldn't find font for character {0}".format(repr(char))
            )
            return fontlist[0]
        else:
            return fontlist[0]

    def get_text_width(self, text, bold=False):
        current_font = self.required_font("a", bold)
        i = 0
        total_width = 0
        while i < len(text):
            rq_font = self.required_font(text[i], bold)
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


class TwitchChatDisplay(object):
    def __init__(self, screen_width, screen_height, client_id):
        self.bg_color = [0x28, 0x25, 0x38]
        self.txt_color = [0xFF, 0xFF, 0xFF]
        self.usercolors = {}
        self.ignore_list = []

        self.size = (screen_width, screen_height)
        self.chatscreen = ChatScreen(screen_width, screen_height, self.bg_color)
        self.font_helper = FontHelper()
        for fontp in FONT_PATHS:
            self.chatscreen.blit_quicktext(
                "Loading font {0}".format(fontp), self.txt_color
            )
            self.font_helper.load_font(fontp)
        for fontp in BOLD_FONT_PATHS:
            self.chatscreen.blit_quicktext(
                "Loading font {0}".format(fontp), self.txt_color
            )
            self.font_helper.load_font(fontp, bold=True)

        self.chatscreen.set_line_height(self.font_helper.font_height)
        self.twitch_badges = TwitchBadges(
            height=self.font_helper.font_height, client_id=client_id
        )
        self.twitch_emotes = TwitchEmotes(
            height=self.font_helper.font_height, client_id=client_id
        )

    def ignore_user(self, username):
        self.ignore_list.append(username)

    def start(self):
        self.chatscreen.start()
        msg = [
            self.render_text("Loading complete. Waiting for messages..", self.txt_color)
        ]
        self.chatscreen.add_chatlines(msg)

    def stop(self):
        self.chatscreen.stop()

    def display_message(self, text):
        self.chatscreen.blit_quicktext(text, self.txt_color)

    def get_usercolor(self, username, usercolor=None):
        if usercolor:
            usercolor = usercolor[1:]  # cut off the # from the start of the string
            hexcolor = (
                int(usercolor[:2], 16),
                int(usercolor[2:4], 16),
                int(usercolor[4:], 16),
            )
            return hexcolor
        elif username not in self.usercolors:
            self.usercolors[username] = webcolors.name_to_rgb(
                random.choice(TWITCH_COLORS)
            )
        return self.usercolors[username]

    def new_twitchmessage(self, result):
        if result["username"] not in self.ignore_list:
            new_lines = self.render_new_twitchmessage(result)
            self.chatscreen.add_chatlines(new_lines)

    def new_usernotice(self, args):
        message = args["system-msg"].replace("\\s", " ")
        new_line = self.render_text(message, self.txt_color)
        self.chatscreen.add_chatlines([new_line])

    def new_followers(self, new_followers, name, total):
        new_lines = self.render_new_followers(new_followers, name)
        self.chatscreen.add_chatlines(new_lines)

    def new_viewers(self, viewercount, name):
        self.chatscreen.viewers[name] = viewercount

    def render_new_subscriber(self, channel, subscriber, months):
        if months == 0:
            text = " {0} subscribed to {1}! ".format(subscriber, channel, months)
        else:
            text = " {0} subscribed to {1} for {2} months in a row! ".format(
                subscriber, channel, months
            )
        rendered = self.render_text(text, self.txt_color)
        return rendered

    def render_emotes(self, text, emotes):
        if emotes:
            emotelist = emotes.split("/")
            emoteindxs = self.generate_emoteindex(emotelist)
            rendered = self.insert_emotesurfs(text, emoteindxs)
            return rendered
        else:
            return list(text)

    def generate_emoteindex(self, emotelist):
        emoteindxs = {}
        for emoteinfo in emotelist:
            emote_id, indexes = emoteinfo.split(":")
            index_rgx = r"(\d*)-(\d*)"
            results = re.findall(index_rgx, indexes)
            for indexes in results:
                emoteindxs[int(indexes[0])] = (int(indexes[1]), emote_id)
        return emoteindxs

    def insert_emotesurfs(self, text, emoteindxs):
        rendered = []
        i = 0
        while i < len(text):
            if i in emoteindxs:
                start_index = i
                end_index, emote_id = emoteindxs[start_index]
                emote = self.twitch_emotes.get(emote_id)
                if emote:
                    rendered.append(emote)
                else:
                    rendered.append(text[i : end_index + 1])
                i = end_index + 1
            else:
                rendered.append(text[i])
                i += 1
        return rendered

    def render_prepends(self, badges, channel, room_id):
        prepends = []
        if badges:
            for badge in badges.split(","):
                prepends.append(
                    self.twitch_badges.get(channel_id=room_id, badge_type=badge)
                )
        return prepends

    def render_new_twitchmessage(self, message):
        try:
            rendered_line = self.render_prepends(
                message["badges"], message["channel"], message["room-id"]
            )
        except Exception:
            self.logger.exception(f"Error rendering prepends for {message}")
            rendered_line = []
        ucolor = self.get_usercolor(message["username"], message["color"])
        rendered_line.extend(
            self.render_text(
                message["display-name"] or message["username"], ucolor, bold=True
            )
        )
        rendered_line.extend(self.render_text(" : ", self.txt_color))
        rendered_line.extend(self.render_emotes(message["message"], message["emotes"]))
        wrapped_lines = self.wraptext(rendered_line, self.size[WIDTH])
        new_lines = []
        for wrapped_line in wrapped_lines:
            new_lines.append(self.render_text(wrapped_line, self.txt_color))
        return new_lines

    def wraptext(self, text, maxwidth):
        lines = []
        cut_i = len(text) - 1
        while text:
            width = self.get_list_rendered_length(text[: cut_i + 1])
            if width > maxwidth:
                cut_i -= 1
            else:
                if text[: cut_i + 1]:
                    lines.append(text[: cut_i + 1])
                    text = text[cut_i + 1 :]
                else:
                    lines.append(text[: cut_i + 2])
                    text = text[cut_i + 2 :]
                if text:
                    cut_i = len(text) - 1
        return lines

    def get_list_rendered_length(self, target_list):
        width = 0
        for item in target_list:
            if isinstance(item, string_types):
                width += self.font_helper.get_text_width(item)
            else:
                width += item.get_width()
        return width

    def render_text(self, text, color, aa=True, bold=False):
        surfaces = []
        if isinstance(text, list):
            for item in text:
                surfaces.extend(self.render_text(item, color, aa))
        elif isinstance(text, string_types):
            current_font = self.font_helper.required_font("a", bold)
            i = 0
            while i < len(text):
                rq_font = self.font_helper.required_font(text[i], bold)
                if rq_font != current_font:
                    if text[:i]:
                        part = current_font[0].render(text[:i], aa, color)
                        surfaces.append(part)
                        text = text[i:]
                        i = 0
                    current_font = rq_font
                else:
                    i += 1
            try:
                part = current_font[0].render(text, aa, color)
                surfaces.append(part)
            except UnicodeError as e:
                if (
                    str(e)
                    == "A Unicode character above '\uFFFF' was found; not supported"
                ):
                    pass
        else:
            return [text]
        return surfaces
