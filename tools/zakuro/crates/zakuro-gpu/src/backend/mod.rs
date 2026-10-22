//! presentation backends.

#[cfg(feature = "opengl")]
pub mod gl;
#[cfg(feature = "vulkan")]
pub mod vulkan;
#[cfg(feature = "vulkan")]
mod vulkan_overlay;

/// one screen's pixels, already converted to straight RGBA8, or where they
/// are on the GPU, for a presenter sharing the renderer's device.
pub struct ScreenImage<'a> {
    pub width: u32,
    pub height: u32,
    pub pixels: &'a [u8],
    pub gpu: Option<GpuScreen>,
}

impl ScreenImage<'_> {
    pub fn is_empty(&self) -> bool {
        self.width == 0 || self.height == 0 || (self.pixels.is_empty() && self.gpu.is_none())
    }
}

/// a screen's picture upright in an image of the renderer's, in the general
/// layout, which the Vulkan presenter draws straight from when the two share
/// a device.
#[derive(Debug, Clone, Copy)]
pub struct GpuScreen {
    #[cfg(feature = "vulkan")]
    pub(crate) view: ash::vk::ImageView,
    /// where the screen's pixels lie in the image, as texture coordinates,
    /// the corner and the size, then the corners inset by half a texel,
    /// which filtering keeps within.
    pub(crate) area: [f32; 4],
    pub(crate) bounds: [f32; 4],
}

/// what is drawn over the screens, a user interface, as textured triangles
/// in window pixels.
#[derive(Default)]
pub struct Overlay {
    /// textures to make or change before drawing.
    pub textures: Vec<OverlayTexture>,
    pub meshes: Vec<OverlayMesh>,
    /// textures that go away once this frame is drawn.
    pub free: Vec<u64>,
}

/// pixels for a texture of the overlay.
pub struct OverlayTexture {
    pub id: u64,
    /// where the pixels go in a texture that exists, none to make it anew at
    /// this size.
    pub offset: Option<[u32; 2]>,
    pub size: [u32; 2],
    /// RGBA, premultiplied by alpha, in sRGB.
    pub pixels: Vec<u8>,
    /// filtered when scaled, rather than nearest.
    pub linear: bool,
}

/// one corner of an overlay triangle.
#[repr(C)]
#[derive(Debug, Clone, Copy, Default)]
pub struct OverlayVertex {
    /// window pixels from the top left.
    pub position: [f32; 2],
    pub uv: [f32; 2],
    /// premultiplied sRGB.
    pub color: [u8; 4],
}

/// triangles of the overlay that share a texture and a clip.
pub struct OverlayMesh {
    pub texture: u64,
    /// the part of the window they may draw in, left, top, right, bottom.
    pub clip: [u32; 4],
    pub vertices: Vec<OverlayVertex>,
    pub indices: Vec<u32>,
}

/// where a screen goes in the window, in pixels from the top left.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Viewport {
    pub x: f32,
    pub y: f32,
    pub width: f32,
    pub height: f32,
}

/// how the screens are arranged in the window.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ScreenLayout {
    /// the top screen over the bottom one, as on the console.
    #[default]
    Stacked,
    /// next to each other, the top screen on the left.
    SideBySide,
    /// the top screen alone.
    TopOnly,
    /// Experimental KIU top screen with a matching 16:9 world projection.
    TopWide,
    /// the bottom screen alone.
    BottomOnly,
    /// Temporary original UI panel, composited after the unchanged top view.
    BottomOverlay { wide: bool },
    /// Legacy two-screen composition retaining the already-selected wide view.
    StackedWide,
    /// An out-of-stage menu on one PC screen: the game's upper picture (the
    /// room, previews) fills the window as in gameplay, and the lower one's
    /// menu, drawn without its backgrounds over a transparent buffer
    /// (kiu_ui::menu), is laid over it, large, on the right, clickable.
    MenuScreen { wide: bool },
}

impl ScreenLayout {
    /// the size the screens take up together at the console's resolution.
    pub fn size(self) -> (u32, u32) {
        match self {
            ScreenLayout::Stacked => (400, 480),
            ScreenLayout::SideBySide => (720, 240),
            ScreenLayout::TopOnly => (400, 240),
            ScreenLayout::TopWide => (1280, 720),
            ScreenLayout::BottomOnly => (320, 240),
            ScreenLayout::BottomOverlay { wide } => if wide { (1280,720) } else { (400,240) },
            ScreenLayout::StackedWide => (1280,1440),
            ScreenLayout::MenuScreen { .. } => (1280,720),
        }
    }
}

