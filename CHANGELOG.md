# Basedmypy Changelog

## [Unreleased]
### Added
- `ignore_any_from_errors` option to suppress `no-any-expr` messages from other errors
- Function types are inferred from Overloads, overrides and default values. (no overrides for now sorry)
- Calls to incomplete functions are an error (configurable with `incomplete_is_typed`)
- Added a new type `Untyped`, it's like `Any`, but more specific
### Enhancements
- Render types a lot better in output messages

## [1.3.0]
### Added
- `default_return` option to imply unannotated return type as `None`.
- Specific error codes for `Any` errors
- Automatic baseline mode, if there are no new errors then write.
- Ignore baseline with `mypy --baseline-file= src`
### Enhancements
- Baseline will ignore reveals (`reveal_type` and `reveal_locals`).
- `--write-baseline` will report total and new errors.
- Much better baseline matching.

## [1.2.0]
### Added
- Unions in output messages show with new syntax
- `--legacy` flag
- new baseline format

## [1.0.0]
### Added
- Strict by default(`--strict` and disable dynamic typing)
- add baseline support(`--write-baseline`, `--baseline-file`)
- Type ignore must specify error code
- Unused type ignore can be ignored
- Add error code for unsafe variance(`unsafe-variance`)
