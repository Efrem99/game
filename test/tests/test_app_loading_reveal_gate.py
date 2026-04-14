from pathlib import Path


ROOT = Path(__file__).absolute().parents[2]


def _finalize_initialization_source():
    content = (ROOT / "src" / "app.py").read_text(encoding="utf-8")
    start = content.index("    def _finalize_initialization(self):")
    end = content.index("    def transition_to_location(self, loc_name):", start)
    return content[start:end]


def test_loading_screen_hides_only_after_post_finalize_visual_stabilization():
    source = _finalize_initialization_source()

    hide_idx = source.index("self.loading_screen.hide()")
    stabilize_idx = source.index("self._stabilize_post_finalize_scene_visuals()")
    guard_idx = source.index('self._guard_runtime_scene_with_label("Post-finalize cursor guard")')
    final_vis_idx = source.index('logger.info(f"Final Vis - Playing: True, Loading: {not self.loading_screen.frame.isHidden()}")')

    assert stabilize_idx < hide_idx
    assert guard_idx < hide_idx
    assert hide_idx < final_vis_idx
