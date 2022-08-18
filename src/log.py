import logging
from multiprocessing import current_process
from os import getenv

# Settings for the primary logger
USE_LOG_COLORS  = True   # Whether to use colored output in the terminal
LOG_TO_FILE     = True   # Whether to log into a file
LOG_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE        = r"siren_cog.log"
LOG_FORMAT      = "{asctime} | {levelname:^8} | {processName} | \
({filename}:{lineno}) >> {message}"

# Set the logging level based on environment. INFO by default
match getenv("SIREN_LOG_LEVEL", None).lower():
    case "debug":
        LOG_LEVEL = logging.DEBUG
    case "warning":
        LOG_LEVEL = logging.WARNING
    case "error":
        LOG_LEVEL = logging.ERROR
    case "critical":
        LOG_LEVEL = logging.CRITICAL
    case other:
        LOG_LEVEL = logging.INFO

# A log formatter capable of outputting colors
class ColoredFormatter(logging.Formatter):
    grey     = "\x1b[38;21m"
    yellow   = "\x1b[33;21m"
    blueish  = "\x1b[33;36m"
    red      = "\x1b[31;21m"
    bold_red = "\x1b[31;1m"
    reset    = "\x1b[0m"

    FORMATS = {
        logging.DEBUG:    grey     + LOG_FORMAT + reset,
        logging.INFO:     blueish  + LOG_FORMAT + reset,
        logging.WARNING:  yellow   + LOG_FORMAT + reset,
        logging.ERROR:    red      + LOG_FORMAT + reset,
        logging.CRITICAL: bold_red + LOG_FORMAT + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(
            log_fmt,
            style="{",
            datefmt=LOG_TIME_FORMAT
        )
        return formatter.format(record)


# Create the logger
globalLog = logging.getLogger(__name__)
globalLog.setLevel(LOG_LEVEL)

# Create a console handler and add it to the logger
consoleHandler = logging.StreamHandler()
consoleHandler.setLevel(LOG_LEVEL)
if USE_LOG_COLORS:
    consoleHandler.setFormatter(ColoredFormatter())
else:
    consoleHandler.setFormatter(
        logging.Formatter(LOG_FORMAT, datefmt=LOG_TIME_FORMAT, style='{')
    )
globalLog.addHandler(consoleHandler)

# Create a file handler and add it to the logger
if LOG_TO_FILE:
    fileHandler = logging.FileHandler(LOG_FILE)
    fileHandler.setFormatter(
        logging.Formatter(LOG_FORMAT, datefmt=LOG_TIME_FORMAT, style='{')
    )
    globalLog.addHandler(fileHandler)
