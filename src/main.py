import logging
import os
import tempfile

import click
import colorama
from colorama import Fore, Style

from checks import State, checks, run_checks
from helpers import header, sh, step
from report import print_report


DISCLAIMER = """
This script is provided as a convenience to automate some steps
of verifying a release candidate. It does not take over the responsibilities
of a (P)PMC in part or in full.
""".strip()
USER_AGENT = "gh:openzipkin-contrib/apache-release-verification"


@click.command()
@click.argument("module")
@click.argument("version")
@click.option(
    "--gpg-key", required=True, help="ID of GPG key used to sign the release"
)
@click.option(
    "--git-hash", required=True, help="Git hash of the commit the release is built from"
)
@click.option("--project", default="zipkin")
@click.option(
    "--incubating/--not-incubating",
    is_flag=True,
    default=True,
    help="Specify to tell the script that the project is it is verifying is "
    "not in incubation. Currently the default is to assume incubation, as "
    "this script is aimed at Zipkin first, which is currently incubating.",
)
@click.option("-v", "--verbose", is_flag=True)
def main(
    module: str,
    version: str,
    git_hash: str,
    gpg_key: str,
    project: str,
    incubating: bool,
    verbose: bool,
) -> None:
    configure_logging(verbose)
    logging.debug(
        f"Arguments: project={project} module={module} version={version} "
        f"incubating={incubating} verbose={verbose} "
        f"gpg_key={gpg_key} git_hash={git_hash}"
    )
    header("Verifying release candidate for " f"{project}/{module} {version}")
    logging.info(f"{Fore.YELLOW}{DISCLAIMER}{Style.RESET_ALL}")

    workdir = make_and_enter_workdir()
    logging.info(f"Working directory: {workdir}")

    base_url = generate_base_url(project, incubating)
    logging.debug(f"Base URL: {base_url}")

    fetch_project(base_url, module, version, incubating)
    fetch_keys(base_url)

    state = State(
        project=project,
        module=module,
        version=version,
        work_dir=workdir,
        incubating=incubating,
        gpg_key=gpg_key,
        git_hash=git_hash
    )

    # TODO filter checks here with optional arguments later
    report = run_checks(state, checks=checks)
    print_report(report)


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


def generate_base_url(project: str, incubating: bool) -> str:
    url = "https://dist.apache.org/repos/dist/dev/"
    if incubating:
        url += "incubator/"
    url += project
    return url


def fetch_project(base_url: str, module: str, version: str, incubating: bool) -> None:
    step("Downloading release")
    version_root = f"{base_url}/{module}/{version}"
    cut_dirs = 3
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
