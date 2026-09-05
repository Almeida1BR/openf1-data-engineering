import logging
from pathlib import Path


LOG_FORMAT = "{asctime} | {levelname} | {name} | {message}"


def configure_logging(log_path=None, level=logging.INFO):
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        LOG_FORMAT,
        style="{",
    )

    if not any(getattr(handler, "openf1_console", False) for handler in root_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.openf1_console = True
        root_logger.addHandler(console_handler)

    if log_path is not None:
        log_path = Path(log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        known_file = str(log_path.resolve())
        has_file = any(
            getattr(handler, "openf1_file", None) == known_file
            for handler in root_logger.handlers
        )

        if not has_file:
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            file_handler.openf1_file = known_file
            root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name):
    return logging.getLogger(name)
