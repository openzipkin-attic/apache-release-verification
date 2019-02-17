import os
from typing import Callable, List, Optional, Union

import apache_2_license
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
        git_hash: str,
    ):
        self.project = project
        self.module = module
        self.version = version
        self.work_dir = work_dir
        self.incubating = incubating
        self.gpg_key = gpg_key
        self.git_hash = git_hash

    @property
    def release_dir(self) -> str:
        return os.path.join(self.work_dir, self.project, self.module, self.version)

    @property
    def base_path(self) -> str:
        filename = f"apache-{self.project}-{self.module}-"
        if self.incubating:
            filename += "incubating-"
        filename += f"{self.version}-source-release"
        return os.path.join(self.release_dir, filename)

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

    @property
    def unzipped_dir(self) -> str:
        return os.path.join(self.work_dir, "unzipped")

    @property
    def source_dir(self) -> str:
        return os.path.join(self.unzipped_dir, f"{self.module}-{self.version}")

    @property
    def git_repo_name(self) -> str:
        repo_name = f"{self.project}-{self.module}.git"
        if self.incubating:
            repo_name = f"incubator-{repo_name}"
        return repo_name

    @property
    def git_dir(self) -> str:
        return os.path.join(self.work_dir, "git", self.git_repo_name)


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


def _check_sh(
    cmds: Union[str, List[str]], workdir: Optional[str] = None
) -> Optional[str]:
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
    return _check_sh(f"sha512sum -c {state.sha512_path}", workdir=state.release_dir)


def check_gpg_key_in_keys_file(state: State) -> Optional[str]:
    return _check_sh(
        "gpg --with-colons --import-options show-only "
        f"--import {state.keys_path} "
        "| grep '^pub:' | cut -f5 -d: "
        f"| grep '{state.gpg_key}$'"
    )


def check_gpg_signature(state: State) -> Optional[str]:
    return _check_sh(
        [
            (
                f"gpg --no-default-keyring --keyring {state.keyring_path} "
                f"--import {state.keys_path}"
            ),
            (
                f"gpgv --keyring {state.keyring_path} "
                f"{state.asc_path} {state.zip_path}"
            ),
        ]
    )


def check_unzip(state: State) -> Optional[str]:
    return _check_sh(f"unzip -q -d {state.unzipped_dir} {state.zip_path}")


def check_base_dir_in_zip(state: State) -> Optional[str]:
    return _check_sh(f"test -d {state.source_dir}")


def check_git_revision(state: State) -> Optional[str]:
    return _check_sh(
        [
            (
                f"git clone https://github.com/apache/{state.git_repo_name} "
                f"{state.git_dir}"
            ),
            (
                f"git --work-tree {state.git_dir} "
                f"--git-dir {state.git_dir}/.git "
                f"checkout --quiet {state.git_hash}"
            ),
            (
                f"diff --recursive {state.git_dir} {state.source_dir} "
                "--exclude DEPENDENCIES --exclude NOTICE --exclude .git "
                "--exclude .gitignore"
            ),
        ]
    )


def _check_file_looks_good(path: str) -> Optional[str]:
    prompt = f"Did the contents of {path} look good to you? [y/N] "
    return _check_sh(
        [f"less {path}", f"read -r -p '{prompt}' response; test \"$response\" == y"]
    )


def check_disclaimer_looks_good(state: State) -> Optional[str]:
    return _check_file_looks_good(os.path.join(state.source_dir, "DISCLAIMER"))


def check_notice_looks_good(state: State) -> Optional[str]:
    return _check_file_looks_good(os.path.join(state.source_dir, "NOTICE"))


def check_license_is_apache_2(state: State) -> Optional[str]:
    expected_license_path = os.path.join(state.work_dir, "expected_license")
    actual_license_path = os.path.join(state.source_dir, "LICENSE")
    with open(expected_license_path, "w") as f:
        f.write(apache_2_license.text)
    return _check_sh([f"diff {expected_license_path} {actual_license_path}"])


def check_license_looks_good(state: State) -> Optional[str]:
    return _check_file_looks_good(os.path.join(state.source_dir, "LICENSE"))


def check_no_binary_files(state: State) -> Optional[str]:
    return _check_sh(
        f"diff <(echo -n) <(find {state.source_dir} -type f "
        "| xargs file | grep -v text | cut -f1 -d:)"
    )


def check_build_and_test(state: State) -> Optional[str]:
    return _check_sh("./mvnw --quiet package", workdir=state.source_dir)


checks = [
    check_zip_file_exists,
    check_sha512_file_exists,
    check_keys_file_exists,
    check_asc_file_exists,
    check_sha512,
    check_gpg_key_in_keys_file,
    check_gpg_signature,
    check_unzip,
    check_base_dir_in_zip,
    check_git_revision,
    check_disclaimer_looks_good,
    check_notice_looks_good,
    check_license_is_apache_2,
    check_license_looks_good,
    check_no_binary_files,
    check_build_and_test,
]
