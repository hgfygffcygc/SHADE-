[app]

title = InfoG
package.name = infog
package.domain = org.techsec
source.dir = .
source.include_exts = py,kv,png,jpg
source.exclude_dirs = .git,.venv,__pycache__,IP-Grabber
version = 1.0.0
requirements = python3,kivy,requests,phonenumbers
orientation = portrait
fullscreen = 0

android.permissions = INTERNET
android.api = 35
android.minapi = 23
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 1