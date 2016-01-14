# -*- coding: utf8 -*-
# Copyright © 2015 Philippe Pepiot
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import unicode_literals
from __future__ import absolute_import

import logging

HAS_ANSIBLE_1 = False
HAS_ANSIBLE_2 = False

try:
    import ansible.inventory
    import ansible.runner
except ImportError:
    pass
else:
    HAS_ANSIBLE_1 = True

try:
    from collections import namedtuple
    from ansible.parsing.dataloader import DataLoader
    from ansible.vars import VariableManager
    from ansible.inventory import Inventory
    from ansible.playbook.play import Play
    from ansible.executor.task_queue_manager import TaskQueueManager
except ImportError:
    pass
else:
    HAS_ANSIBLE_2 = True

from testinfra.backend import base

logger = logging.getLogger("testinfra")


class AnsibleBackend(base.BaseBackend):
    NAME = "ansible"
    HAS_RUN_ANSIBLE = True

    def __init__(self, host, ansible_inventory=None, *args, **kwargs):
        self.host = host
        self.ansible_inventory = ansible_inventory
        print "host : %s \nansible_inventory : %s \n " % (host,ansible_inventory)
        super(AnsibleBackend, self).__init__(host, *args, **kwargs)

    @staticmethod
    def _check_ansible():
        if not HAS_ANSIBLE_1 and not HAS_ANSIBLE_2:
            raise RuntimeError(
                    "You must install ansible package to use the ansible backend")

    def run(self, command, *args):
        self._check_ansible()

        print "self : %s \ncommand : %s \n args: %s" % (self,command,args)

        if HAS_ANSIBLE_1:
            import ansible.inventory
            import ansible.runner
            command = self.get_command(command, *args)
            kwargs = {}
            if self.ansible_inventory is not None:
                kwargs["host_list"] = self.ansible_inventory
            out = ansible.runner.Runner(
                    pattern=self.host,
                    module_name="shell",
                    module_args=command,
                    **kwargs
            ).run()["contacted"][self.host]

            # Ansible return an unicode object but this is bytes ...
            # A simple test case is:
            # >>> assert File("/bin/true").content == open("/bin/true").read()
            stdout_bytes = b"".join((chr(ord(c)) for c in out['stdout']))
            stderr_bytes = b"".join((chr(ord(c)) for c in out['stderr']))

            result = base.CommandResult(
                    self, out['rc'],
                    stdout_bytes,
                    stderr_bytes,
                    command,
                    stdout=out["stdout"], stderr=out["stderr"],
            )
            logger.info("RUN %s", result)
            print "result %s" % result
            return result

        if HAS_ANSIBLE_2:
            from collections import namedtuple
            from ansible.parsing.dataloader import DataLoader
            from ansible.vars import VariableManager
            from ansible.inventory import Inventory
            from ansible.playbook.play import Play
            from ansible.executor.task_queue_manager import TaskQueueManager
            command = self.get_command(command, *args)
            Options = namedtuple('Options', ['connection', 'module_path', 'forks', 'remote_user', 'private_key_file',
                                             'ssh_common_args', 'ssh_extra_args', 'sftp_extra_args', 'scp_extra_args',
                                             'become', 'become_method', 'become_user', 'verbosity', 'check'])
            # initialize needed objects
            variable_manager = VariableManager()
            loader = DataLoader()
            options = Options(connection='smart', module_path=None, forks=100, remote_user=None,
                              private_key_file=None, ssh_common_args=None, ssh_extra_args=None, sftp_extra_args=None,
                              scp_extra_args=None, become=None, become_method=None, become_user=None, verbosity=None,
                              check=False)
            passwords = dict()

            # create inventory and pass to var manager
            inventory = Inventory(loader, variable_manager, self.ansible_inventory)
            variable_manager.set_inventory(inventory)

            # create play with tasks
            play_source = dict(
                    name="Ansible Play",
                    hosts=self.host,
                    gather_facts='no',
                    tasks=[dict(action=dict(module="shell", args=command))]
            )
            play = Play().load(play_source, variable_manager=variable_manager, loader=loader)

            # actually run it
            tqm = None
            try:
                tqm = TaskQueueManager(
                        inventory=inventory,
                        variable_manager=variable_manager,
                        loader=loader,
                        options=options,
                        passwords=passwords,
                        stdout_callback='default',
                )
                result = tqm.run(play)

                print "result: %s" % result


                ret = base.CommandResult(
                        self, result,
                        b"",
                        b"",
                        command,
                        stdout="", stderr="",
                )

                return ret
            finally:
                if tqm is not None:
                    tqm.cleanup()

    @classmethod
    def get_hosts(cls, host, **kwargs):
        AnsibleBackend._check_ansible()

        ansible_inventory = kwargs.get("ansible_inventory")

        if HAS_ANSIBLE_1:
            if ansible_inventory is not None:
                inventory = ansible.inventory.Inventory(ansible_inventory)
            else:
                inventory = ansible.inventory.Inventory()
        else:
            if ansible_inventory is not None:
                variable_manager = VariableManager()
                loader = DataLoader()
                inventory = ansible.inventory.Inventory(loader,variable_manager,ansible_inventory)
            else:
                inventory = ansible.inventory.Inventory()

        return [e.name for e in inventory.get_hosts(pattern=host or "all")]
