#!/usr/bin/env python3
"""WHAT THIS REPOSITORY'S CLOUDFLARE TOKEN CAN DO FOR THE GLOBAL CACHE (the
library's row 724; the owner, 11-02: the pulse's promotion moves off
CACHE_TOKEN onto the existing CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID,
no new token).

The cache is the library's Worker (ops/cache): an R2 bucket `cache`, a D1
first-writer ledger `cache`, the Worker script `cache`. A writer holding the
account's token can reach it one of two ways -- the Worker admits the token,
or the writer goes to R2 and D1 itself -- and which one is buildable depends on
the token's scopes. This answers each question yes or no with its HTTP status,
from the Actions runner where the secret lives. It prints no token, no token
id and nothing derived from either, and it writes nothing.

    cache_probe.py              (reads CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID)
    cache_probe.py --self-test
"""
import datetime
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.cloudflare.com/client/v4"
WORKER = "https://cache.johnnyillinois.workers.dev"
NAME = "cache"


def _call(url, headers, method="GET", body=None):
    req = urllib.request.Request(url, data=body, method=method,
                                 headers=dict(headers, **{"User-Agent": "asset-pulse-cache-probe"}))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:  # DNS, a refused connection
        return 0, str(e).encode()


def _json(body):
    try:
        return json.loads(body)
    except ValueError:
        return {}


