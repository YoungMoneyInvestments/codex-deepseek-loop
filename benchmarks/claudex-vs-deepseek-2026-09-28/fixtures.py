"""Synthetic, secret-free fixtures for the loop reviewer benchmark."""

CASES = [
    {
        "id": "plan-archive-safety",
        "kind": "review",
        "title": "Plugin archive verification plan",
        "plan": """# Plan

Download the plugin archive over HTTPS, unpack it into the plugin directory,
then start the plugin. Verify success by importing the plugin.
""",
        "base": {
            "REQUIREMENTS.md": """# Requirements

Downloaded plugin archives are untrusted. Installation must verify the pinned
SHA-256 before extraction. Extraction must reject absolute paths, parent path
escapes, and symbolic or hard links. Failure must leave the prior install intact.
""",
        },
        "candidate": {},
        "context": ["REQUIREMENTS.md"],
        "expected": [
            {
                "id": "archive-hash",
                "severity": "high",
                "paths": ["PLAN.md", "REQUIREMENTS.md"],
                "keywords": [["hash", "sha-256", "checksum", "digest"]],
            },
            {
                "id": "archive-link-traversal",
                "severity": "high",
                "paths": ["PLAN.md", "REQUIREMENTS.md"],
                "keywords": [["symlink", "symbolic link", "hard link", "path traversal", "escape", "absolute", "parent"], ["archive", "extract", "unpack"]],
            },
            {
                "id": "archive-no-rollback",
                "severity": "high",
                "paths": ["PLAN.md", "REQUIREMENTS.md"],
                "keywords": [["rollback", "staging", "temporary", "atomic", "rename", "swap"], ["prior", "live", "current", "intact", "install"]],
            },
        ],
    },
    {
        "id": "plan-ledger-transfer",
        "kind": "review",
        "title": "Idempotent money transfer plan",
        "plan": """# Plan

1. Load the sender balance and reject insufficient funds.
2. Subtract the amount and save the sender.
3. Add the amount and save the receiver.
4. Store the request ID so later duplicates can return the saved response.
5. Add unit tests for a successful transfer and insufficient funds.
""",
        "base": {
            "REQUIREMENTS.md": """# Requirements

A transfer must be atomic: a crash cannot leave only one account changed.
The request ID is the idempotency key. A retry, including a concurrent retry,
must never apply the transfer twice. Amounts are integer cents.
""",
        },
        "candidate": {},
        "context": ["REQUIREMENTS.md"],
        "expected": [
            {
                "id": "transfer-not-atomic",
                "severity": "high",
                "paths": ["PLAN.md", "REQUIREMENTS.md"],
                "keywords": [["atomic", "transaction", "rollback", "partial", "crash"], ["sender", "receiver", "debit", "credit", "balance"]],
            },
            {
                "id": "idempotency-recorded-late",
                "severity": "high",
                "paths": ["PLAN.md", "REQUIREMENTS.md"],
                "keywords": [["idempot", "duplicate", "retry", "replay"], ["before", "after", "late", "race", "concurrent", "unique", "claim"], ["request id", "key", "store", "persist"]],
            },
            {
                "id": "amount-not-validated",
                "severity": "medium",
                "paths": ["PLAN.md", "REQUIREMENTS.md"],
                "keywords": [["integer", "cents"], ["positive", "negative", "zero", "validate", "reject"]],
            },
        ],
    },
    {
        "id": "plan-market-validation",
        "kind": "review",
        "title": "Market-day validation plan",
        "plan": """# Plan

Group fills by UTC calendar date. Shuffle all labeled rows with a fixed seed,
use 80% for training and 20% for validation, then report mean validation PnL.
""",
        "base": {
            "REQUIREMENTS.md": """# Requirements

Daily results use the exchange timezone, including daylight-saving changes and
overnight sessions. Validation must be chronological and causal: no feature,
label, or split may expose future data to an earlier decision.
""",
        },
        "candidate": {},
        "context": ["REQUIREMENTS.md"],
        "expected": [
            {
                "id": "wrong-session-boundary",
                "severity": "high",
                "paths": ["PLAN.md", "REQUIREMENTS.md"],
                "keywords": [["utc"], ["timezone", "exchange time", "dst", "daylight", "overnight", "session"]],
            },
            {
                "id": "noncausal-validation",
                "severity": "high",
                "paths": ["PLAN.md", "REQUIREMENTS.md"],
                "keywords": [["shuffle", "random"], ["chronological", "causal", "leak", "future"]],
            },
        ],
    },
    {
        "id": "inspect-tenant-cache",
        "kind": "inspect",
        "title": "Tenant-scoped cache regression",
        "plan": """# Work order

Cache product lookups for five minutes without changing tenant isolation.
Product IDs are only unique inside a tenant. Keep the public function signature.
""",
        "base": {
            "catalog.py": """def get_product(tenant_id, product_id, db):
    return db.fetch_product(tenant_id, product_id)
""",
        },
        "candidate": {
            "catalog.py": """import time

_cache = {}


def get_product(tenant_id, product_id, db):
    cached = _cache.get(product_id)
    if cached and cached[0] > time.time():
        return cached[1]
    product = db.fetch_product(tenant_id, product_id)
    _cache[product_id] = (time.time() + 300, product)
    return product
""",
        },
        "context": [],
        "expected": [
            {
                "id": "cross-tenant-cache-leak",
                "severity": "high",
                "paths": ["catalog.py"],
                "keywords": [["tenant"], ["cache", "key", "product_id"], ["leak", "cross-tenant", "collision", "wrong", "other tenant"]],
            },
        ],
    },
    {
        "id": "inspect-zip-slip",
        "kind": "inspect",
        "title": "Unsafe archive extraction",
        "plan": """# Work order

Add ZIP installation. Archives are untrusted. Extract only regular files below
the destination; reject absolute paths, parent escapes, and links.
""",
        "base": {
            "installer.py": """def install(zip_path, destination):
    raise NotImplementedError
""",
        },
        "candidate": {
            "installer.py": """import zipfile


def install(zip_path, destination):
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(destination)
""",
        },
        "context": [],
        "expected": [
            {
                "id": "zip-path-escape",
                "severity": "high",
                "paths": ["installer.py"],
                "keywords": [["extractall"], ["reject", "validate", "traversal", "zip slip", "escape", "outside", "absolute", "parent"]],
            },
        ],
    },
    {
        "id": "inspect-ledger-write",
        "kind": "inspect",
        "title": "Money precision and partial write",
        "plan": """# Work order

Implement transfer using exact decimal amounts. Debit and credit must commit in
one database transaction so any error leaves both balances unchanged.
""",
        "base": {
            "ledger.py": """def transfer(db, sender, receiver, amount):
    raise NotImplementedError
""",
        },
        "candidate": {
            "ledger.py": """def transfer(db, sender, receiver, amount):
    amount = float(amount)
    db.update_balance(sender, -amount)
    db.update_balance(receiver, amount)
""",
        },
        "context": [],
        "expected": [
            {
                "id": "binary-float-money",
                "severity": "high",
                "paths": ["ledger.py"],
                "keywords": [["float"], ["decimal", "precision", "binary", "round"]],
            },
            {
                "id": "partial-ledger-write",
                "severity": "high",
                "paths": ["ledger.py"],
                "keywords": [["transaction", "atomic", "rollback", "partial"], ["update_balance", "debit", "credit"]],
            },
        ],
    },
    {
        "id": "inspect-receipt-parser",
        "kind": "inspect",
        "title": "Blank-line parser state regression",
        "plan": """# Work order

Extract chart price levels from receipt Markdown. Ignore every number in an
`Order IDs` section until the next heading, including across blank lines.
""",
        "base": {
            "levels.py": """def extract_levels(lines):
    return [float(line) for line in lines if line.replace('.', '', 1).isdigit()]
""",
        },
        "candidate": {
            "levels.py": """def extract_levels(lines):
    levels = []
    in_ids = False
    for line in lines:
        if line.startswith('## '):
            in_ids = line.strip() == '## Order IDs'
            continue
        if not line.strip():
            in_ids = False
            continue
        if not in_ids and line.replace('.', '', 1).isdigit():
            levels.append(float(line))
    return levels
""",
        },
        "context": [],
        "expected": [
            {
                "id": "blank-line-ends-id-filter",
                "severity": "medium",
                "paths": ["levels.py"],
                "keywords": [["blank", "empty"], ["in_ids", "order id", "ids", "identifier", "section"], ["reset", "false", "price", "level", "number"]],
            },
        ],
    },
    {
        "id": "inspect-clean-retry",
        "kind": "inspect",
        "title": "Clean bounded retry",
        "plan": """# Work order

Retry `TemporaryError` at most twice after the first attempt. Do not retry any
other exception. Return immediately on success.
""",
        "base": {
            "client.py": """class TemporaryError(Exception):
    pass


def fetch(operation):
    return operation()
""",
        },
        "candidate": {
            "client.py": """class TemporaryError(Exception):
    pass


def fetch(operation):
    for attempt in range(3):
        try:
            return operation()
        except TemporaryError:
            if attempt == 2:
                raise
""",
        },
        "context": [],
        "expected": [],
    },
]
