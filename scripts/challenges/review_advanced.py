"""Harder code_review components.

Same contract as ``review.py``: realistic service code with three seeded
defects, matched by keyword so wording is free but the mechanism has to be
named.

The existing three components seed defects a linter or a careful skim finds —
an f-string in a SQL query, a request without a timeout. These ten are aimed at
the failures that only show up in production: a paginator that spins forever
when a cursor is missing, a readiness probe that reports healthy *because* the
database check threw, a leader lease renewed on the same interval as its own
TTL. The code around them is deliberately unremarkable, so a review has to
reason about what happens under concurrency, failure and time rather than
pattern-match on a suspicious-looking line.
"""

from __future__ import annotations

from .common import dedent_code
from .review import Defect, ReviewCase

# ---------------------------------------------------------------------------
# Shared keyword vocabularies.
#
# Within one component the three sets are kept disjoint: findings are assigned
# to defects greedily in order, so a word shared by two defects would let one
# finding claim the wrong slot.
# ---------------------------------------------------------------------------

STUCK_CURSOR = [
    "infinite", "never advance", "does not advance", "loop forever",
    "never terminate", "same page", "same cursor", "spin", "unchanged",
    "repeat", "endless", "stuck", "no progress",
]
UNBOUNDED_BUFFER = [
    "unbounded", "memory", "accumulat", "grows", "buffers everything",
    "in memory", "out of memory", "oom", "whole result", "entire",
    "all at once", "no limit", "stream",
]
SHORT_PAGE = [
    "short page", "fewer than", "partial page", "ends early", "stops early",
    "premature", "misses", "missed", "skips", "skipped", "full page",
    "page size", "500", "wrong termination", "silently",
]

UNSTABLE_KEY = [
    "timestamp", "clock", "time", "different key", "new key", "changes",
    "not stable", "unstable", "not deterministic", "deterministic",
    "never matches", "unique every", "defeats",
]
CHECK_THEN_ACT = [
    "race", "toctou", "check then act", "concurrent", "atomic", "not atomic",
    "double charge", "charged twice", "duplicate", "twice", "simultaneous",
    "lock", "unique constraint", "upsert", "two requests",
]
LEAKED_SECRET = [
    "secret", "token", "credential", "api key", "card", "pan", "authorization",
    "auth header", "logs the", "logging", "password", "sensitive", "redact",
    "pci",
]

FAIL_OPEN = [
    "fail open", "fails open", "swallow", "silently", "reports healthy",
    "healthy anyway", "still healthy", "always healthy", "catch", "except",
    "masks", "hides", "ignores the error", "returns 200", "200 anyway",
]
NO_TIMEOUT = [
    "timeout", "time out", "hang", "hangs", "block forever", "no deadline",
    "deadline", "indefinitely", "stall",
]
CACHED_FOREVER = [
    "cached", "cache", "never refresh", "never re", "only once", "once",
    "first call", "latches", "sticky", "stale", "permanently", "forever",
    "memo", "never rechecked",
]

INTEGER_DRIFT = [
    "integer division", "truncat", "rounds down", "floor", "remainder",
    "drift", "loses", "lost", "fractional", "rounding", "lower than",
    "slower than", "under the configured", "int",
]
WRONG_KEY = [
    "per client", "per tenant", "per user", "all clients", "one client",
    "not keyed", "keyed by", "everyone", "cross tenant", "same bucket",
    "single bucket", "endpoint", "path", "route",
]
NEVER_EVICTED = [
    "never evict", "no eviction", "grows", "unbounded", "memory leak",
    "no size limit", "leak", "never removed", "cleanup", "forever",
    "out of memory", "entry per",
]
DATA_RACE = [
    "race", "concurrent", "not thread safe", "thread safe", "no lock",
    "without a lock", "mutex", "synchron", "goroutine", "shared state",
    "map is not safe", "atomic",
]

TORN_CONFIG = [
    "in place", "mutate", "partially", "half", "torn", "readers", "atomic",
    "swap", "replace", "clear", "visible", "concurrent", "race", "empty for",
    "window",
]
NO_VALIDATION = [
    "validat", "verify", "schema", "sanity", "typo", "malformed", "invalid",
    "bad config", "before applying", "check the", "unchecked", "garbage",
]
SWALLOWED_ERROR = [
    "swallow", "silently", "ignored", "ignores", "no log", "hides", "masks",
    "fails silently", "empty config", "defaults", "no alert", "unnoticed",
    "except pass", "bare except",
]

NO_TIME_FLUSH = [
    "timer", "time based", "interval", "only when full", "never flushed",
    "sits", "delayed", "low volume", "linger", "until it fills",
    "size only", "latency", "hours",
]
CLEARED_BEFORE_WRITE = [
    "cleared before", "clear the buffer", "before the write", "before flush",
    "before it succeeds", "on failure", "error path", "discarded", "dropped",
    "not restored", "not retried", "lost",
]
NO_SHUTDOWN_FLUSH = [
    "shutdown", "shut down", "exit", "sigterm", "drain", "graceful",
    "terminate", "final flush", "remaining", "close", "deploy", "restart",
]

LEASE_MARGIN = [
    "ttl", "interval", "too long", "equal", "no margin", "gap",
    "renewal period", "half", "same as", "one renewal", "single missed",
    "misses one", "sleeps for", "as long as",
]
NO_FENCING = [
    "fencing", "fence", "split brain", "two leaders", "old leader", "paused",
    "gc pause", "still writes", "stale leader", "epoch", "generation",
    "both", "partition",
]
WALL_CLOCK = [
    "wall clock", "monotonic", "ntp", "skew", "time jump", "system time",
    "local time", "adjust", "clock change", "backwards", "steps",
]

TIMING_ATTACK = [
    "timing attack", "constant time", "timing", "side channel", "early return",
    "byte by byte", "compare_digest", "hmac equal", "leaks the signature",
    "guess the signature",
]
REPLAY = [
    "replay", "timestamp", "expiry", "expire", "stale request", "nonce",
    "reused", "reuse", "old request", "captured request", "freshness",
    "age of the",
]
MISSING_SIGNATURE = [
    "missing", "absent", "empty", "no signature", "none", "null", "bypass",
    "skips verification", "unsigned", "not present", "unauthenticated",
    "returns true", "accepts", "anyone",
]

