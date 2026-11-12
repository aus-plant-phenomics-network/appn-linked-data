#!/usr/bin/env python3

"""ld_dictionary - Import RDF assets into a graph and support diverse query mechanisms.

Import RDF assets into a graph and support diverse query mechanisms

A primary use case is to make the APPN schema and the ontologies it
references accessible for automated use in data processing.

A `Dictionary` can wrap any existing `Graph` to enable it to be explored
more easily

The `Dictionary` class includes several utility methods to assist with
standardisation of `IRI` strings and clean names without whitespace.
"""

from __future__ import annotations

import logging
import re
import textwrap
from importlib import resources

from pydantic import AnyHttpUrl, FilePath
from rdflib import BNode, Graph, Node, URIRef
from rdflib.namespace import Namespace, NamespaceManager

from appn_linked_data import assets
from appn_linked_data.ld_constants import (
    ALT_SCHEMA_SCHEMA,
    ANU_VOCABULARY,
    APPN_SCHEMA,
    APPN_VOCABULARY,
    AU_VOCABULARY,
    BIO_SCHEMA,
    CDI_SCHEMA,
    CDIF_SCHEMA,
    CSU_VOCABULARY,
    DC_SCHEMA,
    DPIRD_VOCABULARY,
    DWC_SCHEMA,
    LTU_VOCABULARY,
    OWL_SCHEMA,
    PPEO_SCHEMA,
    PROV_SCHEMA,
    RDF_SCHEMA,
    RDFS_SCHEMA,
    SCHEMA_SCHEMA,
    SKOS_SCHEMA,
    SOSA_SCHEMA,
    SSN_SCHEMA,
    UQ_VOCABULARY,
    USYD_VOCABULARY,
    UWA_VOCABULARY,
    WSU_VOCABULARY,
    XML_SCHEMA,
)
from appn_linked_data.ld_iri import (
    IRI,
    RDF_PROPERTY,
    RDF_TYPE,
    RDFS_CLASS,
    RDFS_LABEL,
    SCHEMA_NAME,
    SKOS_CONCEPT,
    Triple,
    TriplePosition,
)
from appn_linked_data.ld_namespaces import (
    AssetLoadLocation,
    NamespaceDefinition,
    NamespaceDefinitionManager,
)
from appn_linked_data.ld_settings import (
    ExplicitTermsFilter,
    LinkedDataSettings,
)

logger = logging.getLogger(__name__)

### NAME_REPLACEMENT_PATTERN ##################################################

NAME_REPLACEMENT_PATTERN = re.compile(r"[\s'\"\\?;:,°*+(){}/\[\]-]+")

### Dictionary ################################################################

# BNode prefix - ensure BNodes are recognised and handled correctly.
# BNodes are displayed as strings and not handled by the IRI class. When
# displayed by Dictionary, they include this prefix. When a request is
# received to display triples for a string with this prefix, it is
# stripped and matched with the string representation for the BNode.
BNODE_PREFIX = "::"

# Limit for display of text strings in multi-column format
MAX_COLUMN_LENGTH = 80

NAMESPACE_ASSETS: dict[str, str] = {
    APPN_SCHEMA: "appn-schema.ttl",
    CDI_SCHEMA: "DDICDILibrary.ttl",
    PPEO_SCHEMA: "PPEO.owl",
    BIO_SCHEMA: "bioschemas_types.ttl",
    DC_SCHEMA: "dublin_core_terms.rdf",
    PROV_SCHEMA: "prov.ttl",
    RDF_SCHEMA: "22-rdf-syntax-ns.ttl",
    RDFS_SCHEMA: "rdf-schema.ttl",
    SCHEMA_SCHEMA: "schemaorg-current-http.ttl",
    ALT_SCHEMA_SCHEMA: "schemaorg-current-https.ttl",
    SKOS_SCHEMA: "skos.rdf",
    SOSA_SCHEMA: "sosa.ttl",
    SSN_SCHEMA: "ssn.ttl",
    DWC_SCHEMA: "dwc-terms.ttl",
    OWL_SCHEMA: "owl.ttl",
    CDIF_SCHEMA: "cdifCoreStructuredSchema.json",
    APPN_VOCABULARY: "APPN_vocabulary.ttl",
    ANU_VOCABULARY: "ANU_vocabulary.ttl",
    AU_VOCABULARY: "AU_vocabulary.ttl",
    CSU_VOCABULARY: "CSU_vocabulary.ttl",
    DPIRD_VOCABULARY: "DPIRD_vocabulary.ttl",
    LTU_VOCABULARY: "LTU_vocabulary.ttl",
    UQ_VOCABULARY: "UQ_vocabulary.ttl",
    USYD_VOCABULARY: "USYD_vocabulary.ttl",
    UWA_VOCABULARY: "UWA_vocabulary.ttl",
    WSU_VOCABULARY: "WSU_vocabulary.ttl",
}


