#!/usr/bin/env python3

"""ld_parser - Parsers to generate RDF objects from dictionaries and tabular data."""

from __future__ import annotations

import argparse
import datetime
import logging
import re
import sys
from enum import StrEnum
from pathlib import Path
from typing import Any

import pandas as pd
from rdflib import Graph
from rdflib.namespace import NamespaceManager

from appn_linked_data.ld_constants import (
    ALT_SCHEMA_SCHEMA,
    APPN_SCHEMA,
    APPN_VOCABULARY,
    BIO_SCHEMA,
    CENTRAL_ORGANISATION,
    DC_SCHEMA,
    SKOS_SCHEMA,
)
from appn_linked_data.ld_dictionary import (
    Dictionary,
)
from appn_linked_data.ld_iri import (
    IRI,
    RDF_TYPE,
    SCHEMA_SCHEMA,
    Triple,
)
from appn_linked_data.ld_issue import ISSUE_TYPE, IssueHandler, IssueType
from appn_linked_data.ld_namespaces import NamespaceDefinitionManager
from appn_linked_data.ld_parser import TRAILING_INTEGER_PATTERN, DictParser
from appn_linked_data.ld_settings import (
    LinkedDataSettings,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


### OutputFormat ##############################################################


class OutputFormat(StrEnum):
    """Simple class for vocabulary output formats."""

    TURTLE = "ttl"
    JSON = "json"


### process_argv ##############################################################
#
# Safely process sys.argv, returning a dictionary of option values.
#
#     -n, --node        : Node name (actually name of subfolder under source)
#                         or "all" to process all nodes (subfolders).
#     -m, --mode        : Output mode "json" for JSON-LD or "rdf" for xml/rdf (default)
#     -l, --log-level   : "info" / "error" / "debug".
#     -e,               : Display logging outputs to stderr.
#      --echo-to-stderr
#

ARG_FORMAT = "format"
ARG_NODE = "node"

ARG_VALUE_ALL = "all"


def process_argv(argv: list[str], settings: LinkedDataSettings) -> dict[str, Any]:
    """Parse sys.argv values to extract a list of nodes for processing and a list of output formats.

    :param argv: Arguments from sys.argv.
    :param node_ids: List of abbreviated names for APPN nodes (including APPN for APPN central).
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
    elif ARG_VALUE_ALL in args[ARG_FORMAT]:
        args[ARG_FORMAT] = formats

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


SOURCE_PATH = Path("./src/vocabulary_templates/")
BUILD_PATH = Path("./build/vocabulary/")
EXCEL_SHEET_BASENAME = "VocabularyTemplate_"
EXCEL_SHEET_SUFFIX = ".xlsx"
VOCABULARY_BASENAME = "_vocabulary"


def verify_existing_terms(
    latest_version: Dictionary, published_version: Dictionary
) -> None:
    """Ensure backwards compatibility for vocabulary.

    All instances defined in the previous version of the
    vocabulary should be retained, and all instances should
    still belong to previously defined types.

    Warn the user of issues, but make necessary corrections.

    :param latest_version: Dictionary of the new version to validate.
    :param published_version: Dictionary of current live version.
    """
    instance_type_query = "SELECT ?x ?y WHERE { ?x rdf:type ?y }"

    old_instances = published_version.list_unique_subjects()
    old_types = published_version.query(instance_type_query)
    old_type_dictionary: dict[IRI, list[IRI]] = {}
    for old_type in old_types:
        if old_type[0] not in old_type_dictionary:
            old_type_dictionary[old_type[0]] = []  # type: ignore[index]
        old_type_dictionary[old_type[0]].append(old_type[1])  # type: ignore[index, arg-type]

    new_instances = latest_version.list_unique_subjects()
    new_types = latest_version.query(instance_type_query)
    new_type_dictionary: dict[IRI, list[IRI]] = {}
    for new_type in new_types:
        if new_type[0] not in new_type_dictionary:
            new_type_dictionary[new_type[0]] = []  # type: ignore[index]
        new_type_dictionary[new_type[0]].append(new_type[1])  # type: ignore[index, arg-type]

    for instance in old_instances:
        if instance not in new_instances:
            logger.warning(
                "Published version of vocabulary includes a term %s - adding to the new version",
                instance.curie,
                extra={ISSUE_TYPE: IssueType.MISSING_INSTANCE},
            )
            for triple in published_version.list_triples_for_subject(instance):
                latest_version.add_triple(triple)
        else:
            missing_types: list[IRI] = sorted(
                old_type
                for old_type in old_type_dictionary[instance]
                if old_type not in new_type_dictionary[instance]
            )
            # Ignore cases where the previously reported class is a superclass for one of the
            # reported classes
            reportable_types: list[IRI] = []
            for missing_type in missing_types:
                subclasses = latest_version.list_subclasses(missing_type)
                if not any(
                    subclass in new_type_dictionary[instance] for subclass in subclasses
                ):
                    reportable_types.append(missing_type)
            if len(reportable_types) > 0:
                logger.warning(
                    "Published term %s has missing types: %s - adding these to the new version",
                    instance.curie,
                    ", ".join(
                        [reportable_type.curie for reportable_type in reportable_types]
                    ),
                    extra={ISSUE_TYPE: IssueType.MISSING_INSTANCE_TYPE},
                )
                for missing_type in missing_types:
                    latest_version.add_triple(Triple(instance, RDF_TYPE, missing_type))


def underline(text: str, underline_character: str = "-") -> str:
    """Add aligned underlining text below text (allowing for leading and trailing blanks).

    Repeat the supplied or default underline character in a new line starting
    at the first non-whitespace character in the original line and ending with
    the last non-whitespace character. Any single whitespace character between
    these points will be part of the underlined section.

    :param text: Text to underline.
    :param underline_character: Character to use for underlining.
    :return: Two lines of text, one containing underlining.
    """
    if len(underline_character) > 0:
        underline_character = underline_character[0]
    else:
        underline_character = "-"

    underline = re.sub(r"\S", underline_character, text)
    underline = re.sub(r"\S\s\S", underline_character * 3, underline)

    return f"{text}\n{underline}"


### MAIN PROGRAM ##############################################################
#
# Parse arguments and set up logging. Based on arguments, scan one or all
# source folders for all Excel spreadheets and generate a JSON-LD vocabulary
# for all schema class instances included.
#
if __name__ == "__main__":
    settings = LinkedDataSettings()

    args = process_argv(sys.argv, settings)

    nodes = args["node"]
    formats = args["format"]

    timestamp = datetime.datetime.now(datetime.UTC).isoformat()

    BUILD_PATH.mkdir(parents=True, exist_ok=True)

    appn_vocabulary_path = None

    # Generate vocabulary for each selected node in turn.
    for node in nodes:
        issue_handler = IssueHandler()
        logger.addHandler(issue_handler)

        dictionary = Dictionary()
        dictionary.load(APPN_SCHEMA)
        dictionary.load(SKOS_SCHEMA)
        dictionary.load(DC_SCHEMA)
        if node != CENTRAL_ORGANISATION:
            dictionary.load(APPN_VOCABULARY, asset_path=appn_vocabulary_path)
        dictionary.import_references()

        appn_classes_by_name = {
            c.name: c for c in dictionary.list_classes(namespace=APPN_SCHEMA)
        }

        organisation = settings.get_organisation_by_id(node)

        graph = Graph()
        namespace_manager = NamespaceManager(graph)
        namespace_definitions = NamespaceDefinitionManager().get_namespace_dictionary()
        namespace_manager.bind(
            namespace_definitions[ALT_SCHEMA_SCHEMA].prefix, ALT_SCHEMA_SCHEMA
        )
        namespace_manager.bind(
            namespace_definitions[SCHEMA_SCHEMA].prefix, SCHEMA_SCHEMA
        )

        # Ensure the vocabulary graph uses the preferred namespace prefixes
        graph.bind(organisation.prefix, organisation.namespace, override=True)  # type: ignore[union-attr]
        graph.bind(
            namespace_definitions[APPN_SCHEMA].prefix, APPN_SCHEMA, override=True
        )
        graph.bind(namespace_definitions[BIO_SCHEMA].prefix, BIO_SCHEMA)
        if node != CENTRAL_ORGANISATION:
            appn = LinkedDataSettings().get_appn()
            graph.bind(appn.prefix, appn.namespace)

        excel_template = f"{EXCEL_SHEET_BASENAME}{node}{EXCEL_SHEET_SUFFIX}"
        excel_path = SOURCE_PATH / excel_template

        if not excel_path.exists():
            logger.error(
                "Excel path %s invalid",
                excel_path,
                extra={ISSUE_TYPE: IssueType.EXCEL_PATH_INVALID},
            )
            break

        for sheet in pd.ExcelFile(excel_path).sheet_names:
            # Process any sheet with a name matching an APPN schema class name OR
            # mapped to a class name using `sheet_aliases`
            sheet_class = LinkedDataSettings().get_sheet_aliases().get(sheet, sheet)  # type: ignore[arg-type]
            if sheet_class in appn_classes_by_name:
                class_ = appn_classes_by_name[sheet_class]

                parser = DictParser(
                    dictionary,
                    class_,
                    organisation,  # type: ignore[arg-type]
                    graph=graph,
                    generate_concepts=True,
                )

                try:
                    excel_sheet_dataframe = pd.read_excel(
                        excel_path, sheet_name=sheet, header=None, dtype="str"
                    )
                except Exception:
                    logger.exception(
                        "Excel sheet %s in %s unreadable",
                        sheet,
                        excel_path,
                        extra={ISSUE_TYPE: IssueType.EXCEL_SHEET_INVALID},
                    )
                    break

                column_name_matches: dict[str, int] = {}
                columns: list[str] = []
                for heading in excel_sheet_dataframe.loc[0, :].array:
                    column_name = TRAILING_INTEGER_PATTERN.sub("", heading.strip())
                    if column_name not in column_name_matches:
                        column_name_matches[column_name] = 0
                    else:
                        column_name_matches[column_name] = (
                            column_name_matches[column_name] + 1
                        )
                        column_name = f"{column_name}{column_name_matches[column_name]}"
                    columns.append(column_name)
                excel_sheet_dataframe.columns = columns
                excel_sheet_dataframe = excel_sheet_dataframe.drop(0).dropna(how="all")

                for _, row in excel_sheet_dataframe.iterrows():
                    parser.parse(row)

        vocabulary_path = Path("/home/dhobern/Downloads/") / f"{node}_vocabulary.ttl"
        graph.serialize(destination=vocabulary_path)
        if node == CENTRAL_ORGANISATION:
            appn_vocabulary_path = vocabulary_path