NEVER_RESETS = [
    "reset", "never reset", "cumulative", "consecutive", "not consecutive",
    "over time", "eventually", "counter", "accumulat", "lifetime", "success",
    "days", "forever",
]
HALF_OPEN_FLOOD = [
    "half open", "stampede", "all requests", "one request", "probe", "single",
    "flood", "thundering herd", "at once", "everything through",
]
OVERBROAD_CATCH = [
    "every exception", "all exceptions", "any exception", "every error",
    "all errors", "client error", "4xx", "validation", "bad request",
    "unrelated", "programming", "not a dependency", "catch all",
    "indiscriminate", "own errors",
]

PATH_TRAVERSAL = [
    "traversal", "dot dot", "sanitize", "sanitise", "basename", "arbitrary",
    "escape the directory", "overwrite", "outside", "absolute path",
    "attacker controlled", "filename", "join",
]
UNBOUNDED_READ = [
    "size limit", "content length", "unbounded", "memory", "whole file",
    "entire", "read all", "oom", "out of memory", "max size", "large upload",
    "dos", "exhaust",
]
HANDLE_LEAK = [
    "close", "closed", "leak", "handle", "descriptor", "defer", "cleanup",
    "clean up", "temp", "not removed", "orphan", "context manager",
    "left behind", "fills the disk",
]

# ---------------------------------------------------------------------------
# Contexts
# ---------------------------------------------------------------------------

PAGER_CONTEXT = (
    "This job pulls audit events from a partner API into our warehouse. It runs "
    "every five minutes for every tenant; the API returns at most 500 events per "
    "page and signals the end of the stream with an empty next cursor. The "
    "busiest tenant produces a few million events a day."
)
CHARGE_CONTEXT = (
    "This endpoint charges a customer's card and is meant to be safe to retry. "
    "Clients retry on network errors, and the mobile app is known to send the "
    "same request twice a few hundred milliseconds apart."
)
READY_CONTEXT = (
    "This is the /readyz handler behind the load balancer. Kubernetes calls it "
    "every two seconds per pod and takes the pod out of the service when it "
    "fails; the database check talks to the primary."
)


SYNC_PAGER = {
    "python": ReviewCase(
        component="sync_pager",
        language="python",
        difficulty="hard",
        context=PAGER_CONTEXT,
        code=dedent_code('''
            def sync_events(client, warehouse, tenant_id, since):
                cursor = ""
                collected = []

                while True:
                    page = client.list_events(tenant_id, since=since, cursor=cursor)
                    collected.extend(page["events"])
                    if len(page["events"]) < 500:
                        break
                    cursor = page.get("next_cursor", cursor)

                warehouse.write(collected)
                return len(collected)
        '''),
        defects=[
            Defect("stuck_cursor", 'cursor = page.get("next_cursor", cursor)', "high", STUCK_CURSOR),
            Defect("unbounded_buffer", 'collected.extend(page["events"])', "high", UNBOUNDED_BUFFER),
            Defect("short_page_end", 'if len(page["events"]) < 500:', "high", SHORT_PAGE),
        ],
    ),
    "typescript": ReviewCase(
        component="sync_pager",
        language="typescript",
        difficulty="hard",
        context=PAGER_CONTEXT,
        code=dedent_code('''
            export async function syncEvents(
                client: PartnerClient,
                warehouse: Warehouse,
                tenantId: string,
                since: string,
            ): Promise<number> {
                let cursor = "";
                const collected: AuditEvent[] = [];

                while (true) {
                    const page = await client.listEvents(tenantId, since, cursor);
                    collected.push(...page.events);
                    if (page.events.length < 500) {
                        break;
                    }
                    cursor = page.nextCursor ?? cursor;
                }

                await warehouse.write(collected);
                return collected.length;
            }
        '''),
        defects=[
            Defect("stuck_cursor", "cursor = page.nextCursor ?? cursor;", "high", STUCK_CURSOR),
            Defect("unbounded_buffer", "collected.push(...page.events);", "high", UNBOUNDED_BUFFER),
            Defect("short_page_end", "if (page.events.length < 500) {", "high", SHORT_PAGE),
        ],
    ),
    "go": ReviewCase(
        component="sync_pager",
        language="go",
        difficulty="hard",
        context=PAGER_CONTEXT,
        code=dedent_code('''
            func SyncEvents(client *PartnerClient, wh *Warehouse, tenantID string, since time.Time) (int, error) {
                cursor := ""
                var collected []AuditEvent

                for {
                    page, err := client.ListEvents(tenantID, since, cursor)
                    if err != nil {
                        return 0, err
                    }
                    collected = append(collected, page.Events...)
                    if len(page.Events) < 500 {
                        break
                    }
                    if page.NextCursor != "" {
                        cursor = page.NextCursor
                    }
                }

                return len(collected), wh.Write(collected)
            }
        '''),
        defects=[
            Defect("stuck_cursor", 'if page.NextCursor != "" {', "high", STUCK_CURSOR),
            Defect("unbounded_buffer", "collected = append(collected, page.Events...)", "high", UNBOUNDED_BUFFER),
            Defect("short_page_end", "if len(page.Events) < 500 {", "high", SHORT_PAGE),
        ],
    ),
    "rust": ReviewCase(
        component="sync_pager",
        language="rust",
        difficulty="hard",
        context=PAGER_CONTEXT,
        code=dedent_code('''
            pub fn sync_events(
                client: &PartnerClient,
                warehouse: &Warehouse,
                tenant_id: &str,
                since: i64,
            ) -> usize {
                let mut cursor = String::new();
                let mut collected: Vec<AuditEvent> = Vec::new();

                loop {
                    let page = client.list_events(tenant_id, since, &cursor);
                    collected.extend(page.events.iter().cloned());
                    if page.events.len() < 500 {
                        break;
                    }
                    cursor = page.next_cursor.unwrap_or(cursor);
                }

                warehouse.write(&collected);
                collected.len()
            }
        '''),
        defects=[
            Defect("stuck_cursor", "cursor = page.next_cursor.unwrap_or(cursor);", "high", STUCK_CURSOR),
            Defect("unbounded_buffer", "collected.extend(page.events.iter().cloned());", "high", UNBOUNDED_BUFFER),
            Defect("short_page_end", "if page.events.len() < 500 {", "high", SHORT_PAGE),
        ],
    ),
}


