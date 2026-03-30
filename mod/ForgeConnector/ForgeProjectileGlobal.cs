using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.ModLoader;
using ForgeConnector.Content.Projectiles;

namespace ForgeConnector
{
    /// <summary>
    /// GlobalProjectile that intercepts template projectiles and dynamically
    /// applies stats and custom textures from ForgeManifestStore.
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

        // -----------------------------------------------------------
        // On-hit effects
        // -----------------------------------------------------------

        public override void OnHitNPC(Projectile projectile, NPC target, NPC.HitInfo hit, int damageDone)
        {
            if (projectile.ModProjectile is not ForgeTemplateProjectile template)
                return;

            var data = ForgeManifestStore.GetProjectile(template.SlotIndex);
            if (data == null)
                return;

            // Projectile on-hit effects can be extended here if the manifest supports them
        }
    }
}
