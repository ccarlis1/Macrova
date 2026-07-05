import 'package:flutter/material.dart';

import '../theme/tokens.dart';
import 'dashed_border.dart';

enum EmptyStateVariant { add, loading, skeleton }

class EmptyState extends StatelessWidget {
  final EmptyStateVariant variant;
  final String? label;
  final IconData? icon;
  final VoidCallback? onTap;

  const EmptyState({
    super.key,
    this.variant = EmptyStateVariant.add,
    this.label,
    this.icon,
    this.onTap,
  });

  const EmptyState.loading({
    super.key,
    this.label,
  })  : variant = EmptyStateVariant.loading,
        icon = null,
        onTap = null;

  const EmptyState.skeleton({
    super.key,
  })  : variant = EmptyStateVariant.skeleton,
        label = null,
        icon = null,
        onTap = null;

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return switch (variant) {
      EmptyStateVariant.loading => _LoadingState(
          label: label,
          tokens: tokens,
        ),
      EmptyStateVariant.skeleton => _SkeletonState(tokens: tokens),
      EmptyStateVariant.add => _AddAffordance(
          label: label ?? '+ Add…',
          icon: icon,
          onTap: onTap,
          tokens: tokens,
        ),
    };
  }
}

class _AddAffordance extends StatelessWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onTap;
  final MacrovaTokens tokens;

  const _AddAffordance({
    required this.label,
    required this.icon,
    required this.onTap,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: MacrovaRadius.borderMd,
      child: CustomPaint(
        painter: DashedBorderPainter(
          color: tokens.lineDefault,
          borderRadius: MacrovaRadius.md,
          strokeWidth: 1.5,
          dashWidth: 6,
          dashSpace: 4,
        ),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: MacrovaSpacing.xxl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, color: tokens.inkQuaternary, size: 32),
                const SizedBox(height: MacrovaSpacing.sm),
              ],
              Text(
                label,
                style: MacrovaTypography.bodyMedium(tokens.inkTertiary),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LoadingState extends StatelessWidget {
  final String? label;
  final MacrovaTokens tokens;

  const _LoadingState({
    required this.label,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(MacrovaSpacing.xxl),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(
              strokeWidth: 2.5,
              color: tokens.accent,
              backgroundColor: tokens.lineSoft,
            ),
          ),
          if (label != null) ...[
            const SizedBox(height: MacrovaSpacing.md),
            Text(
              label!,
              style: MacrovaTypography.caption(tokens.inkTertiary),
            ),
          ],
        ],
      ),
    );
  }
}

class _SkeletonState extends StatelessWidget {
  final MacrovaTokens tokens;

  const _SkeletonState({required this.tokens});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          height: 120,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                tokens.surfaceSoft,
                tokens.lineSoft,
                tokens.surfaceSoft,
              ],
            ),
            borderRadius: MacrovaRadius.borderMd,
          ),
        ),
        const SizedBox(height: MacrovaSpacing.md),
        Container(
          height: 14,
          width: double.infinity,
          decoration: BoxDecoration(
            color: tokens.surfaceSoft,
            borderRadius: MacrovaRadius.borderSm,
          ),
        ),
        const SizedBox(height: MacrovaSpacing.sm),
        Container(
          height: 14,
          width: 160,
          decoration: BoxDecoration(
            color: tokens.surfaceSoft,
            borderRadius: MacrovaRadius.borderSm,
          ),
        ),
      ],
    );
  }
}
