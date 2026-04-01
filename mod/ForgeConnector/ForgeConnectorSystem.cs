using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Threading;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using ReLogic.Content;
using Terraria;
using Terraria.GameContent;
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

        private FileSystemWatcher _watcher;
        private string _modSourcesDir = string.Empty;
        private string _triggerPath = string.Empty;
        private string _injectPath = string.Empty;
        private string _heartbeatPath = string.Empty;
        private string _statusPath = string.Empty;

        // (Type ID mappings stored in ForgeManifestStore)

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

            // Hoist reflection lookup outside loop
            var itemTypeMethod = typeof(ModContent).GetMethod("ItemType", Type.EmptyTypes);
            for (int i = 0; i < itemTypes.Length; i++)
            {
                var generic = itemTypeMethod?.MakeGenericMethod(itemTypes[i]);
                if (generic != null)
                {
                    int typeId = (int)generic.Invoke(null, null)!;
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

            var projTypeMethod = typeof(ModContent).GetMethod("ProjectileType", Type.EmptyTypes);
            for (int i = 0; i < projTypes.Length; i++)
            {
                var generic = projTypeMethod?.MakeGenericMethod(projTypes[i]);
                if (generic != null)
                {
                    int typeId = (int)generic.Invoke(null, null)!;
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

            TryProcessInject();
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
                bool hasProjectile = data.ShootProjectileSlot >= 0;
                string projSpritePath = "";
                if (root.TryGetProperty("projectile_sprite_path", out var projSpriteEl)
                    && projSpriteEl.ValueKind == JsonValueKind.String)
                {
                    projSpritePath = projSpriteEl.GetString() ?? "";
                    if (projSpritePath == "None" || projSpritePath == "null")
                        projSpritePath = "";
                    if (!string.IsNullOrEmpty(projSpritePath) && File.Exists(projSpritePath))
                        hasProjectile = true;
                }

                if (hasProjectile)
                {
                    int projSlot = ForgeManifestStore.NextProjectileSlot();
                    var projData = ParseProjectile(root);
                    ForgeManifestStore.RegisterProjectile(projSlot, projData);
                    data.ShootProjectileSlot = projSlot;
                    ForgeManifestStore.RegisterItem(slot, data);

                    if (!string.IsNullOrEmpty(projSpritePath) && File.Exists(projSpritePath))
                        LoadProjectileTexture(projSlot, projSpritePath);
                }

                // Spawn the item into the player's inventory
                int itemTypeId = ForgeManifestStore.GetItemTypeId(slot);
                Mod.Logger.Info($"[ForgeConnector] Slot={slot}, TypeId={itemTypeId}, LocalPlayer null={Main.LocalPlayer == null}");
                if (itemTypeId > 0 && Main.LocalPlayer != null)
                {
                    Main.LocalPlayer.QuickSpawnItem(Main.LocalPlayer.GetSource_Misc("ForgeConnector"), itemTypeId);
                    Mod.Logger.Info("[ForgeConnector] Item spawned successfully");
                }

                WriteStatus("item_injected", itemName, slot);
                Mod.Logger.Info("[ForgeConnector] Status written: item_injected");
            }
            catch (Exception ex)
            {
                Mod.Logger.Error("[ForgeConnector] ProcessInject failed: " + ex);
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
                    data.UseAnimation = GetInt(stats, "use_animation", data.UseTime);
                    data.AutoReuse = GetBool(stats, "auto_reuse", true);
                    data.Rarity = ParseRarity(GetStr(stats, "rarity", "ItemRarityID.White"));
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
                    data.ShootProjectileSlot = mechanics.TryGetProperty("custom_projectile", out var cp) && cp.GetBoolean() ? 0 : -1;
                }

                // Map sub_type to damage class and use style.
                // Must stay in sync with the valid sub_types listed in agents/architect/prompts.py.
                data.DamageClassName = data.SubType switch
                {
                    "Gun" or "Bow" or "Repeater" or "Rifle" or "Pistol"
                        or "Shotgun" or "Launcher" or "Cannon" => "Ranged",
                    "Staff" or "Wand" or "Tome" or "Spellbook" => "Magic",
                    _ => "Melee",
                };
                data.UseStyleName = data.SubType switch
                {
                    "Gun" or "Bow" or "Repeater" or "Rifle" or "Pistol"
                        or "Shotgun" or "Launcher" or "Cannon"
                        or "Staff" or "Wand" or "Tome" or "Spellbook" => "Shoot",
                    "Spear" or "Lance" => "Thrust",
                    _ => "Swing",
                };
                data.NoMelee = data.UseStyleName == "Shoot";
                data.ShootSpeed = data.UseStyleName == "Shoot" ? 10f : 0f;

                // Derive tool power from sub_type, scaled by damage as a tier proxy
                if (data.SubType is "Pickaxe" or "Hamaxe")
                    data.PickPower = Math.Clamp(data.Damage * 3, 35, 225);
                if (data.SubType is "Axe" or "Hamaxe")
                    data.AxePower = Math.Clamp(data.Damage / 2, 7, 35);
                if (data.SubType is "Hammer" or "Hamaxe")
                    data.HammerPower = Math.Clamp(data.Damage + 20, 25, 100);
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

                int typeId = ForgeManifestStore.GetItemTypeId(slot);
                if (typeId > 0)
                {
                    if (SetTextureAssetValue(TextureAssets.Item, typeId, tex))
                        Mod.Logger.Info($"[ForgeConnector] Loaded item texture: {path} ({tex.Width}x{tex.Height}) → type {typeId}");
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
                        Mod.Logger.Info($"[ForgeConnector] Loaded projectile texture: {path} ({tex.Width}x{tex.Height}) → type {typeId}");
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

            // ReLogic.Content.Asset<T> stores the value — field name varies by version
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
                try { File.Delete(_injectPath); } catch { }

                // Store JSON for main-thread processing
                Interlocked.Exchange(ref _pendingInjectJson, json);
                Interlocked.Exchange(ref _injectRequested, 1);
            }
            catch (Exception ex)
            {
                Mod.Logger.Error("[ForgeConnector] HandleInjectTrigger failed: " + ex.Message);
            }
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
            el.TryGetProperty(prop, out var v) && v.TryGetDouble(out double d) ? (float)d : def;

        private static bool GetBool(JsonElement el, string prop, bool def = false) =>
            el.TryGetProperty(prop, out var v) && v.ValueKind is JsonValueKind.True or JsonValueKind.False
                ? v.GetBoolean() : def;
    }
}
