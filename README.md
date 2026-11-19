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

**Status (19 November 2026):** four public test instances are online.
`https://rdap-test.bcsec.io/` is the instance shown at IETF 127 (November
2026), for example `https://rdap-test.bcsec.io/domain/assessed.example`.
`https://rdap-referral.bcsec.io/` runs the same server with the referral
arrangement on, and `https://rdap-assessor.bcsec.io/` runs it as the
assessment service the second one refers to (see below).
`https://rdap-experimental-opaque-to-point.bcsec.io/` is the only one that
implements extension versioning: it is an experiment on the transition from
Opaque to Point Versioning, in which the registered identifier stays under
Opaque Versioning and a placeholder successor identifier uses Point
Versioning (see below). All are test instances with fictional data; the
server can always be run locally as shown below. Questions and reports:
alessandro@bertoldicybersecurity.com.

## What it shows

* **Wire format** of the registered v1: identifier `reliabilityAssessment` in
  `rdapConformance`, member `reliabilityAssessment_results`, the nine fields
  with their types. The Internet-Draft defines the same wire format.
* **Deployment arrangement** of the Internet-Draft, Section 5.4: the server plays the
  server *authoritative* for a fictional zone and **carries the result** in its
  own response. The second arrangement, **referring to a service** through a
  link, is implemented behind a switch that is **off by default**, because the
  Internet-Draft does not fix the link relation and the v1 (Section 5.4) explains why
  reusing `related` is ambiguous. With the switch on, the assessment service
  is *simulated* under `<base>/assessor/` on the same host (`--assessor-base-url`
  moves it elsewhere): an assessment service is by definition a separate
  service, and neither document defines a path segment for it, so this is a
  convention of the prototype, labelled `[proto]` by the client.
* **Consumer rules**, applied and printed by the client with their origin:
  `[v1]` stated in the registered specification, `[draft]` stated only in the
  Internet-Draft, `[core]` RFC 7480 / RFC 9083 / draft-ietf-regext-rdap-extensions,
  `[proto]` a convention of this prototype that no document states.
