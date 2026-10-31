# Work Log — Project 1

Keep this dated and honest. Mentors grade "problem-solving & independence" from entries like these.

| Date | Hours | Work done | Problems & how solved | Next |
|---|---|---|---|---|
| 2026-10-15 | | Read the handbook. Chose AWS + FastAPI. Wrote requirements, data model and API. Implemented products/orders with validation and row locking. 35 tests, 97% coverage | `cfn-lint` rejected Postgres `EngineVersion "16"`, so I omitted it (D15). Realised RDS rotates managed passwords every 7 days, so I added per-connection credential refresh + retry (D7) | Push to GitHub, deploy to AWS |
| 2026-10-31 | | Pushed to GitHub. Deployed the stack to ap-south-1 (~17 min). Cloud smoke test 13/13 PASS | First deploy rolled back: the AWS free plan rejects 7-day RDS backup retention. Made retention a parameter (default 1 day) and redeployed (D16) | Screenshots, video, drills |
| | | Cloud smoke test, dashboard + alarm test screenshots (evidence C1–C6) | | |
| | | Security evidence (C7–C9), restore drill (C10–C11) | | |
| | | Presentation + demo rehearsal. Teardown | | |
