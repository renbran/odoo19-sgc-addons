import { patch } from "@web/core/utils/patch";
import { CheckInOut } from "@hr_attendance/components/check_in_out/check_in_out";
import { _t } from "@web/core/l10n/translation";

patch(CheckInOut.prototype, {
    async signInOut() {
        if (!navigator.geolocation) {
            this.notification.add(
                _t("Location is unavailable on this device/browser. Your attendance will be recorded without GPS position."),
                { type: "warning" }
            );
        }
        navigator.geolocation.getCurrentPosition(
            ({coords: {latitude, longitude}}) => {
                this.orm.call("hr.employee", "update_last_position", [
                    [this.props.employeeId],
                    latitude,
                    longitude
                ]);
            },
            () => {
                this.notification.add(
                    _t("Could not capture your GPS location (device location may be switched off or permission denied). Your attendance will be recorded without GPS position."),
                    { type: "warning" }
                );
                this.orm.call("hr.employee", "update_last_position", [
                    [this.props.employeeId],
                    false,
                    false
                ]);
            }
        );
        const result = await this.orm.call("hr.employee", "attendance_manual", [
            [this.props.employeeId],
            this.props.nextAction,
        ]);
        if (result.action) {
            this.actionService.doAction(result.action);
        } else if (result.warning) {
            this.notification.add(result.warning, {type: "danger"});
        }
    },
});
