# valkey-bundle

This Project is the Git repo of the [Valkey Bundle "Official Image"](https://hub.docker.com/r/valkey/valkey-bundle/)

The Project is maintained by [the Valkey Community](https://github.com/valkey-io/)

## When should a new Docker image be built and published to Docker Hub?

A new Docker Image should be built and published after a new major, minor or patch version of Valkey or any Valkey module releases.

## How do you build and publish new version of a Docker Image?

*Prerequisites: [Fork](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/fork-a-repo) this repo, create a private Docker Hub repo, and setup your GitHub secrets to access the private Docker Hub repo.*

Upon releasing a new version of Valkey or any of its supported modules, a pull request will automatically be created with version specific dockerfiles. Additionally, `versions.json` will be updated with the most up to date versions and `dockerhub-description.md` will be updated with the tags. Once the pull request is merged, sit back, relax, and enjoy looking at your creation getting published to the official `valkey-bundle` Docker Hub page.

## How to add a New Module?
1. Update [versions.json](https://github.com/valkey-io/valkey-bundle/blob/mainline/versions.json):
   
   The `versions.json` file maintains metadata for `valkey-bundle` and its associated modules. To add a new module:
   - Locate the modules object: These are all modules with their respective names and versions.
    ```json
        "modules": {
          "valkey-json": {
            "version": "1.0.0"
          },
          "valkey-bloom": {
            "version": "1.0.0"
          },
          "valkey-search": {
            "version": "1.0.1"
          },
          "valkey-ldap": {
            "version": "1.0.0"
          }
        }
    ```
   - Add a new entry: Insert a JSON object with the following structure:
   ```json
    "valkey-new-module": {
      "version": "1.0.0"
    }
   ```

2. Modify the [Dockerfile.template](https://github.com/valkey-io/valkey-bundle/blob/mainline/Dockerfile.template)

  - Add dependencies: Insert the necessary dependencies to download, build, and install your new module. For example:
    ```bash
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
    Locate the [Clone repositories](https://github.com/valkey-io/valkey-bundle/blob/88722ae5568792c8751b017907c95cb4a8fe1a4d/Dockerfile.template#L33) section in the `Dockerfile` with similar module blocks and add your module in the same pattern like:
    ```bash
     # Clone repositories
    RUN set -eux; \
    git clone --depth 1 --branch {{ ."modules"."valkey-json".version }}  https://github.com/valkey-io/valkey-json.git; \
    git clone --depth 1 --branch {{ ."modules"."valkey-bloom".version }} https://github.com/valkey-io/valkey-bloom.git; \
    git clone --depth 1 --branch {{ ."modules"."valkey-search".version }} https://github.com/valkey-io/valkey-search.git;
    git clone --depth 1 --branch {{ ."modules"."valkey-ldap".version }} https://github.com/valkey-io/valkey-ldap.git;
    ```

  - Add a build step for the new module.
    Locate build steps for modules and add the steps for the new module in the similar way. These steps can be the same as in the `README` file of the new module.
    ```bash
    # Build Search module
    WORKDIR /opt/valkey-search
    RUN set -eux;       \
        ./build.sh;
    ```

    This also helps to track the build changes that may take place in the new versions of the modules.

  - Add the step to copy the module binary to `/usr/lib/valkey/`
    Locate the [Copy built modules](https://github.com/valkey-io/valkey-bundle/blob/88722ae5568792c8751b017907c95cb4a8fe1a4d/Dockerfile.template#L60C1-L60C21) sections and add a step line for the new module like:
    ```bash
    COPY --from=build /opt/valkey-json/build/src/libjson.so /usr/lib/valkey/libjson.so
    COPY --from=build /opt/valkey-bloom/target/release/libvalkey_bloom.so /usr/lib/valkey/libvalkey_bloom.so
    COPY --from=build /opt/valkey-search/.build-release/libsearch.so /usr/lib/valkey/libsearch.so
    ```

  - Add the new module to be loaded on `valkey-server` start up
    Locate the [`valkey-server`](https://github.com/valkey-io/valkey-bundle/blob/88722ae5568792c8751b017907c95cb4a8fe1a4d/Dockerfile.template#L65) command and add the new module binary to be loaded on the server:
    ```bash
    CMD ["valkey-server",                                               \
            "--loadmodule", "/usr/lib/valkey/libjson.so",           \
            "--loadmodule", "/usr/lib/valkey/libvalkey_bloom.so",   \
            "--loadmodule", "/usr/lib/valkey/libsearch.so"          \
    ]
    ```

3. Set up your module repository so the Valkey-Bundle repository can be automatically updated.

  - Create a trigger in your modules `.github/workflows` folder called `trigger-{module-name}-release`
  - Use the [code](https://github.com/valkey-io/valkey-search/blob/main/.github/workflows/trigger-search-release.yml) in the valkey-search repository as a template for your trigger. You can directly copy and paste this code into your file with only some minor changes: 
    - Update the top level name and replace "search" with the name of your module. Then update the description in the `workflow_dispatch` section and replace "search" with the name of your module.
    - In the `Trigger extension update` step, look at the `event-type` field. Modify the field to be `{module-name}-release`. Then in the same step, look at the `client-payload` field. Update the module parameter with the name of your module.
  - After creating this trigger, head over to the [`.github/workflows/update-files.yml`](https://github.com/Nikhil-Manglore/valkey-bundle/blob/mainline/.github/workflows/update-files.yml) in this repository. In the `repository_dispatch` section, add the name of the event type you created in the previous step to the end of the `types` array.
  - Finally create a secret in your repository with the name `EXTENSION_PAT` and secret value as your GitHub personal access token which you can create in your accounts developer settings.

3. Rebuild and Publish
   Now follow the [Build and Publish](#how-do-you-build-and-publish-new-version-of-a-docker-image) steps above.
   - Release a version of your module and that will trigger the automation which will complete all the required steps to build the new Docker images.

You're now ready to contribute a new Valkey module 🎉
