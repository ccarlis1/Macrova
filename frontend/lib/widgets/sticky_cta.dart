import 'dart:ui';

import 'package:flutter/material.dart';

import '../theme/tokens.dart';

class StickyCtaAction {
  final String label;
  final VoidCallback? onPressed;
  final bool isPrimary;

  const StickyCtaAction({
    required this.label,
    this.onPressed,
    this.isPrimary = false,
  });
}

class StickyCta extends StatelessWidget {
  final String label;
  final String detail;
  final List<StickyCtaAction> actions;

  const StickyCta({
    super.key,
    required this.label,
    required this.detail,
    required this.actions,
  });

  @override
  Widget build(BuildContext context) {
    final tokens = Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          decoration: BoxDecoration(
            color: tokens.stickyBar,
            border: Border(top: BorderSide(color: tokens.lineDefault)),
            boxShadow: MacrovaElevation.shadowCta,
          ),
          padding: EdgeInsets.only(
            left: MacrovaSpacing.screenGutter,
            right: MacrovaSpacing.screenGutter,
            top: MacrovaSpacing.md,
            bottom: MacrovaSpacing.md + MediaQuery.paddingOf(context).bottom,
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      label,
                      style: MacrovaTypography.caption(tokens.inkTertiary),
                    ),
                    Text(
                      detail,
                      style: MacrovaTypography.label(tokens.inkPrimary),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: MacrovaSpacing.md),
              ..._buildActions(context, tokens),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _buildActions(BuildContext context, MacrovaTokens tokens) {
    if (actions.length >= 3) {
      return actions
          .map(
            (a) => Expanded(
              child: Padding(
                padding: const EdgeInsets.only(left: MacrovaSpacing.xs),
                child: a.isPrimary
                    ? FilledButton(
                        onPressed: a.onPressed,
                        child: Text(a.label),
                      )
                    : OutlinedButton(
                        onPressed: a.onPressed,
                        child: Text(a.label),
                      ),
              ),
            ),
          )
          .toList();
    }

    return actions
        .map(
          (a) => Padding(
            padding: const EdgeInsets.only(left: MacrovaSpacing.sm),
            child: a.isPrimary
                ? FilledButton(
                    onPressed: a.onPressed,
                    child: Text(a.label),
                  )
                : OutlinedButton(
                    onPressed: a.onPressed,
                    child: Text(a.label),
                  ),
          ),
        )
        .toList();
  }
}
