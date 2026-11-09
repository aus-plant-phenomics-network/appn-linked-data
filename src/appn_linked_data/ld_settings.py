#!/usr/bin/env python3

"""ld_settings - Access to configuration settings for APPN linked data tools."""

from __future__ import annotations

import logging
from enum import StrEnum
from importlib import resources
from typing import Self

import yaml
from pydantic import (
    BaseModel,
    model_validator,
)

from appn_linked_data import settings
from appn_linked_data.ld_constants import (
    APPN_VOCABULARY_ROOT,
    CENTRAL_ORGANISATION,
)
from appn_linked_data.ld_iri import (
    IRI,
)
from appn_linked_data.ld_namespaces import (
    NamespaceDefinitionManager,
)

logger = logging.getLogger(__name__)

# Name of file containing settings
LINKED_DATA_SETTINGS_FILE = "linked-data-settings.yaml"

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


### CompletionRule ############################################################


class CompletionRule(BaseModel):
    """Base class for ReflexiveCompletionRule and any future completion rule types."""


### ReflexiveCompletionRule ###################################################


class ReflexiveCompletionRule(CompletionRule):
    """Rule requiring existence of the specified property with the subject being the default object."""

    reflexive_property: IRI


### Organisation ##############################################################


class Organisation(BaseModel):
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
    namespace: str | None = None
    prefix: str | None = None

    @model_validator(mode="after")
    def complete_organisation(self) -> Self:
        """Postprocess `Organisation` instance to supply defaultable values."""
        if self.namespace is None:
            self.namespace = f"{APPN_VOCABULARY_ROOT}{self.id}"
        if self.prefix is None:
            self.prefix = self.id.lower()
        return self


### LinkedDataSettings ########################################################


class LinkedDataControlSettings(BaseModel):
    """Settings for controlling behaviour of appn_linked_data classes."""

    vocabulary_column_namespaces: list[str] = []
    """Namespaces used to interpret column headings in vocabulary sheets."""

    explicit_classes: dict[str, ExplicitTermsFilter | list[IRI]] = {}
    """Rules to specify classes that should always be referenced in instances of a primary class whenever the secondary class is in the superclasses."""

    explicit_properties: dict[str, ExplicitTermsFilter | list[IRI]] = {}
    """Rules to specified properties that should always be referenced in instances of the primary property whenever the secondary property is in the superproperties."""

    property_expansions: dict[IRI, list[IRI]] = {}
    """Properties that should explicitly be included whenever the primary property is used."""

    excluded_classes: list[IRI] = []
    """Classes that should never be referenced except when specified as primary class."""

    excluded_properties: list[IRI] = []
    """Properties that should never be referenced except when specified as primary peoperty."""

    sheet_aliases: dict[str, str] = {}
    """Mappings for sheet names to override how sheets in Excel spreadsheets are interpreted."""

    column_aliases: dict[str, str] = {}
    """Mappings for column names to override how columns in Excel spreadsheets are interpreted."""

    completion_rules: dict[IRI, list[ReflexiveCompletionRule]] = {}
    """Rules to enforce the properties associated with instances of a class."""

    class_abbreviations: dict[IRI, str] = {}
    """Short strings to replace class names when generating IRI strings."""

    embedded_classes: dict[IRI, list[IRI]] = {}
    """Classes whose definitions may be included inside an Excel sheet for another class."""

    domain_range_properties: dict[IRI, dict[IRI, IRI]] = {}
    """Properties that should be inferred whenever a subject class is linked to an object class without a specified property."""

    property_range_classes: dict[IRI, dict[IRI, IRI]] = {}
    """Classes that should be inferred whenever a subject class is linked to an object of unknown class by a specified property."""

    ro_crate_table_classes: list[IRI] = []
    """Classes that should always be converted to CSV in RO-Crates."""

    organisations: list[Organisation] = []
    """Metadata for APPN and its nodes."""

    @model_validator(mode="after")
    def validate_model(self) -> LinkedDataControlSettings:
        """Check validity of supplied values."""
        manager = NamespaceDefinitionManager()
        namespace_dictionary = manager.get_namespace_dictionary()
        prefix_dictionary = manager.get_namespace_prefix_dictionary()

        # Make sure vocabulary column namespaces have been defined.
        for i in range(len(self.vocabulary_column_namespaces)):
            if self.vocabulary_column_namespaces[i] in prefix_dictionary:
                # Map prefix used in place of namespace
                self.vocabulary_column_namespaces[i] = prefix_dictionary[
                    self.vocabulary_column_namespaces[i]
                ].namespace
            elif self.vocabulary_column_namespaces[i] not in namespace_dictionary:
                raise ValueError(
                    "Vocabulary column namespace %s not recognised",
                    self.vocabulary_column_namespaces[i],
                )

        # Make sure explicit class namespaces have been defined.
        for ns in self.explicit_classes:
            value = self.explicit_classes[ns]
            if ns in prefix_dictionary:
                # Map prefix used in place of namespace
                actual_namespace = prefix_dictionary[ns].namespace
                self.explicit_classes[actual_namespace] = value
                self.explicit_classes.pop(ns)
            elif ns not in namespace_dictionary:
                raise ValueError(
                    "Namespace %s for explicit classes not recognised",
                    ns,
                )

        # Make sure explicit property namespaces have been defined.
        for ns in self.explicit_properties:
            value = self.explicit_properties[ns]
            if ns in prefix_dictionary:
                # Map prefix used in place of namespace
                actual_namespace = prefix_dictionary[ns].namespace
                self.explicit_properties[actual_namespace] = value
                self.explicit_properties.pop(ns)
            elif ns not in namespace_dictionary:
                raise ValueError(
                    "Namespace %s for explicit properties not recognised",
                    ns,
                )

        return self
        # TODO @dhobern: Validate remaining members


