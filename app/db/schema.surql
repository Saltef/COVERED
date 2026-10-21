-- Covered — SurrealDB schema with ROW-LEVEL SECURITY (defense-in-depth).
-- Namespace / database: covered / covered.
--
-- A verified Clerk identity is placed into $auth (user id + role) at sign-in. These table
-- PERMISSIONS enforce ownership IN THE DATABASE, so even an app-layer mistake cannot leak
-- one person's record to another. The application layer enforces the same rule (app/security/rls.py).

-- ---- person: a screening subject's profile (PII-minimized) ----
DEFINE TABLE person SCHEMALESS
  PERMISSIONS
    FOR select, update, delete WHERE owner = $auth.id OR $auth.role = "admin"
    FOR create WHERE owner = $auth.id;

DEFINE FIELD owner      ON person TYPE string;
DEFINE FIELD first_name ON person TYPE option<string>;
DEFINE FIELD province   ON person TYPE string;
DEFINE FIELD created_at ON person TYPE datetime DEFAULT time::now();

-- ---- screening: a saved screening result for a person ----
DEFINE TABLE screening SCHEMALESS
  PERMISSIONS
    FOR select, update, delete WHERE owner = $auth.id OR $auth.role = "admin"
    FOR create WHERE owner = $auth.id;

DEFINE FIELD owner      ON screening TYPE string;
DEFINE FIELD created_at ON screening TYPE datetime DEFAULT time::now();

-- ---- access_grant: least-privilege caregiver access (grantor shares with grantee) ----
DEFINE TABLE access_grant SCHEMALESS
  PERMISSIONS
    FOR select WHERE grantor = $auth.id OR grantee = $auth.id OR $auth.role = "admin"
    FOR create, update, delete WHERE grantor = $auth.id;

DEFINE FIELD grantor ON access_grant TYPE string;
DEFINE FIELD grantee ON access_grant TYPE string;
DEFINE FIELD scope   ON access_grant TYPE string DEFAULT "read";

-- ---- audit_log: who accessed whose record (append-only) ----
DEFINE TABLE audit_log SCHEMALESS
  PERMISSIONS
    FOR select WHERE actor = $auth.id OR $auth.role = "admin"
    FOR create WHERE actor = $auth.id;

DEFINE FIELD actor      ON audit_log TYPE string;
DEFINE FIELD action     ON audit_log TYPE string;
DEFINE FIELD subject    ON audit_log TYPE option<string>;
DEFINE FIELD at         ON audit_log TYPE datetime DEFAULT time::now();

-- ---- program catalogue + the DTC unlock chain as a graph (public, read-only) ----
DEFINE TABLE program SCHEMALESS PERMISSIONS FOR select FULL;
DEFINE FIELD name         ON program TYPE string;
DEFINE FIELD jurisdiction ON program TYPE string;

-- graph edges: program ->unlocks-> program  (e.g. dtc -> cdb, dtc -> rdsp, dtc -> cdcp)
DEFINE TABLE unlocks TYPE RELATION FROM program TO program
  PERMISSIONS FOR select FULL;
