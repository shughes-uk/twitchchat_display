import logging
import os
import signal
import sys
import traceback
from yaml import load
from twitch import twitchirc_handler
from display import console
from time import sleep
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
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s.%(msecs)d %(levelname)s %(name)s : %(message)s',
                        datefmt='%H:%M:%S')
    config = get_config()
    console = console(1920, 1080)
    tirc = twitchirc_handler(config['twitch_username'], config['twitch_oauth'], config['twitch_channels'])
    tirc.subscribeMessage(console.new_twitchmessage)
    try:
        console.start()
        tirc.connect(6667)
        tirc.start()
        while True:
            sleep(0.1)
    finally:
        console.stop()
        tirc.stop()
