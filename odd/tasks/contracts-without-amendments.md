# Contracts without amendments

UPDS Cobija does not use contract amendments ("adendas"). Every change issues the complete contract.
Branch `feat/contracts-without-amendments` from `d89fbcd`. Production: SIPAD VPS, deploy via `ssh sipad-deploy@31.97.129.151 "plan|deploy <sha>"`.

## Specs

- S1: "no quiero nada de contratos de adenda porque no es algo que se ocupe en la upds cobija." Every new contract version for a teacher (load change, name, CI, department, template, terms, comitente) is the complete contract (all lines `full`, full legal PDF); no one-page or delta amendment PDF is ever produced.
- S2: Existing adendas — user chose "Borrarlas de la base": "Las elimino con un respaldo previo y renumero las versiones. Es irreversible sin ese respaldo y rompe la cadena del historial." Production holds 67 one-page name adendas (II/2026, sequence 2 / "versión 3", issued 2026-11-06); each is followed by a full reissue (sequence 3). Delete the 67 with a prior backup and renumber the following versions so each history stays contiguous and valid.
- S3: Version names — user chose "\"Versión N\" (recomendado)": "\"Original\" para el primero y \"Versión 2\", \"Versión 3\"… para los siguientes. Saco la palabra \"Enmienda\" de la pantalla de contratos."
- S4: Teacher left without load — user chose "No emitir nada (recomendado)": "Avisa \"el docente no tiene carga efectiva\" y su último contrato queda como está."

## Tasks

- T1 (S1, S4) backend: always reissue the complete contract; refuse empty load with existing history; tests. Route: inline (workers unavailable). Commit: 5e7d209 — done
- T2 (S3) frontend: "Original" / "Versión N" labels, no "Enmienda" wording on the contracts page. Route: inline (workers unavailable). Commit: 631f549 — done
- T3 (S2) production data: backup, delete 67 adendas, renumber successors, verify. Route: parent, BEFORE the T1/T2 deploy (verifier: version-bound digests make renumbering after new issuances unsafe). Commit: n/a (data operation) — done 2026-11-07
- T4 verify + PR + deploy + close. PRs #200, #201 (master 8ca9b28), deployed 2026-11-07 01:22Z — done

## Log

- L1: "ok perfecto ahora no quiero nada de contratos de adenda porque no es algo que se ocupe en la upds cobija."
- L2: User answers: adendas viejas → "Borrarlas de la base"; nombre → "\"Versión N\" (recomendado)"; sin carga → "No emitir nada (recomendado)".
- L3: Evidence 2026-11-07: production has 460 II/2026 documents, 67 adendas (all name-only, none current); UI labels every later version "Enmienda N".
- L4: T1/T2 evidence: backend full suite 1568 passed, 67 skipped; frontend tsc 0 errors, vite build OK, eslint OK, check-contracts-view 11/11. Design note: idempotency compares only the latest document; a load returning to an earlier state is issued again with digest sha256(snapshot:reissue:sequence). User-visible messages changed from adenda/enmienda to "nueva versión del contrato".
- L5: Independent verify PASS (S1, S3, S4; production history safe). Its 9 probe tests were lost with its scratch dir; not committed.
- L6: T3 applied 2026-11-07 ~01:25Z on production with code d89fbcd still live. Backup pg_dump -Fc sha256 fa2e1cf464b0d90554f8231696bd7612c78c86ec23fad9e2139bdca1bc4516a4 at VPS ~/sipad-backups/pre-delete-adendas-20261107T011814Z.dump and local /home/pedro/backups/sipad/pre-delete-adendas-20261107T011814Z/ (with the SQL). One transaction: immutable triggers disabled only inside it, 67 successors relinked to their pre-adenda predecessor, 67 adendas deleted, successors renumbered 3→2 and filenames _v4→_v3, triggers re-enabled, contiguity and current-name checks passed; rehearsed with ROLLBACK first. Result: 460→393 documents, 0 without lines, 0 non-full lines; API history 393 (v1 161, v2 161, v3 71); batch re-issue of 10 affected teachers returned their v3 with no new rows.
- L7: Post-deploy 8ca9b28: batch of all 164 teachers returned 161 existing contracts in 15 s, 3 "no tiene carga efectiva" errors, 393 documents unchanged; live bundle shows "Versión"/"Versiones posteriores" and no "Enmienda". Independent production verify PASS on S1-S4 (393 documents all complete, contiguous histories, backup holds 460 rows).
- L8: User: "ok ahora resuelve los pendientes menos el cambio de passwd que eso lo hare yo". Follow-up: permanent tests for legacy load amendments (changed/added/removed) replaced once by the complete contract and for the renumbered production name reissue; removed the unreachable adenda PDF renderer.
