#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Yujichang

import os
from app.commom import run_shell_command
from app.config import config
from app.log import ssh_distribute_log as log

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def check_server_sshpass(password):
    """
    检查 server 是否安装了 sshpass，免密登录需要此包
    """
    check_status = run_shell_command('rpm -qa | grep sshpass')

    if check_status.returncode == 0:
        log.info('sshpass is already installed.')
    else:
        rpm_package = os.path.join(basedir, 'packages/sshpass-1.06-2.el7.x86_64.rpm')

        if config['ssh']['user'] != 'root':
            result_status = run_shell_command(f'echo {password} | sudo -S rpm -ivh {rpm_package}')
        else:
            result_status = run_shell_command(f'rpm -ivh {rpm_package}')

        if result_status.returncode == 0:
            log.info('sshpass install complete.')


class SSHWithoutPass(object):
    def __init__(self):
        self.path = os.path.expanduser('~/.ssh')
        self.private_key = os.path.expanduser('~/.ssh/id_dsa')
        self.pub_key = os.path.expanduser('~/.ssh/id_dsa.pub')
        self.create_ssh_key()

    def create_ssh_key(self):
        if not os.path.exists(self.path):
            os.mkdir(self.path, 0o700)

        if os.path.exists(self.pub_key):
            log.info(f'find ssh public key {self.pub_key}.')
        else:
            result = run_shell_command(f'ssh-keygen -t dsa -f {self.private_key} -P ""')
            if result.returncode == 0:
                log.info(f'create ssh key success,private key is {self.private_key}, pub key is {self.pub_key}')
            else:
                self.pub_key = None
                log.error(f'create ssh key failed,cause by {result.stderr}')

    def distribute_ssh_key(self, hosts: list, user='root', port=22, password=None):
        if self.pub_key is None:
            return

        check_server_sshpass(password)

        for ip in hosts:
            command = f'sshpass -p "{password}" ssh-copy-id -i {self.pub_key} -p {port} -o StrictHostKeyChecking=no {user}@{ip}'
            result = run_shell_command(command)
            if result.returncode == 0:
                log.info(f'{ip} distribute success.')
            else:
                log.error(f'{ip} distribute failed, cause by {result.stderr}')
