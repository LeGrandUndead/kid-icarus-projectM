# The wide view, made by the game's camera

The PC version shows the top screen at 16:9 and can zoom out ("Gameplay
view", up to 133%). Until October 29 both were made only in the renderer:
it rescaled the projection the game's shaders receive (`raster.rs`,
`kiu_wide_shader`). The game was not told, so it went on culling, aiming
and placing markers for its original 5:3 view. That made:

- enemies pop in at the new edges ([CULLING_AND_POP_IN.md](CULLING_AND_POP_IN.md));
- the mouse aim stay inside the original frame in flight;
- markers and effects drawn by programs the renderer did not know stay in
  the original frame.

## The game's camera

Found October 29 from a flight snapshot. The projection matrix the
shaders get (`0x00E14C58` in chapter 1's air section) is the cache at
`+0x6C` of a camera object (`0x00E14BEC`). The camera belongs to Project
Sora's `psl` library, built on Nintendo's graphics library:

| | Where | What |
|---|---|---|
| camera `+0` | view updater (table `0x00D20068`) | position, target, up |
| camera `+4` | projection updater (table `0x00D20080`, type 1 = perspective) | near `+8`, far `+0xC`, field of view `+0x10` (radians), aspect `+0x14` |
| camera `+0x6C` | projection matrix | built by the updater's method 2, `0x00B4F89C`, through `0x003901C4` |
| camera `+0x10C` | lens cache | near, far, tan(fov/2) `+0x114`, aspect `+0x118`, fov `+0x11C`, from `0x0090DC70` |
| updater method 3 | culling frustum | `0x00B4F948`, planes from the same lens |

The top screen's cameras have aspect 5:3 (the game briefly uses 1.6656 in
camera transitions); the lower screen's have 4:3. The stage parameters
(`0x006F3058`) give the field of view, near and far planes, and the
flight's camera distance and movable area.

## The fix

`tools/recomp/overrides/kiu-wide-view.c` wraps those three functions. Each
runs as the game wrote it, on a widened lens when the runtime asks for one:

- the field of view's half-angle tangent times the zoom (1/scale);
- the aspect times 16/15, for the 16:9 picture.

Drawing, culling, the aim and the markers then all use the same view. The
game's own lens is never changed, so its camera animations go on from
the values they set.

The runtime (`zakuro-core/src/kiu_wide_view.rs`) writes the factors once a
frame to spare bytes after the game's data (`0x00F35F00`; the data and
zeroed data end at `0x00F35D28`). The zoom applies while the game's world
shaders are drawing, as before. When the library reports a widened
projection, the renderer stops rescaling (`kiu_ui::camera::game_view`):

- the world, markers and reticle are left as the game drew them;
- the health bar and score pieces are still narrowed and moved to the
  wide edges.

A library built without the override never reports one, and the renderer
widens the picture as before.

It needs a library rebuild (`tools/recomp/Rebuild-KIU-With-Hints.ps1`,
about two hours); the runtime part works with either library.

## What to check after the rebuild

- The log says once: "wide view: the game's camera widens itself".
- In flight at 133%, the mouse aim reaches the edges of the picture and
  shots go where the reticle is.
- Enemies no longer pop in at the side edges.
- Lock-on markers sit on their enemies near the edges.
- Land play: the camera and aim feel as before.
- Menus and cutscenes look as before, or better proportioned.

## Known limits

- 2D pieces the game draws on the top screen (markers, captions) are
  stretched 16/15 wider by the 16:9 picture, as menus already are. Only
  the health bar and score are corrected.
- Pit's flying area is a fixed size in the game's units (stage parameters
  `airMovableAreaHalfW_`/`H_`), so at 133% he still covers a smaller part
  of the picture.
