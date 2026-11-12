#!/usr/bin/env python3

"""Tests for `appn_linked_data.ld_dictionary`."""

from __future__ import annotations

from rdflib import Literal, URIRef

from appn_linked_data import (
    APPN_SCHEMA,
    APPN_VOCABULARY,
    AU_VOCABULARY,
    IRI,
    SCHEMA_SCHEMA,
    Dictionary,
    TriplePosition,
)


def get_default_dictionary() -> Dictionary:
    """Return dictionary with some standard imports."""
    dictionary = Dictionary()
    dictionary.load(APPN_SCHEMA)
    dictionary.load(APPN_VOCABULARY)
    dictionary.import_references()
    return dictionary


DEFAULT_DICTIONARY = get_default_dictionary()


def test_load() -> None:
    dictionary = get_default_dictionary()
    result = dictionary.load("au")
    assert result is not None
    traits = dictionary.list_instances("appn:Trait", namespace=APPN_VOCABULARY)
    assert len(traits) > 0
    assert IRI("au:ov_AwnLength") in traits


def test_import_references() -> None:
    dictionary = Dictionary()
    dictionary.load(APPN_SCHEMA)
    before_len = len(dictionary.list_classes())
    dictionary.import_references()
    after_len = len(dictionary.list_classes())
    assert after_len > before_len


def test_get_namespace_from_iri() -> None:
    result = DEFAULT_DICTIONARY.get_namespace_from_iri(URIRef("schema:name"))
    assert result == SCHEMA_SCHEMA


def test_get_namespaces() -> None:
    result = DEFAULT_DICTIONARY.get_namespaces()
    assert result is not None
    assert "ppeo" in result
    assert result["schema"] == SCHEMA_SCHEMA


def test_list_triples() -> None:
    result = DEFAULT_DICTIONARY.list_triples()
    assert result is not None
    assert IRI("appn:ObservedVariable") in [triple.subject for triple in result]


def test_list_unique_subjects() -> None:
    result = DEFAULT_DICTIONARY.list_unique_subjects(namespace=APPN_SCHEMA)
    assert result is not None
    assert IRI("appn:Method") in result
    assert all(iri.ns == APPN_SCHEMA for iri in result)


def test_list_unique_properties() -> None:
    result = DEFAULT_DICTIONARY.list_unique_properties(namespace=SCHEMA_SCHEMA)
    assert result is not None
    assert IRI("schema:name") in result
    assert all(iri.ns == SCHEMA_SCHEMA for iri in result)


def test_list_unique_objects() -> None:
    result = DEFAULT_DICTIONARY.list_unique_objects(namespace=APPN_SCHEMA)
    assert result is not None
    assert IRI("appn:Method") in result
    assert all(iri.ns == APPN_SCHEMA for iri in result)


def test_list_triples_for_subject() -> None:
    result = DEFAULT_DICTIONARY.list_triples_for_subject("appnid:cs_Scale")
    assert result is not None
    assert all(
        isinstance(triple.subject, IRI) and triple.subject.name == "cs_Scale"
        for triple in result
    )
    assert any(
        (isinstance(triple.object, IRI) and triple.object == IRI("skos:ConceptScheme"))
        for triple in result
    )


def test_list_triples_for_object() -> None:
    result = DEFAULT_DICTIONARY.list_triples_for_object("appnid:cs_Scale")
    assert result is not None
    assert all(
        isinstance(triple.object, IRI) and triple.object.name == "cs_Scale"
        for triple in result
    )
    assert any(
        (isinstance(triple.predicate, IRI) and triple.predicate == IRI("skos:inScheme"))
        for triple in result
    )


def test_list_triples_for_property() -> None:
    result = DEFAULT_DICTIONARY.list_triples_for_property("schema:name")
    assert result is not None
    assert all(
        isinstance(triple.predicate, IRI) and triple.predicate.ns == SCHEMA_SCHEMA
        for triple in result
    )
    assert any(
        (isinstance(triple.subject, IRI) and triple.subject == IRI("appn:Trait"))
        for triple in result
    )


