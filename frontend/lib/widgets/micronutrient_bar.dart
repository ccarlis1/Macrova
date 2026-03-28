import 'package:flutter/material.dart';

class MicronutrientBar extends StatelessWidget {
  final String label;
  final double value;
  final double target;
  final String unit;
  final bool isLimit;

  const MicronutrientBar({
    super.key,
    required this.label,
    required this.value,
    required this.target,
    required this.unit,
    this.isLimit = false,
  });

  @override
  Widget build(BuildContext context) {
    final pct = target > 0 ? (value / target).clamp(0.0, 1.5) : 0.0;
    final displayPct = (pct * 100).round();

    Color barColor;
    if (isLimit) {
      barColor = pct > 1.0 ? Colors.red : Colors.green;
    } else if (pct >= 0.8) {
      barColor = Colors.green;
    } else if (pct >= 0.5) {
      barColor = Colors.amber;
    } else {
      barColor = Colors.red;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  label,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
              Text(
                '${value.toStringAsFixed(value < 10 ? 1 : 0)} $unit/ '
                '${target.toStringAsFixed(target < 10 ? 1 : 0)} $unit',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
          const SizedBox(height: 2),
          Row(
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(2),
                  child: LinearProgressIndicator(
                    value: pct.clamp(0.0, 1.0).toDouble(),
                    backgroundColor: barColor.withValues(alpha: 0.15),
                    color: barColor,
                    minHeight: 6,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(
                width: 55,
                child: Text(
                  '$displayPct% ${isLimit ? "limit" : "RDA"}',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: barColor,
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