CHARGE_ONCE = {
    "python": ReviewCase(
        component="charge_once",
        language="python",
        difficulty="hard",
        context=CHARGE_CONTEXT,
        code=dedent_code('''
            import logging
            import time

            log = logging.getLogger(__name__)


            def charge_once(db, gateway, customer_id, amount_cents, card_token):
                key = f"{customer_id}:{amount_cents}:{int(time.time())}"
                log.info(
                    "charging customer=%s card=%s amount=%s",
                    customer_id, card_token, amount_cents,
                )

                existing = db.get_charge(key)
                if existing is not None:
                    return existing

                receipt = gateway.charge(card_token, amount_cents)
                db.put_charge(key, receipt)
                return receipt
        '''),
        defects=[
            Defect("unstable_key", 'key = f"{customer_id}:{amount_cents}:{int(time.time())}"', "critical", UNSTABLE_KEY),
            Defect("check_then_act", "existing = db.get_charge(key)", "critical", CHECK_THEN_ACT),
            Defect("leaked_secret", "customer_id, card_token, amount_cents,", "high", LEAKED_SECRET),
        ],
    ),
    "typescript": ReviewCase(
        component="charge_once",
        language="typescript",
        difficulty="hard",
        context=CHARGE_CONTEXT,
        code=dedent_code('''
            export async function chargeOnce(
                db: Db,
                gateway: Gateway,
                customerId: string,
                amountCents: number,
                cardToken: string,
            ): Promise<Receipt> {
                const key = `${customerId}:${amountCents}:${Date.now()}`;
                console.log("charging", { customerId, cardToken, amountCents });

                const existing = await db.getCharge(key);
                if (existing) {
                    return existing;
                }

                const receipt = await gateway.charge(cardToken, amountCents);
                await db.putCharge(key, receipt);
                return receipt;
            }
        '''),
        defects=[
            Defect("unstable_key", "const key = `${customerId}:${amountCents}:${Date.now()}`;", "critical", UNSTABLE_KEY),
            Defect("check_then_act", "const existing = await db.getCharge(key);", "critical", CHECK_THEN_ACT),
            Defect("leaked_secret", 'console.log("charging", { customerId, cardToken, amountCents });', "high", LEAKED_SECRET),
        ],
    ),
    "go": ReviewCase(
        component="charge_once",
        language="go",
        difficulty="hard",
        context=CHARGE_CONTEXT,
        code=dedent_code('''
            func ChargeOnce(db *DB, gw *Gateway, customerID string, amountCents int64, cardToken string) (*Receipt, error) {
                key := fmt.Sprintf("%s:%d:%d", customerID, amountCents, time.Now().Unix())
                log.Printf("charging customer=%s card=%s amount=%d", customerID, cardToken, amountCents)

                existing, err := db.GetCharge(key)
                if err != nil {
                    return nil, err
                }
                if existing != nil {
                    return existing, nil
                }

                receipt, err := gw.Charge(cardToken, amountCents)
                if err != nil {
                    return nil, err
                }
                return receipt, db.PutCharge(key, receipt)
            }
        '''),
        defects=[
            Defect("unstable_key", 'key := fmt.Sprintf("%s:%d:%d", customerID, amountCents, time.Now().Unix())', "critical", UNSTABLE_KEY),
            Defect("check_then_act", "existing, err := db.GetCharge(key)", "critical", CHECK_THEN_ACT),
            Defect("leaked_secret", 'log.Printf("charging customer=%s card=%s amount=%d", customerID, cardToken, amountCents)', "high", LEAKED_SECRET),
        ],
    ),
    "rust": ReviewCase(
        component="charge_once",
        language="rust",
        difficulty="hard",
        context=CHARGE_CONTEXT,
        code=dedent_code('''
            pub fn charge_once(
                db: &Db,
                gateway: &Gateway,
                customer_id: &str,
                amount_cents: i64,
                card_token: &str,
            ) -> Receipt {
                let key = format!("{}:{}:{}", customer_id, amount_cents, now_unix());
                log::info!(
                    "charging customer={} card={} amount={}",
                    customer_id, card_token, amount_cents
                );

                if let Some(existing) = db.get_charge(&key) {
                    return existing;
                }

                let receipt = gateway.charge(card_token, amount_cents);
                db.put_charge(&key, &receipt);
                receipt
            }
        '''),
        defects=[
            Defect("unstable_key", 'let key = format!("{}:{}:{}", customer_id, amount_cents, now_unix());', "critical", UNSTABLE_KEY),
            Defect("check_then_act", "if let Some(existing) = db.get_charge(&key) {", "critical", CHECK_THEN_ACT),
            Defect("leaked_secret", "customer_id, card_token, amount_cents", "high", LEAKED_SECRET),
        ],
    ),
}


READINESS = {
    "python": ReviewCase(
        component="readiness",
        language="python",
        difficulty="hard",
        context=READY_CONTEXT,
        code=dedent_code('''
            _state = {"ready": False}


            def readyz(db):
                if _state["ready"]:
                    return {"status": "ok"}, 200

                try:
                    db.execute("SELECT 1")
                except Exception:
                    return {"status": "ok"}, 200

                _state["ready"] = True
                return {"status": "ok"}, 200
        '''),
        defects=[
            Defect("cached_forever", 'if _state["ready"]:', "high", CACHED_FOREVER),
            Defect("no_timeout", 'db.execute("SELECT 1")', "high", NO_TIMEOUT),
            Defect("fail_open", "except Exception:", "critical", FAIL_OPEN),
        ],
    ),
    "typescript": ReviewCase(
        component="readiness",
        language="typescript",
        difficulty="hard",
        context=READY_CONTEXT,
        code=dedent_code('''
            let ready = false;

            export async function readyz(db: Db, res: Response): Promise<Response> {
                if (ready) {
                    return res.status(200).json({ status: "ok" });
                }

                try {
                    await db.query("SELECT 1");
                } catch (err) {
                    return res.status(200).json({ status: "ok" });
                }

                ready = true;
                return res.status(200).json({ status: "ok" });
            }
        '''),
        defects=[
            Defect("cached_forever", "if (ready) {", "high", CACHED_FOREVER),
            Defect("no_timeout", 'await db.query("SELECT 1");', "high", NO_TIMEOUT),
            Defect("fail_open", "} catch (err) {", "critical", FAIL_OPEN),
        ],
    ),
    "go": ReviewCase(
        component="readiness",
        language="go",
        difficulty="hard",
        context=READY_CONTEXT,
        code=dedent_code('''
            var ready bool

            func Readyz(w http.ResponseWriter, r *http.Request, db *sql.DB) {
                if ready {
                    w.WriteHeader(http.StatusOK)
                    return
                }

                _, err := db.Query("SELECT 1")
                if err != nil {
                    w.WriteHeader(http.StatusOK)
                    return
                }

                ready = true
                w.WriteHeader(http.StatusOK)
            }
        '''),
        defects=[
            Defect("cached_forever", "if ready {", "high", CACHED_FOREVER),
            Defect("no_timeout", '_, err := db.Query("SELECT 1")', "high", NO_TIMEOUT),
            Defect("fail_open", "if err != nil {", "critical", FAIL_OPEN),
        ],
    ),
    "rust": ReviewCase(
        component="readiness",
        language="rust",
        difficulty="hard",
        context=READY_CONTEXT,
        code=dedent_code('''
            static READY: AtomicBool = AtomicBool::new(false);

            pub fn readyz(db: &Db) -> Response {
                if READY.load(Ordering::Relaxed) {
                    return Response::ok();
                }

                match db.query("SELECT 1") {
                    Ok(_) => {}
                    Err(_) => return Response::ok(),
                }

                READY.store(true, Ordering::Relaxed);
                Response::ok()
            }
        '''),
        defects=[
            Defect("cached_forever", "if READY.load(Ordering::Relaxed) {", "high", CACHED_FOREVER),
            Defect("no_timeout", 'match db.query("SELECT 1") {', "high", NO_TIMEOUT),
            Defect("fail_open", "Err(_) => return Response::ok(),", "critical", FAIL_OPEN),
        ],
    ),
}


