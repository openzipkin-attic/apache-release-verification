import logging
from typing import List, NamedTuple, Optional

from colorama import Fore, Style

from helpers import header


class Result(NamedTuple):
    name: str
    error: Optional[str]

    @staticmethod
    def passed(name: str) -> "Result":
        return Result(name, None)

    @staticmethod
    def failed(name: str, error: str) -> "Result":
        return Result(name, error)

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
        if result.is_passed:
            prefix = f"[{Fore.GREEN}PASS{Style.RESET_ALL}]"
        else:
            prefix = f"[{Fore.RED}FAIL{Style.RESET_ALL}]"
        logging.info(f"{prefix} {result.name}")
        if not result.is_passed:
            logging.info(result.error)

    if report.problem_count == 0:
        logging.info(f"{Fore.GREEN}Everything seems to be in order.{Style.RESET_ALL}")
    else:
        logging.info(
            f"{Fore.RED}Found {report.problem_count} " f"problems.{Style.RESET_ALL}"
        )
