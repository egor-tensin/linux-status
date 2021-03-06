#!/usr/bin/env python3

# Copyright (c) 2021 Egor Tensin <Egor.Tensin@gmail.com>
# This file is part of the "linux-status" project.
# For details, see https://github.com/egor-tensin/linux-status.
# Distributed under the MIT License.

# Initially it was just index.html and a bunch of shell scripts in cgi-bin.
# The web server could be launched using just `python -m http.server --cgi`,
# and all was well.  Until I decided that I want to package this little app
# of mine so that it can be easily installed and run on a variety of systems.
# There was a problem with that, however: the app was designed to be run by
# a regular user, not root (mostly due to all the `systemctl --user` calls),
# and it didn't play nicely with the whole package idea.  Plus, I've long
# wanted to make it show all the systemd user instances, not just the running
# user's.  In addition, I wanted to dedupe the small chunks of code in cgi-bin.
#
# So this script was born.  It could handle a lot more complexity than the
# shell scripts; it could be run as root and as a regular user, etc.  It was
# still a CGI script (and it still is BTW), and a separate Python instance was
# used by the web server to execute it.
#
# There was a problem, of course.  The thing is, I for once had a very strict
# performance requirement for this script: it had to work nicely on my rather
# old Raspberry Pi 1 Model B+.  It, being a Python script, didn't.  After
# some investigation, it was obvious that the main problem were the imports
# (especially those of the cgi & logging modules); they would take more time
# than the interval between requests.  So I had to find a way to make it more
# performant.
#
# I played with Lua for a bit, but couldn't quite make it work in a
# satisfactory way.  Then I had an idea: I could use http.server's HTTP server
# classes, overriding them to handle the "CGI" requests using the code in this
# script.  That way, the imports would only be done once for the entire life
# of the server.  In addition, no more tricks with sudo were required
# (http.server runs CGI scripts as user nobody, which is a no-no for this app;
# some trickery like whitelisting nobody in /etc/sudoers.d were employed).
#
# So that's where we are now, and it works!  Doesn't load my good ol' Raspberry
# no more.

import abc
import cgi
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import http.server
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

    def headers(self):
        yield 'Content-Type', 'text/html; charset=utf-8'

    @staticmethod
    def dump_json(data):
        return json.dumps(data, ensure_ascii=False, indent=4)

    def body(self):
        return self.dump_json(self.data)

    def write_as_cgi_script(self):
        self.write_headers_as_cgi_script()
        self.write_body_as_cgi_script()

    def write_headers_as_cgi_script(self):
        for name, val in self.headers():
            print(f'{name}: {val}')
        print()

    def write_body_as_cgi_script(self):
        if self.data is not None:
            print(self.body())

    def write_as_request_handler(self, handler):
        handler.send_response(http.server.HTTPStatus.OK)
        self.write_headers_as_request_handler(handler)
        self.write_body_as_request_handler(handler)

    def write_headers_as_request_handler(self, handler):
        for name, val in self.headers():
            handler.send_header(name, val)
        handler.end_headers()

    def write_body_as_request_handler(self, handler):
        if self.data is not None:
            handler.wfile.write(self.body().encode(errors='replace'))


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


class Ctl(Systemd):
    def __init__(self, executable, *args):
        super().__init__(executable, *args, '--full')

    @classmethod
    def system(cls, *args):
        return cls('--system', *args)

    @classmethod
    def user(cls, *args):
        return cls('--user', *args)


class Systemctl(Ctl):
    def __init__(self, *args):
        super().__init__('systemctl', *args)


class Journalctl(Ctl):
    def __init__(self, *args):
        super().__init__('journalctl', *args)


class Loginctl(Systemd):
    def __init__(self, *args):
        super().__init__('loginctl', *args, '--full')


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


class RebootTask(Task):
    def __init__(self):
        self.cmd = Command('systemctl', 'reboot')

    def run(self):
        self.task = self.cmd.run()

    def result(self):
        return self.task.result()


class PoweroffTask(Task):
    def __init__(self):
        self.cmd = Command('systemctl', 'poweroff')

    def run(self):
        self.task = self.cmd.run()

    def result(self):
        return self.task.result()


class InstanceStatusTask(Task):
    def __init__(self, systemctl, journalctl):
        self.overview_cmd = systemctl('status')
        self.failed_cmd = systemctl('list-units', '--failed')
        self.timers_cmd = systemctl('list-timers', '--all')
        self.journal_cmd = journalctl('-b', '--lines=20')

    def run(self):
        self.overview_task = self.overview_cmd.run()
        self.failed_task = self.failed_cmd.run()
        self.timers_task = self.timers_cmd.run()
        self.journal_task = self.journal_cmd.run()

    def result(self):
        return {
            'overview': self.overview_task.result(),
            'failed': self.failed_task.result(),
            'timers': self.timers_task.result(),
            'journal': self.journal_task.result(),
        }


class SystemInstanceStatusTask(InstanceStatusTask):
    def __init__(self):
        super().__init__(Systemctl.system, Journalctl.system)


class UserInstanceStatusTask(InstanceStatusTask):
    def __init__(self, systemctl=Systemctl.user, journalctl=Journalctl.user):
        super().__init__(systemctl, journalctl)

    @staticmethod
    def su(user):
        systemctl = lambda *args: Systemd.su(user, Systemctl.user(*args))
        journalctl = lambda *args: Systemd.su(user, Journalctl.user(*args))
        return UserInstanceStatusTask(systemctl, journalctl)


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
        self.system = SystemInstanceStatusTask()
        self.user = UserInstanceStatusTaskList()

    def run(self):
        self.system.run()
        self.user.run()

    def result(self):
        return {
            'hostname': self.hostname,
            'system': self.system.result(),
            'user': self.user.result(),
        }


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
    TOP = 'top'
    REBOOT = 'reboot'
    POWEROFF = 'poweroff'

    def __str__(self):
        return self.value

    @staticmethod
    def from_http_path(path):
        if not path or path[0] != '/':
            raise ValueError('HTTP path must start with a forward slash /')
        return Request(path[1:])

    def process(self):
        if self is Request.STATUS:
            return StatusTask().complete()
        if self is Request.TOP:
            return TopTask().complete()
        if self is Request.REBOOT:
            return RebootTask().complete()
        if self is Request.POWEROFF:
            return PoweroffTask().complete()
        raise NotImplementedError(f'unknown request: {self}')


def process_cgi_request():
    params = cgi.FieldStorage()
    what = params['what'].value
    Request(what).process().write_as_cgi_script()


def main():
    process_cgi_request()


if __name__ == '__main__':
    main()
