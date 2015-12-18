#!/usr/bin/env python
import logging
import os
import signal
import sys
import time
from yaml import load
from twitchchat import twitch_chat
from display import TwitchChatDisplay
from twitcher import twitcher
from youtubechat import YoutubeLiveChat, get_live_chat_id_for_stream_now
import argparse
import pygame
logger = logging.getLogger('twitch_monitor')


def signal_term_handler(signal, frame):
    logger.critical("Sigterm recieved, exiting")
    sys.exit(0)


def remove_nonascii(text):
    return ''.join(i for i in text if ord(i) < 128)


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
    signal.signal(signal.SIGTERM, signal_term_handler)
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--test", help="Subscribe to featured channels to aid testing", action="store_true")
    parser.add_argument('-d',
                        '--debug',
                        help="Enable debugging statements",
                        action="store_const",
                        dest="loglevel",
                        const=logging.DEBUG,
                        default=logging.INFO,)
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel,
                        format='%(asctime)s.%(msecs)d %(levelname)s %(name)s : %(message)s',
                        datefmt='%H:%M:%S')
    config = get_config()
    if args.test:
        from twitch.api import v3 as twitch
        featured_streams = twitch.streams.featured(limit=5)['featured']
        for x in featured_streams:
            config['twitch_channels'].append(x['stream']['channel']['name'])
    try:
        console = TwitchChatDisplay(config['screen_width'], config['screen_height'])
        thandler = twitcher(config['twitch_channels'])
        thandler.subscribe_new_follow(console.new_followers)
        thandler.subscribe_viewers_change(console.new_viewers)
        tirc = twitch_chat(config['twitch_username'], config['twitch_oauth'], config['twitch_channels'])
        tirc.subscribeChatMessage(console.new_twitchmessage)
        tirc.subscribeNewSubscriber(console.new_subscriber)
        ytchat = None
        if 'youtube_enabled' in config:
            if config['youtube_enabled']:
                chatId = get_live_chat_id_for_stream_now('oauth_creds')
                ytchat = YoutubeLiveChat('oauth_creds', [chatId])
                ytchat.subscribe_chat_message(console.new_ytmessage)

        try:
            console.start()
            thandler.start()
            tirc.start()
            if ytchat:
                ytchat.start()
            while True:
                time.sleep(0.1)
                if pygame.display.get_init():
                    pygame.event.pump()
        finally:
            console.stop()
            thandler.stop()
            if ytchat:
                ytchat.stop()
    finally:
        pygame.quit()
