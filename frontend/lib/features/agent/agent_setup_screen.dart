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
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.smart_toy_outlined,
                size: 56,
                color: tokens.accent,
              ),
              const SizedBox(height: MacrovaSpacing.xlAlt),
              Text(
                'Agent features',
                style: Theme.of(context).textTheme.titleLarge,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: MacrovaSpacing.md),
              Text(
                'Add your LLM API key and provider on Profile, save, then tap '
                'Validate. The server must have matching LLM_ENABLED / LLM_API_KEY.',
                style: MacrovaTypography.bodyMedium(tokens.inkTertiary),
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
                          style: MacrovaTypography.bodyMedium(tokens.accentDeep),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: MacrovaSpacing.xxl),
              FilledButton.icon(
                onPressed: onOpenProfile,
                icon: const Icon(Icons.person_outline),
                label: const Text('Open Profile'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
