using System;
using System.Collections.Generic;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.DataStructures;
using Terraria.ID;
using Terraria.ModLoader;
using ForgeConnector.Content.Items;

namespace ForgeConnector
{
    /// <summary>
    /// GlobalItem that intercepts all template items and dynamically applies
    /// stats, tooltips, and custom textures from ForgeManifestStore.
    /// </summary>
    public class ForgeItemGlobal : GlobalItem
    {
        public override bool AppliesToEntity(Item entity, bool lateInstantiation)
        {
            return entity.ModItem is ForgeTemplateItem;
        }

        // -----------------------------------------------------------
        // Stats
        // -----------------------------------------------------------

        public override void SetDefaults(Item item)
        {
            if (item.ModItem is not ForgeTemplateItem template)
                return;

            var data = ForgeManifestStore.GetItem(template.SlotIndex);
            if (data == null)
                return;

            ApplyCommonDefaults(item, data);

            switch (data.ContentType)
            {
                case "Accessory":
                    ApplyAccessoryDefaults(item, data);
                    break;
                case "Summon":
                    ApplySummonDefaults(item, data);
                    break;
                case "Consumable":
                    ApplyConsumableDefaults(item, data);
                    break;
                case "Tool":
                    ApplyToolDefaults(item, data);
                    break;
                default:
                    ApplyWeaponDefaults(item, data);
                    break;
            }

            if (!string.Equals(data.ContentType, "Summon", StringComparison.OrdinalIgnoreCase) && data.BuffType > 0)
            {
                item.buffType = data.BuffType;
                item.buffTime = data.BuffTime;
            }
        }

        private static void ApplyCommonDefaults(Item item, ForgeItemData data)
        {
            if (!string.IsNullOrEmpty(data.DisplayName))
                item.SetNameOverride(data.DisplayName);

            item.width = data.Width;
            item.height = data.Height;
            item.scale = data.Scale;
            item.damage = data.Damage;
            item.knockBack = data.Knockback;
            item.crit = data.CritChance;
            item.useTime = data.UseTime;
            item.useAnimation = data.UseAnimation;
            item.autoReuse = data.AutoReuse;
            item.rare = data.Rarity;
            item.value = data.Value;
            item.noMelee = data.NoMelee;
            item.healLife = data.HealLife;
            item.healMana = data.HealMana;
            item.defense = data.Defense;
            item.accessory = data.Accessory;
            item.consumable = data.Consumable;
            item.maxStack = Math.Max(1, data.MaxStack);

            item.pick = data.PickPower;
            item.axe = data.AxePower;
            item.hammer = data.HammerPower;
            item.fishingPole = data.FishingPower;
        }

        private static void ApplyWeaponDefaults(Item item, ForgeItemData data)
        {
            item.DamageType = data.DamageClassName switch
            {
                "Ranged" => DamageClass.Ranged,
                "Magic" => DamageClass.Magic,
                "Summon" => DamageClass.Summon,
                _ => DamageClass.Melee,
            };

            item.useStyle = data.UseStyleName switch
            {
                "Shoot" => ItemUseStyleID.Shoot,
                "Thrust" => ItemUseStyleID.Thrust,
                "Drink" => ItemUseStyleID.DrinkLiquid,
                "EatFood" => ItemUseStyleID.EatFood,
                "HoldUp" => ItemUseStyleID.HoldUp,
                _ => ItemUseStyleID.Swing,
            };

            item.UseSound = data.UseStyleName switch
            {
                "Shoot" => SoundID.Item11,
                "Thrust" => SoundID.Item1,
                "HoldUp" => SoundID.Item4,
                _ => SoundID.Item1,
            };

            ApplyProjectileDefaults(item, data);
            ApplyAmmoDefaults(item, data);
        }

        private static void ApplyAccessoryDefaults(Item item, ForgeItemData data)
        {
            item.accessory = true;
            item.noMelee = true;
            item.DamageType = DamageClass.Melee;
            item.useStyle = ItemUseStyleID.HoldUp;
            item.UseSound = SoundID.Item4;
        }

        private static void ApplySummonDefaults(Item item, ForgeItemData data)
        {
            item.DamageType = DamageClass.Summon;
            item.noMelee = true;
            item.useStyle = ItemUseStyleID.Shoot;
            item.UseSound = SoundID.Item44;

            int buffType = ResolveSummonBuffType(data);
            if (buffType > 0)
            {
                item.buffType = buffType;
                item.buffTime = 0;
            }

            ApplyProjectileDefaults(item, data);
        }

