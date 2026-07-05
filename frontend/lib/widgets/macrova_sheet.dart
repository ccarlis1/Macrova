import 'package:flutter/material.dart';

import '../theme/tokens.dart';
import 'sticky_cta.dart';

class MacrovaSheet extends StatelessWidget {
  final String title;
  final String? subtitle;
  final VoidCallback onClose;
  final Widget? trailing;
  final int? progressStep;
  final int? progressTotal;
  final Widget body;
  final StickyCta? cta;

  const MacrovaSheet({
    super.key,
    required this.title,
    this.subtitle,
    required this.onClose,
    this.trailing,
    this.progressStep,
    this.progressTotal,
    required this.body,
    this.cta,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Material(
      color: tokens.isDark
          ? MacrovaColorsDark.surfaceCard
          : MacrovaColors.surfaceCard,
      child: Column(
        children: [
          _SheetHeader(
            title: title,
            subtitle: subtitle,
            onClose: onClose,
            trailing: trailing,
            progressStep: progressStep,
            progressTotal: progressTotal,
            tokens: tokens,
          ),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(
                left: MacrovaSpacing.screenGutter,
                right: MacrovaSpacing.screenGutter,
                bottom: cta != null ? MacrovaSpacing.sheetBottomClearance : 0,
              ),
              child: body,
            ),
          ),
          if (cta != null) cta!,
        ],
      ),
    );
  }

  /// Full-height modal sheet with slide-up animation.
  static Future<T?> show<T>({
    required BuildContext context,
    required String title,
    String? subtitle,
    Widget? trailing,
    int? progressStep,
    int? progressTotal,
    required Widget body,
    StickyCta? cta,
  }) {
    return showModalBottomSheet<T>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Colors.transparent,
      barrierColor: MacrovaColors.scrim,
      builder: (ctx) {
        return FractionallySizedBox(
          heightFactor: 1,
          child: MacrovaSheet(
            title: title,
            subtitle: subtitle,
            onClose: () => Navigator.of(ctx).pop(),
            trailing: trailing,
            progressStep: progressStep,
            progressTotal: progressTotal,
            body: body,
            cta: cta,
          ),
        );
      },
    );
  }
}

class _SheetHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  final VoidCallback onClose;
  final Widget? trailing;
  final int? progressStep;
  final int? progressTotal;
  final MacrovaTokens tokens;

  const _SheetHeader({
    required this.title,
    required this.subtitle,
    required this.onClose,
    required this.trailing,
    required this.progressStep,
    required this.progressTotal,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(
            MacrovaSpacing.sm,
            MacrovaSpacing.md,
            MacrovaSpacing.screenGutter,
            MacrovaSpacing.md,
          ),
          child: Row(
            children: [
              IconButton(
                onPressed: onClose,
                icon: const Icon(Icons.arrow_back),
                color: tokens.inkPrimary,
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: MacrovaTypography.titleSm(tokens.inkPrimary),
                    ),
                    if (subtitle != null)
                      Text(
                        subtitle!,
                        style: MacrovaTypography.caption(tokens.inkTertiary),
                      ),
                  ],
                ),
              ),
              if (trailing != null) trailing!,
            ],
          ),
        ),
        if (progressStep != null && progressTotal != null && progressTotal! > 0)
          _ProgressSegments(
            current: progressStep!,
            total: progressTotal!,
            tokens: tokens,
          ),
        Divider(color: tokens.lineSoft, height: 1),
      ],
    );
  }
}

class _ProgressSegments extends StatelessWidget {
  final int current;
  final int total;
  final MacrovaTokens tokens;

  const _ProgressSegments({
    required this.current,
    required this.total,
    required this.tokens,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        MacrovaSpacing.screenGutter,
        0,
        MacrovaSpacing.screenGutter,
        MacrovaSpacing.md,
      ),
      child: Row(
        children: List.generate(total, (i) {
          final isActive = i < current;
          return Expanded(
            child: Container(
              height: 3,
              margin: EdgeInsets.only(right: i < total - 1 ? MacrovaSpacing.xs : 0),
              decoration: BoxDecoration(
                color: isActive ? tokens.accent : tokens.lineSoft,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          );
        }),
      ),
    );
  }
}
