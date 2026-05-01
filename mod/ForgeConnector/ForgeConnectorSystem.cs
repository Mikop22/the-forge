using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Threading;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using ReLogic.Content;
using Terraria;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;
using ForgeConnector.Content.Buffs;
using ForgeConnector.Content.Items;
using ForgeConnector.Content.Projectiles;

namespace ForgeConnector
{
    public class ForgeConnector : Mod { }

    /// <summary>
    /// ModSystem that watches for forge_inject.json (instant item injection)
    /// and command_trigger.json (legacy reload path) in ModSources.
    /// All game-state mutations happen on the main thread via PostUpdateEverything().
    /// </summary>
    public class ForgeConnectorSystem : ModSystem
    {
        private static int _reloadRequested = 0;
        private static int _injectRequested = 0;
        private static string _pendingInjectJson = "";

        private FileSystemWatcher _watcher;
        private string _modSourcesDir = string.Empty;
        private string _triggerPath = string.Empty;
        private string _injectPath = string.Empty;
        private string _hiddenLabRequestPath = string.Empty;
        private string _hiddenLabResultPath = string.Empty;
        private string _runtimeEventsPath = string.Empty;
        private string _heartbeatPath = string.Empty;
        private string _statusPath = string.Empty;
        private string _runtimeSummaryPath = string.Empty;
        private string _lastInjectPath = string.Empty;
        private string _lastInjectDebugPath = string.Empty;
        private string _runtimeAssetDir = string.Empty;
        private int _watcherRetryCooldown;
        private int _injectPollCooldown;
        private string _activeHiddenLabCandidateId = string.Empty;
        private string _activeHiddenLabRunId = string.Empty;
        private string _activeHiddenLabPackageKey = string.Empty;
        private string _activeHiddenLabLoopFamily = string.Empty;
        private string _lastRuntimeSummarySignature = string.Empty;
        private DateTime _lastRuntimeSummaryWriteAt = DateTime.MinValue;
        private string _lastLiveItemName = string.Empty;
        private string _lastInjectStatus = string.Empty;
        private string _lastRuntimeNote = string.Empty;
        private static readonly TimeSpan RuntimeSummaryRefreshInterval = TimeSpan.FromSeconds(5);

        // ------------------------------------------------------------------
        // Lifecycle
        // ------------------------------------------------------------------

        public override void PostSetupContent()
        {
            _modSourcesDir = GetModSourcesDir();
            _triggerPath   = Path.Combine(_modSourcesDir, "command_trigger.json");
            _injectPath    = Path.Combine(_modSourcesDir, "forge_inject.json");
            _hiddenLabRequestPath = Path.Combine(_modSourcesDir, "forge_lab_hidden_request.json");
            _hiddenLabResultPath = Path.Combine(_modSourcesDir, "forge_lab_hidden_result.json");
            _runtimeEventsPath = Path.Combine(_modSourcesDir, "forge_lab_runtime_events.jsonl");
            _heartbeatPath = Path.Combine(_modSourcesDir, "forge_connector_alive.json");
            _statusPath    = Path.Combine(_modSourcesDir, "forge_connector_status.json");
            _runtimeSummaryPath = Path.Combine(_modSourcesDir, "forge_runtime_summary.json");
            _lastInjectPath = Path.Combine(_modSourcesDir, "forge_last_inject.json");
            _lastInjectDebugPath = Path.Combine(_modSourcesDir, "forge_last_inject_debug.json");
            _runtimeAssetDir = Path.Combine(Path.GetDirectoryName(_modSourcesDir)!, "ForgeConnectorStagingAssets");

            RegisterTemplateTypeIds();
            ForgeLabTelemetry.Configure(_modSourcesDir);
            WriteHeartbeat();
            WriteRuntimeSummary(force: true);
            StartWatcher();
        }

        public override void Unload()
        {
            _watcher?.Dispose();
            _watcher = null;
            ForgeManifestStore.Clear();
            ForgeLabTelemetry.Clear();

            try { File.Delete(_heartbeatPath); } catch { /* best-effort */ }
            try { File.Delete(_runtimeSummaryPath); } catch { /* best-effort */ }
        }

        /// <summary>
        /// Registers the tModLoader type IDs for all template items/projectiles/buffs
        /// so we can spawn them by slot index at runtime.
        /// </summary>
        private void RegisterTemplateTypeIds()
        {
            RegisterTypeIds(
                new Type[]
                {
                    typeof(ForgeItem_001), typeof(ForgeItem_002), typeof(ForgeItem_003), typeof(ForgeItem_004), typeof(ForgeItem_005),
                    typeof(ForgeItem_006), typeof(ForgeItem_007), typeof(ForgeItem_008), typeof(ForgeItem_009), typeof(ForgeItem_010),
                    typeof(ForgeItem_011), typeof(ForgeItem_012), typeof(ForgeItem_013), typeof(ForgeItem_014), typeof(ForgeItem_015),
                    typeof(ForgeItem_016), typeof(ForgeItem_017), typeof(ForgeItem_018), typeof(ForgeItem_019), typeof(ForgeItem_020),
                    typeof(ForgeItem_021), typeof(ForgeItem_022), typeof(ForgeItem_023), typeof(ForgeItem_024), typeof(ForgeItem_025),
                    typeof(ForgeItem_026), typeof(ForgeItem_027), typeof(ForgeItem_028), typeof(ForgeItem_029), typeof(ForgeItem_030),
                    typeof(ForgeItem_031), typeof(ForgeItem_032), typeof(ForgeItem_033), typeof(ForgeItem_034), typeof(ForgeItem_035),
                    typeof(ForgeItem_036), typeof(ForgeItem_037), typeof(ForgeItem_038), typeof(ForgeItem_039), typeof(ForgeItem_040),
                    typeof(ForgeItem_041), typeof(ForgeItem_042), typeof(ForgeItem_043), typeof(ForgeItem_044), typeof(ForgeItem_045),
                    typeof(ForgeItem_046), typeof(ForgeItem_047), typeof(ForgeItem_048), typeof(ForgeItem_049), typeof(ForgeItem_050),
                },
                "ItemType",
                ForgeManifestStore.RegisterItemTypeId);

            RegisterTypeIds(
                new Type[]
                {
                    typeof(ForgeProjectile_001), typeof(ForgeProjectile_002), typeof(ForgeProjectile_003), typeof(ForgeProjectile_004), typeof(ForgeProjectile_005),
                    typeof(ForgeProjectile_006), typeof(ForgeProjectile_007), typeof(ForgeProjectile_008), typeof(ForgeProjectile_009), typeof(ForgeProjectile_010),
                    typeof(ForgeProjectile_011), typeof(ForgeProjectile_012), typeof(ForgeProjectile_013), typeof(ForgeProjectile_014), typeof(ForgeProjectile_015),
                    typeof(ForgeProjectile_016), typeof(ForgeProjectile_017), typeof(ForgeProjectile_018), typeof(ForgeProjectile_019), typeof(ForgeProjectile_020),
                    typeof(ForgeProjectile_021), typeof(ForgeProjectile_022), typeof(ForgeProjectile_023), typeof(ForgeProjectile_024), typeof(ForgeProjectile_025),
                },
                "ProjectileType",
                ForgeManifestStore.RegisterProjectileTypeId);

            RegisterTypeIds(
                new Type[]
                {
                    typeof(ForgeBuff_001), typeof(ForgeBuff_002), typeof(ForgeBuff_003), typeof(ForgeBuff_004), typeof(ForgeBuff_005),
                    typeof(ForgeBuff_006), typeof(ForgeBuff_007), typeof(ForgeBuff_008), typeof(ForgeBuff_009), typeof(ForgeBuff_010),
                    typeof(ForgeBuff_011), typeof(ForgeBuff_012), typeof(ForgeBuff_013), typeof(ForgeBuff_014), typeof(ForgeBuff_015),
                    typeof(ForgeBuff_016), typeof(ForgeBuff_017), typeof(ForgeBuff_018), typeof(ForgeBuff_019), typeof(ForgeBuff_020),
                    typeof(ForgeBuff_021), typeof(ForgeBuff_022), typeof(ForgeBuff_023), typeof(ForgeBuff_024), typeof(ForgeBuff_025),
                },
                "BuffType",
                ForgeManifestStore.RegisterBuffTypeId);
        }

