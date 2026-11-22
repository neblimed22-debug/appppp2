[app]
title = ESP32 TempHum
package.name = esp32temphum
package.domain = org.tp
source.dir = .
source.include_exts = py
version = 1.0
orientation = portrait
fullscreen = 0

requirements = python3,kivy==2.3.0

android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 0
