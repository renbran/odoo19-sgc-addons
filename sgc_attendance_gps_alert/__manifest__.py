{
    "name": "SGC Attendance GPS Alert",
    "version": "19.0.1.0.0",
    "summary": "Warns employee/kiosk when GPS location cannot be captured on check-in/out",
    "description": """
SGC Attendance GPS Alert
=========================
Core hr_attendance silently falls back to no location (false, false) when
the browser cannot get GPS (device location off, permission denied,
insecure context). This module patches the check-in/out widget and the
kiosk app to show a warning notification to the user in that case, so
missing GPS on attendance logs is visible immediately instead of silently
happening.
""",
    "author": "SGC TECH AI",
    "website": "https://sgc-tech.ai",
    "license": "LGPL-3",
    "category": "Human Resources",
    "depends": ["hr_attendance"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "sgc_attendance_gps_alert/static/src/js/check_in_out_patch.js",
        ],
        "hr_attendance.assets_public_attendance": [
            "sgc_attendance_gps_alert/static/src/js/public_kiosk_patch.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
