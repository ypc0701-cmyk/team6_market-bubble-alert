{{ config(materialized='ephemeral') }}

-- Phase 2 membership:
-- Universe stocks are eligible for model training.
-- Our original speculative basket is scored, but never used for training.

with speculative_members as (

    select
        ticker,
        listing_date,
        added_date,
        removed_date,
        'our_basket' as role
    from {{ ref('basket_members') }}
    where basket = 'speculative'

),

universe_members as (

    select
        ticker,
        safe_cast(listing_date as date) as listing_date,
        safe_cast(added_date as date) as added_date,
        safe_cast(removed_date as date) as removed_date,
        'universe' as role
    from {{ ref('universe_members') }}

),

combined as (

    select * from speculative_members

    union all

    select u.*
    from universe_members u
    where not exists (
        select 1
        from speculative_members s
        where s.ticker = u.ticker
    )

)

select
    ticker,
    listing_date,
    added_date,
    removed_date,
    role
from combined
