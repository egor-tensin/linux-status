linux-status
============

[![CI](https://github.com/egor-tensin/linux-status/actions/workflows/ci.yml/badge.svg)](https://github.com/egor-tensin/linux-status/actions/workflows/ci.yml)
[![Packages (Debian)](https://github.com/egor-tensin/linux-status/actions/workflows/debian.yml/badge.svg)](https://github.com/egor-tensin/linux-status/actions/workflows/debian.yml)
[![Publish (Launchpad)](https://github.com/egor-tensin/linux-status/actions/workflows/ppa.yml/badge.svg)](https://github.com/egor-tensin/linux-status/actions/workflows/ppa.yml)

Simple Linux status web page.

Shows your `top`, systemd units & timers, allows you to reboot the server, etc.

---

![Example page][example]

[example]: img/example.png "Example page"

---

Installation
------------

* For Arch Linux, use the [AUR package].
* For Ubuntu, use the [PPA].

[AUR package]: https://aur.archlinux.org/packages/linux-status/
[PPA]: https://launchpad.net/~egor-tensin/+archive/ubuntu/linux-status

Control the app using the `linux-status` systemd unit.

Usage
-----

To manually start a web server on port 18101, run:

    > python3 server.py

TODO
----

* Show an error if a AJAX call fails.

License
-------
Distributed under the MIT License.
See [LICENSE.txt] for details.

[LICENSE.txt]: LICENSE.txt
