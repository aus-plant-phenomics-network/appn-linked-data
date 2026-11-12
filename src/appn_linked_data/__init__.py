"""APPN Linked Data Python package."""

from __future__ import annotations

from appn_linked_data.ld_constants import (
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
from appn_linked_data.ld_dictionary import (
    Dictionary,
)
from appn_linked_data.ld_iri import (
    IRI,
    Triple,
    TriplePosition,
)
from appn_linked_data.ld_namespaces import (
    AssetLoadLocation,
    NamespaceDefinition,
    NamespaceDefinitionManager,
)
from appn_linked_data.ld_settings import (
    CompletionRule,
    ExplicitTermsFilter,
    LinkedDataSettings,
    Organisation,
    ReflexiveCompletionRule,
)

__all__ = [
    "ANU_VOCABULARY",
    "APPN_SCHEMA",
    "APPN_VOCABULARY",
    "AU_VOCABULARY",
    "BIO_SCHEMA",
    "CDIF_SCHEMA",
    "CDI_SCHEMA",
    "CSU_VOCABULARY",
    "DC_SCHEMA",
    "DPIRD_VOCABULARY",
    "DWC_SCHEMA",
    "IRI",
    "LTU_VOCABULARY",
    "OWL_SCHEMA",
    "PPEO_SCHEMA",
    "PROV_SCHEMA",
    "RDFS_SCHEMA",
    "RDF_SCHEMA",
    "SCHEMA_SCHEMA",
    "SKOS_SCHEMA",
    "SOSA_SCHEMA",
    "SSN_SCHEMA",
    "UQ_VOCABULARY",
    "USYD_VOCABULARY",
    "UWA_VOCABULARY",
    "WSU_VOCABULARY",
    "XML_SCHEMA",
    "AssetLoadLocation",
    "CompletionRule",
    "Dictionary",
    "ExplicitTermsFilter",
    "Issue",
    "LinkedDataSettings",
    "NamespaceDefinition",
    "NamespaceDefinitionManager",
    "Organisation",
    "Triple",
    "TriplePosition",
]

__version__ = "0.1.0"
