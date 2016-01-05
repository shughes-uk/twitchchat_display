import os
import time
import logging
from threading import Timer, Thread, Lock
from fontTools.ttLib import TTFont
from fontTools.unicode import Unicode
from itertools import chain
import json
import random
import re
import webcolors
import ssl
import sys
import unicodedata
from PIL import Image
PY3 = sys.version_info[0] == 3

if PY3:
    string_types = str,
    from urllib.request import urlopen,urlretrieve
    import pygame.ftfont
    pygame.font = pygame.ftfont
else:
    string_types = basestring,
    from urllib import urlopen,urlretrieve
    import pygame.font

FONT_PATHS = ["FreeSans.ttf", "OpenSansEmoji.ttf","Cyberbit.ttf", "unifont.ttf" ]

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
        urlretrieve(url, 'profile_images/{0}.jpg'.format(channelId), context=context)

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

    def __init__(self, height):
        self.emotes = {}
        self.badges = {}
        self.logos = {}
        self.img_height = height

    def get_emote(self, id):
        if id not in self.emotes:
            self.load_emote(id)
        return self.emotes[id]

    def get_badge(self, channel, btype):
        if channel not in self.badges:
            self.load_badges(channel)
        return self.badges[channel][btype]

    def get_logo(self, channel):
        if channel not in self.logos:
            self.load_logo(channel)
        return self.logos[channel]

    def download_badges(self, channel):
        response = urlopen('https://api.twitch.tv/kraken/chat/{0}/badges'.format(channel)).read().decode("UTF-8")
        data = json.loads(response)
        for btype in BADGE_TYPES:
            if data[btype]:
                response = urlopen(data[btype]['image'])
                im = Image.open(response)
                im.save('badgecache/{0}_{1}.png'.format(channel, btype))


    def download_emote(self, id):
        response = None
        while not response:
            try:
                response = urlopen('http://static-cdn.jtvnw.net/emoticons/v1/{0}/3.0'.format(id))
                if response.getcode() != 200:
                    response = urlopen('http://static-cdn.jtvnw.net/emoticons/v1/{0}/2.0'.format(id))
                if response.getcode() != 200:
                    response = urlopen('http://static-cdn.jtvnw.net/emoticons/v1/{0}/1.0'.format(id))
            except IOError:
                logger.warn("Error downloading twitch emote, trying again")
        im = Image.open(response)
        im.save('emotecache/{0}.png'.format(id))

    def download_logo(self, channel):
        response = urlopen('https://api.twitch.tv/kraken/users/{0}'.format(channel)).read().decode("UTF-8")
        data = json.loads(response)
        response = urlopen(data['logo'])
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

    def load_badges(self, channel):
        if not os.path.isfile('badgecache/{0}_{1}.png'.format(channel, BADGE_TYPES[0])):
            if not os.path.isdir('badgecache'):
                os.mkdir('badgecache')
            self.download_badges(channel)
        self.badges[channel] = {}
        for btype in BADGE_TYPES:
            if os.path.isfile('badgecache/{0}_{1}.png'.format(channel, btype)):
                self.badges[channel][btype] = self.load_and_resize('badgecache/{0}_{1}.png'.format(channel, btype))

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

    def load_font(self, font_path):
        logger.info("Loading font {0}".format(font_path))
        pg_font = pygame.font.Font(font_path, self.font_size)
        fontinfo = self.get_font_details(font_path)
        if pg_font.get_linesize() > self.font_height:
            self.font_height = pg_font.get_linesize()
        self.fonts.append((pg_font, fontinfo, font_path))
        logger.info("Loaded {0}".format(font_path))

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

    def get_text_width(self, text):
        current_font = self.required_font("a")
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


