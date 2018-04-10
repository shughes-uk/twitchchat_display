#!/usr/bin/env python
# This Python file uses the following encoding: utf-8

import argparse
import logging
import os
import signal
import sys
import time

import pygame
from yaml import load

from display import TwitchChatDisplay
from twitchchat import twitch_chat
from twitchevents import twitchevents
from youtubechat import YoutubeLiveChat, get_live_chat_id_for_stream_now

logger = logging.getLogger('twitch_monitor')
PY3 = sys.version_info[0] == 3


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
            required_settings = ['twitch_username', 'twitch_oauth', 'twitch_channels', 'client_id']
            for setting in required_settings:
                if setting not in config:
                    msg = '{} not present in config.txt, put it there! check config_example.txt!'.format(setting)
                    logger.critical(msg)
                    sys.exit()
                if not PY3:
                    # don't allow unicode!
                    if isinstance(config[setting], unicode):
                        config[setting] = str(remove_nonascii(config[setting]))
        except SystemExit:
            sys.exit()
        except Exception as e:
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
    parser.add_argument(
        "-t", "--testtwitch", help="Subscribe to featured channels on twitch to aid testing", action="store_true")
    parser.add_argument(
        "-y", "--testyoutube", help="Subscribe to featured channels on youtube to aid testing", action="store_true")
    parser.add_argument(
        '-d',
        '--debug',
        help="Enable debugging statements",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.INFO,)
    args = parser.parse_args()

    logging.basicConfig(
        level=args.loglevel, format='%(asctime)s.%(msecs)d %(levelname)s %(name)s : %(message)s', datefmt='%H:%M:%S')
    config = get_config()
    if args.testtwitch or args.testyoutube:
        import shutil
        shutil.rmtree('logocache', ignore_errors=True)
        shutil.rmtree('badgecache', ignore_errors=True)
        shutil.rmtree('emotecache', ignore_errors=True)
        shutil.rmtree('profile_images', ignore_errors=True)

    if args.testtwitch:
        from twitch.api import v3 as twitch
        featured_streams = twitch.streams.featured(limit=15)['featured']
        for x in featured_streams:
            config['twitch_channels'].append(x['stream']['channel']['name'])

    try:
        console = TwitchChatDisplay(config['screen_width'], config['screen_height'], config['client_id'])
        console.display_message("Loading twitch_api manager")
        thandler = twitchevents(config['twitch_channels'])
        thandler.subscribe_new_follow(console.new_followers)
        thandler.subscribe_viewers_change(console.new_viewers)
        console.display_message("Loading twitch_message handler")
        tirc = twitch_chat(config['twitch_username'], config['twitch_oauth'], config['twitch_channels'],
                           config['client_id'])
        tirc.subscribeChatMessage(console.new_twitchmessage)
        tirc.subscribeUsernotice(console.new_usernotice)
        ytchat = None
        if 'youtube_enabled' in config:
            if config['youtube_enabled']:
                console.display_message("Grabbing youtube chat id")
                chatId = None
                if args.testyoutube:
                    from youtubechat import get_top_stream_chat_ids
                    chatId = get_top_stream_chat_ids("oauth_creds")[0]
                else:
                    chatId = get_live_chat_id_for_stream_now('oauth_creds')
                console.display_message("Loading youtube chat handler")
                ytchat = YoutubeLiveChat('oauth_creds', [chatId])
                ytchat.subscribe_chat_message(console.new_ytmessage)
        if 'ignored_users' in config:
            for user in config['ignored_users']:
                console.ignore_user(user)
        try:
            console.display_message("Loading complete, awaiting messages")
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
