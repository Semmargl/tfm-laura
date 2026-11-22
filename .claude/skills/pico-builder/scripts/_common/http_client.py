"""Polite, capped, caching HTTP client for the free APIs (NFR-05, NFR-08, W2-3).

* host allow-list (E-utilities, Crossref, OpenAlex, ClinicalTrials.gov v2, Europe PMC, doi.org);
* per-host rate limit, per-run caps (CapExceeded), warn-after-N (NeedsConfirmation);
* backoff on 429/5xx (honours Retry-After), network errors -> NetworkError (=> degrade to LITE-a);
* every real response is stored write-once in raw/api/<sha1(query_key|date)>.json as an envelope with
  metadata {url, status, ts, sha256, ...}; integrity.py treats only such files as API provenance.
`transport` and `sleep` are injectable so tests never touch the network.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config, paths, rawstore

CLIENT_NAME = "tfm-http_client/1.0"
ENVELOPE_SCHEMA = "tfm-api-cache/v1"
META_KEYS = ("url", "query_key", "status", "ts", "date", "sha256", "host", "client")
_NON_IDENTITY = {"mailto", "email", "tool", "api_key", "api-key"}

HOSTS = {
    "eutils.ncbi.nlm.nih.gov": {"group": "eutils", "min_interval": 0.4, "polite": "eutils"},
    "api.crossref.org": {"group": "crossref", "min_interval": 0.2, "polite": "mailto"},
    "api.openalex.org": {"group": "openalex", "min_interval": 0.1, "polite": "mailto"},
    "clinicaltrials.gov": {"group": "clinicaltrials", "min_interval": 1.3, "polite": None},
    "www.ebi.ac.uk": {"group": "europepmc", "min_interval": 0.2, "polite": None},
    "doi.org": {"group": "crossref", "min_interval": 0.2, "polite": None},
}


class HttpError(RuntimeError):
    def __init__(self, status, url):
        self.status, self.url = status, url
        RuntimeError.__init__(self, "HTTP %s for %s" % (status, url))


class NetworkError(RuntimeError):
    """Network unreachable / timeout after retries -> callers degrade FULL -> LITE-a."""


class CapExceeded(RuntimeError):
    pass


class NeedsConfirmation(RuntimeError):
    """More than warn_after real requests: ask Laura, then rerun with confirmed=True / --confirmed."""


class HostNotAllowed(RuntimeError):
    pass


class Response(object):
    def __init__(self, url, status, text, ts, sha256, from_cache, path, rel_path, content_type, query_key, date):
        self.url, self.status, self.text, self.ts, self.sha256 = url, status, text, ts, sha256
        self.from_cache, self.path, self.rel_path = from_cache, path, rel_path
        self.content_type, self.query_key, self.date = content_type, query_key, date

    @property
    def ok(self):
        return 200 <= self.status < 300

    def json(self):
        return json.loads(self.text)

    def meta(self):
        return {"url": self.url, "status": self.status, "ts": self.ts, "sha256": self.sha256,
                "rel_path": self.rel_path, "from_cache": self.from_cache}


def query_key(url: str, params=None) -> str:
    """Canonical identity of a query (sorted params, polite/identity-free params removed)."""
    parts = urllib.parse.urlsplit(url)
    pairs = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    pairs += list((params or {}).items()) if isinstance(params, dict) else list(params or [])
    pairs = sorted((str(k), str(v)) for k, v in pairs if str(k).lower() not in _NON_IDENTITY)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, urllib.parse.urlencode(pairs), ""))


def verify_envelope(path) -> tuple:
    """(ok, reason) for a raw/api file: valid envelope, mandatory metadata, body hash matches (W2-3)."""
    try:
        data = json.loads(paths.read_text(path))
    except (ValueError, OSError) as e:
        return False, "no es JSON: %s" % e
    if not isinstance(data, dict) or data.get("schema") != ENVELOPE_SCHEMA:
        return False, "sin sobre %s" % ENVELOPE_SCHEMA
    meta, body = data.get("_meta"), data.get("body")
    if not isinstance(meta, dict) or not isinstance(body, str):
        return False, "faltan _meta/body"
    miss = [k for k in META_KEYS if k not in meta]
    if miss:
        return False, "metadatos incompletos: %s" % miss
    if not isinstance(meta["status"], int) or not str(meta["url"]).startswith("http"):
        return False, "status/url invalidos"
    if paths.sha256_bytes(body.encode("utf-8")) != meta["sha256"]:
        return False, "sha256 del cuerpo no coincide"
    return True, "ok"


def _default_transport(method, url, headers, timeout):
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers.items()), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers.items()) if e.headers else {}, e.read() or b""
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise NetworkError(str(e))


class HttpClient(object):
    def __init__(self, root, email=None, caps=None, warn_after=None, confirmed=False, transport=None,
                 sleep=None, clock=None, use_cache=True, timeout=30, max_retries=4):
        self.root = paths.Paths(root).root
        cfg = config.load_config(self.root)
        self.email = email if email is not None else (cfg.get("email") or "")
        c = cfg["caps"]
        self.caps = {"eutils": c["eutils_per_run"], "crossref": c["crossref_per_run"], "openalex": c["openalex_per_run"],
                     "clinicaltrials": c["clinicaltrials_per_run"], "europepmc": c["europepmc_per_run"]}
        self.caps.update(caps or {})
        self.warn_after = c["warn_after"] if warn_after is None else warn_after
        self.confirmed = confirmed
        self.transport = transport or _default_transport
        self.sleep = sleep or time.sleep
        self.clock = clock or time.monotonic
        self.use_cache = use_cache
        self.timeout, self.max_retries = timeout, max_retries
        self.counts = {}      # real network requests per group
        self.cache_hits = 0
        self.errors_429 = 0
        self._last = {}

    # ---- stats -------------------------------------------------------------
    def total_requests(self) -> int:
        return sum(self.counts.values())

    def stats(self) -> dict:
        return {"requests": dict(self.counts), "total": self.total_requests(), "cache_hits": self.cache_hits,
                "http_429": self.errors_429}

    # ---- cache -------------------------------------------------------------
    def _cache_name(self, qk, date, n=1):
        h = hashlib.sha1((qk + "|" + date).encode("utf-8")).hexdigest()
        return "raw/api/%s%s.json" % (h, "" if n == 1 else "-r%d" % n)

    def cached_entries(self, qk: str) -> list:
        """All stored responses for a query_key, oldest first (for the 'within 1 h or = cache' check, W-3)."""
        out = []
        d = paths.Paths(self.root).raw_api
        if not d.is_dir():
            return out
        for p in sorted(d.glob("*.json")):
            ok, _ = verify_envelope(p)
            if not ok:
                continue
            data = json.loads(paths.read_text(p))
            if data["_meta"]["query_key"] == qk:
                out.append(self._from_envelope(p, data, True))
        out.sort(key=lambda r: r.ts)
        return out

    def _from_envelope(self, p, data, from_cache):
        m = data["_meta"]
        return Response(m["url"], m["status"], data["body"], m["ts"], m["sha256"], from_cache, p,
                        paths.rel(self.root, p), m.get("content_type", ""), m["query_key"], m["date"])

    def _store(self, qk, url, status, text, ctype, ts, host):
        date = ts[:10]
        n = 1
        while paths.safe_join(self.root, self._cache_name(qk, date, n)).exists():
            n += 1                                   # write-once: a refresh gets -rN, never overwrites
        rel_path = self._cache_name(qk, date, n)
        meta = {"url": url, "query_key": qk, "status": status, "ts": ts, "date": date,
                "sha256": paths.sha256_bytes(text.encode("utf-8")), "content_type": ctype, "host": host,
                "client": CLIENT_NAME, "bytes": len(text.encode("utf-8"))}
        env = {"schema": ENVELOPE_SCHEMA, "_meta": meta, "body": text}
        rawstore.save_new(self.root, rel_path, (json.dumps(env, ensure_ascii=False, indent=1) + "\n").encode("utf-8"),
                          "script", "api")
        p = paths.safe_join(self.root, rel_path)
        return Response(url, status, text, ts, meta["sha256"], False, p, rel_path, ctype, qk, date)

    # ---- request -----------------------------------------------------------
    def _polite(self, info, params):
        p = dict(params or {})
        if info["polite"] == "mailto" and self.email:
            p.setdefault("mailto", self.email)
        elif info["polite"] == "eutils":
            p.setdefault("tool", "tfm_laura")
            if self.email:
                p.setdefault("email", self.email)
        return p

    def get(self, url, params=None, cache="day", max_age_s=None, accept=(200,), headers=None) -> Response:
        """GET with cache policy: 'day' (reuse today's stored response), 'refresh' (always fetch, store -rN),
        'any' (reuse latest stored response of any date), 'none' (no cache read/write).
        max_age_s: reuse the latest stored response if younger than this many seconds (W-3: repeat within 1 h)."""
        host = urllib.parse.urlsplit(url).netloc.lower()
        info = HOSTS.get(host)
        if info is None:
            raise HostNotAllowed("host no permitido (solo APIs gratuitas del proyecto): %s" % host)
        qk = query_key(url, params)
        use_cache = self.use_cache and cache != "none"
        if use_cache and cache != "refresh":
            entries = self.cached_entries(qk)
            if entries:
                last = entries[-1]
                if cache == "any" or (cache == "day" and last.date == paths.today() and max_age_s is None) or \
                        (max_age_s is not None and _age_s(last.ts) <= max_age_s):
                    self.cache_hits += 1
                    return last
        grp = info["group"]
        if self.counts.get(grp, 0) >= self.caps.get(grp, 10 ** 9):
            raise CapExceeded("tope de %d peticiones a %s alcanzado en esta ejecucion" % (self.caps[grp], grp))
        if self.total_requests() >= self.warn_after and not self.confirmed:
            raise NeedsConfirmation("ya van %d peticiones (aviso a partir de %d): pedir confirmacion a Laura"
                                    % (self.total_requests(), self.warn_after))
        full_params = self._polite(info, params)
        full_url = url + (("&" if "?" in url else "?") + urllib.parse.urlencode(full_params) if full_params else "")
        hdrs = {"User-Agent": "TFM-Laura/1.0 (mailto:%s)" % (self.email or "no-email"), "Accept": "*/*"}
        hdrs.update(headers or {})
        status, rheaders, body = self._fetch(full_url, hdrs, info, grp)
        ctype = (rheaders or {}).get("Content-Type", (rheaders or {}).get("content-type", ""))
        text = body.decode("utf-8", errors="replace")
        ts = paths.utc_now()
        if status not in accept:
            raise HttpError(status, full_url)
        if use_cache:
            return self._store(qk, full_url, status, text, ctype, ts, host)
        return Response(full_url, status, text, ts, paths.sha256_bytes(text.encode("utf-8")), False, None, None, ctype, qk, ts[:10])

    def _fetch(self, url, hdrs, info, grp):
        attempt = 0
        while True:
            wait = info["min_interval"] - (self.clock() - self._last.get(grp, -1e9))
            if wait > 0:
                self.sleep(wait)
            self._last[grp] = self.clock()
            self.counts[grp] = self.counts.get(grp, 0) + 1
            try:
                status, rh, body = self.transport("GET", url, hdrs, self.timeout)
            except NetworkError:
                if attempt >= self.max_retries:
                    raise
                status, rh, body = None, {}, b""
            if status is not None and status != 429 and status < 500:
                return status, rh, body
            if status == 429:
                self.errors_429 += 1
            if attempt >= self.max_retries:
                if status is None:
                    raise NetworkError("sin respuesta de %s tras %d intentos" % (url, attempt + 1))
                raise HttpError(status, url)
            ra = (rh or {}).get("Retry-After") or (rh or {}).get("retry-after")
            try:
                delay = min(float(ra), 60.0) if ra else min(2.0 ** attempt, 30.0)
            except ValueError:
                delay = min(2.0 ** attempt, 30.0)
            self.sleep(delay)
            attempt += 1


def _age_s(ts: str) -> float:
    import datetime as dt
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return (dt.datetime.strptime(paths.utc_now(), fmt) - dt.datetime.strptime(ts, fmt)).total_seconds()
