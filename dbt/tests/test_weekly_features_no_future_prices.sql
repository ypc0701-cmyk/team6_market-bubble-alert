-- Independently recalculate selected features using ONLY
-- prices available on or before each weekly as_of date.
-- Fail when stored feature values disagree.

with expected as (
    select
        f.as_of,
        f.ticker,

        safe_divide(
            max(if(p.trade_date = f.as_of, p.adj_close, null)),
            max(if(c.day_idx between w.day_idx - 251
                   and w.day_idx, p.adj_close, null))
        ) - 1 as expected_drawdown,

        safe_divide(
            max(if(p.trade_date = f.as_of, p.adj_close, null)),
            max(if(c.day_idx = w.day_idx - 20,
                   p.adj_close, null))
        ) - 1 as expected_ret_20d,

        safe_divide(
            max(if(p.trade_date = f.as_of, p.adj_close, null)),
            max(if(c.day_idx = w.day_idx - 60,
                   p.adj_close, null))
        ) - 1 as expected_ret_60d,

        safe_divide(
            max(if(p.trade_date = f.as_of, p.adj_close, null)),
            max(if(c.day_idx = w.day_idx - 120,
                   p.adj_close, null))
        ) - 1 as expected_ret_120d

    from {{ ref('weekly_features') }} f

    join {{ ref('int_phase2_calendar') }} w
      on w.trade_date = f.as_of

    join {{ ref('int_phase2_calendar') }} c
      on c.day_idx between w.day_idx - 251 and w.day_idx

    left join {{ ref('stg_prices') }} p
      on p.trade_date = c.trade_date
     and p.ticker = f.ticker

    group by f.as_of, f.ticker
),

violations as (
    select
        f.as_of,
        f.ticker
    from {{ ref('weekly_features') }} f
    join expected e
      on f.as_of = e.as_of
     and f.ticker = e.ticker
    where
        (f.drawdown_252 is null) !=
            (e.expected_drawdown is null)
        or (
            f.drawdown_252 is not null
            and e.expected_drawdown is not null
            and abs(f.drawdown_252 - e.expected_drawdown) > 0.00000001
        )
        or (f.ret_20d is null) != (e.expected_ret_20d is null)
        or (
            f.ret_20d is not null
            and e.expected_ret_20d is not null
            and abs(f.ret_20d - e.expected_ret_20d) > 0.00000001
        )
        or (f.ret_60d is null) != (e.expected_ret_60d is null)
        or (
            f.ret_60d is not null
            and e.expected_ret_60d is not null
            and abs(f.ret_60d - e.expected_ret_60d) > 0.00000001
        )
        or (f.ret_120d is null) != (e.expected_ret_120d is null)
        or (
            f.ret_120d is not null
            and e.expected_ret_120d is not null
            and abs(f.ret_120d - e.expected_ret_120d) > 0.00000001
        )
)

select * from violations
