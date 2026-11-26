# Versioning and deprecation policy

tabledig follows [semantic versioning](https://semver.org) from 1.0.

**Stable (changes need a major version):** the Python names exported from `tabledig` (`extract`,
`Extractor`, `read_tables`, `Record`, `Table`, `Attribute`, `load_*`, `result_schema`), the CLI commands and
flags documented in the [CLI reference](cli.md), and version 1 of the JSON result schema (`tabledig schema`).
New record fields and new CLI flags are added in minor versions and never change the meaning of old ones.

**Not covered:** the exact match `score` and `confidence` numbers (heuristics that may be retuned in a minor
release, and are documented as such), private modules and names starting with an underscore, the text of
`note` fields, and the contents of the built-in synonym packs (aliases may be added or corrected).

**Deprecation:** a stable feature is deprecated for at least one minor release before removal; the
deprecation is announced in the changelog and emits a `DeprecationWarning` (Python) or a stderr note (CLI).

**Python versions:** each tabledig release supports the Python versions listed in CI. Dropping a Python
version that is past its upstream end of life is not a breaking change.
