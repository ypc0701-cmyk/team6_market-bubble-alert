{% macro train_phase2_logistic_dev() %}

    {% if target.name != 'dev' %}
        {{ exceptions.raise_compiler_error(
            "This training macro is restricted to the dev target."
        ) }}
    {% endif %}

    {% set training_table = ref('phase2_train_rows') %}

    {% set sql %}
        CREATE OR REPLACE MODEL
            `{{ target.database }}.marts_dev.phase2_logistic_dev`

        OPTIONS (
            model_type = 'LOGISTIC_REG',
            input_label_cols = ['label_drop_20pct_60d'],
            auto_class_weights = TRUE,
            data_split_method = 'NO_SPLIT',
            max_iterations = 20
        )

        AS SELECT *
        FROM {{ training_table }}
    {% endset %}

    {% do run_query(sql) %}

    {{ log("Development logistic regression training completed.", info=True) }}

{% endmacro %}
