# The following is a cut&paste of the link to the ZIP file provided by ELEGOO
ELEGOO_SOFTWARE_URL := https://download.elegoo.com/02%20Robot%20Car%20Kits/02%20Smart%20Robot%20Car%20V4/ELEGOO%20Smart%20Robot%20Car%20Kit%20V4.0%202023.02.01.zip
ELEGOO_ZIP_FILE := $(subst %20, ,$(notdir $(ELEGOO_SOFTWARE_URL)))
ELEGOO_SOFTWARE_DIR := $(subst .zip,,$(ELEGOO_ZIP_FILE))
ELEGOO_PATH_TO_MAIN_CODE := "$(ELEGOO_SOFTWARE_DIR)"/02\ Manual\ \&\ Main\ Code\ \&\ APP/02\ Main\ Program\ \ \ \(Arduino\ UNO\)/TB6612\ \&\ MPU6050/SmartRobotCarV4.0_V1_20230201
ELEGOO_PATH_TO_CAMERA_CODE := "$(ELEGOO_SOFTWARE_DIR)"/02\ Manual\ \&\ Main\ Code\ \&\ APP/04\ Code\ of\ Carmer\ \(ESP32\)/ESP32-WROVER-Camera/ESP32_CameraServer_AP_20220120

.PHONY: help
help:
	@echo
	@echo "Welcome to the configuration of the elegoo-robot-car4 project.\n"
	@echo "If you already have the '$(ELEGOO_ZIP_FILE)' file,"
	@echo "then place it into the root of the project: this avoids some targets"
	@echo "to download it."
	@echo "Here below there is a brief explanation of the main targets."
	@echo "Explore the Makefile for viewing all the possible targets.\n"
	@echo "MAIN TARGETS FOR BOARDS SOFTWARE:"
	@echo "=================================\n"
	@echo "config: get the official ELEGOO software and patches it so that the"
	@echo "        robot connects to a router.\n"
	@echo "config-ap: similar to config, but keeps the robot in access-point"
	@echo "           (AP) mode.\n"
	@echo "reset-elegoo: removes the ELEGOO software directory. It does not"
	@echo "              erase the '$(ELEGOO_ZIP_FILE)' file.\n"
	@echo "clean-elegoo: removes any downloaded, patched or generated file.\n"
	@echo "Once ELEGOO software has been patched you can upload it to your"
	@echo "boards (main board and ESP32) with the same procedure explained"
	@echo "into the official ELEGOO documentation, which you can find into"
	@echo "the unzipped ELEGOO software directory.\n"
	@echo "MAIN TARGETS FOR PYTHON SOFTWARE:"
	@echo "=================================\n"
	@echo "init:       Initializes the project with dependencies for running in"
	@echo "            production.\n"
	@echo "init-test:  Initializes the project with dependencies for running,"
	@echo "            and testing the code.\n"
	@echo "init-dev:   Initializes the project with dependencies for running,"
	@echo "            developing and testing the code. This target configures"
	@echo "            the project for development.\n"
	@echo "lint:       Runs a linter on the whole sources\n"
	@echo "format:     Runs a formatter on the whole sources\n"
	@echo "test:       Runs all the tests for Python code and produces a code"
	@echo "            coverage report.\n"
	@echo "checklist:  Equivalent to running lint, format and test.\n"
	@echo "update-hooks: Updates all git hooks to their latest version.\n"
	@echo "pre-commit-all-files: Forces a pre-commit run on all files and not"
	@echo "            only on changed files.\n"
	@echo "tag:        Tags the current commit with the version number taken"
	@echo "            from the pyproject.toml file.\n"
	@echo "publish:    Publishes the package to PyPI. Pay attention to how you"
	@echo "            initialized the working copy. You should ahve used init"
	@echo "            and not the other init variants. If you did that, clean"
	@echo "            and re-initialize with the init goal.\n"
	@echo "clean:      Entirely cleans the (Python) project.\n"


# TARGETS FOR BOARDS SOFTWARE
# ===========================

# Prepares the original ELEGOO software
.PHONY: get-elegoo-software
get-elegoo-software:
	@if [ ! -e "$(ELEGOO_ZIP_FILE)" ]; then	\
		echo "Downloading ELEGOO software...";	\
		wget $(ELEGOO_SOFTWARE_URL);	\
	fi
	@if [ ! -d "$(ELEGOO_SOFTWARE_DIR)" ]; then	\
		unzip "$(ELEGOO_ZIP_FILE)";	\
	fi

# Patches the software for the main board
.PHONY: main-patch
main-patch: get-elegoo-software
	patch -d $(ELEGOO_PATH_TO_MAIN_CODE) < elegoo-patches/tb6612_mpu6050.patch

