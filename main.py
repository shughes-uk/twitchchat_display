
import logging
import os
import re
import signal
import socket
import sys
import time
import traceback
# from pygame.locals import *
from threading import Timer, Thread

import pygame
from yaml import load

logger = logging.getLogger('twitch_monitor')


def signal_term_handler(signal, frame):
    print 'got SIGTERM'
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_term_handler)


def remove_nonascii(text):
    return ''.join(i for i in text if ord(i) < 128)


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


def turn_screen_off():
    os.system('/opt/vc/bin/tvservice -o')


def turn_screen_on():
    os.system('/opt/vc/bin/tvservice -p ;fbset -depth 8; fbset -depth 16;')


class TMI:
    def __init__(self, user, oauth, channels):
        logger.info('tmi starting up')
        self.user = user
        self.oauth = oauth
        self.ircSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ircServ = 'irc.twitch.tv'
        self.ircChans = channels
        self.subscribers = []
        self.connected = False

    def connect(self, port):
        logger.info('Connecting to twitch irc')
        self.ircSock.connect((self.ircServ, port))
        logger.info('Connected..authenticating as %s' % self.user)
        self.ircSock.send(str('Pass ' + self.oauth + '\r\n').encode('UTF-8'))
        self.ircSock.send(str('NICK ' + self.user + '\r\n').lower().encode('UTF-8'))
        self.ircSock.send(str('CAP REQ :twitch.tv/tags\r\n').encode('UTF-8'))
        logger.info('Joining channels %s' % self.ircChans)
        for chan in self.ircChans:
            self.ircSock.send(str('JOIN ' + chan + '\r\n').encode('UTF-8'))

    def subscribeMessage(self, callback):
        self.subscribers.append(callback)

    def handleIRCMessage(self, ircMessage):
        logger.debug(ircMessage)
        regex = r'@color=(?:|#([^;]*));'
        regex += r'display-name=([^;]*);'
        regex += r'emotes=([^;]*);'
        regex += r'subscriber=([^;]*);'
        regex += r'turbo=([^;]*);'
        regex += r'user-type=([^ ]*)'
        regex += r' :([^!]*)![^!]*@[^.]*.tmi.twitch.tv'  # username
        regex += r' PRIVMSG #([^ ]*)'  # channel
        regex += r' :(.*)'  # message
        match = re.search(regex, ircMessage)
        if match:
            result = {
            'color' : match.group(1),
            'displayname' : match.group(2),
            'emotes' : match.group(3),
            'subscribed' : bool(int(match.group(4))),
            'turbo' : bool(int(match.group(5))),
            'usertype' : match.group(6),
            'username' : match.group(7),
            'channel' : match.group(8),
            'message' : match.group(9)
            }
            for subscriber in self.subscribers:
                subscriber(result)
        if re.search(r':tmi.twitch.tv NOTICE \* :Error logging i.*', ircMessage):
            logger.critical('Error logging in to twitch irc, check oauth and username are set in config.txt!')
            sys.exit()
        elif ircMessage.find('PING ') != -1:
            logger.info('Responding to a ping from twitch... pong!')
            self.ircSock.send(str('PING :pong\n').encode('UTF-8'))

    def run(self):
        line_sep_exp = re.compile(b'\r?\n')
        socketBuffer = b''
        while True:
            try:
                self.connected = True
                # get messages
                socketBuffer += self.ircSock.recv(1024)
                ircMsgs = line_sep_exp.split(socketBuffer)
                socketBuffer = ircMsgs.pop()
                # Deal with them
                for ircMsg in ircMsgs:
                    msg = ircMsg.decode('utf-8')
                    self.handleIRCMessage(msg)
            except:
                raise

WIDTH = 0
HEIGHT = 1


class Console:
    def __init__(self, screen_width, screen_height):
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

    def make_prependstr(self,usertype,subscriber,channel):
        prepends = ''
        if usertype == 'mod':
            prepends = '@' + prepends
        elif usertype:
            prepends = '^' + usertype + '^_' + prepends
        if subscriber:
            prepends = '$' + prepends
        prepends = '[' + channel[:3] + ']' + prepends
        return prepends

    def prepare_surfaces(self,prepends,username,usercolor,text):
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
        y_pos = self.size[HEIGHT]-(self.font_height*(len(lines)))
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
        new_lines = self.prepare_surfaces(prepends, message['displayname'] or message['username'], message['color'], message['message'])
        self.lines.extend(new_lines)
        self.lines = self.lines[-(self.max_lines):len(self.lines)]
        self.enable_display()
        self.changed = True
        self.idle_timer = Timer(60 * 10, self.disable_display)
        self.idle_timer.start()
        return

    def start(self):
        self.idle_timer = Timer(60 * 10, self.disable_display)
        self.idle_timer.start()
        self.start_rendering()

    def stop(self):
        if self.idle_timer.is_alive():
            self.idle_timer.cancel()
        if self.rendering:
            self.rendering = False
            if self.render_thread.is_alive():
                self.render_thread.join()

    def start_rendering(self):
        self.rendering = True
        self.render_thread = Thread(target = self.render_loop)
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

def get_config():
    logger.info('Loading configuration from config.txt')
    config = None
    if os.path.isfile('config.txt'):
        try:
            config = load(open('config.txt', 'r'))
            required_settings = ['twitch_username', 'twitch_oauth', 'twitch_channels']
            for setting in required_settings:
                if setting not in config:
                    msg = '{} not present in config.txt, put it there! check config_example.txt!'.format(setting)
                    logger.critical(msg)
                    sys.exit()
                # don't allow unicode!
                if isinstance(config[setting], unicode):
                    config[setting] = str(remove_nonascii(config[setting]))
        except SystemExit:
            sys.exit()
        except Exception, e:
            logger.info(e)
            logger.critical('Problem loading configuration file, try deleting config.txt and starting again')
    else:
        logger.critical('config.txt doesn\'t exist, please create it, refer to config_example.txt for reference')
        sys.exit()
    logger.info('Configuration loaded')
    return config

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s.%(msecs)d %(levelname)s %(name)s : %(message)s',
                        datefmt='%H:%M:%S')
    pygame.init()
    turn_screen_on()
    config = get_config()
    console = Console(1920, 1080)
    console.start()
    try:
        while True:
            alerter = TMI(config['twitch_username'], config['twitch_oauth'], config['twitch_channels'])
            try:
                alerter.subscribeMessage(console.new_twitchmessage)
                alerter.connect(6667)
                alerter.run()
            except SystemExit:
                sys.exit()
            except Exception as e:
                print e
                logger.info(traceback.format_exc())

            # If we get here, try to shutdown the bot then restart in 5 seconds
            time.sleep(5)
    finally:
        console.stop()
        turn_screen_on()
        pygame.quit()
        console.idle_timer.cancel()
        sys.exit()
