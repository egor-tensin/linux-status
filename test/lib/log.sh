# Copyright (c) 2026 Egor Tensin <egor@tensin.name>
# This file is part of the "linux-status" project.
# For details, see https://github.com/egor-tensin/linux-status
# Distributed under the MIT License.

log() {
    local msg
    for msg; do
        echo -e "$test_file | $msg" >&2
    done
}

log_run() {
    if [ "$#" -lt 1 ]; then
        log "usage: ${FUNCNAME[0]} ARGV0 [ARG...]"
        return 1
    fi

    local msg='Running:'
    msg="$msg$( printf -- ' %q' "$@" )"
    log "$msg"
}

fail() {
    local msg
    for msg; do
        log "FAIL: $msg"
    done
}

fail_details() {
    local msg
    for msg; do
        fail "    $msg"
    done
}

log_numof_tests_ok=0
log_numof_tests_failed=0
declare -a log_tests_failed=()
declare -A log_tests_should_fail=()

log_test_start() {
    if [ "$#" -ne 1 ]; then
        echo "usage: ${FUNCNAME[0]} TEST_FILE" >&2
        return 1
    fi

    local test_file="$1"

    if [ -n "${test_should_fail:-}" ]; then
        log_tests_should_fail["$test_file"]=1
    fi

    cat <<EOF >&2

======================================================================
TEST: $test_file
======================================================================
EOF

    log "Should fail: ${test_should_fail:-No}"
}

log_test_ok() {
    if [ "$#" -ne 1 ]; then
        echo "usage: ${FUNCNAME[0]} TEST_FILE" >&2
        return 1
    fi

    log_numof_tests_ok=$((log_numof_tests_ok + 1))

    cat <<EOF >&2
----------------------------------------------------------------------
OK: $1
----------------------------------------------------------------------
EOF
}

log_test_fail() {
    if [ "$#" -ne 1 ]; then
        echo "usage: ${FUNCNAME[0]} TEST_FILE" >&2
        return 1
    fi

    log_numof_tests_failed=$((log_numof_tests_failed + 1))
    log_tests_failed+=("$1")

    cat <<EOF >&2
----------------------------------------------------------------------
FAIL: $1
----------------------------------------------------------------------
EOF
}

log_test_finish() {
    if [ "$#" -ne 2 ]; then
        echo "usage: ${FUNCNAME[0]} TEST_FILE EXIT_CODE" >&2
        return 1
    fi

    local test_file="$1"
    local ret="$2"
    local test_should_fail
    test_should_fail="${log_tests_should_fail["$test_file"]:+x}"

    if [ "$ret" -eq 0 ] || [ -n "$test_should_fail" ]; then
        log_test_ok "$test_file"
    else
        log_test_fail "$test_file"
    fi
}

log_tests_summary() {
    cat <<EOF >&2

======================================================================
SUMMARY
======================================================================
OK:   $log_numof_tests_ok
FAIL: $log_numof_tests_failed
EOF

    local test_file
    for test_file in ${log_tests_failed[@]+"${log_tests_failed[@]}"}; do
        cat <<EOF >&2
FAIL: $test_file
EOF
    done

    cat <<EOF >&2
----------------------------------------------------------------------
EOF

    local ret=0
    [ "$log_numof_tests_failed" -gt 0 ] && ret=1

    return "$ret"
}
