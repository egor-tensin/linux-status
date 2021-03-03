#!/usr/bin/env python3

# Copyright (c) 2021 Egor Tensin <Egor.Tensin@gmail.com>
# This file is part of the "linux-status" project.
# For details, see https://github.com/egor-tensin/linux-status.
# Distributed under the MIT License.

import abc
import cgi
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import json
import os
import pwd
import shlex
import socket
import subprocess
from subprocess import DEVNULL, PIPE, STDOUT


def split_by(xs, sep):
    group = []
    for x in xs:
        if x == sep:
            yield group
            group = []
        else:
            group.append(x)
    yield group


def hostname():
    return socket.gethostname()


class Response:
    def __init__(self, data):
        self.data = data

    def print(self):
        print("Content-Type: text/html; charset=utf-8")
        print()
        if self.data is not None:
            print(self.dump_json(self.data))

    @staticmethod
    def dump_json(data):
        return json.dumps(data, ensure_ascii=False)


def run_do(*args, **kwargs):
    output = subprocess.run(args, stdin=DEVNULL, stdout=PIPE, stderr=STDOUT, universal_newlines=True, **kwargs)
    return output.stdout


pool = ThreadPoolExecutor()


def run(*args, **kwargs):
    return pool.submit(run_do, *args, **kwargs)


class Command:
    def __init__(self, *args):
        self.args = args
        self.env = None

    def run(self):
        return run(*self.args, env=self.env)


class Systemd(Command):
    def __init__(self, *args):
        super().__init__(*args)
        self.env = self.make_env()

    @staticmethod
    def make_env():
        env = os.environ.copy()
        env['SYSTEMD_PAGER'] = ''
        env['SYSTEMD_COLORS'] = 'no'
        return env

    @staticmethod
    def su(user, cmd):
        new = Systemd('su', '-c', shlex.join(cmd.args), user.name)
        new.env = Systemd.fix_su_env(user, cmd.env.copy())
        return new

    @staticmethod
    def fix_su_env(user, env):
        # https://unix.stackexchange.com/q/483948
        # https://unix.stackexchange.com/q/346841
        # https://unix.stackexchange.com/q/423632
        # https://unix.stackexchange.com/q/245768
        # https://unix.stackexchange.com/q/434494
        env['XDG_RUNTIME_DIR'] = user.runtime_dir
        # I'm not sure the bus part works everywhere.
        bus_path = os.path.join(user.runtime_dir, 'bus')
        env['DBUS_SESSION_BUS_ADDRESS'] = 'unix:path=' + bus_path
        return env


class Systemctl(Systemd):
    def __init__(self, *args):
        super().__init__('systemctl', *args, '--full')

    @staticmethod
    def system(*args):
        return Systemctl('--system', *args)

    @staticmethod
    def user(*args):
        return Systemctl('--user', *args)


class Loginctl(Systemd):
    def __init__(self, *args):
        super().__init__('loginctl', *args)


class Task(abc.ABC):
    def complete(self):
        self.run()
        return Response(self.result())

    @abc.abstractmethod
    def run(self):
        pass

    @abc.abstractmethod
    def result(self):
        pass


class TopTask(Task):
    def __init__(self):
        self.cmd = Command('top', '-b', '-n', '1', '-w', '512')

    def run(self):
        self.task = self.cmd.run()

    def result(self):
        return self.task.result()


class InstanceStatusTask(Task):
    def __init__(self, systemctl):
        self.overview_cmd = systemctl('status')
        self.failed_cmd = systemctl('list-units', '--failed')
        self.timers_cmd = systemctl('list-timers', '--all')

    def run(self):
        self.overview_task = self.overview_cmd.run()
        self.failed_task = self.failed_cmd.run()
        self.timers_task = self.timers_cmd.run()

    def result(self):
        return {
            'overview': self.overview_task.result(),
            'failed': self.failed_task.result(),
            'timers': self.timers_task.result(),
        }


class SystemInstanceStatusTask(InstanceStatusTask):
    def __init__(self):
        super().__init__(Systemctl.system)


class UserInstanceStatusTask(InstanceStatusTask):
    def __init__(self, systemctl=Systemctl.user):
        super().__init__(systemctl)

    @staticmethod
    def su(user):
        systemctl = lambda *args: Systemd.su(user.name, Systemctl.user(*args))
        return UserInstanceStatusTask(systemctl)


