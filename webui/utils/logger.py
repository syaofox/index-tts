#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IndexTTS WebUI Logger
提供日志记录功能的模块
"""

import os
import logging
import logging.handlers
from datetime import datetime


class Logger:
    """
    日志管理类，提供统一的日志记录接口
    支持多个日志级别和输出目标（控制台和文件）
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance

    def __init__(self, log_level=logging.INFO, log_to_file=False, log_to_console=True):
        """
        初始化日志管理器

        参数:
            log_level: 日志级别，默认为INFO
            log_to_file: 是否将日志输出到文件，默认为True
            log_to_console: 是否将日志输出到控制台，默认为True
        """
        # 避免重复初始化
        if self._initialized:
            return
        self._initialized = True

        # 创建日志目录
        self.log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
        )
        os.makedirs(self.log_dir, exist_ok=True)

        # 配置根日志记录器
        self.logger = logging.getLogger("index_tts")
        self.logger.setLevel(log_level)
        self.logger.propagate = False

        # 设置日志格式
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(module)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        
        # 为INFO级别创建特殊的格式化器
        info_formatter = logging.Formatter("%(message)s")

        # 添加控制台处理器
        if log_to_console and not any(
            isinstance(h, logging.StreamHandler) for h in self.logger.handlers
        ):
            # 为INFO级别创建单独的控制台处理器
            info_console_handler = logging.StreamHandler()
            info_console_handler.setFormatter(info_formatter)
            info_console_handler.setLevel(logging.INFO)
            info_console_handler.addFilter(lambda record: record.levelno == logging.INFO)
            self.logger.addHandler(info_console_handler)
            
            # 为其他级别创建控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            console_handler.setLevel(log_level)
            console_handler.addFilter(lambda record: record.levelno != logging.INFO)
            self.logger.addHandler(console_handler)

        # 添加文件处理器
        if log_to_file and not any(
            isinstance(h, logging.FileHandler) for h in self.logger.handlers
        ):
            current_time = datetime.now().strftime("%Y%m%d")
            log_file = os.path.join(self.log_dir, f"index_tts_{current_time}.log")

            # 为INFO级别创建单独的文件处理器
            info_file_handler = logging.handlers.TimedRotatingFileHandler(
                log_file, when="midnight", backupCount=30, encoding="utf-8"
            )
            info_file_handler.setFormatter(info_formatter)
            info_file_handler.setLevel(logging.INFO)
            info_file_handler.addFilter(lambda record: record.levelno == logging.INFO)
            self.logger.addHandler(info_file_handler)
            
            # 为其他级别创建文件处理器
            file_handler = logging.handlers.TimedRotatingFileHandler(
                log_file, when="midnight", backupCount=30, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(log_level)
            file_handler.addFilter(lambda record: record.levelno != logging.INFO)
            self.logger.addHandler(file_handler)

    def get_logger(self):
        """获取日志记录器实例"""
        return self.logger


# 创建默认日志记录器实例
_default_logger = Logger().get_logger()


# 提供便捷的日志记录函数
def debug(msg, *args, **kwargs):
    """记录调试级别的日志"""
    _default_logger.debug(msg, *args, stacklevel=2, **kwargs)


def info(msg, *args, **kwargs):
    """记录信息级别的日志"""
    _default_logger.info(f"* {msg}", *args, stacklevel=2, **kwargs)


def warning(msg, *args, **kwargs):
    """记录警告级别的日志"""
    _default_logger.warning(msg, *args, stacklevel=2, **kwargs)


def error(msg, *args, **kwargs):
    """记录错误级别的日志"""
    _default_logger.error(msg, *args, stacklevel=2, **kwargs)


def critical(msg, *args, **kwargs):
    """记录严重错误级别的日志"""
    _default_logger.critical(msg, *args, stacklevel=2, **kwargs)


def exception(msg, *args, **kwargs):
    """记录异常信息，包含堆栈跟踪"""
    _default_logger.exception(msg, *args, stacklevel=2, **kwargs)


def set_level(level):
    """设置日志级别"""
    _default_logger.setLevel(level)
    for handler in _default_logger.handlers:
        handler.setLevel(level)
