#!/usr/bin/env bash
set -eo pipefail

dir="$(dirname "$(readlink -f "$BASH_SOURCE")")"
testDir="$(readlink -f "$(dirname "$BASH_SOURCE")")"
testName="$(basename "$testDir")"

image="$1"
cliFlags=()

if [[ "$testName" == *tls* ]]; then
  valkeyCliHelp="$(docker run --rm --entrypoint valkey-cli "$image" --help 2>&1 || :)"
  if ! grep -q -- '--tls' <<<"$valkeyCliHelp"; then
    echo >&2 "skipping; not built with TLS support (possibly version < 6.0 or 32bit variant)"
    exit 0
  fi

  tlsImage="$("$testDir/../image-name.sh" librarytest/valkey-tls "$image")"
  "$testDir/../docker-build.sh" "$testDir" "$tlsImage" <<-EOD
		FROM alpine:3.21 AS certs
		RUN apk add --no-cache openssl
		RUN set -eux; \
			mkdir /certs; \
			openssl genrsa -out /certs/ca-private.key 8192; \
			openssl req -new -x509 \
				-key /certs/ca-private.key \
				-out /certs/ca.crt \
				-days $((365 * 30)) \
				-subj '/CN=lolca'; \
			openssl genrsa -out /certs/private.key 4096; \
			openssl req -new -key /certs/private.key \
				-out /certs/cert.csr -subj '/CN=valkey'; \
			openssl x509 -req -in /certs/cert.csr \
				-CA /certs/ca.crt -CAkey /certs/ca-private.key -CAcreateserial \
				-out /certs/cert.crt -days $((365 * 30)); \
			openssl verify -CAfile /certs/ca.crt /certs/cert.crt

		FROM $image
		COPY --from=certs --chown=valkey:valkey /certs /certs
		CMD [ "valkey-server", \
			"--tls-port", "6379", "--port", "0", \
			"--tls-cert-file", "/certs/cert.crt", \
			"--tls-key-file", "/certs/private.key", \
			"--tls-ca-cert-file", "/certs/ca.crt" \
		]
	EOD

  image="$tlsImage"
  cliFlags+=(--tls --cert /certs/cert.crt --key /certs/private.key --cacert /certs/ca.crt)
fi

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
    "${cliFlags[@]}" \
    "$@"
}

. "$dir/../../retry.sh" --tries 20 '[ "$(valkey-cli ping)" = "PONG" ]'

[ "$(valkey-cli set mykey somevalue)" = "OK" ]
[ "$(valkey-cli get mykey)" = "somevalue" ]

# Test that modules are loaded and functional (bundle-specific addition)
echo "Testing modules..."

# Test JSON module
echo "Testing JSON..."
[ "$(valkey-cli JSON.SET test '$' '{"hello":"world"}')" = "OK" ]
[ "$(valkey-cli JSON.GET test)" = '{"hello":"world"}' ]

# Test Bloom filter 
echo "Testing Bloom..." 
[ "$(valkey-cli BF.RESERVE test_bloom 0.01 1000)" = "OK" ]
[ "$(valkey-cli BF.ADD test_bloom item1)" = "1" ]
[ "$(valkey-cli BF.EXISTS test_bloom item1)" = "1" ]

# Test Search module
echo "Testing Search" 
[ "$(valkey-cli FT.CREATE myIndex SCHEMA vector VECTOR HNSW 6 TYPE FLOAT32 DIM 3 DISTANCE_METRIC COSINE)" = "OK" ]
[ "$(valkey-cli FT._LIST)" = "myIndex" ]

echo "All tests passed!"