def test_count_triples_by_subject() -> None:
    result = DEFAULT_DICTIONARY.count_triples_by_subject()
    assert result is not None
    assert len(result) > 1
    assert IRI("appn:Method") in result
    assert all(count > 0 for count in result.values())


def test_count_triples_by_property() -> None:
    result = DEFAULT_DICTIONARY.count_triples_by_property()
    assert result is not None
    assert IRI("appn:usedMethod") in result
    assert all(count > 0 for count in result.values())


def test_count_triples_by_object() -> None:
    result = DEFAULT_DICTIONARY.count_triples_by_object()
    assert result is not None
    assert IRI("appn:Method") in result
    assert all(count > 0 for count in result.values())


def test_count_triples_by_term() -> None:
    result = DEFAULT_DICTIONARY.count_triples_by_term(TriplePosition.SUBJECT)
    assert result is not None
    assert IRI("appn:Method") in result
    assert all(count > 0 for count in result.values())


def test_list_classes() -> None:
    result = DEFAULT_DICTIONARY.list_classes(namespace="ppeo")
    assert result is not None
    assert IRI("ppeo:method") in result


def test_list_properties() -> None:
    result = DEFAULT_DICTIONARY.list_properties(namespace=SCHEMA_SCHEMA)
    assert result is not None
    assert IRI("schema:description") in result


def test_list_superclasses() -> None:
    result = DEFAULT_DICTIONARY.list_superclasses("appn:Observation")
    assert result is not None
    assert IRI("appn:ResearchActivity") in result
    assert IRI("sosa:Observation") in result


def test_list_superproperties() -> None:
    result = DEFAULT_DICTIONARY.list_superproperties("appn:isForObservationUnit")
    assert result is not None
    assert IRI("sosa:hasFeatureOfInterest") in result


def test_list_subclasses() -> None:
    result = DEFAULT_DICTIONARY.list_subclasses("appn:ObservationUnit")
    assert result is not None
    assert IRI("appn:Sample") in result


def test_list_subproperties() -> None:
    result = DEFAULT_DICTIONARY.list_subproperties("sosa:hasFeatureOfInterest")
    assert result is not None
    assert IRI("appn:isForObservationUnit") in result


def test_list_domain_properties_for_class() -> None:
    result = DEFAULT_DICTIONARY.list_domain_properties_for_class("appn:Assay")
    assert result is not None
    assert IRI("appn:atTime") in result


def test_list_range_properties_for_class() -> None:
    result = DEFAULT_DICTIONARY.list_range_properties_for_class("appn:Method")
    assert result is not None
    assert IRI("appn:usedMethod") in result


def test_list_domain_classes_for_property() -> None:
    result = DEFAULT_DICTIONARY.list_domain_classes_for_property("appn:hasScale")
    assert result is not None
    assert IRI("appn:Variable") in result


def test_list_range_classes_for_property() -> None:
    result = DEFAULT_DICTIONARY.list_range_classes_for_property("appn:hasScale")
    assert result is not None
    assert IRI("appn:Scale") in result


def test_list_instances_without_subclasses() -> None:
    dictionary = get_default_dictionary()
    dictionary.load(AU_VOCABULARY)
    result_with = dictionary.list_instances("schema:Thing")
    result_without = dictionary.list_instances_without_subclasses("schema:Thing")
    assert result_without is not None
    assert len(result_with) > len(result_without)
    assert all(result in result_with for result in result_without)


def test_list_instances() -> None:
    result = DEFAULT_DICTIONARY.list_instances("appn:BiologicalMaterial")
    assert result is not None
    assert IRI("appnid:bm_Barley") in result


def test_list_instances_by_class_and_name() -> None:
    result = DEFAULT_DICTIONARY.list_instances_by_class_and_name(
        "appn:BiologicalMaterial", "barley (BiologicalMaterial)"
    )
    assert result is not None
    assert len(result) > 0
    assert any(iri.name == "bm_Barley" for iri in result)


