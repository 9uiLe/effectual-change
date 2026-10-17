# Notification API
subscribe emits a best-effort hint that something changed. A hint can be dropped or repeated, has no durable sequence position, and contains no complete revision transaction. The intended consumer may use a hint to wake a synchronization attempt; subscribe by itself does not establish cache completeness.
