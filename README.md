linux-status
============

Simple Linux status web pages.

Deployment
----------

Clone to /srv/linux-status and use [config-links]:

    > pwd
    /srv/linux-status

    > ~/workspace/personal/config-links/update.sh
    ...

or just copy linux-status.service from this repository to your $HOME:

    > pwd
    /srv/linux-status

    > mkdir -p ~/.config/systemd/user/
    > cp '%HOME%/.config/systemd/user/linux-status.service' ~/.config/systemd/user/

Enable & start the service:

    > loginctl enable-linger "$( whoami )"
    > systemctl --user enable linux-status
    > systemctl --user start linux-status

[config-links]: https://github.com/egor-tensin/config-links

License
-------
Distributed under the MIT License.
See [LICENSE.txt] for details.

[LICENSE.txt]: LICENSE.txt
