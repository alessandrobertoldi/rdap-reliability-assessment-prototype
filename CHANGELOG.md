# Changelog

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
