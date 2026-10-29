# The white screen after warps (60 FPS mode)

In chapter 9 (Pandora), taking a warp sometimes left the screen white for
many seconds while the game went on underneath. It happened only with the
60 FPS mode on.

## What the game does on a warp

The warp pad plays a short animation script. Chapter 9's
`YAK_G09_Warp_G05_00`, read out of a memory snapshot:

```text
EventPlayerStop, PlaySE
StartFade   out to white over 16 frames     anime_command::StartFade 0x00AEAD80
WaitFrame   16                              anime_command::WaitFrame
Warp        the player sent to the exit     anime_command::Warp 0x00AE0090
WaitFrame   4
StartFade   back in over 16 frames
EventPlayerStop, ...
```

`StartFade` drives the screen fader (singleton `0x00D63620`, a fader per
screen at `+0xB8`): per layer (`0x48` bytes) and slot (4 bytes), the colour
at `+0x1C`, the amount at `+0x2C`, the target at `+0x3C` and the change per
frame at `+0x4C`.

## What went wrong

A trace of every fade (October 29) caught the white: the script's fade-out
to white at 1/16 a frame, and no fade back in for 660 frames. Two memory
snapshots of an earlier white (October 28) had the fader still fading out
after 548 frames, and the warp script's commands loaded with nothing running
them: the script was cut off after `Warp` and never reached its fade back
in. Every normal warp in the trace faded back in about 64 frames after
fading out.

Why the script is cut off at 60 FPS is not pinned down. The likeliest
reading is a race between the pad's script and the player leaving: after
`Warp` the script still has 4 frames to wait, two game updates at 30 and
four at 60, and the pad stops updating once the player is gone.

## The fix

`zakuro-core/src/kiu_warp_fade.rs` finishes the script's own fade. When a
`StartFade` fades out and its script goes on to a `Warp` and then a
`StartFade` back in on the same screen and layer, the fade-in is due once
the waits in between have passed (20 frames for the script above). If the
fader is still faded out half a second after that, the fade-in is started
as the command would: target 0, `-1/frames` a frame. Scripts that fade back
in on time are left alone, and so is every fade that is not a warp's.

It sees fades start by watching writes to the faders' rates; the stack says
whether `StartFade` asked, and which command. Tests:
`cargo test -p zakuro-core kiu_warp_fade`.
