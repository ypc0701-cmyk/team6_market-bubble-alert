{% macro train_phase2_remaining_dev() %}

    {% if target.name != 'dev' %}
        {{ exceptions.raise_compiler_error(
            "This training macro is restricted to dev."
        ) }}
    {% endif %}

    {% set training_table = ref('phase2_train_rows') %}

    {% set models = [
        {'name': 'baseline_drawdown', 'type': 'LOGISTIC_REG', 'feature': 'drawdown_252'},
        {'name': 'baseline_vol', 'type': 'LOGISTIC_REG', 'feature': 'vol_60d'},
        {'name': 'boosted_trees', 'type': 'BOOSTED_TREE_CLASSIFIER', 'feature': none}
    ] %}

    {% for model in models %}

        {% set sql %}
            CREATE OR REPLACE MODEL
                `{{ target.database }}.marts_dev.phase2_{{ model.name }}_dev`

            OPTIONS (
                model_type = '{{ model.type }}',
                input_label_cols = ['label_drop_20pct_60d'],
                data_split_method = 'NO_SPLIT',
                max_iterations = 20
            )

            AS
            SELECT
                {% if model.feature %}
                    {{ model.feature }},
                    label_drop_20pct_60d
                {% else %}
                    *
                {% endif %}
            FROM {{ training_table }}
        {% endset %}

        {% do run_query(sql) %}

        {{ log("Trained " ~ model.name ~ " successfully.", info=True) }}

    {% endfor %}

{% endmacro %}
