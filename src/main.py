import logging
import os
import sys
import tempfile
from typing import Dict, Optional

import click
import click_config_file  # type: ignore
import colorama
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


def yaml_config_provider(path: str, cmd_name: str) -> Dict:
    with open(path) as f:
        return {
            key.replace("-", "_"): value for key, value in yaml.safe_load(f).items()
        }


@click.command()
@click.option("--project", default="zipkin")
@click.option("--module")
@click.option("--version", required=True)
@click.option("--gpg-key", required=True, help="ID of GPG key used to sign the release")
@click.option(
    "--git-hash", required=True, help="Git hash of the commit the release is built from"
)
@click.option("--repo", default="dev", help="dev, release, or test")
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
@click.option("-v", "--verbose", is_flag=True)
@click_config_file.configuration_option(implicit=False, provider=yaml_config_provider)
def main(**kwargs) -> None:
    config = Config(**kwargs)
    configure_logging(config.verbose)

    logging.debug(config)

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


def configure_logging(verbose: bool) -> None:
    if verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(level=level, format="%(message)s")


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
    main()