* **Extension versioning** (`--versioning`, `RDAP_VERSIONING=1`, **off by
  default**): Point Versioning as described in
  [draft-ietf-regext-rdap-versioning-08](https://datatracker.ietf.org/doc/draft-ietf-regext-rdap-versioning/).
  The identifier in `rdapConformance` stays `reliabilityAssessment` and the
  member stays `reliabilityAssessment_results`; responses that carry the member
  add `versioning` to `rdapConformance` and a `versioning_data` member declaring
  version `reliabilityAssessment-0.1`, and the help response adds
  `versioning_help`. Version 0.1 is the wire format of the registered v1,
  unchanged, and the only version served. The registered specification and
  the Internet-Draft (Section 7.2 in each) declare Opaque Versioning, with
  extension version identifier `reliabilityAssessment`, and do not use Point
  Versioning: this instance shows what Point Versioning would look like, and
  is not a statement of either document. The client checks these members (`[ver]`), can ask
  for a version with `--versioning-list` (sent in the `Accept` header), and
  shows the help response with `help`.
* **Transition from Opaque to Point Versioning** (`--transition`,
  `RDAP_TRANSITION=1`, **off by default**): an experiment with Sections 4
  and 7.2 (step 1) of the same draft. The registered identifier
  `reliabilityAssessment` stays opaque and unchanged, and it is the default:
  a client that asks for nothing receives `reliabilityAssessment_results`.
  The same result is also offered, on request only, under a successor
  identifier that uses Point Versioning,
  `draftReliabilityAssessmentExperimental`, version
  `draftReliabilityAssessmentExperimental-0.1`, as
  `draftReliabilityAssessmentExperimental_results`: the same members
  and the same values, only the name changes. **The successor identifier is
  a placeholder, not a proposed name**: identifiers that start with `draft`
  are reserved for work in progress and cannot be registered
  (draft-ietf-regext-rdap-extensions, Section 2.2, "Syntax"). The help response
  relates the two with `successor`, `predecessor` and `default`. A client
  asks for the successor with
  `Accept: application/rdap+json;versioning_list=draftReliabilityAssessmentExperimental-0.1`
  (or the bare identifier, Section 5.1); a client that asks for both
  identifiers receives the result under both names: the versioning draft
  leaves the content of the response to server policy (Section 3.2), and
  returning both follows the transition example of
  draft-ietf-regext-rdap-extensions (Section 5.4.3.1, "Non-overlapping
  Superseders"), where a predecessor and its superseder are in use in the
  same response. Neither
  the registered specification nor the Internet-Draft defines a successor
  identifier: this instance is not a statement of either document. The
  client checks all of this with `transition`.

## Objects served (all fictional, under the reserved `.example` TLD)

| Lookup | Shows |
|---|---|
| `/domain/assessed.example` | domain with one result (draft Appendix C.1); its registrar is reachable through `entities` |
| `/entity/RAR1001` | registrar with results from two issuers, one under review (C.2) |
| `/entity/RAR1002` | registrar with an attestation carrying no score, past its `validUntil` (C.3) |
| `/domain/plain.example` | domain without the member: the client infers nothing (C.4) |
| `/domain/referred.example` | only with the referral switch on: a link to the assessment service, which answers with the minimal response of Section 5.2; its registrar is reachable through `entities` |
| `/domain/combined.example` | the two arrangements together: basic information in the authoritative response (the members fixed when a result is issued: scheme, issuer, value with its range, date, expiry) and, with the referral switch on, a link to the assessment service, which returns the full result; its registrar is reachable through `entities` |
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
internal port. Set `RDAP_REFERRAL=1` to enable the referral arrangement on
that instance. Set `RDAP_REFERRAL_HOST` as well to serve a second instance,
with the referral arrangement always on, under its own name:

```
RDAP_HOST=rdap-test.bcsec.io RDAP_REFERRAL_HOST=rdap-referral.bcsec.io docker compose up -d --build
```

Set `RDAP_ASSESSOR_HOST` to serve a third instance that plays the assessment
service (`--assessor-only`), and `RDAP_ASSESSOR_BASE_URL` to its public URL so
that the second instance links to it instead of simulating it under
`/assessor/`. Locally:

```
python3 server/rdap_ra_server.py --port 8081 --assessor-only --base-url http://localhost:8081
python3 server/rdap_ra_server.py --port 8080 --referral --base-url http://localhost:8080 --assessor-base-url http://localhost:8081
python3 client/rdap_ra_client.py http://localhost:8080 domain combined.example
```

Add `--versioning` to both servers (or `RDAP_VERSIONING=1`) to declare the
version; then, for example:

```
python3 client/rdap_ra_client.py http://localhost:8080 help
python3 client/rdap_ra_client.py http://localhost:8080 domain combined.example --versioning-list reliabilityAssessment-0.1
```

In the Compose file the switch is off for the first three instances. From
15 to 19 November 2026 it was on for `rdap-referral` and `rdap-assessor`, as
a trial that declared Point Versioning on the registered identifier; it was
turned off so that the public instances are consistent with each other: the
registered identifier is declared under Opaque Versioning wherever
versioning is declared, which is on the fourth instance only.

To try the transition experiment:

```
python3 server/rdap_ra_server.py --port 8082 --transition --base-url http://localhost:8082
python3 client/rdap_ra_client.py http://localhost:8082 transition
python3 client/rdap_ra_client.py http://localhost:8082 help
```

In the Compose file it runs as a fourth service, `rdap-experimental`, under
`RDAP_EXPERIMENTAL_HOST`; the other three services do not set the switch.

## Design choices

* Standard library only, so the whole thing can be read in one sitting.
* Read-only: responses are static JSON files under `server/data/`. There is no
  interface to create or modify results (the extension defines none).
* Every data file is validated at start-up against the rules of the v1 and of
  the Internet-Draft (`--check` validates and exits), plus two hygiene rules of the
  prototype that the documents do not state (no unknown member in a result; a
  lookup response does not advertise the extension without carrying the
  member). A file that breaks a rule stops the server from starting.
* `GET` and `HEAD` only (other methods get 405); `application/rdap+json`
  everywhere; every error, including those raised by the HTTP layer or by the
  reverse proxy, is an RDAP error object, never HTML.

## License

BSD 2-Clause. The specification itself is published separately under CC BY 4.0;
the Internet-Draft is subject to the IETF Trust Legal Provisions.
