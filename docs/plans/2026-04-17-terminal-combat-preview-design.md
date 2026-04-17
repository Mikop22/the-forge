# Terminal Combat Preview Design

## Goal

Add a pre-inject combat preview to the Bubble Tea staging screen so a user can see how a forged weapon feels before sending it into Terraria.

The preview should act like a workbench audition: it should show the generated item sprite swinging, thrusting, shooting, or casting, and show the projectile sprite moving across a small Terraria-like scene. The first version should be a terminal-native simulator, not a Terraria runtime capture.

## Product Behavior

After a forge completes and the bench has renderable content, the staging screen should show:

- the current item name and metadata
- a looping combat preview
- the item sprite and projectile sprite preview panels
- stats
- the existing `/try`, `/variants`, and `/forge` command flow

The core decision point is:

`Forge completes -> TUI shows static sprite + animated combat preview -> user chooses /try, /variants, or /forge again`

The preview should never imply that the item has already been injected. It is a pre-inject approximation built from the same manifest and PNG assets that will later be used by the connector.

## Architecture

Keep the first version entirely inside `BubbleTeaTerminal/`. The TUI already has:

- a periodic animation tick in `main.go`
- item/projectile paths in the model
- PNG decoding and half-block rendering in `screen_staging.go`
- manifest stats including `use_time`

The new code should introduce a small terminal canvas layer. It should compose an RGBA scene in memory, draw sprites into that scene with simple transforms, then render the scene using the existing half-block style. This keeps rendering terminal-compatible and avoids Kitty/Sixel/iTerm-specific behavior.

The preview should be deterministic from item data:

- `subType` and manifest use style choose the animation profile
- `use_time` and `use_animation` choose timing
- `spritePath` supplies the held item art
- `projSpritePath` supplies the projectile art
- projectile speed and subtype choose projectile motion

## Animation Profiles

Start with four profiles:

- `Swing`: swords and general melee weapons rotate through a compact arc around a hand anchor.
- `Thrust`: spears and thrust weapons move forward and back with a slight rotation.
- `Shoot`: guns, bows, and staves hold the item forward, flash briefly, then emit a projectile.
- `ProjectileTravel`: projectile sprite travels away from the player with rotation derived from velocity.

These profiles are intentionally approximate. They should communicate shape, scale, orientation, readability, projectile direction, and timing before the user injects the item.

## Runtime Source Of Truth

Terraria should become the source of truth later, not first.

A later live audition mode can ask ForgeConnector to load a temporary preview slot and emit runtime telemetry from actual item use. That would validate the exact in-game behavior, but it is still a form of runtime handoff. The pre-inject terminal simulator is more valuable as the first step because it answers the user’s immediate question before they touch the game.

## Error Handling

If a sprite is missing or unreadable, the preview should degrade gracefully:

- no item sprite: render a simple colored placeholder weapon
- no projectile sprite: render only the held item motion
- no projectile mechanics: render only swing/thrust/hold animation
- small terminal: hide the animated preview before breaking layout

The existing static sprite and stats panels should continue to render even if the animation preview cannot.

## Testing

Tests should focus on deterministic rendering decisions rather than visual perfection:

- profile selection from subtype and content type
- frame progression from `animTick`
- no over-wide lines in compact terminals
- missing sprite paths do not panic
- preview output appears only when bench content exists
- canvas compositor handles transparency and bounds

Manual verification should run the Bubble Tea app in a terminal and check sword, spear, gun/bow/staff, and projectile examples.
