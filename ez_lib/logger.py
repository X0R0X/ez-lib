import logging
import os
import sys
from enum import Enum
from logging.handlers import RotatingFileHandler
from typing import TextIO


class BaseLogModule(Enum):
    pass


class LogConfig:
    def __init__(
            self,
            log_module_cls: type[BaseLogModule] | None = None,
            log_level: int = logging.INFO,
            log_std_stream: TextIO | None = sys.stdout,
            log_file_path: str | None = None,
            log_file_max_size: int = 1 * 1024 ** 2,
            log_file_backup_count: int = 10,
            log_format: str = (
                    '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
            ),
            log_level_libs: int = logging.ERROR,
            log_level_libs_override: dict[str, int] | None = None,
    ):
        """
        Logging Configuration.

        :param log_module_cls: Class inherited from BaseLogModule with
                               logging modules names declared as class
                               variables.
        :param log_level: Default Log Level.
        :param log_std_stream: Default stream to log to.
        :param log_file_path: Path to a log file or None.
        :param log_file_max_size Maximum size of a log file.
        :param log_file_backup_count: Maximum number of rotated log files.
        :param log_format: Log record prefix format.
        :param log_level_libs: Default log level for non-project based
                               libraries.
        :param log_level_libs_override: Dictionary[library_name, log_level] -
                                        Override default log level for
                                        non-project based libraries.
        """
        self.log_module_cls = log_module_cls
        self.log_level = log_level
        self.log_std_stream = log_std_stream
        self.log_file_path = log_file_path
        self.log_file_max_size = log_file_max_size
        self.log_file_backup_count = log_file_backup_count
        self.log_format = log_format
        self.log_level_libs = log_level_libs
        self.log_level_libs_override = log_level_libs_override


loggers = {}
log_handlers = []
log_config: LogConfig | None = LogConfig(BaseLogModule)


def init_logging(config: LogConfig, mute_libs=True):
    global log_config
    d = globals()
    log_config = config

    if config.log_file_path:
        try:
            os.makedirs(os.path.dirname(config.log_file_path))
        except PermissionError:
            print(
                f'Unable to init logging to file, insufficient '
                f'permissions for path "{config.log_file_path}"'
            )
            exit(1)
        except OSError:
            # directories already exist
            pass

    if mute_libs:
        set_lib_log_level()


def get_logger(module: BaseLogModule = None, log_level=None) -> logging.Logger:
    global log_config

    if log_level is None:
        log_level = log_config.log_level

    name = module.value if module else None

    if name in loggers.keys():
        log = loggers[name]
        log.setLevel(log_level)
        return loggers[name]
    else:
        log = logging.getLogger(name)
        loggers[name] = log
        lh = []

        if log_config.log_file_path:
            try:
                handler = RotatingFileHandler(
                    log_config.log_file_path,
                    'a',
                    log_config.log_file_max_size,
                    log_config.log_file_backup_count,
                    'utf-8'
                )

                lh.append(handler)
                log_handlers.append(handler)

            except PermissionError:
                print(
                    f'Unable to init logging to file, insufficient '
                    f'permissions for path "{log_config.log_file_path}"'
                )
                exit(1)
            except OSError as e:
                print(f'Unable to create RotatingFileHandler, error: {e}')

        # todo fix log to file ?
        if log_config.log_std_stream:
            handler = logging.StreamHandler(log_config.log_std_stream)
            lh.append(handler)
            log_handlers.append(handler)

        for handler in lh:
            handler.setLevel(log_level)
            handler.setFormatter(logging.Formatter(log_config.log_format))
            log.addHandler(handler)
            log.setLevel(log_level)

        log.debug(f'Logging initialized (name={name})')

        return log


def set_lib_log_level():
    # Set log level for libraries
    global log_config
    global loggers

    loggers_ = [
        logging.getLogger(name) for name in logging.root.manager.loggerDict
        if name not in [lm.value for lm in log_config.log_module_cls]
    ]

    for logger in loggers_:
        if logger not in loggers:
            if (
                    log_config.log_level_libs_override and
                    logger.name in log_config.log_level_libs_override.keys()
            ):
                logger.setLevel(log_config.log_level_libs_override[logger.name])
            else:
                logger.setLevel(log_config.log_level_libs)


def destroy():
    for handler in log_handlers:
        handler.close()
