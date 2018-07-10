#!/usr/bin/env bash

set -o errexit -o nounset -o pipefail

echo 'Content-Type: text/plain; charset=utf-8'
echo

SYSTEMD_COLORS=no systemctl list-units --failed --no-pager --full
