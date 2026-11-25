-- Universe membership must never overlap with the speculative basket.
select
    u.ticker,
    u.added_date,
    u.removed_date
from {{ ref('universe_members') }} u
join {{ ref('basket_members') }} b
    on u.ticker = b.ticker
    and b.basket = 'speculative'
    and u.added_date < coalesce(b.removed_date, date '9999-12-31')
    and b.added_date < coalesce(u.removed_date, date '9999-12-31')
