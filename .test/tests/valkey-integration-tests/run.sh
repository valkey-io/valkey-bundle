#!/usr/bin/env bash
set -euo pipefail

image="$1"

bundle_cname="valkey-bundle-test-$(date +%s)-$RANDOM"
bundle_cid="$(docker run -dt --user 1000 --name "$bundle_cname" "$image" valkey-server)"

cleanup_bundle() {
    docker logs "$bundle_cname" 2>&1 | tail -20 || true
    docker rm -vf "$bundle_cid" >/dev/null 2>&1 || true
}
trap cleanup_bundle EXIT

sleep 5

test_cname="valkey-test-runner-$(date +%s)-$RANDOM"
test_cid="$(docker run -dt --name "$test_cname" --link "$bundle_cname":valkey-bundle "$image" tail -f /dev/null)"

cleanup_test() {
    docker rm -vf "$test_cid" >/dev/null 2>&1 || true
}
trap 'cleanup_bundle; cleanup_test' EXIT

if ! docker exec "$test_cname" valkey-cli -h valkey-bundle -p 6379 ping >/dev/null 2>&1; then
    echo "Test container cannot connect to bundle"
    exit 1
fi
echo "Test container connected to bundle"

if docker exec "$test_cname" cat /etc/os-release | grep -q "Alpine"; then
    VARIANT="alpine"
else
    VARIANT="debian" 
fi

run_test_against_bundle() {
    local section_name="$1"
    local test_commands="$2"
    
    echo "=== $section_name ==="
    local start_time=$(date +%s)
    
    local modified_commands=$(cat <<EOF
set -e

$test_commands
EOF )
    if docker exec "$test_cname" bash -c "$modified_commands"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        echo "$section_name passed successfully in ${duration}s"
        return 0
    else
        echo "$section_name tests failed"
        return 1
    fi
}

run_test_against_bundle "Valkey Core Tests" "
cd /opt/valkey
echo 'Running Valkey core tests'
make test
"

run_test_against_bundle "JSON Module Tests" "
cd /opt/valkey-json
echo 'Running JSON tests'
./build.sh --unit
"

if [ "$VARIANT" = "debian" ]; then
    run_test_against_bundle "Bloom Module Tests" "
    cd /opt/valkey-bloom
    echo 'Running Bloom tests'
    cargo test --release --verbose --features enable-system-alloc -- --test-threads=1 
    "
else
    echo "Skipping Bloom tests on Alpine variant (known compatibility issues)"
fi

run_test_against_bundle "Search Module Tests" "
cd /opt/valkey-search
echo 'Running Search tests'
./build.sh --run-tests 
"

if [ "$VARIANT" = "debian" ]; then
    run_test_against_bundle "LDAP Module Tests" "
    cd /opt/valkey-ldap
    echo 'Running LDAP tests'
    cargo test --release --verbose --features enable-system-alloc -- --test-threads=1
    "
else
    echo "Skipping LDAP tests on Alpine variant (known compatibility issues)"
fi

echo 'All tests passed successfully'