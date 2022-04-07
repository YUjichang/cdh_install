#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Yujichang

import os
import pandas as pd
import json
from app.log import install_log as log
from app.config import config
from app.commom import ip_hostname_mapping

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
tempdir = '/tmp/cdh_install_temp'

MYSQL_FILE = config['packages']['mysql']
JDK_FILE = config['packages']['jdk']
CDH_PARCELS = config['packages']['cdh-parcels']
CDH_CM_FILE = config['packages']['cdh-cm']
LOG4J_FILE = config['packages']['log4j']


def get_yum_status_task(myansible, hosts):
    task = dict(action=dict(module='shell', args='yum install telnet -y'))
    myansible.run(hosts=hosts, task=task)
    result = myansible.get_result()

    # 命令结果转化为 dataframe 格式
    df = pd.DataFrame.from_dict(json.loads(result).values())

    return df


def run_task_list(myansible, hosts, task_list: list, task_name):
    """
    执行任务列表
    :param myansible: ansible 实例
    :param hosts: 主机标签组
    :param task_list: 任务列表
    :param task_name: 任务名称
    """
    # 生成一个空DataFrame，记录任务运行状态
    df = pd.DataFrame(columns=['host', 'ansible_run_status'])

    # 提交任务列表执行
    for task in task_list:
        myansible.run(hosts=hosts, task=task)
        result = myansible.get_result()
        temp = pd.DataFrame.from_dict(json.loads(result).values())
        df = pd.concat([df, temp], axis=0, sort=False, ignore_index=True)

    # 检查所有主机任务运行状态，记录日志
    check_run_status = df['ansible_run_status'] == 'success'
    if check_run_status.all():
        log.info(f'{hosts} run {task_name} success.')
    else:
        run_host = df[df['ansible_run_status'] != 'success'].drop_duplicates(subset=['host'])['host'].to_list()
        log.error(f'{run_host} run {task_name} failed.')

        stdout = df[(df['host'].isin(run_host)) & (df['ansible_run_status'] == 'failed')]['stdout'].values
        stderr = df[(df['host'].isin(run_host)) & (df['ansible_run_status'] == 'failed')]['stderr'].values
        log.error(f'{run_host} stdout: {stdout} stderr: {stderr}')


def modify_hostname_task(myansible, hosts):
    """
    修改主机名
    """
    log.info(f'{hosts} start run task: modify_hostname.')

    # 设置任务，修改主机名
    task = dict(action=dict(module='hostname', args='name={{ hostname }}'))

    # 提交任务执行
    task_list = [task]
    run_task_list(myansible, hosts, task_list, 'modify_hostname')


def modify_etc_host_task(myansible):
    """
    修改/etc/hosts文件，添加 ip 主机名映射
    """
    log.info('cdh_servers start run task: modify /etc/host.')

    # 获取ip主机名解析
    host_mapping = ip_hostname_mapping()

    # 删除主机名映射到127.0.0.1的行
    task1 = dict(action=dict(module='shell', args='sed -i "/127.0.0.1.*{{ hostname }}/d" /etc/hosts'))

    # 设置任务，将主机名解析添加到/etc/hosts
    task2 = dict(action=dict(module='blockinfile', args=f'path=/etc/hosts block="{host_mapping}" backup=yes'))

    # 提交任务执行
    task_list = [task1, task2]
    run_task_list(myansible, 'cdh_servers', task_list, 'modify /etc/host')


def distribute_file_task(myansible, hosts):
    """
    分发所有 scm_agent 主机用到的文件
    """
    log.info(f'{hosts} start run task: distribute_file.')

    # 要分发的文件
    src_list = (
        os.path.join(basedir, f'packages/{CDH_CM_FILE}'),
        os.path.join(basedir, f'packages/{JDK_FILE}'),
        os.path.join(basedir, f'packages/{LOG4J_FILE}'),
        os.path.join(basedir, 'scripts/installNTP.sh'),
        os.path.join(basedir, 'scripts/installJDK.sh')
    )

    # 设置任务
    task_list = [dict(action=dict(module='file', args=f'path={tempdir} state=directory'))]
    for src in src_list:
        task_list.append(dict(action=dict(module='copy', args=f'src={src} dest={tempdir} force=no')))

    # 提交任务执行
    run_task_list(myansible, hosts, task_list, 'distribute_file')


