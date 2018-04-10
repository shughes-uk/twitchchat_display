import json
import logging
import os
import random
import re
import ssl
import sys
import time
import unicodedata
from threading import Lock, Thread, Timer
from pprint import pprint
import webcolors
from fontTools.ttLib import TTFont
from PIL import Image
from functools import lru_cache

logging.getLogger("PIL").setLevel(logging.WARNING)

PY3 = sys.version_info[0] == 3

if PY3:
    string_types = str,
    from urllib.request import urlopen, Request
    import pygame.ftfont
    pygame.font = pygame.ftfont
else:
    string_types = basestring,
    #from urllib import urlopen
    from urllib2 import urlopen, Request
    import pygame.font

FONT_PATHS = ["FreeSans.ttf", "OpenSansEmoji.ttf", "Cyberbit.ttf", "unifont.ttf"]
BOLD_FONT_PATHS = ['FreeSansBold.ttf']
BADGE_TYPES = ['global_mod', 'admin', 'broadcaster', 'mod', 'staff', 'turbo', 'subscriber']
logger = logging.getLogger("display")
WIDTH = 0
HEIGHT = 1

TWITCH_COLORS = ['Blue', 'Coral', 'DodgerBlue', 'SpringGreen', 'YellowGreen', 'Green', 'OrangeRed', 'Red', 'GoldenRod',
                 'HotPink', 'CadetBlue', 'SeaGreen', 'Chocolate', 'BlueViolet', 'Firebrick']


def strip_unsupported_chars(msg):
    return unicodedata.normalize('NFKD', msg).encode('ascii', 'ignore').decode()


def turn_screen_off():
    os.system('/opt/vc/bin/tvservice -o')


def turn_screen_on():
    os.system('/opt/vc/bin/tvservice -p ;fbset -depth 8; fbset -depth 16;')


class ChatScreen(object):

    def __init__(self, screen_width, screen_height, bg_color):
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
            self.lines = self.lines[-(self.max_lines):len(self.lines)]
        self.new_activity()

    def blit_quicktext(self, text, color=(255, 255, 255)):
        self.new_activity()
        font = pygame.font.Font("FreeSans.ttf", 72)
        surf = font.render(text, True, color)
        self.txt_layer.fill(self.bg_color)
        self.txt_layer.blit(surf, (self.rect.width / 2 - surf.get_rect().width / 2,
                                   self.rect.height / 2 - surf.get_rect().height / 2, 0, 0))
        self.screen.blit(self.txt_layer, self.rect)
        pygame.display.update()

    def blit_lines(self, lines, surface):
        y_pos = self.size[HEIGHT] - (self.line_height * (len(lines) + 1))
        viewerstring = ''
        for name in self.viewers:
            if self.viewers[name] > 0:
                viewerstring = viewerstring + ' {0} : {1}'.format(name, self.viewers[name])
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


class YTProfileImages(object):

    def __init__(self, height):
        self.profile_images = {}
        self.img_height = height

    def get_profile_image(self, url, channelId):
        if channelId not in self.profile_images:
            self.load_profile_image(url, channelId)
        return self.profile_images[channelId]

    def load_profile_image(self, url, channelId):
        if not os.path.isfile('profile_images/{0}.jpg'.format(channelId)):
            if not os.path.isdir('profile_images'):
                os.mkdir('profile_images')
            self.download_profile_image(url, channelId)
        self.profile_images[channelId] = {}
        self.profile_images[channelId] = self.load_and_resize('profile_images/{0}.jpg'.format(channelId))

    def download_profile_image(self, url, channelId):
        context = ssl._create_unverified_context()
        response = urlopen(url, context=context)
        im = Image.open(response)
        im.convert('RGB').save('profile_images/{0}.jpg'.format(channelId))

    def load_and_resize(self, filename):
        surface = pygame.image.load(filename)
        ratio = self.img_height / float(surface.get_height())
        new_size = (int(surface.get_width() * ratio), self.img_height)
        resized = pygame.transform.scale(surface, new_size)
        if not pygame.display.get_init():
            return resized
        else:
            return resized.convert_alpha()


