#!/usr/bin/env python3

"""ld_issue - Issue types for logging."""

from __future__ import annotations

from enum import StrEnum

# Name for extra property to use in log records.

ISSUE_TYPE = "issue_type"
### IssueType #################################################################


class IssueType(StrEnum):
    """Class to hold a message describing an issue and an optional string suggesting a fix."""

    suggested_fix: str | None

    def __new__(cls, message: str, suggested_fix: str | None = None) -> IssueType:
        """Create the `IssueMessage` as a special string with an extra property for the suggested fix."""
        obj = str.__new__(cls, message)
        obj._value_ = message
        obj.suggested_fix = suggested_fix
        return obj

    EXCEL_PATH_INVALID = "Invalid path to Excel spreadsheet"
    EXCEL_SHEET_ERROR = "Failed to read sheet from Excel spreadsheet"
    COLUMN_PROPERTY_NOT_SELECTED = (
        "Zero or multiple properties link the domain and range classes - cannot select a property for the column",
        "Add a domain_range_properties mapping to the YAML configuration file to specify the property to use for links between the domain and range classes. The domain class should be the outer key for the mapping, with the range class and the property as the key and value in the inner dictionary.",
    )
    NO_NAME_COLUMN_FOR_CLASS = (
        "No column identified as name for instances of APPN class in sheet"
    )
    SHEET_CONTAINS_DUPLICATE_NAMES = (
        "Sheet contains multiple rows with the same name",
        "Review sheet and ensure that no two rows share the same value for the name column",
    )
    SHEET_CONTAINS_DUPLICATE_EMBEDDED_NAMES = (
        "Multiple rows define class with the same name - ignoring all but first",
        "This relates to an embedded class. Repeated definitions may be expected. Otherwise review sheet and ensure that no two rows share the same value for the name column for the embedded class.",
    )
    MISSING_REFERENCE = (
        "Did not find expected definition for object referenced in a property",
        "Either add the referenced object to the appropriate sheet or correct the name where it is referenced.",
    )
    ADDED_LOCAL_PROPERTY = (
        "A spreadsheet column name did not match any defined property, so a new property was created in the vocabulary namespace.",
        "This only needs attention if it was unexpected. Check whether the column should have been mapped to a known property. Adding namespaces to the vocabulary_column_namespaces component of the YAML configuration allows properties from other namespaces to be included.",
    )
    RANGE_CLASS_NOT_SELECTED = (
        "A spreadsheet column or property name matches a property with more than one APPN schema class or XML type in its range, so the class for the associated value could not be uniquely determined.",
        "Add an property_range_classes mapping to the YAML configuration file to specify the class to be used for the property in the context of the domain class.",
    )
    RANGE_INVALID_CONFIGURATION_DATA = (
        "Configuration contains data that does not match the expected structure - it will be ignored",
        "Check YAML configuration and ensure that value for specified key has the expected structure",
    )
    UNRECOGNISED_COMPLETION_RULE_TYPE = (
        "A completion rule was specified to ensure a definition is complete, but the rule type is not recognised.",
    )
    MISSING_INSTANCE = (
        "The currently published version of the vocabulary includes a term that is no longer represented in the Excel spreadsheet. All published terms must be preserved, even if they are now deprecated.",
        "All missing terms are automatically added to the new version of the vocabulary, so no intervention is required unless the definition needs to be edited, in which case the Excel row should be restored and edited as required.",
    )
    MISSING_INSTANCE_TYPE = (
        "In the currently published version of the vocabulary, a term has one or more types that are no longer generated from the spreadsheet or processing settings. The types of all published terms must be preserved.",
        "All missing terms types are automatically restored to the new version of the vocabulary, so no intervention is required. Contact the APPN Central Data Team if there are remaining aspects to address.",
    )
    MULTIPLE_NAME_PROPERTY_COLUMNS = (
        "An Excel spreadsheet included multiple columns interpreted as the name for instances of the class. Each instance should have a single name.",
        "Review the spreadsheet and ensure that every sheet has exactly one 'name' column.",
    )
    BAD_VALUE = (
        "An Excel spreadsheet comtains values that are expected to conform to a specific datatype, but a supplied value could not be converted.",
        "Review the spreadsheet and check values for the specified property.",
    )
    UNHANDLED_XML_TYPE = (
        "An Excel spreadsheet included multiple columns that the schema indicates should conform to a specific datatype, but this datatype is not handled.",
        "Notify the APPN Central Data Team to add processing for the missing datatype.",
    )
