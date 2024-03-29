#!/usr/bin/env python3

# Copyright (c) 2021 Egor Tensin <egor@tensin.name>
# This file is part of the "linux-status" project.
# For details, see https://github.com/egor-tensin/linux-status.
# Distributed under the MIT License.

# This script launches a HTTP server and uses app.py for processing a set of
# custom URLs.  See that file for the reasons behind this.

import argparse
from http import HTTPStatus
import http.server
import os
import sys
import traceback

from app import Request, Response


DEFAULT_PORT = 18101


def script_dir():
    return os.path.dirname(os.path.realpath(__file__))


def default_html_dir():
    return os.path.join(script_dir(), 'html')


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    ARGS = None

    def address_string(self):
        if 'x-forwarded-for' in self.headers:
            return self.headers['x-forwarded-for'].split(',')[0].strip()
        if 'x-real-ip' in self.headers:
            return self.headers['x-real-ip']
        return super().address_string()

    def do_GET(self):
        try:
            request = Request.from_http_path(self.path)
            request.disable_power = RequestHandler.ARGS.disable_power
        except ValueError:
            return super().do_GET()
        try:
            response = request.process()
            response.write_to_request_handler(self)
        except:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
            response = Response(traceback.format_exc(), status)
            response.write_to_request_handler(self)
            return


def make_server(port):
    addr = ('', port)
    server = http.server.HTTPServer
    if sys.version_info >= (3, 7):
        server = http.server.ThreadingHTTPServer
    return server(addr, RequestHandler)


def parse_args(args=None):
    if args is None:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', metavar='PORT',
                        type=int, default=DEFAULT_PORT,
                        help='set port number')
    parser.add_argument('-n', '--disable-power', action='store_true',
                        help='disable reboot/poweroff requests')
    parser.add_argument('-d', '--dir', metavar='DIR',
                        default=default_html_dir(),
                        help='HTML directory path')
    return parser.parse_args(args)


def main(args=None):
    args = parse_args(args)
    RequestHandler.ARGS = args

    # It's a failsafe; the script is not allowed to serve a random current
    # working directory.
    os.chdir(args.dir)

    httpd = make_server(args.port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nKeyboard interrupt received, exiting...')


if __name__ == '__main__':
    main()
