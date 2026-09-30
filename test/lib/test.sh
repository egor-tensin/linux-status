# Copyright (c) 2026 Egor Tensin <egor@tensin.name>
# This file is part of the "linux-status" project.
# For details, see https://github.com/egor-tensin/linux-status
# Distributed under the MIT License.

test_should_fail=
test_root_dir=

test_server_port=35605
test_server_pid=

_test_run_server() {
    log "Starting up server..."
    log_run "$script_dir/../src/server.py" --port "$test_server_port"
    "$script_dir/../src/server.py" --port "$test_server_port" >&2 &
    test_server_pid="$!"
    log "Server's PID: $test_server_pid"
    sleep 5
}

_test_kill_server() {
    if [ -n "$test_server_pid" ]; then
        log "Stopping server: $test_server_pid"
        kill "$test_server_pid"
        log "Waiting for it to terminate..."
        wait "$test_server_pid" || true
    fi
}

test_setup() {
    test_root_dir="$( mktemp -d )"
    _test_run_server
}

test_cleanup_default() {
    if [ -n "$test_root_dir" ]; then
        log "Removing test's root directory: $test_root_dir"
        rm -rf -- "$test_root_dir"
    fi
    _test_kill_server
}

test_check_output() {
    if [ "$#" -lt 1 ]; then
        log "usage: ${FUNCNAME[0]} PATH [KEYWORD...]"
        return 1
    fi

    local path="$1"
    shift

    local keyword
    for keyword; do
        if ! grep --fixed-strings --quiet -- "$keyword" "$path"; then
            fail "The following pattern hasn't been found in $path:"
            fail_details "$keyword"
            log "Output:"
            cat -- "$path" >&2
            return 1
        fi
    done
}
