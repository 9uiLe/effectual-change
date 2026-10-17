"""Print the delivery badge for a supplied field value."""

import sys


def delivery_badge(delivered_at: str) -> str:
    return "Delivered" if delivered_at else "Pending"


if __name__ == "__main__":
    print(delivery_badge(sys.argv[1]))
