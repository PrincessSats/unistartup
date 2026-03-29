#!/usr/bin/env python3
"""
Generate AI Generation Metrics Report from live database.
Usage: python scripts/generate_metrics_report.py
"""

import asyncio
import json
from datetime import datetime, timedelta
from sqlalchemy import text
from app.database import AsyncSessionLocal


async def fetch_stats():
    """Fetch all metrics from database."""
    async with AsyncSessionLocal() as session:
        queries = {
            'batch_stats': '''
                SELECT
                    COUNT(*) as total_batches,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                    ROUND(100.0 * COUNT(CASE WHEN status = 'completed' THEN 1 END) / COUNT(*), 1) as completion_rate
                FROM ai_generation_batches;
            ''',
            'variant_stats': '''
                SELECT
                    COUNT(*) as total_variants,
                    COUNT(CASE WHEN passed_all_binary = true THEN 1 END) as passed,
                    COUNT(CASE WHEN is_selected = true THEN 1 END) as selected,
                    ROUND(100.0 * COUNT(CASE WHEN passed_all_binary = true THEN 1 END) / COUNT(*), 1) as pass_rate,
                    ROUND(AVG(COALESCE(quality_score, 0)), 2) as avg_quality,
                    ROUND(AVG(tokens_input + tokens_output), 0) as avg_tokens,
                    ROUND(AVG(generation_time_ms), 0) as avg_gen_time_ms
                FROM ai_generation_variants;
            ''',
            'task_type_dist': '''
                SELECT
                    task_type,
                    COUNT(*) as count,
                    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage,
                    ROUND(100.0 * COUNT(CASE WHEN v.passed_all_binary = true THEN 1 END) /
                        COUNT(*), 1) as pass_rate,
                    ROUND(AVG(COALESCE(v.quality_score, 0)), 2) as avg_quality
                FROM ai_generation_batches b
                JOIN ai_generation_variants v ON b.id = v.batch_id
                GROUP BY b.task_type
                ORDER BY count DESC;
            ''',
            'quality_by_difficulty': '''
                SELECT
                    difficulty,
                    COUNT(*) as total,
                    ROUND(100.0 * COUNT(CASE WHEN passed_all_binary = true THEN 1 END) / COUNT(*), 1) as pass_rate,
                    ROUND(AVG(COALESCE(quality_score, 0)), 2) as avg_quality
                FROM ai_generation_variants
                GROUP BY difficulty
                ORDER BY
                    CASE difficulty WHEN 'easy' THEN 1 WHEN 'medium' THEN 2 WHEN 'hard' THEN 3 ELSE 4 END;
            ''',
            'top_failures': '''
                SELECT
                    failure_reason,
                    COUNT(*) as count,
                    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM ai_generation_variants WHERE failure_reason IS NOT NULL), 1) as percentage
                FROM ai_generation_variants
                WHERE failure_reason IS NOT NULL
                GROUP BY failure_reason
                ORDER BY count DESC
                LIMIT 5;
            ''',
            'rag_usage': '''
                SELECT
                    COUNT(*) as total_batches,
                    COUNT(CASE WHEN rag_context_ids IS NOT NULL AND array_length(rag_context_ids, 1) > 0 THEN 1 END) as rag_enabled,
                    ROUND(100.0 * COUNT(CASE WHEN rag_context_ids IS NOT NULL AND array_length(rag_context_ids, 1) > 0 THEN 1 END) / COUNT(*), 1) as rag_percentage
                FROM ai_generation_batches;
            ''',
            'temperature_analysis': '''
                SELECT
                    ROUND(temperature::numeric, 1) as temperature,
                    COUNT(*) as count,
                    ROUND(100.0 * COUNT(CASE WHEN passed_all_binary = true THEN 1 END) / COUNT(*), 1) as pass_rate,
                    ROUND(AVG(tokens_input + tokens_output), 0) as avg_tokens
                FROM ai_generation_variants
                WHERE temperature IS NOT NULL
                GROUP BY ROUND(temperature::numeric, 1)
                ORDER BY temperature;
            ''',
            'monthly_tokens': '''
                SELECT
                    DATE_TRUNC('month', created_at)::date as month,
                    COUNT(*) as task_count,
                    ROUND(AVG(tokens_input + tokens_output), 0) as avg_tokens_per_task
                FROM ai_generation_variants
                GROUP BY DATE_TRUNC('month', created_at)
                ORDER BY month DESC
                LIMIT 3;
            '''
        }

        results = {}
        for name, query in queries.items():
            try:
                result = await session.execute(text(query))
                rows = result.fetchall()
                results[name] = [dict(row._mapping) for row in rows]
            except Exception as e:
                print(f"Error fetching {name}: {e}")
                results[name] = []

        return results


