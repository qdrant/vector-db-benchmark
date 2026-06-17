#!/usr/bin/env python3
"""
Script to discover available engines and their configurations.
This script can be used to generate engine lists for GitHub Actions workflows.
"""

import json
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from benchmark.config_read import read_engine_configs, read_dataset_config


def get_available_engines():
    """Get all available engine configurations."""
    return read_engine_configs()


def get_available_datasets():
    """Get all available dataset configurations."""
    return read_dataset_config()


def get_engines_by_type():
    """Group engines by their type (e.g., qdrant, elasticsearch, etc.)."""
    engines = get_available_engines()
    engines_by_type = {}
    
    for name, config in engines.items():
        engine_type = config.get('engine', 'unknown')
        if engine_type not in engines_by_type:
            engines_by_type[engine_type] = []
        engines_by_type[engine_type].append({
            'name': name,
            'config': config
        })
    
    return engines_by_type


def get_engine_names():
    """Get just the engine names as a list."""
    engines = get_available_engines()
    return sorted(engines.keys())


def get_engine_types():
    """Get unique engine types."""
    engines = get_available_engines()
    types = set()
    for config in engines.values():
        types.add(config.get('engine', 'unknown'))
    return sorted(types)


def main():
    """Main function to output engine information."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Discover available engines and datasets')
    parser.add_argument('--engines', action='store_true', help='List all engine names')
    parser.add_argument('--types', action='store_true', help='List all engine types')
    parser.add_argument('--by-type', action='store_true', help='Group engines by type')
    parser.add_argument('--datasets', action='store_true', help='List all dataset names')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    if args.engines:
        engines = get_engine_names()
        if args.json:
            print(json.dumps(engines, indent=2))
        else:
            for engine in engines:
                print(engine)
    
    elif args.types:
        types = get_engine_types()
        if args.json:
            print(json.dumps(types, indent=2))
        else:
            for engine_type in types:
                print(engine_type)
    
    elif args.by_type:
        engines_by_type = get_engines_by_type()
        if args.json:
            print(json.dumps(engines_by_type, indent=2))
        else:
            for engine_type, engines in engines_by_type.items():
                print(f"{engine_type}:")
                for engine in engines:
                    print(f"  - {engine['name']}")
    
    elif args.datasets:
        datasets = get_available_datasets()
        dataset_names = sorted(datasets.keys())
        if args.json:
            print(json.dumps(dataset_names, indent=2))
        else:
            for dataset in dataset_names:
                print(dataset)
    
    else:
        # Default: show summary
        engines = get_available_engines()
        datasets = get_available_datasets()
        engines_by_type = get_engines_by_type()
        
        print(f"Available engines: {len(engines)}")
        for engine_type, engine_list in engines_by_type.items():
            print(f"  {engine_type}: {len(engine_list)} configurations")
        
        print(f"\nAvailable datasets: {len(datasets)}")
        for dataset_name in sorted(datasets.keys()):
            dataset_type = datasets[dataset_name].get('type', 'unknown')
            print(f"  {dataset_name} ({dataset_type})")


if __name__ == '__main__':
    main()
