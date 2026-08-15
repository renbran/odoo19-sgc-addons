import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { isIosApp } from "@web/core/browser/feature_detection";
import { _t } from "@web/core/l10n/translation";
import kioskAttendance from "@hr_attendance/public_kiosk/public_kiosk_app";

patch(kioskAttendance.kioskAttendanceApp.prototype, {
    async makeRpcWithGeolocation(route, params) {
        if (!this.props.deviceTrackingEnabled || !navigator.geolocation || isIosApp()) {
            return rpc(route, { ...params });
        }

        return new Promise((resolve) => {
            navigator.geolocation.getCurrentPosition(
                async ({ coords: { latitude, longitude } }) => {
                    const result = await rpc(route, {
                        ...params,
                        latitude,
                        longitude,
                    });
                    resolve(result);
                },
                async () => {
                    this.notification.add(
                        _t("Could not capture GPS location (device location may be switched off or permission denied). Attendance recorded without GPS position."),
                        { type: "warning" }
                    );
                    const result = await rpc(route, {
                        ...params
                    });
                    resolve(result);
                },
                { enableHighAccuracy: true }
            );
        });
    },
});
