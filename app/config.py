#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Yujichang

import os
import yaml

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

with open(os.path.join(basedir, 'conf/config.yml')) as file:
    config = yaml.load(file, Loader=yaml.FullLoader)
