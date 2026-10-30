#!/usr/bin/env python3

"""configuration - Access to configuration settings for APPN linked data tools."""

from __future__ import annotations

import logging
import os
from enum import StrEnum
from pathlib import Path

import yaml
from rdflib import URIRef

from appn_linked_data.logger import IssueLogger
from appn_linked_data.types import (
    IRI,
    CompletionRuleProperty,
    CompletionRuleType,
    NamespaceDefinition,
    Organisation,
)

logger = logging.getLogger(__name__)

# Default values for finding YAML configuration file
APPN_DEFAULT_CONFIGURATION_FOLDER = Path(__file__).parent
APPN_DEFAULT_CONFIGURATION_NAME = "appn-linked-data"

# Environment keys to access local settings for YAML configuration file
APPN_CONFIGURATION_FOLDER_ENVIRONMENT_KEY = "APPN_CONFIGURATION_FOLDER"
APPN_CONFIGURATION_NAME_ENVIRONMENT_KEY = "APPN_CONFIGURATION_NAME"

# Default settings for central organisation (i.e. APPN)
CENTRAL_ORGANISATION = "APPN"
DEFAULT_CENTRAL_VOCABULARY_PREFIX = "appnid"

# Standard APPN namespace URLs
APPN_SCHEMA = "https://schema.plantphenomics.org.au/"
# NOTE: Schema.org publishes versions using both HTTP and HTTPS - we
# use HTTP which matches the RO-Crate context.
SCHEMA_SCHEMA = "http://schema.org/"
ALT_SCHEMA_SCHEMA = "https://schema.org/"
BIO_SCHEMA = "https://bioschemas.org/terms/"
CDI_SCHEMA = "http://ddialliance.org/Specification/DDI-CDI/1.0/RDF/"
DC_SCHEMA = "http://purl.org/dc/terms/"
DWC_SCHEMA = "http://rs.tdwg.org/dwc/terms/"
CDIF_SCHEMA = "https://w3id.org/cdif/"
OWL_SCHEMA = "http://www.w3.org/2002/07/owl#"
PPEO_SCHEMA = "http://purl.org/ppeo/PPEO.owl#"
PROV_SCHEMA = "http://www.w3.org/ns/prov#"
RDF_SCHEMA = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS_SCHEMA = "http://www.w3.org/2000/01/rdf-schema#"
SKOS_SCHEMA = "http://www.w3.org/2004/02/skos/core#"
SOSA_SCHEMA = "http://www.w3.org/ns/sosa/"
SSN_SCHEMA = "http://www.w3.org/ns/ssn/"
XML_SCHEMA = "http://www.w3.org/2001/XMLSchema#"

# Namespaces for APPN central and node vocabularies
APPN_VOCABULARY_ROOT = "https://id.plantphenomics.org.au/"
APPN_VOCABULARY = f"{APPN_VOCABULARY_ROOT}APPN/"
ANU_VOCABULARY = f"{APPN_VOCABULARY_ROOT}ANU/"
AU_VOCABULARY = f"{APPN_VOCABULARY_ROOT}AU/"
CSU_VOCABULARY = f"{APPN_VOCABULARY_ROOT}CSU/"
DPIRD_VOCABULARY = f"{APPN_VOCABULARY_ROOT}DPIRD/"
LTU_VOCABULARY = f"{APPN_VOCABULARY_ROOT}LTU/"
UQ_VOCABULARY = f"{APPN_VOCABULARY_ROOT}UQ/"
USYD_VOCABULARY = f"{APPN_VOCABULARY_ROOT}USYD/"
UWA_VOCABULARY = f"{APPN_VOCABULARY_ROOT}UWA/"
WSU_VOCABULARY = f"{APPN_VOCABULARY_ROOT}WSU/"

# Dictionary of default prefixes to use in APPN linked data
DEFAULT_PREFIXES: dict[str, str] = {
    APPN_SCHEMA: "appn",
    SCHEMA_SCHEMA: "schema",
    ALT_SCHEMA_SCHEMA: "sschema",
    CDI_SCHEMA: "cdi",
    DC_SCHEMA: "dcterms",
    DWC_SCHEMA: "dwc",
    CDIF_SCHEMA: "cdif",
    OWL_SCHEMA: "owl",
    PPEO_SCHEMA: "ppeo",
    RDF_SCHEMA: "rdf",
    RDFS_SCHEMA: "rdfs",
    SKOS_SCHEMA: "skos",
    PROV_SCHEMA: "prov",
    SOSA_SCHEMA: "sosa",
    SSN_SCHEMA: "ssn",
    BIO_SCHEMA: "bio",
    XML_SCHEMA: "xsd",
    APPN_VOCABULARY: "appnid",
    ANU_VOCABULARY: "anu",
    AU_VOCABULARY: "au",
    CSU_VOCABULARY: "csu",
    DPIRD_VOCABULARY: "dpird",
    LTU_VOCABULARY: "ltu",
    UQ_VOCABULARY: "uq",
    USYD_VOCABULARY: "usyd",
    UWA_VOCABULARY: "uwa",
    WSU_VOCABULARY: "wsu",
}

