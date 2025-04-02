#
# NOTE: THIS DOCKERFILE IS GENERATED VIA "apply-templates.sh"
#
# PLEASE DO NOT EDIT IT DIRECTLY.
#

FROM docker.io/valkey/valkey:8.1.0-bookworm AS build

ARG SERVER_VERSION=8.1.0

RUN set -eux;   \
                \
    apt-get update;     \
    apt-get install -y --no-install-recommends  \
                        ca-certificates         \
                        build-essential         \
                        cmake                   \
                        git                     \
                        curl                    \
                        clang                   \
                        clangd                  \
                        g++                     \
                        libgtest-dev            \
                        ninja-build             \
                        libssl-dev              \
                        clang-tidy              \
                        clang-format            \
                        libsystemd-dev          \
                    ;\
    apt-get clean && rm -rf /var/lib/apt/lists/* ;

# Install Rust
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y;
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /opt

# Clone repositories
RUN set -eux; \
    git clone --depth 1 --branch 1.0.0  https://github.com/valkey-io/valkey-json.git; \
    git clone --depth 1 --branch 1.0.0 https://github.com/valkey-io/valkey-bloom.git; \
    git clone --depth 1 --branch 1.0.0-rc1 https://github.com/valkey-io/valkey-search.git;

# Build JSON module
WORKDIR /opt/valkey-json
RUN set -eux; \
    mkdir -p build; \
    cd ./build; \
    cmake .. -DVALKEY_VERSION=${SERVER_VERSION}; \
    make;

# Build Bloom module
WORKDIR /opt/valkey-bloom
RUN cargo build --all --all-targets --release;

# Build Search module
WORKDIR /opt/valkey-search
RUN set -eux;       \
    ./build.sh;

FROM docker.io/valkey/valkey:8.1.0-bookworm

RUN mkdir -p /usr/lib/valkey;

# Copy built modules from the build stage
COPY --from=build /opt/valkey-json/build/src/libjson.so /usr/lib/valkey/libjson.so
COPY --from=build /opt/valkey-bloom/target/release/libvalkey_bloom.so /usr/lib/valkey/libvalkey_bloom.so
COPY --from=build /opt/valkey-search/.build-release/libsearch.so /usr/lib/valkey/libsearch.so

CMD ["valkey-server",                                               \
            "--loadmodule", "/usr/lib/valkey/libjson.so",           \
            "--loadmodule", "/usr/lib/valkey/libvalkey_bloom.so",   \
            "--loadmodule", "/usr/lib/valkey/libsearch.so"          \
    ]
