# Member D integration checkpoint

Existing D tables and IDs retained. Revision 0002 adds compatible C fields and aliases; it does not claim exact C physical schema equivalence (names, lengths, constraints, mandatory goal dates and relationships differ). Existing rows receive migration-time created_at, not historical timestamps. Coordinate canonical schema with C before production. No data reset.

Forecast: existing C projecttt.py wrapped in Docker with health endpoint; optional statistical packages not installed, so baseline fallback may be used. Host 8002, container 8000. A final V2 feature builder/model/API missing: fraud scoring deliberately remains pending, no fabricated results. Advisor requires configured provider. Dataset V3 validation, performance, full E2E, CI and demo recording remain pending. No push performed.

Run docker compose up -d --build --wait backend ml-forecast frontend; check alembic current/check, backend pytest, forecast health and browser flows. Use existing PostgreSQL backup. Do not delete volumes. Review git diff before committing.
