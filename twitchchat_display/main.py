#!/usr/bin/env python
# This Python file uses the following encoding: utf-8

import logging.config
import signal
import sys
import time
from pathlib import Path

import click
import pygame
from twitchchat import twitch_chat

from .config import get_config, logging_config
from .display import TwitchChatDisplay

logger = logging.getLogger("twitch_monitor")


def signal_term_handler(signal, frame):
    logger.critical("Sigterm recieved, exiting")
    sys.exit(0)


@click.command()
@click.option("-v", "--verbosity", count=True)
@click.option(
    "-c",
    "--config",
    "config_fp",
    default="config.yaml",
    type=click.Path(exists=True, dir_okay=False, readable=True, writable=True),
)
def main(verbosity, config_fp):
    logging.config.dictConfig(logging_config(verbosity))
    config_fp = Path(config_fp)
    logger.info(f"Loading {config_fp}")
    config = get_config(config_fp)
    signal.signal(signal.SIGTERM, signal_term_handler)
    try:
        logger.info("Loading TwitchChatDisplay")
        console = TwitchChatDisplay(
            config["screen_width"], config["screen_height"], config["client_id"]
        )
        console.display_message("Loading twitch_api manager")
        console.display_message("Loading twitch_message handler")
        tirc = twitch_chat(
            config["twitch_username"],
            config["twitch_oauth"],
            config["twitch_channels"],
            config["client_id"],
        )
        tirc.subscribeChatMessage(console.new_twitchmessage)
        if "ignored_users" in config:
            for user in config["ignored_users"]:
                console.ignore_user(user)
        try:
            logger.info("Loaded TwitchChatDisplay")
            console.display_message("Loading complete, awaiting messages")
            console.start()
            tirc.start()
            while True:
                time.sleep(0.1)
                if pygame.display.get_init():
                    pygame.event.pump()
        finally:
            console.stop()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
