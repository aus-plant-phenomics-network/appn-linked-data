#!/usr/bin/env python3

"""vocabulariser - CLI to run parsers for Excel spreadsheet vocabularies."""

from __future__ import annotations

import argparse
import datetime
import logging
import sys
import textwrap
from pathlib import Path
from typing import Any

from appn_logging import collect_records, configure_logging

from appn_linked_data.ld_constants import (
    CENTRAL_ORGANISATION,
)
from appn_linked_data.ld_issue import ISSUE_TYPE, IssueType
from appn_linked_data.ld_parser import ExcelParser, OutputFormat
from appn_linked_data.ld_settings import (
    LinkedDataSettings,
)

logger = logging.getLogger(__name__)

### process_argv ##############################################################

ARG_FORMAT = "format"
ARG_NODE = "node"

ARG_VALUE_ALL = "all"


def process_argv(argv: list[str], settings: LinkedDataSettings) -> dict[str, Any]:
    """Parse sys.argv values to extract a list of nodes for processing and a list of output formats.

    :param argv: Arguments from sys.argv.
    :return: Processed arguments
    """
    parser = argparse.ArgumentParser(
        prog=argv[0],
        description=f"{argv[0]}: Generate linked-data outputs from APPN node vocabulary sheets",
    )

    formats = [output_format.value for output_format in OutputFormat]
    parser.add_argument(
        "-f",
        "--format",
        choices=([*formats, ARG_VALUE_ALL]),
        action="append",
        help=f"Output format (default: {OutputFormat.TURTLE}) or 'all' (for all supported formats).",
    )

    # The list of node_ids should start with APPN so any central changes get processed first.
    node_ids: list[str] = sorted(settings.get_organisations().keys())
    parser.add_argument(
        "-n",
        "--node",
        choices=([*node_ids, ARG_VALUE_ALL]),
        action="append",
        help="APPN node abbreviated name or 'all' (default).",
    )

    args = vars(parser.parse_args(argv[1:]))

    if ARG_FORMAT not in args or args[ARG_FORMAT] is None:
        args[ARG_FORMAT] = [OutputFormat.TURTLE]
    else:
        if ARG_VALUE_ALL in args[ARG_FORMAT]:
            args[ARG_FORMAT] = formats
        args[ARG_FORMAT] = [OutputFormat(arg) for arg in args[ARG_FORMAT]]

    if OutputFormat.TURTLE in args[ARG_FORMAT]:
        args[ARG_FORMAT].remove(OutputFormat.TURTLE)
        args[ARG_FORMAT].insert(0, OutputFormat.TURTLE)

    if (
        ARG_NODE not in args
        or args[ARG_NODE] is None
        or ARG_VALUE_ALL in args[ARG_NODE]
    ):
        args[ARG_NODE] = node_ids

    if CENTRAL_ORGANISATION in args[ARG_NODE]:
        args[ARG_NODE].remove(CENTRAL_ORGANISATION)
        args[ARG_NODE].insert(0, CENTRAL_ORGANISATION)

    return args


### wrap_text #################################################################


def wrap_text(
    text: str, width: int, initial_indent: int, subsequent_indent: int
) -> str:
    """Utility wrapper around `textwrap.wrap`."""
    rows = textwrap.wrap(
        text,
        width=width,
        initial_indent=" " * initial_indent,
        subsequent_indent=" " * subsequent_indent,
    )
    return "\n".join(rows).strip()


SOURCE_PATH = Path("./src/vocabulary_templates/")
BUILD_PATH = Path("./build/vocabulary/")
EXCEL_SHEET_BASENAME = "VocabularyTemplate_"
EXCEL_SHEET_SUFFIX = ".xlsx"
VOCABULARY_BASENAME = "_vocabulary"

### MAIN PROGRAM ##############################################################

if __name__ == "__main__":
    configure_logging()

    settings = LinkedDataSettings()

    args = process_argv(sys.argv, settings)

    nodes = args["node"]
    formats = args["format"]

    timestamp = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")

    BUILD_PATH.mkdir(parents=True, exist_ok=True)

    appn_vocabulary_path = None

    # Generate vocabulary for each selected node in turn.
    for node in nodes:
        organisation = settings.get_organisation_by_id(node)
        if organisation is not None:
            excel_spreadsheet = f"{EXCEL_SHEET_BASENAME}{node}{EXCEL_SHEET_SUFFIX}"
            excel_path = SOURCE_PATH / excel_spreadsheet

            with collect_records(key=ISSUE_TYPE) as logged_issues:
                if not excel_path.exists():
                    logger.error(
                        "Excel path %s invalid",
                        excel_path,
                        extra={ISSUE_TYPE: IssueType.EXCEL_PATH_INVALID},
                    )
                    break

                parser = ExcelParser(
                    organisation,
                    appn_vocabulary_path=appn_vocabulary_path,
                    generate_concepts=True,
                    load_organisation_vocabulary=False,
                )
                parser.parse(excel_path)
                parser.validate()

                appn_vocabulary_checked = False
                for output_format in formats:
                    vocabulary_path = (
                        BUILD_PATH / f"{node}_vocabulary.{output_format.value}"
                    )
                    parser.serialize(vocabulary_path)

                    if node == CENTRAL_ORGANISATION and not appn_vocabulary_checked:
                        appn_vocabulary_path = vocabulary_path
                        appn_vocabulary_checked = True

                report_path = BUILD_PATH / f"{node}_report.txt"
                with report_path.open("w") as report:
                    issues: dict[int, dict[IssueType, list[logging.LogRecord]]] = {}
                    for log_record in logged_issues:
                        levelno = log_record.levelno
                        if levelno not in issues:
                            issues[levelno] = {}
                        issue_type = log_record.__dict__[ISSUE_TYPE]
                        if issue_type not in issues[levelno]:
                            issues[levelno][issue_type] = []
                        issues[levelno][issue_type].append(log_record)
                    if len(issues) == 0:
                        report.write(
                            f"No issues detected generating vocabulary for {organisation.name} at {timestamp}\n"
                        )
                    else:
                        report.write(
                            f"Issues detected generating vocabulary for {organisation.name} at {timestamp}\n"
                        )

                        for log_level in sorted(issues.keys(), reverse=True):
                            issue_types = issues[log_level]
                            report.write(
                                f"\nIssues at level: {logging.getLevelName(log_level).upper()}\n"
                            )
                            for issue_type, log_records in issue_types.items():
                                report.write(
                                    f"\n    Issue type:    {wrap_text(issue_type.value, 100, 19, 19)}\n\n"
                                )
                                if issue_type.suggested_fix is not None:
                                    report.write(
                                        f"    Suggested fix: {wrap_text(issue_type.suggested_fix, 100, 19, 19)}\n\n"
                                    )
                                if len(log_records) == 1:
                                    report.write("    The issue occurred once:\n")
                                else:
                                    report.write(
                                        f"    The issue occurred {len(log_records)} times:\n"
                                    )
                                for index in range(len(log_records)):
                                    log_record = log_records[index]
                                    report.write(
                                        f"    {index + 1:>4d}: {wrap_text(log_record.getMessage(), 100, 10, 10)}\n"
                                    )
