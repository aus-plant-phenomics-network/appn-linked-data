#!/usr/bin/env python3

"""Tests for `appn_linked_data.configuration`."""

from __future__ import annotations

import logging

import pytest

from appn_linked_data import (
    APPN_SCHEMA,
    IRI,
    SCHEMA_SCHEMA,
    SKOS_SCHEMA,
    CompletionRuleProperty,
    CompletionRuleType,
    Configuration,
    ExplicitTermsFilter,
    IssueLogger,
    NamespaceDefinition,
)


@pytest.fixture
def default_configuration() -> Configuration:
    """Return configuration with sample settings for all keys."""
    return Configuration()


def test_logger(default_configuration: Configuration) -> None:
    """Check access to APPN Logger."""
    logger = default_configuration.get_logger()
    assert isinstance(logger, IssueLogger)
    logger.log(logging.INFO, __name__, "This is just a test", not_for_real=True)
    assert logger.get_issue_counts_by_message()["This is just a test"] == 1
    assert logger.list_issues(
        logging.INFO, module=__name__, message="This is just a test"
    )[0].properties["not_for_real"]


def test_namespace_definitions(default_configuration: Configuration) -> None:
    """Check get_namespace_definitions."""
    namespace_definitions = default_configuration.get_namespace_definitions()
    assert namespace_definitions is not None
    assert APPN_SCHEMA in namespace_definitions
    assert "https://phenomicstest.com/" not in namespace_definitions


def test_vocabulary_column_namespaces(default_configuration: Configuration) -> None:
    """Check get_vocabulary_column_namespaces."""
    vocabulary_column_namespaces = (
        default_configuration.get_vocabulary_column_namespaces()
    )
    assert vocabulary_column_namespaces is not None
    assert SKOS_SCHEMA in vocabulary_column_namespaces


def test_explicit_classes(default_configuration: Configuration) -> None:
    """Check get_explicit_classes."""
    explicit_classes = default_configuration.get_explicit_classes()
    assert explicit_classes is not None
    assert SCHEMA_SCHEMA in explicit_classes
    assert explicit_classes[SCHEMA_SCHEMA] == ExplicitTermsFilter.FIRST  # type: ignore[index]


def test_explicit_properties(default_configuration: Configuration) -> None:
    """Check get_explicit_properties."""
    explicit_properties = default_configuration.get_explicit_properties()
    assert explicit_properties is not None
    assert SCHEMA_SCHEMA in explicit_properties
    assert explicit_properties[SCHEMA_SCHEMA] == ExplicitTermsFilter.FIRST  # type: ignore[index]


def test_excluded_classes(default_configuration: Configuration) -> None:
    """Check get_excluded_classes."""
    excluded_classes = default_configuration.get_excluded_classes()
    assert excluded_classes is not None
    assert f"{SCHEMA_SCHEMA}Thing" in excluded_classes


def test_sheet_aliases(default_configuration: Configuration) -> None:
    """Check get_sheet_aliases."""
    sheet_aliases = default_configuration.get_sheet_aliases()
    assert sheet_aliases is not None
    assert sheet_aliases["Trait"].name == "ObservedVariable"


def test_column_aliases(default_configuration: Configuration) -> None:
    """Check get_column_aliases."""
    column_aliases = default_configuration.get_column_aliases()
    assert column_aliases is not None
    assert column_aliases["parent"].name == "BiologicalMaterial"


def test_completion_rules(default_configuration: Configuration) -> None:
    """Check get_completion_rules."""
    completion_rules = default_configuration.get_completion_rules()
    assert completion_rules is not None
    ov = f"{APPN_SCHEMA}ObservedVariable"
    ht = f"{APPN_SCHEMA}hasTrait"
    assert ov in completion_rules  # type: ignore[index]
    assert ht in completion_rules[ov]  # type: ignore[index]
    assert (
        completion_rules[ov][ht][CompletionRuleProperty.TYPE]  # type: ignore[index]
        == CompletionRuleType.REFLEXIVE
    )


def test_completion_rules_for_class(default_configuration: Configuration) -> None:
    """Check get_completion_rules_for_class."""
    ov = IRI(f"{APPN_SCHEMA}ObservedVariable")
    completion_rules_for_class = default_configuration.get_completion_rules_for_class(
        ov
    )
    ht = f"{APPN_SCHEMA}hasTrait"
    assert completion_rules_for_class is not None
    assert ht in completion_rules_for_class  # type: ignore[index]
    assert (
        completion_rules_for_class[ht][CompletionRuleProperty.TYPE]  # type: ignore[index]
        == CompletionRuleType.REFLEXIVE
    )


