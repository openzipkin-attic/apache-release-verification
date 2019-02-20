import filecmp
import functools
import logging
import os
from typing import Callable, List, Optional, Union

import apache_2_license
from helpers import sh, step
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


class Check:
    def __init__(
        self,
        fun: Callable[[State], Optional[str]],
        name: Optional[str] = None,
        hide_if_passing: bool = False,
    ):
        self._fun = fun
        self.name = self._generate_nice_name(name, fun)
        self.hide_if_passing = hide_if_passing

    def _generate_nice_name(self, name: Optional[str], fun: Callable):
        if name is not None:
            return name
        name = self._fun.__name__
        if name.startswith("check_"):
            name = name[6:]
        name = name.replace("_", " ")
        return name

    def __call__(self, state: State) -> Optional[str]:
        return self._fun(state)


def check(
    name: Optional[str] = None, hide_if_passing: bool = False
) -> Callable[[Callable], Check]:
    def make_check(fun: Callable) -> Check:
        c = Check(fun, name, hide_if_passing)
        functools.update_wrapper(c, fun)
        return c

    return make_check


def run_checks(state: State, checks: List[Check]) -> Report:
    results = []
    for check in checks:
        step(f"Running check: {check.name}")
        error = check(state)
        if error is None:
            result = Result.passed(check.name, check.hide_if_passing)
        else:
            result = Result.failed(check.name, check.hide_if_passing, error)
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
    return None


@check("Source archive has expected name")
def check_zip_file_exists(state: State) -> Optional[str]:
    return _check_sh(f"test -f {state.zip_path}")


@check("SHA512 checksum exists with expected name", hide_if_passing=True)
def check_sha512_file_exists(state: State) -> Optional[str]:
    return _check_sh(f"test -f {state.sha512_path}")


@check("ASC checksum exists with expected name", hide_if_passing=True)
def check_asc_file_exists(state: State) -> Optional[str]:
    return _check_sh(f"test -f {state.asc_path}")


@check("KEYS file exists", hide_if_passing=True)
def check_keys_file_exists(state: State) -> Optional[str]:
    return _check_sh(f"test -f {state.keys_path}")


@check("SHA512 checksum is correct")
def check_sha512(state: State) -> Optional[str]:
    return _check_sh(f"sha512sum -c {state.sha512_path}", workdir=state.release_dir)


@check("Provided GPG key is in KEYS file")
def check_gpg_key_in_keys_file(state: State) -> Optional[str]:
    return _check_sh(
        "gpg --with-colons --import-options show-only "
        f"--import {state.keys_path} "
        "| grep '^pub:' | cut -f5 -d: "
        f"| grep '{state.gpg_key}$'"
    )


@check("GPG signature is valid, made with the provided key")
def check_gpg_signature(state: State) -> Optional[str]:
    full_keyring = os.path.join(state.work_dir, "gpg.keyring.all")
    strict_keyfile = os.path.join(state.work_dir, "KEYS.strict")
    strict_keyring = os.path.join(state.work_dir, "gpg.keyring.strict")

    # The dance with importing/exporting/importing is needed so that we end up
    # with a keyring containing exactly the key the release is said to be made
    # with, and verify the signature against that key, and that key only.
    return _check_sh(
        [
            # Import all keys from the KEYS file
            (
                f"gpg --no-default-keyring --keyring {full_keyring} "
                f"--import {state.keys_path}"
            ),
            # Export only the key the release is said to be made with
            (
                f"gpg --no-default-keyring --keyring {full_keyring} "
                f"--export --armor {state.gpg_key} > {strict_keyfile}"
            ),
            # Create keyring with only the wanted key
            (
                f"gpg --no-default-keyring --keyring {strict_keyring} "
                f"--import {strict_keyfile}"
            ),
            # Check the signature using exactly the key provided
            (f"gpgv --keyring {strict_keyring} {state.asc_path} {state.zip_path}"),
        ]
    )


@check("Source archive can be unzipped", hide_if_passing=True)
def check_unzip(state: State) -> Optional[str]:
    return _check_sh(f"unzip -q -d {state.unzipped_dir} {state.zip_path}")


@check("Base dir in archive is named {module}-{version}")
def check_base_dir_in_zip(state: State) -> Optional[str]:
    return _check_sh(f"test -d {state.source_dir}")


