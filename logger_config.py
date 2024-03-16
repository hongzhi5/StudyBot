
import logging
from logging.handlers import RotatingFileHandler

import colorlog


def setup_logger(logger_name):
    # Create a logger with the specified name
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    # Create a file handler that logs debug and higher level messages to a file
    file_handler = RotatingFileHandler("discord_study_bot.log", maxBytes=10 ** 6, backupCount=5)

    # Create a stream handler that logs debug and higher level messages to the console
    stream_handler = colorlog.StreamHandler()

    # Create a formatter and add it to the handlers
    file_formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(file_formatter)

    colorlog.default_log_colors["custom_blue"] = "#268785"

    color_formatter = colorlog.ColoredFormatter(
        "%(time_log_color)s%(asctime)s%(reset)s %(levelname_log_color)s%(levelname)-8s%(reset)s %(name_log_color)s%("
        "name)s%(reset)s %(message_log_color)s%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        reset=True,
        secondary_log_colors={
            "levelname": {
                "DEBUG": "cyan",
                "INFO": "light_blue",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
            "time": {
                "DEBUG": "thin_black",
                "INFO": "thin_black",
                "WARNING": "thin_black",
                "ERROR": "thin_black",
                "CRITICAL": "thin_black",
            },
            "name": {"DEBUG": "bold_purple", "INFO": "bold_purple", "WARNING": "bold_purple", "ERROR": "bold_purple", "CRITICAL": "bold_purple"},
            "message": {"DEBUG": "white", "INFO": "white", "WARNING": "white", "ERROR": "white",
                        "CRITICAL": "red,bg_white"},
        },
        style="%",
    )
    stream_handler.setFormatter(color_formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger
