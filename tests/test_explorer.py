#!/usr/bin/env python3

"""Tests for `appn_linked_data.ld_explorer`."""

from __future__ import annotations

from collections import namedtuple
from subprocess import PIPE, STDOUT, Popen

import pytest

from appn_linked_data import (
    APPN_SCHEMA,
    UQ_VOCABULARY,
)

ExplorerTest = namedtuple("ExplorerTest", ["name", "args", "expected", "not_expected"])
"""Simple class to manage a test of explorer.py.

:param name: Name of the test.
:param args: Argument string to explorer command line.
:param expected: Strings expected in result from command.
:param object: Strings not expected in result from command.
"""


# Since explorer.py reads from stdin and writes to stdout, these tests are fed to a
# single process running explorer.py and the results for each test are separated
# out and checked against the test strings.

EXPLORER_TESTS = [
    ExplorerTest(
        "classes", b"classes\n", ["rdfs:Class", "appn:Trait"], ["xyz:Nothing"]
    ),
    ExplorerTest("classes_appn", b"classes -n appn\n", ["appn:Trait"], ["rdfs:Class"]),
    ExplorerTest(
        "namespaces", b"namespaces\n", ["appn", "ppeo", APPN_SCHEMA, UQ_VOCABULARY], []
    ),
    ExplorerTest("triples", b"triples\n", ["cdi:", "dwc:", "au:"], ["xyz:"]),
    ExplorerTest(
        "instances_growth_facility",
        b"instances appn:GrowthFacility\n",
        ["gf_"],
        ["dwc:"],
    ),
    ExplorerTest(
        "instances_specific_thing", b"instances-specific schema:Thing\n", [], ["gf_"]
    ),
    ExplorerTest("subject_trait", b"subject appn:Trait\n", ["rdfs:Class"], ["au:"]),
    ExplorerTest(
        "property_in_scheme",
        b"property appn:hasGrowthFacilityType\n",
        ["gf_"],
        ["sensor"],
    ),
    ExplorerTest("object", b"object appn:BiologicalMaterial\n", ["Barley"], []),
    ExplorerTest("type", b"type appnid:bm_Barley\n", ["BiologicalMaterial"], []),
    ExplorerTest(
        "superclasses",
        b"superclasses appn:Sample\n",
        ["appn:ObservationUnit", "appn:BiologicalUnit", "schema:", "sosa:"],
        [],
    ),
    ExplorerTest(
        "superproperties", b"superproperties schema:name\n", ["rdfs:label"], ["appn"]
    ),
    ExplorerTest(
        "subclasses", b"subclasses schema:Observation\n", ["appn:Observation"], []
    ),
    ExplorerTest(
        "subproperties",
        b"subproperties sosa:hasFeatureOfInterest\n",
        ["appn:isForObservationUnit"],
        [],
    ),
    ExplorerTest(
        "domain_properties",
        b"domain-properties appn:GrowthFacility\n",
        ["appn:hasGrowthFacilityType", "schema:name", "sosa:isFeatureOfInterestOf"],
        [],
    ),
    ExplorerTest(
        "range_properties",
        b"range-properties appn:Sensor\n",
        ["appn:hosts", "sosa:hosts"],
        [],
    ),
    ExplorerTest(
        "domain_classes",
        b"domain-classes appn:usedMethod\n",
        ["appn:Assay", "sosa:Actuation"],
        ["appn:GrowthFacility"],
    ),
    ExplorerTest(
        "range_classes",
        b"range-classes appn:usedMethod\n",
        ["appn:Method", "sosa:Procedure"],
        [],
    ),
    ExplorerTest(
        "domain_range_properties",
        b"domain-range-properties appn:GrowthFacility appn:Sensor\n",
        ["appn:hosts"],
        [],
    ),
    ExplorerTest("properties", b"properties -n ppeo\n", ["ppeo:hasTrait"], ["appn:"]),
    ExplorerTest(
        "unique_subjects",
        b"unique-subjects -n appn\n",
        ["appn:Sample", "appn:usedMethod"],
        ["au:", "appnid:"],
    ),
    ExplorerTest(
        "unique_properties",
        b"unique-properties -n appn\n",
        ["appn:usedMethod"],
        ["appnid", "appn:Sample"],
    ),
    ExplorerTest(
        "unique_objects", b"unique-objects -n appn\n", ["appn:Scale"], ["au:", "uq:"]
    ),
    ExplorerTest(
        "property_name", b"property-name name\n", ["schema:name"], ["rdfs:label"]
    ),
    ExplorerTest(
        "property_name_all",
        b"property-name-all name\n",
        ["schema:name"],
        ["rdfs:label"],
    ),
    ExplorerTest(
        "instance_name_millimeter",
        b"instance-name millimeter\n",
        ["Millimeter"],
        ["mm"],
    ),
    ExplorerTest("instance_name_mm", b"instance-name mm\n", [], ["mm", "Millimeter"]),
    ExplorerTest(
        "instance_name_all", b"instance-name-all mm\n", ["Millimeter"], ["mm"]
    ),
    ExplorerTest(
        "instance_class_name_millimeter",
        b"instance-class-name appn:Scale millimeter\n",
        ["Millimeter"],
        ["mm"],
    ),
    ExplorerTest(
        "instance_class_name_mm",
        b"instance-class-name appn:Scale mm\n",
        [],
        ["mm", "Millimeter"],
    ),
    ExplorerTest(
        "instance_class_name_all",
        b"instance-class-name-all appn:Scale mm\n",
        ["Millimeter"],
        ["mm"],
    ),
    ExplorerTest(
        "subject_counts", b"subject-counts\n", ["appn:", "cdi:", "ppeo:"], ["xsd:"]
    ),
    ExplorerTest(
        "property_counts", b"property-counts\n", ["appn:", "cdi:", "ppeo:"], ["xsd:"]
    ),
    ExplorerTest(
        "object_counts", b"object-counts\n", ["appn:", "cdi:", "ppeo:"], ["xsd:"]
    ),
]