def install_jdk_task(myansible, hosts):
    """
    安装jdk1.8
    """
    log.info(f'{hosts} start run task: install_jdk.')

    # 设置任务
    script_file = os.path.join(tempdir, 'installJDK.sh')
    jdk_file = os.path.join(tempdir, JDK_FILE)
    creates = os.path.join(tempdir, 'install_jdk_ok_tag')
    task = dict(action=dict(module='shell', args=f'creates={creates} sh {script_file} {jdk_file} && touch {creates}'))

    # 提交任务执行
    task_list = [task]
    run_task_list(myansible, hosts, task_list, 'install_jdk')


def install_ntp_task(myansible, hosts):
    """
    安装ntp
    """
    log.info(f'{hosts} start run task: install_ntp.')

    # 设置任务
    script_file = os.path.join(tempdir, 'installNTP.sh')
    creates = os.path.join(tempdir, 'install_ntp_ok_tag')

    if config['ntp_external_server'] is None:
        ntp_server = myansible.inv_obj.get_hosts(pattern='scm_server')[0]
    else:
        ntp_server = config['ntp_external_server']

    task = dict(action=dict(module='shell', args=f'creates={creates} sh {script_file} {ntp_server} && touch {creates}'))

    # 提交任务执行
    task_list = [task]
    run_task_list(myansible, hosts, task_list, 'install_ntp')


def update_log4j_task(myansible, hosts):
    """
    更新log4j2版本，修改log4j漏洞
    """
    log.info(f'{hosts} start run task: update log4j2.')

    # 设置任务
    task1 = dict(action=dict(module='shell', args=f'chdir={tempdir} tar zxf {LOG4J_FILE}'))

    log4j_file = LOG4J_FILE.replace('.tar.gz', '')
    log4j_path = os.path.join(tempdir, log4j_file)
    script_file = os.path.join(log4j_path, 'update_log4j2_for_cdh.sh')

    task2 = dict(action=dict(module='shell', args=f'chdir={log4j_path} sh {script_file}'))

    # 提交任务执行
    task_list = [task1, task2]
    run_task_list(myansible, hosts, task_list, 'update log4j2')


def install_mysql_task(myansible, hosts):
    """
    安装mysql5.7
    """
    log.info(f'{hosts} start run task: install_mysql.')

    # 设置任务
    task_list = []

    # 分发mysql二进制安装包和脚本
    src_list = (
        os.path.join(basedir, f'packages/{MYSQL_FILE}'),
        os.path.join(basedir, 'scripts/installMysql.sh')
    )

    for src in src_list:
        task_list.append(dict(action=dict(module='copy', args=f'src={src} dest={tempdir} force=no')))

    # 执行脚本
    mysql_install_path = config['mysql_install_path']
    script_file = os.path.join(tempdir, 'installMysql.sh')
    creates = os.path.join(tempdir, 'install_mysql_ok_tag')

    task = dict(action=dict(module='shell',
                            args=f'creates={creates} chdir={tempdir} '
                                 f'sh {script_file} {MYSQL_FILE} {mysql_install_path} && touch {creates}'))
    task_list.append(task)

    # 提交任务执行
    run_task_list(myansible, hosts, task_list, 'install_mysql')


def init_mysql_task(myansible, hosts):
    """
    初始化mysql, 修改 mysql 密码，并创建相关数据库和用户
    """
    log.info(f'{hosts} start run task: init_mysql.')

    # 渲染初始化模板
    _initMysql_temp = os.path.join(basedir, 'template/initMysql.j2')
    init_sql = os.path.join(tempdir, 'initMysql.sql')
    task1 = dict(action=dict(module='template', args=f'src={_initMysql_temp} dest={init_sql}'))

    # 执行初始化脚本
    mysql = os.path.join(config['mysql_install_path'], 'mysql/bin/mysql')
    creates = os.path.join(tempdir, 'init_mysql_ok_tag')
    task2 = dict(action=dict(module='shell', args=f'creates={creates} {mysql} -uroot < {init_sql} && touch {creates}'))

    # 设置任务
    task_list = [task1, task2]

    # 提交任务执行
    run_task_list(myansible, hosts, task_list, 'init_mysql')


