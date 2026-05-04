#!/usr/bin/env python3
"""
Performance Log Analyzer
Analyzes performance monitoring logs to track optimization improvements
"""

import json
import re
import sys
from datetime import datetime
from collections import defaultdict
from pathlib import Path


def parse_perf_logs(log_file_path):
    """Parse performance logs and extract metrics"""
    metrics = defaultdict(list)
    
    try:
        with open(log_file_path, 'r') as f:
            for line in f:
                # Look for PERF: log entries
                if 'PERF:' in line:
                    try:
                        # Extract JSON from log line
                        json_match = re.search(r'\| ({.*})', line)
                        if json_match:
                            json_str = json_match.group(1)
                            data = json.loads(json_str)
                            operation = data.get('operation', 'unknown')
                            duration = data.get('duration_ms', 0)
                            metadata = data.get('metadata', {})
                            
                            metrics[operation].append({
                                'duration_ms': duration,
                                'metadata': metadata,
                                'timestamp': data.get('timestamp')
                            })
                    except json.JSONDecodeError:
                        continue
    except FileNotFoundError:
        print(f"Log file not found: {log_file_path}")
        return metrics
    
    return metrics


def calculate_stats(durations):
    """Calculate statistics for a list of durations"""
    if not durations:
        return {}
    
    durations = sorted(durations)
    total = sum(durations)
    count = len(durations)
    
    return {
        'count': count,
        'min_ms': round(min(durations), 2),
        'max_ms': round(max(durations), 2),
        'avg_ms': round(total / count, 2),
        'p50_ms': round(durations[count // 2], 2),
        'p95_ms': round(durations[int(count * 0.95)], 2),
        'p99_ms': round(durations[int(count * 0.99)], 2) if count > 100 else 'N/A',
        'total_ms': round(total, 2)
    }


def print_report(metrics):
    """Print a formatted performance report"""
    print("\n" + "=" * 80)
    print("PERFORMANCE MONITORING REPORT")
    print("=" * 80 + "\n")
    
    # Group by operation type
    task_ops = {k: v for k, v in metrics.items() if k.startswith('task_')}
    db_ops = {k: v for k, v in metrics.items() if k.startswith('db_')}
    poll_ops = {k: v for k, v in metrics.items() if k.startswith('poll_')}
    save_ops = {k: v for k, v in metrics.items() if k.startswith('save_')}
    
    # Task Operations
    if task_ops:
        print("📊 TASK OPERATIONS (Complete, Strike, Undo-Strike)")
        print("-" * 80)
        for op_name, measurements in sorted(task_ops.items()):
            durations = [m['duration_ms'] for m in measurements]
            stats = calculate_stats(durations)
            
            op_type = op_name.replace('task_', '').upper()
            print(f"\n  {op_type}:")
            print(f"    Count:     {stats['count']} operations")
            print(f"    Min:       {stats['min_ms']}ms")
            print(f"    Max:       {stats['max_ms']}ms")
            print(f"    Avg:       {stats['avg_ms']}ms")
            print(f"    P50:       {stats['p50_ms']}ms")
            print(f"    P95:       {stats['p95_ms']}ms")
            if stats['p99_ms'] != 'N/A':
                print(f"    P99:       {stats['p99_ms']}ms")
            print(f"    Total:     {stats['total_ms']}ms")
            
            # Show query count from metadata
            query_counts = [m['metadata'].get('query_count', 0) for m in measurements if m['metadata']]
            if query_counts:
                avg_queries = sum(query_counts) / len(query_counts)
                print(f"    Avg Queries: {avg_queries:.1f}")
    
    # Database Operations
    if db_ops:
        print("\n\n🗄️  DATABASE OPERATIONS")
        print("-" * 80)
        for op_name, measurements in sorted(db_ops.items()):
            durations = [m['duration_ms'] for m in measurements]
            stats = calculate_stats(durations)
            
            op_type = op_name.replace('db_', '').upper()
            print(f"\n  {op_type}:")
            print(f"    Count:     {stats['count']} operations")
            print(f"    Avg:       {stats['avg_ms']}ms")
            print(f"    P95:       {stats['p95_ms']}ms")
            
            # Show query count
            query_counts = [m['metadata'].get('query_count', 0) for m in measurements if m['metadata']]
            if query_counts:
                avg_queries = sum(query_counts) / len(query_counts)
                print(f"    Avg Queries: {avg_queries:.1f}")
    
    # Polling Operations
    if poll_ops:
        print("\n\n📡 POLLING OPERATIONS")
        print("-" * 80)
        for op_name, measurements in sorted(poll_ops.items()):
            durations = [m['duration_ms'] for m in measurements]
            stats = calculate_stats(durations)
            
            op_type = op_name.replace('poll_', '').upper()
            print(f"\n  {op_type}:")
            print(f"    Count:     {stats['count']} polls")
            print(f"    Avg:       {stats['avg_ms']}ms")
            
            # Show interval from metadata
            intervals = [m['metadata'].get('interval_ms', 0) for m in measurements if m['metadata']]
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                print(f"    Avg Interval: {avg_interval:.0f}ms")
    
    # Save Operations
    if save_ops:
        print("\n\n💾 SAVE OPERATIONS")
        print("-" * 80)
        for op_name, measurements in sorted(save_ops.items()):
            durations = [m['duration_ms'] for m in measurements]
            stats = calculate_stats(durations)
            
            op_type = op_name.replace('save_tasks_', '').upper()
            print(f"\n  {op_type}:")
            print(f"    Count:     {stats['count']} saves")
            print(f"    Avg:       {stats['avg_ms']}ms")
            print(f"    P95:       {stats['p95_ms']}ms")
            
            # Show task count
            task_counts = [m['metadata'].get('task_count', 0) for m in measurements if m['metadata']]
            if task_counts:
                avg_tasks = sum(task_counts) / len(task_counts)
                print(f"    Avg Tasks: {avg_tasks:.0f}")
    
    # Summary
    print("\n\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total_ops = sum(len(v) for v in metrics.values())
    print(f"\nTotal Operations Logged: {total_ops}")
    
    if task_ops:
        task_durations = []
        for measurements in task_ops.values():
            task_durations.extend([m['duration_ms'] for m in measurements])
        task_stats = calculate_stats(task_durations)
        print(f"\nTask Operations (Complete/Strike/Undo):")
        print(f"  Average Duration: {task_stats['avg_ms']}ms")
        print(f"  P95 Duration:     {task_stats['p95_ms']}ms")
        print(f"  Total Count:      {task_stats['count']}")
    
    print("\n" + "=" * 80 + "\n")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        # Try to find the log file automatically
        possible_paths = [
            Path('logs/app.log'),
            Path('logs/shakshuka.log'),
            Path('app.log'),
            Path('shakshuka.log'),
        ]
        
        log_file = None
        for path in possible_paths:
            if path.exists():
                log_file = path
                break
        
        if not log_file:
            print("Usage: python analyze_performance_logs.py <log_file>")
            print("\nNo log file found. Please specify a log file path.")
            sys.exit(1)
    else:
        log_file = Path(sys.argv[1])
    
    print(f"Analyzing logs from: {log_file}")
    metrics = parse_perf_logs(str(log_file))
    
    if not metrics:
        print("No performance metrics found in log file.")
        sys.exit(1)
    
    print_report(metrics)


if __name__ == '__main__':
    main()
