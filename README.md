# Archived

This repository has been archived as Zipkin is no longer in the Apache incubator.

# apache-release-verification

This project aims to automate some Apache Software Foundation source release verification steps. It cannot take over release review responsibilities: as a PMC, you're still directly responsible for verifying the release matches requirements. This script automates some of those steps in as transparent a way as possible.

This is semi-automatic, as it walks through each task, asking "Does X look good to you?" at some. The goal is
to lower the barrier to participating in release votes.

## Work in Progress

This is very early days... once more, you need to be sure about the state of the release before voting. If in doubt, re-run commands yourself, or refer to the [wiki](https://cwiki.apache.org/confluence/display/ZIPKIN/Verifying+a+Source+Release).

## Running

### Via `check.sh` (recommended)

This requires Docker to be installed on your machine, but nothing else.

```bash
git clone https://github.com/openzipkin-contrib/apache-release-verification.git
cd apache-release-verification
./check.sh --module brave-karaf --version 0.1.2 --gpg-key BB67A050 --git-hash 3cf4ac6577eb0d4775d20f24814e7a0852fa1635
```

This uses the Docker image built on Docker Hub. To build the image locally instead, set the `BUILD_IMAGE=1` env variable:

```bash
env BUILD_IMAGE=1 ./check.sh \
  --module brave-karaf --version 0.1.2 --gpg-key BB67A050 --git-hash 3cf4ac6577eb0d4775d20f24814e7a0852fa1635
```

If you want to do further manual verification after the script is done, even if all check passed, set the `NO_CLEANUP=1` env variable, like so:

```bash
env NO_CLEANUP=1 ./check.sh \
  --module brave-karaf --version 0.1.2 --gpg-key BB67A050 --git-hash 3cf4ac6577eb0d4775d20f24814e7a0852fa1635
```

At the end of the run, the script will output commands you can use to enter a Docker container with all the results of automated verification, and do your manual work.

### Without `git`

If you really don't want to run `git`, you can get around it like this:

```
bash -c '. <(curl -sSL https://raw.githubusercontent.com/openzipkin-contrib/apache-release-verification/master/check.sh) --module brave-karaf --version 0.1.2 --gpg-key BB67A050 --git-hash 3cf4ac6577eb0d4775d20f24814e7a0852fa1635'
```

(In case you're wondering: this is not a standard `curl|sh` setup because the script is interactive, so it needs STDIN to be your interactive terminal)

### Directly via Docker

You lose the convenience functions provided by `check.sh`, but in exchange you get full control over what happens to your container:

```
docker run --rm -ti \
  abesto/openzipkin-contrib-apache-release-verification \
  --module brave-karaf --version 0.1.2 --gpg-key BB67A050 --git-hash 3cf4ac6577eb0d4775d20f24814e7a0852fa1635
```

### The hard way

For running without Docker, you'll need some system-level dependencies. Some stuff won't work cleanly on macOS due to differences in Unix utilities across macOS and Linux; strongly prefer running under Docker via `check.sh` on macOS.

A best-effort list of system dependencies (the script will fail when it hits a missing one anyway):

* wget
* gpg
* sha256sum
* git
* maven
* ifne (look for a package called `moreutils`)

To run locally:

```bash
make setup-dev
./venv/bin/python3 src/main.py \
  --module brave-karaf --version 0.1.2 --gpg-key BB67A050 --git-hash 3cf4ac6577eb0d4775d20f24814e7a0852fa1635
```

(Or activate the virtualenv, if you want. Or don't. Up to you, really.)

## Hacking

Running locally like above is fine, but make sure your changes work via `check.sh` in the Docker environment. That's the only stable point in our life. Especially if you're not on Linux, since some Unix utilities work differently across macOS / BSD / Linux.

* `make setup-dev` sets you up for Great Success. Call this whenever you need more success in your life. Or more up-to-date dependencies.
* Run `make lint` to format, lint, and type-check code.
* `make clean` does what it says on the box.
* `make upgrade-dependencies` upgrades the Python dependencies used in the project. This should be Done Periodically (TM).
