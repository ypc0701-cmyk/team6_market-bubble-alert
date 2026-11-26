-- A ticker cannot have overlapping membership spans.
select
    ticker,
    added_date,
    removed_date
from (
    select
        ticker,
        added_date,
        removed_date,
        lag(coalesce(removed_date, date '9999-12-31')) over (
            partition by ticker
            order by added_date
        ) as previous_end
    from {{ ref('universe_members') }}
)
where previous_end > added_date
