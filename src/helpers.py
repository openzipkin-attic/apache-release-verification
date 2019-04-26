import logging
import subprocess
from typing import Optional

from colorama import Back, Fore, Style


def header(msg: str) -> None:
    logging.info(f"{Back.MAGENTA}{Style.BRIGHT} {msg} {Style.RESET_ALL}")


def step(msg: str) -> None:
    logging.info(f"{Fore.BLUE}> {msg}{Style.RESET_ALL}")


def substep(msg: str) -> None:
    logging.info(f"{Fore.CYAN}>> {msg}{Style.RESET_ALL}")


def print_error(error: str) -> None:
    logging.error(f"{Fore.RED}{error}{Style.RESET_ALL}")


def sh(cmd: str, workdir: Optional[str] = None) -> int:
    msg = f"Executing `{cmd}`"
    if workdir is not None:
        msg += f" in '{workdir}'"
    substep(msg)
    return subprocess.call(
        f"set -euo pipefail; {cmd}", shell=True, cwd=workdir, executable="bash"
    )
