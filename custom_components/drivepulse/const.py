"""Constants for the DrivePulse integration."""

from __future__ import annotations

DOMAIN = "drivepulse"

CONF_LOCAL_ONLY = "local_only"
DEFAULT_LOCAL_ONLY = True

EVENT_TRIP_START = "drivepulse_trip_start"
EVENT_TRIP_END = "drivepulse_trip_end"
# A saved trip sent again by hand from the app: never a trip_end, so the
# automations on "the car arrived" do not run for a trip of last week.
EVENT_TRIP_RESENT = "drivepulse_trip_resent"

# Messages the app sends (webhook schema 1).
MSG_TRIP_START = "trip_start"
MSG_TRIP_END = "trip_end"
MSG_TRIP_RESEND = "trip_resend"
# The trip that had just started was a false start (fewer than 5 GPS points)
# and the app dropped it: it closes the trip_start already sent.
MSG_TRIP_DISCARDED = "trip_discarded"
MSG_LIVE = "live"
MSG_TEST = "test"
KNOWN_MESSAGES = {
    MSG_TRIP_START,
    MSG_TRIP_END,
    MSG_TRIP_RESEND,
    MSG_TRIP_DISCARDED,
    MSG_LIVE,
    MSG_TEST,
}

# More than this many vehicles on one webhook is not a garage, it is a forged
# or broken sender: further names are ignored instead of creating devices.
MAX_VEHICLES = 20
DEFAULT_VEHICLE_NAME = "DrivePulse"
