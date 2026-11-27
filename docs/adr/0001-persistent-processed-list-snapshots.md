# Persistent processed list snapshots

Ruantiblock recovers from one persistent snapshot of processed lists rather than from cached raw source downloads.

**Processed recovery boundary.** The snapshot covers main, user, and bypass lists as one restorable unit. Raw per-source caching is rejected because it would require every downloader to implement caching and could mix source generations.

**Mandatory staged promotion.** A snapshot is published only from a successful staged update. The optional safe-update mode is retired; higher peak memory use is accepted to preserve known-good lists after a failed update.

**Persistent OpenWrt storage.** The snapshot lives in a fixed package-private directory on the writable root filesystem. Volatile runtime storage and removable-media discovery are rejected as recovery boundaries.
