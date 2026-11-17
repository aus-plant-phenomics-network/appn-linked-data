#!/usr/bin/env python3

"""Tests for `appn_linked_data.ld_parser`."""

from __future__ import annotations

import logging
from datetime import datetime

import pytest
from rdflib import Graph

from appn_linked_data import (
    APPN_SCHEMA,
    APPN_VOCABULARY,
    DC_SCHEMA,
    IRI,
    SKOS_SCHEMA,
    Dictionary,
    DictParser,
    IssueHandler,
    IssueType,
    LinkedDataSettings,
    Triple,
)
from appn_linked_data.ld_parser import (
    NewPropertyHandler,
    NullPropertyHandler,
)

logger = logging.getLogger(__name__)


@pytest.fixture
def default_dictionary() -> Dictionary:
    """Dictionary with main schemas imported."""
    default_dictionary = Dictionary()
    default_dictionary.load(APPN_SCHEMA)
    default_dictionary.load(SKOS_SCHEMA)
    default_dictionary.load(DC_SCHEMA)
    default_dictionary.load(APPN_VOCABULARY)
    default_dictionary.import_references()

    return default_dictionary


@pytest.fixture
def modified_dictionary() -> Dictionary:
    """Contains regular dictionary with some additional property definitions for the GrowthFacility class."""
    modified_dictionary = Dictionary()
    modified_dictionary.load(APPN_SCHEMA)
    modified_dictionary.load(SKOS_SCHEMA)
    modified_dictionary.load(DC_SCHEMA)
    modified_dictionary.load(APPN_VOCABULARY)
    modified_dictionary.add_triple(
        Triple(IRI("appn:hasBooleanValue"), IRI("rdf:type"), IRI("rdf:Property"))
    )
    modified_dictionary.add_triple(
        Triple(
            IRI("appn:hasBooleanValue"), IRI("schema:rangeIncludes"), IRI("xsd:boolean")
        )
    )
    modified_dictionary.add_triple(
        Triple(
            IRI("appn:hasBooleanValue"),
            IRI("schema:domainIncludes"),
            IRI("appn:GrowthFacility"),
        )
    )
    modified_dictionary.add_triple(
        Triple(IRI("appn:hasDateTimeValue"), IRI("rdf:type"), IRI("rdf:Property"))
    )
    modified_dictionary.add_triple(
        Triple(
            IRI("appn:hasDateTimeValue"),
            IRI("schema:rangeIncludes"),
            IRI("xsd:dateTime"),
        )
    )
    modified_dictionary.add_triple(
        Triple(
            IRI("appn:hasDateTimeValue"),
            IRI("schema:domainIncludes"),
            IRI("appn:GrowthFacility"),
        )
    )
    modified_dictionary.add_triple(
        Triple(IRI("appn:hasDecimalValue"), IRI("rdf:type"), IRI("rdf:Property"))
    )
    modified_dictionary.add_triple(
        Triple(
            IRI("appn:hasDecimalValue"), IRI("schema:rangeIncludes"), IRI("xsd:decimal")
        )
    )
    modified_dictionary.add_triple(
        Triple(
            IRI("appn:hasDecimalValue"),
            IRI("schema:domainIncludes"),
            IRI("appn:GrowthFacility"),
        )
    )
    modified_dictionary.add_triple(
        Triple(IRI("appn:hasIntegerValue"), IRI("rdf:type"), IRI("rdf:Property"))
    )
    modified_dictionary.add_triple(
        Triple(
            IRI("appn:hasIntegerValue"), IRI("schema:rangeIncludes"), IRI("xsd:integer")
        )
    )
    modified_dictionary.add_triple(
        Triple(
            IRI("appn:hasIntegerValue"),
            IRI("schema:domainIncludes"),
            IRI("appn:GrowthFacility"),
        )
    )
    modified_dictionary.import_references()

    return modified_dictionary


