#!/usr/bin/env bash

# Copyright (c) 2021 Egor Tensin <egor@tensin.name>
# This file is part of the "linux-status" project.
# For details, see https://github.com/egor-tensin/linux-status.
# Distributed under the MIT License.

set -o errexit -o nounset -o pipefail
shopt -s inherit_errexit lastpipe

script_dir="$( dirname -- "${BASH_SOURCE[0]}" )"
script_dir="$( cd -- "$script_dir" && pwd )"
readonly script_dir
script_name="$( basename -- "${BASH_SOURCE[0]}" )"
readonly script_name

readonly server_port=18101
server_pid=
curl_header_file=
curl_output_file=

dump() {
    local msg
    for msg; do
        echo "$script_name: $msg"
    done
}

run_server() {
    dump "Starting up server..."
    "$script_dir/../src/server.py" --port "$server_port" &
    server_pid="$!"
    dump "Its PID is $server_pid"
    sleep 5
}

kill_server() {
    [ -z "$server_pid" ] && return
    dump "Killing server with PID $server_pid..."
    kill "$server_pid"
    dump "Waiting for it to terminate..."
    wait "$server_pid" || true
    dump "Done"
}

create_files() {
    curl_header_file="$( mktemp )"
    curl_output_file="$( mktemp )"
    dump "curl header file: $curl_header_file"
    dump "curl output file: $curl_output_file"
}

cleanup_files() {
    dump "Cleaning up curl files..."
    [ -n "$curl_header_file" ] && rm -f -- "$curl_header_file"
    [ -n "$curl_output_file" ] && rm -f -- "$curl_output_file"
}

prepare() {
    run_server
    create_files
}

cleanup() {
    kill_server || true
    cleanup_files || true
}

run_curl() {
    if [ "$#" -ne 1 ]; then
        echo "usage: ${FUNCNAME[0]} URL" >&2
        return 1
    fi
    local url="$1"
    curl \
        --silent --show-error \
        --dump-header "$curl_header_file" \
        --output "$curl_output_file" \
        --connect-timeout 3 \
        -- "http://localhost:$server_port$url" || true
}

curl_check_status() {
    if [ "$#" -ne 1 ]; then
        echo "usage: ${FUNCNAME[0]} HTTP_STATUS" >&2
        return 1
    fi

    local expected="$1"
    expected="HTTP/1.0 $expected"$'\r'
    local actual
    actual="$( head -n 1 -- "$curl_header_file" )"

    [ "$expected" == "$actual" ] && return 0

    dump "Actual HTTP response: $actual" >&2
    dump "Expected:             $expected" >&2

    dump 'HTTP headers:' >&2
    cat -- "$curl_header_file" >&2
    dump 'HTTP response:' >&2
    cat -- "$curl_output_file" >&2
    return 1
}

curl_check_keyword() {
    local keyword
    for keyword; do
        if ! grep --fixed-strings --quiet -- "$keyword" "$curl_output_file"; then
            dump "The following pattern hasn't been found:"
            dump "$keyword"
            dump "The output was:"
            cat -- "$curl_output_file"
            return 1
        fi
    done
}

run_curl_test() {
    if [ "$#" -lt 1 ]; then
        echo "usage: ${FUNCNAME[0]} URL [KEYWORD...]" >&2
        return 1
    fi

    local url="$1"
    shift
    dump "Running test for URL: $url"

    run_curl "$url"
    curl_check_status '200 OK'

    local keyword
    for keyword; do
        curl_check_keyword "$keyword"
    done
}

run_curl_tests() {
    # / and /index.html are identical:
    run_curl_test '/'           '<link rel="stylesheet" href="css/bootstrap.min.css">' 'var status_refresh_interval_seconds'
    run_curl_test '/index.html' '<link rel="stylesheet" href="css/bootstrap.min.css">' 'var status_refresh_interval_seconds'

    # /status returns a JSON with a number of fields:
    run_curl_test '/status' '"hostname":' '"thermal":' '"system":' '"user":'
    # /top is `top` output:
    run_curl_test '/top' 'load average:'
    # /thermal is also an endpoint:
    run_curl_test '/thermal'
}

cgi_check_header() {
    local expected='200 OK'
    local actual
    actual="$( head -n 1 -- "$curl_output_file" )"

    [ "$expected" == "$actual" ] && return 0

    dump "Actual CGI header: $actual" >&2
    dump "Expected:          $expected" >&2

    diff <( echo "$actual" ) <( echo "$expected" ) | cat -te
    return 1
}

run_cgi_test() {
    if [ "$#" -lt 1 ]; then
        echo "usage: ${FUNCNAME[0]} WHAT [KEYWORD...]" >&2
        return 1
    fi

    local what="$1"
    shift

    local query_string="what=$what"
    dump "Running CGI test for query string: $query_string"

    QUERY_STRING="$query_string" "$script_dir/../src/app.py" > "$curl_output_file"

    cgi_check_header

    local keyword
    for keyword; do
        curl_check_keyword "$keyword"
    done
}

run_cgi_tests() {
    # Check that app.py still works as a CGI script.

    # /status returns a JSON with a number of fields:
    run_cgi_test 'status' '"hostname":' '"thermal":' '"system":' '"user":'
    # /top is `top` output:
    run_cgi_test 'top' 'load average:'
    # /thermal is also an endpoint:
    run_cgi_test 'thermal'
}

main() {
    trap cleanup EXIT
    prepare
    run_curl_tests
    run_cgi_tests
}

main "$@"
