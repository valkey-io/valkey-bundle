#!/usr/bin/env bash
set -eo pipefail

dir="$(dirname "$(readlink -f "$BASH_SOURCE")")"

image="$1"

network="valkey-network-$RANDOM-$RANDOM"
docker network create "$network" >/dev/null

cname="valkey-container-$RANDOM-$RANDOM"
cid="$(docker run -d --name "$cname" --network "$network" "$image")"

trap "docker rm -vf '$cid' >/dev/null; docker network rm '$network' >/dev/null" EXIT

valkey-cli() {
  docker run --rm -i \
    --network "$network" \
    --entrypoint valkey-cli \
    "$image" \
    -h "$cname" \
    "$@"
}

. "$dir/../../retry.sh" --tries 20 '[ "$(valkey-cli ping)" = "PONG" ]'

# Test basic persistence
[ "$(valkey-cli set mykey somevalue)" = "OK" ]
[ "$(valkey-cli get mykey)" = "somevalue" ]

# Test JSON module data
echo "Testing JSON..."
[ "$(valkey-cli JSON.SET user:1 '$' '{"name":"Alice"}')" = "OK" ]
[ "$(valkey-cli JSON.GET user:1)" = '{"name":"Alice"}' ]

# Test Bloom filter data
echo "Testing Bloom..."
[ "$(valkey-cli BF.RESERVE emails 0.01 1000)" = "OK" ]
[ "$(valkey-cli BF.ADD emails alice@example.com)" = "1" ]
[ "$(valkey-cli BF.ADD emails bob@example.com)" = "1" ]
[ "$(valkey-cli BF.EXISTS emails alice@example.com)" = "1" ]

# # Test Search module
echo "Testing Search Pending..." 
# [ "$(valkey-cli HSET doc:1 title 'Hello World')" = "1" ]
# [ "$(valkey-cli FT.CREATE idx ON HASH SCHEMA title TEXT)" = "OK" ]

# Restart container
docker stop "$cname" >/dev/null
docker start "$cname" >/dev/null

. "$dir/../../retry.sh" --tries 20 '[ "$(valkey-cli ping)" = "PONG" ]'

# Verify basic data persisted
[ "$(valkey-cli get mykey)" = "somevalue" ]

# Verify JSON data persisted
echo "Testing JSON..."
[ "$(valkey-cli JSON.GET user:1)" = '{"name":"Alice"}' ]

# Verify Bloom filter data persisted
echo "Testing Bloom..."
[ "$(valkey-cli BF.EXISTS emails alice@example.com)" = "1" ]
[ "$(valkey-cli BF.EXISTS emails bob@example.com)" = "1" ]
[ "$(valkey-cli BF.EXISTS emails nonexistent@example.com)" = "0" ]

# Verify hash data persisted (search index will rebuild automatically)
echo "Testing Search Pending..."
# [ "$(valkey-cli HGET doc:1 title)" = "Test Document" ]

echo "All persistence tests passed!"