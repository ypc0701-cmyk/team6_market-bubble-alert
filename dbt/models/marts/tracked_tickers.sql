{{ config(materialized='view', schema='marts') }}

select distinct ticker
from {{ ref('basket_members') }}

union distinct

select distinct ticker
from {{ ref('universe_members') }}
