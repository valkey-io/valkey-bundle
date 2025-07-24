#!/bin/bash
set -euo pipefail

image="$1"
container_name="valkey-test-$(date +%s)-$$"
test_results=()

cleanup() {
    local exit_code=$?
    if docker ps -q -f name="$container_name" | grep -q .; then
        docker stop "$container_name" >/dev/null 2>&1 || true
        docker rm "$container_name" >/dev/null 2>&1 || true
    fi
    
    if [ ${#test_results[@]} -gt 0 ]; then
        echo "=== Test Results Summary ==="
        printf '%s\n' "${test_results[@]}"
    fi
    
    exit $exit_code
}

trap cleanup EXIT INT TERM

docker run -d -p 6379:6379 --name "$container_name" "$image" valkey-server --enable-debug-command yes

for i in {1..60}; do
    if docker exec "$container_name" valkey-cli ping > /dev/null 2>&1; then
        break
    fi
    if [ $i -eq 60 ]; then
        echo "Valkey failed to start"
        exit 1
    fi
    sleep 1
done

for repo in "valkey" "valkey-json" "valkey-bloom" "valkey-search" "valkey-ldap"; do
    if [ ! -d "./$repo" ]; then
        if [ "$repo" = "valkey-search" ] || [ "$repo" = "valkey-ldap" ]; then
            git clone -b main --depth=1 "https://github.com/valkey-io/$repo.git" "./$repo"
        else
            git clone -b unstable --depth=1 "https://github.com/valkey-io/$repo.git" "./$repo"
        fi
    fi
done

run_tests() {
    local module=$1
    local module_dir=$2
    
    echo "=== Running $module Integration Tests ==="
    
    export SERVER_VERSION="unstable"
    export VALKEY_HOST="localhost"
    export VALKEY_PORT="6379"
    
    cd "$module_dir"
    
    case $module in
        "Valkey")
            make test
            ;;
        "JSON")
            ./build.sh --unit
            ./build.sh --integration
            ;;
        "Bloom")
            cargo test --release --verbose --features enable-system-alloc -- --test-threads=1
            ;;
        "Search")       
            ./build.sh --run-tests
            ;;
        "LDAP")
            cargo test --release --features enable-system-alloc -- --test-threads=1
            ;;
    esac

    local exit_code=$?
    cd ..
    
    if [ $exit_code -eq 0 ]; then
        echo "$module tests passed successfully"
        test_results+=("$module: passed")
        return 0
    else
        echo "$module tests failed"
        test_results+=("$module: failed")
        return 1
    fi
}

overall_success=true

run_tests "Valkey" "./valkey" || overall_success=false
run_tests "JSON" "./valkey-json" || overall_success=false
run_tests "Bloom" "./valkey-bloom" || overall_success=false
run_tests "Search" "./valkey-search" || overall_success=false
run_tests "LDAP" "./valkey-ldap" || overall_success=false

echo "=== Integration Tests Complete ==="
if [ "$overall_success" = false ]; then
    echo "Some tests failed, check the logs to see the exact test that failed."
    exit 1
else
    echo "All core + module tests passed."
fi