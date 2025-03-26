#
# NOTE: THIS DOCKERFILE IS GENERATED VIA "apply-templates.sh"
#
# PLEASE DO NOT EDIT IT DIRECTLY.
#

FROM docker.io/valkey/valkey:8.1.0-rc2-bookworm AS build

ARG SERVER_VERSION=8.1.0-rc2
ARG JSON_VERSION=1.0.0-rc1 
ARG BLOOM_VERSION=1.0.0-rc1

RUN set -eux; \
\
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        build-essential \
        cmake \
        git \
        curl \
        clang \
    ;\
    apt-get clean && rm -rf /var/lib/apt/lists/* ;

# Install Rust
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y;
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /opt

# Clone repositories
RUN set -eux; \
    git clone --branch ${JSON_VERSION} https://github.com/valkey-io/valkey-json.git; \
    git clone --branch ${BLOOM_VERSION} https://github.com/valkey-io/valkey-bloom.git;

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


FROM docker.io/valkey/valkey:8.1.0-rc2-bookworm

RUN mkdir -p /usr/lib/valkey;

# Copy built modules from the build stage
COPY --from=build /opt/valkey-json/build/src/libjson.so /usr/lib/valkey/libjson.so
COPY --from=build /opt/valkey-bloom/target/release/libvalkey_bloom.so /usr/lib/valkey/libvalkey_bloom.so

CMD ["valkey-server", "--loadmodule", "/usr/lib/valkey/libjson.so", "--loadmodule", "/usr/lib/valkey/libvalkey_bloom.so"]
