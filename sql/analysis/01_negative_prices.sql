-- Starter query: how often is the SA price negative, by hour of day (market time)?
-- Extend this in week 3: by month, by season, and against wind/solar output.

SELECT
    EXTRACT(HOUR FROM interval_start)::int                    AS hour_of_day,
    COUNT(*)                                                  AS intervals,
    COUNT(*) FILTER (WHERE rrp < 0)                           AS negative_intervals,
    ROUND(100.0 * COUNT(*) FILTER (WHERE rrp < 0) / COUNT(*), 1) AS pct_negative,
    ROUND(AVG(rrp), 2)                                        AS avg_rrp
FROM v_price
WHERE regionid = 'SA1'
GROUP BY 1
ORDER BY 1;
