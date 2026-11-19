# Changelog

## Deployment change (2026-11-19), no new version

* Compose file: `RDAP_VERSIONING` is no longer set for `rdap-referral` and
  `rdap-assessor`. Their responses no longer carry `versioning`,
  `versioning_data` or `versioning_help`, and the help response no longer
  carries the notice on extension versioning. Everything else in their
  responses is unchanged.
* Reason: with that switch the registered identifier `reliabilityAssessment`
  was declared with Point Versioning (`reliabilityAssessment-0.1`), a trial
  of 15 November 2026, while the fourth instance declares the same identifier
  with Opaque Versioning and keeps Point Versioning for a successor
  identifier. The public instances now agree: extension versioning is shown
  by the fourth instance only.
* No change to the server or to the client: the `--versioning` switch still
  exists and is off by default. The first and the fourth instance are not
  affected.

## 0.5.0 (2026-11-16)

Experiment: transition from Opaque to Point Versioning, behind a second
switch that is off by default.

* Server: `--transition` (`RDAP_TRANSITION=1`) follows Sections 4 and 7.2
  (step 1) of draft-ietf-regext-rdap-versioning-08. The registered identifier
  `reliabilityAssessment` is declared with Opaque Versioning and is the
  default; a successor identifier with Point Versioning,
  `draftReliabilityAssessmentExperimental`, version
  `draftReliabilityAssessmentExperimental-0.1`, is returned only on request.
  The successor identifier is a placeholder, not a proposed name: identifiers
  starting with `draft` are reserved for work in progress and cannot be
  registered (draft-ietf-regext-rdap-extensions-18, Section 2.2).
* What a client receives: nothing asked, the registered identifier asked, or
  only unsupported versions asked: `reliabilityAssessment_results`. The
  successor asked, by version or by bare identifier (Section 5.1):
  `draftReliabilityAssessmentExperimental_results`, with the same
  members and the same values. Both asked: the result under both names; the
  versioning draft does not cover this case and the choice is the
  prototype's. `rdapConformance` and `versioning_data` list what the response
  uses. The member is renamed at every depth of nested `entities`. Responses
  without the member are unchanged. Responses of this instance carry
  `Vary: Accept`.
* Help response with the switch on: `versioning_help` relates the two
  identifiers with `successor`, `predecessor` and `default`. The two opaque
  entries, `rdap_level_0` and the registered identifier, each carry a single
  `versions` object equal to the identifier, as the text of Section 5.1.2
  says (Figures 6 and 11 of the draft omit it). A notice describes the
  experiment.
* The server now reads the `versioning_list` parameter of the `Accept`
  header, on the media type `application/rdap+json` only and not on a range
  refused with `q=0`. It is used only with the transition switch on: with that switch
  off the server has one version of each extension and the parameter does
  not change any response, as before.
* Client: new `transition` command (18 checks); a `versioning_data` entry for
  the extension with type `opaque` is now checked against Section 5.1.1
  instead of being reported as not a point version; a response that carries
  the result only under the successor name is shown and checked with the
  same rules as the registered member, with a note saying so.
* Deployment: a fourth Compose service, `rdap-experimental`, under
  `RDAP_EXPERIMENTAL_HOST`, and its block in the Caddyfile. The other three
  services do not set the switch.
* With the transition switch off, responses are unchanged: compared with
  0.4.2 in the three existing configurations (plain, referral with
  versioning, assessment service with versioning) on every path, with GET,
  HEAD and POST and with seven `Accept` values, 945 comparisons, no
  difference in status, headers (other than `Date` and `Server`) or body.
  The `Server` header carries the new version number; the deployed proxy
  removes that header.

## 0.4.2 (2026-11-15)

* Data: `combined.example` and `referred.example` now carry their registrar
  in `entities` (`RAR1001` and `RAR1002`, with role, IANA Registrar ID and a
  `self` link), as `assessed.example` and `plain.example` already did, so
  that every authoritative domain response shows a complete object. The
  assessment service responses are unchanged: they stay minimal.
* No change to the code paths, to the extension member or to any other
  response: compared with the previous data on every object and in the
  three configurations, the only difference is the added `entities` member
  on these two objects.

## 0.4.1 (2026-11-15)

* Server: the help notice on extension versioning now states what the
  documents say, instead of only what they do not say. The registered
  specification and the Internet-Draft (Section 7.2 in each) declare Opaque
  Versioning, with extension version identifier `reliabilityAssessment`, and
  do not use Point Versioning; the instance shows what Point Versioning would
  look like and is not a statement of either document. Same wording in the
  README.
