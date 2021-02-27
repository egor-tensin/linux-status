#!/usr/bin/env python3

import cgi, cgitb
from collections import namedtuple
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


def headers():
    print("Content-Type: text/html; charset=utf-8")
    print()


def debugging():
    # TODO: figure out how to include this on the web page
    #cgitb.enable()
    pass


def setup():
    headers()
    debugging()


def format_response(response):
    return json.dumps(response, ensure_ascii=False)


def run(*args, **kwargs):
    output = subprocess.run(args, stdin=DEVNULL, stdout=PIPE, stderr=STDOUT, universal_newlines=True, **kwargs)
    return output.stdout


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


User = namedtuple('User', ['uid', 'name'])
SystemdUser = namedtuple('SystemdUser', ['uid', 'name', 'runtime_dir'])


def running_as_root():
    # AFAIK, Python's http.server drops root privileges and executes the scripts as
    # user nobody.
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
        output = Loginctl('list-users', '--no-legend').run()
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
        output = Loginctl('show-user', *prop_args, '--value', *user_args).run()
        lines = output.splitlines()
        # Assuming that for muptiple users, the properties will be separated by
        # an empty string.
        groups = split_by(lines, '')
        for group in groups:
            if len(group) != len(properties):
                raise RuntimeError(f'invalid `loginctl show-user` output:\n{output}')
            yield SystemdUser(int(group[0]), group[1], group[2])

    return show_users(list_users())


def hostname():
    return socket.gethostname()


def top():
    return run('top', '-b', '-n', '1', '-w', '512')


def su(user, commands):
    return {k: Systemd.su(user, cmd) for k, cmd in commands.items()}


def run_all(commands):
    return {k: cmd.run() for k, cmd in commands.items()}


def status_system():
    return {
        'overview': Systemctl.system('status'),
        'failed': Systemctl.system('list-units', '--failed'),
        'timers': Systemctl.system('list-timers', '--all'),
    }


def status_user():
    return {
        'overview': Systemctl.user('status'),
        'failed': Systemctl.user('list-units', '--failed'),
        'timers': Systemctl.user('list-timers', '--all'),
    }


def timers_system():
    return {
        'timers': Systemctl.system('list-timers', '--all'),
    }


def timers_user():
    return {
        'timers': Systemctl.user('list-timers', '--all'),
    }


def system(commands):
    return run_all(commands())


def user(commands):
    if running_as_root():
        return {user.name: run_all(su(user, commands())) for user in systemd_users()}
    else:
        return {get_current_user().name: run_all(commands())}


def status():
    status = {
        'hostname': hostname(),
        'top': top(),
        'system': system(status_system),
        'user': user(status_user),
    }
    return status


def timers():
    timers = {
        'system': system(timers_system),
        'user': user(timers_user),
    }
    return timers


def do():
    params = cgi.FieldStorage()
    what = params['what'].value
    if what == 'status':
        response = status()
    elif what == 'timers':
        response = timers()
    elif what == 'top':
        response = top()
    else:
        raise RuntimeError(f'invalid parameter "what": {what}')
    print(format_response(response))


def main():
    setup()
    do()


if __name__ == '__main__':
    main()