# Number of parts separated by colons in a valid curie
CURIE_PART_COUNT = 2

# Number of types needed to characterise a dictionary (key and value)
DICTIONARY_TYPE_COUNT = 2

### ConfigurationKey ##########################################################


class ConfigurationKey(StrEnum):
    """Simple class to define expected YAML keys."""

    NAMESPACE_PATHS = "namespace_paths"
    NAMESPACE_PREFIXES = "namespace_prefixes"
    VOCABULARY_COLUMN_NAMESPACES = "vocabulary_column_namespaces"
    EXPLICIT_CLASSES = "explicit_classes"
    EXPLICIT_PROPERTIES = "explicit_properties"
    EXCLUDED_CLASSES = "excluded_classes"
    EXCLUDED_PROPERTIES = "excluded_properties"
    SHEET_ALIASES = "sheet_aliases"
    COLUMN_ALIASES = "column_aliases"
    COMPLETION_RULES = "completion_rules"
    CLASS_ABBREVIATIONS = "class_abbreviations"
    PROPERTY_EXPANSIONS = "property_expansions"
    EMBEDDED_CLASSES = "embedded_classes"
    DOMAIN_RANGE_PROPERTIES = "domain_range_properties"
    PROPERTY_RANGE_CLASSES = "property_range_classes"
    RO_CRATE_TABLE_CLASSES = "ro_crate_table_classes"
    ORGANISATIONS = "organisations"


### ExplicitTermsFilter #####################################################


class ExplicitTermsFilter(StrEnum):
    """Simple class to define special options for `explicit_classes` and `explicit_properties` filters.

    The `all` option indicates that all superclasses or superproperties from a specified
    namespace should be made explicit in the generated linked data. The `first` option
    indicates that only the first such match should be made explicit. This assumes that
    the list of candidate matches was generated hierarchically with the class or property
    most proximal to the primary class appearing before any of its superclasses or
    superproperties.
    """

    ALL = "all"
    FIRST = "first"


### OrganisationProperty ######################################################


class OrganisationProperty(StrEnum):
    """Simple class for property names in organisation definitions."""

    NAME = "name"
    ROR = "ror"
    NAMESPACE = "namespace"
    PREFIX = "prefix"


### ValidationType ############################################################

ValidationType = type | tuple["ValidationType", ...]
"""Recursive definition for type validation when processing configuration."""


### ConfigurationValue ########################################################

ConfigurationElement = (
    str | IRI | ExplicitTermsFilter | CompletionRuleProperty | CompletionRuleType
)
ConfigurationValue = (
    ConfigurationElement
    | list["ConfigurationValue"]
    | dict[ConfigurationElement, "ConfigurationValue"]
)

### Configuration #############################################################


