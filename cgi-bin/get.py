#!/usr/bin/env python3

import cgi, cgitb
import json
import os
import socket
import subprocess
from subprocess import PIPE, STDOUT


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
    output = subprocess.run(args, stdout=PIPE, stderr=STDOUT, universal_newlines=True, **kwargs)
    return output.stdout


def hostname():
    return socket.gethostname()


def top():
    return run('top', '-b', '-n', '1', '-w', '512')


systemd_env = os.environ.copy()
systemd_env['SYSTEMD_PAGER'] = ''
systemd_env['SYSTEMD_COLORS'] = 'no'


def run_systemd_command(*args):
    return run(*args, env=systemd_env)


def run_systemctl(*args):
    return run_systemd_command('systemctl', *args)


def system_status_overview():
    return run_systemctl('--system', 'status', '--full')


def system_status_failed():
    return run_systemctl('--system', 'list-units', '--failed', '--full')


def user_status_overview():
    return run_systemctl('--user', 'status', '--full')


def user_status_failed():
    return run_systemctl('--user', 'list-units', '--failed', '--full')


def system_timers():
    return run_systemctl('--system', 'list-timers', '--all', '--full')


def user_timers():
    return run_systemctl('--user', 'list-timers', '--all', '--full')


def status():
    status = {
        'hostname': hostname(),
        'top': top(),
        'system': {
            'overview': system_status_overview(),
            'failed': system_status_failed(),
            'timers': system_timers(),
        },
        'user': {
            'overview': user_status_overview(),
            'failed': user_status_failed(),
            'timers': user_timers(),
        },
    }
    return status


def timers():
    timers = {
        'system': {
            'timers': system_timers(),
        },
        'user': {
            'timers': user_timers(),
        },
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
