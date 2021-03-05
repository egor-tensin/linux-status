linux-status
============

[![Test](https://github.com/egor-tensin/linux-status/actions/workflows/test.yml/badge.svg)](https://github.com/egor-tensin/linux-status/actions/workflows/test.yml)

Simple Linux status web pages.

Shows your `top`, systemd units & timers, allows you to reboot, etc.

What it looks like
------------------

![Example page][example]

[example]: img/example.png "Example page"

Usage
-----

To start a web server on port 18101:

    > python3 server.py

There's also a [systemd unit] that you can adjust to run the server.

[systemd unit]: dist/systemd/linux-status.service

TODO
----

* Show an error if a AJAX call fails.

License
-------
Distributed under the MIT License.
See [LICENSE.txt] for details.

[LICENSE.txt]: LICENSE.txt