LIMITER_CONTEXT = (
    "This middleware rate-limits the public API. It is constructed once and "
    "used by every request handler in a multi-threaded server; limits are meant "
    "to be per API client and are configured as requests per minute."
)
CONFIG_CONTEXT = (
    "The service reloads its configuration when SIGHUP arrives, while request "
    "handlers read the same config object concurrently. A bad reload has taken "
    "the fleet down before."
)
WRITER_CONTEXT = (
    "This buffers metric points and ships them to the time-series database. One "
    "instance runs per pod, `record` is called from request handlers, and pods "
    "are recycled on every deploy. Low-traffic pods see a few points a minute."
)
LEASE_CONTEXT = (
    "Exactly one replica must own the migration worker. Each replica claims a "
    "lease row with a 10-second TTL and renews it in this loop. A pod can be "
    "paused by a long GC or descheduled at any moment, and the replicas' clocks "
    "are synced by NTP, which occasionally steps them."
)


TOKEN_BUCKET = {
    "python": ReviewCase(
        component="token_bucket",
        language="python",
        difficulty="hard",
        context=LIMITER_CONTEXT,
        code=dedent_code('''
            import time


            class RateLimiter:
                def __init__(self, per_minute):
                    self.per_minute = per_minute
                    self.buckets = {}

                def allow(self, request):
                    now = time.time()
                    bucket = self.buckets.setdefault(
                        request.path, {"tokens": self.per_minute, "at": now}
                    )
                    refill = int((now - bucket["at"]) / 60) * self.per_minute
                    bucket["tokens"] = min(self.per_minute, bucket["tokens"] + refill)
                    bucket["at"] = now

                    if bucket["tokens"] <= 0:
                        return False
                    bucket["tokens"] -= 1
                    return True
        '''),
        defects=[
            Defect("integer_drift", 'refill = int((now - bucket["at"]) / 60) * self.per_minute', "high", INTEGER_DRIFT),
            Defect("wrong_key", "request.path, {\"tokens\": self.per_minute, \"at\": now}", "critical", WRONG_KEY),
            Defect("data_race", 'bucket["tokens"] -= 1', "high", DATA_RACE),
        ],
    ),
    "typescript": ReviewCase(
        component="token_bucket",
        language="typescript",
        difficulty="hard",
        context=LIMITER_CONTEXT,
        code=dedent_code('''
            type Bucket = { tokens: number; at: number };

            export class RateLimiter {
                private buckets = new Map<string, Bucket>();

                constructor(private perMinute: number) {}

                allow(req: Request): boolean {
                    const now = Date.now() / 1000;
                    let bucket = this.buckets.get(req.path);
                    if (bucket === undefined) {
                        bucket = { tokens: this.perMinute, at: now };
                        this.buckets.set(req.path, bucket);
                    }

                    const refill = Math.floor((now - bucket.at) / 60) * this.perMinute;
                    bucket.tokens = Math.min(this.perMinute, bucket.tokens + refill);
                    bucket.at = now;

                    if (bucket.tokens <= 0) {
                        return false;
                    }
                    bucket.tokens -= 1;
                    return true;
                }
            }
        '''),
        defects=[
            Defect("integer_drift", "const refill = Math.floor((now - bucket.at) / 60) * this.perMinute;", "high", INTEGER_DRIFT),
            Defect("wrong_key", "let bucket = this.buckets.get(req.path);", "critical", WRONG_KEY),
            Defect("never_evicted", "private buckets = new Map<string, Bucket>();", "high", NEVER_EVICTED),
        ],
    ),
    "go": ReviewCase(
        component="token_bucket",
        language="go",
        difficulty="hard",
        context=LIMITER_CONTEXT,
        code=dedent_code('''
            type bucket struct {
                tokens int
                at     time.Time
            }

            type RateLimiter struct {
                perMinute int
                buckets   map[string]*bucket
            }

            func (l *RateLimiter) Allow(r *http.Request) bool {
                now := time.Now()
                b, ok := l.buckets[r.URL.Path]
                if !ok {
                    b = &bucket{tokens: l.perMinute, at: now}
                    l.buckets[r.URL.Path] = b
                }

                refill := int(now.Sub(b.at)/time.Minute) * l.perMinute
                b.tokens = min(l.perMinute, b.tokens+refill)
                b.at = now

                if b.tokens <= 0 {
                    return false
                }
                b.tokens--
                return true
            }
        '''),
        defects=[
            Defect("integer_drift", "refill := int(now.Sub(b.at)/time.Minute) * l.perMinute", "high", INTEGER_DRIFT),
            Defect("wrong_key", "b, ok := l.buckets[r.URL.Path]", "critical", WRONG_KEY),
            Defect("data_race", "buckets   map[string]*bucket", "high", DATA_RACE),
        ],
    ),
    "rust": ReviewCase(
        component="token_bucket",
        language="rust",
        difficulty="hard",
        context=LIMITER_CONTEXT,
        code=dedent_code('''
            struct Bucket {
                tokens: i64,
                at: i64,
            }

            pub struct RateLimiter {
                per_minute: i64,
                buckets: HashMap<String, Bucket>,
            }

            impl RateLimiter {
                pub fn allow(&mut self, req: &Request) -> bool {
                    let now = now_secs();
                    let per_minute = self.per_minute;
                    let bucket = self
                        .buckets
                        .entry(req.path.clone())
                        .or_insert(Bucket { tokens: per_minute, at: now });

                    let refill = ((now - bucket.at) / 60) * per_minute;
                    bucket.tokens = per_minute.min(bucket.tokens + refill);
                    bucket.at = now;

                    if bucket.tokens <= 0 {
                        return false;
                    }
                    bucket.tokens -= 1;
                    true
                }
            }
        '''),
        defects=[
            Defect("integer_drift", "let refill = ((now - bucket.at) / 60) * per_minute;", "high", INTEGER_DRIFT),
            Defect("wrong_key", ".entry(req.path.clone())", "critical", WRONG_KEY),
            Defect("never_evicted", "buckets: HashMap<String, Bucket>,", "high", NEVER_EVICTED),
        ],
    ),
}


