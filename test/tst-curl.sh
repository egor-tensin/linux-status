test_curl_header=
test_curl_output=

_curl() {
    if [ "$#" -ne 1 ]; then
        log "usage: ${FUNCNAME[0]} URL"
        return 1
    fi

    local url="$1"

    curl \
        --silent --show-error \
        --dump-header "$test_curl_header" \
        --output "$test_curl_output" \
        --connect-timeout 3 \
        -- \
        "http://127.0.0.1:$test_server_port$url" \
        || true
}

_test_curl_check_status() {
    if [ "$#" -ne 1 ]; then
        log "usage: ${FUNCNAME[0]} HTTP_STATUS"
        return 1
    fi

    local expected="$1"
    expected="HTTP/1.0 $expected"$'\r'
    local actual
    actual="$( head -n 1 -- "$test_curl_header" )"

    [ "$expected" == "$actual" ] && return 0

    fail "Unexpected HTTP status: $actual"
    fail_details "Expected: $expected"

    log 'Response headers:'
    cat -- "$test_curl_header" >&2
    log 'Response data:'
    cat -- "$test_curl_output" >&2
    return 1
}

_test_curl() {
    if [ "$#" -lt 1 ]; then
        log "usage: ${FUNCNAME[0]} URL [KEYWORD...]"
        return 1
    fi

    local url="$1"
    shift
    log "Running test for URL: $url"

    _curl "$url"
    _test_curl_check_status '200 OK'
    test_check_output "$test_curl_output" "$@"
}

test_run() {
    test_setup

    test_curl_header="$test_root_dir/header"
    test_curl_output="$test_root_dir/output"

    # / and /index.html are identical:
    _test_curl '/' \
        '<link rel="stylesheet" href="css/bootstrap.min.css">' \
        'var status_refresh_interval_seconds'
    _test_curl '/index.html' \
        '<link rel="stylesheet" href="css/bootstrap.min.css">' \
        'var status_refresh_interval_seconds'

    # /status returns a JSON with a number of fields:
    _test_curl '/status' '"hostname":' '"thermal":' '"system":' '"user":'
    # /top is `top` output:
    _test_curl '/top' 'load average:'
    # /thermal is also an endpoint:
    _test_curl '/thermal'
}
