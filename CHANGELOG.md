# Basedmypy Changelog

## [Unreleased]
### Added
- `default_return` option to imply unannotated return type as `None`.
- Specific error code for dynamic/Any errors
- Automatic baseline mode, if there are no new errors then write.
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
