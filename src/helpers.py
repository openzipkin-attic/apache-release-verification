import logging
import subprocess
from typing import Any, Optional

from colorama import Back, Fore, Style


def header(msg: str) -> None:
    logging.info(f"{Back.MAGENTA}{Style.BRIGHT} {msg} {Style.RESET_ALL}")


def step(msg: str) -> None:
    logging.info(f"{Fore.BLUE}> {msg}{Style.RESET_ALL}")


def substep(msg: str) -> None:
    logging.info(f"{Fore.CYAN}>> {msg}{Style.RESET_ALL}")


def format_check_name(check: Any) -> str:
    name = check.__name__
    if name.startswith("check_"):
        name = name[len("check_") :]
    name = name.replace("_", " ")
    return name


def sh(cmd: str, workdir: Optional[str] = None) -> int:
    msg = f"Executing `{cmd}`"
    if workdir is not None:
        msg += f" in '{workdir}'"
    substep(msg)
    return subprocess.call(cmd, shell=True, cwd=workdir)