def get_mysql_master_info_task(myansible, hosts):
    """
    主从配置中，获取主库的binlog信息
    """
    my_root_password = config['password']['my_root']
    mysql = os.path.join(config['mysql_install_path'], 'mysql/bin/mysql')

    task1 = dict(action=dict(module='shell',
                             args=f'{mysql} -uroot -p{my_root_password} -e "show master status;" > /tmp/info'))
    task2 = dict(action=dict(module='shell', args='cat /tmp/info | tail -n 1'))

    myansible.run(hosts=hosts, task=task1)
    myansible.run(hosts=hosts, task=task2)
    result = myansible.get_result()

    # 命令结果转化为 dataframe 格式
    df = pd.DataFrame.from_dict(json.loads(result).values())

    result = df['stdout'].to_list()[0].split()
    master_log_file = result[0]
    master_binlog_pos = int(result[1])

    return master_log_file, master_binlog_pos


def configure_mysql_replication(myansible, hosts):
    """
    配置mysql主从同步
    """
    log.info(f'{hosts} start run task: configure_mysql master/slave.')

    # 获取主从服务器ip
    host = myansible.inv_obj.get_groups_dict()[hosts]
    master = host[0]
    slave = host[1]

    my_root_password = config['password']['my_root']
    my_repl_password = config['password']['my_repl']

    # 设置主库的binlog记录，以下是初始化完后的binlog记录
    master_log_file, master_binlog_pos = get_mysql_master_info_task(myansible, master)

    slave_conf = 'read-only = 1\nlog_slave_updates=ON\nrelay-log = relay-bin'
    mysql = os.path.join(config['mysql_install_path'], 'mysql/bin/mysql')
    creates = os.path.join(tempdir, 'repl_mysql_ok_tag')
    change_master_sql = f"change master to master_host\='{master}',master_user\='repl'," \
                        f"master_password\='{my_repl_password}',master_log_file\='{master_log_file}'," \
                        f"master_log_pos\={master_binlog_pos};start slave;"

    slave_task1 = dict(action=dict(module='lineinfile', args='path=/etc/my.cnf regexp="^server-id = 1" '
                                                             'line="server-id = 2" backup=yes'))
    slave_task2 = dict(action=dict(module='lineinfile', args=f'path=/etc/my.cnf line="{slave_conf}" '
                                                             f'insertafter="^binlog_format"'))
    slave_task3 = dict(action=dict(module='service', args='name=mysqld state=restarted'))
    slave_task4 = dict(action=dict(module='shell', args=f'creates={creates} {mysql} -uroot -p{my_root_password} '
                                                        f'-e "{change_master_sql}" && touch {creates}'))

    task_list = [slave_task1, slave_task2, slave_task3, slave_task4]

    # 提交任务执行
    run_task_list(myansible, slave, task_list, 'configure_mysql master/slave')


def close_firewall_task(myansible, hosts):
    """
    关闭 firewalld 防火墙
    """
    log.info(f'{hosts} start run task: close_firewall.')

    # 设置任务
    task = dict(action=dict(module='service', args='name=firewalld state=stopped enabled=no'))

    # 提交任务执行
    task_list = [task]
    run_task_list(myansible, hosts, task_list, 'close_firewall')


def close_selinux_task(myansible, hosts):
    """
    关闭 selinux
    """
    log.info(f'{hosts} start run task: close_selinux.')

    # 设置任务
    task = dict(action=dict(module='shell', args="if [ $(getenforce) \=\= 'Enforcing' ];then setenforce 0;fi"))
    task1 = dict(action=dict(module='lineinfile', args='path=/etc/selinux/config regexp="^SELINUX=enforcing" '
                                                       'line="SELINUX=disabled" backup=yes'))

    # 提交任务执行
    task_list = [task, task1]
    run_task_list(myansible, hosts, task_list, 'close_selinux')


