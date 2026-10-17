# InfoG v2.0
InfoG (it's Info-jee) is an information gathering tool. You can find ip addresses, phone number details and much more.


**How to use:**

First clone the repository:\
**git clone https://github.com/Tech-Sec/InfoG.git**

Change your directory to InfoG  folder:\
**cd InfoG**

Then type:\
**pip install -r requirements.txt**

After that, type:\
**python3 InfoG.py**

![](IMG_1.JPG)


Option 1 will give you the ip address of the domain name you type.\
(Don't type the domain name with the protocol. eg: ~~https://google.com~~, instead type: www.google.com

Option 2 gives you the country name, city, gps coordinates and much more about an ip address.

Option 3 just gives you the country and service provider of aa specific mobile number.\
Enter yor phone number with the country code. eg: +1xxxxxxxxxxxx

Option 4 will give you a lure link with which you can get the ip address of the target once he/she opens it.

**New Feature in v2.0**\
IP-Grabber by ![Krishna Pranav](https://github.com/krishpranav/IP-Grabber)

Now you can grab the ip address of your target by sending him a lure link. You can get the ip address, browser details etc. 

**Note**\
IP-Grabber is only available on non-Windows platform. For more deatails check ![/IP-Grabber/README.md](/IP-Grabber/README.md)

**Versions:**\
**![v1.0](https://github.com/Tech-Sec/InfoG/archive/v1.0.zip)**


**FOR EDUCATIONAL PURPOSES ONLY**

## Public website

This repository includes a website for domain, IP address, and phone-number lookups. It does not include the lure/IP-tracking feature. To give it a public URL, deploy it as a web service:

1. Push this repository to your GitHub account.
2. Sign in to [Render](https://render.com/) and choose **New** > **Blueprint**.
3. Connect the GitHub repository and deploy the `render.yaml` configuration.
4. When the build completes, Render gives the site a public `onrender.com` URL that can be opened on other devices.

The free service may take a short time to wake after inactivity. The site resolves both IPv4 and IPv6 records, rejects private IP addresses for IP-detail lookups, returns structured provider errors, and limits each client to 15 lookups per minute and 300 per day. `/healthz` is the service health endpoint.

The rate limiter uses in-memory storage by default, which is suitable for local development and a single process but is not shared between multiple service instances and resets when the process restarts. For a scaled public deployment, create a Redis-compatible store and set the Render environment variable `RATELIMIT_STORAGE_URI` to its private connection URL.

Recent results can optionally be remembered in the current browser. This is off by default; when enabled, history is stored in that browser's local storage and can be cleared from the page. Do not enable it on a shared device for lookups containing personal information. Lookup requests are processed by this server and may be sent to DNS/geolocation data providers. Use the site only for legitimate lookups and with permission.

The `/my-location` page includes both a local-only self-check and an optional explicit-consent share link. The sender creates a one-time link that expires after 10 minutes. The recipient sees a disclosure naming the location, request IP, and browser/device fields, chooses whether to press the share button, and must then grant browser location permission. Only after both choices are made are details sent to the server for the link creator to view. Sessions are held in process memory, are deleted on cancellation or expiry, and are lost if the server restarts; this design is intended for one running server process. The recipient can decline or leave at any time. No hidden capture, automatic location request, or ISP identification is performed.

To run the website locally for development, install `requirements.txt` and run `python app.py`. Run the automated checks with `python -m pytest`. GitHub Actions runs those tests on pushes and pull requests. This local command does not make the site public; the Render deployment provides the internet-accessible URL.

## Android app

The Android app provides domain-to-IP, IP details, and phone-number lookups. The lure/IP-tracking feature is not included in the mobile app.

Build the APK from Windows using WSL2 with Ubuntu:

1. Install WSL2 and Ubuntu, then open an Ubuntu terminal.
2. Install the Android build prerequisites:

   ```sh
   sudo apt update
   sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-venv \
     autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
     cmake libffi-dev libssl-dev
   ```

3. Copy the project into the Linux filesystem and enter its directory. Replace the Windows path below with your project location:

   ```sh
   cp -r /mnt/c/Users/LENOVO/OneDrive/Documents/GitHub/InfoG ~/InfoG
   cd ~/InfoG
   ```

4. Install Buildozer and build a debug APK:

   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip buildozer
   buildozer android debug
   ```

The APK will be created in `bin/`. The first build downloads the Android SDK/NDK and can take a while. Transfer the APK to an Android device and install it; Android may ask you to allow installation from that source.