def _hmac(key, msg):
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def s3_headers(method, host, path, query, access, secret, now=None):
    """AWS Signature V4 for R2 (region auto, service s3), an empty body."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    amz, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    empty = hashlib.sha256(b"").hexdigest()
    signed = "host;x-amz-content-sha256;x-amz-date"
    canonical = "\n".join([method, path, query, "host:%s\nx-amz-content-sha256:%s\nx-amz-date:%s\n" % (host, empty, amz),
                           signed, empty])
    scope = "%s/auto/s3/aws4_request" % day
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k = _hmac(_hmac(_hmac(_hmac(("AWS4" + secret).encode(), day), "auto"), "s3"), "aws4_request")
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    return {"x-amz-date": amz, "x-amz-content-sha256": empty,
            "Authorization": "AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s" % (access, scope, signed, sig)}


def probe(token, account, call=_call):
    """[(question, yes, detail)]; no detail holds the token or anything derived from it."""
    out = []
    auth = {"Authorization": "Bearer " + token}
    # A user's token verifies at /user, an account's at /accounts/<id>.
    info, kind = {}, ""
    for where, url in (("user", API + "/user/tokens/verify"), ("account", API + "/accounts/%s/tokens/verify" % account)):
        code, body = call(url, auth)
        r = _json(body).get("result") or {}
        if code == 200 and r.get("status") == "active":
            info, kind = r, where
            break
    out.append(("the token is active", bool(info), kind + " token" if kind else "HTTP %d" % code))
    if not info:
        return out
    code, body = call(API + "/accounts/%s/r2/buckets" % account, auth)
    names = [b.get("name") for b in ((_json(body).get("result") or {}).get("buckets") or [])]
    out.append(("R2: it lists the account's buckets", code == 200, "HTTP %d" % code))
    out.append(("R2: the bucket '%s' is among them" % NAME, NAME in names, "%d bucket(s)" % len(names)))
    host = "%s.r2.cloudflarestorage.com" % account
    h = s3_headers("GET", host, "/" + NAME, "list-type=2&max-keys=1", info.get("id", ""),
                   hashlib.sha256(token.encode()).hexdigest())
    code, _ = call("https://%s/%s?list-type=2&max-keys=1" % (host, NAME), h)
    out.append(("R2: it reads '%s' over the S3 API (derived credentials)" % NAME, code == 200, "HTTP %d" % code))
    # Is it the Worker's bucket? The Worker writes roots/ and packs/ (ops/cache);
    # a count of each, no key printed.
    for prefix in ("roots/", "packs/", "blobs/"):
        q = "list-type=2&max-keys=1000&prefix=" + prefix.replace("/", "%2F")
        h = s3_headers("GET", host, "/" + NAME, q, info.get("id", ""), hashlib.sha256(token.encode()).hexdigest())
        code, body = call("https://%s/%s?%s" % (host, NAME, q), h)
        n = body.count(b"<Key>") if code == 200 else 0
        out.append(("R2: '%s' holds the Worker's %s objects" % (NAME, prefix), n > 0,
                    "HTTP %d, %s%d" % (code, "at least " if n == 1000 else "", n)))
    code, body = call(API + "/accounts/%s/d1/database?name=%s" % (account, NAME), auth)
    dbs = [d.get("name") for d in (_json(body).get("result") or [])] if code == 200 else []
    out.append(("D1: it lists the account's databases", code == 200, "HTTP %d" % code))
    out.append(("D1: the ledger '%s' is among them" % NAME, NAME in dbs, "%d database(s)" % len(dbs)))
    code, body = call(API + "/accounts/%s/workers/scripts" % account, auth)
    scripts = [s.get("id") for s in (_json(body).get("result") or [])] if code == 200 else []
    out.append(("Workers: it lists the account's scripts", code == 200, "HTTP %d" % code))
    out.append(("Workers: the script '%s' is among them" % NAME, NAME in scripts, "%d script(s)" % len(scripts)))
    code, _ = call(WORKER + "/missing", dict(auth, **{"Content-Type": "application/json"}), "POST", b'{"entries":[]}')
    out.append(("the Worker admits it as a reader today", code == 200, "HTTP %d" % code))
    return out


def self_test():
    seen = []
    def fake(url, headers, method="GET", body=None):
        seen.append((url, headers))
        if url.endswith("/user/tokens/verify"):
            return 401, b"{}"
        if url.endswith("/tokens/verify"):
            return 200, json.dumps({"result": {"id": "tid", "status": "active"}}).encode()
        if url.endswith("/r2/buckets"):
            return 200, json.dumps({"result": {"buckets": [{"name": "cache"}]}}).encode()
        if "/d1/database" in url:
            return 200, json.dumps({"result": [{"name": "cache"}]}).encode()
        if url.endswith("/workers/scripts"):
            return 403, b"{}"
        if "prefix=roots" in url:
            return 200, b"<Key>roots/aa/x.json</Key>"
        return 401, b""
    rows = probe("secret-token", "acct", fake)
    ok = [r[1] for r in rows] == [True, True, True, False, True, False, False, True, True, False, False, False]
    ok = ok and rows[0][2] == "account token"
    text = " ".join("%s %s %s" % r for r in rows)
    ok = ok and "secret-token" not in text and "tid" not in text and hashlib.sha256(b"secret-token").hexdigest() not in text
    s3 = [h for u, h in seen if "r2.cloudflarestorage.com" in u][0]["Authorization"]
    ok = ok and s3.startswith("AWS4-HMAC-SHA256 Credential=tid/") and "/auto/s3/aws4_request" in s3
    fixed = s3_headers("GET", "h", "/b", "", "AK", "SK", datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc))
    ok = ok and fixed["x-amz-date"] == "20260101T000000Z" and len(fixed["Authorization"].rsplit("=", 1)[1]) == 64
    dead = probe("t", "a", lambda u, h, m="GET", b=None: (401, b"{}"))
    ok = ok and len(dead) == 1 and not dead[0][1]
    print("cache_probe self-test: " + ("ok" if ok else "FAILED"))
    return 0 if ok else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return self_test()
    token, account = os.environ.get("CLOUDFLARE_API_TOKEN", ""), os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    if not token or not account:
        print("cache probe: CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID are not both in this run's environment")
        return 1
    for q, yes, detail in probe(token, account):
        print("cache probe: %s: %s (%s)" % (q, "yes" if yes else "NO", detail))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
