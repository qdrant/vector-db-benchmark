CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE items (
    id SERIAL PRIMARY KEY,
    embedding vector(100) NOT NULL
);