* No other change. Responses are unchanged except for that notice, which
  appears only with the versioning switch on. The client is unchanged.

## 0.4.0 (2026-11-15)

Extension versioning, behind a switch that is off by default.

* Server: `--versioning` (`RDAP_VERSIONING=1`) implements Point Versioning as
  described in draft-ietf-regext-rdap-versioning-08. Responses that carry the
  member (at the top level or in a nested entity) add `versioning` to
  `rdapConformance`, right after `rdap_level_0`, and a `versioning_data`
  member listing `rdap_level_0`, `versioning-0.9` and
  `reliabilityAssessment-0.1`. The help response adds `versioning_help`, with
  one default version per extension, and a notice describing the switch.
  Responses without the member, and error objects, are unchanged.
* The extension identifier stays `reliabilityAssessment` and the member stays
  `reliabilityAssessment_results`. Version 0.1 is the wire format of
  bcsec-RDAP-RA Version 1, unchanged; it is the only version and the default.
  A version asked for in the `Accept` header (`versioning_list`) that the
  server does not support is ignored, as the versioning draft requires.
* With the switch off every response is unchanged: compared with 0.3.1 on
  every path, for GET, HEAD and POST, with and without an `Accept` header
  carrying `versioning_list`, in the three configurations (status, headers
  other than `Server` and `Date`, body): no difference.
* Client: rules tagged `[ver]` check `versioning`, `versioning_data` and the
  Point Extension Version Identifier when a server declares versioning; a
  server that does not is not at fault. New command `help` checks
  `versioning_help`. `--versioning-list` sends the `versioning_list`
  parameter in the `Accept` header.
* Deployment: the switch is on for `rdap-referral` and `rdap-assessor`, off
  for the first instance.
* The four reference cases of the self-test are unchanged and pass with the
  switch on and off.

## 0.3.1 (2026-11-13)

* Server: the help response names the Internet-Draft without a revision
  number (it said -04; Section 5.4 is the same section in the -05).
* Data: in `combined.example` and `referred.example` the issuer identifier
  is the URL of the assessment service the link points to, and the scheme
  and evidence identifiers are URIs under the same name.
* Data: the basic information carried by the authoritative response for
  `combined.example` now includes `validUntil`. It consists of the members
  fixed when a result is issued; `status`, which can change afterwards,
  and the detail stay with the assessment service. The help responses say so.

## 0.3.0 (2026-11-13)

The assessment service becomes a separate server, so that the referral
crosses two services for real.

* Server: `--assessor-only` (`RDAP_ASSESSOR_ONLY=1`) runs the program as an
  assessment service. It is not authoritative: `/domain/<name>` and
  `/entity/<handle>` answer from `data/assessor/` with the minimal response
  of Section 5.2, and its help response says so.
* Server: when `--assessor-base-url` (`RDAP_ASSESSOR_BASE_URL`) is set, the
  referral link points at that service and the local `/assessor/` simulation
  is switched off; the help notice names the service. Without it, behaviour
  is as in 0.2.0.
* Client: a referral link to an assessment service on another host is
  recognised by the title the test server gives it (prototype convention).
* Deployment: Compose service `rdap-assessor` and a third site block in the
  Caddyfile, selected by `RDAP_ASSESSOR_HOST`.
* The four reference cases of the self-test are unchanged and pass in all
  configurations.

## 0.2.0 (2026-11-13)

A second public instance with the referral arrangement on, and an object
that combines the two arrangements of Section 5.4.

* Data: new fictional domain `combined.example`. The authoritative response
  carries a result with basic information only (`scoreScheme`, `scoreIssuer`,
  `scoreValue` with `scoreMaxValue`, `scoreDate`); with the referral switch
  on it also carries the link to the assessment service, which returns the
  full result (`validUntil`, `assessmentId`, `status`, `evidenceUri`). With
  the switch off the object is served without the link.
* Server: with the referral switch on, the help response has a third notice
  saying that the link relation `related` is a placeholder of this prototype
  and describing `referred.example` and `combined.example`.
* Deployment: Compose service `rdap-referral` (same image, referral always
  on) and a second site block in the Caddyfile, selected by
  `RDAP_REFERRAL_HOST`. The first instance is unchanged: referral off unless
  `RDAP_REFERRAL=1`.
* The four reference cases of the self-test are unchanged and pass with the
  switch on and off.

## 0.1.3 (2026-10-14)

Deployment hardening after a security review of the public test instance.

