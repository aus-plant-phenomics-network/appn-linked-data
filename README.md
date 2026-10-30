# appn-linked-data - APPN linked data tools

<!--
  Structure follows APPN Coding Standards §3.2. Answer the questions in order.
  Delete every {{PLACEHOLDER}} and every HTML comment before your first commit.
-->

This repository provides the linked-data tools used across the Australian Plant
Phenotyping Network ([APPN](https://[plantphenomics.org.au/])), including:

* Schema definitions for APPN data
* Vocabularies containing reusable definitions for APPN facilities, equipment and concepts
* Python tools to create, manipulate and query linked-data assets

## Status

**Active** — maintained by **APPN Central Data Team**.
Contact: **data.appn@plantphenomics.org.au**
<!-- Never a personal email; people rotate, roles do not. -->

## Install

Requires **Python 3.12**.

```bash
git clone https://github.com/aus-plant-phenomics-network/appn-linked-data.git
cd appn-linked-data
make install
```

## Run

Explore the APPN schema and referenced schemas:

```bash
python appn_explorer.py
```

Explore the APPN schema, referenced schemas and the APPN and Adelaide University vocabularies:

```bash
python appn_explorer.py -a APPN -a AU
```

Refresh all turtle node vocabularies from their Excel file definitions:

```bash
python appn_vocabulary.py
```

## Configure

Settings live in `config/config.yaml` (committed, no secrets). Any key can be
overridden from the environment as `APPN_LINKED_DATA__<SECTION>__<KEY>`;
secrets come from the environment only.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `APPN_LINKED_DATA__APP__LOG_LEVEL` | No | `INFO` | {{Logging verbosity}} |
| `APPN_LINKED_DATA__APP__LOG_FORMAT` | No | `json` | {{`json` for log aggregation, `text` for local reading}} |

## Test

```bash
make test
```

## Deploy

<!--
{{Deployment command, or a link to docs/runbook.md.}}
-->

## Licence and citation

Licensed under Apache-2.0 — see [LICENSE](LICENSE).

If you use this software in published work, please cite it using the metadata in
[CITATION.cff](CITATION.cff), or the "Cite this repository" button on GitHub.

---

<!--
  Sanity check before you delete this comment: could a new starter get this
  project running from this README alone, in under thirty minutes? If not, it is
  not finished (§3.2).
-->
