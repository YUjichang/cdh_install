#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Yujichang

import os
import logging
import logging.handlers

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class SystemLog(object):
    def __init__(self, logger):
        self.logger = logging.getLogger(logger)

        stream_handler = logging.StreamHandler()
        file_handler = logging.FileHandler(filename=os.path.join(basedir, 'logs/install.log'))

        self.logger.setLevel(logging.INFO)
        stream_handler.setLevel(logging.INFO)
        file_handler.setLevel(logging.INFO)

        formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        stream_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        self.logger.addHandler(stream_handler)
        self.logger.addHandler(file_handler)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def critical(self, msg):
        self.logger.critical(msg)


check_log = SystemLog('checkLog')
ssh_distribute_log = SystemLog('sshDistributeLog')
install_log = SystemLog('installLog')
