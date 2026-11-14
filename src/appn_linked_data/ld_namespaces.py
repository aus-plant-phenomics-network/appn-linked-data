#!/usr/bin/env python3

"""ld_namespaces - Classes to manage access to namespace information."""

from __future__ import annotations

import logging
from enum import StrEnum
from importlib import resources

import yaml
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    Field,
    FilePath,
)

from appn_linked_data import settings
from appn_linked_data.ld_constants import APPN_SCHEMA

logger = logging.getLogger(__name__)


# Name of file containing settings
NAMESPACE_SETTINGS_FILE = "namespace-settings.yaml"


### AssetLoadLocation #########################################################


class AssetLoadLocation(StrEnum):
    """Simple class for pseudo-locations for namespace assets.

    `internal` indicates that the asset should be sources from within the
    appn_linked_data package.

    `origin` indicates that the asset should be loaded from the namespace URL.
    """

    INTERNAL = "internal"
    ORIGIN = "origin"


### NamespaceDefinition #######################################################


class NamespaceDefinition(BaseModel):
    """Simple class for namespace definition.

    Only the location can be changed after creation.
    """

    namespace: str = Field(frozen=True)
    prefix: str = Field(pattern=r"^[a-z]{2,10}$", frozen=True)
    location: AssetLoadLocation | AnyHttpUrl | FilePath = AssetLoadLocation.ORIGIN


### NamespaceDefinitions ######################################################


class NamespaceDefinitionsContainer(BaseModel):
    """Simple class for list of namespace definitions."""

    namespace_definitions: list[NamespaceDefinition] = []


### NamespaceSettings #########################################################


class NamespaceDefinitionManager:
    """Access to namespace definitions."""

    _instance = None

    def __new__(cls) -> NamespaceDefinitionManager:
        """Use the same instance everywhere in this process."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Load definitions from YAML file."""
        if "_initialised" not in dir(self):
            self._namespace_definitions = []
            settings_path = resources.files(settings).joinpath(NAMESPACE_SETTINGS_FILE)
            try:
                logger.debug("Loading namespace definitions: %s", settings_path)
                yaml_content = yaml.safe_load(settings_path.read_text())
                self._namespace_definitions = (
                    NamespaceDefinitionsContainer.model_validate(
                        yaml_content
                    ).namespace_definitions
                )
                logger.debug(
                    "Loaded namespace definitions: \n%s",
                    self._namespace_definitions,
                )
            except yaml.YAMLError as exc:
                logger.exception("config.load exception")
                raise ValueError(
                    "Failed to load namespace definitions from %s", settings_path
                ) from exc

            self._namespace_dictionary: dict[str, NamespaceDefinition] = {}
            self._namespace_prefix_dictionary: dict[str, NamespaceDefinition] = {}
            self._iri_start_dictionary: dict[str, NamespaceDefinition] = {}

            self._index_namespaces()

            self._initialised = True

    def _index_namespaces(self) -> None:
        """Create assets to assist use of definitions."""
        self._namespace_dictionary.clear()
        self._namespace_prefix_dictionary.clear()
        self._iri_start_dictionary.clear()
        self._appn_namespace_definition = None

        for definition in self._namespace_definitions:
            self._namespace_dictionary[definition.namespace] = definition
            self._namespace_prefix_dictionary[definition.prefix] = definition
            self._iri_start_dictionary[definition.namespace] = definition
            self._iri_start_dictionary[f"{definition.prefix}:"] = definition
            if definition.namespace == APPN_SCHEMA:
                self._appn_namespace_definition = definition

    def add_namespace_definition(
        self, namespace_definition: NamespaceDefinition
    ) -> bool:
        """Insert additional `NamespaceDefinition` into definitions.

        The namespace definition is then available via existing lists and dictionaries.

        :param namespace_definition: New namespace definition
        :return: True if successfully added/updated
        """
        if namespace_definition.namespace in self._namespace_dictionary:
            if (
                namespace_definition.prefix
                == self._namespace_dictionary[namespace_definition.namespace].prefix
            ):
                logger.debug(
                    "Changing location for namespace definition for <%s> from %s to %s",
                    namespace_definition.namespace,
                    self._namespace_dictionary[namespace_definition.namespace],
                    str(namespace_definition.location),
                )
                self._namespace_dictionary[
                    namespace_definition.namespace
                ].location = namespace_definition.location
                return True
            logger.error(
                "Cannot add namespace definition %s - prefix for existing namespace definition cannot be changed",
                namespace_definition,
            )
        elif namespace_definition.prefix not in self._namespace_prefix_dictionary:
            logger.info("Adding namespace definition %s", namespace_definition)
            self._namespace_definitions.append(namespace_definition)
            self._index_namespaces()
            return True
        else:
            logger.error(
                "Cannot add namespace definition %s - prefix already in use",
                namespace_definition,
            )
        return False

    def get_namespace_definitions(self) -> list[NamespaceDefinition]:
        """Return namespace definitions.

        The actual list is returned so all users get immediate access to details
        for any newly loaded namespaces. Changes should never be made to the list
        in user code since these will affect all users.
        """
        return self._namespace_definitions

    def get_namespace_dictionary(self) -> dict[str, NamespaceDefinition]:
        """Return namespace definitions indexed by namespace.

        The actual dictionary is returned so all users get immediate access to details
        for any newly loaded namespaces. Changes should never be made to the list
        in user code since these will affect all users.
        """
        return self._namespace_dictionary

    def get_namespace_prefix_dictionary(self) -> dict[str, NamespaceDefinition]:
        """Return namespace definitions indexed by prefix.

        The actual dictionary is returned so all users get immediate access to details
        for any newly loaded namespaces. Changes should never be made to the list
        in user code since these will affect all users.
        """
        return self._namespace_prefix_dictionary

    def get_iri_start_dictionary(self) -> dict[str, NamespaceDefinition]:
        """Return unified dictionary of distinct start strings for the namespace or prefix part of an IRI or CURIE (including colon).

        The actual dictionary is returned so all users get immediate access to details
        for any newly loaded namespaces. Changes should never be made to the list
        in user code since these will affect all users.
        """
        return self._iri_start_dictionary

    def get_appn_namespace_definition(self) -> NamespaceDefinition:
        """Return namespace definition for APPN schema namespace."""
        return self._appn_namespace_definition  # type: ignore[return-value]
