#!/usr/bin/env python3

"""ld_parser - Parsers to generate RDF objects from dictionaries and tabular data."""

from __future__ import annotations

import argparse
import datetime
import logging
import sys
import textwrap
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
    Organisation,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())


### OutputFormat ##############################################################


class OutputFormat(StrEnum):
    """Simple class for vocabulary output formats."""

    TURTLE = "ttl"
    JSON = "json"


class ExcelVocabularyParser:
    """Parser to generate RDF vocabularies from Excel spreadsheets.

    This class expects spreadsheets with sheet names matching the names
    of APPN schema classes, column names matching APPN, SKOS or DCTERMS
    property names for the sheet class, and values that fit the
    expectes property. There must be a "name" column in each sheet. It
    is used to construct an IRI for a class instance. Values in any
    columns for APPN schema properties with ranges including APPN
    schema classes will also be mapped to IRIs.
    """

    def __init__(self, organisation: Organisation) -> None:
        """Initialise parser.

        Load schema assets required to construct the vocabulary.

        :param organisation: `Organisation` representing the node or APPN central.
        """
        self.organisation = organisation

        # Load schemas that will be used in the processing. For any node
        # vocabulary, include the current APPN central vocabulary so its
        # class instances can be referenced wherever relevant.
        self.dictionary = Dictionary()
        self.dictionary.load(APPN_SCHEMA)
        self.dictionary.load(SKOS_SCHEMA)
        self.dictionary.load(DC_SCHEMA)
        if node != CENTRAL_ORGANISATION:
            self.dictionary.load(APPN_VOCABULARY, asset_path=appn_vocabulary_path)
        self.dictionary.import_references()

        # Create a graph to contain the new vocabulary and initialise the
        # required namespaces.
        self.graph = Graph()
        namespace_manager = NamespaceManager(self.graph)
        namespace_definitions = NamespaceDefinitionManager().get_namespace_dictionary()
        # Make sure the correct schema.org domain is used.
        namespace_manager.bind(
            namespace_definitions[ALT_SCHEMA_SCHEMA].prefix, ALT_SCHEMA_SCHEMA
        )
        namespace_manager.bind(
            namespace_definitions[SCHEMA_SCHEMA].prefix, SCHEMA_SCHEMA
        )
        # Ensure the vocabulary graph uses the preferred namespace prefixes
        self.graph.bind(organisation.prefix, organisation.namespace, override=True)  # type: ignore[union-attr]
        self.graph.bind(
            namespace_definitions[APPN_SCHEMA].prefix, APPN_SCHEMA, override=True
        )
        self.graph.bind(namespace_definitions[BIO_SCHEMA].prefix, BIO_SCHEMA)
        if organisation.id != CENTRAL_ORGANISATION:
            appn = LinkedDataSettings().get_appn()
            self.graph.bind(appn.prefix, appn.namespace)

        # Convenience dictionary for checking class names.
        self.appn_classes_by_name = {
            c.name: c for c in self.dictionary.list_classes(namespace=APPN_SCHEMA)
        }

    def parse(self, excel_path: Path) -> None:
        """Read Excel spreadsheet and parse all instances.

        Read the sheet with `pandas`, but load the column headings as the first
        row and normalise column names. This allows a column name to be repeated.
        Each use of the same column name gets a unique name based on a trailing
        decimal integer. Once the unique column names are assigned, drop the first
        row,

        Construct a `DictParser` for each sheet and parse all rows.

        :param excel_path: Path to Excel file.
        """
        try:
            for sheet in pd.ExcelFile(excel_path).sheet_names:
                # Process any sheet with a name matching an APPN schema class name OR
                # mapped to a class name using `sheet_aliases`
                sheet_class = LinkedDataSettings().get_sheet_aliases().get(sheet, sheet)  # type: ignore[arg-type]
                if sheet_class in self.appn_classes_by_name:
                    appn_class = self.appn_classes_by_name[sheet_class]

                    parser = DictParser(
                        self.dictionary,
                        appn_class,
                        self.organisation,  # type: ignore[arg-type]
                        graph=self.graph,
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
                            extra={ISSUE_TYPE: IssueType.EXCEL_SHEET_ERROR},
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
                            column_name = (
                                f"{column_name}{column_name_matches[column_name]}"
                            )
                        columns.append(column_name)
                    excel_sheet_dataframe.columns = columns
                    excel_sheet_dataframe = excel_sheet_dataframe.drop(0).dropna(
                        how="all"
                    )

                    for _, row in excel_sheet_dataframe.iterrows():
                        parser.parse(row)

        except Exception:
            logger.exception(
                "Error parsing Excel spreadsheet",
                extra={ISSUE_TYPE: IssueType.EXCEL_SHEET_ERROR},
            )

    def verify_referenced_objects(self) -> bool:
        """Check that all objects referenced in this namespace have been defined.

        Compare objects of triples with subjects.

        :return: True if all objects have been defined.
        """
        latest_version = Dictionary(self.graph)

        subjects = latest_version.list_unique_subjects(
            namespace=self.organisation.namespace
        )
        objects = latest_version.list_unique_objects(
            namespace=self.organisation.namespace
        )

        missing = [o for o in objects if o not in subjects]
        for iri in missing:
            logger.error(
                "The vocabulary references an undefined instance %s",
                iri.curie,
                extra={ISSUE_TYPE: IssueType.MISSING_REFERENCE},
            )

        return len(missing) == 0

    def verify_existing_terms(self, add_missing_terms: bool = True) -> bool:
        """Ensure backwards compatibility for vocabulary.

        All instances defined in the previous version of the
        vocabulary should be retained, and all instances should
        still belong to previously defined types.

        Warn the user of issues, and optionally make necessary corrections.

        :param add_missing_terms: If true, add triples to the graph as necessary.
        :return: True if the vocabulary satisfied all checks before any additions were made.
        """
        all_present = True

        published_version = Dictionary()
        published_version.load(self.organisation.namespace)  # type: ignore[arg-type]

        latest_version = Dictionary(self.graph)

        published_instances = published_version.list_unique_subjects()
        published_type_dictionary = self.get_types_for_instances(published_version)

        latest_instances = latest_version.list_unique_subjects()
        latest_type_dictionary = self.get_types_for_instances(latest_version)

        for instance in published_instances:
            if instance not in latest_instances:
                all_present = False
                logger.warning(
                    "Published version of vocabulary includes a term %s - adding to the new version",
                    instance.curie,
                    extra={ISSUE_TYPE: IssueType.MISSING_INSTANCE},
                )
                if add_missing_terms:
                    for triple in published_version.list_triples_for_subject(instance):
                        latest_version.add_triple(triple)
            else:
                missing_types: list[IRI] = sorted(
                    published_type
                    for published_type in published_type_dictionary[instance]
                    if published_type not in latest_type_dictionary[instance]
                )
                # Ignore cases where the previously reported class is a superclass for one of the
                # reported classes
                reportable_types: list[IRI] = []
                for missing_type in missing_types:
                    subclasses = latest_version.list_subclasses(missing_type)
                    if not any(
                        subclass in latest_type_dictionary[instance]
                        for subclass in subclasses
                    ):
                        reportable_types.append(missing_type)
                if len(reportable_types) > 0:
                    all_present = False
                    logger.warning(
                        "Published term %s has missing types: %s - adding these to the new version",
                        instance.curie,
                        ", ".join(
                            [
                                reportable_type.curie
                                for reportable_type in reportable_types
                            ]
                        ),
                        extra={ISSUE_TYPE: IssueType.MISSING_INSTANCE_TYPE},
                    )
                    if add_missing_terms:
                        for missing_type in missing_types:
                            latest_version.add_triple(
                                Triple(instance, RDF_TYPE, missing_type)
                            )

        return all_present

    def get_types_for_instances(self, dictionary: Dictionary) -> dict[IRI, list[IRI]]:
        """Get list of explicit types for all instances in a `Dictionary`.

        Query Dictionary for the subject and object of all `rdf:type` properties
        and organise these as a dictionary keyed by instance IRI and with lists
        of type IRIs as values.

        :param dictionary: The `Dictionary` to be queried.
        :return: Instance types organised by instance IRI.
        """
        instance_type_dictionary: dict[IRI, list[IRI]] = {}
        instance_types = dictionary.query("SELECT ?x ?y WHERE { ?x rdf:type ?y }")
        for instance_iri, instance_type in instance_types:
            if instance_iri not in instance_type_dictionary:
                instance_type_dictionary[instance_iri] = []  # type: ignore[index]
            instance_type_dictionary[instance_iri].append(instance_type)  # type: ignore[index, arg-type]
        return instance_type_dictionary

    def validate(self) -> bool:
        """Perform final validation steps for vocabulary.

        Reports whether issues were detected, even if the issues were fixed.

        :return: True no issues were detected.
        """
        return self.verify_existing_terms() and self.verify_referenced_objects()

    def serialize(self, vocabulary_path: Path) -> bool:
        """Write the vocabulary to a file.

        :param vocabulary_path: Path for output file.
        :param format: Specifies linked data output format, with Turtle as default.
        :return: True if successful.
        """
        self.graph.serialize(destination=vocabulary_path)
        return True


### process_argv ##############################################################

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

            with IssueHandler() as issue_handler:
                if not excel_path.exists():
                    logger.error(
                        "Excel path %s invalid",
                        excel_path,
                        extra={ISSUE_TYPE: IssueType.EXCEL_PATH_INVALID},
                    )
                    break

                parser = ExcelVocabularyParser(organisation)
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
                    issues = issue_handler.get_issues(True)
                    if len(issues) == 0:
                        report.write(
                            f"No issues detected generating vocabulary for {organisation.name} at {timestamp}\n"
                        )
                    else:
                        report.write(
                            f"Issues detected generating vocabulary for {organisation.name} at {timestamp}\n\n"
                        )

                        for log_level, issue_types in issues.items():
                            report.write(
                                f"Issues at level: {logging.getLevelName(log_level).upper()}\n"
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
