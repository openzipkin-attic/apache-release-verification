import logging
from typing import List, NamedTuple, Optional

from colorama import Fore, Style

from helpers import header


class Result(NamedTuple):
    name: str
    hide_if_passing: bool
    error: Optional[str]

    @staticmethod
    def passed(name: str, hide_if_passing: bool) -> "Result":
        return Result(name, hide_if_passing, None)

    @staticmethod
    def failed(name: str, hide_if_passing: bool, error: str) -> "Result":
        return Result(name, hide_if_passing, error)

    @property
    def is_passed(self) -> bool:
        return self.error is None


class Report(NamedTuple):
    results: List[Result]

    @property
    def problem_count(self) -> int:
        problems = 0
        for result in self.results:
            if not result.is_passed:
                problems += 1
        return problems


def print_report(report: Report) -> None:
    header("Summary follows")
    for result in report.results:
        if result.is_passed and result.hide_if_passing:
            continue
        if result.is_passed:
            prefix = f"[{Fore.GREEN}PASS{Style.RESET_ALL}]"
        else:
            prefix = f"[{Fore.RED}FAIL{Style.RESET_ALL}]"
        logging.info(f"{prefix} {result.name}")
        if not result.is_passed:
            logging.info(result.error)
