#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import logging
import logging.handlers
from typing import Any, List

import os
import sys
import asyncio

from pilot.configs.model_config import LOGDIR

server_error_msg = (
    "**NETWORK ERROR DUE TO HIGH TRAFFIC. PLEASE REGENERATE OR REFRESH THIS PAGE.**"
)

handler = None


def _get_logging_level() -> str:
    return os.getenv("DBGPT_LOG_LEVEL", "INFO")


def setup_logging_level(logging_level=None, logger_name: str = None):
    if not logging_level:
        logging_level = _get_logging_level()
    if type(logging_level) is str:
        logging_level = logging.getLevelName(logging_level.upper())
    if logger_name:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging_level)
    else:
        logging.basicConfig(level=logging_level, encoding="utf-8")


def setup_logging(logger_name: str, logging_level=None, logger_filename: str = None):
    if not logging_level:
        logging_level = _get_logging_level()
    logger = _build_logger(logger_name, logging_level, logger_filename)
    try:
        import coloredlogs

        color_level = logging_level if logging_level else "INFO"
        coloredlogs.install(level=color_level, logger=logger)
    except ImportError:
        pass


def get_gpu_memory(max_gpus=None):
    import torch

    gpu_memory = []
    num_gpus = (
        torch.cuda.device_count()
        if max_gpus is None
        else min(max_gpus, torch.cuda.device_count())
    )

    for gpu_id in range(num_gpus):
        with torch.cuda.device(gpu_id):
            device = torch.cuda.current_device()
            gpu_properties = torch.cuda.get_device_properties(device)
            total_memory = gpu_properties.total_memory / (1024**3)
            allocated_memory = torch.cuda.memory_allocated() / (1024**3)
            available_memory = total_memory - allocated_memory
            gpu_memory.append(available_memory)
    return gpu_memory


def _build_logger(logger_name, logging_level=None, logger_filename: str = None):
    global handler

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set the format of root handlers
    if not logging.getLogger().handlers:
        setup_logging_level(logging_level=logging_level)
    logging.getLogger().handlers[0].setFormatter(formatter)

    # Redirect stdout and stderr to loggers
    # stdout_logger = logging.getLogger("stdout")
    # stdout_logger.setLevel(logging.INFO)
    # sl_1 = StreamToLogger(stdout_logger, logging.INFO)
    # sys.stdout = sl_1
    #
    # stderr_logger = logging.getLogger("stderr")
    # stderr_logger.setLevel(logging.ERROR)
    # sl = StreamToLogger(stderr_logger, logging.ERROR)
    # sys.stderr = sl

    # Add a file handler for all loggers
    if handler is None and logger_filename:
        os.makedirs(LOGDIR, exist_ok=True)
        filename = os.path.join(LOGDIR, logger_filename)
        handler = logging.handlers.TimedRotatingFileHandler(
            filename, when="D", utc=True
        )
        handler.setFormatter(formatter)

        for name, item in logging.root.manager.loggerDict.items():
            if isinstance(item, logging.Logger):
                item.addHandler(handler)
    # Get logger
    logger = logging.getLogger(logger_name)
    setup_logging_level(logging_level=logging_level, logger_name=logger_name)

    return logger


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """

    def __init__(self, logger, log_level=logging.INFO):
        self.terminal = sys.stdout
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ""

    def __getattr__(self, attr):
        return getattr(self.terminal, attr)

    def write(self, buf):
        temp_linebuf = self.linebuf + buf
        self.linebuf = ""
        for line in temp_linebuf.splitlines(True):
            # From the io.TextIOWrapper docs:
            #   On output, if newline is None, any '\n' characters written
            #   are translated to the system default line separator.
            # By default sys.stdout.write() expects '\n' newlines and then
            # translates them so this is still cross platform.
            if line[-1] == "\n":
                encoded_message = line.encode("utf-8", "ignore").decode("utf-8")
                self.logger.log(self.log_level, encoded_message.rstrip())
            else:
                self.linebuf += line

    def flush(self):
        if self.linebuf != "":
            encoded_message = self.linebuf.encode("utf-8", "ignore").decode("utf-8")
            self.logger.log(self.log_level, encoded_message.rstrip())
        self.linebuf = ""


def disable_torch_init():
    """
    Disable the redundant torch default initialization to accelerate model creation.
    """
    import torch

    setattr(torch.nn.Linear, "reset_parameters", lambda self: None)
    setattr(torch.nn.LayerNorm, "reset_parameters", lambda self: None)


def pretty_print_semaphore(semaphore):
    if semaphore is None:
        return "None"
    return f"Semaphore(value={semaphore._value}, locked={semaphore.locked()})"


def get_or_create_event_loop() -> asyncio.BaseEventLoop:
    loop = None
    try:
        loop = asyncio.get_event_loop()
        assert loop is not None
        return loop
    except RuntimeError as e:
        if "no running event loop" not in str(
            e
        ) and "no current event loop" not in str(e):
            raise e
        logging.warning("Cant not get running event loop, create new event loop now")
    return asyncio.get_event_loop_policy().new_event_loop()


def logging_str_to_uvicorn_level(log_level_str):
    level_str_mapping = {
        "CRITICAL": "critical",
        "ERROR": "error",
        "WARNING": "warning",
        "INFO": "info",
        "DEBUG": "debug",
        "NOTSET": "info",
    }
    return level_str_mapping.get(log_level_str.upper(), "info")


class EndpointFilter(logging.Filter):
    """Disable access log on certain endpoint

    source: https://github.com/encode/starlette/issues/864#issuecomment-1254987630
    """

    def __init__(
        self,
        path: str,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._path = path

    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find(self._path) == -1


def setup_http_service_logging(exclude_paths: List[str] = None):
    """Setup http service logging

    Now just disable some logs

    Args:
        exclude_paths (List[str]): The paths to disable log
    """
    if not exclude_paths:
        # Not show heartbeat log
        exclude_paths = ["/api/controller/heartbeat"]
    if uvicorn_logger := logging.getLogger("uvicorn.access"):
        for path in exclude_paths:
            uvicorn_logger.addFilter(EndpointFilter(path=path))
    if httpx_logger := logging.getLogger("httpx"):
        httpx_logger.setLevel(logging.WARNING)
