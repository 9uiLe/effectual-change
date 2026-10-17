# Listing API
listAll(pageToken) returns pages of the current catalog. Pages are not pinned to one revision. A concurrent rename can therefore produce a mixed traversal. A later traversal can converge once changes stop. Each full traversal downloads all entries. This endpoint does not return a durable resume cursor.
