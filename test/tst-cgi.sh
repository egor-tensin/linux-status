test_cgi_response=

_test_cgi_check_status() {
    local expected='200 OK'
    local actual
    actual="$( head -n 1 -- "$test_cgi_response" )"

    [ "$expected" == "$actual" ] && return 0

    fail "Unexpected HTTP status: $actual"
    fail_details "Expected: $expected"

    diff <( echo "$actual" ) <( echo "$expected" ) | cat -te >&2
    return 1
}

_test_cgi() {
    if [ "$#" -lt 1 ]; then
        log "usage: ${FUNCNAME[0]} WHAT [KEYWORD...]"
        return 1
    fi

    local what="$1"
    shift

    local query_string="what=$what"
    log "Running CGI test for query string: $query_string"

    QUERY_STRING="$query_string" "$script_dir/../src/app.py" > "$test_cgi_response"

    _test_cgi_check_status
    test_check_output "$test_cgi_response" "$@"
}

test_run() {
    # Check that app.py still works as a CGI script.

    test_setup

    test_cgi_response="$test_root_dir/response"

    # /status returns a JSON with a number of fields:
    _test_cgi 'status' '"hostname":' '"thermal":' '"system":' '"user":'
    # /top is `top` output:
    _test_cgi 'top' 'load average:'
    # /thermal is also an endpoint:
    _test_cgi 'thermal'
}
