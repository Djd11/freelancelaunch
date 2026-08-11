# Supabase Setup — dedicated project for the Sprint Platform

> **Rule: the Sprint Platform uses its OWN Supabase project.** It must never share a
> database with the v1 FreelanceLaunch app. `db/schema.sql` enforces this with a
> guard that aborts if v1 tables are detected.

## Why a separate project
The new schema **collides by name** with v1 tables:

| Collision | v1 schema.sql / schema_v2.sql | Sprint Platform |
|---|---|---|
| `cohorts` | v1 cohorts (topic-scoped) | sprint cohorts (cluster-scoped, batch dates) |
| `contracts` | v1 contract tracker (pipeline_id FK) | sprint-scoped contracts |
| `sprints` | v1 sprint track tables | sprint platform sprints |
| `proposals` | v1 sprint proposals | sprint platform proposals |
| `job_feed` | v1 sprint job feed | sprint platform job feed |
| `badges` / `mentor` | v1 sprint tables | sprint platform badges / mentor_sessions |

Same names, different shapes → applying both to one database = corruption.

## 1. Create the new project
1. Go to [supabase.com](https://supabase.com/dashboard) → **New project**.
2. Name it e.g. `sprint-platform-<env>` (dev / prod). Do NOT select the v1 project.
3. Note the **Project URL** and the **anon** + **service_role** keys
   (Project Settings → API).
4. Save them to `.env` (copy from `.env.example`).

## 2. Apply the schema
1. Open the new project's **SQL Editor**.
2. Paste the contents of `db/schema.sql` and run.
3. The guard at the top will **abort with an exception** if it detects v1 tables —
   if that happens, you are in the wrong project.
4. Verify: the tables `sprints`, `job_clusters`, `proposals`, `contracts`,
   `badges`, `mentor_sessions`, and the view `public_freelancers` exist.

## 3. Auth
- Enable **Email** provider under Authentication → Providers.
- (Later) add Google/GitHub when the client-facing profile needs it.

## 4. Connection checklist (before any app code)
- [ ] `SUPABASE_URL` points to the **new** project (not `freelancelaunch`'s)
- [ ] `SUPABASE_SERVICE_ROLE_KEY` is the **new** project's key
- [ ] `db/schema.sql` ran cleanly in the new project
- [ ] `select * from sprints limit 1;` returns "0 rows" (not "relation does not exist")

## Teardown (if you ever stop using it)
- Pause/delete the project from the Supabase dashboard. The v1 project is untouched.
