from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    repo: str
    project: str
    module: Optional[str]
    version: str
    incubating: bool
    zipname_template: str
    sourcedir_template: str
    github_reponame_template: str
    gpg_key: str
    git_hash: str
    build_and_test_command: Optional[str]
    verbose: bool
