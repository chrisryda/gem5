#!/bin/bash
# Collect CPI data from all simulations across different SIM_LIMITs
# Groups by benchmark and sorts by number of ticks

output_file="cpi_summary.txt"
> "$output_file"

# Extract unique benchmarks from all stat files
benchmarks=""
for dir in m5out-*; do
    if [ -d "$dir" ]; then
        SIM_TAG="${dir#m5out-}"
        for bench_file in "$dir"/first-*-"$SIM_TAG".txt; do
            if [ -f "$bench_file" ]; then
                bench_name=$(sed -n '2p' "$bench_file" | awk '{print $1}')
                benchmarks="$benchmarks $bench_name"
            fi
        done
    fi
done

# Sort and deduplicate benchmarks
benchmarks=$(echo "$benchmarks" | tr ' ' '\n' | sort -u | tr '\n' ' ')

# Process each benchmark
for bench in $benchmarks; do
    echo "Benchmark: $bench" >> "$output_file"
    echo "SIM_TAG         CPI             IPC             Ticks" >> "$output_file"
    echo "-----------------------------------------------------------" >> "$output_file"
    
    tmpfile=$(mktemp)
    
    # Collect data for this benchmark from all directories
    for dir in m5out-*; do
        if [ -d "$dir" ]; then
            SIM_TAG="${dir#m5out-}"
            bench_file="$dir/first-$bench-$SIM_TAG.txt"
            if [ -f "$bench_file" ]; then
                cpi=$(grep "core.cpi" "$bench_file" | awk '{print $2}')
                ipc=$(grep "core.ipc" "$bench_file" | awk '{print $2}')
                ticks=$(grep -e "simTicks" -e "core.numCycles" "$bench_file" | head -1 | awk '{print $2}')
                echo "$ticks $SIM_TAG $cpi $ipc" >> "$tmpfile"
            fi
        fi
    done
    
    # Sort by ticks and format output
    sort -n "$tmpfile" | awk '{printf "%-15s %-15s %-15s %s\n", $2, $3, $4, $1}' >> "$output_file"
    rm -f "$tmpfile"
    
    echo "" >> "$output_file"
done

echo "CPI summary collected in $output_file"
cat "$output_file"
