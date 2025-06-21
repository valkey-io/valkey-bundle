
#!/usr/bin/env bash
set -eo pipefail

dir="$(dirname "$(readlink -f "$BASH_SOURCE")")"

image="$1"

newImage="$("$dir/../image-name.sh" librarytest/valkey-basics-config "$image")"
"$dir/../docker-build.sh" "$dir" "$newImage" <<-EOD
	FROM $image
	RUN mkdir -p /usr/local/etc/valkey && \\
		echo 'maxmemory 100000000' > /usr/local/etc/valkey/test.conf && \\
	    echo 'maxmemory-policy allkeys-lru' >> /usr/local/etc/valkey/test.conf && \\
	    echo 'save 60 1000' >> /usr/local/etc/valkey/test.conf && \\
	    echo 'appendonly yes' >> /usr/local/etc/valkey/test.conf
	CMD ["valkey-server", "/usr/local/etc/valkey/test.conf"]
EOD

exec "$dir/real-run.sh" "$newImage"