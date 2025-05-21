# valkey-extensions

This Project is the Git repo of the [Valkey Extensions "Official Image"](https://hub.docker.com/r/valkey/valkey-extensions/)

The Project is maintained by [the Valkey Community](https://github.com/valkey-io/)

## When should a new image built and publish new Docker Image?

A new Docker Image should be built and published after a new major, minor or patch version of Valkey or any Valkey module releases.

## How do you build and publish new version of a Docker Image?

*Pre-requisites: [Fork](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo) this repo, create a private Docker Hub repo, and setup your GitHub secrets to access the private Docker Hub repo.*

1. Bump up the respective versions in versions.json. (will be automated by implementing versions.sh)
2. Run `apply-templates.sh`
3. Update the `dockerhub-description.md` with the updated tags.
4. Open a new PR for the new changes.
5. Once the PR is merged, sit back, relax and enjoy looking at your creation getting published to the official Valkey-extension Docker Hub page.

## How to add a New Module?
1. Update [versions.json](https://github.com/valkey-io/valkey-extension/blob/mainline/versions.json):
   
   The versions.json file maintains metadata for Valkey-extension and its associated modules. To add a new module:
   - Locate the modules object: These are all modules with their respective names and versions.
    ```
        "modules": {
          "valkey-json": {
            "version": "1.0.0"
          },
          "valkey-bloom": {
            "version": "1.0.0"
          },
          "valkey-search": {
            "version": "1.0.0-rc1"
          }
        }
    ```
   - Add a new entry: Insert a JSON object with the following structure:
   ```
    "valkey-new-module": {
      "version": "1.0.0"
    }
   ```

2. Modify the [Dockerfile.template](https://github.com/valkey-io/valkey-extension/blob/mainline/Dockerfile.template)

  - Add dependencies: Insert the necessary dependencies to download, build, and install your new module. For example:
    ```
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
                        .
                        .
    ```

  - Add the clone steps for the new module
    Locate the [Clone repositories](https://github.com/valkey-io/valkey-extension/blob/88722ae5568792c8751b017907c95cb4a8fe1a4d/Dockerfile.template#L33) section in the Dockerfile with similar module blocks and add your module in the same pattern like:
    ```
     # Clone repositories
    RUN set -eux; \
    git clone --depth 1 --branch {{ ."modules"."valkey-json".version }}  https://github.com/valkey-io/valkey-json.git; \
    git clone --depth 1 --branch {{ ."modules"."valkey-bloom".version }} https://github.com/valkey-io/valkey-bloom.git; \
    git clone --depth 1 --branch {{ ."modules"."valkey-search".version }} https://github.com/valkey-io/valkey-search.git;
    ```

  - Add a build step for the new module.
    Locate build steps for modules and add the steps for the new module in the similar way. These steps can be the same as in the README file of the new module.
    ```
    # Build Search module
    WORKDIR /opt/valkey-search
    RUN set -eux;       \
        ./build.sh;
    ```

    This also helps to track the build changes that may take place in the new versions of the modules.

  - Add the step to copy the module binary to `/usr/lib/valkey/`
    Locate the [Copy built modules](https://github.com/valkey-io/valkey-extension/blob/88722ae5568792c8751b017907c95cb4a8fe1a4d/Dockerfile.template#L60C1-L60C21) sections and add a step line for the new module like:
    ```
    COPY --from=build /opt/valkey-json/build/src/libjson.so /usr/lib/valkey/libjson.so
    COPY --from=build /opt/valkey-bloom/target/release/libvalkey_bloom.so /usr/lib/valkey/libvalkey_bloom.so
    COPY --from=build /opt/valkey-search/.build-release/libsearch.so /usr/lib/valkey/libsearch.so
    ```

  - Add the new module to be loaded on `valkey-server` start up
    Locate the [`valkey-server`](https://github.com/valkey-io/valkey-extension/blob/88722ae5568792c8751b017907c95cb4a8fe1a4d/Dockerfile.template#L65) command and add the new module binary to be loaded on the server:
    ```
    CMD ["valkey-server",                                               \
            "--loadmodule", "/usr/lib/valkey/libjson.so",           \
            "--loadmodule", "/usr/lib/valkey/libvalkey_bloom.so",   \
            "--loadmodule", "/usr/lib/valkey/libsearch.so"          \
    ]
    ```

3. Rebuild and Publish
   Now follow the [Build and Publish](#how-do-you-build-and-publish-new-version-of-a-docker-image) steps above.
   - Run [./apply-templates.sh](https://github.com/valkey-io/valkey-extension/blob/mainline/apply-templates.sh)
   - Test the build
   - Open a pull request

You're now ready to contribute a new Valkey module 🎉
