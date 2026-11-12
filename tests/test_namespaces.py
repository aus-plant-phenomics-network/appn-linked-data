#!/usr/bin/env python3

"""Tests for `appn_linked_data.ld_namespaces`."""

from __future__ import annotations

from appn_linked_data import (
    APPN_SCHEMA,
    SCHEMA_SCHEMA,
    NamespaceDefinition,
    NamespaceDefinitionManager,
)

PREFIX_LIST = [
    "appn",
    "anu",
    "au",
    "csu",
    "dpird",
    "ltu",
    "uq",
    "usyd",
    "uwa",
    "wsu",
    "appnid",
    "schema",
    "rdf",
    "rdfs",
    "dcterms",
    "bio",
    "prov",
    "sosa",
    "ssn",
    "dwc",
    "owl",
    "skos",
    "cdi",
    "cdif",
    "ppeo",
]


def test_singleton() -> None:
    """Check repeated calls return same instance."""
    manager = NamespaceDefinitionManager()
    assert manager is NamespaceDefinitionManager()


def test_namespace_definitions() -> None:
    """Check get_namespace_definitions."""
    manager = NamespaceDefinitionManager()
    namespace_definitions = manager.get_namespace_definitions()
    prefixes = {definition.prefix for definition in namespace_definitions}
    assert all(prefix in prefixes for prefix in PREFIX_LIST)


def test_namespace_dictionary() -> None:
    """Check get_namespace_dictionary."""
    manager = NamespaceDefinitionManager()
    namespace_definitions = manager.get_namespace_definitions()
    namespace_dictionary = manager.get_namespace_dictionary()
    assert len(namespace_definitions) == len(namespace_dictionary)
    assert APPN_SCHEMA in namespace_dictionary
    assert namespace_dictionary[APPN_SCHEMA].prefix == "appn"


def test_namespace_prefix_dictionary() -> None:
    """Check get_namespace_prefix_dictionary."""
    manager = NamespaceDefinitionManager()
    namespace_definitions = manager.get_namespace_definitions()
    prefix_dictionary = manager.get_namespace_prefix_dictionary()
    assert len(namespace_definitions) == len(prefix_dictionary)
    assert "schema" in prefix_dictionary
    assert prefix_dictionary["schema"].namespace == SCHEMA_SCHEMA


def test_iri_start_dictionary() -> None:
    """Check get_iri_start_dictionary."""
    manager = NamespaceDefinitionManager()
    namespace_definitions = manager.get_namespace_definitions()
    start_dictionary = manager.get_iri_start_dictionary()
    assert len(namespace_definitions) * 2 == len(start_dictionary)
    assert "schema:" in start_dictionary
    assert "schema" not in start_dictionary
    assert SCHEMA_SCHEMA in start_dictionary
    assert start_dictionary[APPN_SCHEMA] is start_dictionary["appn:"]


def test_get_appn_namespace_definition() -> None:
    """Check get_appn_namespace_definition."""
    manager = NamespaceDefinitionManager()
    appn = manager.get_appn_namespace_definition()
    assert appn.namespace == APPN_SCHEMA
    assert appn.prefix == "appn"


def test_add_namespace_definition() -> None:
    """Check add_namespace_definition."""
    manager = NamespaceDefinitionManager()
    definitions_before = manager.get_namespace_definitions()
    namespaces_before = manager.get_namespace_dictionary()
    prefixes_before = manager.get_namespace_prefix_dictionary()
    starts_before = manager.get_iri_start_dictionary()
    before_length = len(definitions_before)
    definition = NamespaceDefinition(namespace="https://example.org/", prefix="exx")
    manager.add_namespace_definition(definition)
    definitions_after = manager.get_namespace_definitions()
    namespaces_after = manager.get_namespace_dictionary()
    prefixes_after = manager.get_namespace_prefix_dictionary()
    starts_after = manager.get_iri_start_dictionary()
    after_length = len(definitions_after)
    assert after_length == before_length + 1
    assert definitions_after is definitions_before
    assert namespaces_after is namespaces_before
    assert prefixes_after is prefixes_before
    assert starts_before is starts_after
    assert definition in definitions_after
    assert definition.namespace in namespaces_after
    assert definition.prefix in prefixes_after
    assert definition.namespace in starts_after
    assert f"{definition.prefix}:" in starts_after


def test_existing_namespace_definition() -> None:
    """Check add_namespace_definition with matching or partially matching definitions."""
    manager = NamespaceDefinitionManager()
    namespaces_before = manager.get_namespace_dictionary()
    before_length = len(namespaces_before)
    definition = NamespaceDefinition(namespace=APPN_SCHEMA, prefix="exx")
    assert not manager.add_namespace_definition(definition)
    assert len(manager.get_namespace_definitions()) == before_length
    definition = NamespaceDefinition(namespace=APPN_SCHEMA, prefix="appn")
    assert manager.add_namespace_definition(definition)
    assert len(manager.get_namespace_definitions()) == before_length
    definition = NamespaceDefinition(namespace="https://example.org/", prefix="appn")
    assert not manager.add_namespace_definition(definition)
    assert len(manager.get_namespace_definitions()) == before_length