def modify_kernel_task(myansible, hosts):
    """
    修改内核参数
    """
    log.info(f'{hosts} start run task: modify_kernel_option.')

    # 设置任务
    # 添加 vm.swappiness 参数
    task1 = dict(action=dict(module='lineinfile', args='path=/etc/sysctl.conf line="vm.swappiness = 0" backup=yes'))

    # 关闭透明大页
    close_hugepage_1 = 'echo never > /sys/kernel/mm/transparent_hugepage/defrag'
    close_hugepage_2 = 'echo never > /sys/kernel/mm/transparent_hugepage/enabled'
    task2 = dict(action=dict(module='blockinfile',
                             args=f'path=/etc/rc.local block="{close_hugepage_1}\n{close_hugepage_2}" backup=yes'))

    task3 = dict(action=dict(module='shell', args=f'{close_hugepage_1}; {close_hugepage_2}; sysctl -p'))

    # 修改文件句柄数
    _limit_conf = '*  soft  nproc   65535\n*  hard  nproc   65535\n*  soft  nofile  65535\n*  hard  nofile  65535'
    task4 = dict(action=dict(module='blockinfile',
                             args=f'path=/etc/security/limits.conf block="{_limit_conf}" backup=yes'))
    task5 = dict(action=dict(module='lineinfile',
                             args='path=/etc/security/limits.d/20-nproc.conf regexp="^\*" '
                                  'line="*          soft    nproc     65535" backup=yes'))

    # 提交任务执行
    task_list = [task1, task2, task3, task4, task5]
    run_task_list(myansible, hosts, task_list, 'modify_kernel_option')


def unzip_scm_package_task(myansible, hosts):
    """
    安装scm server 和 agent 前解压安装包和添加mysql驱动包
    """
    log.info(f'{hosts} start run task: unzip_scm_package.')
    # 解压安装包
    task1 = dict(action=dict(module='shell', args=f'chdir={tempdir} tar zxf {CDH_CM_FILE}'))

    # 添加mysql驱动包
    mysql_jar_path = os.path.join(tempdir, 'packages/mysql-connector-java-5.1.46.jar')
    task2 = dict(action=dict(module='file', args='path=/usr/share/java state=directory'))
    task3 = dict(action=dict(module='shell', args=f'/usr/bin/cp -f {mysql_jar_path} '
                                                  f'/usr/share/java/mysql-connector-java.jar'))

    # 提交任务执行
    task_list = [task1, task2, task3]
    run_task_list(myansible, hosts, task_list, 'unzip_scm_package')


def install_scm_agent_task(myansible, hosts, is_server=False):
    log.info(f'{hosts} start run task: install_scm_agent.')

    # 判断是否server那台服务器安装agent，因server安装函数已经运行过unzip_scm_package，这里无需在运行
    if not is_server:
        unzip_scm_package_task(myansible, hosts)

    # 安装cloudera manager agent
    package_dir = os.path.join(tempdir, 'packages')
    task1 = dict(action=dict(module='shell', args=f'chdir={package_dir} '
                                                  f'yum -y localinstall cloudera-manager-daemons-* && '
                                                  f'yum -y localinstall cloudera-manager-agent-*'))

    # 设置agent配置文件，指向cloudera manager server
    scm_server_ip = myansible.inv_obj.get_groups_dict()['scm_server']
    scm_server = myansible.inv_obj.get_host(hostname=scm_server_ip[0])
    scm_server_hostname = myansible.variable_manager.get_vars(host=scm_server).get('hostname')
    task2 = dict(action=dict(module='lineinfile', args=f'path=/etc/cloudera-scm-agent/config.ini '
                                                       f'regexp="^server_host=localhost" '
                                                       f'line="server_host={scm_server_hostname}" backup=yes'))

    # 更新log4j
    update_log4j_task(myansible, hosts)

    # 启动cloudera manager agent
    task3 = dict(action=dict(module='service', args='name=cloudera-scm-agent state=started enabled=yes'))

    # 提交任务执行
    task_list = [task1, task2, task3]
    run_task_list(myansible, hosts, task_list, 'install_scm_agent')


