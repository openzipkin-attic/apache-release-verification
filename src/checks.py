import os
from typing import Callable, List, Optional, Union

from helpers import format_check_name, sh, step
from report import Report, Result


class State:
    def __init__(
        self,
        project: str,
        module: str,
        version: str,
        work_dir: str,
        incubating: bool,
        gpg_key: str,
    ):
        self.project = project
        self.module = module
        self.version = version
        self.work_dir = work_dir
        self.incubating = incubating
        self.gpg_key = gpg_key

    @property
    def project_dir(self) -> str:
        return os.path.join(self.work_dir, self.project, self.module, self.version)

    @property
    def base_path(self) -> str:
        filename = f"apache-{self.project}-{self.module}-"
        if self.incubating:
            filename += "incubating-"
        filename += f"{self.version}-source-release"
        return os.path.join(self.project_dir, filename)

    @property
    def zip_path(self) -> str:
        return self.base_path + ".zip"

    @property
    def sha512_path(self) -> str:
        return self.zip_path + ".sha512"

    @property
    def keys_path(self) -> str:
        return os.path.join(self.work_dir, "KEYS")

    @property
    def asc_path(self) -> str:
        return self.zip_path + ".asc"

    @property
    def keyring_path(self) -> str:
        return os.path.join(self.work_dir, "gpg.keyring")


def run_checks(state: State, checks: List[Callable[[State], Optional[str]]]) -> Report:
    results = []
    for check in checks:
        name = format_check_name(check)
        step(f"Running check: {name}")
        error = check(state)
        if error is None:
            result = Result.passed(name)
        else:
            result = Result.failed(name, error)
        results.append(result)
    return Report(results)


def _check_sh(cmds: Union[str, List[str]], workdir: Optional[str] = None) -> Optional[str]:
    if isinstance(cmds, str):
        cmds = [cmds]
    for cmd in cmds:
        status = sh(cmd, workdir)
        if status != 0:
            msg = f"Executing `{cmd}`"
            if workdir is not None:
                msg += f" in {workdir}"
            msg += f" exited with non-zero status code {status}. "
            msg += "See above for output."
            return msg


def check_zip_file_exists(state: State) -> Optional[str]:
    return _check_sh(f"test -f {state.zip_path}")


def check_sha512_file_exists(state: State) -> Optional[str]:
    return _check_sh(f"test -f {state.sha512_path}")


def check_asc_file_exists(state: State) -> Optional[str]:
    return _check_sh(f"test -f {state.asc_path}")


def check_keys_file_exists(state: State) -> Optional[str]:
    return _check_sh(f"test -f {state.keys_path}")


def check_sha512(state: State) -> Optional[str]:
    return _check_sh(f"sha512sum -c {state.sha512_path}", workdir=state.project_dir)


def check_gpg_key_in_keys_file(state: State) -> Optional[str]:
    return _check_sh(
        "gpg --with-colons --import-options show-only "
        f"--import {state.keys_path} "
        "| grep '^pub:' | cut -f5 -d: "
        f"| grep '{state.gpg_key}$'"
    )


def check_gpg_signature(state: State) -> Optional[str]:
    return _check_sh([
        f"gpg --no-default-keyring --keyring {state.keyring_path} --import {state.keys_path}",
        f"gpgv --keyring {state.keyring_path} {state.asc_path} {state.zip_path}"
    ])


checks = [
    check_zip_file_exists,
    check_sha512_file_exists,
    check_keys_file_exists,
    check_asc_file_exists,
    check_sha512,
    check_gpg_key_in_keys_file,
    check_gpg_signature
]
