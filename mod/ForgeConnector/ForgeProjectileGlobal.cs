using System;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.ModLoader;
using ForgeConnector.Content.Projectiles;

namespace ForgeConnector
{
    /// <summary>
    /// GlobalProjectile that intercepts template projectiles and dynamically
    /// applies stats, movement modes, and custom textures from ForgeManifestStore.
    /// </summary>
    public class ForgeProjectileGlobal : GlobalProjectile
    {
        public override bool AppliesToEntity(Projectile entity, bool lateInstantiation)
        {
            return entity.ModProjectile is ForgeTemplateProjectile;
        }

        // -----------------------------------------------------------
        // Stats
        // -----------------------------------------------------------

        public override void SetDefaults(Projectile projectile)
        {
            if (projectile.ModProjectile is not ForgeTemplateProjectile template)
                return;

            var data = ForgeManifestStore.GetProjectile(template.SlotIndex);
            if (data == null)
                return;

            projectile.width = data.Width;
            projectile.height = data.Height;
            projectile.penetrate = data.Penetrate;
            projectile.timeLeft = data.TimeLeft;
            projectile.friendly = data.Friendly;
            projectile.hostile = data.Hostile;
            projectile.light = data.Light;

            switch (NormalizeAiMode(data.AiMode))
            {
                case "hook":
                    projectile.aiStyle = 7;
                    projectile.tileCollide = true;
                    projectile.minion = false;
                    projectile.minionSlots = 0f;
                    break;
                case "minion_follower":
                    projectile.aiStyle = 0;
                    projectile.tileCollide = false;
                    projectile.ignoreWater = true;
                    projectile.minion = true;
                    projectile.minionSlots = data.MinionSlots;
                    projectile.DamageType = DamageClass.Summon;
                    projectile.penetrate = -1;
                    projectile.friendly = true;
                    projectile.hostile = false;
                    break;
                default:
                    projectile.aiStyle = (int)data.AiStyle;
                    break;
            }
        }

        public override void AI(Projectile projectile)
        {
            if (projectile.ModProjectile is not ForgeTemplateProjectile template)
                return;

            var data = ForgeManifestStore.GetProjectile(template.SlotIndex);
            if (data == null)
                return;

            switch (NormalizeAiMode(data.AiMode))
            {
                case "minion_follower":
                    RunMinionFollowerAI(projectile, data);
                    break;
                case "hook":
                case "straight":
                default:
                    // Vanilla AI or aiStyle-driven behavior handles these modes.
                    break;
            }
        }

        private static void RunMinionFollowerAI(Projectile projectile, ForgeProjectileData data)
        {
            if (projectile.owner < 0 || projectile.owner >= Main.maxPlayers)
                return;

            Player owner = Main.player[projectile.owner];
            if (!owner.active || owner.dead)
            {
                projectile.Kill();
                return;
            }

            int buffType = ResolveBuffType(data);
            if (buffType > 0 && !owner.HasBuff(buffType))
            {
                projectile.Kill();
                return;
            }

            projectile.timeLeft = 2;
            projectile.minion = true;
            projectile.minionSlots = data.MinionSlots;
            projectile.friendly = true;
            projectile.hostile = false;
            projectile.tileCollide = false;
            projectile.ignoreWater = true;
            projectile.penetrate = -1;
            projectile.DamageType = DamageClass.Summon;

            NPC target = FindTarget(projectile, data.MinionAttackRange > 0f ? data.MinionAttackRange : 600f);

            Vector2 home = owner.Center + new Vector2(owner.direction * 32f, -data.MinionHoverHeight);
            Vector2 goal = home;

            if (target != null)
            {
                goal = target.Center;
            }

            float teleportDistance = data.MinionTeleportDistance > 0f ? data.MinionTeleportDistance : 1200f;
            if (Vector2.DistanceSquared(projectile.Center, owner.Center) > teleportDistance * teleportDistance)
            {
                projectile.Center = owner.Center + new Vector2(owner.direction * 32f, -data.MinionHoverHeight);
                projectile.velocity = Vector2.Zero;
                return;
            }

            Vector2 toGoal = goal - projectile.Center;
            float distance = toGoal.Length();
            if (distance < 1f)
            {
                projectile.velocity *= 0.9f;
            }
            else
            {
                float maxSpeed = data.MinionSpeed > 0f ? data.MinionSpeed : 8f;
                float accel = Math.Clamp(data.MinionAcceleration, 0.01f, 1f);
                Vector2 desiredVelocity = Vector2.Normalize(toGoal) * maxSpeed;
                projectile.velocity = Vector2.Lerp(projectile.velocity, desiredVelocity, accel);

                if (distance < data.MinionAttackRange * 0.5f && target != null)
                {
                    projectile.velocity *= 0.8f;
                }
            }

            if (projectile.velocity.LengthSquared() < 0.01f && target == null)
            {
                Vector2 drift = home - projectile.Center;
                if (drift.LengthSquared() > 4f)
                {
                    projectile.velocity = Vector2.Normalize(drift) * 2f;
                }
            }

            projectile.direction = projectile.velocity.X >= 0f ? 1 : -1;
            projectile.spriteDirection = projectile.direction;
            projectile.rotation = (float)Math.Atan2(projectile.velocity.Y, projectile.velocity.X);
        }

        private static NPC FindTarget(Projectile projectile, float searchRange)
        {
            NPC best = null;
            float bestDistance = searchRange * searchRange;

            for (int i = 0; i < Main.maxNPCs; i++)
            {
                NPC npc = Main.npc[i];
                if (!npc.active || npc.friendly || npc.dontTakeDamage || npc.immortal)
                    continue;

                float distance = Vector2.DistanceSquared(projectile.Center, npc.Center);
                if (distance < bestDistance)
                {
                    bestDistance = distance;
                    best = npc;
                }
            }

            return best;
        }

        private static int ResolveBuffType(ForgeProjectileData data)
        {
            if (data.MinionBuffSlot >= 0)
            {
                int buffType = ForgeManifestStore.GetBuffTypeId(data.MinionBuffSlot);
                if (buffType > 0)
                    return buffType;
            }

            return -1;
        }

        private static string NormalizeAiMode(string mode)
        {
            if (string.IsNullOrWhiteSpace(mode))
                return "straight";

            return mode.Trim().ToLowerInvariant();
        }

        // -----------------------------------------------------------
        // Custom texture drawing
        // -----------------------------------------------------------

        public override bool PreDraw(Projectile projectile, ref Color lightColor)
        {
            if (projectile.ModProjectile is not ForgeTemplateProjectile template)
                return true;

            var tex = ForgeManifestStore.GetProjectileTexture(template.SlotIndex);
            if (tex == null)
                return true; // fall back to placeholder

            Vector2 drawPos = projectile.Center - Main.screenPosition;
            Vector2 origin = new Vector2(tex.Width / 2f, tex.Height / 2f);

            Main.EntitySpriteDraw(tex, drawPos, null, lightColor, projectile.rotation,
                origin, projectile.scale, SpriteEffects.None, 0);
            return false;
        }
    }
}