CONFIG_RELOAD = {
    "python": ReviewCase(
        component="config_reload",
        language="python",
        difficulty="hard",
        context=CONFIG_CONTEXT,
        code=dedent_code('''
            import json

            CONFIG = {}


            def reload_config(path):
                try:
                    parsed = json.loads(open(path).read())
                except Exception:
                    return

                CONFIG.clear()
                for key, value in parsed.items():
                    CONFIG[key] = value
        '''),
        defects=[
            Defect("torn_config", "CONFIG.clear()", "critical", TORN_CONFIG),
            Defect("no_validation", "CONFIG[key] = value", "high", NO_VALIDATION),
            Defect("swallowed_error", "except Exception:", "high", SWALLOWED_ERROR),
        ],
    ),
    "typescript": ReviewCase(
        component="config_reload",
        language="typescript",
        difficulty="hard",
        context=CONFIG_CONTEXT,
        code=dedent_code('''
            import { readFileSync } from "fs";

            export const config: Record<string, unknown> = {};

            export function reloadConfig(path: string): void {
                let parsed: Record<string, unknown>;
                try {
                    parsed = JSON.parse(readFileSync(path, "utf8"));
                } catch (err) {
                    return;
                }

                for (const key of Object.keys(config)) {
                    delete config[key];
                }
                for (const [key, value] of Object.entries(parsed)) {
                    config[key] = value;
                }
            }
        '''),
        defects=[
            Defect("torn_config", "delete config[key];", "critical", TORN_CONFIG),
            Defect("no_validation", "config[key] = value;", "high", NO_VALIDATION),
            Defect("swallowed_error", "} catch (err) {", "high", SWALLOWED_ERROR),
        ],
    ),
    "go": ReviewCase(
        component="config_reload",
        language="go",
        difficulty="hard",
        context=CONFIG_CONTEXT,
        code=dedent_code('''
            var Config = map[string]string{}

            func ReloadConfig(path string) {
                raw, err := os.ReadFile(path)
                if err != nil {
                    return
                }

                parsed := map[string]string{}
                if err := json.Unmarshal(raw, &parsed); err != nil {
                    return
                }

                for k := range Config {
                    delete(Config, k)
                }
                for k, v := range parsed {
                    Config[k] = v
                }
            }
        '''),
        defects=[
            Defect("torn_config", "delete(Config, k)", "critical", TORN_CONFIG),
            Defect("no_validation", "Config[k] = v", "high", NO_VALIDATION),
            Defect("swallowed_error", "if err := json.Unmarshal(raw, &parsed); err != nil {", "high", SWALLOWED_ERROR),
        ],
    ),
    "rust": ReviewCase(
        component="config_reload",
        language="rust",
        difficulty="hard",
        context=CONFIG_CONTEXT,
        code=dedent_code('''
            pub fn reload_config(path: &str, config: &mut HashMap<String, String>) {
                let parsed: HashMap<String, String> = match fs::read_to_string(path) {
                    Ok(raw) => serde_json::from_str(&raw).unwrap_or_default(),
                    Err(_) => return,
                };

                config.clear();
                for (key, value) in parsed {
                    config.insert(key, value);
                }
            }
        '''),
        defects=[
            Defect("torn_config", "config.clear();", "critical", TORN_CONFIG),
            Defect("no_validation", "config.insert(key, value);", "high", NO_VALIDATION),
            Defect("swallowed_error", "Ok(raw) => serde_json::from_str(&raw).unwrap_or_default(),", "high", SWALLOWED_ERROR),
        ],
    ),
}