# Reverts patching to the software for the main board
.PHONY: main-unpatch
main-unpatch: get-elegoo-software
	patch -Rd $(ELEGOO_PATH_TO_MAIN_CODE) < elegoo-patches/tb6612_mpu6050.patch

# Patches camera software in access-point (AP) mode
.PHONY: camera-patch
camera-patch: get-elegoo-software
	patch -d $(ELEGOO_PATH_TO_CAMERA_CODE) < elegoo-patches/esp32.patch

# Reverts patcing to the camera software in access-point (AP) mode
.PHONY: camera-unpatch
camera-unpatch: get-elegoo-software
	patch -Rd $(ELEGOO_PATH_TO_CAMERA_CODE) < elegoo-patches/esp32.patch

# Patches camera software so that it can connect to a router
.PHONY: camera-to-router-patch
camera-to-router-patch: get-elegoo-software
	patch -d $(ELEGOO_PATH_TO_CAMERA_CODE) < elegoo-patches/esp32-with-conn-to-router.patch

# Reverts patching to camera software for the connection to router case
.PHONY: camera-to-router-unpatch
camera-to-router-unpatch: get-elegoo-software
	patch -Rd $(ELEGOO_PATH_TO_CAMERA_CODE) < elegoo-patches/esp32-with-conn-to-router.patch

# Configures the ELEGOO software so that it is ready for communication
# with Python code through a router
.PHONY: config
config: main-patch camera-to-router-patch
	@echo -n "Network SSID: "; \
	read SSID; \
	echo -n "Password: "; \
	read PASSWORD; \
	sed -e "s/\[ROUTER_SSID\]/$${SSID}/" \
	    -e "s/\[ROUTER_PASSWORD\]/$${PASSWORD}/" \
		$(ELEGOO_PATH_TO_CAMERA_CODE)/CameraWebServer_AP.h.source > \
		$(ELEGOO_PATH_TO_CAMERA_CODE)/CameraWebServer_AP.h

# Configures the ELEGOO software so that it is ready for communication
# with Python code through the ESP32 access point
.PHONY: config-ap
config-ap: main-patch camera-patch

# Resets any configuration performed to ELEGOO software
.PHONY: reset-elegoo
reset-elegoo:
	rm -fr "$(ELEGOO_SOFTWARE_DIR)"

# Completely removes ELEGOO software
.PHONY: clean-elegoo
clean-elegoo: reset-elegoo
	rm -fr "$(ELEGOO_ZIP_FILE)"

# TARGETS FOR PYTHON SOFTWARE
# ===========================

.PHONY: check-uv
check-uv:
	@if [ -z $(shell which uv) ]; then  \
	    echo "uv could not be found. Install it first: https://docs.astral.sh/uv/getting-started/installation/";    \
	    exit 2; \
	fi

.PHONY: lint
lint: check-uv
	uv run ruff check --fix src
	uv run ruff check --fix tests

.PHONY: format
format:	check-uv
	uv run ruff format src
	uv run ruff format tests

.PHONY: test
test:
	# NOTE: At present I'm not enforcing a minimum code coverage
	uv run pytest --cov=src --cov-branch --cov-report=html --cov-report=term-missing --cov-precision=1 tests/
	#uv run pytest --cov=src --cov-branch --cov-report=html --cov-report=term-missing --cov-fail-under=95 --cov-precision=1 tests/

.PHONY: checklist
checklist: lint format test

.PHONY: init-dev
init-dev: check-uv
	@echo "Creating dev .venv"
	uv sync --group dev --group test
	uv run pre-commit install --hook-type pre-commit --hook-type pre-push

.PHONY: init_test
init-test: check-uv
	@echo "Creating test .venv"
	uv sync --no-dev --group test

.PHONY: init
init: check-uv
	@echo "Creating production .venv"
	uv sync --no-dev --no-group test

.PHONY: update-hooks
update-hooks: check-uv
	@echo "Updating git hooks"
	uv run pre-commit autoupdate

.PHONY: pre-commit-all-files
pre-commit-all-files: check-uv
	@echo "Running pre-commit hooks on all files"
	uv run pre-commit run --all-files

.PHONY: tag
tag: check-uv
	@echo "Tagging commit with the current version"
	git tag "$$(uv version --short)"

.PHONY: publish
publish: check-uv
	@echo "Build and publish to PyPI"
	uv build
	uv publish

.PHONY: clean
clean:
	@echo "Cleaning project ..."
	@rm -fr .venv *.lock htmlcov
	@echo "Cleaning finished."
