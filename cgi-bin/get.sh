#!/usr/bin/env bash

set -o errexit -o nounset -o pipefail

script_dir="$( dirname -- "${BASH_SOURCE[0]}" )"
script_dir="$( cd -- "$script_dir" && pwd )"
readonly script_dir

# Python's http.server runs CGI scripts under user nobody.
# This is not what we want unfortunately.
# The best solution I could find so far is to create an entry in
# /etc/sudoers.d, allowing the nobody user to run the real scripts w/ sudo.
if [ "$( id --user --name )" == nobody ]; then
    sudo --non-interactive --preserve-env "$script_dir/get.py"
else
    "$script_dir/get.py"
fi
