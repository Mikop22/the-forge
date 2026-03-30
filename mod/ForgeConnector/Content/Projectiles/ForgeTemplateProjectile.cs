using Terraria;
using Terraria.ModLoader;

namespace ForgeConnector.Content.Projectiles
{
    /// <summary>
    /// Base class for template projectile slots. Each subclass provides a unique SlotIndex.
    /// Real stats are applied at runtime by ForgeProjectileGlobal from the manifest store.
    /// </summary>
    public abstract class ForgeTemplateProjectile : ModProjectile
    {
        public abstract int SlotIndex { get; }

        public override void SetDefaults()
        {
            Projectile.width = 16;
            Projectile.height = 16;
            Projectile.friendly = true;
            Projectile.hostile = false;
            Projectile.penetrate = 1;
            Projectile.timeLeft = 600;
        }
    }

    // 25 template slots (ForgeProjectile_001 through ForgeProjectile_025)
    public class ForgeProjectile_001 : ForgeTemplateProjectile { public override int SlotIndex => 0; }
    public class ForgeProjectile_002 : ForgeTemplateProjectile { public override int SlotIndex => 1; }
    public class ForgeProjectile_003 : ForgeTemplateProjectile { public override int SlotIndex => 2; }
    public class ForgeProjectile_004 : ForgeTemplateProjectile { public override int SlotIndex => 3; }
    public class ForgeProjectile_005 : ForgeTemplateProjectile { public override int SlotIndex => 4; }
    public class ForgeProjectile_006 : ForgeTemplateProjectile { public override int SlotIndex => 5; }
    public class ForgeProjectile_007 : ForgeTemplateProjectile { public override int SlotIndex => 6; }
    public class ForgeProjectile_008 : ForgeTemplateProjectile { public override int SlotIndex => 7; }
    public class ForgeProjectile_009 : ForgeTemplateProjectile { public override int SlotIndex => 8; }
    public class ForgeProjectile_010 : ForgeTemplateProjectile { public override int SlotIndex => 9; }
    public class ForgeProjectile_011 : ForgeTemplateProjectile { public override int SlotIndex => 10; }
    public class ForgeProjectile_012 : ForgeTemplateProjectile { public override int SlotIndex => 11; }
    public class ForgeProjectile_013 : ForgeTemplateProjectile { public override int SlotIndex => 12; }
    public class ForgeProjectile_014 : ForgeTemplateProjectile { public override int SlotIndex => 13; }
    public class ForgeProjectile_015 : ForgeTemplateProjectile { public override int SlotIndex => 14; }
    public class ForgeProjectile_016 : ForgeTemplateProjectile { public override int SlotIndex => 15; }
    public class ForgeProjectile_017 : ForgeTemplateProjectile { public override int SlotIndex => 16; }
    public class ForgeProjectile_018 : ForgeTemplateProjectile { public override int SlotIndex => 17; }
    public class ForgeProjectile_019 : ForgeTemplateProjectile { public override int SlotIndex => 18; }
    public class ForgeProjectile_020 : ForgeTemplateProjectile { public override int SlotIndex => 19; }
    public class ForgeProjectile_021 : ForgeTemplateProjectile { public override int SlotIndex => 20; }
    public class ForgeProjectile_022 : ForgeTemplateProjectile { public override int SlotIndex => 21; }
    public class ForgeProjectile_023 : ForgeTemplateProjectile { public override int SlotIndex => 22; }
    public class ForgeProjectile_024 : ForgeTemplateProjectile { public override int SlotIndex => 23; }
    public class ForgeProjectile_025 : ForgeTemplateProjectile { public override int SlotIndex => 24; }
}
