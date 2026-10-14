#!/usr/bin/env python3
"""
rdap_ra_client.py - RDAP client that understands the "reliabilityAssessment"
extension and applies the rules the specification addresses to consumers.

Usage:
  rdap_ra_client.py BASE_URL domain <name>
  rdap_ra_client.py BASE_URL entity <handle>
  rdap_ra_client.py BASE_URL selftest          # runs the four reference cases
  rdap_ra_client.py --url https://rdap.example/domain/foo.example

Each rule the client applies is printed with its origin:
  [v1]   stated in bcsec-RDAP-RA Version 1, the registered specification
  [-04]  stated only in draft-bertoldi-regext-rdap-reliability-scoring-04
  [core] RFC 7480 / RFC 9083 / draft-ietf-regext-rdap-extensions, not
         specific to the extension
  [proto] a convention of this prototype that no document states
The two documents define the same wire format; the -04 adds consumer rules
the v1 does not have. A client written against the v1 alone applies only
the [v1] lines.

Python standard library only.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

EXTENSION_ID = "reliabilityAssessment"
MEMBER = "reliabilityAssessment_results"
MEDIA_TYPE = "application/rdap+json"
STATUS_VALUES = ("active", "under review", "withdrawn")
FIELDS = ("scoreScheme", "scoreIssuer", "scoreValue", "scoreMaxValue", "scoreDate",
          "validUntil", "assessmentId", "status", "evidenceUri")


class Report:
    def __init__(self):
        self.lines = []
        self.errors = 0

    def rule(self, origin, ok, text):
        mark = "ok " if ok else "ERR"
        if not ok:
            self.errors += 1
        self.lines.append(f"  {mark} [{origin:>4}] {text}")

    def note(self, origin, text):
        self.lines.append(f"  --  [{origin:>4}] {text}")


RFC3339_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt ](\d{2}):(\d{2}):(\d{2})(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")


def parse_dt(value):
    """RFC 3339 Section 5.6 date-time (seconds required, fraction optional,
    'Z' or numeric offset; 't', 'z' and a space separator per the note in
    that section). Leap second 60 is read as 59."""
    if not isinstance(value, str):
        raise ValueError("not a string")
    m = RFC3339_RE.match(value)
    if not m:
        raise ValueError("not RFC 3339")
    y, mo, d, h, mi, sec, frac, off = m.groups()
    if sec == "60":
        sec = "59"
    return datetime.fromisoformat(f"{y}-{mo}-{d}T{h}:{mi}:{sec}" + (frac[:7] if frac else "") +
                                  ("+00:00" if off in ("Z", "z") else off))


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={
        "Accept": MEDIA_TYPE + ", application/json;q=0.5",
        "User-Agent": "rdap-ra-client/0.1.3 (prototype)",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read()
    except (urllib.error.URLError, OSError) as e:
        print(f"  cannot reach {url}: {e.reason if hasattr(e, 'reason') else e}")
        return 0, "", b""


def check_result(res, idx, rep, now):
    where = f"result[{idx}]"
    # structure
    unknown = [k for k in res if k not in FIELDS]
    if unknown:
        rep.note("core", f"{where}: unknown members ignored, as a client MUST "
                         f"(rdap-extensions, Section 2.4.1): {unknown}")
    rep.rule("v1", all(k in res for k in ("scoreScheme", "scoreIssuer")),
             f"{where}: scoreScheme and scoreIssuer present (REQUIRED)")
    rep.rule("v1", all(res.get(k) is not None for k in FIELDS if k in res),
             f"{where}: no null members (a member without a value is omitted)")
    bad_types = [k for k in FIELDS if k in res and res[k] is not None and not (
        isinstance(res[k], (int, float)) and not isinstance(res[k], bool)
        if k in ("scoreValue", "scoreMaxValue") else isinstance(res[k], str))]
    rep.rule("v1", not bad_types, f"{where}: members have the JSON types of Section 7.5" +
             (f" (wrong: {bad_types})" if bad_types else ""))
    if bad_types:
        res = {k: v for k, v in res.items() if k not in bad_types}
    # scheme / issuer
    issuer = res.get("scoreIssuer", "")
    rep.rule("v1", isinstance(issuer, str) and ":" in issuer,
             f"{where}: scoreIssuer is a URI: {issuer}")
    scheme = res.get("scoreScheme", "")
    rep.note("v1", f"{where}: scoreScheme {scheme} compared as a string, no URI normalization")
    # score
    sv, smax = res.get("scoreValue"), res.get("scoreMaxValue")
    if sv is not None and smax is not None:
        rep.rule("v1", sv <= smax, f"{where}: scoreValue {sv} does not exceed scoreMaxValue {smax}")
        rep.note("-04", f"{where}: range is 0..{smax} inclusive, so the score can be placed "
                        f"on a scale without resolving the scheme: {sv}/{smax}")
        rep.note("v1", f"{where}: under the v1 alone the lower bound is not stated, "
                       f"so a bar from zero would be an assumption")
    elif sv is not None:
        rep.note("v1", f"{where}: scoreValue {sv} without scoreMaxValue: unbounded or "
                       f"scheme-defined range, not placed on a scale")
    else:
        rep.note("v1", f"{where}: no scoreValue: scoreValue and scoreMaxValue are OPTIONAL")
        rep.note("-04", f"{where}: a result without a score is complete and conformant: an "
                        f"attestation that the properties of the scheme were examined")
        rep.rule("-04", True, f"{where}: no numeric judgement inferred from the absence of a score")
        if "scoreDate" not in res:
            rep.note("-04", f"{where}: scoreDate SHOULD be present in a result without a score")
    if sv is not None and "scoreDate" not in res:
        rep.note("v1", f"{where}: scoreValue present but scoreDate absent (SHOULD be present)")
    # dates
    sd = vu = None
    if "scoreDate" in res:
        try:
            sd = parse_dt(res["scoreDate"])
            rep.rule("v1", True, f"{where}: scoreDate is RFC 3339: {res['scoreDate']}")
        except ValueError:
            rep.rule("v1", False, f"{where}: scoreDate is not RFC 3339: {res['scoreDate']!r}")
    if "validUntil" in res:
        try:
            vu = parse_dt(res["validUntil"])
            rep.rule("v1", True, f"{where}: validUntil is RFC 3339: {res['validUntil']}")
        except ValueError:
            rep.rule("v1", False, f"{where}: validUntil is not RFC 3339: {res['validUntil']!r}")
    if sd and vu:
        rep.rule("-04", vu >= sd, f"{where}: validUntil does not precede scoreDate")
    # status
    st = res.get("status")
    if st is None:
        rep.note("v1", f"{where}: status absent: no lifecycle state conveyed, NOT assumed active")
    else:
        rep.rule("v1", st in STATUS_VALUES, f"{where}: status {st!r} is a permitted value")
        if st == "under review":
            rep.note("v1", f"{where}: under review: treated with additional caution")
        if st == "withdrawn":
            rep.note("v1", f"{where}: withdrawn: the issuer no longer asserts this result")
    # freshness
    if vu:
        if vu < now:
            rep.note("v1", f"{where}: past validUntil ({res['validUntil']}): STALE, "
                           f"the issuer does not vouch for currency beyond that point")
            if st == "active":
                rep.note("-04", f"{where}: 'active' after validUntil conveys the state last "
                                f"asserted, not a current assertion")
        else:
            rep.note("v1", f"{where}: validUntil in the future: issuer vouches for currency")
    elif sd:
        age = (now - sd).days
        rep.note("v1", f"{where}: no validUntil; scoreDate is {age} days old (freshness is "
                       f"for the consumer to judge)")
    else:
        rep.note("-04", f"{where}: no date at all: treated with skepticism (the v1 staleness "
                        f"item speaks only of results not updated recently or past validUntil)")
    if "evidenceUri" in res:
        rep.note("v1", f"{where}: evidenceUri is maintained by the issuer, not fetched, "
                       f"not assumed public or immutable")


def analyse(obj, rep, now, ctype=""):
    rep.rule("core", ctype.split(";")[0].strip() == MEDIA_TYPE,
             f"Content-Type is {MEDIA_TYPE} (got {ctype.split(';')[0].strip() or 'none'})")
    conf = obj.get("rdapConformance", [])
    rep.rule("core", "rdap_level_0" in conf, "rdapConformance contains rdap_level_0")
    cls = obj.get("objectClassName")
    key = obj.get("ldhName") if cls == "domain" else obj.get("handle")
    rep.note("core", f"object: {cls} {key}")
    if cls == "entity":
        rep.note("v1", "entity represents a registrar: " +
                 ("yes" if "registrar" in obj.get("roles", []) else "no") +
                 " (roles member)")
    if MEMBER not in obj:
        if EXTENSION_ID in conf:
            rep.note("core", "member absent but extension listed in rdapConformance: allowed, a "
                             "help response lists every extension the server supports (RFC 9083, "
                             "Section 4.1)")
        else:
            rep.note("v1", "member absent and extension not advertised in rdapConformance")
        rep.note("v1", "member absent: NOTHING is inferred. Not evidence that the object was "
                       "not assessed, not a negative assessment. The server may not implement "
                       "the extension, may withhold the result, or may require authorization.")
        return
    rep.rule("v1", EXTENSION_ID in conf,
             f"extension advertised: {EXTENSION_ID!r} in rdapConformance")
    arr = obj[MEMBER]
    rep.rule("v1", isinstance(arr, list) and len(arr) > 0,
             f"{MEMBER} is a non-empty array ({len(arr) if isinstance(arr, list) else 'n/a'} results)")
    if not isinstance(arr, list):
        return
    rep.note("v1", "order of results is not significant: no precedence, authority or "
                   "recency inferred from position")
    seen = {}
    for i, res in enumerate(arr):
        if not isinstance(res, dict):
            rep.rule("v1", False, f"result[{i}] is not an object")
            continue
        k = (res.get("scoreScheme"), res.get("scoreIssuer"))
        if k in seen:
            rep.note("v1", f"result[{i}]: second current result for the same scheme+issuer "
                           f"(server SHOULD publish at most one)")
        seen[k] = i
        check_result(res, i, rep, now)


def table(obj):
    arr = obj.get(MEMBER, [])
    if not arr:
        return "  (no assessment results)"
    cols = ("issuer", "scheme", "score", "date", "validUntil", "status")
    rows = []
    for r in arr:
        score = "-"
        if "scoreValue" in r:
            score = str(r["scoreValue"]) + (f"/{r['scoreMaxValue']}" if "scoreMaxValue" in r else "")
        rows.append((r.get("scoreIssuer", ""), r.get("scoreScheme", "").rsplit("/", 1)[-1],
                     score, (r.get("scoreDate") or "-")[:10], (r.get("validUntil") or "-")[:10],
                     r.get("status", "-")))
    widths = [max(len(c), *(len(row[i]) for row in rows)) for i, c in enumerate(cols)]
    out = ["  " + "  ".join(c.ljust(widths[i]) for i, c in enumerate(cols))]
    for row in rows:
        out.append("  " + "  ".join(row[i].ljust(widths[i]) for i in range(len(cols))))
    return "\n".join(out)


def referral_links(obj):
    """PROTOTYPE convention, not a rule of either document: the -04 (Section
    5.4) names the 'referring to a service' arrangement but fixes no link
    relation, media type or path, and the v1 (Section 5.4) says why reusing
    'related' is ambiguous. This client recognises the test server's own
    convention: rel 'related', RDAP media type, href containing '/assessor/'."""
    return [l for l in obj.get("links", [])
            if l.get("rel") == "related" and l.get("type") == MEDIA_TYPE
            and "/assessor/" in l.get("href", "")]


def lookup(url, follow=True, raw=False):
    now = datetime.now(timezone.utc)
    print(f"GET {url}")
    status, ctype, body = fetch(url)
    if status == 0:
        return 1
    print(f"  HTTP {status}")
    try:
        obj = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        print("  body is not JSON; stopping")
        return 1
    if raw:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    if status != 200:
        print(f"  RDAP error object: {obj.get('errorCode')} {obj.get('title')}: "
              f"{' '.join(obj.get('description', []))}")
        return 1
    rep = Report()
    analyse(obj, rep, now, ctype)
    print("\nAssessment results:")
    print(table(obj))
    print("\nRules applied:")
    print("\n".join(rep.lines))
    print(f"\n{rep.errors} rule violation(s).")
    rc = 0 if rep.errors == 0 else 2
    refs = referral_links(obj)
    if refs:
        print(f"\n  [proto] link recognised by this prototype's convention as a referral to an "
              f"assessment service (the -04, Section 5.4, names the arrangement but fixes no "
              f"relation; this server uses rel 'related'): {refs[0]['href']}")
        if follow:
            print("  Following it. An assessment service is NOT authoritative for the "
                  "registration data (v1 and -04, Section 5.2); expect a minimal response.\n")
            rc2 = lookup(refs[0]["href"], follow=False, raw=raw)
            return max(rc, rc2)
    return rc


def selftest(base):
    """The four reference cases of the -04, Appendix C, as served by the test
    server. Pass/fail per case; the exit code is non-zero on any failure."""
    cases = [
        ("C.1 domain lookup with a single result", "domain/assessed.example", True),
        ("C.2 registrar lookup with results from two issuers", "entity/RAR1001", True),
        ("C.3 registrar lookup with an attestation carrying no score", "entity/RAR1002", True),
        ("C.4 domain lookup without assessment metadata", "domain/plain.example", False),
    ]
    now = datetime.now(timezone.utc)
    failed = 0
    for title, path, expect_member in cases:
        url = base.rstrip("/") + "/" + path
        status, ctype, body = fetch(url)
        ok = status == 200
        detail = f"HTTP {status}"
        if ok:
            obj = json.loads(body.decode("utf-8"))
            rep = Report()
            analyse(obj, rep, now, ctype)
            has = MEMBER in obj
            ok = rep.errors == 0 and has == expect_member
            detail += f", member {'present' if has else 'absent'}, {rep.errors} violation(s)"
            if path == "entity/RAR1001" and ok:
                ok = len(obj[MEMBER]) == 2
                detail += f", {len(obj[MEMBER])} results"
            if path == "entity/RAR1002" and ok:
                ok = "scoreValue" not in obj[MEMBER][0]
                detail += ", no score"
        print(f"{'PASS' if ok else 'FAIL'}  {title}  ({detail})")
        failed += 0 if ok else 1
    # negative case: unknown object must be an RDAP error object, not HTML
    status, ctype, body = fetch(base.rstrip("/") + "/domain/nonexistent.example")
    try:
        obj = json.loads(body.decode("utf-8"))
        ok = status == 404 and obj.get("errorCode") == 404 and ctype.startswith(MEDIA_TYPE)
    except ValueError:
        ok = False
    print(f"{'PASS' if ok else 'FAIL'}  unknown object returns an RDAP error object (HTTP {status})")
    failed += 0 if ok else 1
    print(f"\n{len(cases) + 1 - failed} passed, {failed} failed")
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description="RDAP client for the reliabilityAssessment extension")
    ap.add_argument("base", nargs="?", help="base URL of the RDAP server")
    ap.add_argument("what", nargs="?", choices=["domain", "entity", "selftest"])
    ap.add_argument("key", nargs="?", help="domain name or entity handle")
    ap.add_argument("--url", help="full URL to query instead of base/what/key")
    ap.add_argument("--no-follow", action="store_true", help="do not follow a referral link")
    ap.add_argument("--raw", action="store_true", help="also print the JSON response")
    a = ap.parse_args()
    if a.url:
        sys.exit(lookup(a.url, follow=not a.no_follow, raw=a.raw))
    if not a.base or not a.what:
        ap.print_help()
        sys.exit(2)
    if a.what == "selftest":
        sys.exit(selftest(a.base))
    if not a.key:
        ap.error("a domain name or entity handle is required")
    sys.exit(lookup(a.base.rstrip("/") + f"/{a.what}/{a.key}", follow=not a.no_follow, raw=a.raw))


if __name__ == "__main__":
    main()