* Caddy: read/idle timeouts and a 16 KB header limit (slow or oversized
  requests are refused early); request body limited to 4 KB;
  `Referrer-Policy` and a restrictive `Content-Security-Policy`; HTTP/3 port
  (443/udp) actually published, so the advertised `alt-svc` is consistent;
  image pinned to the 2.11 line.
* Compose: both containers drop all capabilities (Caddy keeps
  `NET_BIND_SERVICE`), run with `no-new-privileges`, and have memory and PID
  limits; log rotation for both.
* Server: idle socket timeout of 15 s; handler threads are daemon threads.
* Host (not in this repository): SSH key-only with root login disabled,
  ufw allowing 22/80/443 only, fail2ban on SSH, full package upgrade.


## 0.1.2 (2026-10-14)

Result of an adversarial conformance review against the v1, the -04,
RFC 7480, RFC 9083 and draft-ietf-regext-rdap-extensions.

* Server: the two links in the help response now carry the `value` member,
  which RFC 9083 Section 4.2 requires together with `rel` and `href`.
* Server: request bodies are drained, so a POST with a body no longer leaves
  bytes on a keep-alive connection for the next request; methods other than
  GET and HEAD get a 405 RDAP error object with `Allow`; errors raised by the
  HTTP layer (malformed request line, unsupported version) are RDAP error
  objects too, never HTML.
* Server: strict RFC 3339 parsing (seconds required, leap second accepted);
  `evidenceUri` validated as a URI; a `withdrawn` result may coexist with its
  replacement (Section 7.6), the one-current-result rule of Section 7.4 now
  ignores withdrawn results; missing `ldhName`/`handle` is a data error.
* Server: the simulated assessment service used by the referral switch is
  documented as a prototype convention and can be moved to another base URL
  (`--assessor-base-url` / `RDAP_ASSESSOR_BASE_URL`).
* Client: unknown members inside a result are ignored, as rdap-extensions
  Section 2.4.1 requires of clients, instead of being reported as a `[v1]`
  violation; JSON types are checked before comparisons; the extension listed
  in `rdapConformance` without the member (a help response) is no longer a
  violation; two notes wrongly labelled `[v1]` are now `[-04]` (attestation
  without a score; result with no date); the referral heuristic is labelled
  `[proto]`; violations of the referring response are counted when a referral
  is followed; strict RFC 3339 parsing.
* Data: the registrar nested in a domain response links to itself with
  `rel` `self`.
* Caddy: search and other core paths are proxied so the server's own 501
  answers them; Caddy's own errors are RDAP error objects (`handle_errors`);
  CORS header on the fallback 404.

## 0.1.0 (2026-10-14)

First public version, written for the REGEXT session at IETF 127
(San Francisco, 14-20 November 2026).

* Test RDAP server carrying `reliabilityAssessment` (registered in the IANA
  RDAP Extensions Registry on 6 October 2026). Wire format of bcsec-RDAP-RA
  Version 1; deployment arrangement of draft-bertoldi-regext-rdap-reliability-scoring-04,
  Section 5.4 ("carrying the result"). The "referring to a service" arrangement
  is implemented behind a switch that is off by default.
* Client that applies the consumer rules of the specification and prints the
  origin of each rule (`[v1]`, `[-04]`, `[core]`); `selftest` mode covering the
  four reference cases of the draft's Appendix C plus an error-object check.
* Fictional data only, under the reserved `.example` TLD.

## 0.1.1 (2026-10-14)

* Public test instance online at `https://rdap-test.bcsec.io/`; README
  updated accordingly.
* Caddy: the 404 returned for paths outside the prototype now carries
  `Content-Type: application/rdap+json`, like every other response.

## 0.1.0 (2026-10-14)

First public version, written for the REGEXT session at IETF 127
(San Francisco, 14-20 November 2026).

* Test RDAP server carrying `reliabilityAssessment` (registered in the IANA
  RDAP Extensions Registry on 6 October 2026). Wire format of bcsec-RDAP-RA
  Version 1; deployment arrangement of draft-bertoldi-regext-rdap-reliability-scoring-04,
  Section 5.4 ("carrying the result"). The "referring to a service" arrangement
  is implemented behind a switch that is off by default.
* Client that applies the consumer rules of the specification and prints the
  origin of each rule (`[v1]`, `[-04]`, `[core]`); `selftest` mode covering the
  four reference cases of the draft's Appendix C plus an error-object check.
* Fictional data only, under the reserved `.example` TLD.
* Docker image and a Caddy-based deployment with automatic TLS.
