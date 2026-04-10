-- Run this script once in your MySQL database (DB: dump) to create the CodePad tables.
-- Safe to run multiple times (uses IF NOT EXISTS).

USE dump;

CREATE TABLE IF NOT EXISTS code_snippet (
    id              INT             NOT NULL AUTO_INCREMENT,
    authuser_id     INT             NOT NULL,
    title           VARCHAR(255)    NOT NULL DEFAULT 'Untitled',
    description     TEXT            NULL,
    language        VARCHAR(50)     NOT NULL DEFAULT 'python',
    code            LONGTEXT        NOT NULL DEFAULT '',
    test_cases      JSON            NULL,
    execution_timeout INT           NOT NULL DEFAULT 5,
    is_shared       TINYINT(1)      NOT NULL DEFAULT 0,
    shared_with     JSON            NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_executed_at TIMESTAMP      NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_cs_authuser FOREIGN KEY (authuser_id) REFERENCES authuser(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS code_execution_log (
    id                  INT         NOT NULL AUTO_INCREMENT,
    code_snippet_id     INT         NULL,
    authuser_id         INT         NOT NULL,
    language            VARCHAR(50) NOT NULL,
    code_executed       LONGTEXT    NOT NULL,
    input_data          TEXT        NULL,
    output              LONGTEXT    NULL,
    error               LONGTEXT    NULL,
    execution_time_ms   INT         NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'error',
    created_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT fk_cel_snippet  FOREIGN KEY (code_snippet_id) REFERENCES code_snippet(id)  ON DELETE SET NULL,
    CONSTRAINT fk_cel_authuser FOREIGN KEY (authuser_id)     REFERENCES authuser(id)       ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Verify
SELECT 'code_snippet table:'      AS info, COUNT(*) AS rows FROM code_snippet;
SELECT 'code_execution_log table:' AS info, COUNT(*) AS rows FROM code_execution_log;
