# Quick reference

- **Maintained by**:  
  [the Valkey Community](https://github.com/valkey-io/valkey-extensions)

- **Where to get help**:  
  Please open an issue stating your question at [Valkey Extensions Issues](https://github.com/valkey-io/valkey-extensions/issues).

# Supported tags and respective `Dockerfile` links

## Release candidates
- [`8.1.0-rc1`, `8.1`, `8`, `latest`, `8.1.0-rc1-bookworm`, `8.1-bookworm`, `8-bookworm`, `bookworm`](https://github.com/valkey-io/valkey-extensions/blob/mainline/8.1/debian/Dockerfile)

## What is [Valkey Extensions](https://github.com/valkey-io/valkey-extensions)?
--------------
Valkey Extensions is a containerized version of Valkey, enhanced with popular modules like [Valkey JSON](https://github.com/valkey-io/valkey-json), [Valkey Bloom](https://github.com/valkey-io/valkey-bloom), and [Valkey Search](https://github.com/valkey-io/valkey-search), allowing you to utilize advanced data structures and additional search capabilities alongside standard Valkey functionality.

This image is built on top of the official Valkey base image and simplifies deployment of Valkey with these powerful modules included.

## Module Versions

| valkey-extensions | valkey-json | valkey-bloom | valkey-search |
|-------------------------|-------------|--------------|---------------|
| [8.1.0-rc1](https://github.com/valkey-io/valkey-extensions/releases/tag/8.1.0-rc1) | [1.0.0](https://github.com/valkey-io/valkey-json/releases/tag/1.0.0)| [1.0.0](https://github.com/valkey-io/valkey-bloom/releases/tag/1.0.0)| [1.0.0-rc1](https://github.com/valkey-io/valkey-search/releases/tag/1.0.0-rc1)      |

# Security

For ease of accessing Valkey Extensions from other containers via Docker networking, the "Protected mode" is turned off by default. This means if you expose the port externally (e.g., via `-p`), it will be open without authentication. It is **strongly recommended** to set a password or authentication method if exposing your instance to the internet.

See the following resources for securing Valkey:

- [Valkey security documentation](https://valkey.io/topics/security/)
- [Protected mode](https://valkey.io/topics/security/#protected-mode)

# How to use this image

## Start a valkey-extensions instance

```console
$ docker run --name my-valkey-extensions -d valkey/valkey-extensions
```

## Start with persistent storage

```console
$ docker run --name my-valkey-extensions -d valkey/valkey-extensions valkey-server --save 60 1 --loglevel warning
```

This example saves a snapshot every 60 seconds if at least one write occurred. Data is stored at `VOLUME /data`.

## Connecting via `valkey-cli`

```console
$ docker run -it --network some-network --rm valkey/valkey-extensions valkey-cli -h my-valkey-extensions
```

## Pass additional start arguments with environment variable

You can configure startup arguments with the environment variable `VALKEY_EXTRA_FLAGS`:

```console
$ docker run --env VALKEY_EXTRA_FLAGS='--save 60 1 --loglevel warning' valkey/valkey-extensions
```

## Custom valkey.conf usage

Create a custom configuration file `valkey.conf` and use it in your container:

**Dockerfile approach**:

```dockerfile
FROM valkey/valkey-extensions:latest
COPY valkey.conf /usr/local/etc/valkey/valkey.conf
CMD [ "valkey-server", "/usr/local/etc/valkey/valkey.conf" ]
```

**Docker run approach**:

```console
$ docker run -v /myvalkey/conf:/usr/local/etc/valkey --name my-valkey-extensions valkey/valkey-extensions valkey-server /usr/local/etc/valkey/valkey.conf
```
# Image Variants

## `valkey/valkey-extensions:<version>`

This is the primary image, which includes Valkey along with common modules like valkey-json, valkey-bloom, and valkey-search preloaded. It is suitable for development, testing, and production environments where these modules are needed out of the box.

Some of the tags may include names like `bookworm`, which refer to [Debian release codenames](https://wiki.debian.org/DebianReleases). These indicate the base image used and help ensure compatibility if your container needs additional packages. Specifying these explicitly is recommended to avoid unexpected changes when base image versions update.

If you want a minimal yet functional Valkey container with built-in modules, this image is a great place to start.

# License

View the [license information](https://github.com/valkey-io/valkey-extensions/blob/mainline/LICENSE) for software included in this image.

Users of this image are responsible for ensuring compliance with all licenses of software contained within.
