#
# NOTE: THIS DOCKERFILE IS GENERATED VIA "apply-templates.sh"
#
# PLEASE DO NOT EDIT IT DIRECTLY.
#

FROM docker.io/valkey/valkey:8.1.1-alpine AS build

ARG SERVER_VERSION=8.1.1

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
	;\
    update-ca-certificates; \
    ln -s /usr/lib/ninja-build/bin/ninja /usr/bin/ninja-build;

# Install Rust
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y;
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /opt

# Clone repositories
RUN set -eux; \
    git clone --depth 1 --branch 1.0.0  https://github.com/valkey-io/valkey-json.git; \
    git clone --depth 1 --branch 1.0.0 https://github.com/valkey-io/valkey-bloom.git; \
    git clone --depth 1 --branch alpine-fixes-2 https://github.com/eifrah-aws/valkey-search;

# Build JSON module
WORKDIR /opt/valkey-json
RUN set -eux; \
    mkdir -p build; \
    cd ./build; \
    cmake .. -DVALKEY_VERSION=${SERVER_VERSION}; \
    make;

# Build Bloom module
WORKDIR /opt/valkey-bloom
RUN RUSTFLAGS="-C target-feature=-crt-static" cargo build --all --all-targets --release;

# Build Search module
WORKDIR /opt/valkey-search
# on alpine, the first build fails due to this issue: https://github.com/grpc/grpc/issues/38438
# we just replace mutable int32_t with mutable int in .build-release/.deps/grpc/third_party/re2/util/pcre.h
# based on this upstream change https://github.com/google/re2/commit/b025c6a3ae05995660e3b882eb3277f4399ced1a
RUN set -eux; \
    ./build.sh

FROM docker.io/valkey/valkey:8.1.1-alpine

RUN set -eux; \
    apk add --no-cache libstdc++; \
    mkdir -p /usr/lib/valkey;

# Copy built modules from the build stage
COPY --from=build /opt/valkey-json/build/src/libjson.so /usr/lib/valkey/libjson.so
COPY --from=build /opt/valkey-bloom/target/release/libvalkey_bloom.so /usr/lib/valkey/libvalkey_bloom.so
COPY --from=build /opt/valkey-search/.build-release/libsearch.so /usr/lib/valkey/libsearch.so

CMD ["valkey-server",                                               \
            "--loadmodule", "/usr/lib/valkey/libjson.so",           \
            "--loadmodule", "/usr/lib/valkey/libvalkey_bloom.so",   \
            "--loadmodule", "/usr/lib/valkey/libsearch.so"          \
    ]
