# Fictional relay prototype report
Target: ARM edge board, 1 GB physical RAM, board-specific network driver, deployed viewer, 40 streams; maximum relay RSS 300 MB. Upstream outages occur, and the viewer should recover to current live data after reconnect without restarting the board.

Measured prototype: developer x86 laptop, 32 GB RAM, Linux container, generated data, one loopback stream, no actual viewer, duration 30 seconds. Median relay-only latency 13 ms; RSS at the end 24 MB. Exit code 0. No memory trend, reconnect, backpressure or data completeness observation was recorded.

Implementation fact: when the upstream socket closes, pending messages are currently kept in an unbounded in-memory list until the next successful connection. Retention semantics and overflow behavior have not been chosen. The supplied report contains no raw target-board captures or end-to-end deployment trace.
