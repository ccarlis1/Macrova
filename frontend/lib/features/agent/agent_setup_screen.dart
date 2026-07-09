import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../theme/tokens.dart';
import 'llm_config_provider.dart';

/// Shown on the Agent rail when the user has not validated LLM credentials.
class AgentSetupScreen extends StatelessWidget {
  const AgentSetupScreen({super.key, required this.onOpenProfile});

  final VoidCallback onOpenProfile;

  @override
  Widget build(BuildContext context) {
    final gate = context.watch<LlmConfigProvider>();
    final tokens =
        Theme.of(context).extension<MacrovaTokens>() ?? MacrovaTokens.light;

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: MacrovaSpacing.mobileMaxWidth),
        child: Padding(
          padding: const EdgeInsets.all(MacrovaSpacing.xxl),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.all(MacrovaSpacing.xlAlt),
            decoration: BoxDecoration(
              color: tokens.isDark
                  ? MacrovaColorsDark.surfaceCard
                  : MacrovaColors.surfaceCard,
              borderRadius: MacrovaRadius.borderLg,
              border: Border.all(color: tokens.lineDefault),
              boxShadow: MacrovaElevation.shadow1,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: tokens.accentSoft,
                    shape: BoxShape.circle,
                    border: Border.all(color: tokens.accentTint),
                  ),
                  alignment: Alignment.center,
                  child: Icon(
                    Icons.smart_toy_outlined,
                    size: 32,
                    color: tokens.accent,
                  ),
                ),
                const SizedBox(height: MacrovaSpacing.xlAlt),
                Text(
                  'Agent features',
                  style: MacrovaTypography.headline(tokens.inkPrimary),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: MacrovaSpacing.md),
                Text(
                  'Add your LLM API key and provider on Profile, save, then tap '
                  'Validate. The server must have matching LLM_ENABLED / LLM_API_KEY.',
                  style: MacrovaTypography.body(tokens.inkTertiary),
                  textAlign: TextAlign.center,
                ),
                if (gate.lastValidationError != null) ...[
                  const SizedBox(height: MacrovaSpacing.xl),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(MacrovaSpacing.md),
                    decoration: BoxDecoration(
                      color: tokens.accentSoft,
                      borderRadius: MacrovaRadius.borderMd,
                      border: Border.all(color: tokens.accentTint),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(
                          Icons.error_outline,
                          size: 16,
                          color: tokens.accentDeep,
                        ),
                        const SizedBox(width: MacrovaSpacing.sm),
                        Expanded(
                          child: Text(
                            gate.lastValidationError!,
                            style: MacrovaTypography.bodyMedium(
                              tokens.accentDeep,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: MacrovaSpacing.xxl),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: onOpenProfile,
                    icon: const Icon(Icons.person_outline),
                    label: const Text('Open Profile'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