        private static void RegisterTypeIds(Type[] types, string methodName, Action<int, int> register)
        {
            var method = typeof(ModContent).GetMethod(methodName, Type.EmptyTypes);
            if (method == null)
                return;

            for (int i = 0; i < types.Length; i++)
            {
                var generic = method.MakeGenericMethod(types[i]);
                int typeId = (int)generic.Invoke(null, null)!;
                register(i, typeId);
            }
        }

        // ------------------------------------------------------------------
        // Main-thread hook
        // ------------------------------------------------------------------

        public override void PostUpdateEverything()
        {
            TryStartWatcherIfNeeded();
            PollInjectFileFallback();
            ForgeLabTelemetry.EmitCandidateCompletedForIdleCandidates();
            TryWriteHiddenLabResult();

            // Handle legacy reload request
            if (Interlocked.Exchange(ref _reloadRequested, 0) == 1)
            {
                bool triggered = TriggerReload();
                WriteStatus(triggered ? "reload_triggered" : "reload_failed");
                UpdateRuntimeSummaryState(
                    triggered ? "reload_triggered" : "reload_failed",
                    runtimeNote: triggered ? "Mod reload triggered." : "Mod reload failed."
                );
            }

            TryProcessInject();
            WriteRuntimeSummary();
        }

        /// <summary>
        /// UpdateUI runs even when the game is autopaused (e.g. player alt-tabbed
        /// to the TUI). This ensures inject processing isn't blocked by autopause.
        /// </summary>
        public override void UpdateUI(GameTime gameTime)
        {
            TryProcessInject();
        }

        private void TryProcessInject()
        {
            if (Interlocked.Exchange(ref _injectRequested, 0) == 1)
            {
                string json = Interlocked.Exchange(ref _pendingInjectJson, "");
                if (!string.IsNullOrEmpty(json))
                {
                    ProcessInject(json);
                }
            }
        }

        // ------------------------------------------------------------------
        // Inject processing (runs on main thread)
        // ------------------------------------------------------------------

        private void ProcessInject(string json)
        {
            try
            {
                Mod.Logger.Info("[ForgeConnector] ProcessInject starting, json length=" + json.Length);
                using JsonDocument doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                if (!root.TryGetProperty("action", out var actionEl) || actionEl.GetString() != "inject")
                {
                    Mod.Logger.Warn("[ForgeConnector] ProcessInject: no 'inject' action found");
                    return;
                }

                string itemName = root.TryGetProperty("item_name", out var nameEl) ? nameEl.GetString() ?? "" : "";
                Mod.Logger.Info("[ForgeConnector] Injecting item: " + itemName);

                if (GetBool(root, "compiled_mod_item", false))
                {
                    SpawnCompiledModItem(root, itemName);
                    return;
                }

                var data = ParseManifest(root);
                int itemSlot = ForgeManifestStore.NextItemSlot();
                ForgeLabTelemetryContext telemetryContext = CreateTelemetryContext(root, data.Name);
                ForgeManifestStore.RegisterItem(itemSlot, data);
                ForgeLabTelemetry.RegisterItemContext(itemSlot, telemetryContext);

                string itemSpritePath = GetSpritePath(root, "sprite_path");
                string stagedItemSpritePath = StageRuntimeAsset("item", data.Name, itemSpritePath);
                bool itemSpriteExists = !string.IsNullOrEmpty(stagedItemSpritePath) && File.Exists(stagedItemSpritePath);
                LogSpritePathResolution("item", itemSpritePath, stagedItemSpritePath, itemSpriteExists);

                string projSpritePath = GetSpritePath(root, "projectile_sprite_path");
                string stagedProjSpritePath = StageRuntimeAsset("projectile", data.Name, projSpritePath);
                bool projSpriteExists = !string.IsNullOrEmpty(stagedProjSpritePath) && File.Exists(stagedProjSpritePath);
                LogSpritePathResolution("projectile", projSpritePath, stagedProjSpritePath, projSpriteExists);

                WriteLastInjectArtifacts(
                    json,
                    itemName,
                    itemSpritePath,
                    stagedItemSpritePath,
                    itemSpriteExists,
                    projSpritePath,
                    stagedProjSpritePath,
                    projSpriteExists);

                if (itemSpriteExists)
                {
                    LoadItemTexture(itemSlot, stagedItemSpritePath);
                }

                bool needsProjectile = NeedsProjectile(data, stagedProjSpritePath);

                int projSlot = -1;
                if (needsProjectile && data.ShootProjectileTypeId < 0)
                {
                    projSlot = ForgeManifestStore.NextProjectileSlot();
                    data.ShootProjectileSlot = projSlot;
                }

                int buffSlot = -1;
                if (string.Equals(data.ContentType, "Summon", StringComparison.OrdinalIgnoreCase))
                {
                    buffSlot = ForgeManifestStore.NextBuffSlot();
                    data.BuffTemplateSlot = buffSlot;
                }

                if (projSlot >= 0)
                {
                    var projData = ParseProjectile(root);
                    projData.MinionBuffSlot = buffSlot;
                    projData.MinionProjectileSlot = projSlot;

                    if (string.Equals(data.ContentType, "Summon", StringComparison.OrdinalIgnoreCase))
                    {
                        projData.AiMode = "minion_follower";
                        projData.MinionSlots = data.MinionSlots;
                        projData.MinionHoverHeight = data.MinionHoverHeight;
                        projData.MinionSpeed = data.MinionSpeed;
                        projData.MinionAcceleration = data.MinionAcceleration;
                        projData.MinionTeleportDistance = data.MinionTeleportDistance;
                        projData.MinionAttackRange = data.MinionAttackRange;
                    }
                    else if (string.Equals(data.SubType, "Hook", StringComparison.OrdinalIgnoreCase))
                    {
                        projData.AiMode = "hook";
                    }

                    ForgeManifestStore.RegisterProjectile(projSlot, projData);
                    ForgeLabTelemetry.RegisterProjectileContext(projSlot, telemetryContext);

                    if (projSpriteExists)
                    {
                        LoadProjectileTexture(projSlot, stagedProjSpritePath);
                    }
                }

                if (buffSlot >= 0)
                {
                    int minionTypeId = projSlot >= 0
                        ? ForgeManifestStore.GetProjectileTypeId(projSlot)
                        : data.ShootProjectileTypeId;
                    var buffData = ParseBuff(root, minionTypeId);
                    buffData.MinionProjectileSlot = projSlot;
                    buffData.MinionProjectileTypeId = minionTypeId;
                    ForgeManifestStore.RegisterBuff(buffSlot, buffData);
                }

                ForgeManifestStore.RegisterItem(itemSlot, data);

                int itemTypeId = ForgeManifestStore.GetItemTypeId(itemSlot);
                Mod.Logger.Info($"[ForgeConnector] Slot={itemSlot}, TypeId={itemTypeId}, LocalPlayer null={Main.LocalPlayer == null}");
                bool spawned = itemTypeId > 0 && Main.LocalPlayer != null;
                if (spawned)
                {
                    Main.LocalPlayer.QuickSpawnItem(Main.LocalPlayer.GetSource_Misc("ForgeConnector"), itemTypeId);
                    Mod.Logger.Info("[ForgeConnector] Item spawned successfully");
                }

                if (itemTypeId > 0)
                {
                    if (spawned)
                    {
                        WriteStatus("item_injected", itemName, itemSlot);
                        UpdateRuntimeSummaryState("item_injected", liveItemName: itemName, runtimeNote: "Item delivered to inventory.");
                        Mod.Logger.Info("[ForgeConnector] Status written: item_injected");
                    }
                    else
                    {
                        WriteStatus("item_pending", "No local player — open a world or unpause to receive the item.", itemSlot);
                        UpdateRuntimeSummaryState("item_pending", liveItemName: itemName, runtimeNote: "No local player — open a world or unpause to receive the item.");
                        Mod.Logger.Info("[ForgeConnector] Status written: item_pending (LocalPlayer null)");
                    }
                }
                else
                {
                        WriteStatus("inject_failed", "Invalid item type id after registration.", -1);
                    UpdateRuntimeSummaryState("inject_failed", clearLiveItemName: true, runtimeNote: "Invalid item type id after registration.");
                }
            }
            catch (Exception ex)
            {
                Mod.Logger.Error("[ForgeConnector] ProcessInject failed: " + ex);
                WriteStatus("inject_failed", ex.Message, -1);
                UpdateRuntimeSummaryState("inject_failed", clearLiveItemName: true, runtimeNote: ex.Message);
            }
        }