BATCH_WRITER = {
    "python": ReviewCase(
        component="batch_writer",
        language="python",
        difficulty="hard",
        context=WRITER_CONTEXT,
        code=dedent_code('''
            class MetricWriter:
                def __init__(self, client, batch_size=500):
                    self.client = client
                    self.batch_size = batch_size
                    self.buffer = []

                def record(self, point):
                    self.buffer.append(point)
                    if len(self.buffer) >= self.batch_size:
                        self.flush()

                def flush(self):
                    batch = self.buffer
                    self.buffer = []
                    self.client.write(batch)

                def close(self):
                    self.client.close()
        '''),
        defects=[
            Defect("no_time_flush", "if len(self.buffer) >= self.batch_size:", "high", NO_TIME_FLUSH),
            Defect("cleared_before_write", "self.client.write(batch)", "high", CLEARED_BEFORE_WRITE),
            Defect("no_shutdown_flush", "self.client.close()", "high", NO_SHUTDOWN_FLUSH),
        ],
    ),
    "typescript": ReviewCase(
        component="batch_writer",
        language="typescript",
        difficulty="hard",
        context=WRITER_CONTEXT,
        code=dedent_code('''
            export class MetricWriter {
                private buffer: Point[] = [];

                constructor(private client: TsdbClient, private batchSize = 500) {}

                record(point: Point): void {
                    this.buffer.push(point);
                    if (this.buffer.length >= this.batchSize) {
                        void this.flush();
                    }
                }

                async flush(): Promise<void> {
                    const batch = this.buffer;
                    this.buffer = [];
                    await this.client.write(batch);
                }

                async close(): Promise<void> {
                    await this.client.close();
                }
            }
        '''),
        defects=[
            Defect("no_time_flush", "if (this.buffer.length >= this.batchSize) {", "high", NO_TIME_FLUSH),
            Defect("cleared_before_write", "this.buffer = [];", "high", CLEARED_BEFORE_WRITE),
            Defect("no_shutdown_flush", "await this.client.close();", "high", NO_SHUTDOWN_FLUSH),
        ],
    ),
    "go": ReviewCase(
        component="batch_writer",
        language="go",
        difficulty="hard",
        context=WRITER_CONTEXT,
        code=dedent_code('''
            type MetricWriter struct {
                client    *TSDBClient
                batchSize int
                buffer    []Point
            }

            func (w *MetricWriter) Record(p Point) {
                w.buffer = append(w.buffer, p)
                if len(w.buffer) >= w.batchSize {
                    w.Flush()
                }
            }

            func (w *MetricWriter) Flush() {
                batch := w.buffer
                w.buffer = nil
                w.client.Write(batch)
            }

            func (w *MetricWriter) Close() error {
                return w.client.Close()
            }
        '''),
        defects=[
            Defect("no_time_flush", "if len(w.buffer) >= w.batchSize {", "high", NO_TIME_FLUSH),
            Defect("cleared_before_write", "w.buffer = nil", "high", CLEARED_BEFORE_WRITE),
            Defect("no_shutdown_flush", "return w.client.Close()", "high", NO_SHUTDOWN_FLUSH),
        ],
    ),
    "rust": ReviewCase(
        component="batch_writer",
        language="rust",
        difficulty="hard",
        context=WRITER_CONTEXT,
        code=dedent_code('''
            pub struct MetricWriter {
                client: TsdbClient,
                batch_size: usize,
                buffer: Vec<Point>,
            }

            impl MetricWriter {
                pub fn record(&mut self, point: Point) {
                    self.buffer.push(point);
                    if self.buffer.len() >= self.batch_size {
                        self.flush();
                    }
                }

                pub fn flush(&mut self) {
                    let batch = std::mem::take(&mut self.buffer);
                    self.client.write(&batch);
                }

                pub fn close(&mut self) {
                    self.client.close();
                }
            }
        '''),
        defects=[
            Defect("no_time_flush", "if self.buffer.len() >= self.batch_size {", "high", NO_TIME_FLUSH),
            Defect("cleared_before_write", "let batch = std::mem::take(&mut self.buffer);", "high", CLEARED_BEFORE_WRITE),
            Defect("no_shutdown_flush", "self.client.close();", "high", NO_SHUTDOWN_FLUSH),
        ],
    ),
}


LEASE_RENEW = {
    "python": ReviewCase(
        component="lease_renew",
        language="python",
        difficulty="hard",
        context=LEASE_CONTEXT,
        code=dedent_code('''
            import time
            from datetime import datetime, timedelta

            LEASE_TTL_SECONDS = 10


            def run_as_leader(db, node_id, do_work):
                while True:
                    expires_at = datetime.now() + timedelta(seconds=LEASE_TTL_SECONDS)
                    if not db.upsert_lease(node_id, expires_at):
                        time.sleep(1)
                        continue

                    do_work()
                    time.sleep(LEASE_TTL_SECONDS)
        '''),
        defects=[
            Defect("lease_margin", "time.sleep(LEASE_TTL_SECONDS)", "critical", LEASE_MARGIN),
            Defect("no_fencing", "do_work()", "critical", NO_FENCING),
            Defect("wall_clock", "expires_at = datetime.now() + timedelta(seconds=LEASE_TTL_SECONDS)", "high", WALL_CLOCK),
        ],
    ),
    "typescript": ReviewCase(
        component="lease_renew",
        language="typescript",
        difficulty="hard",
        context=LEASE_CONTEXT,
        code=dedent_code('''
            const LEASE_TTL_MS = 10_000;

            export async function runAsLeader(db: Db, nodeId: string, doWork: () => Promise<void>) {
                while (true) {
                    const expiresAt = new Date(Date.now() + LEASE_TTL_MS);
                    if (!(await db.upsertLease(nodeId, expiresAt))) {
                        await sleep(1000);
                        continue;
                    }

                    await doWork();
                    await sleep(LEASE_TTL_MS);
                }
            }
        '''),
        defects=[
            Defect("lease_margin", "await sleep(LEASE_TTL_MS);", "critical", LEASE_MARGIN),
            Defect("no_fencing", "await doWork();", "critical", NO_FENCING),
            Defect("wall_clock", "const expiresAt = new Date(Date.now() + LEASE_TTL_MS);", "high", WALL_CLOCK),
        ],
    ),
    "go": ReviewCase(
        component="lease_renew",
        language="go",
        difficulty="hard",
        context=LEASE_CONTEXT,
        code=dedent_code('''
            const leaseTTL = 10 * time.Second

            func RunAsLeader(db *DB, nodeID string, doWork func()) {
                for {
                    expiresAt := time.Now().Add(leaseTTL)
                    ok, err := db.UpsertLease(nodeID, expiresAt)
                    if err != nil || !ok {
                        time.Sleep(time.Second)
                        continue
                    }

                    doWork()
                    time.Sleep(leaseTTL)
                }
            }
        '''),
        defects=[
            Defect("lease_margin", "time.Sleep(leaseTTL)", "critical", LEASE_MARGIN),
            Defect("no_fencing", "doWork()", "critical", NO_FENCING),
            Defect("wall_clock", "expiresAt := time.Now().Add(leaseTTL)", "high", WALL_CLOCK),
        ],
    ),
    "rust": ReviewCase(
        component="lease_renew",
        language="rust",
        difficulty="hard",
        context=LEASE_CONTEXT,
        code=dedent_code('''
            const LEASE_TTL: Duration = Duration::from_secs(10);

            pub fn run_as_leader(db: &Db, node_id: &str, do_work: impl Fn()) {
                loop {
                    let expires_at = SystemTime::now() + LEASE_TTL;
                    if !db.upsert_lease(node_id, expires_at) {
                        thread::sleep(Duration::from_secs(1));
                        continue;
                    }

                    do_work();
                    thread::sleep(LEASE_TTL);
                }
            }
        '''),
        defects=[
            Defect("lease_margin", "thread::sleep(LEASE_TTL);", "critical", LEASE_MARGIN),
            Defect("no_fencing", "do_work();", "critical", NO_FENCING),
            Defect("wall_clock", "let expires_at = SystemTime::now() + LEASE_TTL;", "high", WALL_CLOCK),
        ],
    ),
}


