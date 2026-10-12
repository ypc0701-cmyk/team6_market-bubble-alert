-- A ticker may not have two membership spans in force on the same date, in any basket.
-- Also enforces "no name sits in both baskets at once" [M §4].
with spans as (
    select ticker, added_date, coalesce(removed_date, date '9999-12-31') as removed_date
    from {{ ref('basket_members') }}
)
select a.ticker, a.added_date as span_a, b.added_date as span_b
from spans a
join spans b
  on a.ticker = b.ticker
 and a.added_date < b.added_date
 and b.added_date < a.removed_date
