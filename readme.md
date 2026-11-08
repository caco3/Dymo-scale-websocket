# DYMO Scale Gateway

Provides a websocket on port **8085** which broadcasts the weight read from a
DYMO USB scale (**DYMO M10**, USB VID `0922`).

## Connecting the M10

The M10 plugs directly into the PC via USB; this gateway reads its raw HID
reports from `/dev/hidraw*` (it finds the first HID node with VID `0922`).

Note: The M10 normally auto-sleeps after ~3 min without a button press or weight
change and stops enumerating — it must be powered on again with its POWER
button. To work around this, the scale can be modified to toggle the unit (kg/lb) twice every 2.5 minutes.
See https://github.com/caco3/Dymo-M10-scale-without-power-off for details.

## Protocol

- `{"status": "ok", "weight": <grams>}`
- `{"status": "error", "code": "NO_SCALE", "description": "Waage ausgeschaltet oder nicht verbunden!"}`
- `{"status": "error", "code": "NO_DATA", "description": "Keine Daten verfügbar!"}`
- `{"status": "error", "code": "OVERLOAD", "description": "Überlast!"}`

Note: the DYMO only sends HID reports when the weight changes. If the scale is
powered off or silent for >2 s, `NO_SCALE` is broadcast once.

## Setup

```bash
docker compose up -d --build --remove-orphans
```

## Logfile

A log file is written to `Dymo-Waage/log/scale.log` (bind-mounted to
`/app/log` in the container; persists across reboots).
You can monitor it with `tail -F Dymo-Waage/log/scale.log`
(It is buffered and thus delayed).

Every state change (weight or error) is logged with a timestamp;
repeated identical messages are suppressed, e.g.

```
2026-11-08 23:45:12 {"status": "ok", "weight": 123}
2026-11-08 23:46:01 {"status": "error", "code": "NO_SCALE", "description": "Waage ausgeschaltet oder nicht verbunden!"}
```

## Troubleshooting

- The scale must be plugged in (and powered on) to enumerate as a HID device.
- To debug the raw HID reports outside docker, run `python3 app/dymoscale.py`
  on the host (needs permission to open `/dev/hidraw*`, e.g. via sudo).
