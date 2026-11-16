#!/usr/bin/env python3

"""ld_parser - Parsers to generate RDF objects from dictlike objects (including `pandas` `Series`) and Excel spreadsheets.

Public access is via the `DictParser` class which handles dictionaries defining
instances of a single schema class on behalf of a single `Organisation` and via
the 'ExcelVocabularyParser` class which handles collections of definitions
stored in an Excel spreadsheet.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rdflib import Graph, Literal, Node, URIRef
from rdflib.namespace import NamespaceManager

from appn_linked_data.ld_constants import (
    ALT_SCHEMA_SCHEMA,
    APPN_SCHEMA,
    APPN_VOCABULARY,
    BIO_SCHEMA,
    CENTRAL_ORGANISATION,
    DC_SCHEMA,
    SCHEMA_SCHEMA,
    SKOS_SCHEMA,
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
    Triple,
)
from appn_linked_data.ld_issue import ISSUE_TYPE, IssueType
from appn_linked_data.ld_namespaces import NamespaceDefinitionManager
from appn_linked_data.ld_settings import (
    LinkedDataSettings,
    Organisation,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Values that will be ignored in spreadsheet cells
NULL_VALUES = [None, np.nan, ""]

# Values treated as True or False when parsing strings to booleans.
TRUE_STRINGS = ["true", "t", "yes", "y"]
FALSE_STRINGS = ["false", "f", "no", "n"]

# Regex for removing trailing integers.
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
        *,
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
                    target_property, namespace=XML_SCHEMA
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
            value = (
                URIRef(value)
                if (isinstance(value, str) and value.startswith("http"))
                else Literal(value)
            )
        # If the range class is for an XML type, convert the value.
        elif self.range_class.ns == XML_SCHEMA:
            value = self.get_xml_value(self.range_class, value)
        # If a range class is expected and the value is a string, either map the
        # value to a known IRI from the embedded instances or from the dictionary
        # or to a new IRI (which should be described elsewhere in the source being
        # parsed).
        elif isinstance(value, str):
            value = self.get_iri_for_class_instance(self.range_class, value)
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

        # Add the triple and any associated expanded properties. For
        # skos:prefLabel, add the class name in parentheses to the
        # (name) value.
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

    def get_xml_value(self, value_class: IRI, value: Any) -> Any:  # noqa: PLR0911
        """Return XML type representation from string value.

        :param value_class: IRI for XML type.
        :param value: Supplied value.
        :return: Parsed value when possible, as an `rdflib` `Literal`.
        """
        try:
            if value_class == XML_ANYURI:
                return URIRef(value)
            if value_class == XML_DATETIME:
                return (
                    Literal(value)
                    if isinstance(value, datetime)
                    else Literal(datetime.fromisoformat(str(value)))
                )
            if value_class == XML_DECIMAL:
                return (
                    Literal(value)
                    if isinstance(value, float)
                    else Literal(float(value))
                )
            if value_class == XML_INTEGER:
                return Literal(value) if isinstance(value, int) else Literal(int(value))
            if value_class == XML_STRING:
                return Literal(value) if isinstance(value, str) else Literal(str(value))
            if value_class == XML_BOOLEAN:
                if isinstance(value, bool):
                    return Literal(value)
                if isinstance(value, str) and (
                    value.lower() in TRUE_STRINGS or value.lower() in FALSE_STRINGS
                ):
                    return Literal(True)
                # Otherwise drop through.
            else:
                logger.critical(
                    "XML class %s not processed - edit %s to add processing",
                    value_class.curie,
                    __file__,
                    extra={ISSUE_TYPE: IssueType.UNHANDLED_XML_TYPE},
                )
        except Exception:
            logger.exception(
                "Caught exception handling %s (type %s) as %s",
                value,
                type(value),
                value_class.curie,
            )

        logger.error(
            "Could not interpret value '%s' (type %s) as instance of %s for property %s of class %s",
            value,
            type(value),
            value_class.curie,
            self.target_property.curie,
            self.parser.target_class.curie,
            extra={ISSUE_TYPE: IssueType.BAD_VALUE},
        )

        return Literal(value)

    def get_iri_for_class_instance(self, instance_class: IRI, name: str) -> IRI:
        """Find or generate IRI corresponding to class and name.

        Check the `Dictionary` for an existing instance in any namespace.
        This is expected if this is a node vocacbulary and the term is defined
        in the central APPN vocabulary.

        :param instance_class: The class to which the instance should belong.
        :param name: The name that should be used as the basis for the IRI.
        :return: Matching IRI if found, otherwise constructed IRI.
        """
        matching_iris = self.parser.dictionary.list_instances_by_class_and_name(
            instance_class, name
        )
        if len(matching_iris) == 0:
            return self.parser.dictionary.build_iri(
                instance_class,
                self.parser.namespace,  # type: ignore[arg-type]
                name,
            )
        return matching_iris[0]

    def get_property_name(self) -> str:
        """Return the name for the property handled by this `PropertyHandler`."""
        return self.property_name

    def __str__(self) -> str:
        """Generate readable string representation for this handler."""
        return f'{type(self).__name__}({self.parser.organisation.id}, {self.parser.target_class.curie}, "{self.property_name} -> {self.target_property.curie})'


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

    This typically represents either an error or a property specific to a node. The
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
        # When an instance of the property is about to be created, define the
        # rdf:Property and add a warning issue in case this was unexpected.
        if not self.property_defined:
            self.parser.add_instance(RDF_PROPERTY, self.property_name)
            logger.warning(
                "Unknown property %s for class %s - creating new property in %s namespace",
                self.property_name,
                self.parser.target_class.curie,
                self.parser.organisation.prefix,
                extra={ISSUE_TYPE: IssueType.ADDED_LOCAL_PROPERTY},
            )

        super().process(subject_iri, value)


### DictParser ###############################################################


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
    or one of the other namespaces defined by `LinkedDataSettings` to be
    available for vocabulary columns, the parser will use this as the property
    represented by the column.

    The parser generates a triple for the selected property and one for each
    property (if any) configured in `LinkedDataSettings` to be included
    explicitly whenever the main property is used.

    If the property matches the name of another APPN class, it is treated as
    an alias for a property that has the main schema class in its domain and the
    named class in its range. This can be determined automatically if there is
    only one such property in the schema. Otherwise the desired property must
    be defined in `LinkedDataSettings`.

    Whenever the range for a property is an APPN class, the parser will
    transform a string value for the property into an IRI constructed in the
    same way that IRI for the current instance of the main class was constructed.

    `DictParser` supports embedding of definitions for secondary classes in the
    dictionary for the main class. Allowed embeddings are defined in
    `LinkedDataSettings`. When an embedding is defined, any properties in the
    dictionary with names that start with a lowercase version of the embedded
    class name are treated as properties for an instance of the other class
    and passed to a dynamically constructed secondary (embedded)
    parser that handles these properties and creates instances of the
    secondary class. Embedded parsers remove the lowercase class name from the
    property key and lowercase the first letter before processing further.

    If no property can be identified following the processing described above,
    the parser creates a new RDF `Property` in the same namespace as the
    rest of the parsed data.

    Triples are stored in an `rdflib` `Graph` passed to the parser constructor
    or created by the parser as it is initialied. `DictParser` relies on
    the `Graph` to drop duplicate triples as these are generated.
    """

    def __init__(
        self,
        dictionary: Dictionary,
        target_class: IRI,
        organisation: Organisation,
        *,
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
            namespace.
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
        self.scheme_iri: IRI | None = None
        self.embedded_parsers = self.load_embedded_parsers()
        # Embedded handlers process only properties with names beginning with
        # the class name (in lower case) and expect the name field to start
        # with the same prefix.
        if is_embedded:
            self.required_prefix = target_class.name.lower()
            self.name_property = f"{self.required_prefix}Name"
        else:
            self.required_prefix = ""
            self.name_property = "name"
        # Check for completion rules to be run against every instance generated.
        self.completion_rules = LinkedDataSettings().get_completion_rules_for_class(
            target_class
        )
        # Explicit classes are the set of classes for which to generate `rdf:type``
        # properties.
        self.explicit_classes = dictionary.list_explicit_classes(
            target_class, generate_concepts
        )
        # Dictionary to store the property handlers keyed by property name.
        self.property_handlers: dict[str, PropertyHandler] = {}
        # Special post-processing handler to represent instances as `skos:Concept`s
        # if requested - this will also generate any `skos:ConceptScheme`

    def parse(self, properties: dict[str, Any] | pd.Series[Any]) -> IRI | None:
        """Process values for an instance supplied as a dictionary, creating `PropertyHandler`s as needed.

        Updates the existing property handlers so all dictionary keys are mapped.
        Processes dictionary using all property handlers. Executes any embedded
        parsers.

        The property handlers write triples into the `Graph`.

        :param properties: Instance values as key-value pairs.
        :return: IRI for the generated or selected instance, otherwise None.
        """
        # Only proceed if the dictionary contains a name value.
        instance_iri = self.initialise_parsing(properties)
        if instance_iri is not None and (
            not self.restrict_to_namespace or instance_iri.ns == self.namespace
        ):
            # If we have embedded parsers, let them process their instances and
            # get the IRIs for the embedded objects.
            for embedded_parser in self.embedded_parsers.values():
                embedded_parser.parse(properties)

            # Execute all handlers matched by property keys, adding new
            # ones as required.
            for property_name, property_value in properties.items():
                if isinstance(property_value, str):
                    property_value = property_value.strip()  # noqa PLW2901
                if property_value not in NULL_VALUES:
                    if property_name not in self.property_handlers:
                        self.add_property_handler(property_name)  # type: ignore[arg-type]
                    self.property_handlers[property_name].process(  # type: ignore[index]
                        instance_iri, property_value
                    )

            self.finalise_parsing(instance_iri)
        return instance_iri

    def initialise_parsing(
        self, properties: dict[str, Any] | pd.Series[Any]
    ) -> IRI | None:
        """Prepare parser for new dictionary record.

        Only proceed if a name is found for a new instance. If so, locate any
        existing IRI for an instance of the same class with the same name. If
        none is found, create a new IRI. The IRI is returned to the caller.

        This method also adds any necessary `rdf:type` statements to the `Graph`.

        :param properties: Properties for the class instance.
        :return: IRI for the class the instance.
        """
        if self.name_property in properties:
            name_value = properties[self.name_property]
            if isinstance(name_value, IRI):
                return name_value
            if isinstance(name_value, str):
                name_value = name_value.strip()
                # Existing instances are a possibility if the dictionary has already
                # loaded the APPN central vocabulary and/or node vocabularies.
                # In such cases, return the matching IRI, which will normally
                # cause the entire dictionary to be skipped.
                existing_instances = self.dictionary.list_instances_by_class_and_name(
                    self.target_class, name_value
                )
                if len(existing_instances) > 0:
                    return existing_instances[0]
                if len(name_value) > 0:
                    instance_iri = self.dictionary.build_iri(
                        self.target_class,
                        self.namespace,  # type: ignore[arg-type]
                        name_value,
                    )
                    # Generate the `rdf:type` properties.
                    for explicit_class in self.explicit_classes:
                        self.graph.add((instance_iri, RDF_TYPE, explicit_class))
                    return instance_iri
        return None

    def finalise_parsing(self, instance_iri: IRI) -> None:
        """Perform any post-processing on the class instance.

        If the parser is generating SKOS concepts, generate the relevant
        properties.

        If there are completion rules for the class, execute them.

        :param instance_iri: The IRI for the class instance.
        """
        if self.generate_concepts:
            if self.scheme_iri is None:
                self.scheme_iri = self.add_instance(  # type: ignore[unreachable]
                    SKOS_CONCEPT_SCHEME, self.target_class.name
                )
                if self.organisation.id == CENTRAL_ORGANISATION:
                    description = Literal(
                        f"Concept scheme including instances of the {self.target_class.name} class from the Australian Plant Phenomics Network"
                    )
                else:
                    description = Literal(
                        f"Concept scheme including instances of the {self.target_class.name} class from the {self.organisation.name} node of the Australian Plant Phenomics Network"
                    )
                for property_iri in self.dictionary.list_explicit_properties(
                    SCHEMA_DESCRIPTION
                ):
                    self.add(self.scheme_iri, property_iri, description)
            self.add(instance_iri, SKOS_IN_SCHEME, self.scheme_iri)

            # Completion rules (from `LinkedDataSettings`) write directly
            # into the graph to enhance/complete the instance.
            for completion_rule in self.completion_rules:
                completion_rule.complete_instance(instance_iri, graph=self.graph)

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

    def add_property_handler(self, property_name: str) -> None:
        """Construct a `PropertyHandler` for the specified property and manage the `NamePropertyHandler` instance.

        Ensures there is only one NamePropertyHandler.

        :param property_name: Candidate property name from dictionary of instance values.
        :return: `PropertyHandler` instance.
        """
        self.property_handlers[property_name] = self.construct_property_handler(
            property_name
        )

    def construct_property_handler(self, property_name: str) -> PropertyHandler:  # noqa PLR0912
        """Build an appropriate handler for each property_name.

        The class of the property handler depends on the property name.

        :param property_name: Candidate property name from dictionary of instance values.
        :return: `PropertyHandler` instance.
        """
        # If the property name matches the embedding_name for an embedded parser,
        # let the embedded parser construct the `PropertyHandler`.
        for embedding_name, embedded_parser in self.embedded_parsers.items():
            if property_name.startswith(embedding_name):
                embedded_parser.construct_property_handler(property_name)
                # If this column is the name column for the embedded parser, it
                # represents a property linking the current instance to the
                # instance generated by the embedded parser. Determine what
                # property should be used and construct a second handler for
                # the current parser.
                if property_name == embedded_parser.name_property:
                    return self.get_handler_for_range_class(
                        embedded_parser.get_target_class(), property_name
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

        # If the property name is an APPN class name, the field is an external
        # reference to another sheet. Find the appropriate property. This is only
        # for classes that are not embedded.
        if not self.is_embedded:
            appn_classes = self.dictionary.get_class_dictionary_for_namespace(
                APPN_SCHEMA
            )
            if clean_name in appn_classes:
                return self.get_handler_for_range_class(
                    appn_classes[clean_name], property_name
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
        property_iri = self.dictionary.build_iri(
            RDF_PROPERTY,
            self.namespace,  # type: ignore[arg-type]
            clean_name,
        )
        return NewPropertyHandler(self, property_name, property_iri)

    def get_handler_for_range_class(
        self, range_class: IRI, property_name: str
    ) -> PropertyHandler:
        """If the range for values of a property is identified only by class, generate an appropriate handler for a property with the correct domain and range.

        The `Dictionary` takes settings from `LinkedDataSettings` and the
        domains and ranges of defined properties into account. It returns a
        result only if there is a unique match.

        :param range_class: IRI for the range class for the property.
        :param property_name: Name from the properties dictionary.
        :return: IRI for matching property, using `schema:comment` as
            a default.
        """
        target_property = self.dictionary.get_domain_range_property(
            self.target_class, range_class
        )
        if target_property is None:
            logger.error(
                "Failed to select property to link %s with %s",
                self.target_class.curie,
                range_class.curie,
                extra={ISSUE_TYPE: IssueType.COLUMN_PROPERTY_NOT_SELECTED},
            )
            # Use schema:comment as last resort
            target_property = SCHEMA_COMMENT
        return PropertyHandler(
            self, property_name, target_property, range_class=range_class
        )

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
        instance_iri = self.dictionary.build_iri(
            instance_class,
            self.namespace,  # type: ignore[arg-type]
            instance_name,
        )
        for explicit_class in self.dictionary.list_explicit_classes(
            instance_class, is_concept=self.generate_concepts
        ):
            self.add(instance_iri, RDF_TYPE, explicit_class)
        instance_name = Literal(instance_name)
        for explicit_property in self.dictionary.list_explicit_properties(SCHEMA_NAME):
            self.add(instance_iri, explicit_property, instance_name)
        return instance_iri

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


### OutputFormat ##############################################################


class OutputFormat(StrEnum):
    """Simple class for vocabulary output formats."""

    TURTLE = "ttl"
    JSON = "json"


### ExcelVocabularyParser #####################################################


class ExcelVocabularyParser:
    """Parser to generate RDF vocabularies from Excel spreadsheets.

    This class expects spreadsheets with sheet names matching the names
    of APPN schema classes, column names matching APPN, SKOS or DCTERMS
    property names for the sheet class, and values that fit the
    expectes property. There must be a "name" column in each sheet. It
    is used to construct an IRI for a class instance. Values in any
    columns for APPN schema properties with ranges including APPN
    schema classes will also be mapped to IRIs.
    """

    def __init__(
        self, organisation: Organisation, appn_vocabulary_path: Path | None = None
    ) -> None:
        """Initialise parser.

        Load schema assets required to construct the vocabulary.

        :param organisation: `Organisation` representing the node or APPN central.
        :param appn_vocabulary_path: Override for locaiton of APPN schema (for) use when
            regenerating all vocabularies.
        """
        self.organisation = organisation

        # Load schemas that will be used in the processing. For any node
        # vocabulary, include the current APPN central vocabulary so its
        # class instances can be referenced wherever relevant.
        self.dictionary = Dictionary()
        self.dictionary.load(APPN_SCHEMA)
        self.dictionary.load(SKOS_SCHEMA)
        self.dictionary.load(DC_SCHEMA)
        if organisation.id != CENTRAL_ORGANISATION:
            self.dictionary.load(APPN_VOCABULARY, asset_path=appn_vocabulary_path)
        self.dictionary.import_references()

        # Create a graph to contain the new vocabulary and initialise the
        # required namespaces.
        self.graph = Graph()
        namespace_manager = NamespaceManager(self.graph)
        namespace_definitions = NamespaceDefinitionManager().get_namespace_dictionary()
        # Make sure the correct schema.org domain is used.
        namespace_manager.bind(
            namespace_definitions[ALT_SCHEMA_SCHEMA].prefix, ALT_SCHEMA_SCHEMA
        )
        namespace_manager.bind(
            namespace_definitions[SCHEMA_SCHEMA].prefix, SCHEMA_SCHEMA
        )
        # Ensure the vocabulary graph uses the preferred namespace prefixes
        self.graph.bind(organisation.prefix, organisation.namespace, override=True)  # type: ignore[union-attr]
        self.graph.bind(
            namespace_definitions[APPN_SCHEMA].prefix, APPN_SCHEMA, override=True
        )
        self.graph.bind(namespace_definitions[BIO_SCHEMA].prefix, BIO_SCHEMA)
        if organisation.id != CENTRAL_ORGANISATION:
            appn = LinkedDataSettings().get_appn()
            self.graph.bind(appn.prefix, appn.namespace)

        # Convenience dictionary for checking class names.
        self.appn_classes_by_name = {
            c.name: c for c in self.dictionary.list_classes(namespace=APPN_SCHEMA)
        }

    def parse(self, excel_path: Path) -> None:
        """Read Excel spreadsheet and parse all instances.

        Read the sheet with `pandas`, but load the column headings as the first
        row and normalise column names. This allows a column name to be repeated.
        Each use of the same column name gets a unique name based on a trailing
        decimal integer. Once the unique column names are assigned, drop the first
        row,

        Construct a `DictParser` for each sheet and parse all rows.

        :param excel_path: Path to Excel file.
        """
        try:
            for sheet in pd.ExcelFile(excel_path).sheet_names:
                # Process any sheet with a name matching an APPN schema class name OR
                # mapped to a class name using `sheet_aliases`
                sheet_class = LinkedDataSettings().get_sheet_aliases().get(sheet, sheet)  # type: ignore[arg-type]
                if sheet_class in self.appn_classes_by_name:
                    appn_class = self.appn_classes_by_name[sheet_class]

                    parser = DictParser(
                        self.dictionary,
                        appn_class,
                        self.organisation,  # type: ignore[arg-type]
                        graph=self.graph,
                        generate_concepts=True,
                    )

                    try:
                        excel_sheet_dataframe = pd.read_excel(
                            excel_path, sheet_name=sheet, header=None, dtype="str"
                        )
                    except Exception:
                        logger.exception(
                            "Excel sheet %s in %s unreadable",
                            sheet,
                            excel_path,
                            extra={ISSUE_TYPE: IssueType.EXCEL_SHEET_ERROR},
                        )
                        break

                    column_name_matches: dict[str, int] = {}
                    columns: list[str] = []
                    for heading in excel_sheet_dataframe.loc[0, :].array:
                        column_name = TRAILING_INTEGER_PATTERN.sub("", heading.strip())
                        if column_name not in column_name_matches:
                            column_name_matches[column_name] = 0
                        else:
                            column_name_matches[column_name] = (
                                column_name_matches[column_name] + 1
                            )
                            column_name = (
                                f"{column_name}{column_name_matches[column_name]}"
                            )
                        columns.append(column_name)
                    excel_sheet_dataframe.columns = columns
                    excel_sheet_dataframe = excel_sheet_dataframe.drop(0).dropna(
                        how="all"
                    )

                    for _, row in excel_sheet_dataframe.iterrows():
                        parser.parse(row)

        except Exception:
            logger.exception(
                "Error parsing Excel spreadsheet",
                extra={ISSUE_TYPE: IssueType.EXCEL_SHEET_ERROR},
            )

    def verify_referenced_objects(self) -> bool:
        """Check that all objects referenced in this namespace have been defined.

        Compare objects of triples with subjects.

        :return: True if all objects have been defined.
        """
        latest_version = Dictionary(self.graph)

        subjects = latest_version.list_unique_subjects(
            namespace=self.organisation.namespace
        )
        objects = latest_version.list_unique_objects(
            namespace=self.organisation.namespace
        )

        missing = [o for o in objects if o not in subjects]
        for iri in missing:
            logger.error(
                "The vocabulary references an undefined instance %s",
                iri.curie,
                extra={ISSUE_TYPE: IssueType.MISSING_REFERENCE},
            )

        return len(missing) == 0

    def verify_existing_terms(self, add_missing_terms: bool = True) -> bool:
        """Ensure backwards compatibility for vocabulary.

        All instances defined in the previous version of the
        vocabulary should be retained, and all instances should
        still belong to previously defined types.

        Warn the user of issues, and optionally make necessary corrections.

        :param add_missing_terms: If true, add triples to the graph as necessary.
        :return: True if the vocabulary satisfied all checks before any additions were made.
        """
        all_present = True

        published_version = Dictionary()
        published_version.load(self.organisation.namespace)  # type: ignore[arg-type]

        latest_version = Dictionary(self.graph)

        published_instances = published_version.list_unique_subjects()
        published_type_dictionary = self.get_types_for_instances(published_version)

        latest_instances = latest_version.list_unique_subjects()
        latest_type_dictionary = self.get_types_for_instances(latest_version)

        for instance in published_instances:
            if instance not in latest_instances:
                all_present = False
                logger.warning(
                    "Published version of vocabulary includes a term %s - adding to the new version",
                    instance.curie,
                    extra={ISSUE_TYPE: IssueType.MISSING_INSTANCE},
                )
                if add_missing_terms:
                    for triple in published_version.list_triples_for_subject(instance):
                        latest_version.add_triple(triple)
            else:
                missing_types: list[IRI] = sorted(
                    published_type
                    for published_type in published_type_dictionary[instance]
                    if published_type not in latest_type_dictionary[instance]
                )
                # Ignore cases where the previously reported class is a superclass for one of the
                # reported classes
                reportable_types: list[IRI] = []
                for missing_type in missing_types:
                    subclasses = latest_version.list_subclasses(missing_type)
                    if not any(
                        subclass in latest_type_dictionary[instance]
                        for subclass in subclasses
                    ):
                        reportable_types.append(missing_type)
                if len(reportable_types) > 0:
                    all_present = False
                    logger.warning(
                        "Published term %s has missing types: %s - adding these to the new version",
                        instance.curie,
                        ", ".join(
                            [
                                reportable_type.curie
                                for reportable_type in reportable_types
                            ]
                        ),
                        extra={ISSUE_TYPE: IssueType.MISSING_INSTANCE_TYPE},
                    )
                    if add_missing_terms:
                        for missing_type in missing_types:
                            latest_version.add_triple(
                                Triple(instance, RDF_TYPE, missing_type)
                            )

        return all_present

    def get_types_for_instances(self, dictionary: Dictionary) -> dict[IRI, list[IRI]]:
        """Get list of explicit types for all instances in a `Dictionary`.

        Query Dictionary for the subject and object of all `rdf:type` properties
        and organise these as a dictionary keyed by instance IRI and with lists
        of type IRIs as values.

        :param dictionary: The `Dictionary` to be queried.
        :return: Instance types organised by instance IRI.
        """
        instance_type_dictionary: dict[IRI, list[IRI]] = {}
        instance_types = dictionary.query("SELECT ?x ?y WHERE { ?x rdf:type ?y }")
        for instance_iri, instance_type in instance_types:
            if instance_iri not in instance_type_dictionary:
                instance_type_dictionary[instance_iri] = []  # type: ignore[index]
            instance_type_dictionary[instance_iri].append(instance_type)  # type: ignore[index, arg-type]
        return instance_type_dictionary

    def validate(self) -> bool:
        """Perform final validation steps for vocabulary.

        Reports whether issues were detected, even if the issues were fixed.

        :return: True no issues were detected.
        """
        # As additional verification methods are added, ensure that all tests
        # are run by anding their return values with a rolling status.
        valid = self.verify_existing_terms()
        return self.verify_referenced_objects() and valid

    def serialize(self, vocabulary_path: Path) -> bool:
        """Write the vocabulary to a file.

        :param vocabulary_path: Path for output file.
        :param format: Specifies linked data output format, with Turtle as default.
        :return: True if successful.
        """
        self.graph.serialize(destination=vocabulary_path)
        return True
