using System.Collections.Generic;
using Microsoft.Xna.Framework.Graphics;

namespace ForgeConnector
{
    /// <summary>
    /// Data record describing a forged item's stats, appearance, and behavior.
    /// Populated from the forge_inject.json manifest at runtime.
    /// </summary>
    public class ForgeItemData
    {
        // Identity
        public string Name { get; set; } = "";
        public string DisplayName { get; set; } = "";
        public string Tooltip { get; set; } = "";
        public string SubType { get; set; } = "Sword";

        // Core stats
        public int Damage { get; set; } = 10;
        public float Knockback { get; set; } = 4f;
        public int CritChance { get; set; } = 4;
        public int UseTime { get; set; } = 20;
        public int UseAnimation { get; set; } = 20;
        public bool AutoReuse { get; set; } = true;

        // Appearance
        public int Width { get; set; } = 32;
        public int Height { get; set; } = 32;
        public float Scale { get; set; } = 1f;
        public int Rarity { get; set; } = 0;
        public int Value { get; set; } = 0;

        // Damage class: "Melee", "Ranged", "Magic", "Summon"
        public string DamageClassName { get; set; } = "Melee";

        // Use style: "Swing", "Shoot", "Thrust"
        public string UseStyleName { get; set; } = "Swing";

        // Combat
        public bool NoMelee { get; set; } = false;
        public int ShootProjectileSlot { get; set; } = -1; // template projectile slot, -1 = none
        public float ShootSpeed { get; set; } = 0f;

        // Buffs
        public int BuffType { get; set; } = 0;
        public int BuffTime { get; set; } = 0;

        // Healing
        public int HealLife { get; set; } = 0;
        public int HealMana { get; set; } = 0;

        // Tool power
        public int PickPower { get; set; } = 0;
        public int AxePower { get; set; } = 0;   // internal value; display = value * 5
        public int HammerPower { get; set; } = 0;

        // Misc
        public int Defense { get; set; } = 0;
        public bool Accessory { get; set; } = false;
        public bool Consumable { get; set; } = false;
        public int MaxStack { get; set; } = 1;
    }

    /// <summary>
    /// Data record describing a forged projectile's behavior.
    /// </summary>
    public class ForgeProjectileData
    {
        public string Name { get; set; } = "";
        public int Width { get; set; } = 16;
        public int Height { get; set; } = 16;
        public int Penetrate { get; set; } = 1;
        public int TimeLeft { get; set; } = 600;
        public bool Friendly { get; set; } = true;
        public bool Hostile { get; set; } = false;
        public float AiStyle { get; set; } = 0f;
        public float Light { get; set; } = 0f;
    }

    /// <summary>
    /// Static singleton mapping template slot indices to item/projectile data
    /// and runtime-loaded textures. All access happens on the main thread
    /// after the Interlocked.Exchange gate in ForgeConnectorSystem.
    /// </summary>
    public static class ForgeManifestStore
    {
        public const int MaxItemSlots = 50;
        public const int MaxProjectileSlots = 25;

        private static readonly Dictionary<int, ForgeItemData> _items = new();
        private static readonly Dictionary<int, ForgeProjectileData> _projectiles = new();
        private static readonly Dictionary<int, Texture2D> _itemTextures = new();
        private static readonly Dictionary<int, Texture2D> _projectileTextures = new();

        private static int _nextItemSlot = 0;
        private static int _nextProjectileSlot = 0;

        // Map from template slot index → registered tModLoader item type ID
        private static readonly Dictionary<int, int> _itemTypeIds = new();
        private static readonly Dictionary<int, int> _projectileTypeIds = new();

        /// <summary>Returns the next available item slot (round-robin).</summary>
        public static int NextItemSlot()
        {
            int slot = _nextItemSlot;
            _nextItemSlot = (_nextItemSlot + 1) % MaxItemSlots;
            return slot;
        }

        /// <summary>Returns the next available projectile slot (round-robin).</summary>
        public static int NextProjectileSlot()
        {
            int slot = _nextProjectileSlot;
            _nextProjectileSlot = (_nextProjectileSlot + 1) % MaxProjectileSlots;
            return slot;
        }

        public static void RegisterItem(int slot, ForgeItemData data) => _items[slot] = data;
        public static void RegisterProjectile(int slot, ForgeProjectileData data) => _projectiles[slot] = data;

        public static void SetItemTexture(int slot, Texture2D tex)
        {
            if (_itemTextures.TryGetValue(slot, out var old)) old?.Dispose();
            _itemTextures[slot] = tex;
        }

        public static void SetProjectileTexture(int slot, Texture2D tex)
        {
            if (_projectileTextures.TryGetValue(slot, out var old)) old?.Dispose();
            _projectileTextures[slot] = tex;
        }

        public static void RegisterItemTypeId(int slot, int typeId) => _itemTypeIds[slot] = typeId;
        public static void RegisterProjectileTypeId(int slot, int typeId) => _projectileTypeIds[slot] = typeId;

        public static ForgeItemData GetItem(int slot) => _items.TryGetValue(slot, out var d) ? d : null;
        public static ForgeProjectileData GetProjectile(int slot) => _projectiles.TryGetValue(slot, out var d) ? d : null;
        public static Texture2D GetItemTexture(int slot) => _itemTextures.TryGetValue(slot, out var t) ? t : null;
        public static Texture2D GetProjectileTexture(int slot) => _projectileTextures.TryGetValue(slot, out var t) ? t : null;

        public static int GetItemTypeId(int slot) => _itemTypeIds.TryGetValue(slot, out var id) ? id : -1;
        public static int GetProjectileTypeId(int slot) => _projectileTypeIds.TryGetValue(slot, out var id) ? id : -1;

        public static bool HasItem(int slot) => _items.ContainsKey(slot);
        public static bool HasProjectile(int slot) => _projectiles.ContainsKey(slot);

        public static void Clear()
        {
            // Don't Dispose textures here — Unload() runs on a worker thread
            // and Texture2D.Dispose() requires the main thread (FNA ThreadCheck).
            // The textures are tiny and will be reclaimed on process/device reset.
            _items.Clear();
            _projectiles.Clear();
            _itemTextures.Clear();
            _projectileTextures.Clear();
            _nextItemSlot = 0;
            _nextProjectileSlot = 0;
        }
    }
}