class TwitchChatDisplay(object):

    def __init__(self, screen_width, screen_height):
        self.bg_color = [0x32, 0x32, 0x3E]
        self.txt_color = [0xFF, 0xFF, 0xFF]
        self.usercolors = {}

        self.size = (screen_width, screen_height)
        self.chatscreen = ChatScreen(screen_width, screen_height, self.bg_color)
        self.font_helper = FontHelper()
        for fontp in FONT_PATHS:
            self.chatscreen.blit_quicktext("Loading font {0}".format(fontp), self.txt_color)
            self.font_helper.load_font(fontp)
        self.chatscreen.set_line_height(self.font_helper.font_height)
        self.twitchimages = TwitchImages(self.font_helper.font_height)
        self.yt_logo = self.load_yt_icon(self.font_helper.font_height)
        self.youtube_profile_images = YTProfileImages(self.font_helper.font_height)
        self.chatscreen.add_chatlines([self.render_text("Loading complete. Waiting for twitch messages..",
                                                        self.txt_color)])

    def load_yt_icon(self, height):
        surface = pygame.image.load("yt_icon.png")
        ratio = height / float(surface.get_height())
        new_size = (int(surface.get_width() * ratio), height)
        resized = pygame.transform.scale(surface, new_size)
        if not pygame.display.get_init():
            return resized
        else:
            return resized.convert_alpha()

    def start(self):
        self.chatscreen.start()

    def stop(self):
        self.chatscreen.stop()

    def display_message(self, text, duration):
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
        if not PY3:
            result['message'] = strip_unsupported_chars(result['message'])
        new_lines = self.render_new_twitchmessage(result)
        self.chatscreen.add_chatlines(new_lines)

    def new_ytmessage(self, new_msg_objs, chat_id):
        for msgobj in new_msg_objs:
            if not PY3:
                msgobj.message_text = strip_unsupported_chars(msgobj.message_text)
            new_lines = self.render_new_ytmessage(msgobj)
            self.chatscreen.add_chatlines(new_lines)

    def new_subscriber(self, channel, subscriber, months):
        new_line = self.render_new_subscriber(channel, subscriber, months)
        self.chatscreen.add_chatlines([new_line])

    def new_followers(self, new_followers, name, total):
        new_lines = self.render_new_followers(new_followers, name)
        self.chatscreen.add_chatlines(new_lines)

    def new_viewers(self, viewercount, name):
        self.chatscreen.viewers[name] = viewercount

    def render_new_subscriber(self, channel, subscriber, months):
        sub_badge = self.twitchimages.get_badge(channel, "subscriber")
        if months == 0:
            text = " {0} subscribed to {1}! ".format(subscriber, channel, months)
        else:
            text = " {0} subscribed to {1} for {2} months in a row! ".format(subscriber, channel, months)
        rendered = self.render_text(text, self.txt_color)
        rendered.insert(0, sub_badge)
        rendered.append(sub_badge)
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

    def render_prepends(self, usertype, subscriber, channel):
        prepends = [self.twitchimages.get_logo(channel)]
        if usertype:
            prepends.append(self.twitchimages.get_badge(channel, usertype))
        if subscriber:
            prepends.append(self.twitchimages.get_badge(channel, 'subscriber'))
        return prepends

    def render_yt_profile(self, author):
        return self.youtube_profile_images.get_profile_image(author.profile_image_url, author.channel_id)

    def render_new_ytmessage(self, message):
        rendered_line = [self.yt_logo]
        ucolor = self.get_usercolor(message.author.display_name)
        rendered_line.append(self.render_yt_profile(message.author))
        rendered_line.extend(self.render_text(message.author.display_name, ucolor))
        rendered_line.extend(self.render_text(' : ', self.txt_color))
        rendered_line.extend(list(message.message_text))
        wrapped_lines = self.wraptext(rendered_line, self.size[WIDTH])
        new_lines = []
        for wrapped_line in wrapped_lines:
            new_lines.append(self.render_text(wrapped_line, self.txt_color))
        return new_lines

    def render_new_twitchmessage(self, message):
        rendered_line = self.render_prepends(message['user-type'], bool(int(message['subscriber'])), message['channel'])
        ucolor = self.get_usercolor(message['username'], message['color'])
        rendered_line.extend(self.render_text(message['display-name'] or message['username'], ucolor))
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
                if text[:cut_i+1]:
                    lines.append(text[:cut_i + 1])
                    text = text[cut_i + 1:]
                else:
                    lines.append(text[:cut_i+2])
                    text = text[cut_i+2:]
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

    def render_text(self, text, color, aa=True):
        surfaces = []
        if isinstance(text, list):
            for item in text:
                surfaces.extend(self.render_text(item, color, aa))
        elif isinstance(text, string_types):
            current_font = self.font_helper.required_font("a")
            i = 0
            while i < len(text):
                rq_font = self.font_helper.required_font(text[i])
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