def test_list_instances_by_name() -> None:
    result = DEFAULT_DICTIONARY.list_instances_by_name("barley (BiologicalMaterial)")
    assert result is not None
    assert IRI("appnid:bm_Barley") in result


def test_list_properties_by_name() -> None:
    result = DEFAULT_DICTIONARY.list_properties_by_name("name")
    assert result is not None
    assert len(result) > 1
    assert IRI("schema:name") in result


def test_list_properties_by_domain_and_range() -> None:
    result = DEFAULT_DICTIONARY.list_properties_by_domain_and_range(
        "appn:ObservationUnit", "appn:ObservationUnit"
    )
    assert result is not None
    assert IRI("appn:inheritsContext") in result


def test_list_explicit_classes() -> None:
    result = DEFAULT_DICTIONARY.list_explicit_classes("appn:Observation")
    assert result is not None
    assert IRI("schema:Observation") in result
    assert IRI("skos:Concept") not in result
    result = DEFAULT_DICTIONARY.list_explicit_classes("appn:Observation", True)
    assert result is not None
    assert IRI("schema:Observation") in result
    assert IRI("skos:Concept") in result


def test_list_explicit_properties() -> None:
    result = DEFAULT_DICTIONARY.list_explicit_properties("appn:hasLatitude")
    assert result is not None
    assert IRI("schema:latitude") in result


def test_get_property_for_subject() -> None:
    result = DEFAULT_DICTIONARY.get_property_for_subject("appn:Trait", "schema:name")
    assert result is not None
    assert result == Literal("Trait")


def test_query() -> None:
    result = DEFAULT_DICTIONARY.query(
        "SELECT ?x WHERE {?x rdf:type rdfs:Class . ?x schema:name 'Trait' . }"
    )
    assert result is not None
    assert IRI("appn:Trait") in result[0]


def test_get_name() -> None:
    result = DEFAULT_DICTIONARY.get_name("appn:Method")
    assert result is not None
    assert result == "Method"


def test_get_type() -> None:
    result = DEFAULT_DICTIONARY.get_type("appnid:bm_Barley")
    assert result is not None
    assert result == IRI("appn:BiologicalMaterial")


def test_describe() -> None:
    result = DEFAULT_DICTIONARY.describe("appnid:bm_Barley", True)
    assert result is not None
    assert "Genus : Hordeum" in result


def test_format_iri_list() -> None:
    result = DEFAULT_DICTIONARY.format_iri_list(
        DEFAULT_DICTIONARY.list_classes(namespace="appn")
    )
    assert result is not None
    assert "appn:Trait" in result
    assert f"{APPN_SCHEMA}Trait" in result


def test_format_triple_list() -> None:
    result = DEFAULT_DICTIONARY.format_triple_list(
        DEFAULT_DICTIONARY.list_triples_for_subject("appn:ObservedVariable")
    )
    assert result is not None
    assert "schema:name" in result
    assert "appn:Variable" in result


def test_build_iri() -> None:
    result = DEFAULT_DICTIONARY.build_iri(IRI("appn:ObservedVariable"), "au", "Guess")
    assert result is not None
    assert result.curie == "au:ov_Guess"


def test_build_clean_name() -> None:
    result = DEFAULT_DICTIONARY.build_clean_name(
        IRI("appn:ObservedVariable"), "the new name"
    )
    assert result is not None
    assert result == "ov_TheNewName"


def test_domain_range_property() -> None:
    # Property from unique match within schema
    bu = IRI("appn:BiologicalUnit")
    bm = IRI("appn:BiologicalMaterial")
    assert DEFAULT_DICTIONARY.get_domain_range_property(bu, bm) == IRI(
        "appn:hasBiologicalMaterial"
    )
    # Property from settings override
    gf = IRI("appn:GrowthFacility")
    sensor = IRI("appn:Sensor")
    assert DEFAULT_DICTIONARY.get_domain_range_property(gf, sensor) == IRI("appn:hosts")
    # No property defined
    assert DEFAULT_DICTIONARY.get_domain_range_property(sensor, bm) is None