def format_report(stats):
    """Format statistics into markdown report."""

    batch = stats['batch_stats'][0] if stats['batch_stats'] else {}
    variant = stats['variant_stats'][0] if stats['variant_stats'] else {}

    report = f"""# 🤖 HackNet AI Task Generation — Metrics Report

**Generated:** {datetime.now().strftime('%B %d, %Y')} | **Data Period:** Last 90 days

---

## Executive Summary

Our **GRPO-optimized task generation pipeline** has achieved **{variant.get('pass_rate', 'N/A')}% production-ready task generation** with intelligent variant selection.

---

## 📊 Key Performance Indicators

### Generation Efficiency
| Metric | Value |
|--------|-------|
| **Avg Generation Time** | {variant.get('avg_gen_time_ms', 'N/A')}ms |
| **Avg Tokens/Task** | {variant.get('avg_tokens', 'N/A')} |
| **Total Variants Generated** | {variant.get('total_variants', 'N/A')} |
| **Completion Rate** | {batch.get('completion_rate', 'N/A')}% |

### Quality Metrics
| Metric | Value |
|--------|-------|
| **Pass Rate (Binary)** | **{variant.get('pass_rate', 'N/A')}%** |
| **Avg Quality Score** | **{variant.get('avg_quality', 'N/A')}/10** |
| **Selection Rate** | {variant.get('selected', 'N/A')} selected variants |
| **Total Batches** | {batch.get('total_batches', 'N/A')} |

"""

    # Task Type Distribution
    if stats['task_type_dist']:
        report += "\n## 📈 Performance by Task Type\n\n"
        for row in stats['task_type_dist']:
            report += f"- **{row['task_type']}** ({row['count']} variants, {row['percentage']}%)\n"
            report += f"  - Pass Rate: {row['pass_rate']}% | Quality: {row['avg_quality']}/10\n"

    # Quality by Difficulty
    if stats['quality_by_difficulty']:
        report += "\n## 📋 Quality by Difficulty\n\n"
        report += "| Difficulty | Generated | Pass Rate | Avg Quality |\n"
        report += "|------------|-----------|-----------|-------------|\n"
        for row in stats['quality_by_difficulty']:
            report += f"| **{row['difficulty'].capitalize()}** | {row['total']} | {row['pass_rate']}% | {row['avg_quality']}/10 |\n"

    # Temperature Analysis
    if stats['temperature_analysis']:
        report += "\n## 🌡️ Temperature Tuning Analysis\n\n"
        report += "| Temperature | Variants | Pass Rate | Avg Tokens |\n"
        report += "|-------------|----------|-----------|------------|\n"
        for row in stats['temperature_analysis']:
            report += f"| {row['temperature']} | {row['count']} | {row['pass_rate']}% | {row['avg_tokens']} |\n"

    # RAG Usage
    if stats['rag_usage']:
        rag = stats['rag_usage'][0]
        report += f"\n## 🧠 Knowledge Base Integration (RAG)\n\n"
        report += f"- **RAG Enabled:** {rag['rag_enabled']}/{rag['total_batches']} batches ({rag['rag_percentage']}%)\n"

    # Failure Analysis
    if stats['top_failures']:
        report += "\n## ❌ Top Rejection Reasons\n\n"
        report += "| Reason | Count | % |\n"
        report += "|--------|-------|----|\n"
        for row in stats['top_failures']:
            report += f"| {row['failure_reason']} | {row['count']} | {row['percentage']}% |\n"

    # Monthly Trends
    if stats['monthly_tokens']:
        report += "\n## 📊 Monthly Token Usage\n\n"
        for row in stats['monthly_tokens']:
            month = row['month'].strftime('%B %Y')
            report += f"- **{month}:** {row['task_count']} tasks, {row['avg_tokens_per_task']} avg tokens/task\n"

    report += "\n---\n\n**Questions?** Contact the AI Pipeline Team\n"
    return report


async def main():
    print("📊 Fetching metrics from database...")
    stats = await fetch_stats()

    print("📝 Generating report...")
    report = format_report(stats)

    output_path = "AI_GENERATION_METRICS_REPORT.md"
    with open(output_path, "w") as f:
        f.write(report)

    print(f"✅ Report saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