WEBHOOK_CONTEXT = (
    "This verifies incoming webhooks from our payment provider. The endpoint is "
    "public, the shared secret is long-lived, and the provider sends the "
    "signature in X-Signature and the send time in X-Timestamp."
)
BREAKER_CONTEXT = (
    "This breaker guards calls to the recommendations service from every request "
    "handler in a multi-threaded server. It is meant to trip after five "
    "consecutive dependency failures and, once the cool-off has passed, let a "
    "single probe through before closing again."
)
UPLOAD_CONTEXT = (
    "This endpoint accepts avatar uploads from authenticated users and stores "
    "them on a shared volume that the web server also serves files from. The "
    "filename comes from the multipart form and the body is whatever the client "
    "sends."
)


WEBHOOK_VERIFY = {
    "python": ReviewCase(
        component="webhook_verify",
        language="python",
        difficulty="hard",
        context=WEBHOOK_CONTEXT,
        code=dedent_code('''
            import hashlib
            import hmac


            def verify_webhook(secret, headers, body):
                signature = headers.get("X-Signature", "")
                expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

                if not signature:
                    return True

                return signature == expected
        '''),
        defects=[
            Defect("no_replay_protection", 'signature = headers.get("X-Signature", "")', "high", REPLAY),
            Defect("missing_signature", "if not signature:", "critical", MISSING_SIGNATURE),
            Defect("timing_attack", "return signature == expected", "high", TIMING_ATTACK),
        ],
    ),
    "typescript": ReviewCase(
        component="webhook_verify",
        language="typescript",
        difficulty="hard",
        context=WEBHOOK_CONTEXT,
        code=dedent_code('''
            import { createHmac } from "crypto";

            export function verifyWebhook(
                secret: string,
                headers: Record<string, string>,
                body: string,
            ): boolean {
                const signature = headers["x-signature"] ?? "";
                const expected = createHmac("sha256", secret).update(body).digest("hex");

                if (signature === "") {
                    return true;
                }

                return signature === expected;
            }
        '''),
        defects=[
            Defect("no_replay_protection", 'const signature = headers["x-signature"] ?? "";', "high", REPLAY),
            Defect("missing_signature", 'if (signature === "") {', "critical", MISSING_SIGNATURE),
            Defect("timing_attack", "return signature === expected;", "high", TIMING_ATTACK),
        ],
    ),
    "go": ReviewCase(
        component="webhook_verify",
        language="go",
        difficulty="hard",
        context=WEBHOOK_CONTEXT,
        code=dedent_code('''
            func VerifyWebhook(secret string, headers http.Header, body []byte) bool {
                signature := headers.Get("X-Signature")

                mac := hmac.New(sha256.New, []byte(secret))
                mac.Write(body)
                expected := hex.EncodeToString(mac.Sum(nil))

                if signature == "" {
                    return true
                }

                return signature == expected
            }
        '''),
        defects=[
            Defect("no_replay_protection", 'signature := headers.Get("X-Signature")', "high", REPLAY),
            Defect("missing_signature", 'if signature == "" {', "critical", MISSING_SIGNATURE),
            Defect("timing_attack", "return signature == expected", "high", TIMING_ATTACK),
        ],
    ),
    "rust": ReviewCase(
        component="webhook_verify",
        language="rust",
        difficulty="hard",
        context=WEBHOOK_CONTEXT,
        code=dedent_code('''
            pub fn verify_webhook(
                secret: &str,
                headers: &HashMap<String, String>,
                body: &[u8],
            ) -> bool {
                let signature = headers.get("x-signature").cloned().unwrap_or_default();
                let expected = hex::encode(hmac_sha256(secret.as_bytes(), body));

                if signature.is_empty() {
                    return true;
                }

                signature == expected
            }
        '''),
        defects=[
            Defect("no_replay_protection", 'let signature = headers.get("x-signature").cloned().unwrap_or_default();', "high", REPLAY),
            Defect("missing_signature", "if signature.is_empty() {", "critical", MISSING_SIGNATURE),
            Defect("timing_attack", "signature == expected", "high", TIMING_ATTACK),
        ],
    ),
}


CIRCUIT_BREAKER = {
    "python": ReviewCase(
        component="circuit_breaker",
        language="python",
        difficulty="hard",
        context=BREAKER_CONTEXT,
        code=dedent_code('''
            import time


            class CircuitBreaker:
                def __init__(self, threshold=5, cooloff=30):
                    self.threshold = threshold
                    self.cooloff = cooloff
                    self.failures = 0
                    self.opened_at: float | None = None

                def call(self, fn):
                    if self.opened_at is not None:
                        if time.time() - self.opened_at < self.cooloff:
                            raise CircuitOpen()
                        self.opened_at = None

                    try:
                        result = fn()
                    except DependencyError:
                        self.failures += 1
                        if self.failures >= self.threshold:
                            self.opened_at = time.time()
                        raise
                    return result
        '''),
        defects=[
            Defect("half_open_flood", "self.opened_at = None", "high", HALF_OPEN_FLOOD),
            Defect("never_resets", "return result", "high", NEVER_RESETS),
            Defect("data_race", "self.failures += 1", "high", DATA_RACE),
        ],
    ),
    "typescript": ReviewCase(
        component="circuit_breaker",
        language="typescript",
        difficulty="hard",
        context=BREAKER_CONTEXT,
        code=dedent_code('''
            export class CircuitBreaker {
                private failures = 0;
                private openedAt: number | null = null;

                constructor(private threshold = 5, private cooloffMs = 30_000) {}

                async call<T>(fn: () => Promise<T>): Promise<T> {
                    if (this.openedAt !== null) {
                        if (Date.now() - this.openedAt < this.cooloffMs) {
                            throw new CircuitOpenError();
                        }
                        this.openedAt = null;
                    }

                    try {
                        return await fn();
                    } catch (err) {
                        this.failures += 1;
                        if (this.failures >= this.threshold) {
                            this.openedAt = Date.now();
                        }
                        throw err;
                    }
                }
            }
        '''),
        defects=[
            Defect("half_open_flood", "this.openedAt = null;", "high", HALF_OPEN_FLOOD),
            Defect("never_resets", "return await fn();", "high", NEVER_RESETS),
            Defect("overbroad_catch", "} catch (err) {", "high", OVERBROAD_CATCH),
        ],
    ),
    "go": ReviewCase(
        component="circuit_breaker",
        language="go",
        difficulty="hard",
        context=BREAKER_CONTEXT,
        code=dedent_code('''
            type CircuitBreaker struct {
                threshold int
                cooloff   time.Duration
                failures  int
                openedAt  time.Time
            }

            func (b *CircuitBreaker) Call(fn func() error) error {
                if !b.openedAt.IsZero() {
                    if time.Since(b.openedAt) < b.cooloff {
                        return ErrCircuitOpen
                    }
                    b.openedAt = time.Time{}
                }

                if err := fn(); err != nil {
                    b.failures++
                    if b.failures >= b.threshold {
                        b.openedAt = time.Now()
                    }
                    return err
                }
                return nil
            }
        '''),
        defects=[
            Defect("half_open_flood", "b.openedAt = time.Time{}", "high", HALF_OPEN_FLOOD),
            Defect("never_resets", "return nil", "high", NEVER_RESETS),
            Defect("data_race", "b.failures++", "high", DATA_RACE),
        ],
    ),
    "rust": ReviewCase(
        component="circuit_breaker",
        language="rust",
        difficulty="hard",
        context=BREAKER_CONTEXT,
        code=dedent_code('''
            pub struct CircuitBreaker {
                threshold: u32,
                cooloff: Duration,
                failures: u32,
                opened_at: Option<Instant>,
            }

            impl CircuitBreaker {
                pub fn call<T>(&mut self, f: impl FnOnce() -> Result<T, Error>) -> Result<T, Error> {
                    if let Some(opened_at) = self.opened_at {
                        if opened_at.elapsed() < self.cooloff {
                            return Err(Error::CircuitOpen);
                        }
                        self.opened_at = None;
                    }

                    match f() {
                        Ok(value) => Ok(value),
                        Err(err) => {
                            self.failures += 1;
                            if self.failures >= self.threshold {
                                self.opened_at = Some(Instant::now());
                            }
                            Err(err)
                        }
                    }
                }
            }
        '''),
        defects=[
            Defect("half_open_flood", "self.opened_at = None;", "high", HALF_OPEN_FLOOD),
            Defect("never_resets", "Ok(value) => Ok(value),", "high", NEVER_RESETS),
            Defect("overbroad_catch", "Err(err) => {", "high", OVERBROAD_CATCH),
        ],
    ),
}


