using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using Terraria;
using Terraria.ModLoader;

namespace ForgeConnector
{
    internal sealed class ForgeLabTelemetryContext
    {
        public string CandidateId { get; set; } = string.Empty;
        public string RunId { get; set; } = string.Empty;
        public string PackageKey { get; set; } = string.Empty;
        public string LoopFamily { get; set; } = string.Empty;

        public bool SupportsRuntimeLabTelemetry =>
            string.Equals(PackageKey, "storm_brand", StringComparison.OrdinalIgnoreCase)
            && string.Equals(LoopFamily, "mark_cashout", StringComparison.OrdinalIgnoreCase);
    }

    internal static class ForgeLabTelemetry
    {
        private sealed class ForgeLabTelemetryRecord
        {
            public string candidate_id { get; set; } = string.Empty;
            public string run_id { get; set; } = string.Empty;
            public string package_key { get; set; } = string.Empty;
            public string event_type { get; set; } = string.Empty;
            public int timestamp_ms { get; set; }
            public string loop_family { get; set; } = string.Empty;
            public string target_id { get; set; }
            public int? stack_count { get; set; }
            public string fx_marker { get; set; }
            public string audio_marker { get; set; }
        }

        private sealed class TargetStackState
        {
            public int StackCount { get; set; }
            public int TargetType { get; set; }
            public long LastSeenUpdate { get; set; }
            public ForgeLabTelemetryContext Context { get; set; }
        }

        private sealed class CandidateActivityState
        {
            public long LastSeenUpdate { get; set; }
            public ForgeLabTelemetryContext Context { get; set; }
        }

        private static readonly Dictionary<int, ForgeLabTelemetryContext> _itemContexts = new();
        private static readonly Dictionary<int, ForgeLabTelemetryContext> _projectileContexts = new();
        private static readonly Dictionary<string, TargetStackState> _targetStacks = new();
        private static readonly Dictionary<string, CandidateActivityState> _activeCandidates = new();
        private static readonly object _sync = new();

        private static string _eventsPath = string.Empty;

        public static void Configure(string modSourcesDir)
        {
            lock (_sync)
            {
                _eventsPath = Path.Combine(modSourcesDir, "forge_lab_runtime_events.jsonl");
                Directory.CreateDirectory(modSourcesDir);
                _itemContexts.Clear();
                _projectileContexts.Clear();
                _targetStacks.Clear();
                _activeCandidates.Clear();

                try
                {
                    File.Delete(_eventsPath);
                }
                catch
                {
                    // Best effort only. Later appends can still succeed.
                }
            }
        }

        public static void Clear()
        {
            lock (_sync)
            {
                _itemContexts.Clear();
                _projectileContexts.Clear();
                _targetStacks.Clear();
                _activeCandidates.Clear();
            }
        }

        public static ForgeLabTelemetryContext CreateContext(string candidateId, string runId, string packageKey, string loopFamily, string fallbackCandidateId)
        {
            string resolvedCandidateId = string.IsNullOrWhiteSpace(candidateId)
                ? fallbackCandidateId
                : candidateId.Trim();
            string resolvedRunId = runId?.Trim() ?? string.Empty;
            string resolvedPackageKey = packageKey?.Trim() ?? string.Empty;
            string resolvedLoopFamily = loopFamily?.Trim() ?? string.Empty;

            if (string.IsNullOrWhiteSpace(resolvedCandidateId)
                || string.IsNullOrWhiteSpace(resolvedRunId)
                || string.IsNullOrWhiteSpace(resolvedPackageKey)
                || string.IsNullOrWhiteSpace(resolvedLoopFamily))
                return null;

            return new ForgeLabTelemetryContext
            {
                CandidateId = resolvedCandidateId,
                RunId = resolvedRunId,
                PackageKey = resolvedPackageKey,
                LoopFamily = resolvedLoopFamily,
            };
        }

        public static void RegisterItemContext(int slot, ForgeLabTelemetryContext context)
        {
            if (context == null)
                return;

            lock (_sync)
            {
                _itemContexts[slot] = context;
            }
        }

        public static void RegisterProjectileContext(int slot, ForgeLabTelemetryContext context)
        {
            if (context == null)
                return;

            lock (_sync)
            {
                _projectileContexts[slot] = context;
            }
        }

        public static ForgeLabTelemetryContext GetItemContext(int slot)
        {
            lock (_sync)
            {
                return _itemContexts.TryGetValue(slot, out var context) ? context : null;
            }
        }

        public static ForgeLabTelemetryContext GetProjectileContext(int slot)
        {
            lock (_sync)
            {
                return _projectileContexts.TryGetValue(slot, out var context) ? context : null;
            }
        }

