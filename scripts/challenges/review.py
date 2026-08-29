"""code_review: find the defects a reviewer would block the PR on.

Nothing is executed here. Each snippet is realistic service code with three
seeded defects — a correctness bug, a scalability or reliability problem, and a
language-appropriate hazard (a data race, a missing await, an injection, a
leaked secret). The evaluator matches the model's findings against the seeded
defects by keyword, so wording is free but the *substance* has to be right, and
padding the report with speculative findings costs precision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import LANGUAGES, dedent_code


@dataclass
class Defect:
    id: str
    anchor: str  # a unique substring of the offending line
    severity: str
    keywords_any: list[str]


@dataclass
class ReviewCase:
    component: str
    language: str
    difficulty: str
    context: str
    code: str
    defects: list[Defect] = field(default_factory=list)

    def to_case(self) -> dict[str, Any]:
        lines = self.code.split("\n")
        defects = []
        for defect in self.defects:
            matches = [i + 1 for i, line in enumerate(lines) if defect.anchor in line]
            if len(matches) != 1:
                raise ValueError(
                    f"{self.component}/{self.language}: anchor {defect.anchor!r} "
                    f"matched {len(matches)} lines, expected exactly 1"
                )
            defects.append(
                {
                    "id": defect.id,
                    "line": matches[0],
                    "severity": defect.severity,
                    "keywords_any": defect.keywords_any,
                }
            )
        return {
            "id": f"{self.component}_{self.language}",
            "language": self.language,
            "component": self.component,
            "difficulty": self.difficulty,
            "context": self.context,
            "code": self.code,
            "defects": defects,
        }


# Keyword sets shared by the same defect class across languages. Matching is on
# normalized text, so "never evict" also matches "entries are never evicted".
STALE_READ = [
    "expired", "stale", "ttl", "past its ttl", "returns the value anyway",
    "should be a miss", "cache miss", "still served", "not invalidated",
]
UNBOUNDED = [
    "unbounded", "never evict", "no eviction", "grows without", "memory leak",
    "no size limit", "no maximum size", "max size", "unlimited growth",
    "grows forever", "out of memory", "no bound", "leak",
]
SQL_INJECTION = [
    "sql injection", "injection", "parameterized", "parameterised",
    "prepared statement", "bind parameter", "placeholder", "string concatenation",
    "interpolat", "not escaped", "unsanitized", "unsanitised",
]
N_PLUS_ONE = [
    "n 1", "n plus 1", "query per", "query inside the loop", "query in a loop",
    "per row query", "round trip per", "batch", "join", "one query for each",
    "queries in a loop", "loop issues a query",
]
NO_BACKOFF = [
    "backoff", "back off", "immediately retr", "tight loop", "hammer",
    "no delay", "no sleep", "no wait", "retry storm", "thundering herd",
    "busy loop", "spin",
]
NO_TIMEOUT = [
    "timeout", "time out", "hang", "hangs forever", "block forever",
    "no deadline", "deadline", "indefinitely",
]
LEAKED_SECRET = [
    "secret", "token", "credential", "api key", "authorization header",
    "auth header", "logs the token", "logging the token", "password",
    "sensitive", "redact",
]
DATA_RACE = [
    "race", "concurrent", "not thread safe", "thread safe", "no lock",
    "without a lock", "mutex", "synchron", "goroutine", "shared state",
    "map is not safe",
]

TTL_CONTEXT = (
    "This cache sits in front of a slow permissions service. It is created once "
    "at process start and shared by every request handler; the server handles "
    "requests concurrently. Entries are meant to disappear after the TTL."
)
DB_CONTEXT = (
    "This is the admin console's user search. `name_filter` comes straight from "
    "a query parameter, and the largest tenant has ~40,000 users."
)
FETCH_CONTEXT = (
    "This helper calls a third-party billing API from a request handler. It runs "
    "on every checkout, and the API has been known to stall for minutes during "
    "incidents."
)


TTL_CACHE = {
    "python": ReviewCase(
        component="ttl_cache",
        language="python",
        difficulty="medium",
        context=TTL_CONTEXT,
        code=dedent_code('''
            import time


            class TTLCache:
                def __init__(self, ttl_seconds: int):
                    self.ttl = ttl_seconds
                    self.entries = {}

                def get(self, key):
                    entry = self.entries.get(key)
                    if entry is None:
                        return None
                    value, stored_at = entry
                    if time.time() - stored_at > self.ttl:
                        return value
                    return value

                def put(self, key, value):
                    self.entries[key] = (value, time.time())

                def size(self):
                    return len(self.entries)
        '''),
        defects=[
            Defect("stale_read", "if time.time() - stored_at > self.ttl:", "high", STALE_READ),
            Defect("unbounded_growth", "self.entries[key] = (value, time.time())", "high", UNBOUNDED),
            Defect("data_race", "self.entries = {}", "medium", DATA_RACE),
        ],
    ),
    "typescript": ReviewCase(
        component="ttl_cache",
        language="typescript",
        difficulty="medium",
        context=TTL_CONTEXT,
        code=dedent_code('''
            type Entry = { value: unknown; storedAt: number };

            export class TTLCache {
                private ttlSeconds: number;
                private entries = new Map<string, Entry>();

                constructor(ttlSeconds: number) {
                    this.ttlSeconds = ttlSeconds;
                }

                get(key: string): unknown {
                    const entry = this.entries.get(key);
                    if (entry === undefined) {
                        return null;
                    }
                    if (Date.now() - entry.storedAt > this.ttlSeconds) {
                        return entry.value;
                    }
                    return entry.value;
                }

                put(key: string, value: unknown): void {
                    this.entries.set(key, { value, storedAt: Date.now() });
                }

                size(): number {
                    return this.entries.size;
                }
            }
        '''),
        defects=[
            Defect("stale_read", "if (Date.now() - entry.storedAt > this.ttlSeconds) {", "high", STALE_READ),
            Defect("unbounded_growth", "this.entries.set(key, { value, storedAt: Date.now() });", "high", UNBOUNDED),
            Defect(
                "unit_mismatch",
                "private ttlSeconds: number;",
                "high",
                [
                    "millisecond", "1000", "seconds", "wrong unit",
                    "unit mismatch", "mismatch", "wrong scale", "date now",
                ],
            ),
        ],
    ),
    "go": ReviewCase(
        component="ttl_cache",
        language="go",
        difficulty="medium",
        context=TTL_CONTEXT,
        code=dedent_code('''
            package cache

            import "time"

            type entry struct {
                value    interface{}
                storedAt time.Time
            }

            type TTLCache struct {
                ttl     time.Duration
                entries map[string]entry
            }

            func NewTTLCache(ttl time.Duration) *TTLCache {
                return &TTLCache{ttl: ttl, entries: make(map[string]entry)}
            }

            func (c *TTLCache) Get(key string) (interface{}, bool) {
                e, ok := c.entries[key]
                if !ok {
                    return nil, false
                }
                if time.Since(e.storedAt) > c.ttl {
                    return e.value, true
                }
                return e.value, true
            }

            func (c *TTLCache) Put(key string, value interface{}) {
                c.entries[key] = entry{value: value, storedAt: time.Now()}
            }
        '''),
        defects=[
            Defect("stale_read", "if time.Since(e.storedAt) > c.ttl {", "high", STALE_READ),
            Defect("unbounded_growth", "c.entries[key] = entry{value: value, storedAt: time.Now()}", "high", UNBOUNDED),
            Defect("data_race", "entries map[string]entry", "high", DATA_RACE),
        ],
    ),
    "rust": ReviewCase(
        component="ttl_cache",
        language="rust",
        difficulty="medium",
        context=TTL_CONTEXT,
        code=dedent_code('''
            use std::collections::HashMap;
            use std::time::{Duration, Instant};

            pub struct TtlCache {
                ttl: Duration,
                entries: HashMap<String, (String, Instant)>,
            }

            impl TtlCache {
                pub fn new(ttl: Duration) -> Self {
                    TtlCache { ttl, entries: HashMap::new() }
                }

                pub fn get(&self, key: &str) -> Option<String> {
                    let (value, stored_at) = self.entries.get(key)?;
                    if stored_at.elapsed() > self.ttl {
                        return Some(value.clone());
                    }
                    Some(value.clone())
                }

                pub fn put(&mut self, key: String, value: String) {
                    self.entries.insert(key, (value, Instant::now()));
                }

                pub fn must_get(&self, key: &str) -> String {
                    self.get(key).unwrap()
                }
            }
        '''),
        defects=[
            Defect("stale_read", "if stored_at.elapsed() > self.ttl {", "high", STALE_READ),
            Defect("unbounded_growth", "self.entries.insert(key, (value, Instant::now()));", "high", UNBOUNDED),
            Defect(
                "panic_on_miss",
                "self.get(key).unwrap()",
                "high",
                [
                    "unwrap", "panic", "crash", "none", "missing key",
                    "cache miss", "expect", "propagate the error", "option",
                ],
            ),
        ],
    ),
}


USER_LOOKUP = {
    "python": ReviewCase(
        component="user_lookup",
        language="python",
        difficulty="medium",
        context=DB_CONTEXT,
        code=dedent_code('''
            def search_users(conn, name_filter, tenant_id):
                cursor = conn.cursor()
                query = (
                    "SELECT id, name FROM users "
                    f"WHERE tenant_id = {tenant_id} AND name LIKE '%{name_filter}%'"
                )
                cursor.execute(query)
                rows = cursor.fetchall()

                results = []
                for row in rows:
                    user_id, name = row
                    role_cursor = conn.cursor()
                    role_cursor.execute("SELECT role FROM roles WHERE user_id = ?", (user_id,))
                    role = role_cursor.fetchone()
                    results.append({"id": user_id, "name": name, "role": role[0]})
                return results
        '''),
        defects=[
            Defect("sql_injection", 'f"WHERE tenant_id = {tenant_id} AND name LIKE', "critical", SQL_INJECTION),
            Defect("n_plus_one", 'role_cursor.execute("SELECT role FROM roles WHERE user_id = ?", (user_id,))', "high", N_PLUS_ONE),
            Defect(
                "unchecked_result",
                'results.append({"id": user_id, "name": name, "role": role[0]})',
                "medium",
                [
                    "none", "null", "no role", "missing row", "fetchone",
                    "index error", "typeerror", "unchecked", "no result",
                    "crash", "exception",
                ],
            ),
        ],
    ),
    "typescript": ReviewCase(
        component="user_lookup",
        language="typescript",
        difficulty="medium",
        context=DB_CONTEXT,
        code=dedent_code('''
            export async function searchUsers(db: Db, nameFilter: string, tenantId: string) {
                const query =
                    "SELECT id, name FROM users WHERE tenant_id = '" + tenantId +
                    "' AND name LIKE '%" + nameFilter + "%'";
                const rows = await db.query(query);

                const results = [];
                for (const row of rows) {
                    const roleRow = db.query("SELECT role FROM roles WHERE user_id = $1", [row.id]);
                    results.push({ id: row.id, name: row.name, role: roleRow.role });
                }
                return results;
            }
        '''),
        defects=[
            Defect("sql_injection", '"SELECT id, name FROM users WHERE tenant_id = \'" + tenantId +', "critical", SQL_INJECTION),
            Defect("n_plus_one", 'const roleRow = db.query("SELECT role FROM roles WHERE user_id = $1", [row.id]);', "high", N_PLUS_ONE),
            Defect(
                "missing_await",
                "results.push({ id: row.id, name: row.name, role: roleRow.role });",
                "high",
                [
                    "await", "promise", "async", "not awaited", "unresolved",
                    "undefined", "floating promise", "unhandled rejection",
                ],
            ),
        ],
    ),
    "go": ReviewCase(
        component="user_lookup",
        language="go",
        difficulty="medium",
        context=DB_CONTEXT,
        code=dedent_code('''
            func SearchUsers(db *sql.DB, nameFilter string, tenantID string) []User {
                query := fmt.Sprintf(
                    "SELECT id, name FROM users WHERE tenant_id = '%s' AND name LIKE '%%%s%%'",
                    tenantID, nameFilter,
                )
                rows, _ := db.Query(query)

                var results []User
                for rows.Next() {
                    var u User
                    rows.Scan(&u.ID, &u.Name)
                    roleRow := db.QueryRow("SELECT role FROM roles WHERE user_id = $1", u.ID)
                    roleRow.Scan(&u.Role)
                    results = append(results, u)
                }
                return results
            }
        '''),
        defects=[
            Defect("sql_injection", '"SELECT id, name FROM users WHERE tenant_id = \'%s\' AND name LIKE \'%%%s%%\'",', "critical", SQL_INJECTION),
            Defect("n_plus_one", 'roleRow := db.QueryRow("SELECT role FROM roles WHERE user_id = $1", u.ID)', "high", N_PLUS_ONE),
            Defect(
                "ignored_error",
                "rows, _ := db.Query(query)",
                "high",
                [
                    "error", "err", "ignored", "discard", "blank identifier",
                    "not checked", "unchecked", "nil pointer", "close",
                    "rows err",
                ],
            ),
        ],
    ),
    "rust": ReviewCase(
        component="user_lookup",
        language="rust",
        difficulty="medium",
        context=DB_CONTEXT,
        code=dedent_code('''
            pub fn search_users(conn: &Connection, name_filter: &str, tenant_id: &str) -> Vec<User> {
                let query = format!(
                    "SELECT id, name FROM users WHERE tenant_id = '{}' AND name LIKE '%{}%'",
                    tenant_id, name_filter
                );
                let rows = conn.query(&query).unwrap();

                let mut results = Vec::new();
                for row in rows {
                    let role = conn
                        .query_one("SELECT role FROM roles WHERE user_id = $1", &[&row.id])
                        .unwrap();
                    results.push(User { id: row.id, name: row.name, role: role.get(0) });
                }
                results
            }
        '''),
        defects=[
            Defect("sql_injection", '"SELECT id, name FROM users WHERE tenant_id = \'{}\' AND name LIKE \'%{}%\'",', "critical", SQL_INJECTION),
            Defect("n_plus_one", '.query_one("SELECT role FROM roles WHERE user_id = $1", &[&row.id])', "high", N_PLUS_ONE),
            Defect(
                "unwrap_panic",
                "let rows = conn.query(&query).unwrap();",
                "high",
                [
                    "unwrap", "panic", "crash", "result", "propagate",
                    "error handling", "question mark", "expect",
                ],
            ),
        ],
    ),
}


FETCH_RETRY = {
    "python": ReviewCase(
        component="fetch_with_retry",
        language="python",
        difficulty="medium",
        context=FETCH_CONTEXT,
        code=dedent_code('''
            import logging
            import requests

            log = logging.getLogger(__name__)


            def fetch_invoice(invoice_id: str, api_token: str) -> dict:
                url = f"https://billing.example.com/invoices/{invoice_id}"
                headers = {"Authorization": f"Bearer {api_token}"}
                log.info("calling billing api url=%s headers=%s", url, headers)

                attempt = 0
                while attempt < 5:
                    attempt += 1
                    response = requests.get(url, headers=headers)
                    if response.status_code == 200:
                        return response.json()
                raise RuntimeError("billing api unavailable")
        '''),
        defects=[
            Defect("leaked_secret", 'log.info("calling billing api url=%s headers=%s", url, headers)', "critical", LEAKED_SECRET),
            Defect("no_timeout", "response = requests.get(url, headers=headers)", "high", NO_TIMEOUT),
            Defect("no_backoff", "while attempt < 5:", "medium", NO_BACKOFF),
        ],
    ),
    "typescript": ReviewCase(
        component="fetch_with_retry",
        language="typescript",
        difficulty="medium",
        context=FETCH_CONTEXT,
        code=dedent_code('''
            export async function fetchInvoice(invoiceId: string, apiToken: string) {
                const url = `https://billing.example.com/invoices/${invoiceId}`;
                const headers = { Authorization: `Bearer ${apiToken}` };
                console.log("calling billing api", { url, headers });

                let attempt = 0;
                while (attempt < 5) {
                    attempt += 1;
                    const response = await fetch(url, { headers });
                    if (response.status === 200) {
                        return await response.json();
                    }
                }
                throw new Error("billing api unavailable");
            }
        '''),
        defects=[
            Defect("leaked_secret", 'console.log("calling billing api", { url, headers });', "critical", LEAKED_SECRET),
            Defect("no_timeout", "const response = await fetch(url, { headers });", "high", NO_TIMEOUT),
            Defect("no_backoff", "while (attempt < 5) {", "medium", NO_BACKOFF),
        ],
    ),
    "go": ReviewCase(
        component="fetch_with_retry",
        language="go",
        difficulty="medium",
        context=FETCH_CONTEXT,
        code=dedent_code('''
            func FetchInvoice(invoiceID string, apiToken string) ([]byte, error) {
                url := fmt.Sprintf("https://billing.example.com/invoices/%s", invoiceID)
                req, _ := http.NewRequest("GET", url, nil)
                req.Header.Set("Authorization", "Bearer "+apiToken)
                log.Printf("calling billing api url=%s headers=%v", url, req.Header)

                for attempt := 0; attempt < 5; attempt++ {
                    resp, err := http.DefaultClient.Do(req)
                    if err != nil {
                        continue
                    }
                    if resp.StatusCode == 200 {
                        return io.ReadAll(resp.Body)
                    }
                }
                return nil, errors.New("billing api unavailable")
            }
        '''),
        defects=[
            Defect("leaked_secret", 'log.Printf("calling billing api url=%s headers=%v", url, req.Header)', "critical", LEAKED_SECRET),
            Defect("no_timeout", "resp, err := http.DefaultClient.Do(req)", "high", NO_TIMEOUT),
            Defect("no_backoff", "for attempt := 0; attempt < 5; attempt++ {", "medium", NO_BACKOFF),
        ],
    ),
    "rust": ReviewCase(
        component="fetch_with_retry",
        language="rust",
        difficulty="medium",
        context=FETCH_CONTEXT,
        code=dedent_code('''
            pub fn fetch_invoice(invoice_id: &str, api_token: &str) -> Result<String, Error> {
                let url = format!("https://billing.example.com/invoices/{}", invoice_id);
                let auth = format!("Bearer {}", api_token);
                log::info!("calling billing api url={} auth={}", url, auth);

                let client = reqwest::blocking::Client::new();
                let mut attempt = 0;
                while attempt < 5 {
                    attempt += 1;
                    if let Ok(response) = client.get(&url).header("Authorization", &auth).send() {
                        if response.status().is_success() {
                            return Ok(response.text()?);
                        }
                    }
                }
                Err(Error::Unavailable)
            }
        '''),
        defects=[
            Defect("leaked_secret", 'log::info!("calling billing api url={} auth={}", url, auth);', "critical", LEAKED_SECRET),
            Defect("no_timeout", "let client = reqwest::blocking::Client::new();", "high", NO_TIMEOUT),
            Defect("no_backoff", "while attempt < 5 {", "medium", NO_BACKOFF),
        ],
    ),
}


COMPONENTS = [TTL_CACHE, USER_LOOKUP, FETCH_RETRY]


def build_cases() -> list[dict[str, Any]]:
    cases = []
    for component in COMPONENTS:
        for language in LANGUAGES:
            cases.append(component[language].to_case())
    return cases