class TwitchImages(object):

    def __init__(self, height, client_id):
        self.emotes = {}
        self.badges = {}
        self.logos = {}
        self.img_height = height
        self.client_id = client_id
        # self.channel_sub_json = Request('https://badges.twitch.tv/v1/badges/channels/{channel_id}/display?language=en').read().decode("UTF-8")
        # self.global_badge_json = Request('https://badges.twitch.tv/v1/badges/global/display?language=en').read().decode(
        #     "UTF-8")
        # self.channel_sub_json = json.loads(self.channel_sub_json)
        # self.global_badge_json = json.loads(self.channel_sub_json)
        self.chan_id_map = {}

    def _request(self, url):
        req = Request(url)
        req.add_header('Client-ID', self.client_id)
        return urlopen(req).read().decode('utf-8')

    def _request_noread(self, url):
        req = Request(url)
        req.add_header('Client-ID', self.client_id)
        return urlopen(req)

    def get_emote(self, id):
        if id not in self.emotes:
            self.load_emote(id)
        return self.emotes[id]

    def get_badge(self, bcode, channel_id):
        bcode_key, bcode_version = bcode.split('/')
        badge = self.load_badge(bcode_key, bcode_version, channel_id)
        return badge

    def get_logo(self, channel):
        if channel not in self.logos:
            self.load_logo(channel)
        return self.logos[channel]

    @lru_cache(maxsize=1)
    def download_global_badgelist(self):
        url = 'https://badges.twitch.tv/v1/badges/global/display?language=en'
        blob = json.loads(self._request(url))
        return blob

    def get_badge_image(self, bcode, bcode_v, channel_id):
        if bcode == 'subscriber':
            url = 'https://badges.twitch.tv/v1/badges/channels/{channel_id}/display?language=en'
            badge_sets = json.loads(self._request(url.format(channel_id=channel_id)))['badge_sets']
            try:
                badge_url = badge_sets[bcode]['versions'][bcode_v]['image_url_4x']
            except KeyError as e:
                badge_sets = self.download_global_badgelist()['badge_sets']
                badge_url = badge_sets[bcode]['versions'][bcode_v]['image_url_4x']
        else:
            badge_sets = self.download_global_badgelist()['badge_sets']
            badge_url = badge_sets[bcode]['versions'][bcode_v]['image_url_4x']
        response = self._request_noread(badge_url)
        im = Image.open(response)
        return im

    def download_emote(self, id):

        def try_open(target_url):
            try:
                return self._request_noread(target_url)
            except IOError:
                return None

        response = try_open('http://static-cdn.jtvnw.net/emoticons/v1/{0}/3.0'.format(id))
        if not response or response.getcode() != 200:
            response = try_open('http://static-cdn.jtvnw.net/emoticons/v1/{0}/2.0'.format(id))
        if not response or response.getcode() != 200:
            response = try_open('http://static-cdn.jtvnw.net/emoticons/v1/{0}/1.0'.format(id))
        if not response:
            raise Exception("Error trying to download twitch emote, id {0}".format(id))
        im = Image.open(response)
        im.save('emotecache/{0}.png'.format(id))

    def download_logo(self, channel):
        response = self._request('https://api.twitch.tv/kraken/users/{0}'.format(channel))
        data = json.loads(response)
        response = self._request_noread(data['logo'])
        im = Image.open(response)
        im.save('logocache/{0}.png'.format(channel))

    def load_and_resize(self, filename):
        surface = pygame.image.load(filename)
        ratio = self.img_height / float(surface.get_height())
        new_size = (int(surface.get_width() * ratio), self.img_height)
        resized = pygame.transform.scale(surface, new_size)
        if not pygame.display.get_init():
            return resized
        else:
            return resized.convert_alpha()

    @lru_cache(maxsize=1000)
    def load_badge(self, bcode, bcode_v, channel):
        if bcode == 'subscriber':
            badge_path = 'badgecache/{0}/{1}_{2}.png'.format(channel, bcode, bcode_v)
        else:
            badge_path = 'badgecache/{0}_{1}.png'.format(bcode, bcode_v)
        if not os.path.isfile(badge_path):
            os.makedirs(os.path.dirname(badge_path), exist_ok=True)
            b_img = self.get_badge_image(bcode, bcode_v, channel)
            b_img.save(badge_path)
        return self.load_and_resize(badge_path)

    def load_logo(self, channel):
        if not os.path.isfile('logocache/{0}.png'.format(channel)):
            if not os.path.isdir('logocache'):
                os.mkdir('logocache')
            self.download_logo(channel)
        self.logos[channel] = {}
        self.logos[channel] = self.load_and_resize('logocache/{0}.png'.format(channel))

    def load_emote(self, id):
        if not os.path.isfile('emotecache/{0}.png'.format(id)):
            if not os.path.isdir('emotecache'):
                os.mkdir('emotecache')
            self.download_emote(id)
        self.emotes[id] = self.load_and_resize('emotecache/{0}.png'.format(id))


