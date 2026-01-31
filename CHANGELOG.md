# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-02-01

### Added

- New person-following AI: when activated the robot follows any person that
  enters his field of view.
- Now pressing "t" activates a terminal menu for switching mode or toggling
  person following.
- Now robot IP address must be specified through the `--robot-ip` option.
- `--version, -v` options are now available for the `elegoo-smartcar-control`
  script.

## [0.3.0] - 2026-01-30

### Added

- new feature for tracking persons with the camera.
- data and regression script used to calibrate ultrasonic
  sensor measurements.
- this `CHANGELOG.md` file.

## [0.2.0] - 2026-01-27

### Added

- `tag` goal added to the `Makefile`.
- unit and integration tests.
- CI/CD pipeline.

### Changed

- Moved the `capture` functionality to the `Car` class.

## [0.1.1] - 2026-01-19

### Changed

- Upgraded information in `pyproject.toml`.
- Some fixes to `pyproject.toml`.

## [0.1.0] - 2026-01-19
First release.
