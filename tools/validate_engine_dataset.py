#!/usr/bin/env python3
"""
Script to validate engine and dataset compatibility.
This script checks if a given engine configuration is compatible with a dataset.
"""

import json
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from benchmark.config_read import read_engine_configs, read_dataset_config


def validate_engine_dataset_compatibility(engine_name, dataset_name):
    """
    Validate if an engine configuration is compatible with a dataset.
    
    Args:
        engine_name: Name of the engine configuration
        dataset_name: Name of the dataset
        
    Returns:
        tuple: (is_compatible, error_message)
    """
    try:
        # Load engine and dataset configurations
        engines = read_engine_configs()
        datasets = read_dataset_config()
        
        if engine_name not in engines:
            return False, f"Engine configuration '{engine_name}' not found"
        
        if dataset_name not in datasets:
            return False, f"Dataset '{dataset_name}' not found"
        
        engine_config = engines[engine_name]
        dataset_config = datasets[dataset_name]
        
        # Basic compatibility checks without importing heavy dependencies
        
        # Check if the engine supports sparse vectors if the dataset is sparse
        if dataset_config.get('type') == 'sparse':
            # Check if the engine type supports sparse vectors
            engine_type = engine_config.get('engine', 'unknown')
            sparse_supporting_engines = ['qdrant']  # Add more engines that support sparse vectors
            
            if engine_type not in sparse_supporting_engines:
                return False, f"Engine '{engine_name}' (type: {engine_type}) does not support sparse vectors, but dataset '{dataset_name}' is sparse"
        
        # Additional compatibility checks can be added here
        # For example, checking if the engine supports the required distance metric
        
        return True, None
        
    except Exception as e:
        return False, f"Error validating compatibility: {str(e)}"


def main():
    """Main function to validate engine-dataset compatibility."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate engine and dataset compatibility')
    parser.add_argument('engine', help='Engine configuration name')
    parser.add_argument('dataset', help='Dataset name')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    is_compatible, error_message = validate_engine_dataset_compatibility(args.engine, args.dataset)
    
    if args.json:
        result = {
            'compatible': is_compatible,
            'engine': args.engine,
            'dataset': args.dataset,
            'error': error_message if not is_compatible else None
        }
        print(json.dumps(result, indent=2))
    else:
        if is_compatible:
            print(f"✓ Engine '{args.engine}' is compatible with dataset '{args.dataset}'")
        else:
            print(f"✗ Engine '{args.engine}' is NOT compatible with dataset '{args.dataset}': {error_message}")
            sys.exit(1)


if __name__ == '__main__':
    main()