class UserInstanceStatusTaskList(Task):
    def __init__(self):
        if running_as_root():
            # As root, we can query all the user instances.
            self.tasks = {user.name: UserInstanceStatusTask.su(user) for user in systemd_users()}
        else:
            # As a regular user, we can only query ourselves.
            self.tasks = {get_current_user().name: UserInstanceStatusTask()}

    def run(self):
        for task in self.tasks.values():
            task.run()

    def result(self):
        return {name: task.result() for name, task in self.tasks.items()}


class StatusTask(Task):
    def __init__(self):
        self.hostname = hostname()
        self.top = TopTask()
        self.system = SystemInstanceStatusTask()
        self.user = UserInstanceStatusTaskList()

    def run(self):
        self.top.run()
        self.system.run()
        self.user.run()

    def result(self):
        return {
            'hostname': self.hostname,
            'top': self.top.result(),
            'system': self.system.result(),
            'user': self.user.result(),
        }


class TimersTask(StatusTask):
    # TODO: I'm going to remove the timers-only endpoint completely.
    pass


User = namedtuple('User', ['uid', 'name'])
SystemdUser = namedtuple('SystemdUser', ['uid', 'name', 'runtime_dir'])


def running_as_root():
    # AFAIK, Python's http.server drops root privileges and executes the scripts
    # as user nobody.
    # It does no such thing if run as a regular user though.
    return os.geteuid() == 0 or running_as_nobody()


def running_as_nobody():
    for user in users():
        if user.name == 'nobody':
            return user.uid == os.geteuid()
    return False


def get_current_user():
    uid = os.getuid()
    entry = pwd.getpwuid(uid)
    return User(entry.pw_uid, entry.pw_name)


# A pitiful attempt to find a list of possibly-systemd-enabled users follows
# (i.e. users that might be running a per-user systemd instance).
# I don't know of a better way than probing /run/user/UID.
# Maybe running something like `loginctl list-sessions` would be better?

# These are the default values, see [1].
# The actual values are specified in /etc/login.defs.
# Still, they can be overridden on the command line, so I don't think there
# actually is a way to list non-system users (imma call them "human").
#
#   [1]: https://man7.org/linux/man-pages/man8/useradd.8.html
UID_MIN = 1000
UID_MAX = 60000


def users():
    for entry in pwd.getpwall():
        yield User(entry.pw_uid, entry.pw_name)


def human_users():
    for user in users():
        if user.uid < UID_MIN:
            continue
        if user.uid > UID_MAX:
            continue
        yield user


# You know what, loginctl might just be the answer.
# Namely, `loginctl list-users`: during my testing, it did only list the users
# that were running a systemd instance.
def systemd_users():
    def list_users():
        output = Loginctl('list-users', '--no-legend').run().result()
        lines = output.splitlines()
        if not lines:
            return
        for line in lines:
            # This assumes user names cannot contain spaces.
            # loginctl list-users output must be in the UID NAME format.
            info = line.split(' ', 2)
            if len(info) < 2:
                raise RuntimeError(f'invalid `loginctl list-users` output:\n{output}')
            uid, user = info[0], info[1]
            yield User(uid, user)

    def show_users(users):
        properties = 'UID', 'Name', 'RuntimePath'
        prop_args = (arg for prop in properties for arg in ('-p', prop))
        user_args = (user.name for user in users)
        output = Loginctl('show-user', *prop_args, '--value', *user_args).run().result()
        lines = output.splitlines()
        # Assuming that for muptiple users, the properties will be separated by
        # an empty string.
        groups = split_by(lines, '')
        for group in groups:
            if len(group) != len(properties):
                raise RuntimeError(f'invalid `loginctl show-user` output:\n{output}')
            yield SystemdUser(int(group[0]), group[1], group[2])

    return show_users(list_users())


class Request(Enum):
    STATUS = 'status'
    TIMERS = 'timers'
    TOP = 'top'

    def __str__(self):
        return self.value

    def process(self):
        if self is Request.STATUS:
            return StatusTask().complete()
        if self is Request.TIMERS:
            return TimersTask().complete()
        if self is Request.TOP:
            return TopTask().complete()
        raise NotImplementedError(f'unknown request: {self}')


def process_cgi_request():
    params = cgi.FieldStorage()
    what = params['what'].value
    Request(what).process().print()


def main():
    process_cgi_request()


if __name__ == '__main__':
    main()
