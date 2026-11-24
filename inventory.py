"""Small in-memory primary/secondary replication lab. No dependencies."""

import argparse
import getpass
import socket
import threading
import time


class Inventory:
    def __init__(self):
        self.stock = {"primary": 0, "secondary": 0}
        self.paused = False
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.worker = threading.Thread(target=self.replicate)
        self.worker.start()

    def read(self, replica):
        with self.lock:
            return self.stock[replica]

    def write(self, stock):
        if type(stock) is not int or stock < 0:
            raise ValueError("Stock must be a nonnegative integer")
        with self.lock:
            self.stock["primary"] = stock

    def pause(self, paused):
        with self.lock:
            self.paused = paused

    def replicate(self):
        while not self.stopped.wait(0.5):
            with self.lock:
                if not self.paused:
                    self.stock["secondary"] = self.stock["primary"]

    def close(self):
        self.stopped.set()
        self.worker.join()


def wait_for_stock(inventory, expected):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if inventory.read("secondary") == expected:
            return
        time.sleep(0.05)
    raise TimeoutError(f"Secondary did not reach stock={expected}")


def demo(step=False):
    def heading(title):
        if step:
            print("\033[2J\033[H", end="", flush=True)
        print(f"{getpass.getuser()}@{socket.gethostname()}")
        print(title)
        print("-" * 48)

    def show(expected_primary, expected_secondary):
        primary = inventory.read("primary")
        secondary = inventory.read("secondary")
        print(f"READ primary   -> stock={primary}")
        print(f"READ secondary -> stock={secondary}")
        assert (primary, secondary) == (expected_primary, expected_secondary)

    def next_step():
        if step:
            input("\nPress Enter for the next test...")
        else:
            print()

    inventory = Inventory()
    try:
        heading("1. Successful replication")
        print("WRITE primary -> stock=10")
        inventory.write(10)
        assert inventory.read("primary") == 10
        print("Waiting for background replication...")
        wait_for_stock(inventory, 10)
        show(10, 10)
        print("PASS: both replicas return 10")
        next_step()

        heading("2. Stale read")
        inventory.pause(True)
        print("Replication PAUSED")
        inventory.write(9)
        print("WRITE primary -> stock=9")
        print("Waiting 2 seconds with replication paused...")
        time.sleep(2)
        show(9, 10)
        print("PASS: secondary still returns the old value (10)")
        next_step()

        heading("3. Recovery and convergence")
        inventory.pause(False)
        print("Replication RESUMED (no new write)")
        print("Waiting for the secondary to catch up...")
        wait_for_stock(inventory, 9)
        show(9, 9)
        print("PASS: both replicas return 9")
        print("\nAll three checks passed.")
    finally:
        inventory.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", action="store_true", help="pause between tests for screenshots")
    demo(parser.parse_args().step)
