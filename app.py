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


class Response:
    DEFAULT_STATUS = http.server.HTTPStatus.OK

    @staticmethod
    def body_from_json(body):
        return json.dumps(body, ensure_ascii=False, indent=4)

    def __init__(self, body, status=None):
        if status is None:
            status = Response.DEFAULT_STATUS
        self.status = status
        self.body = body

    def headers(self):
        yield 'Content-Type', 'text/html; charset=utf-8'

    def encode_body(self):
        return self.body.encode(errors='replace')

    def write_as_cgi_script(self):
        self.write_headers_as_cgi_script()
        self.write_body_as_cgi_script()

    def write_headers_as_cgi_script(self):
        for name, val in self.headers():
            print(f'{name}: {val}')
        print()

    def write_body_as_cgi_script(self):
        if self.body is not None:
            print(self.body)

    def write_to_request_handler(self, handler):
        handler.send_response(self.status)
        self.write_headers_to_request_handler(handler)
        self.write_body_to_request_handler(handler)

    def write_headers_to_request_handler(self, handler):
        for name, val in self.headers():
            handler.send_header(name, val)
        handler.end_headers()

    def write_body_to_request_handler(self, handler):
        if self.body is not None:
            handler.wfile.write(self.encode_body())


def run_do(*args, **kwargs):
    output = subprocess.run(args, stdin=DEVNULL, stdout=PIPE, stderr=STDOUT, universal_newlines=True, **kwargs)
    # Include the output in the exception's message:
    try:
        output.check_returncode()
    except Exception as e:
        raise RuntimeError("Command's output was this:\n" + output.stdout) from e
    return output.stdout


class Task(abc.ABC):
    def complete(self):
        self.run()
        return Response(Response.body_from_json(self.result()))

    @abc.abstractmethod
    def run(self):
        pass

    @abc.abstractmethod
    def result(self):
        pass


class TaskList(Task):
    def __init__(self, tasks):
        self.tasks = tasks

    def add(self, name, task):
        if name in self.tasks:
            raise RuntimeError(f'duplicate task name: {name}')
        self.tasks[name] = task

    def run(self):
        for task in self.tasks.values():
            task.run()

    def result(self):
        return {name: task.result() for name, task in self.tasks.items()}


pool = ThreadPoolExecutor()


def run(*args, **kwargs):
    return pool.submit(run_do, *args, **kwargs)


class Command(Task):
    def __init__(self, *args):
        self.args = args
        self.env = None

    def run(self):
        self.task = run(*self.args, env=self.env)
        return self.task

    def result(self):
        return self.task.result()

    def now(self):
        return self.run().result()


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


class Docker(Command):
    def __init__(self, *args):
        super().__init__('docker', *args)


class DockerVersion(Docker):
    def __init__(self, *args):
        super().__init__('version')

    @staticmethod
    def is_daemon_running():
        try:
            DockerVersion().now()
            return True
        except:
            return False


class DockerPs(Docker):
    def __init__(self, *args):
        super().__init__('ps', *args)

    @staticmethod
    def quiet(*args):
        return DockerPs('--quiet', *args)

    @staticmethod
    def get_all_ids():
        cmd = DockerPs.quiet('--all')
        return cmd.now().splitlines()


class DockerInspect(Docker):
    # This is pretty cool.  I wanted to separate container entries with \0, and
    # this is the best I could come up with.  Note that a newline still gets
    # added at the end.
    FORMAT = '{{printf "%s%c" (json .) 0}}'

    def __init__(self, *args):
        super().__init__('inspect', f'--format={DockerInspect.FORMAT}', *args)


class DockerStatus(DockerInspect):
    def __init__(self):
        self.containers = DockerPs.get_all_ids()
        super().__init__(*self.containers)

    def run(self):
        if not self.containers:
            # `docker inspect` requires at least one container argument.
            return ''
        return super().run()

    def result(self):
        if not self.containers:
            # `docker inspect` requires at least one container argument.
            return []
        result = super().result()
        result = result.split('\0')
        result = [json.loads(info) for info in result if info.strip()]
        result = [DockerStatus.filter_info(info) for info in result]
        return result

    @staticmethod
    def filter_info(info):
        assert info['Name'][0] == '/'
        return {
            'exit_code': info['State']['ExitCode'],
            'health': info['State'].get('Health', {}).get('Status', None),
            'image': info['Config']['Image'],
            # Strip the leading /:
            'name': info['Name'][1:],
            'started_at': info['State']['StartedAt'],
            'status': info['State']['Status'],
        }

