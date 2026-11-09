#!/usr/bin/env python3

"""ld_constants - Constant definitions for APPN linked data tools."""

# Default settings for central organisation (i.e. APPN)
from __future__ import annotations

CENTRAL_ORGANISATION = "APPN"
DEFAULT_CENTRAL_VOCABULARY_PREFIX = "appnid"

# Standard APPN namespaces
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

APPN_VOCABULARY_ROOT = "https://id.plantphenomics.org.au/"

# Namespaces for APPN central and node vocabularies
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

# Number of parts separated by colons in a valid curie
CURIE_PART_COUNT = 2

# Number of types needed to characterise a dictionary (key and value)
DICTIONARY_TYPE_COUNT = 2