/// works out where the screens go inside a window, keeping the 3DS's
/// aspect ratio and centring them. a screen that does not show has no place.
pub fn layout(window_width: u32, window_height: u32, arrangement: ScreenLayout) -> (Option<Viewport>, Option<Viewport>) {
    if let ScreenLayout::MenuScreen { wide } = arrangement {
        let (top, _) = layout(window_width, window_height, if wide { ScreenLayout::TopWide } else { ScreenLayout::TopOnly });
        let Some(top) = top else { return (None, None) };
        // the menu at 78% of the view's height, its right edge a margin in
        let height = top.height * 0.78;
        let width = (height * 4.0 / 3.0).min(top.width * 0.9);
        let height = width * 0.75;
        let margin = top.height * 0.04;
        return (Some(top), Some(Viewport { x: top.x + top.width - width - margin,
            y: top.y + (top.height - height) * 0.5, width, height }));
    }
    if arrangement == ScreenLayout::StackedWide {
        let height=(window_height as f32*0.5).min(window_width as f32*9.0/16.0);
        let y=(window_height as f32-2.0*height)*0.5;
        let top_width=height*16.0/9.0;
        let bottom_width=height*4.0/3.0;
        return (Some(Viewport { x:(window_width as f32-top_width)*0.5,y,width:top_width,height }),
            Some(Viewport { x:(window_width as f32-bottom_width)*0.5,y:y+height,width:bottom_width,height }));
    }
    if let ScreenLayout::BottomOverlay { wide } = arrangement {
        let (top, _) = layout(window_width,window_height,
            if wide { ScreenLayout::TopWide } else { ScreenLayout::TopOnly });
        // Readable temporary panel, not a permanent shrunken second screen.
        let height = (window_height as f32 * 0.84).min(window_width as f32 * 0.84 * 0.75);
        let width = height * 4.0 / 3.0;
        return (top, Some(Viewport { x:(window_width as f32-width)*0.5,
            y:(window_height as f32-height)*0.5,width,height }));
    }
    if arrangement == ScreenLayout::TopWide {
        let scale = (window_width as f32 / 16.0).min(window_height as f32 / 9.0);
        let (width, height) = (16.0 * scale, 9.0 * scale);
        return (Some(Viewport { x: (window_width as f32-width)/2.0,
            y: (window_height as f32-height)/2.0, width, height }), None);
    }
    let (total_width, total_height) = arrangement.size();
    let (total_width, total_height) = (total_width as f32, total_height as f32);

    let scale = (window_width as f32 / total_width).min(window_height as f32 / total_height);
    let offset_x = (window_width as f32 - total_width * scale) / 2.0;
    let offset_y = (window_height as f32 - total_height * scale) / 2.0;

    let top = (arrangement != ScreenLayout::BottomOnly).then_some(Viewport {
        x: offset_x,
        y: offset_y,
        width: 400.0 * scale,
        height: 240.0 * scale,
    });
    let bottom = match arrangement {
        // the bottom screen is narrower, so it is centered under the top one.
        ScreenLayout::Stacked => Some(Viewport {
            x: offset_x + 40.0 * scale,
            y: offset_y + 240.0 * scale,
            width: 320.0 * scale,
            height: 240.0 * scale,
        }),
        ScreenLayout::SideBySide => Some(Viewport {
            x: offset_x + 400.0 * scale,
            y: offset_y,
            width: 320.0 * scale,
            height: 240.0 * scale,
        }),
        ScreenLayout::TopOnly | ScreenLayout::TopWide | ScreenLayout::BottomOverlay { .. } | ScreenLayout::StackedWide
            | ScreenLayout::MenuScreen { .. } => None,
        ScreenLayout::BottomOnly => Some(Viewport {
            x: offset_x,
            y: offset_y,
            width: 320.0 * scale,
            height: 240.0 * scale,
        }),
    };
    (top, bottom)
}

/// Whether the lower picture is laid over the upper one by its own
/// coverage (alpha) instead of covering its rectangle.
pub fn bottom_blends(arrangement: ScreenLayout) -> bool { matches!(arrangement, ScreenLayout::MenuScreen { .. }) }

#[derive(Debug, thiserror::Error)]
pub enum PresentError {
    #[error("{0}")]
    Backend(String),
    #[error("the swapchain is out of date and was recreated")]
    OutOfDate,
}

pub trait Presenter {
    fn name(&self) -> &'static str;

    /// draws both screens into the window, and the overlay over them.
    fn present(
        &mut self,
        top: ScreenImage<'_>,
        bottom: ScreenImage<'_>,
        overlay: &Overlay,
    ) -> Result<(), PresentError>;

    /// the window changed size.
    fn resize(&mut self, width: u32, height: u32);

