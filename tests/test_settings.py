#!/usr/bin/env python3

"""Tests for `appn_linked_data.ld_settings`."""

from __future__ import annotations

import pytest

from appn_linked_data import (
    APPN_SCHEMA,
    IRI,
    SCHEMA_SCHEMA,
    SKOS_SCHEMA,
    ExplicitTermsFilter,
    LinkedDataSettings,
    ReflexiveCompletionRule,
)


@pytest.fixture
def default_settings() -> LinkedDataSettings:
    """Return configuration with sample settings for all keys."""
    return LinkedDataSettings()


def test_vocabulary_column_namespaces(default_settings: LinkedDataSettings) -> None:
    """Check get_vocabulary_column_namespaces."""
    vocabulary_column_namespaces = default_settings.get_vocabulary_column_namespaces()
    assert vocabulary_column_namespaces is not None
    assert SKOS_SCHEMA in vocabulary_column_namespaces


def test_explicit_classes(default_settings: LinkedDataSettings) -> None:
    """Check get_explicit_classes."""
    explicit_classes = default_settings.get_explicit_classes()
    assert explicit_classes is not None
    assert SCHEMA_SCHEMA in explicit_classes
    assert explicit_classes[SCHEMA_SCHEMA] == ExplicitTermsFilter.FIRST  # type: ignore[index]


def test_explicit_properties(default_settings: LinkedDataSettings) -> None:
    """Check get_explicit_properties."""
    explicit_properties = default_settings.get_explicit_properties()
    assert explicit_properties is not None
    assert SCHEMA_SCHEMA in explicit_properties
    assert explicit_properties[SCHEMA_SCHEMA] == ExplicitTermsFilter.FIRST  # type: ignore[index]


def test_excluded_classes(default_settings: LinkedDataSettings) -> None:
    """Check get_excluded_classes."""
    excluded_classes = default_settings.get_excluded_classes()
    assert excluded_classes is not None
    assert f"{SCHEMA_SCHEMA}Thing" in excluded_classes


def test_sheet_aliases(default_settings: LinkedDataSettings) -> None:
    """Check get_sheet_aliases."""
    sheet_aliases = default_settings.get_sheet_aliases()
    assert sheet_aliases is not None
    assert sheet_aliases["Trait"] == "ObservedVariable"


def test_column_aliases(default_settings: LinkedDataSettings) -> None:
    """Check get_column_aliases."""
    column_aliases = default_settings.get_column_aliases()
    assert column_aliases is not None
    assert column_aliases["parent"] == "BiologicalMaterial"


def test_completion_rules(default_settings: LinkedDataSettings) -> None:
    """Check get_completion_rules."""
    completion_rules = default_settings.get_completion_rules()
    assert completion_rules is not None
    ov = IRI(f"{APPN_SCHEMA}ObservedVariable")
    ht = IRI(f"{APPN_SCHEMA}hasTrait")
    assert ov in completion_rules
    assert isinstance(completion_rules[ov][0], ReflexiveCompletionRule)
    assert completion_rules[ov][0].reflexive_property == ht  # type: ignore[attr-defined]


def test_completion_rules_for_class(default_settings: LinkedDataSettings) -> None:
    """Check get_completion_rules_for_class."""
    ov = IRI(f"{APPN_SCHEMA}ObservedVariable")
    completion_rules_for_class = default_settings.get_completion_rules_for_class(ov)
    ht = IRI(f"{APPN_SCHEMA}hasTrait")
    assert completion_rules_for_class is not None
    assert isinstance(completion_rules_for_class[0], ReflexiveCompletionRule)
    assert completion_rules_for_class[0].reflexive_property == ht


def test_class_abbreviations(default_settings: LinkedDataSettings) -> None:
    """Check get_class_abbreviations."""
    class_abbreviations = default_settings.get_class_abbreviations()
    ov = f"{APPN_SCHEMA}ObservedVariable"
    assert class_abbreviations is not None
    assert class_abbreviations[ov] == "ov"  # type: ignore[index]


def test_property_expansions(default_settings: LinkedDataSettings) -> None:
    """Check get_property_expansions."""
    property_expansions = default_settings.get_property_expansions()
    schema_name = f"{SCHEMA_SCHEMA}name"
    pl = f"{SKOS_SCHEMA}prefLabel"
    assert property_expansions is not None
    assert schema_name in property_expansions
    assert pl in property_expansions[schema_name]  # type: ignore[index]


def test_embedded_classes(default_settings: LinkedDataSettings) -> None:
    """Check get_embedded_classes."""
    embedded_classes = default_settings.get_embedded_classes()
    assert embedded_classes is not None
    ov = f"{APPN_SCHEMA}ObservedVariable"
    method = f"{APPN_SCHEMA}Method"
    assert ov in embedded_classes  # type: ignore[index]
    assert method in embedded_classes[ov]  # type: ignore[index]


def test_domain_range_properties(default_settings: LinkedDataSettings) -> None:
    """Check get_domain_range_properties."""
    domain_range_properties = default_settings.get_domain_range_properties()
    assert domain_range_properties is not None
    gf = f"{APPN_SCHEMA}GrowthFacility"
    sensor = f"{APPN_SCHEMA}Sensor"
    hosts = f"{APPN_SCHEMA}hosts"
    assert gf in domain_range_properties  # type: ignore[index]
    assert sensor in domain_range_properties[gf]  # type: ignore[index]
    assert domain_range_properties[gf][sensor] == hosts  # type: ignore[index]


def test_property_range_classes(default_settings: LinkedDataSettings) -> None:
    """Check get_property_range_classes."""
    property_range_classes = default_settings.get_property_range_classes()
    assert property_range_classes is not None
    gf = f"{APPN_SCHEMA}GrowthFacility"
    hgft = f"{APPN_SCHEMA}hasGrowthFacilityType"
    gft = f"{APPN_SCHEMA}GrowthFacilityType"
    assert gf in property_range_classes  # type: ignore[index]
    assert hgft in property_range_classes[gf]  # type: ignore[index]
    assert property_range_classes[gf][hgft] == gft  # type: ignore[index]


def test_ro_crate_table_classes(default_settings: LinkedDataSettings) -> None:
    """Check get_ro_crate_table_classes."""
    ro_crate_table_classes = default_settings.get_ro_crate_table_classes()
    assert ro_crate_table_classes is not None
    assert IRI(f"{APPN_SCHEMA}Observation") in ro_crate_table_classes


def test_organisations(default_settings: LinkedDataSettings) -> None:
    """Check get_organisations."""
    organisations = default_settings.get_organisations()
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


def test_organisation_by_id(default_settings: LinkedDataSettings) -> None:
    """Check get_organisation_by_id."""
    organisation_by_id = default_settings.get_organisation_by_id("LTU")
    assert organisation_by_id is not None
    assert organisation_by_id.prefix == "ltu"


def test_appn(default_settings: LinkedDataSettings) -> None:
    """Check get_appn."""
    appn = default_settings.get_appn()
    assert appn is not None
    assert appn.prefix == "appnid"
