import logging
import os
import sys
import tempfile
from typing import Any, Dict, Optional, Union

import click
import colorama
import requests
import yaml
from colorama import Fore, Style

from checks import State, checks, run_checks
from config import Config
from helpers import header, sh, step
from report import print_report

DISCLAIMER = """
This script is provided as a convenience to automate some steps
of verifying a release candidate. It does not take over the responsibilities
of a (P)PMC in part or in full.
""".strip()
USER_AGENT = "gh:openzipkin-contrib/apache-release-verification"


def _load_yaml(x: Any) -> Dict:
    return {key.replace("-", "_"): value for key, value in yaml.safe_load(x).items()}


def local_config_callback(
    ctx: click.Context,
    _param: Union[click.Option, click.Parameter],
    value: Optional[str],
) -> Optional[str]:
    if value is None:
        logging.debug("local_config_callback: value is None, not loading anything")
        return None
    with open(value) as f:
        data = _load_yaml(f)
    logging.debug(f"local_config_callback: loaded data from {value}: {data}")
    original = ctx.default_map or {}
    ctx.default_map = {**original, **data}
    return value


def remote_config_provider(is_default: bool, url: str) -> Dict:
    if not url.startswith("http://") and not url.startswith("https://"):
        url = (
            "https://openzipkin-contrib.github.io/apache-release-verification/"
            f"presets/{url}.yaml"
        )
    logging.debug(f"remote_config_provider: Loading remote config from {url}")
    resp = requests.get(url, headers={"User-Agent": USER_AGENT})
    try:
        resp.raise_for_status()
        data = _load_yaml(resp.content)
        logging.debug(f"remote_config_provider: Loaded data: {data}")
        return data
    except requests.exceptions.HTTPError:
        if is_default:
            return {}
        else:
            raise


def remote_config_callback(
    ctx: click.Context,
    _param: Union[click.Option, click.Parameter],
    value: Optional[str],
) -> Optional[str]:
    is_default = False
    if value is None:
        is_default = True
        project = ctx.params["project"]
        module = ctx.params["module"]
        if project is not None and module is not None:
            value = f"{project}/{module}"
            logging.debug(f"remote_config_callback: inferred URL {value}")
        else:
            logging.debug(
                "remote_config_callback: no value specified, and project or "
                "module is None, not fetching remote config"
            )
    if value is not None:
        original = ctx.default_map or {}
        ctx.default_map = {**original, **remote_config_provider(is_default, value)}
    return value


def configure_logging(verbose: bool):
    if verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(level=level, format="%(message)s")


def configure_logging_callback(
    _ctx: click.Context, _param: Union[click.Option, click.Parameter], verbose: bool
) -> bool:
    configure_logging(verbose)
    return verbose


