using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeConnector.Content.Buffs
{
    /// <summary>
    /// Base class for template buff slots. Each subclass provides a unique SlotIndex.
    /// Real runtime behavior is applied from ForgeManifestStore.
    /// </summary>
    public abstract class ForgeTemplateBuff : ModBuff
    {
        public abstract int SlotIndex { get; }

        public override void SetStaticDefaults()
        {
            Main.buffNoSave[Type] = true;
            Main.buffNoTimeDisplay[Type] = true;
        }

        public override void Update(Player player, ref int buffIndex)
        {
            var data = ForgeManifestStore.GetBuff(SlotIndex);
            if (data == null)
                return;

            int projectileTypeId = ResolveMinionProjectileTypeId(data);
            if (projectileTypeId <= 0)
            {
                player.DelBuff(buffIndex);
                buffIndex--;
                return;
            }

            if (player.ownedProjectileCounts[projectileTypeId] > 0)
            {
                player.buffTime[buffIndex] = data.BuffTime > 0 ? data.BuffTime : 18000;
            }
            else
            {
                player.DelBuff(buffIndex);
                buffIndex--;
            }
        }

        private static int ResolveMinionProjectileTypeId(ForgeBuffData data)
        {
            if (data.MinionProjectileTypeId > 0)
                return data.MinionProjectileTypeId;

            if (data.MinionProjectileSlot >= 0)
                return ForgeManifestStore.GetProjectileTypeId(data.MinionProjectileSlot);

            return -1;
        }
    }

    public class ForgeBuff_001 : ForgeTemplateBuff { public override int SlotIndex => 0; }
    public class ForgeBuff_002 : ForgeTemplateBuff { public override int SlotIndex => 1; }
    public class ForgeBuff_003 : ForgeTemplateBuff { public override int SlotIndex => 2; }
    public class ForgeBuff_004 : ForgeTemplateBuff { public override int SlotIndex => 3; }
    public class ForgeBuff_005 : ForgeTemplateBuff { public override int SlotIndex => 4; }
    public class ForgeBuff_006 : ForgeTemplateBuff { public override int SlotIndex => 5; }
    public class ForgeBuff_007 : ForgeTemplateBuff { public override int SlotIndex => 6; }
    public class ForgeBuff_008 : ForgeTemplateBuff { public override int SlotIndex => 7; }
    public class ForgeBuff_009 : ForgeTemplateBuff { public override int SlotIndex => 8; }
    public class ForgeBuff_010 : ForgeTemplateBuff { public override int SlotIndex => 9; }
    public class ForgeBuff_011 : ForgeTemplateBuff { public override int SlotIndex => 10; }
    public class ForgeBuff_012 : ForgeTemplateBuff { public override int SlotIndex => 11; }
    public class ForgeBuff_013 : ForgeTemplateBuff { public override int SlotIndex => 12; }
    public class ForgeBuff_014 : ForgeTemplateBuff { public override int SlotIndex => 13; }
    public class ForgeBuff_015 : ForgeTemplateBuff { public override int SlotIndex => 14; }
    public class ForgeBuff_016 : ForgeTemplateBuff { public override int SlotIndex => 15; }
    public class ForgeBuff_017 : ForgeTemplateBuff { public override int SlotIndex => 16; }
    public class ForgeBuff_018 : ForgeTemplateBuff { public override int SlotIndex => 17; }
    public class ForgeBuff_019 : ForgeTemplateBuff { public override int SlotIndex => 18; }
    public class ForgeBuff_020 : ForgeTemplateBuff { public override int SlotIndex => 19; }
    public class ForgeBuff_021 : ForgeTemplateBuff { public override int SlotIndex => 20; }
    public class ForgeBuff_022 : ForgeTemplateBuff { public override int SlotIndex => 21; }
    public class ForgeBuff_023 : ForgeTemplateBuff { public override int SlotIndex => 22; }
    public class ForgeBuff_024 : ForgeTemplateBuff { public override int SlotIndex => 23; }
    public class ForgeBuff_025 : ForgeTemplateBuff { public override int SlotIndex => 24; }
}
