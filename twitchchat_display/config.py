import logging
import sys

import click
import yaml

LOG_MAP = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}


def get_config(config_path):
    config = yaml.safe_load(config_path.read_bytes())
    required_settings = [
        "twitch_username",
        "twitch_oauth",
        "twitch_channels",
        "client_id",
    ]
    for setting in required_settings:
        if setting not in config:
            raise click.Abort(
                f"{setting} not present in config.txt, put it there! check config_example.txt!"
            )
    return config


def logging_config(verbosity):
    log_level = LOG_MAP[verbosity]
    return {
        "disable_existing_loggers": False,
        "raiseExceptions": True,
        "version": 1,
        "handlers": {
            "console": {
                "formatter": "colorlog",
                "stream": sys.stdout,
                "class": "logging.StreamHandler",
            }
        },
        "loggers": {
            "": {"level": log_level, "handlers": ["console"]},
            "twitchchat_display": {"propagate": True, "level": log_level},
        },
        "formatters": {
            "colorlog": {
                "()": "colorlog.ColoredFormatter",
                "datefmt": "%Y-%m-%d %H:%M:%S",
                "format": "[%(cyan)s%(asctime)s%(reset)s][%(blue)s%(name)s%(reset)s][%(log_color)s%(levelname)s%(reset)s] - %(message)s",
                "log_colors": {
                    "DEBUG": "purple",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red",
                },
            },
        },
    }
