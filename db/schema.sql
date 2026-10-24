-- All NEM timestamps are market time: AEST (UTC+10), no daylight saving.
-- SETTLEMENTDATE marks the END of a 5-minute dispatch interval, so
-- interval_start is derived for readability.

CREATE TABLE IF NOT EXISTS dispatch_price (
    settlementdate  TIMESTAMP     NOT NULL,
    interval_start  TIMESTAMP     GENERATED ALWAYS AS (settlementdate - INTERVAL '5 minutes') STORED,
    regionid        TEXT          NOT NULL,
    intervention    SMALLINT      NOT NULL DEFAULT 0,
    rrp             NUMERIC(12,5) NOT NULL,   -- regional reference price, $/MWh
    source          TEXT          NOT NULL,   -- 'nemosis' | 'nemweb'
    loaded_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    PRIMARY KEY (settlementdate, regionid, intervention)
);

CREATE TABLE IF NOT EXISTS dispatch_region (
    settlementdate       TIMESTAMP     NOT NULL,
    interval_start       TIMESTAMP     GENERATED ALWAYS AS (settlementdate - INTERVAL '5 minutes') STORED,
    regionid             TEXT          NOT NULL,
    intervention         SMALLINT      NOT NULL DEFAULT 0,
    totaldemand          NUMERIC(12,3),          -- MW
    availablegeneration  NUMERIC(12,3),          -- MW
    netinterchange       NUMERIC(12,3),          -- MW, positive = export
    source               TEXT          NOT NULL,
    loaded_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),
    PRIMARY KEY (settlementdate, regionid, intervention)
);

-- Which raw files have already been loaded, so daily runs are idempotent.
CREATE TABLE IF NOT EXISTS ingest_log (
    filename    TEXT        PRIMARY KEY,
    tables      TEXT[]      NOT NULL,
    row_count   INTEGER     NOT NULL,
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Prices for analysis. During an AEMO intervention two runs are published;
-- the market price is set by the non-intervention run (INTERVENTION = 0).
CREATE OR REPLACE VIEW v_price AS
SELECT settlementdate, interval_start, regionid, rrp
FROM dispatch_price
WHERE intervention = 0;
