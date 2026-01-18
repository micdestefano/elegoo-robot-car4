.PHONY: help get-elegoo-software main-patch main-unpatch camera-patch	\
	camera-unpatch camera-to-router-patch camera-to-router-unpatch	\
	config config-ap reset clean

# The following is a cut&paste of the link to the ZIP file provided by ELEGOO
ELEGOO_SOFTWARE_URL := https://download.elegoo.com/02%20Robot%20Car%20Kits/02%20Smart%20Robot%20Car%20V4/ELEGOO%20Smart%20Robot%20Car%20Kit%20V4.0%202023.02.01.zip
ELEGOO_ZIP_FILE := $(subst %20, ,$(notdir $(ELEGOO_SOFTWARE_URL)))
ELEGOO_SOFTWARE_DIR := $(subst .zip,,$(ELEGOO_ZIP_FILE))
ELEGOO_PATH_TO_MAIN_CODE := "$(ELEGOO_SOFTWARE_DIR)"/02\ Manual\ \&\ Main\ Code\ \&\ APP/02\ Main\ Program\ \ \ \(Arduino\ UNO\)/TB6612\ \&\ MPU6050/SmartRobotCarV4.0_V1_20230201
ELEGOO_PATH_TO_CAMERA_CODE := "$(ELEGOO_SOFTWARE_DIR)"/02\ Manual\ \&\ Main\ Code\ \&\ APP/04\ Code\ of\ Carmer\ \(ESP32\)/ESP32-WROVER-Camera/ESP32_CameraServer_AP_20220120


help:
	@echo
	@echo "Welcome to the configuration of the elegoo-robot-car4 project.\n"
	@echo "If you already have the '$(ELEGOO_ZIP_FILE)' file,"
	@echo "then place it into the root of the project: this avoids some targets"
	@echo "to download it."
	@echo "Here below there is a brief explanation of the main targets."
	@echo "Explore the Makefile for viewing all the possible targets.\n"
	@echo "config: get the official ELEGOO software and patches it so that the"
	@echo "        robot connects to a router.\n"
	@echo "config-ap: similar to config, but keeps the robot in access-point"
	@echo "           (AP) mode.\n"
	@echo "reset: removes the ELEGOO software directory. It does not erase the"
	@echo "       '$(ELEGOO_ZIP_FILE)' file.\n"
	@echo "clean: removes any downloaded, patched or generated file.\n"
	@echo "Once ELEGOO software has been patched you can upload it to your"
	@echo "boards (main board and ESP32) with the same procedure explained"
	@echo "into the official ELEGOO documentation, which you can find into"
	@echo "the unzipped ELEGOO software directory.\n"


# Prepares the original ELEGOO software
get-elegoo-software:
	@if [ ! -e "$(ELEGOO_ZIP_FILE)" ]; then	\
		echo "Downloading ELEGOO software...";	\
		wget $(ELEGOO_SOFTWARE_URL);	\
	fi
	@if [ ! -d "$(ELEGOO_SOFTWARE_DIR)" ]; then	\
		unzip "$(ELEGOO_ZIP_FILE)";	\
	fi

# Patches the software for the main board
main-patch: get-elegoo-software
	patch -d $(ELEGOO_PATH_TO_MAIN_CODE) < elegoo-patches/tb6612_mpu6050.patch

# Reverts patching to the software for the main board
main-unpatch: get-elegoo-software
	patch -Rd $(ELEGOO_PATH_TO_MAIN_CODE) < elegoo-patches/tb6612_mpu6050.patch

# Patches camera software in access-point (AP) mode
camera-patch: get-elegoo-software
	patch -d $(ELEGOO_PATH_TO_CAMERA_CODE) < elegoo-patches/esp32.patch

# Reverts patcing to the camera software in access-point (AP) mode
camera-unpatch: get-elegoo-software
	patch -Rd $(ELEGOO_PATH_TO_CAMERA_CODE) < elegoo-patches/esp32.patch

# Patches camera software so that it can connect to a router
camera-to-router-patch: get-elegoo-software
	patch -d $(ELEGOO_PATH_TO_CAMERA_CODE) < elegoo-patches/esp32-with-conn-to-router.patch

# Reverts patching to camera software for the connection to router case
camera-to-router-unpatch: get-elegoo-software
	patch -Rd $(ELEGOO_PATH_TO_CAMERA_CODE) < elegoo-patches/esp32-with-conn-to-router.patch

# Configures the ELEGOO software so that it is ready for communication
# with Python code through a router
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
config-ap: main-patch camera-patch

# Resets any configuration performed
reset:
	rm -fr "$(ELEGOO_SOFTWARE_DIR)"

# Restores the project to its initial state
clean: reset
	rm -fr "$(ELEGOO_ZIP_FILE)"
