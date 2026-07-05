import 'package:flutter/material.dart';

import '../theme/tokens.dart';

class FailureFixRow {
  final String label;
  final String description;
  final VoidCallback? onTap;

  const FailureFixRow({
    required this.label,
    required this.description,
    this.onTap,
  });
}

/// Planner failure hero panel.
///
/// Map OpenAPI `PlanFailure` when wiring: `code` → [terminationCode],
/// `message` → [cause], `fix_hint` → [fixHint]. [hardestConstraint],
/// [constraintProgress], [trace], and [fixes] are UI-only — derive from
/// `details` or planner debug output; do not invent values.
class FailurePanel extends StatefulWidget {
  final String terminationCode;
  final String cause;
  final String? hardestConstraint;
  final double? constraintProgress;
  final List<FailureFixRow> fixes;
  final String? trace;
  final String? fixHint;

  const FailurePanel({
    super.key,
    required this.terminationCode,
    required this.cause,
    this.hardestConstraint,
    this.constraintProgress,
    this.fixes = const [],
    this.trace,
    this.fixHint,
  });

  @override
  State<FailurePanel> createState() => _FailurePanelState();
}

class _FailurePanelState extends State<FailurePanel> {
  bool _traceExpanded = false;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.all(MacrovaSpacing.xl),
          decoration: BoxDecoration(
            color: tokens.accentSoft,
            borderRadius: MacrovaRadius.borderLg,
            border: Border.all(color: tokens.accentTint),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.error_outline, size: 14, color: tokens.accentDeep),
                  const SizedBox(width: MacrovaSpacing.xs + 3),
                  Text(
                    MacrovaTypography.labelCapsText('Infeasible'),
                    style: MacrovaTypography.labelCaps(tokens.accentDeep),
                  ),
                  const Spacer(),
                  Text(
                    widget.terminationCode,
                    style: MacrovaTypography.mono(tokens.accentDeep),
                  ),
                ],
              ),
              const SizedBox(height: MacrovaSpacing.md),
              Text(
                widget.cause,
                style: MacrovaTypography.subtitle(tokens.inkPrimary).copyWith(
                  fontWeight: FontWeight.w500,
                ),
              ),
              if (widget.fixHint != null) ...[
                const SizedBox(height: MacrovaSpacing.sm),
                Text(
                  widget.fixHint!,
                  style: MacrovaTypography.body(tokens.inkSecondary),
                ),
              ],
            ],
          ),
        ),
        if (widget.hardestConstraint != null) ...[
          const SizedBox(height: MacrovaSpacing.lg),
          _HardestConstraintCard(
            label: widget.hardestConstraint!,
            progress: widget.constraintProgress,
            tokens: tokens,
          ),
        ],
        if (widget.fixes.isNotEmpty) ...[
          const SizedBox(height: MacrovaSpacing.lg),
          ...widget.fixes.map(
            (fix) => _FixRow(fix: fix, tokens: tokens),
          ),
        ],
        if (widget.trace != null && widget.trace!.isNotEmpty) ...[
          const SizedBox(height: MacrovaSpacing.lg),
          InkWell(
            onTap: () => setState(() => _traceExpanded = !_traceExpanded),
            borderRadius: MacrovaRadius.borderSm,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: MacrovaSpacing.sm),
              child: Row(
                children: [
                  Icon(
                    _traceExpanded
                        ? Icons.keyboard_arrow_down
                        : Icons.keyboard_arrow_right,
                    color: tokens.inkTertiary,
                  ),
                  Text(
                    'Solver trace',
                    style: MacrovaTypography.label(tokens.inkSecondary),
                  ),
                ],
              ),
            ),
          ),
          if (_traceExpanded)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(MacrovaSpacing.md),
              decoration: BoxDecoration(
                color: tokens.surfaceSoft,
                borderRadius: MacrovaRadius.borderSm,
                border: Border.all(color: tokens.lineDefault),
              ),
              child: SelectableText(
                widget.trace!,
                style: MacrovaTypography.mono(tokens.inkSecondary),
              ),
            ),
        ],
      ],
    );
  }
}

class _HardestConstraintCard extends StatelessWidget {
  final String label;
  final double? progress;
  final MacrovaTokens tokens;

  const _HardestConstraintCard({
    required this.label,
    required this.progress,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(MacrovaSpacing.lg),
      decoration: BoxDecoration(
        color: tokens.surfaceTint,
        borderRadius: MacrovaRadius.borderMd,
        border: Border.all(color: tokens.lineDefault),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            MacrovaTypography.labelCapsText('Hardest constraint'),
            style: MacrovaTypography.labelCaps(tokens.inkTertiary),
          ),
          const SizedBox(height: MacrovaSpacing.sm),
          Text(
            label,
            style: MacrovaTypography.label(tokens.inkPrimary),
          ),
          if (progress != null) ...[
            const SizedBox(height: MacrovaSpacing.md),
            ClipRRect(
              borderRadius: BorderRadius.circular(2),
              child: LinearProgressIndicator(
                value: progress!.clamp(0.0, 1.0),
                minHeight: 4,
                backgroundColor: tokens.accent.withValues(alpha: 0.15),
                color: tokens.accent,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _FixRow extends StatelessWidget {
  final FailureFixRow fix;
  final MacrovaTokens tokens;

  const _FixRow({
    required this.fix,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: MacrovaSpacing.sm),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: MacrovaRadius.borderSm,
        side: BorderSide(color: tokens.lineDefault),
      ),
      child: ListTile(
        onTap: fix.onTap,
        title: Text(
          fix.label,
          style: MacrovaTypography.label(tokens.inkPrimary),
        ),
        subtitle: Text(
          fix.description,
          style: MacrovaTypography.caption(tokens.inkTertiary),
        ),
        trailing: fix.onTap != null
            ? Icon(Icons.chevron_right, color: tokens.inkQuaternary)
            : null,
      ),
    );
  }
}
