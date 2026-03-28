import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'llm_config_provider.dart';

/// Shown on the Agent rail when the user has not validated LLM credentials.
class AgentSetupScreen extends StatelessWidget {
  const AgentSetupScreen({super.key, required this.onOpenProfile});

  final VoidCallback onOpenProfile;

  @override
  Widget build(BuildContext context) {
    final gate = context.watch<LlmConfigProvider>();
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 480),
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.smart_toy_outlined,
                size: 56,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(height: 24),
              Text(
                'Agent features',
                style: Theme.of(context).textTheme.headlineSmall,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Text(
                'Add your LLM API key and provider on Profile, save, then tap '
                'Validate. The server must have matching LLM_ENABLED / LLM_API_KEY.',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                textAlign: TextAlign.center,
              ),
              if (gate.lastValidationError != null) ...[
                const SizedBox(height: 20),
                Material(
                  color: Theme.of(context).colorScheme.errorContainer,
                  borderRadius: BorderRadius.circular(8),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(
                      gate.lastValidationError!,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Theme.of(context)
                                .colorScheme
                                .onErrorContainer,
                          ),
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 28),
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
