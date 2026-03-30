using System.Collections.Generic;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;
using Terraria.UI.Chat;
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
            item.maxStack = data.MaxStack;

            // Damage class
            item.DamageType = data.DamageClassName switch
            {
                "Ranged" => DamageClass.Ranged,
                "Magic" => DamageClass.Magic,
                "Summon" => DamageClass.Summon,
                _ => DamageClass.Melee,
            };

            // Use style
            item.useStyle = data.UseStyleName switch
            {
                "Shoot" => ItemUseStyleID.Shoot,
                "Drink" => ItemUseStyleID.DrinkLiquid,
                "EatFood" => ItemUseStyleID.EatFood,
                _ => ItemUseStyleID.Swing,
            };

            // Sound
            item.UseSound = data.UseStyleName switch
            {
                "Shoot" => SoundID.Item11,
                _ => SoundID.Item1,
            };

            // Projectile
            if (data.ShootProjectileSlot >= 0)
            {
                int projTypeId = ForgeManifestStore.GetProjectileTypeId(data.ShootProjectileSlot);
                if (projTypeId > 0)
                {
                    item.shoot = projTypeId;
                    item.shootSpeed = data.ShootSpeed;
                }
            }

            // Buff (accessories / potions)
            if (data.BuffType > 0)
            {
                item.buffType = data.BuffType;
                item.buffTime = data.BuffTime;
            }
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

            // Replace the item name
            var nameLine = tooltips.Find(t => t.Name == "ItemName" && t.Mod == "Terraria");
            if (nameLine != null)
                nameLine.Text = data.DisplayName;

            // Add custom tooltip
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
