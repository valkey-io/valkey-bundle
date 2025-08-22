#
# NOTE: THIS DOCKERFILE IS GENERATED VIA "apply-templates.sh"
#
# PLEASE DO NOT EDIT IT DIRECTLY.
#

FROM docker.io/valkey/valkey:8.1.3-alpine AS build

ARG SERVER_VERSION=8.1.3

RUN set -eux; \
    apk add --no-cache            \
	        ca-certificates       \
	        build-base            \
	        cmake                 \
	        git                   \
	        curl                  \
	        clang                 \
	        clang19-dev           \
	        gtest-dev             \
	        ninja-build           \
	        ninja-is-really-ninja \
	        openssl-dev           \
	        clang19-extra-tools   \
	        linux-headers         \
	        bash                  \
                pkgconfig             \
	;\
    update-ca-certificates; \
    ln -s /usr/lib/ninja-build/bin/ninja /usr/bin/ninja-build;

# Install Rust
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y;
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /opt

# Clone repositories
RUN set -eux; \
    git clone --depth 1 --branch 1.0.1 https://github.com/valkey-io/valkey-json.git; \
    git clone --depth 1 --branch 1.0.0 https://github.com/valkey-io/valkey-bloom.git; \
    git clone --depth 1 --branch 1.0.1 https://github.com/valkey-io/valkey-search.git; \
    git clone --depth 1 --branch 1.0.0 https://github.com/valkey-io/valkey-ldap.git;

# Build JSON module
WORKDIR /opt/valkey-json
RUN set -eux; \
    ./build.sh --release

# Build Bloom module
WORKDIR /opt/valkey-bloom
RUN RUSTFLAGS="-C target-feature=-crt-static" cargo build --all --all-targets --release;

# Build Search module
WORKDIR /opt/valkey-search
RUN set -eux; \
    ./build.sh

# Build LDAP module
WORKDIR /opt/valkey-ldap
RUN RUSTFLAGS="-C target-feature=-crt-static" cargo build --all --all-targets --release;

FROM docker.io/valkey/valkey:8.1.3-alpine

RUN set -eux; \
    apk add --no-cache libstdc++; \
    mkdir -p /usr/lib/valkey;

# Copy built modules from the build stage
COPY --from=build /opt/valkey-json/build/src/libjson.so /usr/lib/valkey/libjson.so
COPY --from=build /opt/valkey-bloom/target/release/libvalkey_bloom.so /usr/lib/valkey/libvalkey_bloom.so
COPY --from=build /opt/valkey-search/.build-release/libsearch.so /usr/lib/valkey/libsearch.so
COPY --from=build /opt/valkey-ldap/target/release/libvalkey_ldap.so /usr/lib/valkey/libvalkey_ldap.so

COPY bundle-docker-entrypoint.sh /usr/local/bin/
ENTRYPOINT ["bundle-docker-entrypoint.sh"]

EXPOSE 6379
CMD ["valkey-server"]
