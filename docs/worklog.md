# Work Log — Project 1

Keep this dated and honest. Mentors grade "problem-solving & independence" from entries like these.

| Date | Hours | Work done | Problems & how solved | Next |
|---|---|---|---|---|
| 2026-10-15 | | Read the handbook. Chose AWS + FastAPI. Wrote requirements, data model and API. Implemented products/orders with validation and row locking. 35 tests, 97% coverage | `cfn-lint` rejected Postgres `EngineVersion "16"`, so I omitted it (D15). Realised RDS rotates managed passwords every 7 days, so I added per-connection credential refresh + retry (D7) | Push to GitHub, deploy to AWS |
| | | Deploy stack with `deploy.ps1`. Confirm the SNS email | | |
| | | Cloud smoke test, dashboard + alarm test screenshots (evidence C1–C6) | | |
| | | Security evidence (C7–C9), restore drill (C10–C11) | | |
| | | Presentation + demo rehearsal. Teardown | | |
