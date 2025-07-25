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

get_latest_versions() {
    
    LATEST_VERSION=$(jq -r 'keys | .[-1]' versions.json)
    
    VALKEY_SERVER_VERSION=$(jq -r ".\"$LATEST_VERSION\".\"valkey-server\".version" versions.json)
    JSON_TAG=$(jq -r ".\"$LATEST_VERSION\".modules.\"valkey-json\".version" versions.json)
    BLOOM_TAG=$(jq -r ".\"$LATEST_VERSION\".modules.\"valkey-bloom\".version" versions.json)
    SEARCH_TAG=$(jq -r ".\"$LATEST_VERSION\".modules.\"valkey-search\".version" versions.json)
    LDAP_TAG=$(jq -r ".\"$LATEST_VERSION\".modules.\"valkey-ldap\".version" versions.json)
    
    if [[ "$VALKEY_SERVER_VERSION" =~ ^([0-9]+\.[0-9]+) ]]; then
        VALKEY_BRANCH="${BASH_REMATCH[1]}"
        VALKEY_TAG="$VALKEY_SERVER_VERSION"
    fi
}

get_latest_versions

docker run -d -p 6379:6379 --name "$container_name" "$image" \
    valkey-server \
    --save "" \
    --enable-debug-command yes \
    --enable-module-command yes \
    --protected-mode no

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

repos=("valkey" "valkey-json" "valkey-bloom" "valkey-search" "valkey-ldap")
branches=("$VALKEY_BRANCH" "$JSON_TAG" "$BLOOM_TAG" "$SEARCH_TAG" "$LDAP_TAG")

for i in "${!repos[@]}"; do
    repo="${repos[i]}"
    branch="${branches[i]}"
    
    if [ ! -d "./$repo" ]; then
        echo "Cloning $repo with branch/tag: $branch"
        git clone -b "$branch" --depth=1 "https://github.com/valkey-io/$repo.git" "./$repo"
    else
        echo "$repo directory already exists, skipping clone"
    fi
done

run_tests() {
    local module=$1
    local module_dir=$2
    
    echo "=== Running $module Integration Tests ==="
    
    export SERVER_VERSION="$VALKEY_TAG"
    export VALKEY_HOST="localhost"
    export VALKEY_PORT="6379"
    
    cd "$module_dir"
    
    case $module in
        "Valkey")
            make -j$(nproc) || {
                make
            }
            
            # Create /data directory for CLI RDB dump tests
            sudo mkdir -p /data || echo "Could not create /data directory"
            sudo chmod 777 /data 2>/dev/null || echo "Could not set permissions on /data"
            
            ./runtest --host 127.0.0.1 --port 6379 \
            --verbose \
            --tags -slow \
            --ignore-encoding \
            --skipunit unit/introspection \
            --skipunit unit/multi \
            --skiptest "Dumping an RDB - functions only: yes"
            ;;
        "JSON")
            VALKEY_HOST=127.0.0.1 VALKEY_PORT=6379 ./build.sh --integration
            ;;
        "Bloom")
            VALKEY_HOST=127.0.0.1 VALKEY_PORT=6379 ./build.sh
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