        private void SpawnCompiledModItem(JsonElement root, string itemName)
        {
            string modName = GetStr(root, "mod_name", "ForgeGeneratedMod");
            string compiledItemName = GetStr(root, "compiled_item_name", itemName);
            string fullName = modName + "/" + compiledItemName;

            Mod.Logger.Info("[ForgeConnector] Compiled item inject: " + fullName);

            if (!ModContent.TryFind<ModItem>(fullName, out var modItem))
            {
                string message = "Compiled item not found: " + fullName;
                Mod.Logger.Warn("[ForgeConnector] " + message);
                WriteStatus("inject_failed", message, -1);
                UpdateRuntimeSummaryState("inject_failed", clearLiveItemName: true, runtimeNote: message);
                return;
            }

            int itemTypeId = modItem.Type;
            bool spawned = itemTypeId > 0 && Main.LocalPlayer != null;
            if (spawned)
            {
                Main.LocalPlayer.QuickSpawnItem(Main.LocalPlayer.GetSource_Misc("ForgeConnectorCompiled"), itemTypeId);
                WriteStatus("item_injected", compiledItemName, -1);
                UpdateRuntimeSummaryState("item_injected", liveItemName: compiledItemName, runtimeNote: "Compiled item delivered to inventory.");
                Mod.Logger.Info("[ForgeConnector] Compiled item spawned successfully");
            }
            else if (itemTypeId > 0)
            {
                WriteStatus("item_pending", "No local player — open a world or unpause to receive the compiled item.", -1);
                UpdateRuntimeSummaryState("item_pending", liveItemName: compiledItemName, runtimeNote: "No local player — open a world or unpause to receive the compiled item.");
                Mod.Logger.Info("[ForgeConnector] Compiled item pending (LocalPlayer null)");
            }
            else
            {
                WriteStatus("inject_failed", "Invalid compiled item type id: " + fullName, -1);
                UpdateRuntimeSummaryState("inject_failed", clearLiveItemName: true, runtimeNote: "Invalid compiled item type id: " + fullName);
            }
        }

        /// <summary>Prefer manifest.type; fall back to content_type (Architect emits both).</summary>
        private static string ReadContentTypeFromManifest(JsonElement manifest, string fallback)
        {
            string t = GetStr(manifest, "type", "");
            if (string.IsNullOrWhiteSpace(t))
                t = GetStr(manifest, "content_type", "");
            if (string.IsNullOrWhiteSpace(t))
                t = fallback;
            return NormalizeContentType(t);
        }

