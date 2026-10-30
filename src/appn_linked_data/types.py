#!/usr/bin/env python3

"""types - Reusable type definitions for appn-linked-data tools."""

from __future__ import annotations

import logging
from enum import IntEnum, StrEnum
from typing import Any, NamedTuple

from rdflib import Node, URIRef

### Issue #####################################################################


class Issue(NamedTuple):
    """Simple class for notifiable issues.

    :param level: Log level for issue (from `logging`)
    :param module: String name for module logging issue
    :param message: Error message
    :param properties: Dictionary of additional information
    """

    level: int
    module: str
    message: str
    properties: dict[str, str]

    def __str__(self) -> str:
        """Produce informative string for logging."""
        if len(self.properties) > 0:
            property_string = f"(Properties: {'; '.join([f'{k}: {v}' for k, v in self.properties.items()])})"
        else:
            property_string = ""
        return f"{logging.getLevelName(self.level)} - {self.module}: {self.message}{property_string}"


### Organisation ##############################################################


class Organisation(NamedTuple):
    """Simple class for organisation properties.

    :param id: Short identifier for the organisation
    :param name: Name of the organisation
    :param ror: ROR identifier for the organisation
    :param namespace: Namespace for organisation vocabulary
    :param prefix: Prefix to be used for namespace in CURIEs
    """

    id: str
    name: str
    ror: str
    namespace: str
    prefix: str


### NamespaceDefinition #######################################################


class NamespaceDefinition(NamedTuple):
    """Simple class for namespace definitions.

    :param namespace: Namespace for a linked-data asset
    :param prefix: Prefix to be used for namespace
    :param path: Path to access machine-readable RDF for namespace terms
    """

    ns: str
    prefix: str
    path: str


### CompletionRuleProperty ####################################################


class CompletionRuleProperty(StrEnum):
    """Simple class for permitted properties for a `CompletionRule."""

    TYPE = "type"


### CompletionRuleType ########################################################


class CompletionRuleType(StrEnum):
    """Simple class for permitted choices for `type` in a `CompletionRule."""

    REFLEXIVE = "reflexive"


### IRI #######################################################################


class IRI(URIRef):
    """Subclass of URIRef offering easy access to ns, prefix, curie and name.

    IRI can be used wherever a URIRef is expected
    """

    # Reserve property names for instances
    __slots__ = ("_curie", "_name", "_ns", "_prefix")

    namespace_definitions: dict[str, NamespaceDefinition] | None = None

    def __new__(
        cls,
        iri: str | URIRef,
        namespace_definition: NamespaceDefinition | None = None,
    ) -> IRI:
        """IRI offers URIRef behaviour with additional properties.

        If the supplied string lacks a namespace and prefix, assume it is
        an unqualified name and should be scoped to the namespace.

        :param iri: An existing URIRef or IRI string
        :param namespace_definition: `NamespaceDefinition` to determine namespace and prefix.
        """
        iri = str(iri)

        if namespace_definition is not None:
            ns = namespace_definition.ns
            prefix = namespace_definition.prefix
            if iri.startswith(namespace_definition.ns):
                name = iri[len(namespace_definition.ns) :]
                curie = f"{namespace_definition.prefix}:{name}"
            elif iri.startswith(f"{namespace_definition.prefix}:"):
                name = iri[len(namespace_definition.prefix) + 1 :]
                curie = iri
                iri = f"{namespace_definition.ns}{name}"
            elif iri == namespace_definition.prefix:
                name = ""
                curie = prefix
                iri = namespace_definition.ns
            else:
                name = iri
                curie = f"{namespace_definition.prefix}:{iri}"
                iri = f"{namespace_definition.ns}{iri}"
        else:
            ns = ""
            prefix = ""
            curie = iri
            name = iri

        obj = super().__new__(cls, iri)
        obj._ns = ns
        obj._prefix = prefix
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
        return self._ns  # type: ignore[attr-defined]

    @property
    def prefix(self) -> str:
        """Get namespace prefix as string.

        :return: Namespace prefix string
        """
        return self._prefix  # type: ignore[attr-defined]

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


### Triple ####################################################################


class Triple(NamedTuple):
    """Simple class to represent a triple of strings.

    :param subject: `IRI` for the subject of a triple
    :param property: `IRI` for the property of a triple
    :param object: `IRI`|Literal  for the object of a triple
    """

    subject: IRI | Node
    property: IRI | Node
    object: IRI | Node


### TriplePosition ############################################################


class TriplePosition(IntEnum):
    """Simple class for positions in a triple."""

    SUBJECT = 0
    PROPERTY = 1
    OBJECT = 2
