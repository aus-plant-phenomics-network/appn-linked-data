#!/usr/bin/env python3

"""spreadsheet_parser - CLI to Excel spreadsheet datasets."""

from __future__ import annotations

import argparse
import logging
import sys
import textwrap
from pathlib import Path
from typing import Any

from appn_linked_data.ld_issue import IssueHandler
from appn_linked_data.ld_parser import ExcelParser, OutputFormat
from appn_linked_data.ld_settings import (
    LinkedDataSettings,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


### process_argv ##############################################################

ARG_FORMAT = "format"
ARG_NODE = "node"
ARG_ORGANISATION = "organisation"
ARG_NAMESPACE = "namespace"
ARG_PREFIX = "prefix"
ARG_SPREADSHEET = "spreadsheet"

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

    node_ids: list[str] = sorted(settings.get_organisations().keys())
    parser.add_argument(
        "-o",
        "--organisation",
        choices=([*node_ids]),
        help="APPN organisation node abbreviated name.",
        required=True,
    )

    parser.add_argument(
        "-n",
        "--namespace",
        help="Namespace for output graph.",
        required=True,
    )

    parser.add_argument(
        "-p",
        "--prefix",
        help="Prefix for output graph.",
        required=True,
    )

    parser.add_argument(
        "spreadsheet",
        help="File path for Excel spreadsheer.",
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
    settings = LinkedDataSettings()

    args = process_argv(sys.argv, settings)

    spreadsheet = Path(args["spreadsheet"])
    if not spreadsheet.exists():
        logger.error("Spreadsheet %s does not exist", str(Path))
        sys.exit(1)

    formats = args[ARG_FORMAT]
    namespace = args[ARG_NAMESPACE]
    prefix = args[ARG_PREFIX]
    organisation = settings.get_organisation_by_id(args[ARG_ORGANISATION])

    with IssueHandler() as issue_handler:
        parser = ExcelParser(
            organisation, generate_concepts=False, namespace=namespace, prefix=prefix
        )
        parser.parse(spreadsheet)
        parser.validate()

        for output_format in formats:
            linked_data_path = spreadsheet.with_suffix(f".{output_format.value}")
            parser.serialize(linked_data_path, output_format=output_format.value)

        report_path = spreadsheet.parent / f"{spreadsheet.stem}_report.txt"
        with report_path.open("w") as report:
            issues = issue_handler.get_issues(True)
            if len(issues) == 0:
                report.write(
                    f"No issues detected generating linked data for {organisation.name} dataset {namespace}\n"
                )
            else:
                report.write(
                    f"Issues detected generating linked data for {organisation.name} dataset {namespace}\n"
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
