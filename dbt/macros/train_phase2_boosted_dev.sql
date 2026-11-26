{% macro train_phase2_boosted_dev() %}

    {% if target.name != 'dev' %}
        {{ exceptions.raise_compiler_error(
            "This training macro is restricted to dev."
        ) }}
    {% endif %}

    {% set training_table = ref('phase2_train_rows') %}

    {% set sql %}
        CREATE OR REPLACE MODEL
            `{{ target.database }}.marts_dev.phase2_boosted_trees_dev`

        OPTIONS (
            model_type = 'BOOSTED_TREE_CLASSIFIER',
            input_label_cols = ['label_drop_20pct_60d'],
            data_split_method = 'NO_SPLIT',
            max_iterations = 20
        )

        AS SELECT *
        FROM {{ training_table }}
    {% endset %}

    {% do run_query(sql) %}

    {{ log("Boosted-trees training completed successfully.", info=True) }}

{% endmacro %}