        public static int IncrementTargetStack(ForgeLabTelemetryContext context, NPC target)
        {
            string key = BuildTargetKey(context, target.whoAmI);
            long now = Main.GameUpdateCount;
            lock (_sync)
            {
                if (!_targetStacks.TryGetValue(key, out var state)
                    || state.TargetType != target.type
                    || now - state.LastSeenUpdate > 600L)
                {
                    state = new TargetStackState
                    {
                        StackCount = 0,
                        TargetType = target.type,
                        LastSeenUpdate = now,
                        Context = context,
                    };
                    _targetStacks[key] = state;
                }

                state.StackCount += 1;
                state.LastSeenUpdate = now;
                state.Context = context;
                return state.StackCount;
            }
        }

        public static void EmitCandidateCompletedForIdleCandidates(long idleUpdates = 120L)
        {
            var completedContexts = new Dictionary<string, ForgeLabTelemetryContext>();
            long now = Main.GameUpdateCount;

            lock (_sync)
            {
                var candidateKeysToRemove = new List<string>();
                foreach (var entry in _activeCandidates)
                {
                    CandidateActivityState state = entry.Value;
                    if (now - state.LastSeenUpdate < idleUpdates || state.Context == null)
                        continue;

                    completedContexts[entry.Key] = state.Context;
                    candidateKeysToRemove.Add(entry.Key);
                }

                foreach (string key in candidateKeysToRemove)
                    _activeCandidates.Remove(key);

                var keysToRemove = new List<string>();
                foreach (var entry in _targetStacks)
                {
                    TargetStackState state = entry.Value;
                    if (now - state.LastSeenUpdate < idleUpdates || state.Context == null)
                        continue;

                    string candidateKey = BuildCandidateKey(state.Context);
                    completedContexts[candidateKey] = state.Context;
                    keysToRemove.Add(entry.Key);
                }

                foreach (string key in keysToRemove)
                    _targetStacks.Remove(key);
            }

            foreach (ForgeLabTelemetryContext context in completedContexts.Values)
                Emit(context, "candidate_completed");
        }

        public static void ResetTargetStack(ForgeLabTelemetryContext context, int targetWhoAmI)
        {
            string key = BuildTargetKey(context, targetWhoAmI);
            lock (_sync)
            {
                _targetStacks.Remove(key);
            }
        }

        public static void Emit(
            ForgeLabTelemetryContext context,
            string eventType,
            string targetId = null,
            int? stackCount = null,
            string fxMarker = null,
            string audioMarker = null)
        {
            if (context == null || !context.SupportsRuntimeLabTelemetry || string.IsNullOrWhiteSpace(_eventsPath))
                return;

            string candidateKey = BuildCandidateKey(context);
            lock (_sync)
            {
                if (eventType == "candidate_completed")
                {
                    _activeCandidates.Remove(candidateKey);
                }
                else
                {
                    _activeCandidates[candidateKey] = new CandidateActivityState
                    {
                        LastSeenUpdate = Main.GameUpdateCount,
                        Context = context,
                    };
                }
            }

            var record = new ForgeLabTelemetryRecord
            {
                candidate_id = context.CandidateId,
                run_id = context.RunId,
                package_key = context.PackageKey,
                event_type = eventType,
                timestamp_ms = GetTimestampMs(),
                loop_family = context.LoopFamily,
                target_id = targetId,
                stack_count = stackCount,
                fx_marker = fxMarker,
                audio_marker = audioMarker,
            };

            try
            {
                string line = JsonSerializer.Serialize(record);
                lock (_sync)
                {
                    File.AppendAllText(_eventsPath, line + Environment.NewLine);
                }
            }
            catch (Exception ex)
            {
                ModContent.GetInstance<ForgeConnector>().Logger.Warn($"[ForgeConnector] Failed to write runtime telemetry: {ex.Message}");
            }
        }

        private static string BuildTargetKey(ForgeLabTelemetryContext context, int targetWhoAmI)
        {
            return $"{context.CandidateId}|{context.RunId}|{context.PackageKey}|{targetWhoAmI}";
        }

        private static string BuildCandidateKey(ForgeLabTelemetryContext context)
        {
            return $"{context.CandidateId}|{context.RunId}|{context.PackageKey}|{context.LoopFamily}";
        }

        private static int GetTimestampMs()
        {
            long timestampMs = (long)Main.GameUpdateCount * 16L;
            return timestampMs > int.MaxValue ? int.MaxValue : (int)timestampMs;
        }
    }
}