class FontHelper(object):

    def __init__(self):
        logger.info("Fonthelper init")
        self.font_size = 48
        self.font_height = 0
        self.fonts = []
        self.bold_fonts = []

    def load_font(self, font_path, bold=False):
        logger.info("Loading font {0}".format(font_path))
        pg_font = pygame.font.Font(font_path, self.font_size)
        fontinfo = self.get_font_details(font_path)
        if pg_font.get_linesize() > self.font_height:
            self.font_height = pg_font.get_linesize()
        if bold:
            self.bold_fonts.append((pg_font, fontinfo, font_path))
        else:
            self.fonts.append((pg_font, fontinfo, font_path))
        logger.info("Loaded {0}".format(font_path))

    def get_font_details(self, font_path):
        ttf = TTFont(font_path, 0, verbose=0, allowVID=0, ignoreDecompileErrors=True, fontNumber=-1)
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
            logger.critical("Couldn't find font for character {0}".format(repr(char)))
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
            self.chatscreen.blit_quicktext("Loading font {0}".format(fontp), self.txt_color)
            self.font_helper.load_font(fontp)
        for fontp in BOLD_FONT_PATHS:
            self.chatscreen.blit_quicktext("Loading font {0}".format(fontp), self.txt_color)
            self.font_helper.load_font(fontp, bold=True)

        self.chatscreen.set_line_height(self.font_helper.font_height)
        self.twitchimages = TwitchImages(self.font_helper.font_height, client_id)
        self.yt_logo = self.load_yt_icon(self.font_helper.font_height)
        self.youtube_profile_images = YTProfileImages(self.font_helper.font_height)

    def load_yt_icon(self, height):
        surface = pygame.image.load("yt_icon.png")
        ratio = height / float(surface.get_height())
        new_size = (int(surface.get_width() * ratio), height)
        resized = pygame.transform.scale(surface, new_size)
        if not pygame.display.get_init():
            return resized
        else:
            return resized.convert_alpha()

    def ignore_user(self, username):
        self.ignore_list.append(username)

    def start(self):
        self.chatscreen.start()
        msg = [self.render_text("Loading complete. Waiting for messages..", self.txt_color)]
        self.chatscreen.add_chatlines(msg)

    def stop(self):
        self.chatscreen.stop()

    def display_message(self, text):
        self.chatscreen.blit_quicktext(text, self.txt_color)

    def get_usercolor(self, username, usercolor=None):
        if usercolor:
            usercolor = usercolor[1:]  # cut off the # from the start of the string
            hexcolor = (int(usercolor[:2], 16), int(usercolor[2:4], 16), int(usercolor[4:], 16))
            return hexcolor
        elif username not in self.usercolors:
            self.usercolors[username] = webcolors.name_to_rgb(random.choice(TWITCH_COLORS))
        return self.usercolors[username]

    def new_twitchmessage(self, result):
        if result['username'] not in self.ignore_list:
            if not PY3:
                result['message'] = strip_unsupported_chars(result['message'])
            new_lines = self.render_new_twitchmessage(result)
            self.chatscreen.add_chatlines(new_lines)

    def new_ytmessage(self, new_msg_objs, chat_id):
        for msgobj in new_msg_objs:
            if msgobj.author.display_name not in self.ignore_list:
                if not PY3:
                    msgobj.message_text = strip_unsupported_chars(msgobj.message_text)
                new_lines = self.render_new_ytmessage(msgobj)
                self.chatscreen.add_chatlines(new_lines)

    def new_usernotice(self, args):
        message = args['system-msg'].replace('\\s', ' ')
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
            text = " {0} subscribed to {1} for {2} months in a row! ".format(subscriber, channel, months)
        rendered = self.render_text(text, self.txt_color)
        return rendered

    def render_emotes(self, text, emotes):
        if emotes:
            emotelist = emotes.split('/')
            emoteindxs = self.generate_emoteindex(emotelist)
            rendered = self.insert_emotesurfs(text, emoteindxs)
            return rendered
        else:
            return list(text)

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
                rendered.append(self.twitchimages.get_emote(id))
                i = end_index + 1
            else:
                rendered.append(text[i])
                i += 1
        return rendered

    def render_prepends(self, badges, channel, room_id):
        prepends = [self.twitchimages.get_logo(channel)]
        if badges:
            for badge in badges.split(','):
                prepends.append(self.twitchimages.get_badge(badge, room_id))
        return prepends

    def render_yt_profile(self, author):
        return self.youtube_profile_images.get_profile_image(author.profile_image_url, author.channel_id)

    def render_new_ytmessage(self, message):
        rendered_line = [self.yt_logo]
        ucolor = self.get_usercolor(message.author.display_name)
        rendered_line.append(self.render_yt_profile(message.author))
        rendered_line.extend(self.render_text(message.author.display_name, ucolor, bold=True))
        rendered_line.extend(self.render_text(' : ', self.txt_color))
        rendered_line.extend(list(message.message_text))
        wrapped_lines = self.wraptext(rendered_line, self.size[WIDTH])
        new_lines = []
        for wrapped_line in wrapped_lines:
            new_lines.append(self.render_text(wrapped_line, self.txt_color))
        return new_lines

    def render_new_twitchmessage(self, message):
        rendered_line = self.render_prepends(message['badges'], message['channel'], message['room-id'])
        ucolor = self.get_usercolor(message['username'], message['color'])
        rendered_line.extend(self.render_text(message['display-name'] or message['username'], ucolor, bold=True))
        rendered_line.extend(self.render_text(' : ', self.txt_color))
        rendered_line.extend(self.render_emotes(message['message'], message['emotes']))
        wrapped_lines = self.wraptext(rendered_line, self.size[WIDTH])
        new_lines = []
        for wrapped_line in wrapped_lines:
            new_lines.append(self.render_text(wrapped_line, self.txt_color))
        return new_lines

    def wraptext(self, text, maxwidth):
        lines = []
        cut_i = len(text) - 1
        while text:
            width = self.get_list_rendered_length(text[:cut_i + 1])
            if width > maxwidth:
                cut_i -= 1
            else:
                if text[:cut_i + 1]:
                    lines.append(text[:cut_i + 1])
                    text = text[cut_i + 1:]
                else:
                    lines.append(text[:cut_i + 2])
                    text = text[cut_i + 2:]
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

    def render_new_followers(self, new_followers, name):
        lines = []
        for follower_name in new_followers:
            text = "{0} followed {1}!".format(follower_name, name)
            logger.info(text)
            rendered = self.render_text(text, self.txt_color)
            lines.append(rendered)
        return lines

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
                if str(e) == "A Unicode character above '\uFFFF' was found; not supported":
                    pass
        else:
            return [text]
        return surfaces
