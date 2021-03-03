#!/usr/bin/env python3

# Copyright (c) 2021 Egor Tensin <Egor.Tensin@gmail.com>
# This file is part of the "linux-status" project.
# For details, see https://github.com/egor-tensin/linux-status.
# Distributed under the MIT License.

import http.server

from app import Request


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


def main():
    addr = ('', 18101)
    httpd = http.server.ThreadingHTTPServer(addr, RequestHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nKeyboard interrupt received, exiting...')


if __name__ == '__main__':
    main()
