import os
import glob
import fcntl
import struct
import select

DYMO_VENDOR_ID = 0x0922

# HIDIOCGRAWINFO: _IOR('H', 0x03, struct hidraw_devinfo {u32 bustype; s16 vendor; s16 product})
HIDIOCGRAWINFO = 0x80084803
BUS_USB = 0x03

# Status codes (USB HID "Point of Sale" scale usage page)
STATUS_FAULT = 0x01
STATUS_STABLE_ZERO = 0x02
STATUS_IN_MOTION = 0x03
STATUS_STABLE = 0x04
STATUS_UNDER_ZERO = 0x05
STATUS_OVER_LIMIT = 0x06
STATUS_REQUIRES_CAL = 0x07
STATUS_REQUIRES_REZERO = 0x08

STATUS_NAMES = {
    STATUS_FAULT: "fault",
    STATUS_STABLE_ZERO: "stable at zero",
    STATUS_IN_MOTION: "in motion",
    STATUS_STABLE: "stable",
    STATUS_UNDER_ZERO: "under zero",
    STATUS_OVER_LIMIT: "over limit",
    STATUS_REQUIRES_CAL: "requires calibration",
    STATUS_REQUIRES_REZERO: "requires re-zeroing",
}

# Statuses which carry a usable weight value
WEIGHT_STATUSES = (STATUS_STABLE_ZERO, STATUS_IN_MOTION, STATUS_STABLE, STATUS_UNDER_ZERO)

# HID units-of-weight to grams conversion factor
UNIT_TO_GRAMS = {
    0x01: 0.001,        # milligram
    0x02: 1.0,          # gram
    0x03: 1000.0,       # kilogram
    0x04: 0.2,          # carat
    0x05: 37.7994,      # tael
    0x06: 0.0647989,    # grain
    0x07: 1.55517384,   # pennyweight
    0x08: 1000000.0,    # metric ton
    0x09: 1016046.91,   # avoirdupois ton
    0x0A: 31.1034768,   # troy ounce
    0x0B: 28.3495231,   # ounce
    0x0C: 453.59237,    # pound
}


class DymoScale():
    """Reads weight reports from a DYMO USB scale (e.g. M10) via hidraw."""

    fd = None
    device_path = None

    @staticmethod
    def find_device():
        """Scan all /dev/hidraw* nodes and return the path of the first DYMO device."""
        for path in sorted(glob.glob("/dev/hidraw*")):
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError:
                continue
            try:
                info = fcntl.ioctl(fd, HIDIOCGRAWINFO, b"\x00" * 8)
                bustype, vid, pid = struct.unpack("Ihh", info[:8])
                if bustype == BUS_USB and vid == DYMO_VENDOR_ID:
                    return path
            except OSError:
                pass
            finally:
                os.close(fd)
        return None

    def connect(self):
        """Find and open the DYMO scale. Returns True on success."""
        self.disconnect()
        path = self.find_device()
        if path is None:
            print("No DYMO scale found on any /dev/hidraw* device")
            return False
        try:
            # Open blocking: reads wait for the next report
            self.fd = os.open(path, os.O_RDONLY)
            self.device_path = path
            print(f"Connected to DYMO scale on {path}")
            return True
        except OSError as ex:
            print(f"Failed to open {path}: {ex}")
            self.fd = None
            return False

    def disconnect(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
            self.device_path = None

    def read_report(self, timeout=None):
        """Read one HID report. Returns bytes, or None on timeout. Raises on disconnect."""
        if self.fd is None:
            raise Exception("Scale is not connected")
        r, _, _ = select.select([self.fd], [], [], timeout)
        if not r:
            return None
        data = os.read(self.fd, 64)
        if len(data) == 0:
            raise Exception("Scale disconnected (empty read)")
        return data

    @staticmethod
    def parse_report(data):
        """Parse a HID report.

        Expected layout: [report_id, status, unit, exponent, weight_lo, weight_hi]
        (without leading report_id byte on unnumbered reports).

        Returns {"weight": <grams>} for weight reports,
        {"code": <str>, "description": <str>} for error statuses,
        or None if the report cannot be used.
        """
        # Find the layout: numbered reports start with a report ID byte,
        # unnumbered ones start directly with the status byte.
        offset = None
        for o in (1, 0):
            if len(data) >= o + 5 and data[o + 1] in UNIT_TO_GRAMS:
                offset = o
                break

        if offset is None:
            # Unit byte not recognized; assume a numbered report and grams
            if len(data) >= 6:
                offset = 1
            else:
                print(f"Unexpected report ({len(data)} bytes): {data.hex()}")
                return None

        status = data[offset]
        unit = data[offset + 1]
        exponent = struct.unpack("b", data[offset + 2:offset + 3])[0]
        raw = struct.unpack("<h", data[offset + 3:offset + 5])[0]

        status_name = STATUS_NAMES.get(status, f"unknown ({status:#x})")

        if status in WEIGHT_STATUSES:
            factor = UNIT_TO_GRAMS.get(unit)
            if factor is None:
                print(f"Unknown unit {unit:#x}, assuming grams")
                factor = 1.0
            grams = raw * (10 ** exponent) * factor
            # Round to whole grams (the M10's 2 g resolution in kg mode anyway,
            # and this avoids fractional output when the scale reports oz/lb)
            return {"weight": round(grams)}
        elif status == STATUS_OVER_LIMIT:
            return {"code": "OVERLOAD", "description": "Ueberlast!"}
        else:
            print(f"Scale status: {status_name} (report: {data.hex()})")
            return None


if __name__ == "__main__":
    # Standalone test: print raw reports and parsed weights
    import time
    scale = DymoScale()
    while True:
        while not scale.connect():
            time.sleep(1)
        try:
            report = scale.read_report(timeout=10)
            if report is None:
                print("No report within 10s")
                continue
            print(f"Report ({len(report)} bytes): {report.hex()} -> {scale.parse_report(report)}")
        except Exception as ex:
            print(f"Error: {ex}")
            scale.disconnect()
