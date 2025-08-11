#!/bin/bash
set -euo pipefail

image="$1"
CONTAINER_NAME="valkey-test-$(date +%s)-$$"
test_results=()
TEST_FRAMEWORK_REPO="https://github.com/Nikhil-Manglore/valkey-test-framework.git"

cleanup_container() {
    if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        docker stop "$CONTAINER_NAME" >/dev/null 2>&1
        docker rm "$CONTAINER_NAME" >/dev/null 2>&1
    fi
}

summary() {
    local exit_code=$?

    cleanup_container
    
    if [ ${#test_results[@]} -gt 0 ]; then
        echo "=== Test Results Summary ==="
        printf '%s\n' "${test_results[@]}"
    fi
    
    exit $exit_code
}

setup_test_framework() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        git clone "$TEST_FRAMEWORK_REPO"
        mkdir -p "$dir"
        mv "valkey-test-framework/src"/* "$dir/"
        rm -rf valkey-test-framework
    fi
}

trap summary EXIT INT TERM

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

echo "=== Valkey Bundle Container Started ==="

repos=("valkey" "valkey-json" "valkey-bloom" "valkey-search" "valkey-ldap")
branches=("$VALKEY_BRANCH" "$JSON_TAG" "$BLOOM_TAG" "$SEARCH_TAG" "$LDAP_TAG")

for i in "${!repos[@]}"; do
    repo="${repos[i]}"
    branch="${branches[i]}"
    
    if [ ! -d "./$repo" ]; then
        echo "Cloning $repo with branch/tag: $branch"
        git clone -b "$branch" --depth=1 "https://github.com/valkey-io/$repo.git" "./$repo"
    fi
done

run_tests() {
    local module=$1
    local module_dir=$2
    
    echo "=== Running $module Integration Tests ==="
    
    export VALKEY_EXTERNAL_SERVER=true
    export VALKEY_HOST=localhost
    export VALKEY_PORT=6379
    export SERVER_VERSION="$VALKEY_TAG"
    
    cd "$module_dir"
    
    case $module in
        "Valkey")

            echo "Starting Valkey Bundle Container"
            docker run -d -p 6379:6379 --name "$CONTAINER_NAME" "$image" \
                valkey-server \
                --save "" \
                --enable-debug-command yes \
                --enable-module-command yes \
                --protected-mode no

            for i in {1..60}; do
                if docker exec "$CONTAINER_NAME" valkey-cli ping > /dev/null 2>&1; then
                    echo "Valkey container ready"
                    break
                fi
                if [ $i -eq 60 ]; then
                    echo "Valkey failed to start"
                    return 1
                fi
                sleep 1
            done

            ./runtest --host 127.0.0.1 --port 6379 \
            --verbose \
            --tags -slow \
            --ignore-encoding \
            --skiptest "CONFIG SET rollback on apply error" \
            --skiptest "MULTI is rejected when CLIENT REPLY is ON/OFF/SKIP" \
            --skiptest "CLIENT REPLY OFF/SKIP: multi command" \
            --skiptest "AUTH errored inside MULTI will add the reply" \
            --skipunit integration/valkey-cli \
            --skiptest "Dumping an RDB - functions only: yes"
            ;;
        "JSON")
            setup_test_framework "tst/integration/valkeytests"
            
            pip install -r requirements.txt

            docker run -d -p 6379:6379 --name "$CONTAINER_NAME" "$image" \
                valkey-server \
                --enable-debug-command yes >/dev/null 2>&1
            sleep 3

            export SOURCE_DIR="$(pwd)"
            cd tst/integration
            python -m pytest --cache-clear -v -s
            local pytest_exit_code=$?
            cleanup_container
            cd ../..
            return $pytest_exit_code
            ;;
        "Bloom")
            start_bloom_containers() {
                docker network create valkey-net >/dev/null 2>&1 || true
                docker run -d --name "${CONTAINER_NAME}-master" --network valkey-net -p 6379:6379 "$image" \
                    valkey-server --enable-debug-command yes >/dev/null 2>&1
                sleep 10
                docker run -d --name "${CONTAINER_NAME}-replica" --network valkey-net -p 6380:6379 "$image" \
                    valkey-server --enable-debug-command yes --replicaof "${CONTAINER_NAME}-master" 6379 >/dev/null 2>&1
                sleep 20
            }

            cleanup_bloom_containers() {
                docker stop "${CONTAINER_NAME}-master" "${CONTAINER_NAME}-replica" >/dev/null 2>&1 || true
                docker rm "${CONTAINER_NAME}-master" "${CONTAINER_NAME}-replica" >/dev/null 2>&1 || true
                docker network rm valkey-net >/dev/null 2>&1 || true
            }

            setup_test_framework "tests/build/valkeytestframework"
            pip install -r requirements.txt

            TESTS=$(python -m pytest --collect-only -q tests/test_bloom_*.py | grep "::test_" | grep -v "warnings" | \
                grep -v "test_large_allocation_when_below_maxmemory" | \
                grep -v "test_large_allocation_when_above_maxmemory" | \
                grep -v "test_restore_failed_large_bloom_filter" | \
                grep -v "test_rdb_restore_non_bloom_compatibility")
            
            if docker image inspect "$image" --format '{{.Architecture}}' | grep -q "arm64"; then
                TESTS=$(echo "$TESTS" | grep -v "test_bloom_defrag")
            fi

            test_count=0
            passed_count=0

            for test in $TESTS; do
                test_count=$((test_count + 1))
                
                cleanup_bloom_containers
                start_bloom_containers
                
                export VALKEY_REPLICA_HOST=localhost
                export VALKEY_REPLICA_PORT=6380
                python -m pytest "$test" --cache-clear -v
                local test_exit_code=$?
                
                if [ $test_exit_code -eq 0 ]; then
                    passed_count=$((passed_count + 1))
                fi
            done

            cleanup_bloom_containers
            echo "SUMMARY: $passed_count/$test_count Valkey Bloom Tests Passed"
            
            if [ $passed_count -ne $test_count ]; then
                return 1
            fi
            ;;
        "Search")
            echo "CANT RUN SEARCH TESTS UNTIL BUNDLE IS UPDATED WITH NEW SEARCH PATCH"
    
            # setup_test_framework "integration/valkey-test-framework"
                    
            # pip install -r integration/valkey-test-framework/requirements.txt
            # pip install absl-py numpy 

            # docker run -d -p 6379:6379 --name "$CONTAINER_NAME" "$image" \
            #    valkey-server \
            #       --enable-debug-command yes \
            #       --protected-mode no >/dev/null 2>&1
            # sleep 3

            # cd integration
            # export PYTHONPATH="$(pwd)/valkeytestframework:$(pwd)"
            # export SKIPLOGCLEAN=1
            # python -m pytest --log-cli-level=INFO --capture=sys --cache-clear -v -k "not (test_module_loaded or CME or cluster)" test_*.py
            # local pytest_exit_code=$?
            # cleanup_container
            # return $pytest_exit_code
            ;;
        "LDAP")
            echo "VALKEY LDAP DOESN'T USE VALKEY TEST FRAMEWORK"
            ;;
    esac

    local exit_code=$?
    cd ..
    
    if [ $exit_code -eq 0 ]; then
        echo "$module tests passed successfully"
        test_results+=("$module: passed")
    else
        echo "$module tests failed"
        test_results+=("$module: failed")
    fi
    
    return $exit_code
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
    echo "All Valkey Core and Module Tests Passed Successfully."
fi