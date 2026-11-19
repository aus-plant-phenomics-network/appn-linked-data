#!/usr/bin/env python3

"""Tests for `appn_linked_data.spreadsheet_parser`."""

from __future__ import annotations

from pathlib import Path
from subprocess import PIPE, Popen

import pytest
from appn_logging import collect_records

from appn_linked_data import (
    APPN_SCHEMA,
    APPN_VOCABULARY,
    IRI,
    Dictionary,
)
from appn_linked_data.ld_issue import ISSUE_TYPE

# These tests run explorer.py in a separate process, so they belong in the
# integration stage (pyproject.toml: "crosses a real boundary").
pytestmark = pytest.mark.integration

TEST_SPREADSHEET = Path("tests/appn-test-excel-form.xlsx")
TEST_NAMESPACE = "https://data.plantphenomics.org.au/AU/Tralee_123/"
TEST_PREFIX = "tralee"


def test_parser() -> None:
    assert TEST_SPREADSHEET.exists()
    turtle_path = TEST_SPREADSHEET.with_suffix(".ttl")
    report_path = TEST_SPREADSHEET.parent / f"{TEST_SPREADSHEET.stem}_report.txt"
    if turtle_path.exists():
        turtle_path.unlink()
    if report_path.exists():
        report_path.unlink()

    with (
        collect_records(key=ISSUE_TYPE) as logged_issues,
        Popen(  # noqa: S603 RUF100
            [  # noqa: S607
                "python",
                "src/appn_linked_data/spreadsheet_parser.py",
                "-n",
                TEST_NAMESPACE,
                "-p",
                TEST_PREFIX,
                "-o",
                "AU",
                TEST_SPREADSHEET,
            ],
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
        ) as parser,
    ):
        out, err = parser.communicate()
        assert len(out) == 0
        assert b"INFO" in err
        assert b"WARN" not in err
        assert b"ERROR" not in err
        assert turtle_path.exists()
        assert report_path.exists()
        assert len(list(logged_issues)) == 0
        inspector = Dictionary()
        inspector.load(TEST_NAMESPACE, turtle_path, TEST_PREFIX)
        instances = inspector.list_unique_subjects(namespace=TEST_NAMESPACE)
        for iri in [
            IRI(f"{TEST_PREFIX}:{name}")
            for name in ["person_MulligatawnyTempleton", "role_Funder"]
        ]:
            assert iri in instances
        objects = inspector.list_unique_objects(namespace=APPN_SCHEMA)
        for iri in [
            IRI(f"appn:{name}")
            for name in [
                "Grant",
                "Role",
                "Person",
                "Organisation",
                "Study",
                "Investigation",
                "GrowthFacility",
                "BiologicalMaterial",
            ]
        ]:
            assert iri in objects
        objects = inspector.list_unique_objects(namespace=APPN_VOCABULARY)
        for iri in [IRI(f"appnid:{name}") for name in ["bm_Barley"]]:
            assert iri in objects

    if turtle_path.exists():
        turtle_path.unlink()
    if report_path.exists():
        report_path.unlink()