        private ForgeItemData ParseManifest(JsonElement root)
        {
            var data = new ForgeItemData();
            var manifest = GetManifest(root);

            data.Name = GetStr(manifest, "item_name", data.Name);
            data.DisplayName = GetStr(manifest, "display_name", data.Name);
            data.Tooltip = GetStr(manifest, "tooltip", data.Tooltip);
            data.ContentType = ReadContentTypeFromManifest(manifest, data.ContentType);
            data.SubType = GetStr(manifest, "sub_type", data.SubType);

            if (manifest.TryGetProperty("stats", out var stats))
            {
                data.Damage = GetInt(stats, "damage", data.Damage);
                data.Knockback = GetFloat(stats, "knockback", data.Knockback);
                data.CritChance = GetInt(stats, "crit_chance", data.CritChance);
                data.UseTime = GetInt(stats, "use_time", data.UseTime);
                data.UseAnimation = GetInt(stats, "use_animation", data.UseTime);
                data.AutoReuse = GetBool(stats, "auto_reuse", data.AutoReuse);
                data.Rarity = ParseRarity(GetStr(stats, "rarity", "ItemRarityID.White"));
                data.Value = GetInt(stats, "value", data.Value);
                data.Defense = GetInt(stats, "defense", data.Defense);
                data.HealLife = GetInt(stats, "heal_life", data.HealLife);
                data.HealMana = GetInt(stats, "heal_mana", data.HealMana);
                data.MaxStack = Math.Max(1, GetInt(stats, "max_stack", data.MaxStack));
            }

            if (manifest.TryGetProperty("visuals", out var visuals))
            {
                if (visuals.TryGetProperty("icon_size", out var iconSize)
                    && iconSize.ValueKind == JsonValueKind.Array
                    && iconSize.GetArrayLength() >= 2)
                {
                    data.Width = iconSize[0].GetInt32();
                    data.Height = iconSize[1].GetInt32();
                }
            }

            if (manifest.TryGetProperty("mechanics", out var mechanics))
            {
                data.ShootProjectileName = GetStr(mechanics, "shoot_projectile", "");
                data.ShootProjectileTypeId = ResolveProjectileId(data.ShootProjectileName);
                data.CustomProjectile = GetBool(mechanics, "custom_projectile", false) ||
                    IsCustomProjectileName(data.ShootProjectileName);

                if (data.ShootProjectileTypeId >= 0)
                {
                    data.CustomProjectile = false;
                }
                else if (!string.IsNullOrWhiteSpace(data.ShootProjectileName)
                    && !IsCustomProjectileName(data.ShootProjectileName)
                    && data.ShootProjectileName.IndexOf("ProjectileID.", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    // LLM requested a vanilla projectile that didn't resolve — fall back to BallofFire
                    // so the weapon at least fires something visible rather than silently doing nothing.
                    Mod.Logger.Warn($"[ForgeConnector] Unresolved shoot_projectile '{data.ShootProjectileName}' for '{data.Name}', falling back to BallofFire");
                    data.ShootProjectileTypeId = ProjectileID.BallofFire;
                    data.CustomProjectile = false;
                }

                string onHitBuff = GetStr(mechanics, "on_hit_buff", "");
                string buffIdField = GetStr(mechanics, "buff_id", "");
                string buffRaw = string.IsNullOrWhiteSpace(onHitBuff) ? buffIdField : onHitBuff;
                data.BuffType = ResolveBuffId(buffRaw);
                data.BuffTime = GetInt(mechanics, "buff_time", data.BuffTime);
                data.UseAmmoTypeId = ResolveAmmoId(GetStr(mechanics, "use_ammo", ""));

                data.PickPower = GetInt(mechanics, "pick_power", data.PickPower);
                data.AxePower = GetInt(mechanics, "axe_power", data.AxePower);
                data.HammerPower = GetInt(mechanics, "hammer_power", data.HammerPower);
                data.FishingPower = GetInt(mechanics, "fishing_power", data.FishingPower);
                data.HookProjectileSlot = GetInt(mechanics, "hook_projectile_slot", data.HookProjectileSlot);

                data.MinionSlots = GetFloat(mechanics, "minion_slots", data.MinionSlots);
                data.MinionHoverHeight = GetFloat(mechanics, "minion_hover_height", data.MinionHoverHeight);
                data.MinionSpeed = GetFloat(mechanics, "minion_speed", data.MinionSpeed);
                data.MinionAcceleration = GetFloat(mechanics, "minion_acceleration", data.MinionAcceleration);
                data.MinionTeleportDistance = GetFloat(mechanics, "minion_teleport_distance", data.MinionTeleportDistance);
                data.MinionAttackRange = GetFloat(mechanics, "minion_attack_range", data.MinionAttackRange);
                data.MinionBuffTime = GetInt(mechanics, "minion_buff_time", data.MinionBuffTime);
                data.MinionAiMode = GetStr(mechanics, "minion_ai_mode", data.MinionAiMode);
                data.BuffTemplateSlot = GetInt(mechanics, "buff_template_slot", data.BuffTemplateSlot);
            }

            ApplyContentTypeDefaults(data);
            ApplySubTypeDefaults(data);

            if (data.ShootProjectileTypeId < 0 && data.CustomProjectile)
                data.ShootProjectileSlot = -1;

            if (data.ContentType == "Summon" && data.ShootSpeed <= 0f)
                data.ShootSpeed = 10f;

            if (root.TryGetProperty("item_name", out var rootName))
                data.Name = rootName.GetString() ?? data.Name;

            return data;
        }

        private ForgeProjectileData ParseProjectile(JsonElement root)
        {
            var data = new ForgeProjectileData();
            var manifest = GetManifest(root);

            data.Name = GetStr(manifest, "item_name", data.Name);
            data.ContentType = ReadContentTypeFromManifest(manifest, data.ContentType);
            data.SubType = GetStr(manifest, "sub_type", data.SubType);

            if (manifest.TryGetProperty("projectile_visuals", out var pv)
                && pv.ValueKind == JsonValueKind.Object)
            {
                if (pv.TryGetProperty("icon_size", out var iconSize)
                    && iconSize.ValueKind == JsonValueKind.Array
                    && iconSize.GetArrayLength() >= 2)
                {
                    data.Width = iconSize[0].GetInt32();
                    data.Height = iconSize[1].GetInt32();
                }
            }

            JsonElement projectileSection = manifest;
            if (!TryGetObject(manifest, "projectile", out projectileSection))
            {
                TryGetObject(manifest, "mechanics", out projectileSection);
            }

            string defaultAiMode = data.ContentType == "Summon"
                ? "minion_follower"
                : string.Equals(data.SubType, "Hook", StringComparison.OrdinalIgnoreCase)
                    ? "hook"
                    : "straight";

            data.AiMode = GetStr(projectileSection, "ai_mode", defaultAiMode);
            data.AiStyle = GetFloat(projectileSection, "ai_style", data.AiMode == "hook" ? 7f : 0f);
            data.Friendly = GetBool(projectileSection, "friendly", data.AiMode != "hook");
            data.Hostile = GetBool(projectileSection, "hostile", false);
            data.Penetrate = GetInt(projectileSection, "penetrate", data.AiMode == "minion_follower" ? -1 : data.Penetrate);
            data.TimeLeft = GetInt(projectileSection, "time_left", data.AiMode == "minion_follower" ? 18000 : data.TimeLeft);
            data.Light = GetFloat(projectileSection, "light", data.Light);
            data.MinionSlots = GetFloat(projectileSection, "minion_slots", data.MinionSlots);
            data.MinionHoverHeight = GetFloat(projectileSection, "minion_hover_height", data.MinionHoverHeight);
            data.MinionSpeed = GetFloat(projectileSection, "minion_speed", data.MinionSpeed);
            data.MinionAcceleration = GetFloat(projectileSection, "minion_acceleration", data.MinionAcceleration);
            data.MinionTeleportDistance = GetFloat(projectileSection, "minion_teleport_distance", data.MinionTeleportDistance);
            data.MinionAttackRange = GetFloat(projectileSection, "minion_attack_range", data.MinionAttackRange);
            data.MinionContactDamage = GetBool(projectileSection, "contact_damage", data.MinionContactDamage);
            data.HookSpeed = GetFloat(projectileSection, "hook_speed", data.HookSpeed);
            data.HookRange = GetFloat(projectileSection, "hook_range", data.HookRange);
            data.HookReelSpeed = GetFloat(projectileSection, "hook_reel_speed", data.HookReelSpeed);

            if (data.AiMode == "minion_follower")
            {
                data.Penetrate = -1;
                data.TimeLeft = Math.Max(data.TimeLeft, 18000);
                data.Friendly = true;
                data.Hostile = false;
            }
            else if (data.AiMode == "hook")
            {
                data.Penetrate = -1;
                data.Friendly = false;
                data.Hostile = false;
            }

            if (root.TryGetProperty("item_name", out var rootName))
                data.Name = rootName.GetString() ?? data.Name;

            return data;
        }

        private ForgeBuffData ParseBuff(JsonElement root, int minionProjectileTypeId)
        {
            var data = new ForgeBuffData();
            var manifest = GetManifest(root);

            data.Name = GetStr(manifest, "item_name", data.Name);
            data.ContentType = ReadContentTypeFromManifest(manifest, data.ContentType);
            data.SubType = GetStr(manifest, "sub_type", data.SubType);
            data.Tooltip = GetStr(manifest, "tooltip", data.Tooltip);

            JsonElement buffSection = manifest;
            if (!TryGetObject(manifest, "buff", out buffSection))
            {
                TryGetObject(manifest, "summon", out buffSection);
            }
            if (buffSection.ValueKind == JsonValueKind.Undefined)
            {
                TryGetObject(manifest, "mechanics", out buffSection);
            }

            data.MinionProjectileSlot = GetInt(buffSection, "minion_projectile_slot", data.MinionProjectileSlot);
            data.MinionProjectileTypeId = GetInt(buffSection, "minion_projectile_type_id", minionProjectileTypeId);
            data.MinionSlots = GetFloat(buffSection, "minion_slots", data.MinionSlots);
            data.MinionHoverHeight = GetFloat(buffSection, "minion_hover_height", data.MinionHoverHeight);
            data.MinionSpeed = GetFloat(buffSection, "minion_speed", data.MinionSpeed);
            data.MinionAcceleration = GetFloat(buffSection, "minion_acceleration", data.MinionAcceleration);
            data.MinionTeleportDistance = GetFloat(buffSection, "minion_teleport_distance", data.MinionTeleportDistance);
            data.MinionAttackRange = GetFloat(buffSection, "minion_attack_range", data.MinionAttackRange);
            data.BuffTime = GetInt(buffSection, "buff_time", data.BuffTime);
            data.NoSave = GetBool(buffSection, "no_save", data.NoSave);
            data.NoTimeDisplay = GetBool(buffSection, "no_time_display", data.NoTimeDisplay);
            data.ContactDamage = GetBool(buffSection, "contact_damage", data.ContactDamage);
            data.AiMode = GetStr(buffSection, "minion_ai_mode", data.AiMode);

            if (data.MinionProjectileTypeId < 0 && minionProjectileTypeId > 0)
                data.MinionProjectileTypeId = minionProjectileTypeId;

            return data;
        }

        private void ApplyContentTypeDefaults(ForgeItemData data)
        {
            switch (data.ContentType)
            {
                case "Accessory":
                    data.Accessory = true;
                    data.NoMelee = true;
                    data.Damage = 0;
                    if (data.UseStyleName == "Swing")
                        data.UseStyleName = "HoldUp";
                    break;
                case "Summon":
                    data.DamageClassName = "Summon";
                    data.NoMelee = true;
                    if (data.UseStyleName == "Swing")
                        data.UseStyleName = "Shoot";
                    if (data.MinionAiMode.Length == 0)
                        data.MinionAiMode = "minion_follower";
                    break;
                case "Consumable":
                    data.Consumable = true;
                    if (data.HealLife > 0 && data.UseStyleName == "Swing")
                        data.UseStyleName = "EatFood";
                    else if (data.HealMana > 0 && data.UseStyleName == "Swing")
                        data.UseStyleName = "Drink";
                    break;
                case "Tool":
                    if (string.Equals(data.SubType, "Hook", StringComparison.OrdinalIgnoreCase)
                        || string.Equals(data.SubType, "Fishing", StringComparison.OrdinalIgnoreCase))
                    {
                        data.NoMelee = true;
                        if (data.UseStyleName == "Swing")
                            data.UseStyleName = "Shoot";
                    }
                    break;
            }
        }

        private void ApplySubTypeDefaults(ForgeItemData data)
        {
            if (data.ContentType == "Summon")
            {
                data.DamageClassName = "Summon";
                if (string.Equals(data.SubType, "Staff", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(data.SubType, "Wand", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(data.SubType, "Tome", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(data.SubType, "Spellbook", StringComparison.OrdinalIgnoreCase))
                {
                    data.UseStyleName = "Shoot";
                }
            }
            else if (data.ContentType == "Weapon")
            {
                data.DamageClassName = data.SubType switch
                {
                    "Gun" or "Bow" or "Repeater" or "Rifle" or "Pistol"
                        or "Shotgun" or "Launcher" or "Cannon" => "Ranged",
                    "Staff" or "Wand" or "Tome" or "Spellbook" => "Magic",
                    _ => data.DamageClassName,
                };

                data.UseStyleName = data.SubType switch
                {
                    "Gun" or "Bow" or "Repeater" or "Rifle" or "Pistol"
                        or "Shotgun" or "Launcher" or "Cannon"
                        or "Staff" or "Wand" or "Tome" or "Spellbook" => "Shoot",
                    "Spear" or "Lance" => "Thrust",
                    _ => data.UseStyleName,
                };
            }

            if (data.SubType is "Pickaxe" or "Hamaxe")
                data.PickPower = Math.Max(data.PickPower, Math.Clamp(data.Damage * 3, 35, 225));
            if (data.SubType is "Axe" or "Hamaxe")
                data.AxePower = Math.Max(data.AxePower, Math.Clamp(data.Damage / 2, 7, 35));
            if (data.SubType is "Hammer" or "Hamaxe")
                data.HammerPower = Math.Max(data.HammerPower, Math.Clamp(data.Damage + 20, 25, 100));
            if (string.Equals(data.SubType, "Fishing", StringComparison.OrdinalIgnoreCase))
                data.FishingPower = Math.Max(data.FishingPower, 35);
            if (string.Equals(data.SubType, "Hook", StringComparison.OrdinalIgnoreCase))
                data.HookProjectileSlot = Math.Max(data.HookProjectileSlot, -1);
        }

        private static bool NeedsProjectile(ForgeItemData data, string projSpritePath)
        {
            if (!string.IsNullOrWhiteSpace(projSpritePath))
                return true;

            if (data.CustomProjectile && data.ShootProjectileTypeId < 0)
                return true;

            if (string.Equals(data.ContentType, "Summon", StringComparison.OrdinalIgnoreCase))
                return data.ShootProjectileTypeId < 0;

            if (string.Equals(data.ContentType, "Tool", StringComparison.OrdinalIgnoreCase)
                && (string.Equals(data.SubType, "Hook", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(data.SubType, "Fishing", StringComparison.OrdinalIgnoreCase)))
            {
                return data.ShootProjectileTypeId < 0;
            }

            return data.ShootProjectileSlot >= 0;
        }

        private static bool IsCustomProjectileName(string value)
        {
            return !string.IsNullOrWhiteSpace(value)
                && value.StartsWith("ModContent.ProjectileType<", StringComparison.Ordinal);
        }

        private static JsonElement GetManifest(JsonElement root)
        {
            return root.TryGetProperty("manifest", out var manifest) ? manifest : root;
        }

        private static ForgeLabTelemetryContext CreateTelemetryContext(JsonElement root, string fallbackCandidateId)
        {
            JsonElement manifest = GetManifest(root);
            JsonElement mechanics = TryGetObject(manifest, "mechanics", out var mechanicsValue) ? mechanicsValue : default;
            JsonElement resolvedCombat = TryGetObject(manifest, "resolved_combat", out var resolvedCombatValue) ? resolvedCombatValue : default;

            string candidateId = GetStr(root, "candidate_id", GetStr(manifest, "candidate_id", fallbackCandidateId));
            string runId = GetStr(root, "run_id", string.Empty);
            string packageKey = GetStr(resolvedCombat, "package_key", GetStr(mechanics, "combat_package", string.Empty));
            string loopFamily = GetStr(resolvedCombat, "loop_family", ResolveLoopFamily(packageKey));

            return ForgeLabTelemetry.CreateContext(candidateId, runId, packageKey, loopFamily, fallbackCandidateId);
        }

        private static string ResolveLoopFamily(string packageKey)
        {
            return packageKey switch
            {
                "storm_brand" => "mark_cashout",
                _ => string.Empty,
            };
        }

        private static bool TryGetObject(JsonElement parent, string prop, out JsonElement value)
        {
            if (parent.ValueKind == JsonValueKind.Object && parent.TryGetProperty(prop, out value)
                && value.ValueKind == JsonValueKind.Object)
            {
                return true;
            }

            value = default;
            return false;
        }

        private static string GetSpritePath(JsonElement root, string prop)
        {
            if (!root.TryGetProperty(prop, out var el) || el.ValueKind != JsonValueKind.String)
                return "";

            string path = el.GetString() ?? "";
            if (path == "None" || path == "null")
                return "";
            return path;
        }

        private static int ResolveProjectileId(string value)
        {
            return ResolveStaticInt(typeof(ProjectileID), value);
        }

        private static int ResolveBuffId(string value)
        {
            return ResolveStaticInt(typeof(BuffID), value);
        }

        private static int ResolveAmmoId(string value)
        {
            return ResolveStaticInt(typeof(AmmoID), value);
        }

        private static int ResolveStaticInt(Type staticType, string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return -1;

            string token = value.Trim();
            if (token.StartsWith("ModContent.", StringComparison.Ordinal))
                return -1;

            int dot = token.LastIndexOf('.');
            if (dot >= 0)
                token = token[(dot + 1)..];

            var field = staticType.GetField(token, BindingFlags.Public | BindingFlags.Static | BindingFlags.IgnoreCase);
            if (field == null && staticType == typeof(ProjectileID))
            {
                token = NormalizeProjectileIdToken(token);
                field = staticType.GetField(token, BindingFlags.Public | BindingFlags.Static | BindingFlags.IgnoreCase);
            }
            if (field != null && field.FieldType == typeof(int))
                return (int)field.GetValue(null)!;

            return -1;
        }

        private static string NormalizeProjectileIdToken(string token)
        {
            return token switch
            {
                // Common LLM-generated aliases that don't match the actual C# field names:
                "Fireball"       => "BallofFire",
                "FireBall"       => "BallofFire",
                "FireBolt"       => "BallofFire",
                "FlameOrb"       => "BallofFire",
                "SwordBeam"      => "StarWrath",
                "LightBeam"      => "LightBlade",
                "LightBolt"      => "LightBlade",
                "IceBeam"        => "Blizzard",
                "IceBolt"        => "IceSickle",
                "FrostBolt"      => "FrostBoltSword",
                "FrostBeam"      => "FrostBoltSword",
                "ShadowBolt"     => "ShadowBeam",
                "DarkBolt"       => "ShadowBeam",
                "DarkBeam"       => "ShadowBeam",
                "MagicBolt"      => "MagicMissile",
                "MagicBeam"      => "MagicMissile",
                "VoidBolt"       => "ShadowBeam",
                "VoidBeam"       => "ShadowBeam",
                "StarBeam"       => "Starfury",
                "StarBolt"       => "Starfury",
                "LavaOrb"        => "BallofFire",
                "LavaBolt"       => "BallofFire",
                "ThunderBolt"    => "BallLightning",
                "LightningBolt"  => "BallLightning",
                _ => token,
            };
        }

        private void LoadItemTexture(int slot, string path)
        {
            try
            {
                using var stream = File.OpenRead(path);
                var tex = Texture2D.FromStream(Main.graphics.GraphicsDevice, stream);
                ForgeManifestStore.SetItemTexture(slot, tex);

                int typeId = ForgeManifestStore.GetItemTypeId(slot);
                if (typeId > 0)
                {
                    if (SetTextureAssetValue(TextureAssets.Item, typeId, tex))
                        Mod.Logger.Info($"[ForgeConnector] Loaded item texture: {path} ({tex.Width}x{tex.Height}) -> type {typeId}");
                    else
                        Mod.Logger.Warn($"[ForgeConnector] Item texture loaded to ManifestStore but TextureAssets reflection failed for type {typeId}");
                }
            }
            catch (Exception ex)
            {
                Mod.Logger.Error("[ForgeConnector] LoadItemTexture failed: " + ex.Message);
            }
        }

        private void LoadProjectileTexture(int slot, string path)
        {
            try
            {
                using var stream = File.OpenRead(path);
                var tex = Texture2D.FromStream(Main.graphics.GraphicsDevice, stream);
                ForgeManifestStore.SetProjectileTexture(slot, tex);

                int typeId = ForgeManifestStore.GetProjectileTypeId(slot);
                if (typeId > 0)
                {
                    if (SetTextureAssetValue(TextureAssets.Projectile, typeId, tex))
                        Mod.Logger.Info($"[ForgeConnector] Loaded projectile texture: {path} ({tex.Width}x{tex.Height}) -> type {typeId}");
                    else
                        Mod.Logger.Warn($"[ForgeConnector] Projectile texture loaded to ManifestStore but TextureAssets reflection failed for type {typeId}");
                }
            }
            catch (Exception ex)
            {
                Mod.Logger.Error("[ForgeConnector] LoadProjectileTexture failed: " + ex.Message);
            }
        }

        /// <summary>
        /// Uses reflection to replace the texture inside an existing Asset&lt;Texture2D&gt;.
        /// This ensures ALL rendering paths (inventory, hotbar, melee swing, world drop)
        /// use our custom sprite instead of the 1x1 placeholder.
        /// </summary>
        private bool SetTextureAssetValue(Asset<Texture2D>[] assetArray, int index, Texture2D tex)
        {
            if (index < 0 || index >= assetArray.Length)
                return false;

            var asset = assetArray[index];
            if (asset == null)
                return false;

            var assetType = asset.GetType();
            var flags = BindingFlags.NonPublic | BindingFlags.Instance;

            // ReLogic.Content.Asset<T> stores the value - field name varies by version
            var valueField = assetType.GetField("ownValue", flags)
                          ?? assetType.GetField("_value", flags)
                          ?? assetType.GetField("value", flags);

            if (valueField != null)
            {
                valueField.SetValue(asset, tex);
            }
            else
            {
                Mod.Logger.Warn("[ForgeConnector] Could not find Asset<T> value field via reflection");
                return false;
            }

            // Mark the asset as loaded so the Value getter returns our texture
            var stateField = assetType.GetField("_state", flags)
                          ?? assetType.GetField("state", flags);
            if (stateField != null && stateField.FieldType.IsEnum)
            {
                object loadedState;
                try { loadedState = Enum.Parse(stateField.FieldType, "Loaded"); }
                catch (Exception ex)
                {
                    Mod.Logger.Warn("[ForgeConnector] Enum.Parse('Loaded') failed, falling back to ordinal 2: " + ex.Message);
                    loadedState = Enum.ToObject(stateField.FieldType, 2);
                }
                stateField.SetValue(asset, loadedState);
            }

            return true;
        }

        // ------------------------------------------------------------------
        // FileSystemWatcher
        // ------------------------------------------------------------------

        private void StartWatcher()
        {
            if (!Directory.Exists(_modSourcesDir))
                return;

            _watcher?.Dispose();
            _watcher = new FileSystemWatcher(_modSourcesDir)
            {
                Filter = "*.json",
                NotifyFilter = NotifyFilters.FileName | NotifyFilters.LastWrite,
                EnableRaisingEvents = true,
            };

            _watcher.Created += OnJsonEvent;
            _watcher.Changed += OnJsonEvent;
            Mod.Logger.Info("[ForgeConnector] FileSystemWatcher started on " + _modSourcesDir);
        }

        /// <summary>
        /// If ModSources was missing at startup, retry periodically until the directory exists.
        /// </summary>
        private void TryStartWatcherIfNeeded()
        {
            if (_watcher != null)
                return;

            if (string.IsNullOrEmpty(_modSourcesDir))
                return;

            _watcherRetryCooldown++;
            if (_watcherRetryCooldown < 120)
                return;

            _watcherRetryCooldown = 0;

            if (!Directory.Exists(_modSourcesDir))
                return;

            _modSourcesDir = GetModSourcesDir();
            _triggerPath = Path.Combine(_modSourcesDir, "command_trigger.json");
            _injectPath = Path.Combine(_modSourcesDir, "forge_inject.json");
            _hiddenLabRequestPath = Path.Combine(_modSourcesDir, "forge_lab_hidden_request.json");
            _hiddenLabResultPath = Path.Combine(_modSourcesDir, "forge_lab_hidden_result.json");
            _runtimeEventsPath = Path.Combine(_modSourcesDir, "forge_lab_runtime_events.jsonl");
            _heartbeatPath = Path.Combine(_modSourcesDir, "forge_connector_alive.json");
            _statusPath = Path.Combine(_modSourcesDir, "forge_connector_status.json");
            _runtimeSummaryPath = Path.Combine(_modSourcesDir, "forge_runtime_summary.json");
            _lastInjectPath = Path.Combine(_modSourcesDir, "forge_last_inject.json");
            _lastInjectDebugPath = Path.Combine(_modSourcesDir, "forge_last_inject_debug.json");
            _runtimeAssetDir = Path.Combine(Path.GetDirectoryName(_modSourcesDir)!, "ForgeConnectorStagingAssets");
            WriteHeartbeat();
            WriteRuntimeSummary(force: true);
            StartWatcher();
        }

        /// <summary>
        /// Fallback when FileSystemWatcher misses events (e.g. some network / sync folders).
        /// </summary>
        private void PollInjectFileFallback()
        {
            _injectPollCooldown++;
            if (_injectPollCooldown < 90)
                return;

            _injectPollCooldown = 0;

            try
            {
                if (!string.IsNullOrEmpty(_injectPath) && File.Exists(_injectPath))
                {
                    HandleInjectTrigger();
                    return;
                }

                if (!string.IsNullOrEmpty(_hiddenLabRequestPath) && File.Exists(_hiddenLabRequestPath))
                    HandleHiddenLabRequestTrigger();
            }
            catch (Exception ex)
            {
                Mod.Logger.Error("[ForgeConnector] PollInjectFileFallback: " + ex.Message);
            }
        }

        private void OnJsonEvent(object sender, FileSystemEventArgs e)
        {
            string fileName = Path.GetFileName(e.FullPath);

            if (fileName == "command_trigger.json")
                HandleCommandTrigger();
            else if (fileName == "forge_inject.json")
                HandleInjectTrigger();
            else if (fileName == "forge_lab_hidden_request.json")
                HandleHiddenLabRequestTrigger();
        }

        private void TryDeleteModSourcesFile(string path, string role)
        {
            try
            {
                File.Delete(path);
            }
            catch (Exception ex)
            {
                Mod.Logger.Warn($"[ForgeConnector] Could not delete {role}: {ex.Message}");
            }
        }

        private void HandleCommandTrigger()
        {
            Thread.Sleep(50);

            try
            {
                string json = File.ReadAllText(_triggerPath);
                using JsonDocument doc = JsonDocument.Parse(json);
                if (!doc.RootElement.TryGetProperty("action", out JsonElement actionEl))
                    return;
                if (actionEl.GetString() != "execute")
                    return;

                TryDeleteModSourcesFile(_triggerPath, "command_trigger.json");

                Interlocked.Exchange(ref _reloadRequested, 1);
            }
            catch (Exception ex)
            {
                Mod.Logger.Error("[ForgeConnector] HandleCommandTrigger failed: " + ex.Message);
            }
        }

        private void HandleInjectTrigger()
        {
            Thread.Sleep(50);

            try
            {
                string json = File.ReadAllText(_injectPath);
                Mod.Logger.Info("[ForgeConnector] HandleInjectTrigger: read " + json.Length + " bytes");

                // Delete immediately to prevent double-fire
                TryDeleteModSourcesFile(_injectPath, "forge_inject.json");

                // Store JSON for main-thread processing
                Interlocked.Exchange(ref _pendingInjectJson, json);
                Interlocked.Exchange(ref _injectRequested, 1);
            }
            catch (Exception ex)
            {
                Mod.Logger.Error("[ForgeConnector] HandleInjectTrigger failed: " + ex.Message);
            }
        }

        private void HandleHiddenLabRequestTrigger()
        {
            Thread.Sleep(50);

            try
            {
                string json = File.ReadAllText(_hiddenLabRequestPath);
                using JsonDocument doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                _activeHiddenLabCandidateId = root.TryGetProperty("candidate_id", out var candidateEl)
                    ? candidateEl.GetString() ?? string.Empty
                    : string.Empty;
                _activeHiddenLabRunId = root.TryGetProperty("run_id", out var runEl)
                    ? runEl.GetString() ?? string.Empty
                    : string.Empty;
                _activeHiddenLabPackageKey = root.TryGetProperty("package_key", out var packageEl)
                    ? packageEl.GetString() ?? string.Empty
                    : string.Empty;
                _activeHiddenLabLoopFamily = root.TryGetProperty("loop_family", out var loopEl)
                    ? loopEl.GetString() ?? string.Empty
                    : string.Empty;

                TryDeleteModSourcesFile(_hiddenLabResultPath, "forge_lab_hidden_result.json");
                TryDeleteModSourcesFile(_hiddenLabRequestPath, "forge_lab_hidden_request.json");

                Interlocked.Exchange(ref _pendingInjectJson, json);
                Interlocked.Exchange(ref _injectRequested, 1);
            }
            catch (Exception ex)
            {
                Mod.Logger.Error("[ForgeConnector] HandleHiddenLabRequestTrigger failed: " + ex.Message);
            }
        }

        private void TryWriteHiddenLabResult()
        {
            if (string.IsNullOrWhiteSpace(_activeHiddenLabCandidateId)
                || string.IsNullOrWhiteSpace(_activeHiddenLabRunId)
                || string.IsNullOrWhiteSpace(_hiddenLabResultPath)
                || string.IsNullOrWhiteSpace(_runtimeEventsPath)
                || !File.Exists(_runtimeEventsPath))
                return;

            try
            {
                var events = new List<JsonElement>();
                bool sawCashout = false;
                bool sawCompletion = false;
                foreach (string line in File.ReadAllLines(_runtimeEventsPath))
                {
                    if (string.IsNullOrWhiteSpace(line))
                        continue;

                    using JsonDocument eventDoc = JsonDocument.Parse(line);
                    JsonElement root = eventDoc.RootElement;
                    if (!root.TryGetProperty("candidate_id", out var candidateEl)
                        || !string.Equals(candidateEl.GetString(), _activeHiddenLabCandidateId, StringComparison.Ordinal))
                        continue;

                    if (!root.TryGetProperty("run_id", out var runEl)
                        || !string.Equals(runEl.GetString(), _activeHiddenLabRunId, StringComparison.Ordinal))
                        continue;

                    events.Add(root.Clone());

                    if (root.TryGetProperty("event_type", out var eventTypeEl)
                        && string.Equals(eventTypeEl.GetString(), "cashout_triggered", StringComparison.Ordinal))
                    {
                        sawCashout = true;
                    }

                    if (root.TryGetProperty("event_type", out eventTypeEl)
                        && string.Equals(eventTypeEl.GetString(), "candidate_completed", StringComparison.Ordinal))
                    {
                        sawCompletion = true;
                    }
                }

                if (events.Count == 0 || (!sawCashout && !sawCompletion))
                    return;

                string json = JsonSerializer.Serialize(new
                {
                    candidate_id = _activeHiddenLabCandidateId,
                    run_id = _activeHiddenLabRunId,
                    package_key = _activeHiddenLabPackageKey,
                    loop_family = _activeHiddenLabLoopFamily,
                    events,
                }, new JsonSerializerOptions { WriteIndented = true });

                string tmp = _hiddenLabResultPath + ".tmp";
                File.WriteAllText(tmp, json);
                File.Move(tmp, _hiddenLabResultPath, overwrite: true);

                _activeHiddenLabCandidateId = string.Empty;
                _activeHiddenLabRunId = string.Empty;
                _activeHiddenLabPackageKey = string.Empty;
                _activeHiddenLabLoopFamily = string.Empty;
            }
            catch (Exception ex)
            {
                Mod.Logger.Error("[ForgeConnector] TryWriteHiddenLabResult failed: " + ex.Message);
            }
        }

        private string StageRuntimeAsset(string kind, string itemName, string sourcePath)
        {
            if (string.IsNullOrWhiteSpace(sourcePath))
                return string.Empty;

            try
            {
                if (!File.Exists(sourcePath))
                    return string.Empty;

                Directory.CreateDirectory(_runtimeAssetDir);

                string safeItemName = SanitizeFileStem(itemName);
                string extension = Path.GetExtension(sourcePath);
                if (string.IsNullOrWhiteSpace(extension))
                    extension = ".png";

                string stagedPath = Path.Combine(_runtimeAssetDir, $"{safeItemName}_{kind}{extension}");
                string sourceFullPath = Path.GetFullPath(sourcePath);
                string stagedFullPath = Path.GetFullPath(stagedPath);

                if (!string.Equals(sourceFullPath, stagedFullPath, StringComparison.Ordinal))
                    File.Copy(sourceFullPath, stagedFullPath, overwrite: true);

                return stagedFullPath;
            }
            catch (Exception ex)
            {
                Mod.Logger.Error($"[ForgeConnector] StageRuntimeAsset failed for {kind} sprite '{sourcePath}': {ex.Message}");
                return sourcePath;
            }
        }

        private void LogSpritePathResolution(string kind, string rawPath, string stagedPath, bool exists)
        {
            bool rawExists = !string.IsNullOrWhiteSpace(rawPath) && File.Exists(rawPath);
            Mod.Logger.Info(
                $"[ForgeConnector] {kind} sprite raw='{rawPath}' rawExists={rawExists} staged='{stagedPath}' stagedExists={exists}");
        }

        private void WriteLastInjectArtifacts(
            string rawJson,
            string itemName,
            string rawItemSpritePath,
            string stagedItemSpritePath,
            bool itemSpriteExists,
            string rawProjectileSpritePath,
            string stagedProjectileSpritePath,
            bool projectileSpriteExists)
        {
            try
            {
                Directory.CreateDirectory(_modSourcesDir);

                if (!string.IsNullOrWhiteSpace(_lastInjectPath))
                    File.WriteAllText(_lastInjectPath, rawJson);

                if (string.IsNullOrWhiteSpace(_lastInjectDebugPath))
                    return;

                string debugJson = JsonSerializer.Serialize(new
                {
                    item_name = itemName,
                    timestamp = DateTime.UtcNow.ToString("o"),
                    item_sprite = new
                    {
                        raw_path = rawItemSpritePath,
                        staged_path = stagedItemSpritePath,
                        exists = itemSpriteExists,
                    },
                    projectile_sprite = new
                    {
                        raw_path = rawProjectileSpritePath,
                        staged_path = stagedProjectileSpritePath,
                        exists = projectileSpriteExists,
                    },
                }, new JsonSerializerOptions { WriteIndented = true });

                File.WriteAllText(_lastInjectDebugPath, debugJson);
            }
            catch (Exception ex)
            {
                Mod.Logger.Error("[ForgeConnector] WriteLastInjectArtifacts failed: " + ex.Message);
            }
        }

        private static string SanitizeFileStem(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return "InjectedAsset";

            char[] invalidChars = Path.GetInvalidFileNameChars();
            char[] chars = value.ToCharArray();
            for (int i = 0; i < chars.Length; i++)
            {
                if (Array.IndexOf(invalidChars, chars[i]) >= 0 || char.IsWhiteSpace(chars[i]))
                    chars[i] = '_';
            }

            return new string(chars);
        }

        // ------------------------------------------------------------------
        // Reload trigger (legacy path)
        // ------------------------------------------------------------------

        private bool TriggerReload()
        {
            try
            {
                var interfaceType = Type.GetType("Terraria.ModLoader.UI.Interface, tModLoader");
                if (interfaceType == null)
                    interfaceType = Type.GetType("Terraria.GameContent.UI.Interface, Terraria");

                if (interfaceType != null)
                {
                    var field = interfaceType.GetField("reloadModsID",
                        BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);

                    if (field != null)
                    {
                        int reloadId = (int)field.GetValue(null)!;
                        Main.menuMode = reloadId;
                        return true;
                    }
                }
            }
            catch (Exception ex)
            {
                Mod.Logger.Warn("[ForgeConnector] TriggerReload interface reflection failed: " + ex.Message);
            }

            try
            {
                var reloadMethod = typeof(ModLoader)
                    .GetMethod("Reload", BindingFlags.Static | BindingFlags.NonPublic);
                if (reloadMethod == null)
                    return false;

                reloadMethod.Invoke(null, null);
                return true;
            }
            catch (Exception ex)
            {
                Mod.Logger.Warn("[ForgeConnector] TriggerReload ModLoader.Reload fallback failed: " + ex.Message);
            }

            return false;
        }

        // ------------------------------------------------------------------
        // Status writer
        // ------------------------------------------------------------------

        private void WriteStatus(string status, string itemName = "", int slot = -1)
        {
            try
            {
                string json;
                if (status == "item_injected" || status == "inject_failed" || status == "item_pending")
                {
                    json = JsonSerializer.Serialize(new
                    {
                        status,
                        item_name = itemName,
                        slot,
                        timestamp = DateTime.UtcNow.ToString("o"),
                    }, new JsonSerializerOptions { WriteIndented = true });
                }
                else
                {
                    json = JsonSerializer.Serialize(new
                    {
                        status,
                        timestamp = DateTime.UtcNow.ToString("o"),
                    }, new JsonSerializerOptions { WriteIndented = true });
                }

                string tmp = _statusPath + ".tmp";
                File.WriteAllText(tmp, json);
                File.Move(tmp, _statusPath, overwrite: true);
            }
            catch (Exception ex)
            {
                Mod.Logger.Error("[ForgeConnector] WriteStatus failed: " + ex);
                try
                {
                    string fail = JsonSerializer.Serialize(new
                    {
                        status = "inject_failed",
                        message = "Could not write forge_connector_status.json: " + ex.Message,
                        timestamp = DateTime.UtcNow.ToString("o"),
                    }, new JsonSerializerOptions { WriteIndented = true });
                    string fallback = Path.Combine(Path.GetDirectoryName(_statusPath) ?? _modSourcesDir, "forge_connector_status.json");
                    File.WriteAllText(fallback + ".tmp", fail);
                    File.Move(fallback + ".tmp", fallback, overwrite: true);
                }
                catch (Exception ex2)
                {
                    Mod.Logger.Error("[ForgeConnector] WriteStatus recovery failed: " + ex2);
                }
            }
        }

        private void UpdateRuntimeSummaryState(string injectStatus = "", string liveItemName = "", bool clearLiveItemName = false, string runtimeNote = "")
        {
            if (!string.IsNullOrWhiteSpace(injectStatus))
                _lastInjectStatus = injectStatus;
            if (clearLiveItemName)
                _lastLiveItemName = string.Empty;
            else if (!string.IsNullOrWhiteSpace(liveItemName))
                _lastLiveItemName = liveItemName;
            if (!string.IsNullOrWhiteSpace(runtimeNote))
                _lastRuntimeNote = runtimeNote;

            WriteRuntimeSummary();
        }

        private void WriteRuntimeSummary(bool force = false)
        {
            if (string.IsNullOrWhiteSpace(_runtimeSummaryPath))
                return;

            try
            {
                Directory.CreateDirectory(_modSourcesDir);

                bool worldLoaded = !Main.gameMenu;
                string note = worldLoaded
                    ? (string.IsNullOrWhiteSpace(_lastRuntimeNote) ? "World loaded." : _lastRuntimeNote)
                    : "At main menu.";
                DateTime now = DateTime.UtcNow;

                string signature = string.Join("|", new[]
                {
                    worldLoaded ? "1" : "0",
                    _lastLiveItemName ?? string.Empty,
                    _lastInjectStatus ?? string.Empty,
                    note,
                });

                if (!force
                    && string.Equals(signature, _lastRuntimeSummarySignature, StringComparison.Ordinal)
                    && now - _lastRuntimeSummaryWriteAt < RuntimeSummaryRefreshInterval)
                    return;

                string json = JsonSerializer.Serialize(new
                {
                    bridge_alive = true,
                    world_loaded = worldLoaded,
                    live_item_name = string.IsNullOrWhiteSpace(_lastLiveItemName) ? null : _lastLiveItemName,
                    last_inject_status = string.IsNullOrWhiteSpace(_lastInjectStatus) ? null : _lastInjectStatus,
                    last_runtime_note = note,
                    updated_at = now.ToString("o"),
                }, new JsonSerializerOptions { WriteIndented = true });

                string tmp = _runtimeSummaryPath + ".tmp";
                File.WriteAllText(tmp, json);
                File.Move(tmp, _runtimeSummaryPath, overwrite: true);
                _lastRuntimeSummarySignature = signature;
                _lastRuntimeSummaryWriteAt = now;
            }
            catch (Exception ex)
            {
                Mod.Logger.Error("[ForgeConnector] WriteRuntimeSummary failed: " + ex.Message);
            }
        }

        // ------------------------------------------------------------------
        // Helpers
        // ------------------------------------------------------------------

        private static string GetModSourcesDir()
        {
            string? env = Environment.GetEnvironmentVariable("FORGE_MOD_SOURCES_DIR");
            if (!string.IsNullOrWhiteSpace(env))
                return env.Trim();

            string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);

            if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            {
                string profile = Environment.GetEnvironmentVariable("USERPROFILE");
                if (string.IsNullOrEmpty(profile))
                    profile = home;
                return Path.Combine(profile, "Documents", "My Games", "Terraria", "tModLoader", "ModSources");
            }

            if (RuntimeInformation.IsOSPlatform(OSPlatform.Linux))
            {
                return Path.Combine(home, ".local", "share", "Terraria", "tModLoader", "ModSources");
            }

            return Path.Combine(home, "Library", "Application Support", "Terraria", "tModLoader", "ModSources");
        }

        private void WriteHeartbeat()
        {
            try
            {
                Directory.CreateDirectory(_modSourcesDir);

                var payload = new
                {
                    status     = "listening",
                    loaded_at  = DateTime.UtcNow.ToString("o"),
                    pid        = Environment.ProcessId,
                    version    = "2.0.0",
                    mod_sources_dir = _modSourcesDir,
                    capabilities = new[] { "reload", "inject", "compiled_item_inject" },
                };

                string json = JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true });
                string tmp = _heartbeatPath + ".tmp";
                File.WriteAllText(tmp, json);
                File.Move(tmp, _heartbeatPath, overwrite: true);
            }
            catch (Exception ex)
            {
                Mod.Logger.Warn("[ForgeConnector] WriteHeartbeat failed: " + ex.Message);
            }
        }

        private static string NormalizeContentType(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return "Weapon";

            return value.Trim();
        }

        private static int ParseRarity(string rarityStr) => rarityStr switch
        {
            "ItemRarityID.White" => ItemRarityID.White,
            "ItemRarityID.Blue" => ItemRarityID.Blue,
            "ItemRarityID.Green" => ItemRarityID.Green,
            "ItemRarityID.Orange" => ItemRarityID.Orange,
            "ItemRarityID.LightRed" => ItemRarityID.LightRed,
            "ItemRarityID.Pink" => ItemRarityID.Pink,
            "ItemRarityID.LightPurple" => ItemRarityID.LightPurple,
            "ItemRarityID.Lime" => ItemRarityID.Lime,
            "ItemRarityID.Yellow" => ItemRarityID.Yellow,
            "ItemRarityID.Cyan" => ItemRarityID.Cyan,
            "ItemRarityID.Red" => ItemRarityID.Red,
            "ItemRarityID.Purple" => ItemRarityID.Purple,
            _ => ItemRarityID.White,
        };

        private static string GetStr(JsonElement el, string prop, string def = "")
        {
            return el.ValueKind == JsonValueKind.Object && el.TryGetProperty(prop, out var v)
                ? v.GetString() ?? def
                : def;
        }

        private static int GetInt(JsonElement el, string prop, int def = 0)
        {
            return el.ValueKind == JsonValueKind.Object && el.TryGetProperty(prop, out var v) && v.TryGetInt32(out int i)
                ? i
                : def;
        }

        private static float GetFloat(JsonElement el, string prop, float def = 0f)
        {
            return el.ValueKind == JsonValueKind.Object && el.TryGetProperty(prop, out var v) && v.TryGetDouble(out double d)
                ? (float)d
                : def;
        }

        private static bool GetBool(JsonElement el, string prop, bool def = false)
        {
            return el.ValueKind == JsonValueKind.Object && el.TryGetProperty(prop, out var v) && v.ValueKind is JsonValueKind.True or JsonValueKind.False
                ? v.GetBoolean()
                : def;
        }
    }
}