UPLOAD_HANDLER = {
    "python": ReviewCase(
        component="upload_handler",
        language="python",
        difficulty="hard",
        context=UPLOAD_CONTEXT,
        code=dedent_code('''
            import os

            UPLOAD_DIR = "/srv/avatars"


            def handle_upload(request):
                filename = request.form["filename"]
                target = os.path.join(UPLOAD_DIR, filename)

                data = request.stream.read()

                handle = open(target, "wb")
                handle.write(data)
                handle.close()
                return {"path": target}
        '''),
        defects=[
            Defect("path_traversal", "target = os.path.join(UPLOAD_DIR, filename)", "critical", PATH_TRAVERSAL),
            Defect("unbounded_read", "data = request.stream.read()", "high", UNBOUNDED_READ),
            Defect("handle_leak", 'handle = open(target, "wb")', "medium", HANDLE_LEAK),
        ],
    ),
    "typescript": ReviewCase(
        component="upload_handler",
        language="typescript",
        difficulty="hard",
        context=UPLOAD_CONTEXT,
        code=dedent_code('''
            import * as path from "path";
            import { promises as fs } from "fs";

            const UPLOAD_DIR = "/srv/avatars";

            export async function handleUpload(req: Request): Promise<{ path: string }> {
                const filename = req.body.filename as string;
                const target = path.join(UPLOAD_DIR, filename);

                const data = await readEntireBody(req);

                const handle = await fs.open(target, "w");
                await handle.write(data);
                await handle.close();
                return { path: target };
            }
        '''),
        defects=[
            Defect("path_traversal", "const target = path.join(UPLOAD_DIR, filename);", "critical", PATH_TRAVERSAL),
            Defect("unbounded_read", "const data = await readEntireBody(req);", "high", UNBOUNDED_READ),
            Defect("handle_leak", 'const handle = await fs.open(target, "w");', "medium", HANDLE_LEAK),
        ],
    ),
    "go": ReviewCase(
        component="upload_handler",
        language="go",
        difficulty="hard",
        context=UPLOAD_CONTEXT,
        code=dedent_code('''
            const uploadDir = "/srv/avatars"

            func HandleUpload(w http.ResponseWriter, r *http.Request) {
                filename := r.FormValue("filename")
                target := filepath.Join(uploadDir, filename)

                data, err := io.ReadAll(r.Body)
                if err != nil {
                    http.Error(w, "bad request", http.StatusBadRequest)
                    return
                }

                f, err := os.Create(target)
                if err != nil {
                    http.Error(w, "server error", http.StatusInternalServerError)
                    return
                }
                f.Write(data)
                f.Close()
            }
        '''),
        defects=[
            Defect("path_traversal", "target := filepath.Join(uploadDir, filename)", "critical", PATH_TRAVERSAL),
            Defect("unbounded_read", "data, err := io.ReadAll(r.Body)", "high", UNBOUNDED_READ),
            Defect("handle_leak", "f.Close()", "medium", HANDLE_LEAK),
        ],
    ),
    "rust": ReviewCase(
        component="upload_handler",
        language="rust",
        difficulty="hard",
        context=UPLOAD_CONTEXT,
        code=dedent_code('''
            const UPLOAD_DIR: &str = "/srv/avatars";

            pub fn handle_upload(req: &mut Request) -> Result<String, Error> {
                let filename = req.form_value("filename");
                let target = Path::new(UPLOAD_DIR).join(&filename);

                let mut data = Vec::new();
                req.body().read_to_end(&mut data)?;

                let mut file = File::create(&target)?;
                file.write_all(&data)?;
                Ok(target.display().to_string())
            }
        '''),
        defects=[
            Defect("path_traversal", "let target = Path::new(UPLOAD_DIR).join(&filename);", "critical", PATH_TRAVERSAL),
            Defect("unbounded_read", "req.body().read_to_end(&mut data)?;", "high", UNBOUNDED_READ),
            Defect("partial_file", "file.write_all(&data)?;", "medium", HANDLE_LEAK),
        ],
    ),
}


ADVANCED_COMPONENTS = [
    SYNC_PAGER,
    CHARGE_ONCE,
    READINESS,
    TOKEN_BUCKET,
    CONFIG_RELOAD,
    BATCH_WRITER,
    LEASE_RENEW,
    WEBHOOK_VERIFY,
    CIRCUIT_BREAKER,
    UPLOAD_HANDLER,
]