TEST_DICTIONARY: dict[str, ExplorerTest] = {test.name: test for test in EXPLORER_TESTS}

EXPLORER_RESULTS: dict[str, str] = {}


@pytest.fixture
def explorer_results() -> dict[str, str]:
    if len(EXPLORER_RESULTS) < len(EXPLORER_TESTS):
        with Popen(  # noqa: S603
            ["python", "src/appn_linked_data/explorer.py", "-a", "au"],  # noqa: S607
            stdin=PIPE,
            stdout=PIPE,
            stderr=STDOUT,
        ) as explorer:
            test_commands = b"".join([test.args for test in EXPLORER_TESTS]) + b"q\n"
            result = explorer.communicate(input=test_commands)[0].decode().splitlines()
            test: ExplorerTest | None = None
            test_index = 0
            test_response = ""
            for line in result:
                if "Enter query" in line:
                    if test is not None:
                        EXPLORER_RESULTS[test.name] = test_response
                    if test_index < len(EXPLORER_TESTS):
                        test = EXPLORER_TESTS[test_index]
                        test_index += 1
                        test_response = ""
                    else:
                        break
                elif len(line) > 0:
                    test_response += f"{line}\n"
    return EXPLORER_RESULTS


def test_classes(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["classes"]
    results = explorer_results["classes"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_classes_appn(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["classes_appn"]
    results = explorer_results["classes_appn"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_namespaces(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["namespaces"]
    results = explorer_results["namespaces"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_triples(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["triples"]
    results = explorer_results["triples"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_instances_growth_facility(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["instances_growth_facility"]
    results = explorer_results["instances_growth_facility"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_instances_specific_thing(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["instances_specific_thing"]
    results = explorer_results["instances_specific_thing"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_subject_trait(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["subject_trait"]
    results = explorer_results["subject_trait"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_property_in_scheme(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["property_in_scheme"]
    results = explorer_results["property_in_scheme"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_object(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["object"]
    results = explorer_results["object"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_type(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["type"]
    results = explorer_results["type"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_superclasses(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["superclasses"]
    results = explorer_results["superclasses"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_superproperties(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["superproperties"]
    results = explorer_results["superproperties"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_subclasses(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["subclasses"]
    results = explorer_results["subclasses"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_subproperties(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["subproperties"]
    results = explorer_results["subproperties"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_domain_properties(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["domain_properties"]
    results = explorer_results["domain_properties"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_range_properties(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["range_properties"]
    results = explorer_results["range_properties"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_domain_classes(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["domain_classes"]
    results = explorer_results["domain_classes"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_range_classes(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["range_classes"]
    results = explorer_results["range_classes"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_domain_range_properties(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["domain_range_properties"]
    results = explorer_results["domain_range_properties"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_properties(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["properties"]
    results = explorer_results["properties"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_unique_subjects(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["unique_subjects"]
    results = explorer_results["unique_subjects"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_unique_properties(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["unique_properties"]
    results = explorer_results["unique_properties"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_unique_objects(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["unique_objects"]
    results = explorer_results["unique_objects"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_property_name(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["property_name"]
    results = explorer_results["property_name"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_property_name_all(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["property_name_all"]
    results = explorer_results["property_name_all"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_instance_name_millimeter(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["instance_name_millimeter"]
    results = explorer_results["instance_name_millimeter"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_instance_name_mm(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["instance_name_mm"]
    results = explorer_results["instance_name_mm"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_instance_name_all(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["instance_name_all"]
    results = explorer_results["instance_name_all"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_instance_class_name_millimeter(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["instance_class_name_millimeter"]
    results = explorer_results["instance_class_name_millimeter"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_instance_class_name_mm(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["instance_class_name_mm"]
    results = explorer_results["instance_class_name_mm"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_instance_class_name_all(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["instance_class_name_all"]
    results = explorer_results["instance_class_name_all"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_subject_counts(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["subject_counts"]
    results = explorer_results["subject_counts"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_property_counts(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["property_counts"]
    results = explorer_results["property_counts"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results


def test_object_counts(explorer_results: dict[str, str]) -> None:
    test = TEST_DICTIONARY["object_counts"]
    results = explorer_results["object_counts"]
    for test_string in test.expected:
        assert test_string in results
    for test_string in test.not_expected:
        assert test_string not in results