        private static void ApplyConsumableDefaults(Item item, ForgeItemData data)
        {
            item.consumable = true;
            item.maxStack = Math.Max(1, data.MaxStack);
            item.noMelee = true;
            item.DamageType = DamageClass.Melee;

            if (data.HealMana > 0)
                item.useStyle = ItemUseStyleID.DrinkLiquid;
            else if (data.HealLife > 0)
                item.useStyle = ItemUseStyleID.EatFood;
            else
                item.useStyle = ItemUseStyleID.Swing;

            item.UseSound = item.useStyle == ItemUseStyleID.DrinkLiquid ? SoundID.Item3 : SoundID.Item4;
        }

        private static void ApplyToolDefaults(Item item, ForgeItemData data)
        {
            if (string.Equals(data.SubType, "Hook", StringComparison.OrdinalIgnoreCase))
            {
                item.noMelee = true;
                item.useStyle = ItemUseStyleID.Shoot;
                item.UseSound = SoundID.Item1;
                item.DamageType = DamageClass.Melee;
                item.shoot = ResolveHookProjectileType(data);
                item.shootSpeed = data.ShootSpeed > 0f ? data.ShootSpeed : 16f;
                return;
            }

            if (string.Equals(data.SubType, "Fishing", StringComparison.OrdinalIgnoreCase))
            {
                item.noMelee = true;
                item.useStyle = ItemUseStyleID.Shoot;
                item.UseSound = SoundID.Item1;
                item.DamageType = DamageClass.Melee;
                item.fishingPole = Math.Max(1, data.FishingPower);
                item.shoot = ResolveFishingProjectileType(data);
                item.shootSpeed = data.ShootSpeed > 0f ? data.ShootSpeed : 11f;
                return;
            }

            item.DamageType = DamageClass.Melee;
            item.useStyle = data.UseStyleName switch
            {
                "Shoot" => ItemUseStyleID.Shoot,
                "Thrust" => ItemUseStyleID.Thrust,
                "HoldUp" => ItemUseStyleID.HoldUp,
                _ => ItemUseStyleID.Swing,
            };

            item.UseSound = data.UseStyleName switch
            {
                "Shoot" => SoundID.Item11,
                "Thrust" => SoundID.Item1,
                _ => SoundID.Item1,
            };

            ApplyProjectileDefaults(item, data);
            ApplyAmmoDefaults(item, data);
        }

        private static void ApplyProjectileDefaults(Item item, ForgeItemData data)
        {
            int projectileType = ResolveProjectileType(data);
            if (projectileType > 0)
            {
                item.shoot = projectileType;
                item.shootSpeed = data.ShootSpeed > 0f ? data.ShootSpeed : 10f;
            }
        }

        private static void ApplyAmmoDefaults(Item item, ForgeItemData data)
        {
            if (data.UseAmmoTypeId > 0)
                item.useAmmo = data.UseAmmoTypeId;
        }

        private static int ResolveProjectileType(ForgeItemData data)
        {
            if (data.ShootProjectileTypeId > 0)
                return data.ShootProjectileTypeId;

            if (data.ShootProjectileSlot >= 0)
            {
                int projTypeId = ForgeManifestStore.GetProjectileTypeId(data.ShootProjectileSlot);
                if (projTypeId > 0)
                    return projTypeId;
            }

            return -1;
        }

        private static int ResolveHookProjectileType(ForgeItemData data)
        {
            if (data.HookProjectileSlot >= 0)
            {
                int projTypeId = ForgeManifestStore.GetProjectileTypeId(data.HookProjectileSlot);
                if (projTypeId > 0)
                    return projTypeId;
            }

            int resolved = ResolveProjectileType(data);
            if (resolved > 0)
                return resolved;

            return ProjectileID.GemHookAmethyst;
        }

        private static int ResolveFishingProjectileType(ForgeItemData data)
        {
            int resolved = ResolveProjectileType(data);
            if (resolved > 0)
                return resolved;

            return ProjectileID.BobberWooden;
        }