def test_parse_to_default_graph(default_dictionary: Dictionary) -> None:
    organisation = LinkedDataSettings().get_organisation_by_id("UQ")
    with IssueHandler() as issue_handler:
        parser = DictParser(
            default_dictionary, IRI("appn:GrowthFacility"), organisation
        )
        assert parser is not None
        assert len(parser.property_handlers) == 0
        iri = parser.parse(
            {
                "name": "Shed 1",
                "description": "The old shed",
                "GrowthFacilityType": "pot",
            }
        )
        assert len(parser.property_handlers) == 3
        assert iri == IRI("uq:gf_Shed1")
        iri2 = parser.parse(
            {
                "name": "Shed 2",
                "description": "The new shed",
                "GrowthFacilityType": "pot",
            }
        )
        assert len(parser.property_handlers) == 3
        assert iri2 == IRI("uq:gf_Shed2")
        inspector = Dictionary(parser.get_graph())
        assert set(inspector.list_unique_subjects()) == {iri, iri2}
        assert IRI("appnid:gft_Pot") in inspector.list_unique_objects()
        assert len(issue_handler.get_issues(False)) == 0


def test_parse_to_supplied_graph(default_dictionary: Dictionary) -> None:
    organisation = LinkedDataSettings().get_organisation_by_id("UQ")
    graph = Graph()
    parser = DictParser(
        default_dictionary, IRI("appn:GrowthFacility"), organisation, graph=graph
    )
    assert parser is not None
    assert len(parser.property_handlers) == 0
    iri = parser.parse(
        {
            "name": "Shed 1",
            "description": "The old shed",
            "GrowthFacilityType": "pot",
        }
    )
    inspector = Dictionary(graph)
    assert inspector.list_unique_subjects() == [iri]


def test_embedded_class(default_dictionary: Dictionary) -> None:
    organisation = LinkedDataSettings().get_organisation_by_id("UQ")
    with IssueHandler():
        parser = DictParser(
            default_dictionary,
            IRI("appn:ObservedVariable"),
            organisation,
            generate_concepts=True,
        )
        assert parser is not None
        assert len(parser.property_handlers) == 0
        assert len(parser.embedded_parsers) == 1
        iri = parser.parse(
            {
                "name": "greenness",
                "description": "How green things are",
                "methodName": "guessing",
                "methodDescription": "Closing one's eyes and imagining the colour green",
                "Scale": "integer",
                "mood": "angry",
            }
        )
        inspector = Dictionary(parser.get_graph())
        assert len(parser.property_handlers) == 6
        assert (
            len(
                [
                    handler
                    for handler in parser.property_handlers.values()
                    if isinstance(handler, NewPropertyHandler)
                ]
            )
            == 1
        )
        assert (
            len(
                [
                    handler
                    for handler in parser.property_handlers.values()
                    if isinstance(handler, NullPropertyHandler)
                ]
            )
            == 1
        )
        embedded_handlers = parser.embedded_parsers["method"].property_handlers
        assert len(embedded_handlers) == 6
        assert (
            len(
                [
                    handler
                    for handler in embedded_handlers.values()
                    if isinstance(handler, NewPropertyHandler)
                ]
            )
            == 0
        )
        assert (
            len(
                [
                    handler
                    for handler in embedded_handlers.values()
                    if isinstance(handler, NullPropertyHandler)
                ]
            )
            == 4
        )
        assert set(inspector.list_unique_subjects()) == {
            iri,
            IRI("uq:method_Guessing"),
            IRI("uq:cs_ObservedVariable"),
            IRI("uq:cs_Method"),
            IRI("uq:property_Mood"),
        }
        unique_objects = inspector.list_unique_objects()
        # This includes checking that the CompletionRule for appn:hasTrait fired and that a new property was created.
        assert all(
            iri in unique_objects
            for iri in {iri, IRI("uq:method_Guessing"), IRI("appnid:scale_Integer")}
        )
        # This includes checking that the CompletionRule for appn:hasTrait fired and that a new property was created.
        unique_properties = inspector.list_unique_properties()
        assert all(iri in unique_properties for iri in {IRI("uq:property_Mood")})


