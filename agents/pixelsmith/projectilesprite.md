Here is a master markdown reference guide you can save and keep open while you are drawing sprites and coding in tModLoader. It covers the standard conventions for getting your artwork to behave properly in the Terraria engine.

---

# The tModLoader Projectile Sprite Master Guide

Terraria handles image rotation by pivoting sprites based on mathematical angles. Because of this, **how you draw the sprite on the canvas is just as important as the code you write.**

## 1. Universal Golden Rules for the Canvas

Before drawing any specific type of projectile, always follow these baseline rules:

* **Crop Your Canvas:** Never leave excess transparent space around your sprite. If your artwork is 14x40 pixels, your `.png` file must be exactly 14x40. Blank space throws off the game's default center-point calculations.
* **Even Numbers are Best:** Try to make your canvas dimensions even numbers (e.g., 16x16, 30x40). It makes finding the exact pixel center for rotations and hitboxes much cleaner.
* **Point the Tip Outward:** Always draw the "business end" (the pointy part) facing away from the center of the canvas.

---

## 2. Directional Projectiles (Arrows, Bullets, Magic Bolts)

These are projectiles that need to point dynamically in the exact direction they are flying based on your mouse cursor.

**Option A: The "Straight Up" Convention (Recommended)**

* **How to Draw:** Pointing straight up at 12 o'clock.
* **The Code:** `Projectile.rotation = Projectile.velocity.ToRotation() + MathHelper.PiOver2;`

**Option B: The "Straight Right" Convention**

* **How to Draw:** Pointing perfectly to the right at 3 o'clock. (Terraria's base math assumes 0 degrees is pointing right).
* **The Code:** `Projectile.rotation = Projectile.velocity.ToRotation();`

---

## 3. Thrown Weapons & Spears (Javelins, Knives)

If a projectile is meant to look exactly like the item the player is holding in their hand, you must draw it on a diagonal.

* **How to Draw:** Pointing diagonally to the **top-right corner (45 degrees)**.
* **The Reason:** Terraria's inventory icons and hand-held sprites default to this 45-degree angle. By drawing your projectile the same way, you can use the exact same `.png` for both the item and the projectile.
* **The Code:** `Projectile.rotation = Projectile.velocity.ToRotation() + MathHelper.PiOver4;`

---

## 4. Spinning Projectiles (Boomerangs, Yoyos, Chakrams)

These projectiles rotate continuously in the air rather than pointing in their travel direction.

* **How to Draw:** The orientation does not matter, but **the artwork must be perfectly centered** in the canvas.
* **The Reason:** If the sprite is heavier on one side of the transparent canvas, the axis of rotation will be off-center, causing it to wobble awkwardly like a broken wheel.
* **The Code:** `Projectile.rotation += 0.4f * (float)Projectile.direction;` (You manually add to the rotation every frame; tweak the `0.4f` to spin faster or slower).

---

## 5. Sword & Melee Projectiles

Modern Terraria swords often spawn projectiles rather than just using a simple invisible hitbox.

**Sword Beams (e.g., Terra Blade)**

* **How to Draw:** Top-right corner (45 degrees), exactly like the physical sword sprite.
* **The Code:** `Projectile.rotation = Projectile.velocity.ToRotation() + MathHelper.PiOver4;`

**Sweeping Arcs (e.g., 1.4 Broadswords)**

* **How to Draw:** A crescent or half-moon shape pointing straight up (12 o'clock) or straight right (3 o'clock).
* **The Code:** Do not use `velocity`. Calculate the percentage of the player's swing animation, and mathematically rotate the sprite in a semi-circle around the player's center.

**Stabbing Rapiers / Shortswords**

* **How to Draw:** Top-right corner (45 degrees).
* **The Code:** `Projectile.rotation = Projectile.velocity.ToRotation() + MathHelper.PiOver4;`

---

---
