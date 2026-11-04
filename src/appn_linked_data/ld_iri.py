#!/usr/bin/env python3

"""ld_iri - IRI representation for APPN linked data."""

from __future__ import annotations

import logging
from enum import IntEnum
from typing import Any

from pydantic import (
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
from rdflib import Node, URIRef

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

        :param other: Object with which to compare
        :return: True if object IRI strings match
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


### TriplePosition ############################################################


class TriplePosition(IntEnum):
    """Simple class for positions in a triple."""

    SUBJECT = 0
    PREDICATE = 1
    OBJECT = 2


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
