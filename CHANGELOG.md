# Changelog

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