def test_class_abbreviations(default_configuration: Configuration) -> None:
    """Check get_class_abbreviations."""
    class_abbreviations = default_configuration.get_class_abbreviations()
    ov = f"{APPN_SCHEMA}ObservedVariable"
    assert class_abbreviations is not None
    assert class_abbreviations[ov] == "ov"  # type: ignore[index]


def test_property_expansions(default_configuration: Configuration) -> None:
    """Check get_property_expansions."""
    property_expansions = default_configuration.get_property_expansions()
    schema_name = f"{SCHEMA_SCHEMA}name"
    pl = f"{SKOS_SCHEMA}prefLabel"
    assert property_expansions is not None
    assert schema_name in property_expansions
    assert pl in property_expansions[schema_name]  # type: ignore[index]


def test_embedded_classes(default_configuration: Configuration) -> None:
    """Check get_embedded_classes."""
    embedded_classes = default_configuration.get_embedded_classes()
    assert embedded_classes is not None
    ov = f"{APPN_SCHEMA}ObservedVariable"
    method = f"{APPN_SCHEMA}Method"
    assert ov in embedded_classes  # type: ignore[index]
    assert method in embedded_classes[ov]  # type: ignore[index]


def test_domain_range_properties(default_configuration: Configuration) -> None:
    """Check get_domain_range_properties."""
    domain_range_properties = default_configuration.get_domain_range_properties()
    assert domain_range_properties is not None
    gf = f"{APPN_SCHEMA}GrowthFacility"
    sensor = f"{APPN_SCHEMA}Sensor"
    hosts = f"{APPN_SCHEMA}hosts"
    assert gf in domain_range_properties  # type: ignore[index]
    assert sensor in domain_range_properties[gf]  # type: ignore[index]
    assert domain_range_properties[gf][sensor] == hosts  # type: ignore[index]


def test_property_range_classes(default_configuration: Configuration) -> None:
    """Check get_property_range_classes."""
    property_range_classes = default_configuration.get_property_range_classes()
    assert property_range_classes is not None
    gf = f"{APPN_SCHEMA}GrowthFacility"
    hgft = f"{APPN_SCHEMA}hasGrowthFacilityType"
    gft = f"{APPN_SCHEMA}GrowthFacilityType"
    assert gf in property_range_classes  # type: ignore[index]
    assert hgft in property_range_classes[gf]  # type: ignore[index]
    assert property_range_classes[gf][hgft] == gft  # type: ignore[index]


def test_ro_crate_table_classes(default_configuration: Configuration) -> None:
    """Check get_ro_crate_table_classes."""
    ro_crate_table_classes = default_configuration.get_ro_crate_table_classes()
    assert ro_crate_table_classes is not None
    assert f"{APPN_SCHEMA}Observation" in ro_crate_table_classes


def test_organisations(default_configuration: Configuration) -> None:
    """Check get_organisations."""
    organisations = default_configuration.get_organisations()
    assert organisations is not None
    assert all(
        key in sorted(organisations.keys())
        for key in [
            "ANU",
            "APPN",
            "AU",
            "CSU",
            "DPIRD",
            "LTU",
            "UQ",
            "USYD",
            "UWA",
            "WSU",
        ]
    )
    assert organisations["WSU"].name == "Western Sydney University"


def test_organisation_by_id(default_configuration: Configuration) -> None:
    """Check get_organisation_by_id."""
    organisation_by_id = default_configuration.get_organisation_by_id("LTU")
    assert organisation_by_id is not None
    assert organisation_by_id.prefix == "ltu"


def test_appn(default_configuration: Configuration) -> None:
    """Check get_appn."""
    appn = default_configuration.get_appn()
    assert appn is not None
    assert appn.prefix == "appnid"


def test_get_iri(default_configuration: Configuration) -> None:
    iri_name = "TestValue"
    iri_string = f"{SCHEMA_SCHEMA}{iri_name}"
    iri = default_configuration.get_iri(iri_string)
    assert iri.iri == iri_string
    assert iri.ns == SCHEMA_SCHEMA
    assert iri.prefix == "schema"
    assert iri.name == iri_name
    assert iri.curie == f"{iri.prefix}:{iri.name}"
    other_iri = default_configuration.get_iri(iri.curie)
    assert other_iri == iri
    namespace_definitions = default_configuration.get_namespace_definitions()
    appn_iri = default_configuration.get_iri(
        iri_name, namespace_definitions[APPN_SCHEMA]
    )
    assert appn_iri != iri
    assert appn_iri.iri == f"{APPN_SCHEMA}{iri_name}"


def test_add_namespace_definition(default_configuration: Configuration) -> None:
    ns = "https://example.org/"
    prefix = "exx"
    name = "Something"
    namespace_definition = NamespaceDefinition(ns, prefix, ns)
    default_configuration.add_namespace_definition(namespace_definition)
    iri = default_configuration.get_iri(f"{prefix}:{name}")
    assert iri.iri == f"{ns}{name}"