### Configuration #############################################################


class LinkedDataSettings:
    """Class to access configuration settings for APPN code.

    This is a Singleton class - only one copy exists for each process. The
    `LinkedDataSettings` can be used to store persistent state. It is an access
    point for the current `InstanceLogger`.

    LinkedDataSettings elements are read from a YAML file for which the folder and
    name can be overridden with environment variables. The default is
    "./appn.yaml".

    Access methods always receive a copy of any lists or dictionaries
    returned so the configuration is not affected by any changes.

    Data from YAML is validated to ensure it fits the expected structure.
    """

    _instance = None

    def __new__(cls) -> LinkedDataSettings:
        """Use the same instance everywhere in this process."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Load settings from YAML configuration files."""
        if "_initialised" not in dir(self):
            # Load the namespace definitions. These are required to process the
            # rest of the settings.

            self.namespace_definitions = (
                NamespaceDefinitionManager().get_namespace_definitions()
            )
            settings_path = resources.files(settings).joinpath(
                LINKED_DATA_SETTINGS_FILE
            )
            try:
                logger.debug("Loading linked data definitions: %s", settings_path)
                yaml_content = yaml.safe_load(settings_path.read_text())
                self.settings = LinkedDataControlSettings.model_validate(yaml_content)
                logger.debug("Loaded linked data definitions: \n%s", self.settings)
            except yaml.YAMLError as exc:
                logger.exception("config.load exception")
                raise ValueError(
                    "Failed to load linked data definitions from %s", settings_path
                ) from exc

            self.organisations = {
                organisation.id: organisation
                for organisation in self.settings.organisations
            }

            # Make sure we don't re-initialise later.
            self._initialised = True

    def get_vocabulary_column_namespaces(self) -> list[str]:
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
        return self.settings.vocabulary_column_namespaces.copy()

    def get_explicit_classes(self) -> dict[str, ExplicitTermsFilter | list[IRI]]:
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
        return self.settings.explicit_classes.copy()

    def get_explicit_properties(self) -> dict[str, ExplicitTermsFilter | list[IRI]]:
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
        return self.settings.explicit_properties.copy()

    def get_excluded_classes(self) -> list[IRI]:
        """Get list of classes that should NOT be matched when using the rules specified by `get_explicit_classes`.

        This allows finer control over the exact set of classes asserted
        for an instance.

        Returns a copy of the list included in the YAML configuration.

        :return: List of class IRIs
        """
        return self.settings.excluded_classes.copy()

    def get_excluded_properties(self) -> list[IRI]:
        """Get list of properties that should NOT be matched when using the rules specified by `get_explicit_properties`.

        This allows finer control over the exact set of properties asserted
        for an instance.

        Returns a copy of the list included in the YAML configuration.

        :return: List of property IRIs
        """
        return self.settings.excluded_properties.copy()

    def get_sheet_aliases(self) -> dict[str, str]:
        """Get dictionary of class names to use when Excel sheets have other names.

        The primary purpose is to ensure that sheets named Trait are
        processed as the subclass ObservedVariable and can include
        Method or Scale embeddings

        Returns a copy of the dictionary included in the YAML configuration.

        :return: Dictionary mapping names to class names
        """
        return self.settings.sheet_aliases.copy()

    def get_column_aliases(self) -> dict[str, str]:
        """Get dictionary of column names to use when Excel sheets have other names.

        This allows spreadsheets to use names that may not match those of
        schema properties but that better match the understanding of users.

        Returns a copy of the dictionary included in the YAML configuration.

        :return: Dictionary mapping column names to preferred names
        """
        return self.settings.column_aliases.copy()

    def get_completion_rules(
        self,
    ) -> dict[IRI, list[CompletionRule]]:
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
        return self.settings.completion_rules.copy()  # type: ignore[return-value]

    def get_completion_rules_for_class(self, class_: IRI) -> list[CompletionRule]:
        """Convenience method to get completion rules for a single class.

        :param class_: IRI for class to return rules
        :return: Dictionary mapping property IRIs to dictionaries of rule
            elements
        """
        rules = self.get_completion_rules()
        if class_ in rules:
            return rules[class_]
        return []

    def get_class_abbreviations(self) -> dict[IRI, str]:
        """Get dictionary of alternate strings (normally abbreviations) to substitute for class names in term IRIs.

        This allows otherwise lengthy IRI strings (including e.g.
        "observedvariable_") to be shortened in predictable ways (e.g. "ov_").

        :return: Dictionary mapping class names to abbreviations
        """
        return self.settings.class_abbreviations.copy()

    def get_class_abbreviation(self, class_: IRI) -> str:
        """Get alternate string (normally abbreviation) to substitute for class name in term IRIs.

        If no abbreviation registered, return the lowercase class name.

        :param class_: IRI for class
        :return: Abbreviated or lowered class name
        """
        abbreviations = self.get_class_abbreviations()
        if class_ in abbreviations:
            abbreviation = abbreviations[class_]
        else:
            abbreviation = class_.name.lower()

        return abbreviation

    def get_property_expansions(self) -> dict[IRI, list[IRI]]:
        """Get dictionary mapping property IRIs to lists of IRIs that should be added to terms whenever the primary property IRI is used.

        This allows terms to include multiple properties offering the same
        value (the object term or literal) to users focused on different
        schemas.

        This method returns IRIs.

        :return: Dictionary mapping property IRIs to lists of property IRIs
        """
        return self.settings.property_expansions.copy()

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
        return self.settings.embedded_classes.copy()

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
        return self.settings.domain_range_properties.copy()

    def get_property_range_classes(self) -> dict[IRI, dict[IRI, IRI]]:
        """Get classes to expect when processing specified properties for specific classes.

        Property values will be converted to IRI references when the specified
        domain class and property are used.

        :return: Dictionary mapping domain class names to dictionaries mapping
            property names to range class IRIs
        """
        return self.settings.property_range_classes.copy()

    def get_ro_crate_table_classes(self) -> list[IRI]:
        """Get names of classes that should be serialised to CSV tables in RO-Crates.

        The named classes are likely to add significantly to the size of the
        linked-data graph.

        :return: List of class names
        """
        return self.settings.ro_crate_table_classes.copy()

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
        return self.get_organisations()[CENTRAL_ORGANISATION]
