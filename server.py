#!/usr/bin/env python3

# Copyright (c) 2021 Egor Tensin <Egor.Tensin@gmail.com>
# This file is part of the "linux-status" project.
# For details, see https://github.com/egor-tensin/linux-status.
# Distributed under the MIT License.

# This script launches a HTTP server and uses app.py for processing a set of
# custom URLs.  See that file for the reasons behind this.

import argparse
import http.server
import os
import sys

from app import Request


DEFAULT_PORT = 18101


def script_dir():
    return os.path.dirname(os.path.realpath(__file__))


class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            request = Request.from_http_path(self.path)
        except ValueError:
            return super().do_GET()
        try:
            response = request.process()
        except:
            self.send_response(http.server.HTTPStatus.INTERNAL_SERVER_ERROR)
            self.end_headers()
            return
        response.write_as_request_handler(self)


def parse_args(args=None):
    if args is None:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', metavar='PORT',
                        type=int, default=DEFAULT_PORT,
                        help='set port number')
    return parser.parse_args(args)


def main(args=None):
    # It's a failsafe; this script is only allowed to serve the directory it
    # resides in.
    os.chdir(script_dir())
    args = parse_args(args)
    addr = ('', args.port)
    httpd = http.server.ThreadingHTTPServer(addr, RequestHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nKeyboard interrupt received, exiting...')


if __name__ == '__main__':
    main()