def _check_dircmp_only_either_allowed(diff: filecmp.dircmp) -> List[str]:
    errors = []
    allowed_left_only = [
        ".git",
        ".gitignore",
        ".mvn",
        "mvnw",
        "mvnw.cmd",
        "Jenkinsfile",
    ]
    allowed_right_only: List[str] = []
    # Check files only in the git checkout
    for filename in diff.left_only:
        if filename not in allowed_left_only:
            errors.append(
                os.path.join(diff.left, filename) + " is only in the git checkout"
            )
    # Check files only in the source archive
    for filename in diff.right_only:
        if filename not in allowed_right_only:
            errors.append(
                os.path.join(diff.right, filename) + " is only in the source archive"
            )
    # And recurse into subdirectories
    for subdiff in diff.subdirs.values():
        errors += _check_dircmp_only_either_allowed(subdiff)
    return errors


def _check_dircmp_no_diff_files(diff: filecmp.dircmp) -> List[str]:
    errors: List[str] = []
    if diff.diff_files:
        errors += "The contents of the following files differ: " + " ".join(
            diff.diff_files
        )
    for subdiff in diff.subdirs.values():
        errors += _check_dircmp_no_diff_files(subdiff)
    return errors


def _check_dircmp_no_funny_files(diff: filecmp.dircmp) -> List[str]:
    errors: List[str] = []
    if diff.funny_files:
        errors += "Failed to compare contents of the following files: " + " ".join(
            diff.diff_files
        )
    for subdiff in diff.subdirs.values():
        errors += _check_dircmp_no_diff_files(subdiff)
    return errors


@check("Git tree at provided revision matches source archive")
def check_git_revision(state: State) -> Optional[str]:
    sh_result = _check_sh(
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
        ]
    )
    if sh_result is not None:
        return sh_result

    logging.info("NOTE: The following diff output is only informational.")
    logging.info("NOTE: The actual verification is done in Python.")
    sh(f"diff --recursive {state.git_dir} {state.source_dir}")

    diff = filecmp.dircmp(state.git_dir, state.source_dir, ignore=[])
    errors: List[str] = []

    # First, check that any files appearing in only one tree are allowed
    errors += _check_dircmp_only_either_allowed(diff)

    # Then make sure that all files that exist in both places have no diff
    errors += _check_dircmp_no_diff_files(diff)
    # And finally that there we could compare all the files
    errors += _check_dircmp_no_funny_files(diff)

    if errors:
        errors.append("See above for a full output of diff.")
        return "\n\n".join(errors)
    return None


@check("No blacklisted files in the source archive", hide_if_passing=True)
def check_blacklisted_files(state: State) -> Optional[str]:
    blacklist = [".git", ".gitignore", ".mvn", "mvnw", "mvnw.cmd", "Jenkinsfile"]
    commands = [
        f"test $(find {state.source_dir} -name {item} | wc -l) -eq 0"
        for item in blacklist
    ]
    return _check_sh(commands)


def _check_file_looks_good(path: str) -> Optional[str]:
    prompt = f"Did the contents of {path} look good to you? [y/N] "
    return _check_sh(
        [f"less {path}", f"read -r -p '{prompt}' response; test \"$response\" == y"]
    )


@check("DISCLAIMER and NOTICE look good")
def check_disclaimer_and_notice_look_good(state: State) -> Optional[str]:
    errors = []
    for path in ["DISCLAIMER", "NOTICE"]:
        result = _check_file_looks_good(os.path.join(state.source_dir, path))
        if result is not None:
            errors.append(result)
    if errors:
        return "\n".join(errors)
    return None


@check("LICENSE is Apache 2.0", hide_if_passing=True)
def check_license_is_apache_2(state: State) -> Optional[str]:
    expected_license_path = os.path.join(state.work_dir, "expected_license")
    actual_license_path = os.path.join(state.source_dir, "LICENSE")
    with open(expected_license_path, "w") as f:
        f.write(apache_2_license.text)
    return _check_sh([f"diff {expected_license_path} {actual_license_path}"])


@check("LICENSE looks good")
def check_license_looks_good(state: State) -> Optional[str]:
    return _check_file_looks_good(os.path.join(state.source_dir, "LICENSE"))


@check("No binary files in the release")
def check_no_binary_files(state: State) -> Optional[str]:
    return _check_sh(
        f"diff <(echo -n) <(find {state.source_dir} -type f "
        "| xargs file | grep -v text | cut -f1 -d:)"
    )


@check("Source release builds cleanly")
def check_build_and_test(state: State) -> Optional[str]:
    return _check_sh(
        [
            "mvn --quiet -N io.takari:maven:wrapper -Dmaven=3.6.0",
            "./mvnw --quiet package",
        ],
        workdir=state.source_dir,
    )


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
    check_blacklisted_files,
    check_disclaimer_and_notice_look_good,
    check_license_is_apache_2,
    check_license_looks_good,
    check_no_binary_files,
    check_build_and_test,
]
