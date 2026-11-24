-- A pending outcome must not have a label.
-- Completed outcomes must have a valid binary label.

select
    as_of,
    ticker,
    label_status,
    label_drop_20pct_60d
from {{ ref('weekly_labels') }}
where
    (label_status = 'pending'
        and label_drop_20pct_60d is not null)
    or
    (label_status in ('final', 'truncated')
        and label_drop_20pct_60d is null)
