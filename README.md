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