#!/bin/bash
# Run the enhanced case import script and capture output
echo "Running enhanced NSPE case import..."
python import_enhanced_nspe_case.py > enhanced_case_import_results.txt 2>&1
echo "Import completed. Results saved to enhanced_case_import_results.txt"
