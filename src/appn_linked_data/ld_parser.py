#!/usr/bin/env python3

"""ld_parser - Parser to generate RDF objects from dictlike objects (including `pandas` `Series`).

Public access is via the `DictParser` class which handles dictionaries defining
instances of a single schema class on behalf of a single `Organisation`.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from rdflib import Graph, Literal, Node, URIRef

from appn_linked_data.ld_constants import (
    APPN_SCHEMA,
    CENTRAL_ORGANISATION,
    XML_SCHEMA,
)
from appn_linked_data.ld_dictionary import (
    Dictionary,
)
from appn_linked_data.ld_iri import (
    IRI,
    RDF_PROPERTY,
    RDF_TYPE,
    SCHEMA_COMMENT,
    SCHEMA_DESCRIPTION,
    SCHEMA_NAME,
    SKOS_CONCEPT_SCHEME,
    SKOS_IN_SCHEME,
    SKOS_PREF_LABEL,
    XML_ANYURI,
    XML_BOOLEAN,
    XML_DATETIME,
    XML_DECIMAL,
    XML_INTEGER,
    XML_STRING,
)
from appn_linked_data.ld_issue import ISSUE_TYPE, IssueType
from appn_linked_data.ld_settings import (
    LinkedDataSettings,
    Organisation,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


PROPERTY_NAME_NAME = "name"
NULL_VALUES = [None, np.nan, ""]
TRAILING_INTEGER_PATTERN = re.compile(r"[0-9]+$")


### PropertyHandler classes ##################################################


class PropertyHandler:
    """Transform property value into Triples.

    Base class for all property handlers.

    Each property handler processes data associated with a single dictionary
    key. It processes values associated with the key to generate one or more
    triples for the the current class instance.
    """

    def __init__(
        self,
        parser: DictParser,
        property_name: str,
        target_property: IRI,
        range_class: IRI | None = None,
    ) -> None:
        """Initialise handler.

        Prepare for first value to be processed.

        :param parser: The `DictParser` that created this handler and holds
            runtime attributes required by this handler.
        :param property_name: String name for the property as represented in
            the keys of dictionaries that the parser handles.
        :param target_property: IRI for the primary property to be generated
            by this handler.
        :param range_class: If supplied, the IRI of the class to which all
            range values should belong.
        """
        self.property_name = property_name
        self.parser = parser
        self.target_property = target_property
        self.expanded_properties = parser.dictionary.list_explicit_properties(
            target_property
        )
        # Look for a possible range class in order in:
        # 1) The `range_class` parameter
        # 2) Property specified in `LinkedDataSettings`
        # 3) Implicit parsing of the APPN schema - log an error if multiple
        #    classes match
        self.range_class = (
            range_class
            if range_class is not None
            else LinkedDataSettings().get_property_range_class(
                parser.target_class, target_property
            )
        )
        if self.range_class is None:
            # If there is one matching APPN class or one matching XML type, assume values are
            # references to instances of that class. If more than one class matches, report an
            # error - the choice should be specified in `appn-linked-data.yaml`. Otherwise,
            # leave the `range_class` as None, indicating that a `Literal` value is expected.
            range_classes = parser.dictionary.list_range_classes_for_property(
                target_property, namespace=APPN_SCHEMA
            )
            if len(range_classes) == 0:
                range_classes = parser.dictionary.list_range_classes_for_property(
                    target_property, namespace=APPN_SCHEMA
                )
            if len(range_classes) == 1:
                self.range_class = range_classes[0]
            elif len(range_classes) > 1:
                class_list = ", ".join(
                    [appn_class.curie for appn_class in range_classes]
                )
                logger.error(
                    "Could not determine range class for property name %s and class %s - possible matches: %s",
                    self.property_name,
                    parser.target_class.curie,
                    class_list,
                    extra={ISSUE_TYPE: IssueType.RANGE_CLASS_NOT_SELECTED},
                )

    def process(self, subject_iri: IRI, value: Any) -> None:
        """Process supplied value and update graph with primary triple and any required by configuration.

        :param subject_iri: IRI to use as subject.
        :param value: Supplied value to be used for domain value.
        """
        # If there is no range class, the value can simply be converted to a `IRI` or
        # Literal ready for writing to the graph.
        if self.range_class is None:
            if isinstance(value, str) and value.startswith("http"):
                value = URIRef(value)
            else:
                value = Literal(value)
        # If the range class is for an XML type, convert the value.
        elif (
            self.range_class.ns == XML_SCHEMA
            and self.range_class != XML_STRING
            and isinstance(value, str)
        ):
            value = self.get_xml_value(self.range_class, value)
        # If a range class is expected and the value is a string, either map the
        # value to a known IRI from the dictionary or to a new IRI (which should
        # be described elsewhere in the source being parsed).
        elif isinstance(value, str):
            iri_name = self.parser.dictionary.build_clean_name(self.range_class, value)
            matching_iris = self.parser.dictionary.list_instances_by_class_and_name(
                self.range_class, iri_name
            )
            if len(matching_iris) == 0:
                value = IRI(f"{self.parser.namespace}{iri_name}")
            else:
                value = matching_iris[0]
        # Otherwise, treat anything other than an IRI as an error but insert it as
        # a Literal value.
        elif not isinstance(value, IRI):
            logger.error(
                "Unexpected type (%s) for value %s - expected value to be identifier for instance of class %s as value for property %s for class %s",
                type(value),
                value,
                self.range_class.curie,
                self.target_property.curie,
                self.parser.target_class.curie,
                extra={ISSUE_TYPE: IssueType.BAD_VALUE},
            )
            value = Literal(value)

        # Add the triple and any associated expanded properties.
        self.parser.add(subject_iri, self.target_property, value)
        for expanded_property in self.expanded_properties:
            if expanded_property == SKOS_PREF_LABEL:
                self.parser.add(
                    subject_iri,
                    SKOS_PREF_LABEL,
                    Literal(f"{value!s} ({self.parser.target_class.name})"),
                )
            else:
                self.parser.add(subject_iri, expanded_property, value)

    def get_xml_value(self, value_class: IRI, value: str) -> Any:
        """Return XML type representation from string value.

        :param value_class: IRI for XML type.
        :param value: String value.
        :return: Parsed value when possible, as an `rdflib` `Literal`.
        """
        try:
            if value_class == XML_ANYURI:
                return URIRef(value)
            if value_class == XML_BOOLEAN:
                return Literal(value.lower() in ["true", "t", "yes", "y"])
            if value_class == XML_DATETIME:
                return Literal(datetime.fromisoformat(value))
            if value_class == XML_DECIMAL:
                return Literal(float(value))
            if value_class == XML_INTEGER:
                return Literal(int(value))
            if value_class != XML_STRING:
                logger.critical(
                    "XML class %s not processed - edit %s to add processing",
                    value_class.curie,
                    __file__,
                    extra={ISSUE_TYPE: IssueType.UNHANDLED_XML_TYPE},
                )
        except Exception:
            logger.exception(
                "Could not interpret value '%s' as instance of %s for property %s of class %s",
                value,
                value_class.curie,
                self.target_property.curie,
                self.parser.target_class.curie,
                extra={ISSUE_TYPE: IssueType.BAD_VALUE},
            )

        return Literal(value)

    def add_instance(self, instance_class: IRI, instance_name: str) -> IRI:
        """Create a new instance of the specified class.

        This is a convenience method that allows any `PropertyHandler` instance
        to generate a new instance of any class where required in its processing.

        This is intended to allow handlers to generate associated instances only
        when required. Examples include generation of a `skos:ConceptSchema` only
        when the first associated `skos:Concept` is generated or of an `rdf:Property`
        only when it is first used with a value.

        Constructs an IRI for the instance and generates required type and name
        properties.

        :param instance_class: The class for which the instance is to be created.
        :param instance_name: The name to be used for the instance (and from
            which its IRI is constructed.
        :return: IRI for the new instance.
        """
        instance_iri = self.parser.dictionary.build_iri(
            instance_class,
            self.parser.namespace,  # type: ignore[arg-type]
            instance_name,
        )
        for explicit_class in self.parser.dictionary.list_explicit_classes(
            instance_class, is_concept=self.parser.generate_concepts
        ):
            self.parser.add(instance_iri, RDF_TYPE, explicit_class)
        instance_name = Literal(instance_name)
        for explicit_property in self.parser.dictionary.list_explicit_properties(
            SCHEMA_NAME
        ):
            self.parser.add(instance_iri, explicit_property, instance_name)
        return instance_iri

    def get_property_name(self) -> str:
        """Return the name for the property handled by this `PropertyHandler`."""
        return self.property_name

    def __str__(self) -> str:
        """Generate readable string representation for this handler."""
        return f'{type(self).__name__}({self.parser.organisation.id}, {self.parser.target_class.curie}, "{self.property_name} -> {self.target_property.curie})'


class NamePropertyHandler(PropertyHandler):
    """Subclass of `PropertyHandler` to generate the subject IRI for an instance from its name.

    This class behaves as for any other PropertyHandler, but also derives
    the correct IRI for an instance from the name value.
    """

    def __init__(self, parser: DictParser, property_name: str) -> None:
        """Initialise handler, always returning instances of `schema:name`.

        :param value_class: IRI for XML type.
        :param value: String value.
        :return: Parsed value when possible, as an `rdflib` `Literal`.
        """
        super().__init__(parser, property_name, SCHEMA_NAME)

    def get_subject(self, properties: dict[str, Any] | pd.Series[Any]) -> IRI | None:
        """Check for existing instance with the same name, otherwise create new IRI.

        :param properties: Dictionary which should contain a name for the instance.
        :return: IRI for instance.
        """
        if self.property_name in properties:
            value = properties[self.property_name]
            if isinstance(value, IRI):
                return value
            if isinstance(value, str):
                value = value.strip()
                # Existing instances are a possibility if the dictionary has already
                # loaded the APPN central vocabulary and/or node vocabularies.
                # In such cases, return the matching IRI, which will normally
                # cause the entire dictionary to be skipped.
                existing_instances = (
                    self.parser.dictionary.list_instances_by_class_and_name(
                        self.parser.target_class, value
                    )
                )
                if len(existing_instances) > 0:
                    return existing_instances[0]
                if len(value) > 0:
                    return self.parser.dictionary.build_iri(
                        self.parser.target_class,
                        self.parser.namespace,  # type: ignore[arg-type]
                        value,
                    )
        return None


class NullPropertyHandler(PropertyHandler):
    """Subclass of `PropertyHandler` as placeholder generating no triples."""

    def __init__(self, parser: DictParser, property_name: str) -> None:
        """Initialise handler, in theory returning instances of `schema:comment`, but nothing will be generated.

        :param value_class: IRI for XML type.
        :param value: String value.
        :return: Parsed value when possible, as an `rdflib` `Literal`.
        """
        super().__init__(parser, property_name, SCHEMA_COMMENT)

    def process(self, subject_iri: IRI, value: Any) -> None:  # noqa: ARG002
        """Do nothing.

        :param subject_iri: IRI to use as subject.
        :param value: Supplied value to be used for domain value.
        """
        return


class NewPropertyHandler(PropertyHandler):
    """Subclass of `PropertyHandler` to handle new properties defined in the current namespace.

    This typically represents an error or a property specific to a node. The
    associated property should only be generated when it is first used.
    """

    def __init__(
        self, parser: DictParser, property_name: str, target_property: IRI
    ) -> None:
        """Remember we have not yet generated an `rdf:Property`.

        :param value_class: IRI for XML type.
        :param value: String value.
        :return: Parsed value when possible, as an `rdflib` `Literal`.
        """
        super().__init__(parser, property_name, target_property)
        self.property_defined = False

    def process(self, subject_iri: IRI, value: Any) -> None:  # noqa: ARG002 RUF100
        """Generate the property with first use.

        Leave the parent class to generate the instance triple.

        :param subject_iri: IRI to use as subject.
        :param value: Supplied value to be used for domain value.
        """
        if not self.property_defined:
            self.add_instance(RDF_PROPERTY, self.property_name)

        super().process(subject_iri, value)


class ConceptPropertyHandler(PropertyHandler):
    """Subclass of `PropertyHandler` to handle generate `skos:ConceptScheme` and `skos:inScheme` properties.

    Only generate the scheme when a concept has been created. Mark each
    concept as belonging to the scheme.
    """

    def __init__(self, parser: DictParser) -> None:
        """Remember we have not yet generated a `skos:ConceptScheme`.

        :param value_class: IRI for XML type.
        :param value: String value.
        :return: Parsed value when possible, as an `rdflib` `Literal`.
        """
        super().__init__(parser, "inScheme", SKOS_IN_SCHEME)
        self.scheme_iri: IRI | None = None

    def process(self, subject_iri: IRI, value: Any) -> None:  # noqa: ARG002 RUF100
        """Process supplied value and update graph with corresponding triple and any required by configuration."""
        if self.scheme_iri is None:
            self.scheme_iri = self.add_instance(
                SKOS_CONCEPT_SCHEME, self.parser.target_class.name
            )
            if self.parser.organisation.id == CENTRAL_ORGANISATION:
                description = Literal(
                    f"Concept scheme including instances of the {self.parser.target_class.name} class from the Australian Plant Phenomics Network"
                )
            else:
                description = Literal(
                    f"Concept scheme including instances of the {self.parser.target_class.name} class from the {self.parser.organisation.name} node of the Australian Plant Phenomics Network"
                )
            for property_iri in self.parser.dictionary.list_explicit_properties(
                SCHEMA_DESCRIPTION
            ):
                self.parser.add(self.scheme_iri, property_iri, description)
        self.parser.add(subject_iri, SKOS_IN_SCHEME, self.scheme_iri)


class DictParser:
    """Parser to generate RDF objects from dictlike objects (including `pandas` `Series`).

    `DictParser` instantiates instances of `PropertyHandler` and its various subclasses
    to generate linked data triples from values associated with each key in the
    dictionary. Handlers are constructed dynamically when the first dictionary is
    parsed. Additional handlers are constructed as required as new dictionaries
    are parsed.

    The parser automatically constructs the subject IRIs for each dictionary based
    on the organisation, the schema class and the value in the dictionary for the
    key "name". This key is required for a dictionary to be parsable. IRIs are
    constructed using settings from the `LinkedDataSettings` class (for class
    prefix abbreviations) and a `Dictionary` object passed to the parser. The
    `Dictionary` should hold definitions for any relevant pre-existing
    definitions. The `Dictionary` is interrogated to check for any known
    instances of the schema class that already have the specified name. This
    reflects the current primary use of the `DictParser` class, to process
    Excel spreadsheets of vocabulary term definitions for APPN nodes. In such
    cases, existing terms from the main APPN vocabulary should be used in
    place of any matching term in the node namespace.

    The parser generates one or more triples for each supplied non-null
    property.

    If a property name ends with a decimal integer, the integer part is
    ignored - it represents how tabular data is preprocessed to allow
    multiple columns to share the same name.

    If the property name matches a suitable property known from the APPN schema
    or one of the other namespaces defined in `LinkedDataSettings` as
    available for vocabulary columns, the parser will generate a triple for
    that property and one for each property (if any) configured in
    `LinkedDataSettings` as an explicit property based on the primary
    property. Suitability in this case depends on the property including
    the current schema class in its defined domain or having no defined
    domain.

    If the property matches the name of another APPN class, it is treated as
    an alias for a property that has the main schema class in its domain and the
    named class in its range, either because there is only one such property
    or because a specific property is defined in `LinkedDataSettings` for use
    in such contexts.

    Whenever the range for a property is an APPN class, the parser will
    transform a string value for the property into an IRI constructed in the
    same way that IRI for the current instance of the main class was constructed.

    `DictParser` supports embedding of definitions for secondary classes in the
    dictionary for the main class. Such embeddings are defined in
    `LinkedDataSettings`. When an embedding is defined, any properties in the
    dictionary with names that start with a lowercase version of the embedded
    class name are treated as properties for a separate instance of the
    other class and passed to a dynamically constructed secondary (embedded)
    parser that handles these properties and creates instances of the
    secondary class. To do so, it removes the lowercase class name from the
    property key and lowercases the first letter before processing further.

    If no property can be identified following the processing described above,
    the parser creates a new RDF `Property` in the same namespace as the
    rest of the parsed data.

    Triples are stored in an `rdflib` `Graph` passed to the parser constructor
    or created by the parser as it is initialied. `DictParser` relies on
    the `Graph` to drop duplicate triples as these get generated.
    """

    def __init__(
        self,
        dictionary: Dictionary,
        target_class: IRI,
        organisation: Organisation,
        graph: Graph | None = None,
        generate_concepts: bool = False,
        is_embedded: bool = False,
        namespace: str | None = None,
        restrict_to_namespace: bool = True,
    ) -> None:
        """Set up parser to create linked data triples from dictlike data.

        The `Dictionary` and `LinkedDataSettings` control features of the generated
        linked data.

        :param dictionary: `Dictionary` object providing existing linked data
            definitions that define classes, properties and existing instances
            of classes.
        :param target_class: IRI for class into which this parser converts
            dictionary properties.
        :param organisation: `Organisation` to which instances will be related.
        :param graph: `Graph` into which triples should be written - defaults to
            new `Graph` created by this object.
        :param generate_concepts: If true, all instances should also be instances
            of `skos:Concept` and belong to a shared `skos:ConceptScheme`.
        :param is_embedded: Indicates that this parser is controlled by another
            parser and generates instances based only on properties with names
            beginning with the lowercase name for the `target_class`.
        :param namespace: Optional namespace for generated instances - defaults
            to the namespace from the `Organisation`.
        :param restrict_to_namespace: If true, do not generate instances for
            which the generated IRI is in a different namespace from the parser
            namespace. (See `NamePropertyHandler`).
        """
        self.dictionary = dictionary
        self.target_class = target_class
        self.organisation = organisation
        self.graph = Graph() if graph is None else graph
        self.generate_concepts = generate_concepts
        self.is_embedded = is_embedded
        self.namespace = self.organisation.namespace if namespace is None else namespace
        self.restrict_to_namespace = restrict_to_namespace
        # Settings for configured behaviours.
        self.settings = LinkedDataSettings()
        self.embedded_parsers = self.load_embedded_parsers()
        # Check for completion rules to be run against every instance generated.
        self.completion_rules = LinkedDataSettings().get_completion_rules_for_class(
            target_class
        )
        # Embedded handlers process only properties with names beginning with
        # the class name (in lower case).
        self.required_prefix = target_class.name.lower() if is_embedded else ""
        # Dictionary to store the property handlers keyed by property name.
        self.property_handlers: dict[str, PropertyHandler] = {}
        # Placeholder for special handler to process name and IRI for instances.
        self.name_property_handler: NamePropertyHandler | None = None
        # Special post-processing handler to represent instances as `skos:Concept`s
        # if requested - this will also generate any `skos:ConceptScheme`
        self.concept_property_handler = (
            ConceptPropertyHandler(self) if self.generate_concepts else None
        )

    def parse(self, properties: dict[str, Any] | pd.Series[Any]) -> None:
        """Process values for an instance supplied as a dictionary, creating `PropertyHandler`s as needed.

        Updates the existing property handlers so all dictionary keys are mapped.
        Processes dictionary using all property handlers. Executes any embedded
        parsers.

        The property handlers write triples into the `Graph`.

        :param properties: Instance values as key-value pairs.
        """
        # On first use, generate all parsers - this includes the required
        # NamePropertyParser.
        if len(self.property_handlers) == 0:
            self.initialise_property_handlers(properties)

        # Only proceed if there is a `NamePropertyHandler` to generate the IRI.
        if self.name_property_handler is not None:
            # Generate the IRI for this instance and determine whether to proceed.
            instance_iri = self.name_property_handler.get_subject(properties)
            if instance_iri is not None and (
                not self.restrict_to_namespace or instance_iri.ns == self.namespace
            ):
                # Generate the `rdf:type` properties.
                for explicit_class in self.dictionary.list_explicit_classes(
                    self.target_class, self.generate_concepts
                ):
                    self.graph.add((instance_iri, RDF_TYPE, explicit_class))

                # Execute all handlers matched by property keys, adding new
                # ones when required.
                for property_name, property_value in properties.items():
                    if isinstance(property_value, str):
                        property_value = property_value.strip()  # noqa PLW2901
                    if property_value not in NULL_VALUES:
                        if property_name not in self.property_handlers:
                            self.add_property_handler(property_name)  # type: ignore[arg-type]
                        self.property_handlers[property_name].process(  # type: ignore[index]
                            instance_iri, property_value
                        )

                # Completion rules (from `LinkedDataSettings`) write directly
                # into the graph to enhance/complete the instance.
                for completion_rule in self.completion_rules:
                    completion_rule.complete_instance(instance_iri, graph=self.graph)

                # The `ConceptPropertyHandler` ensures concept schemes are handled
                # correctly.
                if self.concept_property_handler is not None:
                    self.concept_property_handler.process(instance_iri, None)

                # If we have embedded parsers, let them process their instances.
                for embedded_parser in self.embedded_parsers.values():
                    embedded_parser.parse(properties)

    def load_embedded_parsers(self) -> dict[str, DictParser]:
        """Load any `DictParser`s required to handle instances of another class that may be embedded in the data for the main class.

        These parsers will process the same data passed to the main parser but
        will only process columns with names starting with the required_prefix
        derived by the embedded parser.

        :return: Dictionary mapping `required_prefix` strings to `DictParser` instances.
        """
        embedded_parsers: dict[str, DictParser] = {}
        if not self.is_embedded:
            embedded_classes = self.settings.get_embedded_classes()
            if self.target_class in embedded_classes:
                for embedded_class in embedded_classes[self.target_class]:
                    embedded_parser = DictParser(
                        self.dictionary,
                        embedded_class,
                        self.organisation,
                        graph=self.graph,
                        generate_concepts=self.generate_concepts,
                        is_embedded=True,
                    )
                    embedded_parsers[embedded_parser.required_prefix] = embedded_parser
        return embedded_parsers

    def initialise_property_handlers(
        self, properties: dict[str, Any] | pd.Series[Any]
    ) -> None:
        """Construct a `PropertyHandler` for each property name in a dictionary.

        :param properties: Dictionary of properties.
        """
        for property_name in properties.keys():  # noqa: SIM118
            if isinstance(property_name, str):
                property_name = property_name.strip()  # noqa PLW2901
            if property_name not in NULL_VALUES:
                self.add_property_handler(property_name)

    def add_property_handler(self, property_name: str) -> None:
        """Construct a `PropertyHandler` for the specified property and manage the `NamePropertyHandler` instance.

        Ensures there is only one NamePropertyHandler.

        :param property_name: Candidate property name from dictionary of instance values.
        :return: `PropertyHandler` instance.
        """
        property_handler = self.construct_property_handler(property_name)
        if isinstance(property_handler, NamePropertyHandler):
            if self.name_property_handler is None:
                self.name_property_handler = property_handler  # type: ignore[assignment]
            else:
                logger.error(  # type: ignore[unreachable]
                    "Multiple name properties supplied for class %s: %s and %s - %s will be ignored",
                    self.target_class.curie,
                    self.name_property_handler.property_name,
                    property_name,
                    property_name,
                    extra={ISSUE_TYPE: IssueType.MULTIPLE_NAME_PROPERTY_COLUMNS},
                )
                property_handler = NullPropertyHandler(self, property_name)
        self.property_handlers[property_name] = property_handler

    def construct_property_handler(self, property_name: str) -> PropertyHandler:  # noqa PLR0911 PLR0912 - Breaking method would not simplify code
        """Build an appropriate handler for each property_name.

        The class of the property handler depends on the property name.

        :param property_name: Candidate property name from dictionary of instance values.
        :return: `PropertyHandler` instance.
        """
        # If the property name matches the embedding_name for an embedded parser,
        # let the embedded parser construct the `PropertyHandler`.
        for embedding_name, embedded_parser in self.embedded_parsers.items():
            if property_name.startswith(embedding_name):
                embedded_handler = embedded_parser.construct_property_handler(
                    property_name
                )
                # The embedded parser returns a `NamePropertyHandler` for the
                # `property_name` matching its expected name. Wrap this with a
                # `ReferencePropertyHandler` that will invoke the `NamePropertyHandler`
                # and then create the reference from the main instance.
                # For all other embedded handlers, store it as normal. It can be
                # invoked like any other handler and will return the expected
                # triple.
                if isinstance(embedded_handler, NamePropertyHandler):
                    range_class = embedded_parser.get_target_class()
                    target_property = self.dictionary.get_domain_range_property(
                        self.target_class, range_class
                    )
                    if target_property is None:
                        logger.error(
                            "Failed to select property to link %s with %s",
                            self.target_class.curie,
                            range_class.curie,
                        )
                        # Use schema:comment as last resort
                        target_property = SCHEMA_COMMENT
                    return PropertyHandler(
                        self, property_name, target_property, range_class=range_class
                    )
                return NullPropertyHandler(self, property_name)

        # Property names for embedded classes will start with a lowercase version of
        # the name of the class. Strip this and lowercase the following letter to
        # get the name expected as a property for the class. Strip any trailing
        # integers - these are simply to facilitate multiple instances of the same
        # property in tabular formats such as pandas that require unique column
        # names.
        if self.is_embedded:
            if property_name.startswith(self.target_class.name.lower()):
                clean_name = property_name[len(self.target_class.name) :]
                clean_name = clean_name[0].lower() + clean_name[1:]
            else:
                return NullPropertyHandler(self, property_name)
        else:
            clean_name = property_name
        clean_name = TRAILING_INTEGER_PATTERN.sub("", clean_name)

        # If the property name is now "name", this is the property_value that will
        # be used to construct an IRI - it is returned as a special subclass of
        # `PropertyHandler`.
        if clean_name == PROPERTY_NAME_NAME:
            return NamePropertyHandler(self, property_name)

        # If the property name is an APPN class name, the field is an external
        # reference to another sheet. Find the appropriate property. This is only
        # for classes that are not embedded.
        if not self.is_embedded:
            appn_classes = self.dictionary.get_class_dictionary_for_namespace(
                APPN_SCHEMA
            )
            if clean_name in appn_classes:
                range_class = appn_classes[clean_name]
                target_property = self.dictionary.get_domain_range_property(
                    self.target_class, range_class
                )
                if target_property is None:
                    logger.error(
                        "Failed to select property to link %s with %s",
                        self.target_class.curie,
                        range_class.curie,
                    )
                    # Use schema:comment as last resort
                    target_property = SCHEMA_COMMENT
                return PropertyHandler(
                    self, property_name, target_property, range_class=range_class
                )

        # Other property names should match properties associated with the class or
        # with a property in one of the vocabulary column namespaces. Select the
        # appropriate property and return the handler.
        for class_property in self.dictionary.list_domain_properties_for_class(
            self.target_class
        ):
            if class_property.name == clean_name:
                return PropertyHandler(self, property_name, class_property)

        for namespace in self.settings.get_vocabulary_column_namespaces():
            for namespace_property in self.dictionary.list_properties(
                namespace=namespace
            ):
                if namespace_property.name == clean_name:
                    return PropertyHandler(self, property_name, namespace_property)

        # If no property handler has so far been returned, this is an unexpected
        # property. Generate a property handler that will return triples using
        # a new property in the organisations namespace.
        logger.warning(
            "Unknown property %s (%s) for class %s - creating new property in %s namespace",
            clean_name[0:30],
            property_name[0:30],
            self.target_class.curie,
            self.organisation.prefix,
            extra={ISSUE_TYPE: IssueType.ADDED_LOCAL_PROPERTY},
        )
        property_iri = self.dictionary.build_iri(
            RDF_PROPERTY,
            self.namespace,  # type: ignore[arg-type]
            clean_name,
        )
        return NewPropertyHandler(self, property_name, property_iri)

    def add(self, subject_: IRI, predicate_: IRI, object_: Node) -> None:
        """Add a triple to the `Graph`."""
        self.graph.add((subject_, predicate_, object_))

    def get_target_class(self) -> IRI:
        """Return the IRI for the target class for instances."""
        return self.target_class

    def get_required_prefix(self) -> str:
        """Return the required prefix filtering properties handled by this parser."""
        return self.required_prefix

    def get_graph(self) -> Graph:
        """Return the `Graph` instance."""
        return self.graph
