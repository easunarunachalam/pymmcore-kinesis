"""Print the serial numbers of all connected Thorlabs Kinesis controllers.

    python -m pymmcore_kinesis.list
"""

from __future__ import annotations

from pylablib.devices import Thorlabs


def main() -> None:
    devices = Thorlabs.list_kinesis_devices()
    if not devices:
        print("No Kinesis devices found. Is the hardware connected and powered on?")
        return
    print(f"{'index':>5}  {'serial':>10}  description")
    for i, (serial, desc) in enumerate(devices):
        print(f"{i:>5}  {serial:>10}  {desc}")


if __name__ == "__main__":
    main()
