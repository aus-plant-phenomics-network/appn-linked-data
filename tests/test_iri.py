#!/usr/bin/env python3

"""Tests for `appn_linked_data.ld_namespaces`."""

from __future__ import annotations

from rdflib import Literal, URIRef

from appn_linked_data import (
    APPN_SCHEMA,
    IRI,
    SCHEMA_SCHEMA,
    Triple,
)


def test_iri_from_string() -> None:
    """Check construction of IRIs."""
    iri_string = f"{APPN_SCHEMA}Trait"
    for string in [iri_string, "appn:Trait"]:
        iri = IRI(string)
        assert iri is not None
        assert iri.iri == iri_string
        assert iri.curie == "appn:Trait"
        assert iri.ns == APPN_SCHEMA
        assert iri.prefix == "appn"
        assert iri.name == "Trait"

    iri_string = "NoNamespace"
    iri = IRI(iri_string)
    assert iri.iri == iri_string
    assert iri.curie == iri_string
    assert iri.name == iri_string
    assert iri.ns == ""
    assert iri.prefix == ""


def test_triple() -> None:
    strings = ["https://example.org/123", "schema:name", "One Thirty-Three"]
    triple = Triple(URIRef(strings[0]), URIRef(strings[1]), Literal(strings[2]))
    assert triple is not None
    assert isinstance(triple.subject, IRI)
    assert triple.subject.curie == strings[0]
    assert isinstance(triple.predicate, IRI)
    assert triple.predicate.iri == f"{SCHEMA_SCHEMA}name"
    assert not isinstance(triple.object, IRI)
    assert str(triple.object) == strings[2]
