DROP TABLE IF EXISTS conversation;

CREATE TABLE conversation (
  id TEXT PRIMARY KEY,
  history TEXT NOT NULL
);
