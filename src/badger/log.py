import logging
from logging.config import dictConfig
from badger.utils import merge_params

logger = logging.getLogger(__name__)

'''
def set_log_level(level):
    loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
    for logger in loggers:
        logger.setLevel(level)
'''

def init_logger(logger_obj, log_filepath, level):
    """
    Init a named logger with handlers to log file and terminal.

    Args:
        logger_obj (logging.Logger): Logger to configure.
        log_filepath (str): Path to log file.
        level (str): Logging level.
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.DEBUG)

    logger_obj.setLevel(level)

    # prevent logging messages from being propagated to root
    # logger_obj.propagate = False

    # file handler
    file_handler = logging.FileHandler(log_filepath, mode='a')
    # console handler
    stream_handler = logging.StreamHandler()

    # formatting
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    logger_obj.addHandler(file_handler)
    logger_obj.addHandler(stream_handler)

def set_log_level(level, project_namespace="badger"):
    """
    Set logging level for all loggers in badger only.

    Args:
        level (str): logging level
        project_namespace (str): the root name of your project loggers
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.DEBUG)

    root_logger = logging.getLogger(project_namespace)
    root_logger.setLevel(level)

    # iterate all existing loggers, only update those in your namespace
    for name, logger_obj in logging.root.manager.loggerDict.items():
        if isinstance(logger_obj, logging.Logger) and name.startswith(project_namespace):
            logger.info(f"Setting logger {logger_obj.name} to level {logging.getLevelName(level)}")
            logger_obj.setLevel(level)

    # optionally also update handlers on root logger
    for handler in root_logger.handlers:
        handler.setLevel(level)