# rdap-reliability-assessment-prototype

Prototype server and client for the RDAP extension **`reliabilityAssessment`**,
registered in the IANA RDAP Extensions Registry on 6 October 2026 against the
specification [bcsec-RDAP-RA, Version 1](https://bcsec.io/rdap/v1/bcsec-rdap-reliability-assessment.txt).
The same extension is the subject of the Internet-Draft
[draft-bertoldi-regext-rdap-reliability-scoring](https://datatracker.ietf.org/doc/draft-bertoldi-regext-rdap-reliability-scoring/)
(REGEXT, individual submission).

Written by the author of the specification. It exists so that the extension
can be seen on the wire, and so that the consumer rules in the documents can
be seen applied. It is not a production RDAP server.

**Status (14 October 2026):** a public test instance is online at
`https://rdap-test.bcsec.io/` for IETF 127 (14-20 November 2026), for
example `https://rdap-test.bcsec.io/domain/assessed.example`. It is a
temporary instance and may be withdrawn after the meeting; the server can
always be run locally as shown below. Questions and reports:
alessandro@bertoldicybersecurity.com.

## What it shows

* **Wire format** of the registered v1: identifier `reliabilityAssessment` in
  `rdapConformance`, member `reliabilityAssessment_results`, the nine fields
  with their types. The -04 defines the same wire format.
* **Deployment arrangement** of the -04, Section 5.4: the server plays the
  server *authoritative* for a fictional zone and **carries the result** in its
  own response. The second arrangement, **referring to a service** through a
  link, is implemented behind a switch that is **off by default**, because the
  -04 does not fix the link relation and the v1 (Section 5.4) explains why
  reusing `related` is ambiguous. With the switch on, the assessment service
  is *simulated* under `<base>/assessor/` on the same host (`--assessor-base-url`
  moves it elsewhere): an assessment service is by definition a separate
  service, and neither document defines a path segment for it, so this is a
  convention of the prototype, labelled `[proto]` by the client.
* **Consumer rules**, applied and printed by the client with their origin:
  `[v1]` stated in the registered specification, `[-04]` stated only in the
  draft, `[core]` RFC 7480 / RFC 9083 / draft-ietf-regext-rdap-extensions,
  `[proto]` a convention of this prototype that no document states.

## Objects served (all fictional, under the reserved `.example` TLD)

| Lookup | Shows |
|---|---|
| `/domain/assessed.example` | domain with one result (draft Appendix C.1); its registrar is reachable through `entities` |
| `/entity/RAR1001` | registrar with results from two issuers, one under review (C.2) |
| `/entity/RAR1002` | registrar with an attestation carrying no score, past its `validUntil` (C.3) |
| `/domain/plain.example` | domain without the member: the client infers nothing (C.4) |
| `/domain/referred.example` | only with the referral switch on: a link to the assessment service, which answers with the minimal response of Section 5.2 |
| `/help` | server notices |

No real registrar or domain is assessed. See Sections 8, 11 and 12 of the
specification for why that matters.

## Run locally

Python 3.9 or later, standard library only.

```
python3 server/rdap_ra_server.py --port 8080
python3 client/rdap_ra_client.py http://localhost:8080 selftest
python3 client/rdap_ra_client.py http://localhost:8080 domain assessed.example
python3 client/rdap_ra_client.py http://localhost:8080 entity RAR1002
```

The client also works against any RDAP server; where the member is absent it
says so and infers nothing:

```
python3 client/rdap_ra_client.py --url https://rdap.verisign.com/com/v1/domain/example.com
```

Against the public test instance:

```
python3 client/rdap_ra_client.py https://rdap-test.bcsec.io selftest
```

Referral switch: `python3 server/rdap_ra_server.py --referral --base-url http://localhost:8080`.

## Run with Docker, with HTTPS

```
cd deploy
RDAP_HOST=rdap-test.bcsec.io docker compose up -d --build
```

Caddy obtains the certificate from Let's Encrypt; the DNS name must point at
the host first. Only Caddy is exposed (80/443); the RDAP server listens on an
internal port. Set `RDAP_REFERRAL=1` to enable the referral arrangement.

## Design choices

* Standard library only, so the whole thing can be read in one sitting.
* Read-only: responses are static JSON files under `server/data/`. There is no
  interface to create or modify results (the extension defines none).
* Every data file is validated at start-up against the rules of the v1 and of
  the -04 (`--check` validates and exits), plus two hygiene rules of the
  prototype that the documents do not state (no unknown member in a result; a
  lookup response does not advertise the extension without carrying the
  member). A file that breaks a rule stops the server from starting.
* `GET` and `HEAD` only (other methods get 405); `application/rdap+json`
  everywhere; every error, including those raised by the HTTP layer or by the
  reverse proxy, is an RDAP error object, never HTML.

## License

BSD 2-Clause. The specification itself is published separately under CC BY 4.0;
the Internet-Draft is subject to the IETF Trust Legal Provisions.
