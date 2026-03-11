Here is your master markdown reference guide for drawing **weapon and item sprites** in Terraria.

While projectiles have a lot of weird math depending on how they fly, weapons are generally much simpler. For about 90% of the weapons in the game, there is one golden rule: **Bottom-Left to Top-Right**.

---

# The tModLoader Weapon Sprite Master Guide

## 1. Universal Golden Rules for Weapon Canvases

Before drawing your weapons, always keep these engine quirks in mind:

* **The "Bottom-Left" Grip:** Terraria assumes the player is holding the weapon by the bottom-left corner of the image canvas. If you center your sword like a standard RPG icon, the player will hold it by the middle of the blade.
* **Crop Tight to the Handle:** Do not leave empty transparent pixels in the bottom-left corner. The player's hand will spawn exactly where the first non-transparent pixel begins in that corner.
* **Keep Sizes Reasonable:** Standard Terraria weapons are usually drawn on canvases between `32x32` and `64x64` pixels. If you draw a massive `128x128` sword, it will drag through the floor. (If you want a giant weapon, draw it normally and use `Item.scale = 2f;` in the code).

---

## 2. Melee Weapons

**Swords, Pickaxes, and Axes**

* **How to Draw:** Pointing diagonally toward the **top-right corner (45 degrees)**.
* **The Setup:** The pommel/handle must be in the absolute bottom-left corner.
* **The Code:** `Item.useStyle = ItemUseStyleID.Swing;` (The game will automatically pivot it from behind the player's back to in front of them).

**Spears and Shortswords (Stabbing Weapons)**

* **How to Draw:** Pointing diagonally toward the **top-right corner (45 degrees)**.
* **The Setup:** Handle in the bottom-left.
* **The Code:** `Item.useStyle = ItemUseStyleID.Rapier;` or `ItemUseStyleID.Shoot;` (Depending on if you are using 1.4 projectile mechanics). The game will automatically level the sprite out to point at the mouse cursor.

**Yoyos and Flails**

* **How to Draw:** The item icon (what you see in the inventory) is usually just the yoyo body **centered** in the canvas, or a flail ball sitting in the middle with a bit of chain.
* **The Code:** The actual string and swinging mechanics are entirely handled by the projectile code, not the item sprite.

---

## 3. Ranged Weapons

**Guns and Launchers**

* **How to Draw:** Pointing perfectly to the **right (3 o'clock)**.
* **The Setup:** The grip/trigger should be near the bottom-left, but the barrel must be perfectly horizontal. Terraria naturally holds these weapons level.
* **The Code:** `Item.useStyle = ItemUseStyleID.Shoot;`

**Bows**

* **How to Draw:** Usually drawn pointing **straight up (12 o'clock)** or slightly tilted to the right.
* **The Setup:** The game will automatically rotate the bow to face your cursor when you draw an arrow.

---

## 4. Magic and Summon Weapons

**Staves (e.g., your Staff of Limitless Light)**

* **How to Draw:** Pointing diagonally toward the **top-right corner (45 degrees)**.
* **The Setup:** Handle in the bottom-left.
* **The Code:** You must include `Item.staff[Type] = true;` in your `SetStaticDefaults()`. If you forget this line, the player will swing the staff over their head like a broadsword instead of holding it upright like a wizard.

**Spell Tomes / Books**

* **How to Draw:** Drawn perfectly upright and centered in the canvas, showing the spine or cover.
* **The Code:** `Item.useStyle = ItemUseStyleID.Shoot;` The game knows to hold books out flat in the player's palm.

