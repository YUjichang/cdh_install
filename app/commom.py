#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Yujichang

import subprocess
import os
from app.config import config
from string import Template

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def run_shell_command(command):
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
    return result


def set_config_by_ansible(myansible):
    """
    加载 ansible 变量到 config
    """
    all_hosts = myansible.inv_obj.get_groups_dict()['all']

    hostname = []
    for ip in all_hosts:
        host = myansible.inv_obj.get_host(hostname=ip)
        host_vars = myansible.variable_manager.get_vars(host=host)
        hostname.append({'ip': ip, 'name': host_vars.get('hostname')})

    config['host'] = hostname


def set_ansible_by_config(myansible):
    """
    加载 config 配置文件变量到 ansible
    """
    # 加载密码
    myansible.variable_manager.extra_vars.update(config['password'])

    # 加载ssh端口
    myansible.variable_manager.extra_vars.update({'ansible_ssh_port': config['ssh']['port']})

    # 加载impala和hive的地址
    myansible.variable_manager.extra_vars.update({'impala_server': config['impala']['impala_server'],
                                                  'hs2_server': config['hive']['hs2_server']})


def ip_hostname_mapping():
    # 读取配置文件，生成ip和hostname字符串
    _temple = '$ip $name'
    host_map_temple = Template(_temple)

    ip_hostname = [host_map_temple.substitute(host) for host in config['host']]

    host_mapping = '\n'.join(ip_hostname)

    return host_mapping