class Dictionary:
    """Wrapper class around rdflib Graph instance to simplify common query needs.

    A new Dictionary has an empty graph and cache. Linked-data objects can be
    added to the graph via the load() method. When the graph changes, the
    response cache is cleared.

    All get_* and list_* methods check the cache for a previous response to the
    request and otherwise generate and cache a new response from the graph.

    The main cache is managed by the class (rather than using `functools.cache` or
    `functools.lru_cache`) since it needs to be flushed whenever a new asset
    is loaded. Caches for the name and type for IRIs use `functools.cache` since
    the results are not expected to change.
    """

    def __init__(
        self,
        graph: Graph | None = None,
    ) -> None:
        """Initialise properties based either on a supplied `Graph` or a new empty one.

        Use any `NamespaceDefinition`s to manage prefixes and locations for
        loading assets.

        :param graph: Optional `Graph` to initialise `Dictionary` - note that
            any `load` operations will modify the graph for all users.
        """
        self._graph = Graph() if graph is None else graph
        self.namespace_manager = NamespaceManager(self._graph)
        self.namespace_dictionary = (
            NamespaceDefinitionManager().get_namespace_dictionary()
        )
        self.namespace_prefix_dictionary = (
            NamespaceDefinitionManager().get_namespace_prefix_dictionary()
        )

        self.settings = LinkedDataSettings()

        # Force selection of HTTP/HTTPS for schema.org to match imported
        # assets and RO-Crate expectations and preferred prefixes for all other
        # namespaces.
        self.namespace_manager.bind("altschema", ALT_SCHEMA_SCHEMA)
        for namespace in self.namespace_dictionary:
            if namespace != ALT_SCHEMA_SCHEMA:
                self.namespace_manager.bind(
                    self.namespace_dictionary[namespace].prefix, namespace
                )

        # Keep track of what namespaces have been loaded
        self.loaded: set[str] = set()

        # Cache for response values. In future this could be changed to a pair
        # of LRU caches, a large one for IRIs and one for all other responses.
        self.cache: dict[
            str,
            list[IRI] | list[Triple] | dict[IRI, int] | list[tuple[IRI | Node, ...]],
        ] = {}

    def get_graph(self) -> Graph:
        """Return graph.

        :return: Internal `Graph` instance
        """
        return self._graph

    def load(  # noqa: PLR0912
        self,
        asset_namespace: str,
        asset_path: AssetLoadLocation | AnyHttpUrl | FilePath | None = None,
        asset_prefix: str | None = None,
    ) -> bool:
        """Load an RDF asset (any format supported by `rdflib`).

        The method loads definitions from the specified namespace into the
        `Graph`. If the path (file location) and/or prefix are not passed to
        the method, the supplied `NamespaceDefinition`s (if any) are checked
        for the missing information. If they are still not defined, the
        namespace will be given an anonymous prefix and loaded from the
        namespace URL.

        :param asset_namespace: Namespace string for asset
        :param asset_path: Optional location for a file containing RDF definitions for the namespace (in any supported RDF format)
        :param asset_prefix: Prefix to use for namespace in CURIE representations
        :return: True if successful
        """
        namespace_definition: NamespaceDefinition | None = None

        # Tolerate prefix as alias for namespace
        if (
            not asset_namespace.startswith("http")
            and asset_namespace in self.namespace_prefix_dictionary
        ):
            namespace_definition = self.namespace_prefix_dictionary[asset_namespace]
            logger.debug(
                "Found and mapped namespace for %s: %s",
                asset_namespace,
                namespace_definition,
            )
            asset_namespace = namespace_definition.namespace

        # Check for `NamespaceDefinition`
        elif asset_namespace in self.namespace_dictionary:
            namespace_definition = self.namespace_dictionary[asset_namespace]
            logger.debug(
                "Found namespace for %s: %s",
                asset_namespace,
                namespace_definition,
            )

        # Determine where to load the asset from, either a supplied path, or
        # one from a `NamespaceDefinition`, or the namespace URL.
        if asset_path is None:
            asset_path = (
                namespace_definition.location
                if (
                    namespace_definition is not None
                    and namespace_definition.location is not None
                )
                else AnyHttpUrl(asset_namespace)
            )

        # Determine what prefix to use for the namespace, either a supplied
        # parameter, or one from a `NamespaceDefinition`, or an anonymous
        # prefix in the series ns1, ns2, ...
        if asset_prefix is None:
            if (
                namespace_definition is not None
                and namespace_definition.prefix is not None
            ):
                asset_prefix = namespace_definition.prefix
            else:
                index = 1
                while f"ns{index}" in self.namespace_prefix_dictionary:
                    index += 1
                asset_prefix = f"ns{index}"

        # Load the asset into the `Graph` and bind it with the prefix
        logger.debug(
            "Loading %s from %s with prefix: %s",
            {asset_namespace},
            asset_path,
            asset_prefix,
        )
        try:
            if isinstance(asset_path, AssetLoadLocation):
                if (
                    asset_path == AssetLoadLocation.INTERNAL
                    and asset_namespace in NAMESPACE_ASSETS
                ):
                    self._graph.parse(
                        resources.files(assets) / NAMESPACE_ASSETS[asset_namespace]  # type: ignore[arg-type]
                    )
                else:
                    self._graph.parse(asset_namespace)
            else:
                self._graph.parse(asset_path)  # type: ignore[arg-type]

            self.loaded.add(asset_namespace)
            if asset_prefix is not None:
                self.namespace_manager.bind(
                    asset_prefix, Namespace(asset_namespace), override=True
                )
                definition = NamespaceDefinition(
                    namespace=asset_namespace,
                    prefix=asset_prefix,
                    location=asset_path,  # type: ignore[arg-type]
                )
                NamespaceDefinitionManager().add_namespace_definition(definition)

            # Clear any cached query results because the `Graph` has changed,
            # and update the namespace dictionaries.
            self.cache = {}

            logger.debug("Loaded %s", asset_namespace)

        except Exception:
            logger.exception("Failed to load %s as linked data asset", asset_namespace)
            return False

        return True

    def import_references(self) -> bool:
        """Load all RDF assets referenced (one-hop) by existing triples in the `Graph`.

        For all IRIs in the `Graph`, if the namespace asset has not already been
        loaded, attempt to do so.

        :return: True if successful
        """
        success = True
        iris = set()
        self.load(OWL_SCHEMA)
        for s, o, p in self._graph:
            for iri in [s, o, p]:
                if isinstance(iri, URIRef) and iri not in iris:
                    ns = self.get_namespace_from_iri(iri)
                    logger.debug("Mapped <%s> to namespace <%s>", iri, ns)
                    # If we detect the unused version of the schema.org namespace,
                    # something has gone wrong.
                    if ns == ALT_SCHEMA_SCHEMA:
                        logger.error(
                            "Unexpected use of alternative schema.org namespace (%s) in triple (%s, %s, %s)",
                            ALT_SCHEMA_SCHEMA,
                            str(s),
                            str(o),
                            str(p),
                        )
                        success = False
                    # Don't try importing XSD - no RDF representation available
                    elif ns is not None and ns not in self.loaded and ns != XML_SCHEMA:
                        if not self.load(ns):
                            success = False
                    logger.debug("Found IRI <%s>", iri)
                    iris.add(iri)
        return success

    def get_namespace_from_iri(self, iri: str | IRI) -> str | None:
        """Find the namespace to which an IRI belongs.

        :param iri: IRI for request
        :return: Namespace string if the IRI matches one of the known
            namespaces, otherwise None
        """
        iri = IRI(iri)
        if iri.ns not in [None, ""]:
            return iri.ns
        return None

    def get_namespaces(self) -> dict[str, str]:
        """Get mappings of namespace prefixes to namespaces.

        :return: Dictionary of namespace prefixes to loaded namespaces
        """
        return {
            k: self.namespace_prefix_dictionary[k].namespace
            for k in sorted(self.namespace_prefix_dictionary.keys())
        }

    def list_triples(self) -> list[Triple]:
        """Return all `Triple`s in the `Graph` with `URIRef`s upgraded to `IRI`s.

        :return: List of `Triples` based on `Graph` contents
        """
        key = "triples"
        if key not in self.cache:
            self.cache[key] = [Triple(s, p, o) for s, p, o in self._graph]
        return self.cache[key].copy()  # type: ignore[return-value]

    def list_unique_subjects(self, namespace: str | None = None) -> list[IRI]:
        """Return list of all IRIs used as subjects for triples.

        Results may optionally be filtered to matches within a specified
        namespace.

        :param namespace: Optional namespace for filtering results
        :return: List of `IRIs` for subject IRIs
        """
        return self.list_unique_terms_by_position(TriplePosition.SUBJECT, namespace)

    def list_unique_properties(self, namespace: str | None = None) -> list[IRI]:
        """Return list of all IRIs used as properties for triples.

        Results may optionally be filtered to matches within a specified
        namespace.

        :param namespace: Optional namespace for filtering results
        :return: List of `IRIs` for property IRIs
        """
        return self.list_unique_terms_by_position(TriplePosition.PREDICATE, namespace)

    def list_unique_objects(self, namespace: str | None = None) -> list[IRI]:
        """Return list of all IRIs used as objects for triples.

        Results may optionally be filtered to matches within a specified
        namespace.

        :param namespace: Optional namespace for filtering results
        :return: List of `IRIs` for object IRIs
        """
        return self.list_unique_terms_by_position(TriplePosition.OBJECT, namespace)

    def list_unique_terms_by_position(
        self, position: TriplePosition, namespace: str | None = None
    ) -> list[IRI]:
        """Return list of all IRIs from a position in a triple.

        Results may optionally be filtered to matches within a specified
        namespace.

        :param position: `TriplePosition` specifying which item in triple is
            targeted
        :param namespace: Optional namespace for filtering results
        :return: List of `IRIs` for IRIs in specified position
        """
        if namespace is None:
            namespace = ""
        elif namespace in self.namespace_prefix_dictionary:
            namespace = self.namespace_prefix_dictionary[namespace].namespace
        if namespace in self.namespace_dictionary:
            full_curie = f"{self.namespace_dictionary[namespace]}:"
        else:
            full_curie = None

        values = {
            str(triple[position])
            for triple in self._graph
            if isinstance(triple[position], URIRef)
        }
        return [
            IRI(value)
            for value in sorted(values)
            if (
                value.startswith(namespace)
                or (full_curie is not None and value.startswith(full_curie))
            )
        ]

    def list_triples_for_subject(self, subject_: str | IRI) -> list[Triple]:
        """Return list of all `Triple`s with a given term as subject.

        :param subject_: String IRI or `IRI`
        :return: List of `Triple`s with given subject
        """
        if isinstance(subject_, str) and subject_.startswith(BNODE_PREFIX):  # type: ignore[redundant-expr]
            subject_ = subject_[len(BNODE_PREFIX) :]
        else:
            subject_ = IRI(subject_)

        key = f"subject|{subject_}"

        if key not in self.cache:
            self.cache[str(key)] = self.filter_triples(subject_=subject_)

        return self.cache[key].copy()  # type: ignore[return-value]

    def list_triples_for_object(self, object_: str | IRI) -> list[Triple]:
        """Return list of all `Triple`s with a given term as object.

        :param object_: String IRI or `IRI`
        :return: List of `Triple`s with given object
        """
        object_ = IRI(object_)
        key = f"object|{object_}"

        if key not in self.cache:
            self.cache[key] = self.filter_triples(object_=object_)

        return self.cache[key].copy()  # type: ignore[return-value]

    def list_triples_for_property(self, property_: str | IRI) -> list[Triple]:
        """Return list of all `Triple`s with a given property term.

        :param property_: String IRI or `IRI`
        :return: List of `Triple`s with given property term
        """
        property_ = IRI(property_)
        key = f"property|{property_}"

        if key not in self.cache:
            self.cache[key] = self.filter_triples(property_=property_)

        return self.cache[key].copy()  # type: ignore[return-value]

    def count_triples_by_subject(self) -> dict[IRI, int]:
        """Return count of Triple`s  for every term used as subject.

        :return: Counts of matching `Triple`s per term
        """
        return self.count_triples_by_term(TriplePosition.SUBJECT)

    def count_triples_by_property(self) -> dict[IRI, int]:
        """Return count of Triple`s for every term used as property.

        :return: Counts of matching `Triple`s per term
        """
        return self.count_triples_by_term(TriplePosition.PREDICATE)

    def count_triples_by_object(self) -> dict[IRI, int]:
        """Return count of Triple`s for every term used as object.

        :return: Counts of matching `Triple`s per term
        """
        return self.count_triples_by_term(TriplePosition.OBJECT)

    def count_triples_by_term(self, position: TriplePosition) -> dict[IRI, int]:
        """Return counts of Triple`s for every term in a specified position.

        :param position: `TriplePosition` specifying which item in triple is
            targeted
        :return: Counts of matching `Triple`s per term
        """
        key = "counts|position"
        if key in self.cache:
            return self.cache[key].copy()  # type: ignore[return-value]

        counts = {}
        for term in [triple.term(position) for triple in self.list_triples()]:
            if isinstance(term, IRI):
                if term not in counts:
                    counts[term] = 1
                else:
                    counts[term] += 1

        self.cache[key] = counts

        return counts.copy()

    def list_classes(
        self,
        namespace: str | None = None,
    ) -> list[IRI]:
        """List all classes (type rdfs:Class) in `Graph`.

        Results may optionally be filtered to matches within a specified
        namespace.

        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for classes
        """
        class_subclasses = self.list_subclasses(RDFS_CLASS)
        return self.list_iris(
            [
                " UNION ".join(
                    [f"{{ ?q rdf:type <{class_.iri}> }}" for class_ in class_subclasses]
                )
                + "."
            ],
            f"classes|{namespace}",
            namespace,
        )

    def list_properties(
        self,
        namespace: str | None = None,
    ) -> list[IRI]:
        """List all properties (type rdfs:Property) in `Graph`.

        Results may optionally be filtered to matches within a specified
        namespace.

        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for properties
        """
        property_subclasses = self.list_subclasses(RDF_PROPERTY)
        return self.list_iris(
            [
                " UNION ".join(
                    [
                        f"{{ ?q rdf:type <{property_.iri}> }}"
                        for property_ in property_subclasses
                    ]
                )
                + "."
            ],
            f"properties|{namespace}",
            namespace,
        )

    def list_superclasses(
        self,
        class_iri: str | IRI,
        namespace: str | None = None,
    ) -> list[IRI]:
        """List all superclasses of a specified class (including the class itself).

        Results may optionally be filtered to matches within a specified
        namespace.

        :param class_iri: String IRI or `IRI` for class
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for classes
        """
        logger.debug("Finding all superclasses for class %s", class_iri)
        return self.list_iris_transitive(
            class_iri,
            "rdfs:subClassOf",
            f"superclasses|{class_iri}|{namespace}",
            namespace=namespace,
        )

    def list_superproperties(
        self,
        property_iri: str | IRI,
        namespace: str | None = None,
    ) -> list[IRI]:
        """List all superproperties of a specified property (including the property itself).

        Results may optionally be filtered to matches within a specified
        namespace.

        :param property_iri: String IRI or `IRI` for property
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for properties
        """
        logger.debug("Finding all superproperties for property %s", property_iri)
        return self.list_iris_transitive(
            property_iri,
            "rdfs:subPropertyOf",
            f"superproperties|{property_iri}|{namespace}",
            namespace=namespace,
        )

    def list_subclasses(
        self,
        class_iri: str | IRI,
        namespace: str | None = None,
    ) -> list[IRI]:
        """List all subclasses of a specified class (including the class itself).

        Results may optionally be filtered to matches within a specified
        namespace.

        :param class_iri: String IRI or `IRI` for class
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for classes
        """
        logger.debug("Finding all subclasses for class %s", class_iri)
        return self.list_iris_transitive(
            class_iri,
            "rdfs:subClassOf",
            f"subclasses|{class_iri}|{namespace}",
            namespace=namespace,
            reverse=True,
        )

    def list_subproperties(
        self,
        property_iri: str | IRI,
        namespace: str | None = None,
    ) -> list[IRI]:
        """List all subproperties of a specified property (including the property itself).

        Results may optionally be filtered to matches within a specified
        namespace.

        :param property_iri: String IRI or `IRI` for property
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for properties
        """
        logger.debug("Finding all subproperties for property %s", property_iri)
        return self.list_iris_transitive(
            property_iri,
            "rdfs:subPropertyOf",
            f"subproperties|{property_iri}|{namespace}",
            namespace=namespace,
            reverse=True,
        )

    def list_domain_properties_for_class(
        self,
        class_iri: str | IRI,
        namespace: str | None = None,
    ) -> list[IRI]:
        """List all known properties that include a specified class in their domain.

        Results may optionally be filtered to matches within a specified
        namespace.

        :param class_iri: String IRI or `IRI` for class
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for properties
        """
        class_iri = IRI(class_iri)
        query_strings = [
            f"{{ ?q schema:domainIncludes <{class_.iri}> }} UNION {{ ?q rdfs:domain <{class_.iri}> }} ."
            for class_ in self.list_superclasses(class_iri)
        ]
        return self.list_iris(
            query_strings, f"domain|{class_iri}|{namespace}", namespace
        )

    def list_range_properties_for_class(
        self,
        class_iri: str | IRI,
        namespace: str | None = None,
    ) -> list[IRI]:
        """List all known properties that include a specified class in their range.

        Results may optionally be filtered to matches within a specified
        namespace.

        :param class_iri: String IRI or `IRI` for class
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for properties
        """
        class_iri = IRI(class_iri)
        query_strings = [
            f"{{ ?q schema:rangeIncludes <{class_.iri}> }} UNION {{ ?q rdfs:range <{class_.iri}> }} ."
            for class_ in self.list_superclasses(class_iri)
        ]
        return self.list_iris(
            query_strings, f"range_properties|{class_iri}|{namespace}", namespace
        )

    def get_domain_range_property(self, domain_iri: IRI, range_iri: IRI) -> IRI | None:
        """Return the property that should be used to link instances of a domain class with those of an instance class.

        If a property is configured in `LinkedDataSettings`.`get_domain_range_properties`,
        return that. Otherwise, if only one APPN property has the specified classes
        in its domain and range, return that. Otherwise, return None.

        :param domain_iri: IRI for domain class.
        :param range_iri: IRI for range class.
        :return: IRI for selected property if any.
        """
        cache_key = f"domain_range_property|{domain_iri}|{range_iri}"
        if cache_key in self.cache:
            return self.cache[cache_key]  # type: ignore[return-value]

        domain_range_properties = self.settings.get_domain_range_properties()
        if (
            domain_iri in domain_range_properties
            and range_iri in domain_range_properties[domain_iri]
        ):
            property_iri: IRI | None = domain_range_properties[domain_iri][range_iri]
        else:
            range_properties = self.list_properties_by_domain_and_range(
                domain_iri,
                range_iri,
                namespace=APPN_SCHEMA,
            )
            property_iri = range_properties[0] if len(range_properties) == 1 else None

        self.cache[cache_key] = property_iri  # type: ignore[assignment]
        return property_iri

    def list_domain_classes_for_property(
        self,
        property_iri: str | IRI,
        namespace: str | None = None,
    ) -> list[IRI]:
        """List all known classes that are included in the domain of a specified property.

        If a specific `rdfs:domain` is included for the property or one of its superproperties,
        return that class - it is an exclusive domain.

        Otherwise, return the union of all classes included in `schema:domainIncludes` properties
        for the property or one of its superproperties. These are inclusive domains, documenting
        expectations rather than constraints.

        Results may optionally be filtered to matches within a specified
        namespace.

        :param property_iri: String IRI or `IRI` for property
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for classes
        """
        property_iri = IRI(property_iri)

        cache_key = f"domain|{property_iri}|{namespace}"
        if cache_key in self.cache:
            return self.cache[cache_key].copy()  # type: ignore[return-value]

        superproperties = self.list_superproperties(property_iri)

        for property_ in superproperties:
            exact_domain = self.list_iris(
                [f"{{ <{property_}> rdfs:domain ?q }} ."],
                f"exact_domain|{property_}|{namespace}",
            )
            if len(exact_domain) == 1:
                self.cache[cache_key] = self.list_subclasses(exact_domain[0])
                return self.cache[cache_key].copy()  # type: ignore[return-value]

        query_strings = [
            f"{{ <{property_}> schema:domainIncludes ?q }} ."
            for property_ in superproperties
        ]
        return self.list_iris(query_strings, cache_key, namespace)

    def list_range_classes_for_property(
        self,
        property_iri: str | IRI,
        namespace: str | None = None,
    ) -> list[IRI]:
        """List all known classes that are included in the range of a specified property.

        If a specific `rdfs:range` is included for the property or one of its superproperties,
        return that class - it is an exclusive range.

        Otherwise, return the union of all classes included in `schema:rangeIncludes` properties
        for the property or one of its superproperties. These are inclusive ranges, documenting
        expectations rather than constraints.

        Results may optionally be filtered to matches within a specified
        namespace.

        :param property_iri: String IRI or `IRI` for property
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for classes
        """
        property_iri = IRI(property_iri)

        cache_key = f"range_classes|{property_iri}|{namespace}"
        if cache_key in self.cache:
            return self.cache[cache_key].copy()  # type: ignore[return-value]

        superproperties = self.list_superproperties(property_iri)

        for property_ in superproperties:
            exact_range = self.list_iris(
                [f"{{ <{property_}> rdfs:range ?q }} ."],
                f"exact_range|{property_}|{namespace}",
            )
            if len(exact_range) == 1:
                self.cache[cache_key] = self.list_subclasses(
                    exact_range[0], namespace=namespace
                )
                return self.cache[cache_key].copy()  # type: ignore[return-value]

        query_strings = [
            f"{{ <{property_}> schema:rangeIncludes ?q }} ."
            for property_ in superproperties
        ]
        return self.list_iris(query_strings, cache_key, namespace)

    def list_instances_without_subclasses(
        self, class_iri: str | IRI, namespace: str | None = None
    ) -> list[IRI]:
        """List all known instances of the specified class ignoring subclasses.

        Results may optionally be filtered to matches within a specified
        namespace.

        :param class_iri: String IRI or `IRI` for class
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for instances
        """
        class_iri = IRI(class_iri)
        return self.list_iris(
            [f"?q rdf:type <{class_iri}> ."],
            f"instances-specific|{class_iri}|{namespace}",
            namespace,
        )

    def list_instances(
        self, class_iri: str | IRI, namespace: str | None = None
    ) -> list[IRI]:
        """List all known instances of the specified class or a known subclass.

        Results may optionally be filtered to matches within a specified
        namespace.

        :param class_iri: String IRI or `IRI` for class
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for instances
        """
        key = f"instances|{class_iri}|{namespace}"
        if key in self.cache:
            return self.cache[key].copy()  # type: ignore[return-value]

        instances = set()
        for class_ in self.list_subclasses(class_iri):
            for instance in self.list_instances_without_subclasses(class_):
                instances.add(instance)
        instance_list: list[IRI] = list(instances)
        self.cache[key] = instance_list
        return instance_list.copy()

    def list_instances_by_class_and_name(
        self,
        class_iri: str | IRI,
        name: str,
        check_alternate_names: bool = False,
        namespace: str | None = None,
    ) -> list[IRI]:
        """List all known instances of the specified class with the specified unqualified name.

        Results may optionally be filtered to matches within a specified
        namespace.

        NOTE: At present, this is case-sensitive.

        :param class_iri: String IRI or `IRI` for class
        :param name: Unqualified name to find
        :param check_alternate_names: True if alternateName properties should
            also be checked
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for instances
        """
        class_iri = IRI(class_iri)
        cache_key = f"instances-class-name|{class_iri}|{name}|{check_alternate_names}|{namespace}"
        query_strings = [
            f"?q rdf:type <{class_iri}> . {{ ?q schema:name '{name}'@en }} UNION {{ ?q schema:name '{name}'}}."
        ]
        query_strings.append(
            f"?q rdf:type <{class_iri}> .  {{ ?q rdfs:label '{name}'@en }} UNION {{ ?q rdfs:label '{name}'}} UNION {{ ?q skos:prefLabel '{name}'@en}} UNION {{ ?q skos:prefLabel '{name}'}}."
        )
        if check_alternate_names:
            query_strings.append(
                f"?q rdf:type <{class_iri}> .  {{ ?q schema:alternateName '{name}'@en }} UNION {{ ?q schema:alternateName '{name}'}} UNION {{ ?q skos:altLabel '{name}'@en }} UNION {{ ?q skos:altLabel '{name}'}}."
            )
        return self.list_iris(query_strings, cache_key, namespace=namespace)

    def list_instances_by_name(
        self,
        name: str,
        check_alternate_names: bool = False,
        namespace: str | None = None,
    ) -> list[IRI]:
        """List all known instances of any or no class with the specified unqualified name.

        Results may optionally be filtered to matches within a specified
        namespace.

        NOTE: At present, this is case-sensitive.

        :param name: Unqualified name to find
        :param check_alternate_names: True if alternateName properties should
            also be checked
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for instances
        """
        cache_key = f"instances-name|{name}|{check_alternate_names}|{namespace}"
        query_strings = [
            f"{{ ?q schema:name '{name}'@en }} UNION {{ ?q schema:name '{name}'}}."
        ]
        query_strings.append(
            f"{{ ?q rdfs:label '{name}'@en }} UNION {{ ?q rdfs:label '{name}'}} UNION {{ ?q skos:prefLabel '{name}'@en}} UNION {{ ?q skos:prefLabel '{name}'}}."
        )
        if check_alternate_names:
            query_strings.append(
                f"{{ ?q schema:alternateName '{name}'@en }} UNION {{ ?q schema:alternateName '{name}'}} UNION {{ ?q skos:altLabel '{name}'@en }} UNION {{ ?q skos:altLabel '{name}'}}."
            )
        return self.list_iris(query_strings, cache_key, namespace=namespace)

    def list_properties_by_name(
        self,
        name: str,
        check_alternate_names: bool = False,
        namespace: str | None = None,
    ) -> list[IRI]:
        """List all known properties with the specified unqualified name.

        Results may optionally be filtered to matches within a specified
        namespace.

        :param property_iri: String IRI or `IRI` for property
        :param name: Unqualified name to find
        :param check_alternate_names: True if alternateName properties should
            also be checked
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for properties
        """
        return self.list_instances_by_class_and_name(
            "rdf:Property",
            name,
            check_alternate_names=check_alternate_names,
            namespace=namespace,
        )

    def list_properties_by_domain_and_range(
        self, domain_iri: str | IRI, range_iri: str, namespace: str | None = None
    ) -> list[IRI]:
        """List all known properties with the specified classes in their domain and range (one of each).

        Results may optionally be filtered to matches within a specified
        namespace.

        :param domain_iri: String IRI or `IRI` for domain
        :param range_iri: String IRI for domain
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI`s for properties
        """
        cache_key = f"domain-and-range|{domain_iri}|{range_iri}|{namespace}"

        if cache_key in self.cache:
            return self.cache[cache_key].copy()  # type: ignore[return-value]

        domain_properties = self.list_domain_properties_for_class(domain_iri, namespace)
        range_properties = self.list_range_properties_for_class(range_iri, namespace)

        properties = list(set(domain_properties) & set(range_properties))

        self.cache[cache_key] = properties

        return properties.copy()

    def list_explicit_classes(
        self, main_class: IRI | str, is_concept: bool = False
    ) -> list[IRI]:
        """Build list of classes (`rdf:type` values) to define for an instance of the given class.

        The `LinkedDataSsettings` can specify superclasses that should automatically
        be inserted, and skos:Concept is included for all vocabulary terms.

        :param main_class_iri: `IRI` for APPN schema class
        :param is_concept: True if `skos:Concept` should be included
        :return: List of IRIs for matching superclasses
        """
        main_class = IRI(main_class)

        key = f"explicit_classes|{main_class}|{is_concept}"

        # Cache to minimise redundant calculations
        if key in self.cache:
            return self.cache[key].copy()  # type: ignore[return-value]

        # Get list of all known classes in inheritance hierarchy for
        # this class (including the class itself)
        superclasses = self.list_superclasses(main_class)

        # Rules determining which superclasses should be added
        explicit_rules = self.settings.get_explicit_classes()

        # Filters to override explicit rules
        excluded_classes = self.settings.get_excluded_classes()

        explicit_classes = []

        for superclass in superclasses:
            if superclass == main_class:
                # Always include the class itself
                explicit_classes.append(main_class)
            else:
                superclass_namespace = IRI(superclass.ns)
                if (
                    superclass_namespace in explicit_rules
                    and superclass not in excluded_classes
                ):
                    rule = explicit_rules[superclass_namespace]
                    if isinstance(rule, list):
                        # Include any class explicitly referenced by a rule
                        if superclass in rule:
                            explicit_classes.append(superclass)
                    elif isinstance(rule, ExplicitTermsFilter):
                        if rule == ExplicitTermsFilter.ALL:
                            # Include all classes matching an "all" rule
                            explicit_classes.append(superclass)
                        elif rule == ExplicitTermsFilter.FIRST:
                            # Match only the first class matching a "first" rule
                            explicit_classes.append(superclass)

                            # Remove the rule so we don't add more matches
                            # NOTE - every call to settings.get_explicit_classes returns
                            # a new copy, so popping the value is safe.
                            explicit_rules.pop(superclass_namespace)

        if is_concept and main_class.ns == APPN_SCHEMA:
            # This IRI is also a SKOS Concept
            explicit_classes.append(SKOS_CONCEPT)

        # Remenber this list
        self.cache[key] = explicit_classes

        return explicit_classes.copy()

    def list_explicit_properties(self, main_property_iri: IRI | str) -> list[IRI]:
        """Build list of properties to define alongside an instance of the given property.

        The `LinkedDataSsettings` can specify superproperties that should automatically
        be inserted.

        :param main_property_iri: `IRI` for APPN schema property
        :return: List of IRIs for matching superproperties
        """
        main_property_iri = IRI(main_property_iri)

        main_property = str(main_property_iri)

        key = f"explicit_properties|{main_property}"

        # Cache to minimise redundant calculations
        if key in self.cache:
            return self.cache[key].copy()  # type: ignore[return-value]

        # Get list of all known properties in inheritance hierarchy for
        # this property (including the property itself)
        superproperties = self.list_superproperties(main_property)

        # Rules determining which superproperties should be added
        explicit_rules = self.settings.get_explicit_properties()

        # Filters to override explicit rules
        excluded_properties = self.settings.get_excluded_properties()

        # Additional property expansions
        property_expansions = self.settings.get_property_expansions()

        if main_property_iri in property_expansions:
            explicit_properties = [
                IRI(term) for term in property_expansions[main_property_iri]
            ]
        else:
            explicit_properties = []

        for superproperty in superproperties:
            if superproperty.iri == main_property:
                # Always include the property itself
                explicit_properties.append(main_property_iri)
            elif (
                superproperty.ns in explicit_rules
                and superproperty.iri not in excluded_properties
            ):
                rule = explicit_rules[superproperty.ns]
                if isinstance(rule, list):
                    # Include any property explicitly referenced by a rule
                    if superproperty.name in rule:
                        explicit_properties.append(IRI(superproperty.iri))
                elif isinstance(rule, str):
                    if rule == ExplicitTermsFilter.ALL.value:
                        # Include all properties matching an "all" rule
                        explicit_properties.append(IRI(superproperty.iri))
                    elif rule == ExplicitTermsFilter.FIRST.value:
                        # Match only the first property matching a "first" rule
                        explicit_properties.append(IRI(superproperty.iri))

                        # Remove the rule so we don't add more matches
                        # NOTE - every call to settings.get_explicit_properties returns
                        # a new copy, so popping the value is safe.
                        explicit_rules.pop(superproperty.ns)

        # Remenber this list
        self.cache[key] = explicit_properties

        return explicit_properties.copy()

    def get_property_for_subject(
        self, subject_: IRI | str, property_: IRI | str
    ) -> Node | None:
        """Return object value matching subject and property.

        Filter the `Graph` and return value from first triple for the supplied subject
        and property.

        :param subject_: Subject for matching triple
        :param property_: Property for matching triple
        :return: Value of property if found - URIRefs are converted to IRIs.
        """
        triples = self.filter_triples(subject_=IRI(subject_), property_=IRI(property_))

        if len(triples) > 0:
            value = triples[0].object
            if isinstance(value, URIRef):
                return IRI(value)
            return value

        return None

    def query(self, sparql_query: str) -> list[tuple[IRI | str, ...]]:
        """Execute SPARQL query against current `Graph`.

        Issue query and convert all URIRefs to IRIs before returning results as a
        list of tuples.

        :param sparql_query: Query string
        :return: List of tuples of `IRI`s or `Node`s
        """
        results: list[tuple[IRI | str, ...]] = []

        logger.debug("Issuing query:\n%s", sparql_query)

        for row in self._graph.query(sparql_query):
            if not isinstance(row, bool):
                results.append(
                    tuple(
                        IRI(item) if isinstance(item, URIRef) else str(item)
                        for item in row
                    )
                )
        return results

    def filter_triples(
        self,
        subject_: IRI | str | None = None,
        property_: IRI | None = None,
        object_: IRI | str | int | float | bool | None = None,
    ) -> list[Triple]:
        """Return triples matching filter values.

        Filter triples in the `Graph` by zero to three options (subject and/or property and/or object).

        :param subject_: Optional IRI for subject of matching triples
        :param property_: Optional IRI for property of matching triples
        :param object_: Optional IRI for object of matching triples
        :return: List of matching triples
        """
        return [
            Triple(s, p, o)
            for s, p, o in self._graph.triples((subject_, property_, object_))  # type: ignore[arg-type]
        ]

    def get_name(self, iri: IRI | str, triples: list[Triple] | None = None) -> str:
        """Return name string for supplied IRI if one can be found.

        Prefered result is a value for schema:name, otherwise for
        rdfs:label. If neither can be found, return the CURIE.

        Results are cached using `functools.cache`.

        :param iri: IRI for which name is sought
        :param triples: List of triples associated with subject - if
            this is not supplied, the method will query the graph.
        :return: Name string
        """
        iri = IRI(iri)

        if triples is None:
            triples = self.list_triples_for_subject(iri)
        label = None

        for t in triples:
            if t.predicate == SCHEMA_NAME:
                return str(t.object)
            if t.predicate == RDFS_LABEL:
                label = str(t.object)
        if label is not None:
            return label
        return str(iri.curie)

    def get_type(
        self, iri: IRI | str, triples: list[Triple] | None = None
    ) -> IRI | None:
        """Return most specific type string available for supplied IRI.

        From all `rdf:type` properties for the IRI, find the one
        that is most specific (not a superclass).

        Results are cached using `functools.cache`.

        :param iri: IRI for which type is sought
        :param triples: List of triples associated with subject - if
            this is not supplied, the method will query the graph.
        :return: IRI for type if one exists
        """
        iri = IRI(iri)

        if triples is None:
            triples = self.list_triples_for_subject(iri)
        iri_types: set[IRI] = set()

        for t in triples:
            if t.predicate == RDF_TYPE and isinstance(t.object, IRI):
                iri_types.add(t.object)

        if len(iri_types) == 0:
            return None

        if len(iri_types) > 1:
            for type_iri in list(iri_types):
                for superclass in self.list_superclasses(type_iri):
                    if superclass != type_iri and superclass in iri_types:
                        iri_types.remove(superclass)

        if len(iri_types) > 1 and SKOS_CONCEPT in iri_types:
            iri_types.remove(SKOS_CONCEPT)

        if len(iri_types) > 1:
            logger.warning(
                "IRI {iri} has multiple types: %s",
                ", ".join([t.curie for t in iri_types]),
            )

        return iri_types.pop()

    def list_iris(
        self, query_strings: list[str], cache_key: str, namespace: str | None = None
    ) -> list[IRI]:
        """List IRIs matching any of a set of SPARQL query strings.

        Results may optionally be filtered using a specified namespace.

        :param query_strings: List of SPARQL query elements
        :param cache_key: Key to store results in cache - this should be
            supplied by the initial caller and None during recursion
        :param namespace: Optional namespace for filtering results
        :return: List of `IRI` instances
        """
        logger.debug(
            "Listing IRIs for query: %s (namespace: %s", str(query_strings), namespace
        )

        full_curie = None
        if namespace is not None and namespace in self.namespace_prefix_dictionary:
            definition = self.namespace_prefix_dictionary[namespace]
            full_curie = f"{namespace}:"
            namespace = definition.namespace
        elif namespace in self.namespace_dictionary:
            full_curie = f"{self.namespace_dictionary[namespace].prefix}:"

        if cache_key in self.cache:
            return self.cache[cache_key].copy()  # type: ignore[return-value]

        results = []

        for q in query_strings:
            query = f"""
                    prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                    prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    prefix schema: <http://schema.org/>

                    SELECT ?q
                    WHERE {{ {q} }}
                    """

            logger.debug("Issuing query:\n%s", query)

            for p in self._graph.query(query):
                # The rdflib `Result` object may be a boolean
                if (
                    not isinstance(p, bool)
                    and isinstance(p[0], URIRef)
                    and (
                        namespace is None
                        or str(p[0]).startswith(namespace)
                        or (full_curie is not None and str(p[0]).startswith(full_curie))
                    )
                ):
                    iri = IRI(str(p[0]))
                    if iri not in results:
                        results.append(iri)

        self.cache[cache_key] = results

        logger.debug("Matching terms: %s", ", ".join([iri.curie for iri in results]))

        return results.copy()

    def list_iris_transitive(
        self,
        subject: str,
        transitive_property: str,
        cache_key: str | None,
        matches: list[IRI] | None = None,
        namespace: str | None = None,
        reverse: bool | None = False,
    ) -> list[IRI]:
        """List IRIs connected to the subject IRI or CURIE by any number of links of the specified property.

        The `matches` parameter is internal for the recursion and should
        not be set by a caller.

        Results may optionally be filtered using a specified namespace.

        :param subject: String IRI or CURIE for starting term
        :param transitive_property: String IRI or CURIE for property to follow
        :param cache_key: Key to store results in cache - this should be
            supplied by the initial caller and None during recursion
        :param matches: IRIs for terms already matched - this should be
            None on the initial call and is set during recursion
        :param namespace: Optional namespace for filtering results
        :param reverse: If True, treat `subject` as the object and find matching subjects
        :return: List of `IRI` instances
        """
        logger.debug(
            "Listing IRIs for subject: %s with transitive property: %s",
            subject,
            transitive_property,
        )

        if cache_key is not None and cache_key in self.cache:
            return self.cache[cache_key].copy()  # type: ignore[return-value]

        full_curie = None
        if namespace is not None and namespace in self.namespace_prefix_dictionary:
            definition = self.namespace_prefix_dictionary[namespace]
            full_curie = f"{namespace}:"
            namespace = definition.namespace
        elif namespace in self.namespace_dictionary:
            full_curie = f"{self.namespace_dictionary[namespace].prefix}:"

        subject_term = IRI(subject)
        property_term = IRI(transitive_property)

        if matches is None:
            matches = []
            if namespace is None or subject_term.ns == namespace:
                matches.append(subject_term)

        if reverse:
            query = f"""
                    prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                    SELECT ?t
                    WHERE {{
                    ?t <{property_term.iri}> <{subject_term.iri}> .
                    }}
                    """
        else:
            query = f"""
                    prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>

                    SELECT ?t
                    WHERE {{
                    <{subject_term.iri}> <{property_term.iri}> ?t .
                    }}
                    """

        logger.debug("Issuing query:\n%s", query)

        for t in self._graph.query(query):
            if isinstance(t, tuple) and isinstance(t[0], URIRef):
                match = IRI(t[0])
                if match not in matches:
                    if (
                        namespace is None
                        or match.ns.startswith(namespace)
                        or (full_curie is not None and str(t[0]).startswith(full_curie))
                    ):
                        matches.append(match)
                    self.list_iris_transitive(
                        match.iri,
                        transitive_property,
                        None,
                        matches,
                        namespace=namespace,
                        reverse=reverse,
                    )

        if cache_key is not None:
            self.cache[cache_key] = matches

        return matches.copy()

    def add_triple(self, triple: Triple) -> None:
        """Add a `Triple` to the `Graph`.

        :param triple: Triple compatible with rdflib `Graph`
        """
        self._graph.add(triple)  # type: ignore[arg-type]

    def describe(self, iri: IRI | str, friendly: bool | None = False) -> str:
        """Format an IRI and its properties.

        :param iri: IRI to be formatted
        :return: Multi-line string with CURIE, IRI and all properties
        """
        iri = IRI(iri)

        triples = self.list_triples_for_subject(iri)

        if friendly:
            iri_type = self.get_type(iri)
            type_string = (
                ""
                if iri_type is None
                else f"{self.get_name(iri_type, triples=triples)}: "
            )
            property_strings = []
            for triple in triples:
                pp = triple.predicate
                po = triple.object
                if isinstance(pp, IRI) and pp not in [SCHEMA_NAME, RDF_TYPE]:  # type: ignore[has-type]
                    property_name = self.get_name(pp).title()  # type: ignore[has-type]
                    if isinstance(po, IRI):  # type: ignore[has-type]
                        object_name = self.get_name(po)  # type: ignore[has-type]
                        object_type = self.get_type(po)  # type: ignore[has-type]
                        if object_type is None:
                            object_value = object_name
                        else:
                            object_value = (
                                f"{object_name} ({self.get_name(object_type)})"
                            )
                    else:
                        object_value = str(po)  # type: ignore[has-type]
                    if len(object_value) > MAX_COLUMN_LENGTH:
                        object_value = "\n" + (
                            "\n".join(
                                textwrap.wrap(
                                    object_value,
                                    width=MAX_COLUMN_LENGTH,
                                    initial_indent="        ",
                                    subsequent_indent="        ",
                                )
                            )
                        )
                    property_strings.append(f"\n    {property_name} : {object_value}")
            formatted = (
                f"{type_string}{self.get_name(iri)}{''.join(sorted(property_strings))}"
            )
        else:
            formatted = f"{iri.curie}   ({iri.iri})"
            for triple in triples:
                pp = triple.predicate
                po = triple.object
                formatted += f"\n    {pp.curie if isinstance(pp, IRI) else str(pp)} : {po.curie if isinstance(po, IRI) else str(po)}"  # type: ignore[has-type]
        return formatted

    def format_iri_list(
        self,
        iris: list[IRI],
        max_rows: int | None = None,
        descriptions: bool | None = False,
    ) -> str:
        """Return string containing (column-aligned) a specified number of elements from each in a list of tuples.

        :param tuples: list of `IRIs` or `Triples` (treated as tuples)
        :param element_count: number of tuple elements to display
        :param max_rows: optional cap on the number of tuples to process
        :param descriptions: If True, output properties for each IRI.
        """
        if len(iris) == 0:
            return ""

        if max_rows is not None:
            iris = iris[0:max_rows]

        if descriptions:
            separator = "\n\n"
            curie_length = 0
        else:
            separator = "\n"
            curie_length = max([len(iri.curie) for iri in iris])
        formatted = []
        for iri in iris:
            if descriptions:
                formatted.append(self.describe(iri))
            else:
                formatted.append(f"{iri.curie:{curie_length}s}   {iri.iri}")
        return separator.join(formatted)

    def format_triple_list(
        self,
        triples: list[Triple],
        max_rows: int | None = None,
        max_node_length: int | None = None,
    ) -> str:
        """Return string containing (column-aligned) a specified number of elements from each in a list of tuples.

        :param tuples: list of `IRIs` or `Triples` (treated as tuples)
        :param max_rows: optional cap on the number of tuples to process
        :param max_node_length: maximum string length for any triple member
        """
        if len(triples) == 0:
            return ""

        if max_rows is not None and max_rows > 1:
            triples = triples[0:max_rows]

        if max_node_length is not None and max_node_length < 1:
            max_node_length = None

        formatted: list[tuple[str, str, str]] = []
        subject_length = 0
        property_length = 0

        for triple in triples:
            s = (
                triple.subject.curie  # type: ignore[attr-defined]
                if isinstance(triple.subject, IRI)
                else (
                    f"{BNODE_PREFIX}{triple.subject!s}"
                    if isinstance(triple.subject, BNode)
                    else str(triple.subject)
                )
            )
            p = (
                triple.predicate.curie  # type: ignore[attr-defined]
                if isinstance(triple.predicate, IRI)
                else str(triple.predicate)
            )
            o = (
                triple.object.curie  # type: ignore[attr-defined]
                if isinstance(triple.object, IRI)
                else (
                    f"{BNODE_PREFIX}{triple.object!s}"
                    if isinstance(triple.object, BNode)
                    else str(triple.object)
                )
            )
            formatted.append((s, p, o))
        subject_length = max([len(s) for s, _, _ in formatted])
        if max_node_length is not None and max_node_length < subject_length:
            subject_length = max_node_length
        property_length = max([len(p) for _, p, _ in formatted])
        if max_node_length is not None and max_node_length < property_length:
            property_length = max_node_length

        return "\n".join(
            [
                f"{s:{subject_length}s}   {p:{property_length}s}   {o if max_node_length is None else o[0:max_node_length]}"
                for s, p, o in formatted
            ]
        )

    def build_iri(self, class_iri: IRI | str, namespace: str, name: str) -> IRI:
        """Generate an IRI for an instance of a class in the node namespace and with the given name.

        Converts an instance name to a safe IRI. The IRI has the pattern
        "<namespace>/<class_identifier>_<name>".

        :param class_iri: The class to which the instance should belong
        :param namespace: The namespace in which the IRI is to be constructed
        :param name:      String name for the search
        :return: Constructed IRI
        """
        if namespace in self.namespace_prefix_dictionary:
            namespace = self.namespace_prefix_dictionary[namespace].namespace

        # Build and return the IRI
        return IRI(f"{namespace}{self.build_clean_name(class_iri, name)}")

    def build_clean_name(self, class_iri: IRI | str, name: str) -> str:
        """Build clean version of instance name with prefix (avoiding whitespace and problematic characters).

        The pattern is <class_identifier>_<title_case_name>".

        :param namespace: The namespace in which the IRI is to be constructed
        :param name:      String name to clean
        :return:          Cleaned TitleCase name
        """
        if not isinstance(class_iri, IRI):
            class_iri = IRI(class_iri)

        class_abbreviations = self.settings.get_class_abbreviations()

        # Use any abbreviation for the class from the `LinkedDataSettings`
        prefix = (class_abbreviations.get(class_iri, class_iri.name)).lower()

        clean_name_string = "".join(
            [
                (w[0].upper() + w[1:])
                for w in NAME_REPLACEMENT_PATTERN.sub(" ", name).strip().split()
            ]
        )

        return f"{prefix}_{clean_name_string}"

    def get_class_dictionary_for_namespace(self, namespace: str) -> dict[str, IRI]:
        """Utility method to map names of all classes in a namespace to IRIs.

        Return class names from given namespace.

        :param namespace: String namespace or prefix
        :return: Dict mapping class names to class IRIs
        """
        cache_key = "class_names|{namespace}"
        if cache_key not in self.cache:
            self.cache[cache_key] = {
                class_.name: class_  # type: ignore[misc]
                for class_ in self.list_classes(namespace=namespace)
            }
        return self.cache[cache_key].copy()  # type: ignore[return-value]
