linux-status
============

Simple Linux status web pages.

Shows your `top`, systemd units & timers, allows you to reboot, etc.

What it looks like
------------------

![Example page][example]

[example]: img/example.png "Example page"

Usage
-----

To start a web server on port 18101:

    > python3 -m http.server --cgi 18101

There's also a [systemd unit] that you can adjust to run the server.

[systemd unit]: systemd/linux-status.service

TODO
----

* Show an error if a AJAX call fails.
* Dedupe scripts in cgi-bin.

License
-------
Distributed under the MIT License.
See [LICENSE.txt] for details.

[LICENSE.txt]: LICENSE.txt
