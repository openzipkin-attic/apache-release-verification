import logging
import os
import tempfile
from typing import Optional

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
@click.option("--project", default="zipkin")
@click.option("--module", required=False)
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
@click.option("-v", "--verbose", is_flag=True)
def main(
    project: str,
    module: Optional[str],
    version: str,
    git_hash: str,
    gpg_key: str,
    repo: str,
    incubating: bool,
    zipname_template: str,
    sourcedir_template: str,
    github_reponame_template: str,
    verbose: bool,
) -> None:
    configure_logging(verbose)
    logging.debug(
        f"Arguments: project={project} module={module} version={version} "
        f"incubating={incubating} verbose={verbose} "
        f"zipname_template={zipname_template} sourcedir_template={sourcedir_template} "
        f"github_reponame_template={github_reponame_template} "
        f"gpg_key={gpg_key} git_hash={git_hash}"
    )

    header_msg = f"Verifying release candidate for {project}"
    if module:
        header_msg += f"/{module}"
    header_msg += f" {version}"
    header(header_msg)
    logging.info(f"{Fore.YELLOW}{DISCLAIMER}{Style.RESET_ALL}")

    workdir = make_and_enter_workdir()
    logging.info(f"Working directory: {workdir}")

    base_url = generate_base_url(repo, project, incubating)
    logging.debug(f"Base URL: {base_url}")

    fetch_project(base_url, module, version, incubating)
    fetch_keys(base_url)

    state = State(
        project=project,
        module=module,
        version=version,
        work_dir=workdir,
        incubating=incubating,
        zipname_template=zipname_template,
        sourcedir_template=sourcedir_template,
        github_reponame_template=github_reponame_template,
        gpg_key=gpg_key,
        git_hash=git_hash,
    )

    # TODO this is the place to filter checks here with optional arguments
    report = run_checks(state, checks=checks)
    print_report(report)
    if report.problem_count == 0:
        logging.info(f"{Fore.GREEN}Everything seems to be in order.{Style.RESET_ALL}")
    else:
        raise click.ClickException(
            f"{Fore.RED}Found {report.problem_count} " f"problems.{Style.RESET_ALL}"
        )


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
