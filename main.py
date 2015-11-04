#!/usr/bin/env python
import logging
import os
import signal
import sys
from yaml import load
from twitchchat import twitch_chat
from display import TwitchChatDisplay
from twitch_handler import TwitchHandler
import argparse
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

    console = TwitchChatDisplay(1920, 1080)
    thandler = TwitchHandler(config['twitch_channels'])
    thandler.subscribe_new_follow(console.new_followers)
    tirc = twitch_chat(config['twitch_username'], config['twitch_oauth'], config['twitch_channels'])
    tirc.subscribeChatMessage(console.new_twitchmessage)
    tirc.subscribeNewSubscriber(console.new_subscriber)
    try:
        console.start()
        thandler.start()
        tirc.run()
    finally:
        console.stop()
        thandler.stop()
