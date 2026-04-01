import 'package:flutter/material.dart';

import '../models/optimize_cart_job_status.dart';

/// Progress bar, stage label, and elapsed time for an async optimize-cart job.
class OptimizationProgress extends StatelessWidget {
  const OptimizationProgress({
    super.key,
    required this.status,
    required this.startedAt,
  });

  final OptimizeCartJobStatus status;
  final DateTime startedAt;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final elapsed = DateTime.now().difference(startedAt);
    final mm = elapsed.inMinutes.remainder(60).toString().padLeft(2, '0');
    final ss = elapsed.inSeconds.remainder(60).toString().padLeft(2, '0');

    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: theme.colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Optimizing grocery cart',
                    style: theme.textTheme.titleSmall,
                  ),
                ),
                Text(
                  '${elapsed.inHours > 0 ? '${elapsed.inHours}:' : ''}$mm:$ss',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: status.progress.clamp(0, 100) / 100.0,
                minHeight: 6,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '${status.progress}% · ${status.stage}',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