    /// how the screens are arranged from the next frame on.
    fn set_layout(&mut self, arrangement: ScreenLayout);
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn temporary_panel_keeps_both_images_and_touch_aspect_at_any_size() {
        for (w,h) in [(1920,1080),(1280,720),(800,1200),(2560,1080),(640,480)] {
            for wide in [true,false] {
                let (top,bottom)=layout(w,h,ScreenLayout::BottomOverlay { wide });
                let base=layout(w,h,if wide {ScreenLayout::TopWide} else {ScreenLayout::TopOnly}).0;
                assert_eq!(top,base);
                let b=bottom.unwrap();
                assert!((b.width/b.height-4.0/3.0).abs()<0.0001);
                assert!(b.x>=0.0 && b.y>=0.0 && b.x+b.width<=w as f32 && b.y+b.height<=h as f32);
                // Identical inverse mapping is used by frontend touch().
                let x=(b.x+b.width*0.5-b.x)/b.width*320.0;
                let y=(b.y+b.height*0.5-b.y)/b.height*240.0;
                assert!((x-160.0).abs()<0.001 && (y-120.0).abs()<0.001);
            }
        }
    }
    #[test]
    fn a_menu_screen_fills_the_window_with_the_menu_over_the_view() {
        for (w,h) in [(1920,1080),(1280,720),(800,1200),(2560,1080),(640,480)] {
            for wide in [true,false] {
                let (top,bottom)=layout(w,h,ScreenLayout::MenuScreen { wide });
                let view=layout(w,h,if wide {ScreenLayout::TopWide} else {ScreenLayout::TopOnly}).0;
                assert_eq!(top,view, "the upper picture is the whole view, as in gameplay");
                let (t,b)=(top.unwrap(),bottom.unwrap());
                assert!((b.width/b.height-4.0/3.0).abs()<0.0001);
                assert!(b.x>=t.x && b.y>=t.y && b.x+b.width<=t.x+t.width+0.001 && b.y+b.height<=t.y+t.height+0.001);
            }
        }
        let (_,b)=layout(1920,1080,ScreenLayout::MenuScreen { wide: true });
        assert!(b.unwrap().height>800.0, "large enough to read and click at 1080p");
        assert!(bottom_blends(ScreenLayout::MenuScreen { wide: true }) && !bottom_blends(ScreenLayout::TopWide));
    }
    #[test]
    fn legacy_composition_does_not_squeeze_an_existing_wide_camera() {
        let (top,bottom)=layout(1920,1080,ScreenLayout::StackedWide);
        let (top,bottom)=(top.unwrap(),bottom.unwrap());
        assert_eq!(top.width/top.height,16.0/9.0);
        assert_eq!(bottom.width/bottom.height,4.0/3.0);
        assert_eq!(top.y+top.height,bottom.y);
    }
    #[test]
    fn experimental_wide_fills_1080p_without_changing_original_layout() {
        let (top, bottom) = layout(1920, 1080, ScreenLayout::TopWide);
        assert_eq!(top.unwrap(), Viewport { x: 0.0, y: 0.0, width: 1920.0, height: 1080.0 });
        assert!(bottom.is_none());
        let original = layout(1920, 1080, ScreenLayout::TopOnly).0.unwrap();
        assert_eq!(original.width, 1800.0);
        assert_eq!(original.x, 60.0);
        let wide_monitor = layout(2560, 1080, ScreenLayout::TopWide).0.unwrap();
        assert_eq!(wide_monitor.width, 1920.0);
        assert_eq!(wide_monitor.x, 320.0);
    }

    #[test]
    fn layout_keeps_the_aspect_ratio_and_centers() {
        // a window exactly 400x480 needs no scaling or offset.
        let (top, bottom) = layout(400, 480, ScreenLayout::Stacked);
        let (top, bottom) = (top.unwrap(), bottom.unwrap());
        assert_eq!(top.x, 0.0);
        assert_eq!(top.y, 0.0);
        assert_eq!(top.width, 400.0);
        assert_eq!(bottom.y, 240.0);
        assert_eq!(bottom.x, 40.0);
        assert_eq!(bottom.width, 320.0);

        // doubling both dimensions doubles the scale.
        let top = layout(800, 960, ScreenLayout::Stacked).0.unwrap();
        assert_eq!(top.width, 800.0);
        assert_eq!(top.height, 480.0);

        // a window that is too wide letterboxes horizontally.
        let top = layout(1000, 480, ScreenLayout::Stacked).0.unwrap();
        assert_eq!(top.width, 400.0);
        assert_eq!(top.x, 300.0);
    }

    #[test]
    fn the_other_layouts_place_the_screens_their_way() {
        // side by side, the bottom screen starts where the top one ends
        let (top, bottom) = layout(1440, 480, ScreenLayout::SideBySide);
        let (top, bottom) = (top.unwrap(), bottom.unwrap());
        assert_eq!((top.x, top.y, top.width), (0.0, 0.0, 800.0));
        assert_eq!((bottom.x, bottom.y, bottom.width, bottom.height), (800.0, 0.0, 640.0, 480.0));

        // the top screen alone fills a window of its shape, and a taller
        // one centers it
        let (top, bottom) = layout(800, 960, ScreenLayout::TopOnly);
        assert!(bottom.is_none());
        let top = top.unwrap();
        assert_eq!((top.x, top.y, top.width, top.height), (0.0, 240.0, 800.0, 480.0));

        // and so does the bottom screen alone, a wider window centering it
        let (top, bottom) = layout(800, 480, ScreenLayout::BottomOnly);
        assert!(top.is_none());
        let bottom = bottom.unwrap();
        assert_eq!((bottom.x, bottom.y, bottom.width, bottom.height), (80.0, 0.0, 640.0, 480.0));
    }
}
