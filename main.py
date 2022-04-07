#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Yujichang

import sys
import argparse
from app.ansible_api import MyAnsible
from app.log import check_log
from app.ssh_without_pass import SSHWithoutPass
from app.commom import set_config_by_ansible, set_ansible_by_config
from app.config import config
from app.task import BaseTemple, ScmServerTemple, ScmAgentTemple, DBTemple, get_yum_status_task, HATemple


def servers_check(myansible, hosts):
    """
    检查服务器连通性和是否可以 yum 安装软件包
    :param myansible: ansible 实例
    :param hosts:：主机组标签
    """
    exit_code = 0

    # 检查 yum 是否正常
    df = get_yum_status_task(myansible, hosts)

    # 检查是否存在 yum 安装失败、主机不可达，存在任一错误，程序都将会退出
    unreachable_server = df[df['ansible_run_status'] == 'unreachable']['host'].to_list()
    failed_server = df[df['ansible_run_status'] == 'failed']['host'].to_list()

    if unreachable_server:
        check_log.error(f'{unreachable_server} is unreachable')
        exit_code += 1
    if failed_server:
        check_log.error(f'{failed_server} is failed')
        exit_code += 1

    if exit_code > 0:
        check_log.error('server check failed,the program will exit.')
        sys.exit(1)
    check_log.info('server check ok.')


class CdhInstall(object):
    def __init__(self, password):
        self.password = password
        self.port = config['ssh']['port']
        self.user = config['ssh']['user']

        if self.user != 'root':
            self.myansible = MyAnsible(inventory='conf/hosts', remote_user=self.user,
                                       become=True, become_method='sudo', become_user='root')
            self.myansible.variable_manager.extra_vars.update({'ansible_become_password': self.password})
        else:
            self.myansible = MyAnsible(inventory='conf/hosts', remote_user=self.user)

        self.__set_config()

    def _ssh_distribute(self, hosts: list):
        swp = SSHWithoutPass()
        swp.distribute_ssh_key(hosts=hosts, user=self.user, password=self.password, port=self.port)

    def __set_config(self):
        set_config_by_ansible(self.myansible)
        set_ansible_by_config(self.myansible)

    def install(self):
        host_list = self.myansible.inv_obj.get_hosts()
        self._ssh_distribute(host_list)

        servers_check(self.myansible, hosts='cdh_servers')

        cdh_server = BaseTemple(self.myansible, hosts='cdh_servers')
        cdh_server.run_task()

        db_server = DBTemple(self.myansible, hosts='db_server')
        db_server.run_task()

        scm_server = ScmServerTemple(self.myansible, hosts='scm_server')
        scm_server.run_task()

        scm_agent = ScmAgentTemple(self.myansible, hosts='scm_agent')
        scm_agent.run_task()

        if config['ha']:
            ha = HATemple(self.myansible, haproxy_hosts='haproxy_server')
            ha.run_task()

    def add_agent(self, hosts):
        """
        添加agent节点
        :param hosts: 字符串格式，如果只有一台，则必须以 , 结尾，如192.168.100.200,
        """
        host_list = hosts.split(',')
        self._ssh_distribute(host_list)

        servers_check(self.myansible, hosts=hosts)

        base_init = BaseTemple(self.myansible, hosts=hosts)
        base_init.run_task()

        scm_agent = ScmAgentTemple(self.myansible, hosts=hosts)
        scm_agent.run_task()


if __name__ == '__main__':
    parse = argparse.ArgumentParser(description='install cloudera manager server and agent')
    group = parse.add_mutually_exclusive_group()
    group.add_argument(
        "--install",
        action="store_true",
        help='Install cloudera manager server and agent'
    )
    group.add_argument(
        "--add",
        action="store_true",
        help='Add cloudera manager agent'
    )
    parse.add_argument(
        "--hosts",
        help='Server host list by add cloudera manager agent'
    )
    parse.add_argument(
        "-p",
        "--password",
        help='Server password'
    )
    parse.add_argument(
        "--ha",
        action="store_true",
        help='Enable mysql master/slave mode and Install haproxy to load balancing for impala/hiveserver2'
    )

    args = parse.parse_args()

    if args.ha:
        config['ha'] = True

    if not args.password:
        print('Server password is need, please configure -p | --password argument')
        sys.exit(2)

    if args.install:
        cdh = CdhInstall(args.password)
        cdh.install()

    if args.add:
        if not args.hosts:
            print('Server host list is need by add agent, please configure --hosts argument')
        else:
            cdh = CdhInstall(args.password)
            cdh.add_agent(args.hosts)