class Configuration:
    """Class to access configuration settings for APPN code.

    This is a Singleton class - only one copy exists for each process. The
    `Configuration` can be used to store persistent state. It is an access
    point for the current `InstanceLogger`.

    Configuration elements are read from a YAML file for which the folder and
    name can be overridden with environment variables. The default is
    "./appn.yaml".

    Access methods always receive a copy of any lists or dictionaries
    returned so the configuration is not affected by any changes.

    Data from YAML is validated to ensure it fits the expected structure.
    """

    _instance = None

    def __new__(cls) -> Configuration:
        """Use the same instance everywhere in this process."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Read configuration from YAML file."""
        # Only ever initialise the single instance once
        if "_initialised" not in dir(self):
            # The severity of errors reported depends on whether an explicit location was
            # offered or defaults used.
            defaults_overridden = False

            # Safe default if nothing is read
            self.configuration: dict[str, ConfigurationValue] = {}

            # Dictionary to store cached validated content for configuration elements
            self.cache: dict[str, ConfigurationValue] = {}

            # Logger to store messages of importance to data administrators. Anything
            # logged to the logger is also logged via Python logging.
            self.logger = IssueLogger()

            # Use folder from environment or default
            if APPN_CONFIGURATION_FOLDER_ENVIRONMENT_KEY in os.environ:
                self.configuration_folder = Path(
                    os.environ[APPN_CONFIGURATION_FOLDER_ENVIRONMENT_KEY]
                )
                defaults_overridden = True
            else:
                self.configuration_folder = Path(APPN_DEFAULT_CONFIGURATION_FOLDER)
            logger.debug("Configuration folder: %s", self.configuration_folder)

            # Use supplied filename or filename from environment or default
            if APPN_CONFIGURATION_NAME_ENVIRONMENT_KEY in os.environ:
                configuration_name = os.environ[APPN_CONFIGURATION_NAME_ENVIRONMENT_KEY]
                defaults_overridden = True
            else:
                configuration_name = APPN_DEFAULT_CONFIGURATION_NAME
            if not configuration_name.lower().endswith(".yaml"):
                configuration_name = f"{configuration_name}.yaml"
            logger.debug("Configuration name: %s", configuration_name)

            # Validate file
            self.configuration_filepath = self.configuration_folder / configuration_name
            if not self.configuration_filepath.exists():
                message = (
                    f"Configuration file {self.configuration_filepath} does not exist"
                )
                if defaults_overridden:
                    logger.error(message)
                    raise ValueError(message)
                logger.debug(message)
            else:
                # Load configuration from file
                with Path.open(self.configuration_filepath) as stream:
                    try:
                        logger.debug(
                            "Loading configuration: %s", self.configuration_filepath
                        )
                        self.configuration = yaml.safe_load(stream)
                        logger.debug("Loaded configuration: \n%s", self.configuration)
                    except yaml.YAMLError as exc:
                        logger.exception("config.load exception")
                        raise ValueError(
                            f"Failed to load configuration from {self.configuration_filepath}"
                        ) from exc

            # Organisations element requires parsing before use - only do this when
            # requested
            self.organisations: dict[str, Organisation] | None = None

            # Parse namespace definitions
            self.namespace_definitions: dict[str, NamespaceDefinition] = (
                self.load_namespace_definitions()
            )

            # Make sure we don't re-initialise later.
            self._initialised = True

    def fetch_values(
        self, key: ConfigurationKey, validation_type: ValidationType
    ) -> ConfigurationValue:
        """Safe and efficient access to YAML dictionary.

        Checks presence and structure of YAML metadata and maps strings to
        defined types.

        Validation is via a `ValidationType` tuple. This is constructed as a
        nested definition of the types that should be used for checks and
        transformations required against the values read from YAML. The
        outermost tuple in `validation_type` should have two members. The first
        is one of `dict` or `list` to indicate the expected collection type.
        The second should be the expected type for list items or a tuple of
        two types for the keys and values of a dictionary. Each item type and
        each dictionary value type may be another `ValidationType` to support
        nested collections or a tuple of alternative types that will be tested
        in turn for the YAML value. This last feature can be used to test a
        string against multiple `StrEnum` classes and return the value from
        the first match found or to support a mix of str, `StrEnum` and `list`
        values in the same collection.

        The types that are currently supported for use in `ValidationType` are
        `dict`, `list`, `str`, `IRI` and any `StrEnum` class. IRIs are generated
        using `get_iri` and can be supplied as IRI strings, CURIEs or class/
        property names from the APPN schema.

        Examples:
        `(list, IRI)` - List of IRIs
        `(dict, (str, IRI))` - Dictionary mapping strings to IRIs
        `(dict, (IRI, (list, IRI)))` - Dictionary mapping IRIs to lists of IRIs.
        `(dict, (IRI, (dict, (IRI, (list, IRI))))` - Dictionary mapping IRIs to dictionaries mapping IRIs to lists of IRIs.
        `(dict, (CompletionRuleProperty, (CompletionRuleType, str)))` - Dictionary mapping CompletionRuleProperty values to CompletionRuleType values where possible and otherwise to string values.

        Callers always receive a copy of the validated version, so the
        configuration is not affected by any external changes.

        :param key: `ConfigurationKey` for requested content
        :validation_type`: Definition for validating and transforming YAML values.
        :return: Dictionary of strings to strings
        """
        # All results are cached for quick return on subseqent calls
        if key not in self.cache:
            # Verify that the YAML content matches the expected structure.
            # All keys in YAML are strings, so the types of any dictionary
            # keys do not need to be validated.
            value = None
            if key.value in self.configuration:
                value = self.validate_values(
                    self.configuration[key.value], validation_type
                )
            if value is None:
                if (
                    isinstance(validation_type, tuple)
                    and len(validation_type) > 0
                    and validation_type[0] is list
                ):
                    value = []
                else:
                    value = {}

            self.cache[key] = value
            logger.debug("Cached value for configuration key %s", key.value)

        if isinstance(self.cache[key], list | dict):
            return self.cache[key].copy()  # type: ignore[union-attr]
        return self.cache[key]

    def validate_values(  # noqa: PLR0911 - Clearer without refactoring
        self,
        raw: ConfigurationValue,
        validation_type: ValidationType,
        suppress_errors: bool = False,
    ) -> ConfigurationValue | None:
        """Recursively test and validate or map YAML values to desired types.

        Check types against possible YAML values for validation type, recurse
        through collections, and convert strings to `IRI` or `StrEnum` values
        where requested.

        :param raw: YAML value to validate
        :param validation_type: Types for validation (see `fetch_values`)
        :return: Validated results in requested form.
        """
        if isinstance(validation_type, tuple):
            if len(validation_type) > 0:
                if validation_type[0] is dict:
                    return self.validate_dictionary(raw, validation_type)
                if validation_type[0] is list:
                    return self.validate_list(raw, validation_type)
                return self.validate_polymorphic_data(raw, validation_type)
        elif isinstance(raw, str):
            if validation_type is IRI:
                return self.get_iri(raw)
            if issubclass(validation_type, StrEnum) and raw in validation_type:
                return validation_type(raw)
            if validation_type is str:
                return str(raw)

        # TODO @dhobern: Exception
        if not suppress_errors:
            logger.error("Could not parse %s as %s", str(raw), str(validation_type))
        return None

    def validate_dictionary(
        self, raw: ConfigurationValue, validation_type: ValidationType
    ) -> ConfigurationValue | None:
        """Test and validate or map YAML values as dictionary with specified types.

        Check types against possible YAML values for validation type, recurse
        through collections, and convert strings to `IRI` or `StrEnum` values
        where requested.

        :param raw: YAML value to validate as dictionary
        :param validation_type: Types for validation (see `fetch_values`)
        :return: Validated results in requested form.
        """
        if (
            isinstance(raw, dict)
            and isinstance(validation_type, tuple)
            and len(validation_type) > 1
            and isinstance(validation_type[1], tuple)
            and len(validation_type[1]) == DICTIONARY_TYPE_COUNT
        ):
            key_type = validation_type[1][0]
            value_type = validation_type[1][1]
            value: dict[ConfigurationElement, ConfigurationValue] = {}
            for item_key, item_value in raw.items():
                if (
                    (value_key := self.validate_values(item_key, key_type)) is not None
                    and (value_value := self.validate_values(item_value, value_type))
                    is not None
                    and isinstance(value_key, ConfigurationElement)
                ):
                    value[value_key] = value_value
                else:
                    # TODO @dhobern: Exception
                    logger.error(
                        "Could not parse %s as %s", str(raw), str(validation_type)
                    )

            return value

        # TODO @dhobern: Exception
        logger.error("Could not parse %s as %s", str(raw), str(validation_type))
        return None

    def validate_list(
        self, raw: ConfigurationValue, validation_type: ValidationType
    ) -> ConfigurationValue | None:
        """Test and validate or map YAML values as list of specified type.

        Check types against possible YAML values for validation type, recurse
        through collections, and convert strings to `IRI` or `StrEnum` values
        where requested.

        :param raw: YAML value to validate as list
        :param validation_type: Type for validation of list items(see `fetch_values`)
        :return: Validated results in requested form.
        """
        if (
            isinstance(raw, list)
            and isinstance(validation_type, tuple)
            and len(validation_type) > 1
        ):
            item_type = validation_type[1]
            value: list[ConfigurationValue] = []
            for item in raw:
                if (item_value := self.validate_values(item, item_type)) is not None:
                    value.append(item_value)
                else:
                    # TODO @dhobern: Exception
                    logger.error(
                        "Could not parse %s as %s", str(raw), str(validation_type)
                    )

            return value

        # TODO @dhobern: Exception
        logger.error("Could not parse %s as %s", str(raw), str(validation_type))
        return None

    def validate_polymorphic_data(
        self, raw: ConfigurationValue, validation_types: tuple[ValidationType, ...]
    ) -> ConfigurationValue | None:
        """Test and validate or map YAML values against a set of types in turn.

        Check raw value against each of the specified types and return first valid
        mapping.

        :param raw: YAML value to validate as dictionary
        :param validation_types: Tuple of alternative types for validation (see `fetch_values`)
        :return: Validated results in requested form.
        """
        for validation_type in validation_types:
            if (
                value := self.validate_values(
                    raw, validation_type, suppress_errors=True
                )
            ) is not None:
                return value

        # TODO @dhobern: Exception
        logger.error("Could not parse %s as %s", str(raw), str(validation_type))
        return None

    def get_logger(self) -> IssueLogger:
        """Access the `IssueLogger` for the current context.

        :return: `IssueLogger` instance
        """
        return self.logger

    def load_namespace_definitions(self) -> dict[str, NamespaceDefinition]:
        """Return `NamespaceDefinition`s from configuration.

        `NamespaceDefinitions` include the namespace, preferred namespace
        prefix and path for accessing a machine-readable version of the
        definitions in the namespace.

        The namespaces and prefixes are defined by `DEFAULT_PREFIXES`.
        Any paths are set via the `namespace_paths` key in the YAML
        configuration.

        :return: Dictionary of `NameDefinition` objects keyed by the
            namespace string
        """
        # Find any configured namespace paths (locations for schema assets).
        # Assets without paths will be only be loadable by using the namespace
        # as a URL. Load as strings rather than IRIs to avoid recursion.
        paths: dict[str, str] = self.fetch_values(  # type: ignore[assignment]
            ConfigurationKey.NAMESPACE_PATHS, (dict, (str, str))
        )
        logger.debug("Imported namespace paths: %s", str(paths))

        # Find any configured namespace prefixes.
        prefixes: dict[str, str] = self.fetch_values(  # type: ignore[assignment]
            ConfigurationKey.NAMESPACE_PREFIXES, (dict, (str, str))
        )
        logger.debug("Imported namespace prefixes: %s", str(prefixes))

        # Build the namespace definitions for all default namespaces, taking
        # into account the configured namespace paths.
        namespace_definitions: dict[str, NamespaceDefinition] = {
            ns: NamespaceDefinition(ns, pre, paths.get(ns, ns))
            for ns, pre in DEFAULT_PREFIXES.items()
        }

        for ns, prefix in prefixes.items():
            namespace_definitions[ns] = NamespaceDefinition(
                ns, prefix, paths.get(ns, ns)
            )

        return namespace_definitions

    def add_namespace_definition(
        self, namespace_definition: NamespaceDefinition
    ) -> None:
        """Insert additional `NamespaceDefinition` into dictionary of namespace definitions.

        The namespace defintion is then available for constructing `IRI`s.

        :param namespace_definition: New namespace definition
        """
        self.namespace_definitions[namespace_definition.ns] = namespace_definition

    def get_namespace_definitions(self) -> dict[str, NamespaceDefinition]:
        """Return `NamespaceDefinition`s from configuration.

        `NamespaceDefinitions` include the namespace, preferred namespace
        prefix and path for accessing a machine-readable version of the
        definitions in the namespace.

        The namespaces and prefixes are defined by `DEFAULT_PREFIXES`.
        Any paths are set via the `namespace_paths` key in the YAML
        configuration.

        :return: Dictionary of `NameDefinition` objects keyed by the
            namespace string
        """
        return self.namespace_definitions.copy()

    def get_vocabulary_column_namespaces(self) -> list[IRI]:
        """Get list of namespaces to search for mapping spreadsheet columns.

        The `column_namespaces` list controls the eligibility of namespaces
        to serve as the source of properties matching spreadsheet column
        names. The namespaces will be checked in the supplied order to
        find a property with a name exactly matching a column heading.
        Properties from the APPN schema will automatically be checked.
        Unmatched names will be converted into locally defined properties.

        The list should contain schema.org, SKOS Core and Dublin Core.

        Returns a copy of any list included in the YAML configuration.

        :return: List of namespace strings
        """
        return self.fetch_values(  # type: ignore[return-value]
            ConfigurationKey.VOCABULARY_COLUMN_NAMESPACES, (list, IRI)
        )

    def get_explicit_classes(self) -> dict[IRI, ExplicitTermsFilter | list[IRI]]:
        """Get dictionary of additional classes that should explicitly be specified when applicable.

        The APPN schema inherits from classes in several other schemas.
        Users of the data may benefit if the classes they expect are
        explicitly identified via `rdf:type` for all instances of any
        relevant APPN class.

        The `explicit_classes` list identifies namespaces that should be
        included as additional `rdf:type` statements. For each such
        namespace, a list of specific classes for inclusion may be
        supplied, or the keyword "all" (indicating any relevant class
        from the schema) or the keyword "first" (indicating the class
        from the schema that is closest in the superclass hierarchy to
        the APPN class being assigned.

        The expected behaviour is that, when an instance of an APPN
        class is created, the known superclasses of the APPN class should
        be scanned for classes that match any of these rules, and extra
        `rdf:type` statements should be added for each match.

        Returns a copy of the dictionary included in the YAML configuration.

        :return: Dictionary mapping namespaces to selection rules
        """
        return self.fetch_values(  # type: ignore[return-value]
            ConfigurationKey.EXPLICIT_CLASSES,
            (dict, (IRI, (ExplicitTermsFilter, (list, IRI)))),
        )

    def get_explicit_properties(self) -> dict[IRI, ExplicitTermsFilter | list[IRI]]:
        """Get dictionary of additional propertues that should explicitly be specified when applicable.

        The APPN schema inherits from properties in several other schemas.
        Users of the data may benefit if the properties they expect are
        explicitly identified alongside all instances of any relevant APPN
        property.

        The `explicit_properties` list identifies namespaces that should be
        included as additional `rdf:type` statements. For each such
        namespace, a list of specific properties for inclusion may be
        supplied, or the keyword "all" (indicating any relevant property
        from the schema) or the keyword "first" (indicating the property
        from the schema that is closest in the superproperty hierarchy to
        the APPN property being assigned.

        The expected behaviour is that, when an instance of an APPN
        property is created, the known superproperties of the APPN property
        should be scanned for classes that match any of these rules, and
        extra properties should be added for each match.

        Returns a copy of the dictionary included in the YAML configuration.

        :return: Dictionary mapping namespaces to selection rules
        """
        return self.fetch_values(  # type: ignore[return-value]
            ConfigurationKey.EXPLICIT_PROPERTIES,
            (dict, (IRI, (ExplicitTermsFilter, (list, IRI)))),
        )

    def get_excluded_classes(self) -> list[IRI]:
        """Get list of classes that should NOT be matched when using the rules specified by `get_explicit_classes`.

        This allows finer control over the exact set of classes asserted
        for an instance.

        Returns a copy of the list included in the YAML configuration.

        :return: List of class IRIs
        """
        return self.fetch_values(ConfigurationKey.EXCLUDED_CLASSES, (list, IRI))  # type: ignore[return-value]

    def get_excluded_properties(self) -> list[IRI]:
        """Get list of properties that should NOT be matched when using the rules specified by `get_explicit_properties`.

        This allows finer control over the exact set of properties asserted
        for an instance.

        Returns a copy of the list included in the YAML configuration.

        :return: List of property IRIs
        """
        return self.fetch_values(ConfigurationKey.EXCLUDED_PROPERTIES, (list, IRI))  # type: ignore[return-value]

    def get_sheet_aliases(self) -> dict[str, IRI]:
        """Get dictionary of class names to use when Excel sheets have other names.

        The primary purpose is to ensure that sheets named Trait are
        processed as the subclass ObservedVariable and can include
        Method or Scale embeddings

        Returns a copy of the dictionary included in the YAML configuration.

        :return: Dictionary mapping names to class names
        """
        return self.fetch_values(ConfigurationKey.SHEET_ALIASES, (dict, (str, IRI)))  # type: ignore[return-value]

    def get_column_aliases(self) -> dict[str, IRI]:
        """Get dictionary of column names to use when Excel sheets have other names.

        This allows spreadsheets to use names that may not match those of
        schema properties but that better match the understanding of users.

        Returns a copy of the dictionary included in the YAML configuration.

        :return: Dictionary mapping column names to preferred names
        """
        return self.fetch_values(ConfigurationKey.COLUMN_ALIASES, (dict, (str, IRI)))  # type: ignore[return-value]

    def get_completion_rules(
        self,
    ) -> dict[IRI, dict[IRI, dict[CompletionRuleProperty, CompletionRuleType]]]:
        """Get dictionary of rules that should be applied to complete terms.

        Resolve the state of a specific property for a specific class.The
        dictionary maps class names to dictionaries mapping property IRIs to a
        set of key-value rule elements.

        This is intended to be an extensible framework for post-processing
        terms. Each rule must include a `type` property matching a name
        from the `CompletionRuleType` enumeration from `appn_types`.

        Rules are expected to be applied only if there is no pre-existing
        instance of the property for the term. This could be altered by
        including a property to the rule dictionary that specifies
        multiple instances of the property are allowed.

        The types include `reflexive`, for which the response is to add an
        instance of the specified property to each class instance with the
        same class instance as the object of the property. This can be
        used to ensure that each APPN `ObservedVariable` has a `hasTrait`
        property.

        Returns a copy of the dictionary included in the YAML configuration.

        :return: Dictionary mapping class IRIs to dictionaries mapping
            property IRIs to dictionaries of rule elements
        """
        return self.fetch_values(  # type: ignore[return-value]
            ConfigurationKey.COMPLETION_RULES,
            (
                dict,
                (
                    IRI,
                    (
                        dict,
                        (
                            IRI,
                            (dict, (CompletionRuleProperty, (CompletionRuleType, str))),
                        ),
                    ),
                ),
            ),
        )

    def get_completion_rules_for_class(
        self, class_: IRI
    ) -> dict[IRI, dict[CompletionRuleProperty, CompletionRuleType]]:
        """Convenience method to get completion rules for a single class.

        :param class_: IRI for class to return rules
        :return: Dictionary mapping property IRIs to dictionaries of rule
            elements
        """
        rules = self.get_completion_rules()
        if class_ in rules:
            return rules[class_]
        return {}

    def get_class_abbreviations(self) -> dict[IRI, str]:
        """Get dictionary of alternate strings (normally abbreviations) to substitute for class names in term IRIs.

        This allows otherwise lengthy IRI strings (including e.g.
        "observedvariable_") to be shortened in predictable ways (e.g. "ov_").

        :return: Dictionary mapping class names to abbreviations
        """
        return self.fetch_values(
            ConfigurationKey.CLASS_ABBREVIATIONS,
            (dict, (IRI, str)),  # type: ignore[return-value]
        )

    def get_class_abbreviation(self, class_: IRI) -> str:
        """Get alternate string (normally abbreviation) to substitute for class name in term IRIs.

        If no abbreviation registered, return the lowercase class name.

        :param class_: IRI for class
        :return: Abbreviated or lowered class name
        """
        key = f"abbreviation|{class_}"
        if key in self.cache:
            return self.cache[key]  # type: ignore[return-value]

        abbreviations = self.get_class_abbreviations()
        if class_ in abbreviations:
            abbreviation = abbreviations[class_]
        else:
            abbreviation = class_.name.lower()

        self.cache[key] = abbreviation
        return abbreviation

    def get_property_expansions(self) -> dict[IRI, list[IRI]]:
        """Get dictionary mapping property IRIs to lists of IRIs that should be added to terms whenever the primary property IRI is used.

        This allows terms to include multiple properties offering the same
        value (the object term or literal) to users focused on different
        schemas.

        This method returns IRIs.

        :return: Dictionary mapping property IRIs to lists of property IRIs
        """
        return self.fetch_values(
            ConfigurationKey.PROPERTY_EXPANSIONS,
            (dict, (IRI, (list, IRI))),  # type: ignore[return-value]
        )

    def get_embedded_classes(self) -> dict[IRI, list[IRI]]:
        """Get dictionary mapping class names to lists of names for classes that may be included as embeddings inside sheets for the primary class.

        If a sheet for the primary class includes one or more columns with
        names starting with a lower-first representation of an embedded class
        (e.g. "methodName", "methodDescription"), these will be processed as
        if they appeared in a sheet named after the embedded class ("Method")
        and had names without the initial class reference ("name",
        "description"). Embedded classes should ALWAYS include a column that
        will map to "name" once the class reference is removed from the
        name.

        Instances of embedded classes may repeat inside the sheet for the
        primary class (allowing the same instance to be referenced by more
        than one instance of the primary class). The embedded class instance
        will be constructed using terms in the first row that references it.
        Subsequent definitions of the same embedded class instance will be
        ignored.

        :return: Dictionary mapping class names to lists of embeddable classes
        """
        return self.fetch_values(
            ConfigurationKey.EMBEDDED_CLASSES,
            (dict, (IRI, (list, IRI))),  # type: ignore[return-value]
        )

    def get_domain_range_properties(self) -> dict[IRI, dict[IRI, IRI]]:
        """Get dictionary mapping domain class names to dictionaries mapping range class names to property IRIs.

        This supports the use of embedded classes. The ExcelVocabularyParser
        needs to create properties linking each primary class instance to
        the embedded class instance, but the relevant column refers to its
        relationship to the embedded class as its name (e.g. "methodName").
        The way that the embedded (range) class instance is linked to the
        primary (domain) class instance is not defined.

        In most cases, only one property exists in the APPN schema that has
        the primary class in its domain and the embedded class in its range.
        In such cases, the behaviour is to assume this is the intended
        property.

        This method allows the property selection to be made explicit. This
        will be required if the APPN schema includes multiple candidate
        properties.

        :return: Dictionary mapping domain class names to dictionaries mapping
            range class names to property IRIs
        """
        return self.fetch_values(
            ConfigurationKey.DOMAIN_RANGE_PROPERTIES,
            (dict, (IRI, (dict, (IRI, IRI)))),  # type: ignore[return-value]
        )

    def get_property_range_classes(self) -> dict[IRI, dict[IRI, IRI]]:
        """Get classes to expect when processing specified properties for specific classes.

        Property values will be converted to IRI references when the specified
        domain class and property are used.

        :return: Dictionary mapping domain class names to dictionaries mapping
            property names to range class IRIs
        """
        return self.fetch_values(
            ConfigurationKey.PROPERTY_RANGE_CLASSES,
            (dict, (IRI, (dict, (IRI, IRI)))),  # type: ignore[return-value]
        )

    def get_ro_crate_table_classes(self) -> list[IRI]:
        """Get names of classes that should be serialised to CSV tables in RO-Crates.

        The named classes are likely to add significantly to the size of the
        linked-data graph.

        :return: List of class names
        """
        return self.fetch_values(ConfigurationKey.RO_CRATE_TABLE_CLASSES, (list, IRI))  # type: ignore[return-value]

    def get_organisations(self) -> dict[str, Organisation]:
        """Get metadata elements for `Organisation`s defined in schema and for the APPN central organisation.

        Each `Organisation` holds a short id, a name, a ROR identifier,
        the namespace for the organisation's vocabulary terms, and the prefix
        to be used for the namespace in CURIE representations.

        Organisation ids are used to identify APPN nodes and APPN as a whole
        ("APPN") in data produced by APPN. The other components are attached
        to these ids so that software can correctly generate vocabularies and
        data.

        The organisation definitions are sourced from the YAML configuration
        file.

        If the name is not specified, the id is used in its place.

        If the namespace is not specified, it is constructed from a root URL
        combined with the id.

        If the namespace prefix is not specified, a default is selected from
        `DEFAULT_PREFIXES` if one is defined. Otherwise, the lowercase id is
        used.

        Regardless of the YAML content, an entry is always included for the
        APPN central organisation.

        Since the organisations dictionary is processed and not found directly
        in the YAML configuration, it is stored in an instance property of the
        `Configuration`.

        :return: Dictionary mapping organisation ids to `Organisation`s.
        """
        if self.organisations is None:
            self.organisations = {}
            organisations: dict[str, dict[str, str]] = self.fetch_values(  # type: ignore[assignment]
                ConfigurationKey.ORGANISATIONS, (dict, (str, (dict, (str, str))))
            )
            for organisation_id, properties in organisations.items():
                name = str(
                    properties.get(OrganisationProperty.NAME.value, organisation_id)
                )
                ror = str(properties.get(OrganisationProperty.ROR.value, None))
                namespace = str(
                    properties.get(
                        OrganisationProperty.NAMESPACE.value,
                        f"{APPN_VOCABULARY_ROOT}{organisation_id}/",
                    )
                )
                prefix = str(
                    properties[OrganisationProperty.PREFIX.value]
                    if OrganisationProperty.PREFIX.value in properties
                    else (
                        DEFAULT_CENTRAL_VOCABULARY_PREFIX
                        if organisation_id == CENTRAL_ORGANISATION
                        else (
                            DEFAULT_PREFIXES[organisation_id]
                            if organisation_id in DEFAULT_PREFIXES
                            else organisation_id.lower()
                        )
                    )
                )
                self.organisations[organisation_id] = Organisation(
                    organisation_id, name, ror, namespace, prefix
                )
            if CENTRAL_ORGANISATION not in self.organisations:
                self.organisations[CENTRAL_ORGANISATION] = Organisation(
                    CENTRAL_ORGANISATION,
                    "Australian Plant Phenomics Network",
                    "https://ror.org/02zj7b759",
                    APPN_VOCABULARY,
                    DEFAULT_PREFIXES[APPN_VOCABULARY],
                )
        return self.organisations.copy()

    def get_organisation_by_id(self, organisation_id: str) -> Organisation | None:
        """Convenience method to retrieve a single `Organisation` by its id.

        :return: `Organisation` for given id, if defined
        """
        organisations = self.get_organisations()
        if organisation_id in organisations:
            return organisations[organisation_id]
        return None

    def get_appn(self) -> Organisation:
        """Convenience method to retrieve the APPN central `Organisation`.

        :return: `Organisation` with id "APPN"
        """
        organisations = self.get_organisations()
        return organisations[CENTRAL_ORGANISATION]

    def get_iri(
        self,
        iri_value: str | URIRef | IRI,
        default_namespace_definition: NamespaceDefinition | None = None,
    ) -> IRI:
        """Get `IRI` for specified CURIE or IRI string, `URIRef`` or `IRI`.

        If the supplied value is an `IRI`, it is returned directly

        CURIEs are mapped to IRI strings using the current namespace_definitions

        IRI strings are then coverted to `IRI` instances

        :param iri_string: String IRI or CURIE
        :param default_namespace_definition: `NamespaceDefinition` to be used when
            none can be inferred.
        :return: `IRI` instance
        """
        if isinstance(iri_value, IRI):
            return iri_value

        iri = str(iri_value)

        namespace_definition = default_namespace_definition

        # Find namespace definition from namespace or prefix
        if iri.startswith("http"):
            for namespace, definition in self.namespace_definitions.items():
                if iri.startswith(namespace):
                    namespace_definition = definition
                    break
        else:
            parts = iri.split(":")
            prefix = parts[0] if len(parts) == CURIE_PART_COUNT else iri
            for definition in self.namespace_definitions.values():
                if prefix == definition.prefix:
                    namespace_definition = definition
                    break

        # If no namespace inferred from iri_string, use supplied default or
        # APPN namespace.
        if namespace_definition is None:
            namespace_definition = self.namespace_definitions[APPN_SCHEMA]

        return IRI(iri, namespace_definition)