def test_xml_types(modified_dictionary: Dictionary) -> None:
    organisation = LinkedDataSettings().get_organisation_by_id("UQ")
    with IssueHandler() as issue_handler:
        parser = DictParser(
            modified_dictionary, IRI("appn:GrowthFacility"), organisation
        )
        inspector = Dictionary(parser.get_graph())
        assert parser is not None
        assert len(parser.property_handlers) == 0
        iri = parser.parse(
            {
                "name": "Shed 1",
                "description": "The old shed",
                "GrowthFacilityType": "pot",
                "hasIntegerValue": "10",
                "hasBooleanValue": "Yes",
                "hasDecimalValue": "17.5764",
                "hasDateTimeValue": "2015-07-12T10:16:25",
            }
        )
        assert len(parser.property_handlers) == 7
        assert iri == IRI("uq:gf_Shed1")
        triples = inspector.list_triples_for_subject(IRI("uq:gf_Shed1"))
        assert any(
            t.predicate == IRI("appn:hasIntegerValue") and t.object.value == 10  # type: ignore[attr-defined]
            for t in triples
        )
        assert any(
            t.predicate == IRI("appn:hasBooleanValue") and t.object.value is True  # type: ignore[attr-defined]
            for t in triples
        )
        assert any(
            t.predicate == IRI("appn:hasDecimalValue") and t.object.value == 17.5764  # type: ignore[attr-defined]
            for t in triples
        )
        assert any(
            t.predicate == IRI("appn:hasDateTimeValue") and t.object.value.year == 2015  # type: ignore[attr-defined]
            for t in triples
        )
        parser.parse(
            {
                "name": "Shed 2",
                "description": "The new shed",
                "GrowthFacilityType": "pot",
                "hasIntegerValue": 11,
                "hasBooleanValue": False,
                "hasDecimalValue": 17.5764,
                "hasDateTimeValue": datetime.now(),  # noqa: DTZ005
            }
        )
        triples = inspector.list_triples_for_subject(IRI("uq:gf_Shed2"))
        assert any(
            t.predicate == IRI("appn:hasIntegerValue") and t.object.value == 11  # type: ignore[attr-defined]
            for t in triples
        )
        assert any(
            t.predicate == IRI("appn:hasBooleanValue") and t.object.value is False  # type: ignore[attr-defined]
            for t in triples
        )
        assert any(
            t.predicate == IRI("appn:hasDecimalValue") and t.object.value == 17.5764  # type: ignore[attr-defined]
            for t in triples
        )
        assert any(
            t.predicate == IRI("appn:hasDateTimeValue") and t.object.value.year >= 2026  # type: ignore[attr-defined]
            for t in triples
        )
        assert len(issue_handler.get_issues(True)) == 0
        parser.parse(
            {
                "name": "Shed 3",
                "description": "Someone else's shed",
                "GrowthFacilityType": "pot",
                "hasIntegerValue": "False",
                "hasBooleanValue": "2015-07-12T10:16:25",
                "hasDecimalValue": "Thursday",
                "hasDateTimeValue": 16,
            }
        )
        triples = inspector.list_triples_for_subject(IRI("uq:gf_Shed3"))
        assert any(
            t.predicate == IRI("appn:hasIntegerValue")
            and isinstance(t.object.value, str)  # type: ignore[attr-defined]
            for t in triples
        )
        assert any(
            t.predicate == IRI("appn:hasBooleanValue")
            and isinstance(t.object.value, str)  # type: ignore[attr-defined]
            for t in triples
        )
        assert any(
            t.predicate == IRI("appn:hasDecimalValue")
            and isinstance(t.object.value, str)  # type: ignore[attr-defined]
            for t in triples
        )
        assert any(
            t.predicate == IRI("appn:hasDateTimeValue")
            and isinstance(t.object.value, int)  # type: ignore[attr-defined]
            for t in triples
        )
        issues = issue_handler.get_issues(True)
        assert len(issues) == 1
        assert len(issues[logging.ERROR]) == 1
        assert len(issues[logging.ERROR][IssueType.BAD_VALUE]) == 4
