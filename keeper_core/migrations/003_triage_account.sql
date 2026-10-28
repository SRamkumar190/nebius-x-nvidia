-- A product database is scoped to one verified demo Gmail account.
CREATE TABLE triage_account (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    account TEXT NOT NULL
);
