#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Yujichang

import json
import shutil
import ansible.constants as C
from ansible.module_utils.common.collections import ImmutableDict
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager
from ansible.inventory.manager import InventoryManager
from ansible.playbook.play import Play
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.plugins.callback import CallbackBase
from ansible import context
from ansible.executor.playbook_executor import PlaybookExecutor


class ResultCallback(CallbackBase):
    """
    回调函数
    """
    def __init__(self, *args, **kwargs):
        super(ResultCallback, self).__init__(*args, **kwargs)
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}

    def v2_runner_on_unreachable(self, result):
        self.host_unreachable[result._host.get_name()] = result

    def v2_runner_on_ok(self, result, *args, **kwargs):
        self.host_ok[result._host.get_name()] = result

    def v2_runner_on_failed(self, result, *args, **kwargs):
        self.host_failed[result._host.get_name()] = result

    def cleanup(self):
        self.host_ok.clear()
        self.host_failed.clear()
        self.host_unreachable.clear()


class MyAnsible(object):
    def __init__(self,
                 connection='smart',
                 remote_user=None,
                 remote_password=None,
                 sudo=None, sudo_user=None, ask_sudo_pass=None,
                 module_path=None,
                 become=None,
                 become_method=None,
                 become_user=None,
                 check=False, diff=False,
                 listhosts=None, listtasks=None, listtags=None,
                 verbosity=3,
                 syntax=None,
                 start_at_task=None,
                 inventory=None):

        """
        初始化函数，定义的默认的选项值，
        在初始化的时候可以传参，以便覆盖默认选项的值
        """
        context.CLIARGS = ImmutableDict(
            connection=connection,
            remote_user=remote_user,
            sudo=sudo,
            sudo_user=sudo_user,
            ask_sudo_pass=ask_sudo_pass,
            module_path=module_path,
            become=become,
            become_method=become_method,
            become_user=become_user,
            verbosity=verbosity,
            listhosts=listhosts,
            listtasks=listtasks,
            listtags=listtags,
            syntax=syntax,
            start_at_task=start_at_task,
        )

        self.inventory = inventory if inventory else "localhost,"

        # 实例化数据解析器
        self.loader = DataLoader()

        # 实例化资产配置对象
        self.inv_obj = InventoryManager(loader=self.loader, sources=self.inventory)

        # 设置密码，当为空时使用免密登录
        self.passwords = remote_password

        # 实例化回调插件对象
        self.results_callback = ResultCallback()

        # 变量管理器
        self.variable_manager = VariableManager(self.loader, self.inv_obj)

    def run(self, hosts='localhost', gether_facts="no", task=None, task_time=0):
        """
        参数说明：
        task_time -- 执行异步任务时等待的秒数，这个需要大于 0 ，等于 0 的时候不支持异步（默认值）
        """
        if task is None:
            task = dict(action=dict(module='ping', args=''), async=task_time, poll=0)
        else:
            task['async'] = task_time
            task['poll'] = 0

        play_source = dict(
            name="Ad-hoc",
            hosts=hosts,
            gather_facts=gether_facts,
            tasks=[task]
        )

        play = Play().load(play_source, variable_manager=self.variable_manager, loader=self.loader)

        tqm = TaskQueueManager(
            inventory=self.inv_obj,
            variable_manager=self.variable_manager,
            loader=self.loader,
            passwords=self.passwords,
            stdout_callback=self.results_callback
        )

        try:
            result = tqm.run(play)
        finally:
            tqm.cleanup()
            if self.loader:
                self.loader.cleanup_all_tmp_files()
            shutil.rmtree(C.DEFAULT_LOCAL_TMP, True)

    def playbook(self, playbooks):
        """
        Keyword arguments:
        playbooks --  需要是一个列表类型
        """
        playbook = PlaybookExecutor(playbooks=playbooks,
                                    inventory=self.inv_obj,
                                    variable_manager=self.variable_manager,
                                    loader=self.loader,
                                    passwords=self.passwords
                                    )

        # 使用回调函数
        playbook._tqm._stdout_callback = self.results_callback

        result = playbook.run()

    def get_result(self):
        result_raw = {}

        for host, result in self.results_callback.host_ok.items():
            result._result['ansible_run_status'] = 'success'
            result._result['host'] = host
            result_raw[host] = result._result
        for host, result in self.results_callback.host_failed.items():
            result._result['ansible_run_status'] = 'failed'
            result._result['host'] = host
            result_raw[host] = result._result
        for host, result in self.results_callback.host_unreachable.items():
            result._result['ansible_run_status'] = 'unreachable'
            result._result['host'] = host
            result_raw[host] = result._result

        # 最终打印结果，并且使用 JSON 继续格式化
        # print(json.dumps(result_raw, indent=4))

        self.results_callback.cleanup()
        return json.dumps(result_raw)
