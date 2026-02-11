#!/bin/bash
# Vision Optimizer for MacBook Air M2
# Usage: ./vision_optimizer.sh [input_path] [output_path] [width]

INPUT=$1
OUTPUT=$2
WIDTH=${3:-1024}

if [ -f "$INPUT" ]; then
    sips -Z $WIDTH "$INPUT" --out "$OUTPUT" > /dev/null 2>&1
    echo "Optimized: $OUTPUT (Width: $WIDTH)"
else
    echo "Error: Input file not found."
    exit 1
fi