@click.command(context_settings=dict(max_content_width=120))
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    expose_value=False,
    # We don't actually use this; it's evaluated in the __main__ block.
    # See comment there for details.
)
@click.option("--project", default="zipkin", is_eager=True)
@click.option("--module", is_eager=True)
@click.option(
    "--config",
    default=None,
    callback=local_config_callback,
    expose_value=False,
    is_eager=True,
    help="Path to a local .yml file to load options from.",
)
@click.option(
    "--remote-config",
    default=None,
    callback=remote_config_callback,
    expose_value=False,
    is_eager=True,
    help="Remote file to load options from. Can be a full HTTP(S) URL, or a "
    "simple string PROJECT/MODULE, which will be expanded to load from "
    "the central repository at https://openzipkin-contrib.github.io/"
    "apache-release-verification/presets/PROJECT/MODULE.yaml. Defaults "
    "to $PROJECT/$MODULE",
)
@click.option("--version", required=True)
@click.option("--gpg-key", required=True, help="ID of GPG key used to sign the release")
@click.option(
    "--git-hash", required=True, help="Git hash of the commit the release is built from"
)
@click.option(
    "--repo",
    type=click.Choice(["dev", "release", "test"]),
    default="dev",
    help="dev, release, or test",
)
@click.option(
    "--incubating/--not-incubating",
    is_flag=True,
    default=True,
    help="Specify to tell the script that the project is it is verifying is "
    "not in incubation. Currently the default is to assume incubation, as "
    "this script is aimed at Zipkin first, which is currently incubating.",
)
@click.option(
    "--zipname-template",
    default="apache-{project}{dash_module}{dash_incubating}-{version}-source-release",
    help="Specify the format of the expected .zip filename. Supports the same "
    "placeholders as --sourcedir-template.",
)
@click.option(
    "--sourcedir-template",
    default="{module_or_project}-{version}",
    help="Specify the format of the expected top-level directory in the source "
    "archive. Usable placeholders: "
    f"{', '.join(State.list_placeholder_keys())}",
)
@click.option(
    "--github-reponame-template",
    default="{incubator_dash}{project}{dash_module}.git",
    help="Specify the format for the name of the GitHub repository of the project."
    "Supports the same placeholders as --sourcedir-template.",
)
@click.option(
    "--build-and-test-command",
    help="Instead of built-in heuristics, use this command to build and "
    "test the release. Executed with the exctracted source release archive "
    "as the working directory.",
)
def main(**kwargs) -> None:
    config = Config(**kwargs)
    logging.debug(f"Resolved config: {config}")

    header_msg = f"Verifying release candidate for {config.project}"
    if config.module:
        header_msg += f"/{config.module}"
    header_msg += f" {config.version}"
    header(header_msg)
    logging.info(f"{Fore.YELLOW}{DISCLAIMER}{Style.RESET_ALL}")

    workdir = make_and_enter_workdir()
    logging.info(f"Working directory: {workdir}")

    base_url = generate_base_url(config.repo, config.project, config.incubating)
    logging.debug(f"Base URL: {base_url}")

    fetch_project(base_url, config.module, config.version, config.incubating)
    fetch_keys(base_url)

    state = State(work_dir=workdir, **config.__dict__)

    # TODO this is the place to filter checks here with optional arguments
    report = run_checks(state, checks=checks)
    print_report(report)
    if report.problem_count == 0:
        logging.info(f"{Fore.GREEN}Everything seems to be in order.{Style.RESET_ALL}")
    else:
        logging.info(
            f"{Fore.RED}Found {report.problem_count} "
            f"potential problems.{Style.RESET_ALL}"
        )
        sys.exit(1)


def make_and_enter_workdir() -> str:
    workdir = tempfile.mkdtemp()
    os.chdir(workdir)
    return workdir


def generate_base_url(repo: str, project: str, incubating: bool) -> str:
    url = f"https://dist.apache.org/repos/dist/{repo}/"
    if incubating:
        url += "incubator/"
    url += project
    return url


def fetch_project(
    base_url: str, module: Optional[str], version: str, incubating: bool
) -> None:
    step("Downloading release")

    version_root = f"{base_url}/"
    if module:
        version_root += f"{module}/"
    version_root += version

    cut_dirs = 3
    if module:
        cut_dirs += 1
    if incubating:
        cut_dirs += 1
    sh(
        "wget --recursive --no-parent --reject index.html "
        f"--no-verbose --user-agent='{USER_AGENT}' "
        f"--no-host-directories --cut-dirs={cut_dirs} {version_root}"
    )


def fetch_keys(base_url: str) -> None:
    step("Downloading KEYS file")
    sh(f"wget --no-verbose --user-agent='{USER_AGENT}' {base_url}/KEYS")


if __name__ == "__main__":
    colorama.init()

    # There is only a single level of eagerness in Click, and we use that to
    # load config options from local or remote files. But we need to handle
    # --verbose before that happens, so that we can log from the related
    # functions. So... you know, this is it.
    if "-v" in sys.argv or "--verbose" in sys.argv:
        configure_logging(True)
    else:
        configure_logging(False)

    # Now we can execute the actual program
    main()
