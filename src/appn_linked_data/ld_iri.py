#!/usr/bin/env python3

"""ld_iri - IRI representation for APPN linked data."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from enum import IntEnum
from typing import Any

from pydantic import (
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
from rdflib import Literal, Node, URIRef

from appn_linked_data.ld_constants import (
    DC_SCHEMA,
    RDF_SCHEMA,
    RDFS_SCHEMA,
    SCHEMA_SCHEMA,
    SKOS_SCHEMA,
    XML_SCHEMA,
)
from appn_linked_data.ld_namespaces import (
    NamespaceDefinitionManager,
)

logger = logging.getLogger(__name__)


### IRI #######################################################################


class IRI(URIRef):
    """Subclass of URIRef offering easy access to ns, prefix, curie and name.

    IRI is also a pydantic model.

    IRI can be used wherever a URIRef is expected.
    """

    # Reserve property names for instances
    __slots__ = ("_curie", "_name", "_namespace_definition")

    # Dictionary of namespace definitions optimised for matching IRIs and CURIEs.
    iri_start_dictionary = NamespaceDefinitionManager().get_iri_start_dictionary()

    def __new__(cls, iri: str | URIRef) -> IRI:
        """IRI offers URIRef behaviour with additional properties.

        If the supplied string lacks a namespace and prefix, assume it is
        an unqualified name and should be scoped to the namespace.

        :param iri: An existing URIRef or IRI string
        :param namespace_definition: `NamespaceDefinition` to determine namespace and prefix.
        """
        if isinstance(iri, IRI):
            return iri

        iri = str(iri)

        namespace_definition = None
        for iri_start_string, definition in cls.iri_start_dictionary.items():
            if iri.startswith(iri_start_string):
                namespace_definition = definition
                break

        if namespace_definition is not None:
            if iri.startswith(namespace_definition.namespace):
                name = iri[len(namespace_definition.namespace) :]
                curie = f"{namespace_definition.prefix}:{name}"
            else:
                name = iri[len(namespace_definition.prefix) + 1 :]
                curie = iri
                iri = f"{namespace_definition.namespace}{name}"
        else:
            curie = iri
            name = iri

        obj = super().__new__(cls, iri)
        obj._namespace_definition = namespace_definition
        obj._name = name
        obj._curie = curie

        return obj

    @property
    def iri(self) -> str:
        """Get IRI as string.

        :return: IRI string
        """
        return self.__str__()

    @property
    def curie(self) -> str:
        """Get CURIE as string.

        :return: CURIE string
        """
        return self._curie  # type: ignore[attr-defined]

    @property
    def name(self) -> str:
        """Get unqualified name as string.

        :return: Unqualified name string
        """
        return self._name  # type: ignore[attr-defined]

    @property
    def ns(self) -> str:
        """Get namespace as string.

        :return: Namespace string
        """
        return (
            ""
            if self._namespace_definition is None  # type: ignore[attr-defined]
            else self._namespace_definition.namespace  # type: ignore[attr-defined]
        )

    @property
    def prefix(self) -> str:
        """Get namespace prefix as string.

        :return: Namespace prefix string
        """
        return (
            ""
            if self._namespace_definition is None  # type: ignore[attr-defined]
            else self._namespace_definition.prefix  # type: ignore[attr-defined]
        )

    def __eq__(self, other: Any) -> bool:
        """Equality with other representations of the same IRI.

        Assert equality with matching `URIRef` and string instances

        :param other: Object with which to compare
        :return: True is object IRI strings match
        """
        if isinstance(other, (URIRef | str)):
            return str(other) == self.iri or str(other) == self.curie
        return super().__eq__(other)  # type: ignore[unreachable]

    def __hash__(self) -> int:
        """Hash the IRI value.

        Hash is based on the IRI string

        :return: Hash value
        """
        return hash(self.iri)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """Return definitions required by pydantic."""

        def validate_from_str(value: str) -> IRI:
            return IRI(value)

        from_str_schema = core_schema.chain_schema(
            [
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(validate_from_str),
            ]
        )

        return core_schema.json_or_python_schema(
            json_schema=from_str_schema,
            python_schema=core_schema.union_schema(
                [core_schema.is_instance_schema(IRI), from_str_schema]
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda instance: instance.iri
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """Return definitions required by pydantic."""
        return handler(core_schema.str_schema())


### Convenience versions of regularly used IRIs ##############################

DC_DESCRIPTION = IRI(f"{DC_SCHEMA}description")
DC_TITLE = IRI(f"{DC_SCHEMA}title")
RDF_PROPERTY = IRI(f"{RDF_SCHEMA}Property")
RDF_TYPE = IRI(f"{RDF_SCHEMA}type")
RDFS_CLASS = IRI(f"{RDFS_SCHEMA}Class")
RDFS_COMMENT = IRI(f"{RDFS_SCHEMA}comment")
RDFS_LABEL = IRI(f"{RDFS_SCHEMA}label")
SCHEMA_COMMENT = IRI(f"{SCHEMA_SCHEMA}comment")
SCHEMA_DESCRIPTION = IRI(f"{SCHEMA_SCHEMA}description")
SCHEMA_DOMAIN_INCLUDES = IRI(f"{SCHEMA_SCHEMA}domainIncludes")
SCHEMA_NAME = IRI(f"{SCHEMA_SCHEMA}name")
SKOS_CONCEPT = IRI(f"{SKOS_SCHEMA}Concept")
SKOS_CONCEPT_SCHEME = IRI(f"{SKOS_SCHEMA}ConceptScheme")
SKOS_IN_SCHEME = IRI(f"{SKOS_SCHEMA}inScheme")
SKOS_PREF_LABEL = IRI(f"{SKOS_SCHEMA}prefLabel")
XML_ANYURI = IRI(f"{XML_SCHEMA}anyURI")
XML_BOOLEAN = IRI(f"{XML_SCHEMA}boolean")
XML_DATETIME = IRI(f"{XML_SCHEMA}dateTime")
XML_DECIMAL = IRI(f"{XML_SCHEMA}decimal")
XML_INTEGER = IRI(f"{XML_SCHEMA}integer")
XML_STRING = IRI(f"{XML_SCHEMA}string")


### TriplePosition ############################################################


class TriplePosition(IntEnum):
    """Simple class for positions in a triple."""

    SUBJECT = 0
    PREDICATE = 1
    OBJECT = 2


TRIPLE_LENGTH = 3

### Triple ####################################################################


class Triple:
    """Simple class to represent a triple."""

    def __init__(self, s: Node, p: Node, o: Node) -> None:
        """Produce `Triple` with IRIs in place of URIRefs.

        :param s: Triple subject as `rdflib` `Node`
        :param p: Triple predicate as `rdflib` `Node`
        :param o: Triple object as `rdflib` `Node`
        :return: `Triple`
        """
        self._subject = IRI(s) if isinstance(s, URIRef) else s
        self._predicate = IRI(p) if isinstance(p, URIRef) else p
        self._object = IRI(o) if isinstance(o, URIRef) else o

    @property
    def subject(self) -> IRI | Node:
        """Get subject of triple.

        :return: IRI or Node
        """
        return self._subject

    @property
    def predicate(self) -> IRI | Node:
        """Get predicate from triple.

        :return: IRI or Node
        """
        return self._predicate

    @property
    def object(self) -> IRI | Node:
        """Get object of triple.

        :return: IRI or Node
        """
        return self._object

    def term(self, position: TriplePosition) -> IRI | Node:
        """Get element of triple by position."""
        if position == TriplePosition.SUBJECT:
            return self._subject
        if position == TriplePosition.PREDICATE:
            return self._predicate
        return self._object

    def __iter__(self) -> Iterator:
        """Return iterator."""
        return (self._subject, self._predicate, self._object).__iter__()

    def __eq__(self, other: Any) -> bool:
        """Equality with other representations of the same triple.

        Assert equality with matching triples containing `URIRef` and
        string instances

        :param other: Object with which to compare
        :return: True is triples match
        """
        if isinstance(other, Triple):
            return (
                other._subject == self._subject
                and other._predicate == self._predicate
                and other._object == self._object
            )
        return (
            isinstance(other, Sequence)
            and len(other) == TRIPLE_LENGTH
            and (self._subject, self._predicate, self._object)
            == (
                other[0],
                other[1],
                other[2] if isinstance(other[2], Node) else Literal(other[2]),
            )
        )

    def __hash__(self) -> int:
        """Hash the triple value.

        Hash is based on the three elements.

        :return: Hash value
        """
        return hash(str(self._subject) + str(self._predicate) + str(self._object))

    def __str__(self) -> str:
        """String representation for triple.

        Display triple elememts.

        :return: String representation
        """
        return f"Triple({self._subject.curie if isinstance(self._subject, IRI) else str(self._subject)}, {self._predicate.curie if isinstance(self._predicate, IRI) else str(self._predicate)}, {self._object.curie if isinstance(self._object, IRI) else str(self._object)})"
