using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Threading;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;
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

        private FileSystemWatcher? _watcher;
        private string _modSourcesDir = string.Empty;
        private string _triggerPath = string.Empty;
        private string _injectPath = string.Empty;
        private string _heartbeatPath = string.Empty;
        private string _statusPath = string.Empty;

        // Mapping from slot index → tModLoader type IDs (populated once at load)
        private static readonly Dictionary<int, int> _slotToItemType = new();
        private static readonly Dictionary<int, int> _slotToProjectileType = new();

        // ------------------------------------------------------------------
        // Lifecycle
        // ------------------------------------------------------------------

        public override void PostSetupContent()
        {
            _modSourcesDir = GetModSourcesDir();
            _triggerPath   = Path.Combine(_modSourcesDir, "command_trigger.json");
            _injectPath    = Path.Combine(_modSourcesDir, "forge_inject.json");
            _heartbeatPath = Path.Combine(_modSourcesDir, "forge_connector_alive.json");
            _statusPath    = Path.Combine(_modSourcesDir, "forge_connector_status.json");

            RegisterTemplateTypeIds();
            WriteHeartbeat();
            StartWatcher();
        }

        public override void Unload()
        {
            _watcher?.Dispose();
            _watcher = null;
            _slotToItemType.Clear();
            _slotToProjectileType.Clear();
            ForgeManifestStore.Clear();

            try { File.Delete(_heartbeatPath); } catch { /* best-effort */ }
        }

        /// <summary>
        /// Registers the tModLoader type IDs for all template items/projectiles
        /// so we can spawn them by slot index at runtime.
        /// </summary>
        private void RegisterTemplateTypeIds()
        {
            // Items: ForgeItem_001 through ForgeItem_050
            var itemTypes = new Type[]
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
            };

            for (int i = 0; i < itemTypes.Length; i++)
            {
                // ModContent.ItemType<T>() via reflection since we can't use generics with a runtime Type
                var method = typeof(ModContent).GetMethod("ItemType", Type.EmptyTypes);
                var generic = method?.MakeGenericMethod(itemTypes[i]);
                if (generic != null)
                {
                    int typeId = (int)generic.Invoke(null, null)!;
                    _slotToItemType[i] = typeId;
                    ForgeManifestStore.RegisterItemTypeId(i, typeId);
                }
            }

            // Projectiles: ForgeProjectile_001 through ForgeProjectile_025
            var projTypes = new Type[]
            {
                typeof(ForgeProjectile_001), typeof(ForgeProjectile_002), typeof(ForgeProjectile_003), typeof(ForgeProjectile_004), typeof(ForgeProjectile_005),
                typeof(ForgeProjectile_006), typeof(ForgeProjectile_007), typeof(ForgeProjectile_008), typeof(ForgeProjectile_009), typeof(ForgeProjectile_010),
                typeof(ForgeProjectile_011), typeof(ForgeProjectile_012), typeof(ForgeProjectile_013), typeof(ForgeProjectile_014), typeof(ForgeProjectile_015),
                typeof(ForgeProjectile_016), typeof(ForgeProjectile_017), typeof(ForgeProjectile_018), typeof(ForgeProjectile_019), typeof(ForgeProjectile_020),
                typeof(ForgeProjectile_021), typeof(ForgeProjectile_022), typeof(ForgeProjectile_023), typeof(ForgeProjectile_024), typeof(ForgeProjectile_025),
            };

            for (int i = 0; i < projTypes.Length; i++)
            {
                var method = typeof(ModContent).GetMethod("ProjectileType", Type.EmptyTypes);
                var generic = method?.MakeGenericMethod(projTypes[i]);
                if (generic != null)
                {
                    int typeId = (int)generic.Invoke(null, null)!;
                    _slotToProjectileType[i] = typeId;
                    ForgeManifestStore.RegisterProjectileTypeId(i, typeId);
                }
            }
        }

        // ------------------------------------------------------------------
        // Main-thread hook
        // ------------------------------------------------------------------

        public override void PostUpdateEverything()
        {
            // Handle legacy reload request
            if (Interlocked.Exchange(ref _reloadRequested, 0) == 1)
            {
                bool triggered = TriggerReload();
                WriteStatus(triggered ? "reload_triggered" : "reload_failed");
            }

            // Handle instant inject request
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
                using JsonDocument doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                if (!root.TryGetProperty("action", out var actionEl) || actionEl.GetString() != "inject")
                    return;

                string itemName = root.TryGetProperty("item_name", out var nameEl) ? nameEl.GetString() ?? "" : "";

                // Parse manifest into ForgeItemData
                var data = ParseManifest(root);

                // Allocate a template slot
                int slot = ForgeManifestStore.NextItemSlot();
                ForgeManifestStore.RegisterItem(slot, data);

                // Load sprite texture
                if (root.TryGetProperty("sprite_path", out var spriteEl))
                {
                    string spritePath = spriteEl.GetString() ?? "";
                    if (File.Exists(spritePath))
                    {
                        LoadItemTexture(slot, spritePath);
                    }
                }

                // Handle projectile if specified
                int projSlot = -1;
                if (data.ShootProjectileSlot >= 0 || root.TryGetProperty("projectile_sprite_path", out var projSpriteEl))
                {
                    projSlot = ForgeManifestStore.NextProjectileSlot();
                    var projData = ParseProjectile(root);
                    ForgeManifestStore.RegisterProjectile(projSlot, projData);
                    data.ShootProjectileSlot = projSlot;
                    ForgeManifestStore.RegisterItem(slot, data); // update with projectile slot

                    if (root.TryGetProperty("projectile_sprite_path", out var pspEl))
                    {
                        string pspPath = pspEl.GetString() ?? "";
                        if (File.Exists(pspPath))
                        {
                            LoadProjectileTexture(projSlot, pspPath);
                        }
                    }
                }

                // Spawn the item into the player's inventory
                int itemTypeId = ForgeManifestStore.GetItemTypeId(slot);
                if (itemTypeId > 0 && Main.LocalPlayer != null)
                {
                    Main.LocalPlayer.QuickSpawnItem(Main.LocalPlayer.GetSource_Misc("ForgeConnector"), itemTypeId);
                }

                WriteStatus("item_injected", itemName, slot);
            }
            catch (Exception ex)
            {
                WriteStatus("inject_failed", ex.Message, -1);
            }
        }

        private ForgeItemData ParseManifest(JsonElement root)
        {
            var data = new ForgeItemData();

            if (root.TryGetProperty("manifest", out var manifest))
            {
                data.Name = GetStr(manifest, "item_name");
                data.DisplayName = GetStr(manifest, "display_name", data.Name);
                data.Tooltip = GetStr(manifest, "tooltip");
                data.SubType = GetStr(manifest, "sub_type", "Sword");

                if (manifest.TryGetProperty("stats", out var stats))
                {
                    data.Damage = GetInt(stats, "damage", 10);
                    data.Knockback = GetFloat(stats, "knockback", 4f);
                    data.CritChance = GetInt(stats, "crit_chance", 4);
                    data.UseTime = GetInt(stats, "use_time", 20);
                    data.UseAnimation = GetInt(stats, "use_time", 20); // same as use_time by default
                    data.AutoReuse = GetBool(stats, "auto_reuse", true);
                    data.Rarity = ParseRarity(GetStr(stats, "rarity", "ItemRarityID.White"));
                }

                if (manifest.TryGetProperty("visuals", out var visuals))
                {
                    if (visuals.TryGetProperty("icon_size", out var iconSize) && iconSize.GetArrayLength() >= 2)
                    {
                        data.Width = iconSize[0].GetInt32();
                        data.Height = iconSize[1].GetInt32();
                    }
                }

                if (manifest.TryGetProperty("mechanics", out var mechanics))
                {
                    data.ShootProjectileSlot = mechanics.TryGetProperty("custom_projectile", out var cp) && cp.GetBoolean() ? 0 : -1;
                }

                // Map sub_type to damage class and use style
                data.DamageClassName = data.SubType switch
                {
                    "Gun" or "Bow" => "Ranged",
                    "Staff" => "Magic",
                    "Summon" => "Summon",
                    _ => "Melee",
                };
                data.UseStyleName = data.SubType switch
                {
                    "Gun" or "Bow" or "Staff" => "Shoot",
                    _ => "Swing",
                };
                data.NoMelee = data.UseStyleName == "Shoot";
                data.ShootSpeed = data.UseStyleName == "Shoot" ? 10f : 0f;
            }

            if (root.TryGetProperty("item_name", out var rootName))
                data.Name = rootName.GetString() ?? data.Name;

            return data;
        }

        private ForgeProjectileData ParseProjectile(JsonElement root)
        {
            var data = new ForgeProjectileData();

            if (root.TryGetProperty("manifest", out var manifest))
            {
                if (manifest.TryGetProperty("projectile_visuals", out var pv))
                {
                    if (pv.TryGetProperty("icon_size", out var iconSize) && iconSize.GetArrayLength() >= 2)
                    {
                        data.Width = iconSize[0].GetInt32();
                        data.Height = iconSize[1].GetInt32();
                    }
                }
            }

            return data;
        }

        private void LoadItemTexture(int slot, string path)
        {
            try
            {
                using var stream = File.OpenRead(path);
                var tex = Texture2D.FromStream(Main.graphics.GraphicsDevice, stream);
                ForgeManifestStore.SetItemTexture(slot, tex);
            }
            catch { /* best-effort */ }
        }

        private void LoadProjectileTexture(int slot, string path)
        {
            try
            {
                using var stream = File.OpenRead(path);
                var tex = Texture2D.FromStream(Main.graphics.GraphicsDevice, stream);
                ForgeManifestStore.SetProjectileTexture(slot, tex);
            }
            catch { /* best-effort */ }
        }

        // ------------------------------------------------------------------
        // FileSystemWatcher
        // ------------------------------------------------------------------

        private void StartWatcher()
        {
            if (!Directory.Exists(_modSourcesDir))
                return;

            _watcher = new FileSystemWatcher(_modSourcesDir)
            {
                Filter = "*.json",
                NotifyFilter = NotifyFilters.FileName | NotifyFilters.LastWrite,
                EnableRaisingEvents = true,
            };

            _watcher.Created += OnJsonEvent;
            _watcher.Changed += OnJsonEvent;
        }

        private void OnJsonEvent(object sender, FileSystemEventArgs e)
        {
            string fileName = Path.GetFileName(e.FullPath);

            if (fileName == "command_trigger.json")
                HandleCommandTrigger();
            else if (fileName == "forge_inject.json")
                HandleInjectTrigger();
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

                try { File.Delete(_triggerPath); } catch { }

                Interlocked.Exchange(ref _reloadRequested, 1);
            }
            catch { }
        }

        private void HandleInjectTrigger()
        {
            Thread.Sleep(50);

            try
            {
                string json = File.ReadAllText(_injectPath);

                // Delete immediately to prevent double-fire
                try { File.Delete(_injectPath); } catch { }

                // Store JSON for main-thread processing
                Interlocked.Exchange(ref _pendingInjectJson, json);
                Interlocked.Exchange(ref _injectRequested, 1);
            }
            catch { }
        }

        // ------------------------------------------------------------------
        // Reload trigger (legacy path)
        // ------------------------------------------------------------------

        private static bool TriggerReload()
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
            catch { }

            try
            {
                var reloadMethod = typeof(ModLoader)
                    .GetMethod("Reload", BindingFlags.Static | BindingFlags.NonPublic);
                if (reloadMethod == null)
                    return false;

                reloadMethod.Invoke(null, null);
                return true;
            }
            catch { }

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
                if (status == "item_injected" || status == "inject_failed")
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
            catch { }
        }

        // ------------------------------------------------------------------
        // Helpers
        // ------------------------------------------------------------------

        private static string GetModSourcesDir()
        {
            string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
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
                    capabilities = new[] { "reload", "inject" },
                };

                string json = JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true });
                string tmp = _heartbeatPath + ".tmp";
                File.WriteAllText(tmp, json);
                File.Move(tmp, _heartbeatPath, overwrite: true);
            }
            catch { }
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

        private static string GetStr(JsonElement el, string prop, string def = "") =>
            el.TryGetProperty(prop, out var v) ? v.GetString() ?? def : def;

        private static int GetInt(JsonElement el, string prop, int def = 0) =>
            el.TryGetProperty(prop, out var v) && v.TryGetInt32(out int i) ? i : def;

        private static float GetFloat(JsonElement el, string prop, float def = 0f) =>
            el.TryGetProperty(prop, out var v) ? (float)v.GetDouble() : def;

        private static bool GetBool(JsonElement el, string prop, bool def = false) =>
            el.TryGetProperty(prop, out var v) ? v.GetBoolean() : def;
    }
}
