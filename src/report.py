import logging
from enum import Enum, auto
from math import ceil, floor
from typing import List, NamedTuple, Optional

from colorama import Fore, Style

from helpers import header


class ResultKind(Enum):
    PASS = auto()
    FAIL = auto()
    WARN = auto()
    NOTE = auto()
    ERROR = auto()


RESULT_STYLES = {
    ResultKind.PASS: Fore.GREEN,
    ResultKind.FAIL: Fore.RED,
    ResultKind.WARN: Fore.YELLOW,
    ResultKind.NOTE: Fore.BLUE,
    ResultKind.ERROR: Fore.RED,
}


class Result(NamedTuple):
    name: str
    hide_if_passing: bool
    message: Optional[str]
    kind: ResultKind

    @staticmethod
    def passed(name: str, hide_if_passing: bool) -> "Result":
        return Result(name, hide_if_passing, None, ResultKind.PASS)

    @staticmethod
    def failed(
        name: str, hide_if_passing: bool, message: str, kind: ResultKind
    ) -> "Result":
        return Result(name, hide_if_passing, message, kind)

    @property
    def is_passed(self) -> bool:
        return self.kind is ResultKind.PASS


class Report(NamedTuple):
    results: List[Result]

    @property
    def problem_count(self) -> int:
        problems = 0
        for result in self.results:
            if not result.is_passed:
                problems += 1
        return problems


def color_result(msg: str, kind: ResultKind) -> str:
    prefix = RESULT_STYLES.get(kind, "")
    return f"{prefix}{msg}{Style.RESET_ALL}"


def print_report(report: Report) -> None:
    header("Summary follows")
    max_len = max(len(result.kind.name) for result in report.results)
    for result in report.results:
        if result.is_passed and result.hide_if_passing:
            continue
        padding_left = " " * ceil((max_len - len(result.kind.name)) / 2.0)
        padding_right = " " * floor((max_len - len(result.kind.name)) / 2.0)
        prefix = color_result(result.kind.name, result.kind)
        logging.info(f"[{padding_left}{prefix}{padding_right}] {result.name}")
        if not result.is_passed:
            logging.info(result.message)
