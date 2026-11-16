#!/usr/bin/env python3
"""
rdap_ra_server.py - test RDAP server carrying the "reliabilityAssessment"
extension (IANA RDAP Extensions Registry, registered 2026-10-06).

Wire format: bcsec-RDAP-RA Version 1
  https://bcsec.io/rdap/v1/bcsec-rdap-reliability-assessment.txt
Deployment arrangements shown: draft-bertoldi-regext-rdap-reliability-scoring-04,
  Section 5.4 ("carrying the result"; "referring to a service" behind a switch).

The server plays the role of the server AUTHORITATIVE for a fictional test
zone. Being a test server it is not listed in the IANA bootstrap registries
(RFC 9224), so a client reaches it only when given its base URL; a real
authoritative server would be found through the bootstrap.

Design choices:
  * Python standard library only. No third-party code.
  * Read-only. Responses are static JSON files under data/. There is no
    interface for creating or modifying assessment data (the extension
    defines none; Section 11, "Result integrity").
  * All data is validated at start-up against the rules of the v1 and of
    the -04, plus two hygiene rules of this prototype that the documents do
    not state (no unknown member inside a result; no advertising of the
    extension in a lookup response that carries no member, which RFC 9083
    Section 4.1 implies). A data file that breaks a rule stops the server.
  * Only GET and HEAD. Lookups: /domain/<name>, /entity/<handle>, /help.
  * Media type application/rdap+json (RFC 7480). Errors are RDAP error
    objects (RFC 9083 Section 6), never HTML.
  * Extension versioning (draft-ietf-regext-rdap-versioning-08, Point
    Versioning) behind a switch, OFF by default. When on, the extension is
    declared as version reliabilityAssessment-0.1, whose wire format is that
    of bcsec-RDAP-RA Version 1, byte for byte: only the members "versioning",
    "versioning_data" and "versioning_help" are added.
  * Transition from Opaque to Point Versioning behind a second switch, OFF
    by default (Sections 4 and 7.2 of the same draft). When on, the
    registered identifier stays opaque and is the default; the same result
    is also offered, on request only, under a PLACEHOLDER successor
    identifier that uses Point Versioning. The placeholder starts with
    "draft" (draft-ietf-regext-rdap-extensions-18, Section 2.2: reserved
    for work in progress, never registered) and is not a proposed name.

This is a prototype written by the author of the specification. It is not
a production RDAP server and implements only what the demonstration needs.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

EXTENSION_ID = "reliabilityAssessment"
MEMBER = "reliabilityAssessment_results"
MEDIA_TYPE = "application/rdap+json"
STATUS_VALUES = ("active", "under review", "withdrawn")

# draft-ietf-regext-rdap-versioning-08: extension identifier of the
# versioning extension itself, and its Point Extension Version Identifier
# (Section 8 of that draft).
VERSIONING_ID = "versioning"
VERSIONING_VERSION = "versioning-0.9"
# Point Extension Version Identifier of this extension in the prototype
# (Section 5.2.1 of the versioning draft: name "-" major "." minor). 0.1 is
# the wire format of bcsec-RDAP-RA Version 1, unchanged. PROTOTYPE choice:
# neither the registered specification nor the -05 declares point versions.
EXTENSION_VERSION = EXTENSION_ID + "-0.1"
# Transition experiment (switch "transition_enabled"). PLACEHOLDER successor
# identifier, used only to show the mechanism of Section 4 of the versioning
# draft (predecessor and successor) for an extension that moves from Opaque
# to Point Versioning. It is not a proposed name: identifiers that start
# with "draft" are reserved for work in progress and cannot be registered
# (draft-ietf-regext-rdap-extensions-18, Section 2.2).
SUCCESSOR_ID = "draftReliabilityAssessmentExperimental"
SUCCESSOR_MEMBER = SUCCESSOR_ID + "_results"
SUCCESSOR_VERSION = SUCCESSOR_ID + "-0.1"
ALLOWED_FIELDS = {
    "scoreScheme": str,
    "scoreIssuer": str,
    "scoreValue": (int, float),
    "scoreMaxValue": (int, float),
    "scoreDate": str,
    "validUntil": str,
    "assessmentId": str,
    "status": str,
    "evidenceUri": str,
}
REQUIRED_FIELDS = ("scoreScheme", "scoreIssuer")

# Public base URL of the server (used for "self" links). Set at start-up.
CONFIG = {
    "base_url": "http://localhost:8080",
    # -04 Section 5.4, "Referring to a service". OFF by default: the -04 does
    # not fix the link relation, and the v1 (Section 5.4) explains why
    # reusing "related" is ambiguous. Enable only to put the question to
    # the working group with a running example.
    "referral_enabled": False,
    # Base URL under which the simulated assessment service answers. In this
    # prototype it defaults to <base_url>/assessor on the SAME host, which is
    # a simulation: an assessment service is by definition a different
    # service (v1 and -04, Section 2), and the -04 defines no path segment
    # for it (Section 4; the dedicated-segment idea is recorded in Section
    # 5.4 as NOT defined). Point it at another host to make the link cross
    # services for real.
    "assessor_base_url": None,
    # True when --assessor-base-url points at another service: the local
    # /assessor/ simulation is then switched off.
    "assessor_external": False,
    # Assessment service mode (v1 and -04, Section 5.2): this process is not
    # an authoritative server. It answers /domain/<name> and /entity/<handle>
    # with the minimal response of an assessment service, from data/assessor/.
    "assessor_only": False,
    # draft-ietf-regext-rdap-versioning-08, Point Versioning. OFF by default:
    # with the switch off no response changes.
    "versioning_enabled": False,
    # Transition from Opaque to Point Versioning with a successor identifier
    # (Sections 4 and 7.2 of the versioning draft). OFF by default: with the
    # switch off no response changes. When on it replaces the behaviour of
    # "versioning_enabled" for this process.
    "transition_enabled": False,
    "data_dir": None,
}

DATA = {"domain": {}, "entity": {}, "assessor_domain": {}, "assessor_entity": {}}


# ---------------------------------------------------------------- validation

class DataError(Exception):
    pass


RFC3339_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[Tt ](\d{2}):(\d{2}):(\d{2})(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")


def parse_rfc3339(value, where):
    """RFC 3339 Section 5.6 date-time: full date, 'T' (or 't'/space per the
    note in that section), full time with seconds, fraction optional, and a
    'Z'/'z' or numeric offset. Leap second 60 is accepted and read as 59."""
    if not isinstance(value, str):
        raise DataError(f"{where}: date-time must be a string")
    m = RFC3339_RE.match(value)
    if not m:
        raise DataError(f"{where}: not an RFC 3339 date-time: {value!r}")
    y, mo, d, h, mi, sec, frac, off = m.groups()
    if sec == "60":
        sec = "59"
    iso = f"{y}-{mo}-{d}T{h}:{mi}:{sec}" + (frac[:7] if frac else "") + \
          ("+00:00" if off in ("Z", "z") else off)
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        raise DataError(f"{where}: not a valid RFC 3339 date-time: {value!r}")


def is_uri(value):
    # RFC 3986 scheme ":" hier-part. A deliberately simple check: the
    # specification requires a URI, it does not require dereferenceability.
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:[^\s]+$", value))


def validate_result(res, where):
    """Rules of v1 Section 7.5/7.6 and -04 Section 7.5, applied to one
    assessment result object. The 'unknown member' check is prototype
    hygiene for this server's own data files, not a rule of the documents:
    a CLIENT must ignore unknown members (draft-ietf-regext-rdap-extensions,
    Section 2.4.1)."""
    if not isinstance(res, dict):
        raise DataError(f"{where}: result must be a JSON object")
    for k in REQUIRED_FIELDS:
        if k not in res:
            raise DataError(f"{where}: missing REQUIRED member {k}")
    for k, v in res.items():
        if k not in ALLOWED_FIELDS:
            raise DataError(f"{where}: unknown member {k}")
        if v is None:
            raise DataError(f"{where}: {k} is null; omit the member instead")
        if not isinstance(v, ALLOWED_FIELDS[k]) or isinstance(v, bool):
            raise DataError(f"{where}: {k} has the wrong JSON type")
    if not is_uri(res["scoreIssuer"]):
        raise DataError(f"{where}: scoreIssuer MUST be a URI")
    if "evidenceUri" in res and not is_uri(res["evidenceUri"]):
        raise DataError(f"{where}: evidenceUri is defined as a URI")
    if "scoreValue" in res and res["scoreValue"] < 0:
        raise DataError(f"{where}: scoreValue must be non-negative")
    if "scoreMaxValue" in res and res["scoreMaxValue"] < 0:
        raise DataError(f"{where}: scoreMaxValue must be non-negative")
    if "scoreValue" in res and "scoreMaxValue" in res:
        if res["scoreValue"] > res["scoreMaxValue"]:
            raise DataError(f"{where}: scoreValue MUST NOT exceed scoreMaxValue")
    if "status" in res and res["status"] not in STATUS_VALUES:
        raise DataError(f"{where}: status {res['status']!r} not permitted")
    sd = parse_rfc3339(res["scoreDate"], where) if "scoreDate" in res else None
    vu = parse_rfc3339(res["validUntil"], where) if "validUntil" in res else None
    if sd and vu and vu < sd:
        # -04 only: validUntil MUST NOT precede scoreDate.
        raise DataError(f"{where}: validUntil precedes scoreDate (-04, Section 7.5)")


def validate_envelope(obj, where):
    if MEMBER not in obj:
        return
    arr = obj[MEMBER]
    if not isinstance(arr, list) or len(arr) == 0:
        raise DataError(f"{where}: {MEMBER} MUST be a non-empty array")
    seen = set()
    for i, res in enumerate(arr):
        validate_result(res, f"{where} result[{i}]")
        if res.get("status") == "withdrawn":
            # Section 7.6: a withdrawn result MAY continue to be published
            # next to its replacement; the SHOULD in 7.4 is about CURRENT
            # results only.
            continue
        key = (res["scoreScheme"], res["scoreIssuer"])  # compared as strings
        if key in seen:
            raise DataError(f"{where}: more than one current result for scheme+issuer {key}"
                            " (Section 7.4, SHOULD)")
        seen.add(key)
    conf = obj.get("rdapConformance", [])
    if EXTENSION_ID not in conf:
        raise DataError(f"{where}: {EXTENSION_ID} missing from rdapConformance")


def validate_object(obj, cls, where):
    if obj.get("objectClassName") != cls:
        raise DataError(f"{where}: objectClassName must be {cls!r}")
    if "rdap_level_0" not in obj.get("rdapConformance", []):
        raise DataError(f"{where}: rdap_level_0 missing from rdapConformance")
    if MEMBER not in obj and EXTENSION_ID in obj.get("rdapConformance", []):
        # RFC 9083 Section 4.1: a lookup response lists only the
        # specifications used in its construction (help responses differ).
        raise DataError(f"{where}: advertises {EXTENSION_ID} but carries no member")
    validate_envelope(obj, where)
    # nested entities (registrar inside a domain): the member is allowed
    # there too, and the same rules apply.
    for j, ent in enumerate(obj.get("entities", [])):
        if MEMBER in ent:
            validate_envelope({**ent, "rdapConformance": obj["rdapConformance"]},
                              f"{where} entities[{j}]")


def load_dir(path, cls, store):
    if not os.path.isdir(path):
        return
    for fn in sorted(os.listdir(path)):
        if not fn.endswith(".json"):
            continue
        full = os.path.join(path, fn)
        with open(full, encoding="utf-8") as f:
            obj = json.load(f)
        validate_object(obj, cls, full)
        keyname = "ldhName" if cls == "domain" else "handle"
        if not isinstance(obj.get(keyname), str):
            raise DataError(f"{full}: {keyname} missing or not a string")
        key = obj["ldhName"].lower() if cls == "domain" else obj["handle"]
        store[key] = obj


def load_data(data_dir):
    load_dir(os.path.join(data_dir, "domain"), "domain", DATA["domain"])
    load_dir(os.path.join(data_dir, "entity"), "entity", DATA["entity"])
    load_dir(os.path.join(data_dir, "assessor", "domain"), "domain", DATA["assessor_domain"])
    load_dir(os.path.join(data_dir, "assessor", "entity"), "entity", DATA["assessor_entity"])


# ------------------------------------------------------------------ responses

def with_links(obj, path):
    """Add a 'self' link (RFC 9083 Section 4.2) pointing at this server."""
    base = CONFIG["base_url"].rstrip("/")
    out = json.loads(json.dumps(obj).replace("{BASE}", base))  # deep copy
    self_url = base + path
    out.setdefault("links", []).insert(0, {
        "value": self_url, "rel": "self", "href": self_url, "type": MEDIA_TYPE,
    })
    return out


def apply_referral(obj, cls, key):
    """-04 Section 5.4, second arrangement: the authoritative server publishes
    a link to a resource from which the result may be retrieved. Only when
    the switch is on, and only for objects that carry a 'referral' marker in
    their data file instead of the member itself."""
    if not CONFIG["referral_enabled"]:
        obj.pop("x_referral", None)
        return obj
    marker = obj.pop("x_referral", None)
    if not marker:
        return obj
    target = CONFIG["assessor_base_url"].rstrip("/") + f"/{cls}/{key}"
    obj.setdefault("links", []).append({
        "value": CONFIG["base_url"].rstrip("/") + f"/{cls}/{key}",
        "rel": "related",          # PROTOTYPE choice; neither document fixes a relation
        "href": target,
        "type": MEDIA_TYPE,
        "title": "reliability assessment (prototype referral)",
    })
    return obj


def carries_member(obj):
    """True when the response carries the extension member, at the top level
    or inside a nested entity (the registrar inside a domain)."""
    if MEMBER in obj:
        return True
    return any(isinstance(e, dict) and MEMBER in e for e in obj.get("entities", []))


def add_versioning_conformance(obj):
    conf = obj.setdefault("rdapConformance", [])
    if VERSIONING_ID not in conf:
        # Same position as in Figures 6, 8 and 13 of the versioning draft:
        # right after rdap_level_0.
        pos = conf.index("rdap_level_0") + 1 if "rdap_level_0" in conf else 0
        conf.insert(pos, VERSIONING_ID)


def versioning_data():
    """draft-ietf-regext-rdap-versioning-08, Section 3.3.3: the versions in
    use in this response. Shape as in Figure 8 of that draft."""
    return [
        {"extension": "rdap_level_0", "type": "opaque", "version": "rdap_level_0"},
        {"extension": VERSIONING_ID, "type": "point", "version": VERSIONING_VERSION},
        {"extension": EXTENSION_ID, "type": "point", "version": EXTENSION_VERSION},
    ]


def requested_versions(accept_values):
    """Section 3.2.1 of the versioning draft: the client lists Extension
    Version Identifiers in the "versioning_list" parameter of the media type
    in the Accept header, separated by "+". Returns the set of identifiers
    asked for; empty when the client asks for nothing."""
    out = set()
    for value in accept_values or []:
        for media_range in value.split(","):
            parts = media_range.split(";")
            # The parameter belongs to the RDAP media type: it is not read
            # from any other media range.
            if parts[0].strip().lower() != MEDIA_TYPE:
                continue
            params = {}
            for param in parts[1:]:
                name, _, val = param.strip().partition("=")
                params.setdefault(name.strip().lower(), val.strip().strip('"'))
            # A range the client refuses (q=0) carries no request.
            try:
                if "q" in params and float(params["q"]) == 0:
                    continue
            except ValueError:
                pass
            out.update(v for v in params.get("versioning_list", "").split("+") if v)
    return out


def transition_selection(requested):
    """Which identifiers a response uses in the transition experiment.
    Returns (old, new). The request is a hint and the server decides
    (Section 3.2); an unsupported version is ignored. PROTOTYPE policy:
      * nothing asked, or only versions this server does not have: the
        registered identifier, which is the default (step 1 of Section 7.2);
      * the successor asked, by version or by bare identifier: the
        successor only;
      * both asked: both, each under its own name. The versioning draft does
        not say what to do in this case; the prototype does what was asked.
    """
    # Section 5.1 of the versioning draft: an extension that uses another
    # Versioning Type MAY be referred to by its bare identifier, and the
    # server then returns its default version. The successor has one version.
    want_new = SUCCESSOR_VERSION in requested or SUCCESSOR_ID in requested
    want_old = EXTENSION_ID in requested
    if want_new:
        return want_old, True
    return True, False


def carries_member_deep(obj):
    """Like carries_member, at any depth of nested "entities"."""
    if MEMBER in obj:
        return True
    return any(isinstance(e, dict) and carries_member_deep(e)
               for e in obj.get("entities", []) if isinstance(obj.get("entities"), list))


def rename_member(obj, old, new):
    """Rebuild one JSON object so that the result is carried under the names
    chosen by transition_selection, in the position of the original member,
    in this object and in its nested "entities" at any depth. The value (the
    array of results) is never modified."""
    out = {}
    for k, v in obj.items():
        if k == MEMBER:
            if old:
                out[MEMBER] = v
            if new:
                out[SUCCESSOR_MEMBER] = json.loads(json.dumps(v))
        elif k == "entities" and isinstance(v, list):
            out[k] = [rename_member(e, old, new) if isinstance(e, dict) else e for e in v]
        else:
            out[k] = v
    return out


def apply_transition(obj, requested):
    """Transition experiment: Sections 3.3.1, 3.3.3, 4 and 7.2 of the
    versioning draft. Only for responses that carry the member."""
    if not carries_member_deep(obj):
        return obj
    old, new = transition_selection(requested)
    obj = rename_member(obj, old, new)
    conf = []
    for c in obj.get("rdapConformance", []):
        if c == EXTENSION_ID:
            if old:
                conf.append(EXTENSION_ID)
            if new:
                conf.append(SUCCESSOR_ID)
        else:
            conf.append(c)
    obj["rdapConformance"] = conf
    add_versioning_conformance(obj)
    data = [
        {"extension": "rdap_level_0", "type": "opaque", "version": "rdap_level_0"},
        {"extension": VERSIONING_ID, "type": "point", "version": VERSIONING_VERSION},
    ]
    if old:
        data.append({"extension": EXTENSION_ID, "type": "opaque", "version": EXTENSION_ID})
    if new:
        data.append({"extension": SUCCESSOR_ID, "type": "point", "version": SUCCESSOR_VERSION})
    obj["versioning_data"] = data
    return obj


def transition_help_members(obj):
    """Help response of the transition experiment: the two related extension
    objects of Section 4, with the members of Section 3.3.2."""
    base = CONFIG["base_url"].rstrip("/")
    conf = obj.setdefault("rdapConformance", [])
    if SUCCESSOR_ID not in conf:
        conf.append(SUCCESSOR_ID)
    add_versioning_conformance(obj)
    obj["versioning_help"] = [
        # Section 5.1.2: for an extension with Opaque Versioning only there
        # is a single "versions" object whose "version" matches "extension".
        # Figures 6 and 11 of the draft omit it; the text is followed here,
        # for both opaque entries (rdap_level_0 is treated as an Opaque
        # Extension Version Identifier, Section 5.1).
        {"extension": "rdap_level_0", "type": "opaque",
         "versions": [{"version": "rdap_level_0"}]},
        {"extension": VERSIONING_ID, "type": "point",
         "versions": [{"version": VERSIONING_VERSION, "default": True}]},
        {"extension": EXTENSION_ID, "type": "opaque",
         "successor": SUCCESSOR_ID, "default": True,
         "versions": [{"version": EXTENSION_ID}],
         "links": [{"value": base + "/help", "rel": "describedby", "type": "text/plain",
                    "href": "https://bcsec.io/rdap/v1/bcsec-rdap-reliability-assessment.txt"}]},
        # "default" here is the one among related extension objects (the
        # successor is not what a client receives when it asks for nothing).
        # Its single version carries no "default": Section 3.3.2 makes a
        # single extension version object the default of its extension.
        {"extension": SUCCESSOR_ID, "type": "point",
         "predecessor": EXTENSION_ID, "default": False,
         "versions": [{"version": SUCCESSOR_VERSION}]},
    ]
    obj["versioning_data"] = [
        {"extension": "rdap_level_0", "type": "opaque", "version": "rdap_level_0"},
        {"extension": VERSIONING_ID, "type": "point", "version": VERSIONING_VERSION},
    ]
    obj["notices"].append({
        "title": "Transition from Opaque to Point Versioning (experiment)",
        "description": [
            "This instance is an experiment with draft-ietf-regext-rdap-versioning-08, "
            "Sections 4 and 7.2: an extension that starts with Opaque Versioning "
            "and continues with Point Versioning under a successor identifier.",
            "reliabilityAssessment is the registered identifier. It stays opaque "
            "and unchanged, and it is the default: a client that asks for nothing "
            "receives reliabilityAssessment_results, as registered.",
            SUCCESSOR_ID + " is a PLACEHOLDER successor, not a proposed name. "
            "Identifiers that start with 'draft' are reserved for work in progress "
            "and cannot be registered (draft-ietf-regext-rdap-extensions-18, "
            "Section 2.2). It uses Point Versioning, version " + SUCCESSOR_VERSION + ".",
            "The successor is returned only on request, with the Accept header "
            "application/rdap+json;versioning_list=" + SUCCESSOR_VERSION + " (or "
            "the bare identifier, Section 5.1 of the versioning draft). The "
            "result is then carried as " + SUCCESSOR_MEMBER + ", with the same "
            "members and the same values: only the name changes.",
            "A client that asks for both, with versioning_list=" + EXTENSION_ID + "+"
            + SUCCESSOR_VERSION + ", receives the result under both names. The "
            "versioning draft does not say what a server does in this case; this "
            "is a choice of the prototype. An unsupported version is ignored.",
            "In versioning_help, default: false on the successor means that it "
            "is not what a client receives when it asks for nothing. Its single "
            "version carries no default member: a single version is the default "
            "of its own extension (Section 3.3.2).",
            "This is step 1 of Section 7.2 only (new version optional, old version "
            "default). Neither the registered specification nor the Internet-Draft "
            "defines a successor identifier; this instance is not a statement of "
            "either document.",
        ],
    })
    return obj


def apply_versioning(obj, requested=None):
    """Section 3.3.1 and 3.3.3 of the versioning draft: a response that
    carries extension fields declares "versioning" in rdapConformance and
    lists the versions in "versioning_data". Only when the switch is on and
    only for responses that carry the member; nothing else is touched, and
    the member itself is never modified."""
    if CONFIG["transition_enabled"]:
        return apply_transition(obj, requested or set())
    if not CONFIG["versioning_enabled"] or not carries_member(obj):
        return obj
    add_versioning_conformance(obj)
    obj["versioning_data"] = versioning_data()
    return obj


def versioning_help_members(obj):
    """Section 3.3.2 of the versioning draft: the help response describes
    the supported versions; shape as in Figure 13. One version per
    extension, so each is the default."""
    if CONFIG["transition_enabled"]:
        return transition_help_members(obj)
    if not CONFIG["versioning_enabled"]:
        return obj
    add_versioning_conformance(obj)
    obj["versioning_help"] = [
        {"extension": "rdap_level_0", "type": "opaque"},
        {"extension": VERSIONING_ID, "type": "point",
         "versions": [{"version": VERSIONING_VERSION, "default": True}]},
        {"extension": EXTENSION_ID, "type": "point",
         "versions": [{"version": EXTENSION_VERSION, "default": True}]},
    ]
    obj["versioning_data"] = [versioning_data()[0], versioning_data()[1]]
    obj["notices"].append({
        "title": "Extension versioning (prototype)",
        "description": [
            "This instance implements Point Versioning as described in "
            "draft-ietf-regext-rdap-versioning-08. The extension identifier in "
            "rdapConformance stays reliabilityAssessment; the version in use is "
            "declared in versioning_data as " + EXTENSION_VERSION + ".",
            EXTENSION_VERSION + " is the wire format of bcsec-RDAP-RA Version 1, "
            "unchanged. It is the only version served, and the default.",
            "A client may ask for a version in the Accept header, for example "
            "application/rdap+json;versioning_list=" + EXTENSION_VERSION + ". An "
            "unsupported version is ignored and the default is returned.",
            "The registered specification and the Internet-Draft (Section 7.2 "
            "in each) declare Opaque Versioning, with extension version "
            "identifier reliabilityAssessment, and do not use Point Versioning. "
            "This instance shows what Point Versioning would look like; it is "
            "not a statement of either document.",
        ],
    })
    return obj


def error_object(code, title, description):
    return {
        "rdapConformance": ["rdap_level_0"],
        "errorCode": code,
        "title": title,
        "description": [description],
    }


def assessor_help_object():
    base = CONFIG["base_url"].rstrip("/")
    notices = [{
        "title": "About this server",
        "description": [
            "Test RDAP assessment service for the reliabilityAssessment extension "
            "(IANA RDAP Extensions Registry, registered 2026-10-06).",
            "This service is NOT authoritative for registration data. A response "
            "identifies the object and carries the assessment result, nothing else "
            "(bcsec-RDAP-RA Version 1 and "
            "draft-bertoldi-regext-rdap-reliability-scoring, Section 5.2).",
            "It is the service an authoritative test server refers to; see "
            "https://rdap-referral.bcsec.io/help.",
            "The issuer identifier in its results is the URL of this service. "
            "Scheme and evidence identifiers are URIs under the same name; "
            "they identify, and are not meant to be retrieved.",
            "All objects are fictional. No real registrar or domain is assessed.",
            "Lookups: /domain/<name>, /entity/<handle>. Read-only.",
        ],
        "links": [
            {"value": base + "/help", "rel": "describedby", "type": "text/plain",
             "href": "https://bcsec.io/rdap/v1/bcsec-rdap-reliability-assessment.txt"},
            {"value": base + "/help", "rel": "related", "type": "text/html",
             "href": "https://datatracker.ietf.org/doc/draft-bertoldi-regext-rdap-reliability-scoring/"},
        ],
    }, {
        "title": "Objects available",
        "description": [
            "domains: " + ", ".join(sorted(DATA["assessor_domain"])),
            "entities: " + (", ".join(sorted(DATA["assessor_entity"])) or "none"),
        ],
    }]
    return versioning_help_members(
        {"rdapConformance": ["rdap_level_0", EXTENSION_ID], "notices": notices})


def help_object():
    if CONFIG["assessor_only"]:
        return assessor_help_object()
    notices = [{
        "title": "About this server",
        "description": [
            "Test RDAP server for the reliabilityAssessment extension "
            "(IANA RDAP Extensions Registry, registered 2026-10-06).",
            "Wire format: bcsec-RDAP-RA Version 1. Deployment arrangements: "
            "draft-bertoldi-regext-rdap-reliability-scoring, Section 5.4.",
            "All objects are fictional. No real registrar or domain is assessed.",
            "Lookups: /domain/<name>, /entity/<handle>. Read-only.",
        ],
        # RFC 9083 Section 4.2: "value", "rel" and "href" MUST be specified.
        "links": [
            {"value": CONFIG["base_url"].rstrip("/") + "/help",
             "rel": "describedby", "type": "text/plain",
             "href": "https://bcsec.io/rdap/v1/bcsec-rdap-reliability-assessment.txt"},
            {"value": CONFIG["base_url"].rstrip("/") + "/help",
             "rel": "related", "type": "text/html",
             "href": "https://datatracker.ietf.org/doc/draft-bertoldi-regext-rdap-reliability-scoring/"},
        ],
    }, {
        "title": "Objects available",
        "description": [
            "domains: " + ", ".join(sorted(DATA["domain"])),
            "entities: " + ", ".join(sorted(DATA["entity"])),
            "referral arrangement: " + ("ON" if CONFIG["referral_enabled"] else "OFF"),
        ],
    }]
    if CONFIG["referral_enabled"]:
        notices.append({
            "title": "Referral arrangement (prototype)",
            "description": [
                "This instance also publishes a link from the authoritative "
                "response to an assessment service: "
                + (f"a separate RDAP service at {CONFIG['assessor_base_url']}."
                   if CONFIG["assessor_external"]
                   else "simulated under /assessor/ on this host."),
                "The link relation 'related' is a placeholder of this prototype: "
                "no registered relation type describes an assessment result, and "
                "none is defined yet.",
                "/domain/referred.example carries the link only. "
                "/domain/combined.example carries basic information together "
                "with the link: the members fixed when a result is issued "
                "(scheme, issuer, value with its range, date, expiry). What "
                "can change afterwards (status) and the detail (assessment "
                "identifier, evidence) are returned by the assessment service.",
                "In these two examples the issuer identifier is the URL of the "
                "assessment service the link points to.",
            ],
        })
    return versioning_help_members(
        {"rdapConformance": ["rdap_level_0", EXTENSION_ID], "notices": notices})


class Handler(BaseHTTPRequestHandler):
    server_version = "rdap-ra-proto/0.5.0"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    # Idle socket timeout: a client that opens a connection and sends nothing
    # (or dribbles bytes) is dropped after this many seconds.
    timeout = 15

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _drain_body(self):
        """Consume any request body so that a keep-alive connection is not
        left with unread bytes (they would be parsed as the next request)."""
        headers = getattr(self, "headers", None)
        if headers is None:
            return
        try:
            n = int(headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        while n > 0:
            chunk = self.rfile.read(min(n, 65536))
            if not chunk:
                break
            n -= len(chunk)
        if headers.get("Transfer-Encoding", "").lower() == "chunked":
            self.close_connection = True

    def send_json(self, code, obj, head=False, extra=None):
        self._drain_body()
        body = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", MEDIA_TYPE)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        if CONFIG["transition_enabled"]:
            # The response depends on the Accept header on this instance only.
            self.send_header("Vary", "Accept")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        # Errors raised by the HTTP layer itself (malformed request line,
        # oversized headers, ...) are RDAP error objects too, never HTML.
        self.close_connection = True
        try:
            self.send_json(code, error_object(code, message or "Error",
                                              explain or message or "Request rejected."),
                           head=(getattr(self, "command", "") == "HEAD"))
        except Exception:
            pass

    def route(self):
        path = unquote(urlsplit(self.path).path)
        parts = [p for p in path.split("/") if p]
        headers = getattr(self, "headers", None)
        requested = requested_versions(headers.get_all("Accept") if headers else None)
        if parts == ["help"]:
            return 200, help_object()
        if CONFIG["assessor_only"] and len(parts) == 2 and parts[0] in ("domain", "entity"):
            # Assessment service mode: minimal response (Section 5.2).
            cls, key = parts
            k = key.lower() if cls == "domain" else key
            store = DATA["assessor_" + cls]
            if k in store:
                return 200, apply_versioning(with_links(store[k], f"/{cls}/{k}"), requested)
            return 404, error_object(404, "Not Found",
                                     f"No assessment for {cls} {key!r} at this service.")
        if len(parts) == 2 and parts[0] in ("domain", "entity"):
            cls, key = parts
            store = DATA[cls]
            k = key.lower() if cls == "domain" else key
            if k in store:
                obj = with_links(store[k], f"/{cls}/{k}")
                return 200, apply_versioning(apply_referral(obj, cls, k), requested)
            return 404, error_object(404, "Not Found",
                                     f"No {cls} object with key {key!r} on this server.")
        if len(parts) == 3 and parts[0] == "assessor" and parts[1] in ("domain", "entity"):
            # Assessment service configuration (v1 and -04, Section 5.2):
            # minimal response, binds the object, carries the member, nothing
            # else. Available only when the referral switch is on.
            if (not CONFIG["referral_enabled"] or CONFIG["assessor_external"]
                    or CONFIG["assessor_only"]):
                return 404, error_object(404, "Not Found",
                                         "No assessment service is simulated on this server.")
            cls, key = parts[1], parts[2]
            k = key.lower() if cls == "domain" else key
            store = DATA["assessor_" + cls]
            if k in store:
                return 200, apply_versioning(with_links(store[k], f"/assessor/{cls}/{k}"), requested)
            return 404, error_object(404, "Not Found",
                                     f"No assessment for {cls} {key!r} at this service.")
        if parts and parts[0] in ("domains", "entities", "nameserver", "nameservers",
                                  "ip", "autnum"):
            return 501, error_object(501, "Not Implemented",
                                     "This test server implements domain and entity lookup only.")
        return 404, error_object(404, "Not Found", "Unknown path.")

    def do_GET(self):
        code, obj = self.route()
        self.send_json(code, obj)

    def do_HEAD(self):
        code, obj = self.route()
        self.send_json(code, obj, head=True)

    def _not_allowed(self):
        # RFC 7480 Section 4.1: "Servers are under no obligation to support
        # other HTTP methods". The answer is still an RDAP error object.
        self.send_json(405, error_object(405, "Method Not Allowed",
                                         "This server supports GET and HEAD only."),
                       extra={"Allow": "GET, HEAD"})

    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _not_allowed


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "data"))
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--base-url", default=os.environ.get("RDAP_BASE_URL", "http://localhost:8080"))
    ap.add_argument("--referral", action="store_true",
                    default=os.environ.get("RDAP_REFERRAL", "0") == "1",
                    help="enable the -04 'referring to a service' arrangement (default off)")
    ap.add_argument("--assessor-base-url",
                    default=os.environ.get("RDAP_ASSESSOR_BASE_URL") or None,
                    help="base URL of the simulated assessment service "
                         "(default: <base-url>/assessor, same host: a simulation)")
    ap.add_argument("--assessor-only", action="store_true",
                    default=os.environ.get("RDAP_ASSESSOR_ONLY", "0") == "1",
                    help="run as an assessment service, not as an authoritative "
                         "server: /domain and /entity answer from data/assessor/")
    ap.add_argument("--versioning", action="store_true",
                    default=os.environ.get("RDAP_VERSIONING", "0") == "1",
                    help="enable Point Versioning (draft-ietf-regext-rdap-versioning-08) "
                         "as version " + EXTENSION_VERSION + " (default off)")
    ap.add_argument("--transition", action="store_true",
                    default=os.environ.get("RDAP_TRANSITION", "0") == "1",
                    help="experiment: the registered identifier stays opaque and "
                         "default, and a placeholder successor with Point Versioning "
                         "(" + SUCCESSOR_VERSION + ") is returned on request (default off)")
    ap.add_argument("--check", action="store_true", help="validate data and exit")
    args = ap.parse_args()

    CONFIG["base_url"] = args.base_url
    CONFIG["referral_enabled"] = args.referral
    CONFIG["assessor_base_url"] = args.assessor_base_url or args.base_url.rstrip("/") + "/assessor"
    CONFIG["assessor_external"] = bool(args.assessor_base_url)
    CONFIG["assessor_only"] = args.assessor_only
    CONFIG["versioning_enabled"] = args.versioning
    CONFIG["transition_enabled"] = args.transition
    CONFIG["data_dir"] = args.data
    try:
        load_data(args.data)
    except DataError as e:
        print(f"data error: {e}", file=sys.stderr)
        sys.exit(2)
    print(f"data OK: {len(DATA['domain'])} domains, {len(DATA['entity'])} entities, "
          f"referral {'ON' if args.referral else 'OFF'}"
          f"{', ASSESSMENT SERVICE mode' if args.assessor_only else ''}"
          f"{', versioning ON (' + EXTENSION_VERSION + ')' if args.versioning and not args.transition else ''}"
          f"{', TRANSITION experiment ON (' + SUCCESSOR_VERSION + ' on request)' if args.transition else ''}",
          file=sys.stderr)
    if args.check:
        return
    ThreadingHTTPServer.daemon_threads = True
    httpd = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"listening on {args.bind}:{args.port}, base URL {args.base_url}", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