def install_scm_server_task(myansible, hosts):
    log.info(f'{hosts} start run task: install_scm_server.')

    # 解压安装包
    unzip_scm_package_task(myansible, hosts)

    # 安装cloudera manager server
    package_dir = os.path.join(tempdir, 'packages')
    task1 = dict(action=dict(module='shell', args=f'chdir={package_dir} '
                                                  f'yum -y localinstall cloudera-manager-daemons-* && '
                                                  f'yum -y localinstall cloudera-manager-server-6.*'))

    # 渲染scm数据库配置文件
    _db_properties_temp = os.path.join(basedir, 'template/db.properties.j2')
    _db_properties = '/etc/cloudera-scm-server/db.properties'
    task2 = dict(action=dict(module='template', args=f'src={_db_properties_temp} dest={_db_properties} '
                                                     f'owner="cloudera-scm" group="cloudera-scm" mode="0600"'))

    # 拷贝parcels包
    src = os.path.join(basedir, f'packages/{CDH_PARCELS}')
    dest = '/opt/cloudera/parcel-repo'
    task3 = dict(action=dict(module='copy', args=f'src={src} dest={dest} force=no'))
    task4 = dict(action=dict(module='shell', args=f'chdir={dest} tar zxf {CDH_PARCELS} && rm -f {CDH_PARCELS}'))

    # 更新log4j
    update_log4j_task(myansible, hosts)

    # 启动cloudera manager server
    task5 = dict(action=dict(module='service', args='name=cloudera-scm-server state=started enabled=yes'))

    # 提交任务执行
    task_list = [task1, task2, task3, task4, task5]
    run_task_list(myansible, hosts, task_list, 'install_scm_server')

    # server端也需要安装agent
    install_scm_agent_task(myansible, hosts, is_server=True)


def install_haproxy_task(myansible, hosts):
    """
    安装haproxy
    """
    log.info(f'{hosts} start run task: install_haproxy.')

    # 设置任务
    task1 = dict(action=dict(module='yum', args='name=haproxy state=present disable_gpg_check=yes'))

    # 渲染配置文件
    _haproxy_cfg_temp = os.path.join(basedir, 'template/haproxy_cfg.j2')
    _haproxy_cfg = '/etc/haproxy/haproxy.cfg'
    task2 = dict(action=dict(module='template', args=f'src={_haproxy_cfg_temp} dest={_haproxy_cfg}'))

    task3 = dict(action=dict(module='service', args='name=haproxy state=started enabled=no'))

    # 提交任务执行
    task_list = [task1, task2, task3]
    run_task_list(myansible, hosts, task_list, 'install_haproxy')


class BaseTemple(object):
    def __init__(self, myansible, hosts):
        self.myansible = myansible
        self.hosts = hosts

    def run_task(self):
        distribute_file_task(self.myansible, self.hosts)
        modify_hostname_task(self.myansible, self.hosts)
        modify_etc_host_task(self.myansible)
        close_firewall_task(self.myansible, self.hosts)
        close_selinux_task(self.myansible, self.hosts)
        modify_kernel_task(self.myansible, self.hosts)

        install_jdk_task(self.myansible, self.hosts)
        install_ntp_task(self.myansible, self.hosts)


class DBTemple(object):
    def __init__(self, myansible, hosts):
        self.myansible = myansible
        self.hosts = hosts

    def run_task(self):
        install_mysql_task(self.myansible, self.hosts)
        init_mysql_task(self.myansible, self.hosts)

        if config['ha']:
            configure_mysql_replication(self.myansible, self.hosts)


class ScmServerTemple(object):
    def __init__(self, myansible, hosts):
        self.myansible = myansible
        self.hosts = hosts

    def run_task(self):
        install_scm_server_task(self.myansible, self.hosts)


class ScmAgentTemple(object):
    def __init__(self, myansible, hosts):
        self.myansible = myansible
        self.hosts = hosts

    def run_task(self):
        install_scm_agent_task(self.myansible, self.hosts)


class HATemple(object):
    def __init__(self, myansible, haproxy_hosts):
        self.myansible = myansible
        self.haproxy_hosts = haproxy_hosts

    def run_task(self):
        install_haproxy_task(self.myansible, self.haproxy_hosts)