class Hostname(Task):
    def run(self):
        pass

    def result(self):
        return socket.gethostname()


class Top(Command):
    COMMAND = None

    def __init__(self):
        super().__init__(*Top.get_command())

    @staticmethod
    def get_command():
        # On more modern versions of top, we want to enable memory scaling
        # from the command line (another option is the rc file, but that's too
        # complicated).  For that, we simply run `top -h` once, and check if
        # the output contains the flags we want to use.
        if Top.COMMAND is not None:
            return Top.COMMAND
        help_output = run_do('top', '-h')
        args = ['top', '-b', '-n', '1', '-w', '512']
        if 'Ee' in help_output:
            args += ['-E', 'm', '-e', 'm']
        Top.COMMAND = args
        return Top.COMMAND


class Reboot(Command):
    def __init__(self):
        super().__init__('systemctl', 'reboot')


class Poweroff(Command):
    def __init__(self):
        super().__init__('systemctl', 'poweroff')


class InstanceStatus(TaskList):
    def __init__(self, systemctl, journalctl):
        tasks = {
            'overview': systemctl('status'),
            'failed': systemctl('list-units', '--failed'),
            'timers': systemctl('list-timers', '--all'),
            'journal': journalctl('-b', '--lines=20'),
        }
        super().__init__(tasks)


class SystemStatus(InstanceStatus):
    def __init__(self):
        super().__init__(Systemctl.system, Journalctl.system)
        if DockerVersion.is_daemon_running():
            self.add('docker', DockerStatus())


class UserStatus(InstanceStatus):
    def __init__(self, systemctl=Systemctl.user, journalctl=Journalctl.user):
        super().__init__(systemctl, journalctl)

    @staticmethod
    def su(user):
        systemctl = lambda *args: Systemd.su(user, Systemctl.user(*args))
        journalctl = lambda *args: Systemd.su(user, Journalctl.user(*args))
        return UserStatus(systemctl, journalctl)


class UserStatusList(TaskList):
    def __init__(self):
        if running_as_root():
            # As root, we can query all the user instances.
            tasks = {user.name: UserStatus.su(user) for user in systemd_users()}
        else:
            # As a regular user, we can only query ourselves.
            tasks = {}
            user = get_current_user()
            if user_instance_active(user):
                tasks[user.name] = UserStatus()
        super().__init__(tasks)


class Status(TaskList):
    def __init__(self):
        tasks = {
            'hostname': Hostname(),
            'system': SystemStatus(),
            'user': UserStatusList(),
        }
        super().__init__(tasks)


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


def user_instance_active(user):
    # I'm pretty sure this is the way to determine if the user instance is
    # running?
    # Source: https://www.freedesktop.org/software/systemd/man/user@.service.html
    unit_name = f'user@{user.uid}.service'
    cmd = Systemctl.system('is-active', unit_name, '--quiet')
    try:
        cmd.now()
        return True
    except Exception:
        return False


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
        output = Loginctl('list-users', '--no-legend').now()
        lines = output.splitlines()
        if not lines:
            return
        for line in lines:
            # This assumes user names cannot contain spaces.
            # loginctl list-users output must be in the UID NAME format.
            info = line.lstrip().split(' ', 2)
            if len(info) < 2:
                raise RuntimeError(f'invalid `loginctl list-users` output:\n{output}')
            uid, user = info[0], info[1]
            yield User(uid, user)

    def show_users(users):
        user_args = [user.name for user in users]
        if not user_args:
            return None
        properties = 'UID', 'Name', 'RuntimePath'
        prop_args = (arg for prop in properties for arg in ('-p', prop))
        output = Loginctl('show-user', *prop_args, '--value', *user_args).now()
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
            return Status().complete()
        if self is Request.TOP:
            return Top().complete()
        if self is Request.REBOOT:
            return Reboot().complete()
        if self is Request.POWEROFF:
            return Poweroff().complete()
        raise NotImplementedError(f'unknown request: {self}')


def process_cgi_request():
    params = cgi.FieldStorage()
    what = params['what'].value
    Request(what).process().write_as_cgi_script()


def main():
    process_cgi_request()


if __name__ == '__main__':
    main()