        private static int ResolveSummonBuffType(ForgeItemData data)
        {
            if (data.BuffTemplateSlot >= 0)
            {
                int buffTypeId = ForgeManifestStore.GetBuffTypeId(data.BuffTemplateSlot);
                if (buffTypeId > 0)
                    return buffTypeId;
            }

            return data.BuffType;
        }

        // -----------------------------------------------------------
        // Use hooks
        // -----------------------------------------------------------

        public override bool Shoot(Item item, Player player, EntitySource_ItemUse_WithAmmo source, Vector2 position, Vector2 velocity, int type, int damage, float knockback)
        {
            if (item.ModItem is not ForgeTemplateItem template)
                return true;

            var data = ForgeManifestStore.GetItem(template.SlotIndex);
            if (data == null)
                return true;

            ForgeLabTelemetryContext telemetryContext = ForgeLabTelemetry.GetItemContext(template.SlotIndex);
            ForgeLabTelemetry.Emit(
                telemetryContext,
                "seed_triggered",
                fxMarker: "storm_seed_cast",
                audioMarker: "storm_seed_cast");

            if (string.Equals(data.ContentType, "Summon", StringComparison.OrdinalIgnoreCase))
            {
                int buffType = ResolveSummonBuffType(data);
                if (buffType > 0)
                    player.AddBuff(buffType, 2);
            }

            return true;
        }

        // -----------------------------------------------------------
        // Tooltips
        // -----------------------------------------------------------

        public override void ModifyTooltips(Item item, List<TooltipLine> tooltips)
        {
            if (item.ModItem is not ForgeTemplateItem template)
                return;

            var data = ForgeManifestStore.GetItem(template.SlotIndex);
            if (data == null)
                return;

            var nameLine = tooltips.Find(t => t.Name == "ItemName" && t.Mod == "Terraria");
            if (nameLine != null && !string.IsNullOrEmpty(data.DisplayName))
                nameLine.Text = data.DisplayName;

            if (!string.IsNullOrEmpty(data.Tooltip))
            {
                int insertIdx = tooltips.FindIndex(t => t.Name == "ItemName" && t.Mod == "Terraria");
                if (insertIdx >= 0)
                {
                    tooltips.Insert(insertIdx + 1,
                        new TooltipLine(Mod, "ForgeTooltip", data.Tooltip));
                }
            }
        }

        // -----------------------------------------------------------
        // Custom texture drawing (inventory)
        // -----------------------------------------------------------

        public override bool PreDrawInInventory(Item item, SpriteBatch spriteBatch,
            Vector2 position, Rectangle frame, Color drawColor, Color itemColor, Vector2 origin, float scale)
        {
            if (item.ModItem is not ForgeTemplateItem template)
                return true;

            var tex = ForgeManifestStore.GetItemTexture(template.SlotIndex);
            if (tex == null)
                return true; // fall back to placeholder

            spriteBatch.Draw(tex, position, null, drawColor, 0f, origin, scale, SpriteEffects.None, 0f);
            return false; // skip default draw
        }

        // -----------------------------------------------------------
        // Custom texture drawing (world)
        // -----------------------------------------------------------

        public override bool PreDrawInWorld(Item item, SpriteBatch spriteBatch,
            Color lightColor, Color alphaColor, ref float rotation, ref float scale, int whoAmI)
        {
            if (item.ModItem is not ForgeTemplateItem template)
                return true;

            var tex = ForgeManifestStore.GetItemTexture(template.SlotIndex);
            if (tex == null)
                return true;

            Vector2 drawPos = item.position - Main.screenPosition + new Vector2(item.width / 2f, item.height / 2f);
            Vector2 texOrigin = new Vector2(tex.Width / 2f, tex.Height / 2f);

            spriteBatch.Draw(tex, drawPos, null, lightColor, rotation, texOrigin, scale, SpriteEffects.None, 0f);
            return false;
        }

        // -----------------------------------------------------------
        // On-hit buff application
        // -----------------------------------------------------------

        public override void OnHitNPC(Item item, Player player, NPC target, NPC.HitInfo hit, int damageDone)
        {
            if (item.ModItem is not ForgeTemplateItem template)
                return;

            var data = ForgeManifestStore.GetItem(template.SlotIndex);
            if (data == null || data.BuffType <= 0)
                return;

            target.AddBuff(data.BuffType, data.BuffTime);
        }
    }
}
