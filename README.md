# hacs-aws-test

Throwaway HACS integration to verify that Home Assistant can install the AWS IoT SDK
(`awsiotsdk` + native `awscrt`) via the `requirements` field in `manifest.json`.

## What it does

1. HACS installs the integration and `pip install awsiotsdk>=1.26.0` runs automatically.
2. `awsiotsdk` pulls in `awscrt` (native C extension) as a dependency.
3. On setup, the integration imports both packages and logs whether they loaded.
4. Two sensors appear in HA showing the installed versions of `awscrt` and `awsiot`.

If both sensors show version numbers (not "IMPORT FAILED"), the dependency chain works.

## Installation

1. Add this repo as a **custom repository** in HACS (category: Integration).
2. Install **Hello AWS IoT** from HACS.
3. Restart Home Assistant.
4. Go to Settings → Devices & Services → Add Integration → **Hello AWS IoT**.
5. Check the two sensors: `sensor.awscrt_version` and `sensor.awsiot_version`.

## Why

The `awscrt` package is a native C wheel (`musllinux_1_1_aarch64`).
This test confirms that HA's pip + the wheels.home-assistant.io index can resolve
and install it on a production HA OS instance via HACS.
