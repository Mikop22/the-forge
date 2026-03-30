using Terraria;
using Terraria.ModLoader;

namespace ForgeConnector.Content.Items
{
    /// <summary>
    /// Base class for template item slots. Each subclass provides a unique SlotIndex.
    /// Real stats are applied at runtime by ForgeItemGlobal from the manifest store.
    /// </summary>
    public abstract class ForgeTemplateItem : ModItem
    {
        public abstract int SlotIndex { get; }

        public override void SetDefaults()
        {
            Item.width = 32;
            Item.height = 32;
            Item.maxStack = 1;
        }
    }

    // 50 template slots (ForgeItem_001 through ForgeItem_050)
    public class ForgeItem_001 : ForgeTemplateItem { public override int SlotIndex => 0; }
    public class ForgeItem_002 : ForgeTemplateItem { public override int SlotIndex => 1; }
    public class ForgeItem_003 : ForgeTemplateItem { public override int SlotIndex => 2; }
    public class ForgeItem_004 : ForgeTemplateItem { public override int SlotIndex => 3; }
    public class ForgeItem_005 : ForgeTemplateItem { public override int SlotIndex => 4; }
    public class ForgeItem_006 : ForgeTemplateItem { public override int SlotIndex => 5; }
    public class ForgeItem_007 : ForgeTemplateItem { public override int SlotIndex => 6; }
    public class ForgeItem_008 : ForgeTemplateItem { public override int SlotIndex => 7; }
    public class ForgeItem_009 : ForgeTemplateItem { public override int SlotIndex => 8; }
    public class ForgeItem_010 : ForgeTemplateItem { public override int SlotIndex => 9; }
    public class ForgeItem_011 : ForgeTemplateItem { public override int SlotIndex => 10; }
    public class ForgeItem_012 : ForgeTemplateItem { public override int SlotIndex => 11; }
    public class ForgeItem_013 : ForgeTemplateItem { public override int SlotIndex => 12; }
    public class ForgeItem_014 : ForgeTemplateItem { public override int SlotIndex => 13; }
    public class ForgeItem_015 : ForgeTemplateItem { public override int SlotIndex => 14; }
    public class ForgeItem_016 : ForgeTemplateItem { public override int SlotIndex => 15; }
    public class ForgeItem_017 : ForgeTemplateItem { public override int SlotIndex => 16; }
    public class ForgeItem_018 : ForgeTemplateItem { public override int SlotIndex => 17; }
    public class ForgeItem_019 : ForgeTemplateItem { public override int SlotIndex => 18; }
    public class ForgeItem_020 : ForgeTemplateItem { public override int SlotIndex => 19; }
    public class ForgeItem_021 : ForgeTemplateItem { public override int SlotIndex => 20; }
    public class ForgeItem_022 : ForgeTemplateItem { public override int SlotIndex => 21; }
    public class ForgeItem_023 : ForgeTemplateItem { public override int SlotIndex => 22; }
    public class ForgeItem_024 : ForgeTemplateItem { public override int SlotIndex => 23; }
    public class ForgeItem_025 : ForgeTemplateItem { public override int SlotIndex => 24; }
    public class ForgeItem_026 : ForgeTemplateItem { public override int SlotIndex => 25; }
    public class ForgeItem_027 : ForgeTemplateItem { public override int SlotIndex => 26; }
    public class ForgeItem_028 : ForgeTemplateItem { public override int SlotIndex => 27; }
    public class ForgeItem_029 : ForgeTemplateItem { public override int SlotIndex => 28; }
    public class ForgeItem_030 : ForgeTemplateItem { public override int SlotIndex => 29; }
    public class ForgeItem_031 : ForgeTemplateItem { public override int SlotIndex => 30; }
    public class ForgeItem_032 : ForgeTemplateItem { public override int SlotIndex => 31; }
    public class ForgeItem_033 : ForgeTemplateItem { public override int SlotIndex => 32; }
    public class ForgeItem_034 : ForgeTemplateItem { public override int SlotIndex => 33; }
    public class ForgeItem_035 : ForgeTemplateItem { public override int SlotIndex => 34; }
    public class ForgeItem_036 : ForgeTemplateItem { public override int SlotIndex => 35; }
    public class ForgeItem_037 : ForgeTemplateItem { public override int SlotIndex => 36; }
    public class ForgeItem_038 : ForgeTemplateItem { public override int SlotIndex => 37; }
    public class ForgeItem_039 : ForgeTemplateItem { public override int SlotIndex => 38; }
    public class ForgeItem_040 : ForgeTemplateItem { public override int SlotIndex => 39; }
    public class ForgeItem_041 : ForgeTemplateItem { public override int SlotIndex => 40; }
    public class ForgeItem_042 : ForgeTemplateItem { public override int SlotIndex => 41; }
    public class ForgeItem_043 : ForgeTemplateItem { public override int SlotIndex => 42; }
    public class ForgeItem_044 : ForgeTemplateItem { public override int SlotIndex => 43; }
    public class ForgeItem_045 : ForgeTemplateItem { public override int SlotIndex => 44; }
    public class ForgeItem_046 : ForgeTemplateItem { public override int SlotIndex => 45; }
    public class ForgeItem_047 : ForgeTemplateItem { public override int SlotIndex => 46; }
    public class ForgeItem_048 : ForgeTemplateItem { public override int SlotIndex => 47; }
    public class ForgeItem_049 : ForgeTemplateItem { public override int SlotIndex => 48; }
    public class ForgeItem_050 : ForgeTemplateItem { public override int SlotIndex => 49; }
}
