"""Self-hosted auth primitives (D-0014) — no external service, stdlib only.

`passwords` hashes with PBKDF2-HMAC-SHA256; `tokens` mints HMAC-signed bearer
tokens. Both are dependency-free and fully self-hostable, in line with the
cost-conscious/FOSS policy (D-0012).
"""

from __future__ import annotations
