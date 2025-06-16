#!/usr/bin/env python3
import json
import sys
from itertools import product


def generate_config_combinations(override_params_json, base_configs_json):
    """
    Generate all parameter combinations using Cartesian product applied to all base configs.

    Args:
        override_params_json: JSON string containing parameter overrides
        base_configs_json: JSON string containing array of base configurations

    Returns:
        JSON string containing list of unique configurations
    """
    override_params = json.loads(override_params_json)
    base_configs = json.loads(base_configs_json)

    # If no override params, return original configs
    if not override_params:
        return json.dumps(base_configs)

    # Generate Cartesian product of all parameter values
    param_keys = list(override_params.keys())
    param_values = [override_params[key] for key in param_keys]

    # Generate all combinations for each base config
    result_configs = []
    for base_config in base_configs:
        for combination in product(*param_values):
            config = base_config.copy()
            for i, value in enumerate(combination):
                config[param_keys[i]] = value
            result_configs.append(config)

    # Remove duplicates by converting to JSON strings and back
    unique_configs = []
    seen = set()
    for config in result_configs:
        config_str = json.dumps(config, sort_keys=True)
        if config_str not in seen:
            seen.add(config_str)
            unique_configs.append(config)

    # Sort by dataset
    unique_configs.sort(key=lambda x: x.get("dataset", ""))

    return json.dumps(unique_configs)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Usage: python generate_configs.py <override_params_json> <base_configs_json>",
            file=sys.stderr,
        )
        sys.exit(1)

    override_params_json = sys.argv[1]
    base_configs_json = sys.argv[2]

    result = generate_config_combinations(override_params_json, base_configs_json)
    print(result)
